"""Smoke test that runs the full LangGraph workflow with a mocked LLMClient.

No network calls. Verifies that:
  * schemas serialize/deserialize cleanly
  * the workflow walks all nodes
  * write_project produces a sane on-disk layout
  * path-traversal protection works
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest

import os

os.environ.setdefault("CANOPYWAVE_API_KEY", "test-fake-key")

from orgos.config import Config
from orgos.llm import LLMClient
from orgos.output import UnsafePathError, _safe_join, write_project
from orgos.schemas import (
    FixOutput,
    Finding,
    GeneratedFile,
    ImplementerOutput,
    Plan,
    PlannedFile,
    ReviewOutput,
    Spec,
)
from orgos.workflow import run_workflow


# ---------- canned responses ----------


CANNED_SPEC = Spec(
    name="hello-cli",
    one_liner="A tiny CLI that greets the world.",
    description="Tiny demo project.",
    tech_stack=["Python 3.11", "Click"],
    features=["Prints hello, optionally with a custom name"],
    non_goals=["Internationalization"],
    acceptance_criteria=[
        "Running `python -m hello` prints 'Hello, world!'",
        "Running `python -m hello --name Alice` prints 'Hello, Alice!'",
    ],
)

CANNED_PLAN = Plan(
    project_name="hello-cli",
    summary="Tiny CLI demo.",
    files=[
        PlannedFile(path="hello/__init__.py", owner="backend", summary="Package init"),
        PlannedFile(path="hello/__main__.py", owner="backend", summary="CLI entrypoint"),
        PlannedFile(path="README.md", owner="devops", summary="Docs"),
        PlannedFile(path=".env.example", owner="devops", summary="Empty env example"),
        PlannedFile(path="tests/test_hello.py", owner="qa", summary="Tests"),
    ],
    setup_commands=["python -m venv .venv", "source .venv/bin/activate", "pip install click"],
    run_commands=["python -m hello"],
)


def _impl_output_for(domain: str) -> ImplementerOutput:
    if domain == "backend":
        return ImplementerOutput(
            files=[
                GeneratedFile(
                    path="hello/__init__.py",
                    content='__all__ = ["greet"]\n\ndef greet(name: str = "world") -> str:\n    return f"Hello, {name}!"\n',
                    owner="backend",
                ),
                GeneratedFile(
                    path="hello/__main__.py",
                    content=(
                        "from __future__ import annotations\n"
                        "import argparse\n"
                        "from . import greet\n\n"
                        "def main() -> None:\n"
                        "    p = argparse.ArgumentParser()\n"
                        "    p.add_argument('--name', default='world')\n"
                        "    args = p.parse_args()\n"
                        "    print(greet(args.name))\n\n"
                        "if __name__ == '__main__':\n"
                        "    main()\n"
                    ),
                    owner="backend",
                ),
            ],
            notes="",
        )
    if domain == "devops":
        return ImplementerOutput(
            files=[
                GeneratedFile(
                    path="README.md",
                    content="# hello-cli\n\nTiny CLI.\n",
                    owner="devops",
                ),
                GeneratedFile(
                    path=".env.example", content="# no env vars needed\n", owner="devops"
                ),
            ],
            notes="",
        )
    if domain == "qa":
        return ImplementerOutput(
            files=[
                GeneratedFile(
                    path="tests/test_hello.py",
                    content=(
                        "from hello import greet\n\n"
                        "def test_default():\n"
                        "    assert greet() == 'Hello, world!'\n\n"
                        "def test_custom():\n"
                        "    assert greet('Alice') == 'Hello, Alice!'\n"
                    ),
                    owner="qa",
                )
            ],
            notes="",
        )
    return ImplementerOutput(files=[], notes="No frontend for a CLI project.")


CANNED_REVIEW = ReviewOutput(findings=[], summary="Looks good.")
CANNED_SECURITY = ReviewOutput(findings=[], summary="No issues.")


def _fix_output_for(domain: str, files: list[GeneratedFile], findings) -> FixOutput:
    return FixOutput(
        files=list(files),
        addressed_findings=[],
        deferred_findings=["(no findings)"],
    )


# ---------- mock client ----------


class FakeClient:
    """LLMClient stand-in. Returns canned schema instances based on `role`."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def call_structured(self, *, role, user_message, schema, **_kwargs):
        self.calls.append((role, schema.__name__))
        if role == "product":
            return CANNED_SPEC
        if role == "architect":
            return CANNED_PLAN
        if role in ("backend", "frontend", "devops", "qa") and schema is ImplementerOutput:
            return _impl_output_for(role)
        if role in ("backend", "frontend", "devops", "qa") and schema is FixOutput:
            return _fix_output_for(role, [], [])
        if role == "reviewer":
            return CANNED_REVIEW
        if role == "security":
            return CANNED_SECURITY
        raise AssertionError(f"unexpected role/schema: {role} / {schema.__name__}")

    async def close(self):
        pass


# ---------- tests ----------


def test_path_safety(tmp_path: Path):
    base = tmp_path
    p = _safe_join(base, "sub/file.py")
    assert p.relative_to(base.resolve()).parts == ("sub", "file.py")
    for bad in ["../etc/passwd", "/etc/passwd", "sub/../../etc"]:
        with pytest.raises(UnsafePathError):
            _safe_join(base, bad)


class FakeClientWithFindings(FakeClient):
    """Variant where reviewer raises one finding so fixer actually runs."""

    async def call_structured(self, *, role, user_message, schema, **_kwargs):
        if role == "reviewer":
            self.calls.append((role, schema.__name__))
            return ReviewOutput(
                findings=[
                    Finding(
                        file="hello/__main__.py",
                        severity="major",
                        rule="TYPE_HINT",
                        message="missing return type on main()",
                    )
                ],
                summary="One issue.",
            )
        return await super().call_structured(role=role, user_message=user_message, schema=schema, **_kwargs)


def test_workflow_with_findings_runs_fixer(tmp_path: Path):
    fake = FakeClientWithFindings()
    final_state = asyncio.run(run_workflow(fake, "hello world"))

    assert len(final_state["findings"]) == 1
    # Backend domain has the file with the finding, so its fixer must have run.
    roles_called = [c[0] for c in fake.calls]
    assert roles_called.count("backend") == 2, f"backend should run twice, got {roles_called}"


def test_workflow_smoke(tmp_path: Path):
    fake = FakeClient()
    final_state = asyncio.run(run_workflow(fake, "hello world"))

    assert final_state["spec"].name == "hello-cli"
    assert len(final_state["plan"].files) == 5
    assert final_state["files_v1"]
    assert final_state["files_final"]
    assert final_state["findings"] == []

    project_root = write_project(
        output_root=tmp_path,
        project_name=final_state["plan"].project_name,
        files=final_state["files_final"],
        spec=final_state["spec"],
        plan=final_state["plan"],
        findings=final_state["findings"],
    )

    assert (project_root / "hello" / "__main__.py").exists()
    assert (project_root / "README.md").exists()
    assert (project_root / "tests" / "test_hello.py").exists()
    assert (project_root / ".orgos" / "spec.json").exists()
    assert (project_root / ".orgos" / "plan.json").exists()

    spec_dump = json.loads((project_root / ".orgos" / "spec.json").read_text())
    assert spec_dump["name"] == "hello-cli"

    # Roles called: product, architect, 4 implementer v1s, reviewer + security.
    # Fixers short-circuit (no LLM call) when there are no relevant findings or
    # the domain owns no files — that's a feature, not a bug.
    roles_called = [c[0] for c in fake.calls]
    assert roles_called.count("product") == 1
    assert roles_called.count("architect") == 1
    assert roles_called.count("reviewer") == 1
    assert roles_called.count("security") == 1
    # backend / devops / qa get one v1 implementer call (frontend is skipped since plan has zero frontend files).
    for d in ("backend", "devops", "qa"):
        assert roles_called.count(d) >= 1, f"{d} should be called at least once"
    assert roles_called.count("frontend") == 0
