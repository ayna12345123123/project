"""LangGraph wiring for the OrgOS pipeline.

This module is intentionally thin: every meaningful decision lives in
:class:`orgos.chief.ChiefOrchestrator`. The LangGraph here exists only so
that we get free checkpointing, retries, and visualization tooling — it
does NOT make routing decisions.

Pipeline (single linear chain; Chief handles parallelism inside each node):

    INTAKE → SPEC → PLAN → IMPLEMENT → REVIEW → FIX → DONE

Every node is a one-line delegate to a Chief method. Roles never appear
in this file. If you need to add a role, add it to Chief — never wire it
into the graph directly.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .chief import ChiefOrchestrator, ChiefState
from .schemas import (
    Finding,
    GeneratedFile,
    Plan,
    Spec,
)

logger = logging.getLogger(__name__)


class OrgState(TypedDict, total=False):
    idea: str
    spec: Spec
    plan: Plan
    files_v1: list[GeneratedFile]
    findings: list[Finding]
    files_final: list[GeneratedFile]
    notes: list[str]
    _chief_state: ChiefState  # internal: passed between nodes


# Optional progress hook so the CLI / Web UI can show what's happening.
ProgressFn = Callable[[str, str], Awaitable[None] | None]


def build_workflow(client: Any, progress: ProgressFn | None = None):
    """Compile a LangGraph state machine that delegates to a single Chief."""

    chief = ChiefOrchestrator(client=client, progress=progress)

    async def node_intake(state: OrgState) -> OrgState:
        chief_state = ChiefState(idea=state["idea"])
        return {"_chief_state": chief_state}

    async def node_spec(state: OrgState) -> OrgState:
        cs = state["_chief_state"]
        await chief.do_spec(cs)
        return {"_chief_state": cs, "spec": cs.spec}  # type: ignore[typeddict-item]

    async def node_plan(state: OrgState) -> OrgState:
        cs = state["_chief_state"]
        await chief.do_plan(cs)
        return {"_chief_state": cs, "plan": cs.plan}  # type: ignore[typeddict-item]

    async def node_implement(state: OrgState) -> OrgState:
        cs = state["_chief_state"]
        await chief.do_implement(cs)
        return {
            "_chief_state": cs,
            "files_v1": list(cs.files_v1),
            "notes": list(cs.notes),
        }

    async def node_review(state: OrgState) -> OrgState:
        cs = state["_chief_state"]
        await chief.do_review(cs)
        return {"_chief_state": cs, "findings": list(cs.findings)}

    async def node_fix(state: OrgState) -> OrgState:
        cs = state["_chief_state"]
        await chief.do_fix(cs)
        return {"_chief_state": cs, "files_final": list(cs.files_final)}

    graph = StateGraph(OrgState)
    graph.add_node("do_intake", node_intake)
    graph.add_node("do_spec", node_spec)
    graph.add_node("do_plan", node_plan)
    graph.add_node("do_implement", node_implement)
    graph.add_node("do_review", node_review)
    graph.add_node("do_fix", node_fix)

    graph.add_edge(START, "do_intake")
    graph.add_edge("do_intake", "do_spec")
    graph.add_edge("do_spec", "do_plan")
    graph.add_edge("do_plan", "do_implement")
    graph.add_edge("do_implement", "do_review")
    graph.add_edge("do_review", "do_fix")
    graph.add_edge("do_fix", END)

    return graph.compile()


async def run_workflow(
    client: Any,
    idea: str,
    progress: ProgressFn | None = None,
) -> OrgState:
    """Top-level convenience: run the full pipeline for a single idea.

    Internally this just builds and invokes the graph; the graph in turn
    delegates everything to a ChiefOrchestrator instance. The return
    value is a flat dict so existing callers (CLI, Web UI, tests) don't
    need to know about ChiefState.
    """

    app = build_workflow(client, progress)
    final_state = await app.ainvoke({"idea": idea})

    # Strip the internal Chief state from the public return value.
    public: OrgState = {k: v for k, v in final_state.items() if not k.startswith("_")}  # type: ignore[assignment]
    return public
