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
    TestRunResult,
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


class _TestRunnerProto(Protocol):
    """Minimal test runner interface Chief optionally depends on."""

    async def run(
        self, files: list[GeneratedFile]
    ) -> TestRunResult:  # pragma: no cover - protocol
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
    test_run: TestRunResult | None = None
    test_findings: list[Finding] = field(default_factory=list)
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
            "test_run": self.test_run,
            "test_findings": list(self.test_findings),
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
        test_runner: _TestRunnerProto | None = None,
    ) -> None:
        self.client = client
        self.progress = progress
        self.test_runner = test_runner

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

    # ── optional auto-execute-tests phase ───────────────────────────────

    async def do_execute_tests(self, state: ChiefState) -> None:
        """Run the generated test suite in an isolated environment.

        Only invoked if a ``test_runner`` was provided. Result lands in
        ``state.test_run``; if any tests failed, they're also converted
        into ``state.test_findings`` (severity=block, rule=TEST_FAIL)
        for the next fixer pass to consume.
        """
        assert self.test_runner is not None, "Chief invariant: test runner required"
        await self._route(
            "implementers", "test_runner", "execute pytest in isolated venv"
        )
        await self._emit(
            "test.start", "Running generated tests in isolated venv…"
        )

        result = await self.test_runner.run(state.files_final)
        state.test_run = result

        if not result.ran:
            await self._emit(
                "test.skipped", f"Skipped: {result.skip_reason or 'unknown reason'}"
            )
            return
        if result.passed:
            await self._emit(
                "test.done",
                f"All tests passed (exit={result.exit_code}, {result.duration_s:.1f}s)",
            )
            return

        # Convert each TestFailure into a Finding the fixer agent can consume.
        test_findings: list[Finding] = []
        for tf in result.failures:
            test_findings.append(
                Finding(
                    file=tf.file_path,
                    severity="block",
                    line=None,
                    rule="TEST_FAIL",
                    message=f"{tf.test_name} — {tf.error_excerpt}".strip(" —"),
                )
            )
        # If parsing didn't find specific failures but exit_code != 0,
        # synthesize a single catch-all finding so the fixer still gets context.
        if not test_findings:
            test_findings.append(
                Finding(
                    file="(test suite)",
                    severity="block",
                    line=None,
                    rule="TEST_FAIL",
                    message=(
                        f"pytest exited non-zero ({result.exit_code}). "
                        f"Last output: {result.raw_output[-1000:]}"
                    ),
                )
            )
        state.test_findings = test_findings
        await self._emit(
            "test.failed",
            f"{len(test_findings)} test failure(s) captured (exit={result.exit_code})",
        )

    async def do_fix_from_tests(self, state: ChiefState) -> None:
        """Re-run the implementers, this time with test failures as findings."""
        assert state.spec is not None and state.plan is not None
        await self._route(
            "test_runner",
            "implementers",
            f"third pass on {len(state.test_findings)} test failures",
        )
        await self._emit(
            "retest_fix.start", "Implementers patching failing tests in parallel…"
        )

        async def one(domain: Domain) -> list[GeneratedFile]:
            assert state.spec is not None and state.plan is not None
            domain_files = [f for f in state.files_final if f.owner == domain]
            out: FixOutput = await run_fixer(
                self.client,
                state.spec,
                state.plan,
                domain,
                domain_files,
                state.test_findings,
            )
            await self._emit(
                "retest_fix.domain.done",
                f"{domain}: addressed {len(out.addressed_findings)}, "
                f"deferred {len(out.deferred_findings)}",
            )
            return out.files

        results = await asyncio.gather(*(one(d) for d in DOMAINS))
        merged: list[GeneratedFile] = []
        for fs in results:
            merged.extend(fs)
        # Defensive merge: keep any prior file the fixer dropped.
        seen = {f.path for f in merged}
        for f in state.files_final:
            if f.path not in seen:
                merged.append(f)

        state.files_final = merged
        await self._emit(
            "retest_fix.done",
            f"final has {len(merged)} files (after test-fix iteration)",
        )

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
            if self.test_runner is not None:
                await self.do_execute_tests(state)
                if (
                    state.test_run is not None
                    and state.test_run.ran
                    and not state.test_run.passed
                ):
                    await self.do_fix_from_tests(state)
            await self._emit("chief.done", "Pipeline complete")
            return state
        except Exception as e:
            await self._emit("chief.error", f"{type(e).__name__}: {e}")
            raise
