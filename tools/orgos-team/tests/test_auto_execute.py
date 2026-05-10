"""Tests for the auto-execute-tests phase.

Two layers covered:
  1. Topology: when a test_runner is wired in, Chief gets two new edges
     (implementers→test_runner, test_runner→implementers) — and they
     only fire when actually needed.
  2. TestRunner internals: pytest output parsing, skip behaviour, isolated
     execution of a tiny synthetic project. Real subprocess test only
     runs locally because it depends on venv + pip and is slow.
"""

from __future__ import annotations

import asyncio
import os

os.environ.setdefault("CANOPYWAVE_API_KEY", "test-fake-key")

import pytest

from orgos.chief import ChiefOrchestrator
from orgos.demo_client import DemoLLMClient, DemoTestRunner
from orgos.schemas import GeneratedFile, TestFailure, TestRunResult
from orgos.test_runner import TestRunner, _parse_failures


# ── topology ─────────────────────────────────────────────────────────────


EXPECTED_ROUTES_BASE = {
    ("idea", "product"),
    ("product", "architect"),
    ("architect", "implementers"),
    ("implementers", "reviewers"),
    ("reviewers", "implementers"),
}
EXPECTED_ROUTES_WITH_TESTS = EXPECTED_ROUTES_BASE | {
    ("implementers", "test_runner"),
}
EXPECTED_ROUTES_WITH_FAILED_TESTS = EXPECTED_ROUTES_WITH_TESTS | {
    ("test_runner", "implementers"),
}


def _capture_routes(client, runner):
    routes: list[tuple[str, str]] = []

    def progress(event: str, detail: str) -> None:
        if event == "chief.route":
            head = detail.split(":", 1)[0]
            frm, to = (s.strip() for s in head.split("→"))
            routes.append((frm, to))

    chief = ChiefOrchestrator(client=client, progress=progress, test_runner=runner)
    state = asyncio.run(chief.run("a tiny CLI"))
    return routes, state


def test_routes_when_tests_pass_skip_the_fix_iteration():
    """Tests pass → exactly one new route (implementers→test_runner)."""
    client = DemoLLMClient(per_call_delay=0.0)
    runner = DemoTestRunner(per_call_delay=0.0, fail_first_run=False)
    routes, state = _capture_routes(client, runner)

    assert set(routes) == EXPECTED_ROUTES_WITH_TESTS, set(routes)
    assert state.test_run is not None
    assert state.test_run.passed is True
    assert state.test_findings == []


def test_routes_when_tests_fail_trigger_extra_fixer_pass():
    """Failing tests → both new routes fire."""
    client = DemoLLMClient(per_call_delay=0.0)
    runner = DemoTestRunner(per_call_delay=0.0, fail_first_run=True)
    routes, state = _capture_routes(client, runner)

    assert set(routes) == EXPECTED_ROUTES_WITH_FAILED_TESTS, set(routes)
    assert state.test_run is not None
    assert state.test_run.passed is False
    # Test failures must be converted to Findings with rule=TEST_FAIL
    assert state.test_findings
    assert all(f.rule == "TEST_FAIL" for f in state.test_findings)
    assert all(f.severity == "block" for f in state.test_findings)


def test_routes_unchanged_when_no_test_runner():
    """No test runner → no new edges; identical to PR #4 baseline."""
    client = DemoLLMClient(per_call_delay=0.0)
    routes, _ = _capture_routes(client, None)
    assert set(routes) == EXPECTED_ROUTES_BASE


# ── pytest output parsing ────────────────────────────────────────────────


def test_parse_failures_handles_typical_output():
    pytest_output = """\
============================= test session starts ==============================
collected 3 items

tests/test_foo.py::test_one PASSED                                         [ 33%]
tests/test_foo.py::test_two FAILED                                         [ 66%]
tests/test_foo.py::test_three FAILED                                       [100%]

=================================== FAILURES ===================================
________________________________ test_two ________________________________
    >  assert 1 == 2
E   assert 1 == 2

tests/test_foo.py:5: AssertionError
=========================== short test summary info ============================
FAILED tests/test_foo.py::test_two - assert 1 == 2
FAILED tests/test_foo.py::test_three - ZeroDivisionError: division by zero
========================= 2 failed, 1 passed in 0.04s ==========================
"""
    failures = _parse_failures(pytest_output)
    assert len(failures) == 2
    assert failures[0].test_name == "test_two"
    assert failures[0].file_path == "tests/test_foo.py"
    assert "assert 1 == 2" in failures[0].error_excerpt
    assert failures[1].test_name == "test_three"
    assert "ZeroDivisionError" in failures[1].error_excerpt


def test_parse_failures_returns_empty_on_clean_output():
    assert _parse_failures("==== 5 passed in 0.1s ====") == []


# ── TestRunner: skip path (no real subprocess needed) ───────────────────


def test_real_runner_skips_when_no_test_files_present():
    """A project with no test_*.py and no tests/ should be skipped, not failed."""
    runner = TestRunner()
    files = [
        GeneratedFile(path="main.py", content="print('hi')\n", owner="backend"),
        GeneratedFile(
            path="requirements.txt", content="", owner="devops"
        ),
    ]
    result = asyncio.run(runner.run(files))
    assert result.ran is False
    assert result.passed is False
    assert "No Python tests" in (result.skip_reason or "")
    assert result.failures == []


# ── TestRunner: real subprocess (slow; opt-in) ──────────────────────────


REAL_TEST_RUNNER = os.environ.get("ORGOS_RUN_REAL_TEST_RUNNER", "0") == "1"


@pytest.mark.skipif(
    not REAL_TEST_RUNNER,
    reason="slow: spawns subprocess + venv + pip install. Set ORGOS_RUN_REAL_TEST_RUNNER=1.",
)
def test_real_runner_executes_tiny_passing_project():
    """End-to-end: real venv, real pytest, on a tiny synthetic project.

    Marked slow because of venv + pip install (~20-30s on a fresh machine).
    Run locally with::

        ORGOS_RUN_REAL_TEST_RUNNER=1 pytest tests/test_auto_execute.py -v
    """
    runner = TestRunner()
    files = [
        GeneratedFile(
            path="tests/test_one.py",
            content="def test_one():\n    assert 1 + 1 == 2\n",
            owner="qa",
        ),
        GeneratedFile(path="requirements.txt", content="", owner="devops"),
    ]
    result = asyncio.run(runner.run(files))
    assert result.ran is True, result.skip_reason
    assert result.passed is True
    assert result.exit_code == 0


# ── DemoTestRunner sanity checks ────────────────────────────────────────


def test_demo_test_runner_default_passes():
    runner = DemoTestRunner(per_call_delay=0.0)
    result = asyncio.run(runner.run([]))
    assert isinstance(result, TestRunResult)
    assert result.ran is True
    assert result.passed is True


def test_demo_test_runner_fail_first_run_then_passes():
    runner = DemoTestRunner(per_call_delay=0.0, fail_first_run=True)
    first = asyncio.run(runner.run([]))
    second = asyncio.run(runner.run([]))
    assert first.passed is False
    assert isinstance(first.failures[0], TestFailure)
    assert second.passed is True
