"""Tests for ChiefOrchestrator and DemoLLMClient.

Two invariants we encode here:
  1. Every cross-role hop emits a `chief.route` event. The full set of
     routes is a fixed, audited list — we lock it down so the topology
     can't silently sprout new edges.
  2. DemoLLMClient drives the entire pipeline end-to-end without any
     network calls and produces a runnable demo project.
"""

from __future__ import annotations

import asyncio
import os

os.environ.setdefault("CANOPYWAVE_API_KEY", "test-fake-key")

import pytest

from orgos.chief import ChiefOrchestrator, ChiefState
from orgos.demo_client import DemoLLMClient
from orgos.workflow import run_workflow


# ── DemoLLMClient ──────────────────────────────────────────────────────


def test_demo_client_runs_full_pipeline_without_network():
    """DemoLLMClient must be a complete drop-in for LLMClient.

    No mocks, no patches — if this test ever needs `httpx_mock` or the
    like, demo mode has regressed.
    """
    client = DemoLLMClient(per_call_delay=0.0)
    state = asyncio.run(run_workflow(client, "Telegram bot for tracking expenses"))

    assert state["spec"].name.endswith("-demo")
    assert "Telegram bot" in state["spec"].description
    assert len(state["plan"].files) == 6
    # backend + devops + qa each contribute files; frontend contributes none.
    owners = {f.owner for f in state["files_final"]}
    assert owners == {"backend", "devops", "qa"}
    # Demo seeds two reviewer findings + one security finding.
    assert len(state["findings"]) == 3


def test_demo_client_close_is_noop():
    client = DemoLLMClient(per_call_delay=0.0)
    asyncio.run(client.close())  # must not raise


# ── ChiefOrchestrator route auditing ───────────────────────────────────


EXPECTED_ROUTES = {
    ("idea", "product"),
    ("product", "architect"),
    ("architect", "implementers"),
    ("implementers", "reviewers"),
    ("reviewers", "implementers"),
}


def test_chief_emits_exactly_the_expected_routes():
    """Lock down the topology: only these inter-role hops may exist."""
    client = DemoLLMClient(per_call_delay=0.0)
    routes: list[tuple[str, str]] = []

    def progress(event: str, detail: str) -> None:
        if event == "chief.route":
            # detail looks like: "from → to: what"
            head = detail.split(":", 1)[0]
            frm, to = (s.strip() for s in head.split("→"))
            routes.append((frm, to))

    chief = ChiefOrchestrator(client=client, progress=progress)
    state = ChiefState(idea="x")
    asyncio.run(chief.run("a tiny CLI"))

    seen = set(routes)
    assert seen == EXPECTED_ROUTES, (
        f"unexpected topology — got {seen}, expected {EXPECTED_ROUTES}"
    )


def test_chief_run_returns_complete_state():
    client = DemoLLMClient(per_call_delay=0.0)
    chief = ChiefOrchestrator(client=client, progress=None)
    state = asyncio.run(chief.run("anything"))

    assert state.spec is not None
    assert state.plan is not None
    assert state.files_v1
    assert state.files_final
    # Demo seeds findings; pipeline must reach the fix phase.
    assert state.findings


# ── No agent imports another agent ─────────────────────────────────────


def test_agents_never_import_each_other():
    """Compile-time invariant: the only thing roles import is their LLM
    client + their schema. Cross-role imports are forbidden."""
    import pathlib

    agents_dir = pathlib.Path(__file__).resolve().parent.parent / "orgos" / "agents"
    forbidden_pairs: list[tuple[str, str]] = []
    role_files = sorted(p for p in agents_dir.glob("*.py") if p.name != "__init__.py")
    role_names = {p.stem for p in role_files}

    for path in role_files:
        text = path.read_text()
        for other in role_names:
            if other == path.stem:
                continue
            # `implementer` is shared by 4 roles, that's fine.
            if other == "implementer":
                continue
            if f"from .{other}" in text or f"from orgos.agents.{other}" in text:
                forbidden_pairs.append((path.stem, other))

    assert not forbidden_pairs, (
        "agents must not import each other directly — go through Chief: "
        f"{forbidden_pairs}"
    )


# ── Default model is the new one ───────────────────────────────────────


def test_default_model_is_kimi_k2_6(monkeypatch):
    monkeypatch.setenv("CANOPYWAVE_API_KEY", "x")
    monkeypatch.delenv("ORGOS_DEFAULT_MODEL", raising=False)
    from orgos.config import Config

    cfg = Config.load()
    assert cfg.default_model == "moonshotai/kimi-k2.6"
    for role in ("product", "architect", "backend", "frontend", "devops", "qa", "reviewer", "security"):
        assert cfg.model_for(role) == "moonshotai/kimi-k2.6"
