"""LangGraph workflow that wires the 8 agents together.

Pipeline:
    INTAKE → SPEC → PLAN → IMPLEMENT (4 parallel) → REVIEW (2 parallel) →
        FIX (4 parallel) → WRITE → DONE
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .agents import (
    run_architect,
    run_fixer,
    run_implementer,
    run_product,
    run_reviewer,
    run_security,
)
from .llm import LLMClient
from .schemas import (
    Domain,
    Finding,
    GeneratedFile,
    Plan,
    Spec,
)

logger = logging.getLogger(__name__)

DOMAINS: tuple[Domain, ...] = ("backend", "frontend", "devops", "qa")


class OrgState(TypedDict, total=False):
    idea: str
    spec: Spec
    plan: Plan
    files_v1: list[GeneratedFile]
    findings: list[Finding]
    files_final: list[GeneratedFile]
    notes: list[str]


# Optional progress hook so the CLI can show what's happening.
ProgressFn = Callable[[str, str], Awaitable[None] | None]


def _maybe_await(result: Any) -> Awaitable[None]:
    async def _noop() -> None:
        return None

    if asyncio.iscoroutine(result):
        return result
    return _noop()


async def _emit(progress: ProgressFn | None, event: str, detail: str) -> None:
    if progress is None:
        return
    res = progress(event, detail)
    if asyncio.iscoroutine(res):
        await res


def build_workflow(client: LLMClient, progress: ProgressFn | None = None):
    """Compile a LangGraph state machine bound to this LLMClient."""

    async def node_spec(state: OrgState) -> OrgState:
        await _emit(progress, "spec.start", "Product Lead is drafting the spec…")
        spec = await run_product(client, state["idea"])
        await _emit(progress, "spec.done", f"Spec ready: {spec.name}")
        return {"spec": spec}

    async def node_plan(state: OrgState) -> OrgState:
        await _emit(progress, "plan.start", "Architect is decomposing into files…")
        plan = await run_architect(client, state["spec"])
        await _emit(
            progress,
            "plan.done",
            f"Plan ready: {len(plan.files)} files across {len({f.owner for f in plan.files})} domains",
        )
        return {"plan": plan}

    async def node_implement(state: OrgState) -> OrgState:
        await _emit(progress, "implement.start", "4 implementers writing code in parallel…")
        spec = state["spec"]
        plan = state["plan"]

        async def one(domain: Domain) -> tuple[Domain, list[GeneratedFile], str]:
            out = await run_implementer(client, spec, plan, domain)
            await _emit(
                progress,
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
        await _emit(progress, "implement.done", f"v1 has {len(files)} files")
        return {"files_v1": files, "notes": notes}

    async def node_review(state: OrgState) -> OrgState:
        await _emit(progress, "review.start", "Reviewer + Security auditing…")
        files = state["files_v1"]
        spec = state["spec"]
        rev_out, sec_out = await asyncio.gather(
            run_reviewer(client, spec, files),
            run_security(client, spec, files),
        )
        findings = list(rev_out.findings) + list(sec_out.findings)
        await _emit(
            progress,
            "review.done",
            f"{len(findings)} findings ({len(rev_out.findings)} review + {len(sec_out.findings)} security)",
        )
        return {"findings": findings}

    async def node_fix(state: OrgState) -> OrgState:
        await _emit(progress, "fix.start", "Implementers revising in parallel…")
        spec = state["spec"]
        plan = state["plan"]
        files_v1 = state["files_v1"]
        findings = state.get("findings", [])

        async def one(domain: Domain) -> list[GeneratedFile]:
            domain_files = [f for f in files_v1 if f.owner == domain]
            out = await run_fixer(client, spec, plan, domain, domain_files, findings)
            await _emit(
                progress,
                "fix.domain.done",
                f"{domain}: addressed {len(out.addressed_findings)}, deferred {len(out.deferred_findings)}",
            )
            return out.files

        results = await asyncio.gather(*(one(d) for d in DOMAINS))
        final: list[GeneratedFile] = []
        for fs in results:
            final.extend(fs)

        # Merge: keep v1 files that the fixer didn't return (defensive).
        seen = {f.path for f in final}
        for f in files_v1:
            if f.path not in seen:
                final.append(f)

        await _emit(progress, "fix.done", f"final has {len(final)} files")
        return {"files_final": final}

    graph = StateGraph(OrgState)
    graph.add_node("do_spec", node_spec)
    graph.add_node("do_plan", node_plan)
    graph.add_node("do_implement", node_implement)
    graph.add_node("do_review", node_review)
    graph.add_node("do_fix", node_fix)

    graph.add_edge(START, "do_spec")
    graph.add_edge("do_spec", "do_plan")
    graph.add_edge("do_plan", "do_implement")
    graph.add_edge("do_implement", "do_review")
    graph.add_edge("do_review", "do_fix")
    graph.add_edge("do_fix", END)

    return graph.compile()


async def run_workflow(
    client: LLMClient,
    idea: str,
    progress: ProgressFn | None = None,
) -> OrgState:
    """Top-level convenience: run the full graph for a single idea."""

    app = build_workflow(client, progress)
    final_state = await app.ainvoke({"idea": idea})
    return final_state  # type: ignore[return-value]
