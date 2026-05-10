"""Chief Orchestrator — the single agent every other agent talks to.

## Why this exists

In the previous version the workflow was a LangGraph state machine that
called role functions directly. Functionally that already routes everything
through one place (the workflow), but visually it doesn't look like
"hub-and-spoke" — to a reader it's not obvious that, say, the Architect
never talks to the Backend implementer.

`ChiefOrchestrator` makes that invariant explicit:

  * Every inter-role transition is a method on this class.
  * Roles never import each other. They only return artifacts to Chief.
  * Chief is the only object that calls `LLMClient`. Roles construct
    prompts; Chief executes them.
  * Every routing emits a `chief.route` event so the UI/CLI can show
    a live trace of the topology.

The shape is hub-and-spoke:

       ┌────────────────────────┐
       │                        │
   Product ──▶ Chief ◀── Architect
                │ ▲
       ┌────────┘ └────────┐
       ▼                   ▼
   Implementers       Reviewers
   (BE/FE/DO/QA)      (Reviewer + Security)

No edge between any two non-Chief nodes exists. Period.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from .agents import (
    run_architect,
    run_fixer,
    run_implementer,
    run_product,
    run_reviewer,
    run_security,
)
from .schemas import (
    Domain,
    Finding,
    FixOutput,
    GeneratedFile,
    ImplementerOutput,
    Plan,
    ReviewOutput,
    Spec,
)

logger = logging.getLogger(__name__)

DOMAINS: tuple[Domain, ...] = ("backend", "frontend", "devops", "qa")

ProgressFn = Callable[[str, str], Awaitable[None] | None]

T = TypeVar("T", bound=BaseModel)


class _ClientProto(Protocol):
    """Minimal LLM client interface Chief depends on."""

    async def call_structured(
        self, *, role: str, user_message: str, schema: type[T], **kwargs: Any
    ) -> T:  # pragma: no cover - protocol
        ...

    async def close(self) -> None:  # pragma: no cover - protocol
        ...


@dataclass
class ChiefState:
    """The single source of truth, owned by Chief, never shared with roles."""

    idea: str
    spec: Spec | None = None
    plan: Plan | None = None
    files_v1: list[GeneratedFile] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    files_final: list[GeneratedFile] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Snapshot, used by workflow.run_workflow to return a state dict."""
        return {
            "idea": self.idea,
            "spec": self.spec,
            "plan": self.plan,
            "files_v1": list(self.files_v1),
            "findings": list(self.findings),
            "files_final": list(self.files_final),
            "notes": list(self.notes),
        }


class ChiefOrchestrator:
    """The only object that knows the full pipeline shape.

    Roles never call each other. They return artifacts to Chief; Chief
    decides who runs next, what data they receive, and how their output
    is merged.
    """

    def __init__(
        self,
        client: _ClientProto,
        progress: ProgressFn | None = None,
    ) -> None:
        self.client = client
        self.progress = progress

    # ── routing primitives ──────────────────────────────────────────────

    async def _emit(self, event: str, detail: str) -> None:
        if self.progress is None:
            return
        res = self.progress(event, detail)
        if asyncio.iscoroutine(res):
            await res

    async def _route(self, frm: str, to: str, what: str) -> None:
        """Single, audited inter-role transition.

        Every cross-role hand-off in the system goes through this method.
        Grep for `chief.route` to enumerate the entire topology.
        """
        await self._emit("chief.route", f"{frm} → {to}: {what}")
        logger.info("chief.route %s → %s :: %s", frm, to, what)

    # ── phase methods (each owns a single role hop) ────────────────────

    async def do_spec(self, state: ChiefState) -> None:
        await self._route("idea", "product", "draft Spec")
        await self._emit("spec.start", "Product Lead is drafting the spec…")
        spec = await run_product(self.client, state.idea)
        state.spec = spec
        await self._emit("spec.done", f"Spec ready: {spec.name}")

    async def do_plan(self, state: ChiefState) -> None:
        assert state.spec is not None, "Chief invariant: spec must precede plan"
        await self._route("product", "architect", "decompose Spec → Plan")
        await self._emit("plan.start", "Architect is decomposing into files…")
        plan = await run_architect(self.client, state.spec)
        state.plan = plan
        domains_used = {f.owner for f in plan.files}
        await self._emit(
            "plan.done",
            f"Plan ready: {len(plan.files)} files across {len(domains_used)} domains",
        )

    async def do_implement(self, state: ChiefState) -> None:
        assert state.spec is not None and state.plan is not None
        await self._route(
            "architect",
            "implementers",
            f"4 domains in parallel ({', '.join(DOMAINS)})",
        )
        await self._emit(
            "implement.start", "4 implementers writing code in parallel…"
        )

        async def one(domain: Domain) -> tuple[Domain, list[GeneratedFile], str]:
            assert state.spec is not None and state.plan is not None
            out: ImplementerOutput = await run_implementer(
                self.client, state.spec, state.plan, domain
            )
            await self._emit(
                "implement.domain.done",
                f"{domain}: {len(out.files)} files",
            )
            return domain, out.files, out.notes

        results = await asyncio.gather(*(one(d) for d in DOMAINS))
        files: list[GeneratedFile] = []
        notes: list[str] = []
        for domain, fs, n in results:
            files.extend(fs)
            if n:
                notes.append(f"[{domain}] {n}")
        state.files_v1 = files
        state.notes = notes
        await self._emit("implement.done", f"v1 has {len(files)} files")

    async def do_review(self, state: ChiefState) -> None:
        assert state.spec is not None
        await self._route(
            "implementers", "reviewers", "Reviewer + Security audit (parallel)"
        )
        await self._emit("review.start", "Reviewer + Security auditing…")

        rev_out: ReviewOutput
        sec_out: ReviewOutput
        rev_out, sec_out = await asyncio.gather(
            run_reviewer(self.client, state.spec, state.files_v1),
            run_security(self.client, state.spec, state.files_v1),
        )
        findings = list(rev_out.findings) + list(sec_out.findings)
        state.findings = findings
        await self._emit(
            "review.done",
            f"{len(findings)} findings ({len(rev_out.findings)} review + {len(sec_out.findings)} security)",
        )

    async def do_fix(self, state: ChiefState) -> None:
        assert state.spec is not None and state.plan is not None
        await self._route(
            "reviewers", "implementers", f"second pass on {len(state.findings)} findings"
        )
        await self._emit("fix.start", "Implementers revising in parallel…")

        async def one(domain: Domain) -> list[GeneratedFile]:
            assert state.spec is not None and state.plan is not None
            domain_files = [f for f in state.files_v1 if f.owner == domain]
            out: FixOutput = await run_fixer(
                self.client,
                state.spec,
                state.plan,
                domain,
                domain_files,
                state.findings,
            )
            await self._emit(
                "fix.domain.done",
                f"{domain}: addressed {len(out.addressed_findings)}, "
                f"deferred {len(out.deferred_findings)}",
            )
            return out.files

        results = await asyncio.gather(*(one(d) for d in DOMAINS))
        final: list[GeneratedFile] = []
        for fs in results:
            final.extend(fs)

        # Defensive merge: keep any v1 files the fixer dropped on the floor.
        seen = {f.path for f in final}
        for f in state.files_v1:
            if f.path not in seen:
                final.append(f)

        state.files_final = final
        await self._emit("fix.done", f"final has {len(final)} files")

    # ── top-level entrypoint ────────────────────────────────────────────

    async def run(self, idea: str) -> ChiefState:
        """Orchestrate the entire pipeline for one idea, end to end."""
        await self._emit("chief.start", "Chief Orchestrator activated")
        state = ChiefState(idea=idea)
        try:
            await self.do_spec(state)
            await self.do_plan(state)
            await self.do_implement(state)
            await self.do_review(state)
            await self.do_fix(state)
            await self._emit("chief.done", "Pipeline complete")
            return state
        except Exception as e:
            await self._emit("chief.error", f"{type(e).__name__}: {e}")
            raise
