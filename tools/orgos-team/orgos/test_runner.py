"""Auto-execute generated Python tests in an isolated environment.

After Chief's normal FIX phase, we materialize the project files into a
temporary directory, build a fresh venv, install dependencies, and run
``pytest``. Any failures get folded back into the Chief pipeline as
:class:`Finding` objects with ``rule="TEST_FAIL"``, which triggers an
extra implementer pass.

Design notes:

* **Always isolated.** A new tmp dir + new venv per execution. We never
  install AI-generated code into the user's main interpreter.
* **Bounded by time.** Three independent timeouts: ``venv``, ``pip
  install``, ``pytest``. None of them can dead-lock the workflow.
* **Conservative parsing.** We don't try to be clever about test
  discovery — we look for ``tests/`` or ``test_*.py`` files, and only
  parse the standard pytest "FAILED nodeid - message" line format.
  Anything we can't parse falls back to "passed = (exit_code == 0)".
* **Path-safety re-applied.** We refuse to materialize files with
  absolute paths or ``..`` components, just like
  :mod:`orgos.output`. AI-generated paths are not trusted.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Protocol

from .schemas import GeneratedFile, TestFailure, TestRunResult

logger = logging.getLogger(__name__)

# Pattern: "FAILED tests/x.py::test_y - AssertionError: foo"
_FAILED_LINE = re.compile(r"^FAILED\s+(\S+?)(?:\s*-\s*(.*))?$", re.MULTILINE)

DEFAULT_VENV_TIMEOUT_S = 90.0
DEFAULT_INSTALL_TIMEOUT_S = 180.0
DEFAULT_PYTEST_TIMEOUT_S = 90.0
RAW_OUTPUT_TAIL_BYTES = 10_000


class TestRunnerProto(Protocol):
    """Anything Chief will accept as a test runner."""

    async def run(
        self, files: list[GeneratedFile]
    ) -> TestRunResult:  # pragma: no cover - protocol
        ...


def _materialize(files: list[GeneratedFile], project: Path) -> int:
    """Write files into project, skipping unsafe paths. Returns count written."""
    written = 0
    for f in files:
        p = Path(f.path)
        if p.is_absolute() or any(part == ".." for part in p.parts):
            logger.warning("test_runner: skipping unsafe path %r", f.path)
            continue
        target = project / p
        try:
            target.relative_to(project)
        except ValueError:
            logger.warning("test_runner: path escapes project root %r", f.path)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f.content, encoding="utf-8")
        written += 1
    return written


def _has_python_tests(project: Path) -> bool:
    if (project / "tests").is_dir():
        return True
    for py in project.rglob("test_*.py"):
        if py.is_file():
            return True
    for py in project.rglob("*_test.py"):
        if py.is_file():
            return True
    return False


def _venv_executables(venv_dir: Path) -> tuple[Path, Path]:
    """Return (python, pip) paths inside the venv, OS-aware."""
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe", venv_dir / "Scripts" / "pip.exe"
    return venv_dir / "bin" / "python", venv_dir / "bin" / "pip"


def _parse_failures(output: str) -> list[TestFailure]:
    failures: list[TestFailure] = []
    for m in _FAILED_LINE.finditer(output):
        nodeid = m.group(1).strip()
        excerpt = (m.group(2) or "").strip()
        if "::" in nodeid:
            file_path, test_name = nodeid.split("::", 1)
        else:
            file_path, test_name = nodeid, nodeid
        failures.append(
            TestFailure(
                test_name=test_name,
                file_path=file_path,
                error_excerpt=excerpt[:500],
            )
        )
    return failures


def _tail(text: str, max_bytes: int) -> str:
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return text
    return "…(truncated)…\n" + encoded[-max_bytes:].decode("utf-8", errors="replace")


async def _run_subprocess(
    *args: str,
    cwd: Path | None = None,
    timeout_s: float,
) -> tuple[int | None, str]:
    """Run a subprocess; return (exit_code, combined stdout+stderr).

    Exit code is ``None`` if the process timed out and was killed.
    """
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(cwd) if cwd is not None else None,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except TimeoutError:
        proc.kill()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except TimeoutError:
            pass
        return None, "(timed out)"
    return proc.returncode, out.decode("utf-8", errors="replace")


class TestRunner:
    """Isolated, bounded pytest runner.

    Each call to :meth:`run` uses a fresh temporary directory and a
    fresh venv. No state leaks between runs.
    """

    # Tell pytest this is NOT a test class (the "Test" prefix triggers collection).
    __test__ = False

    def __init__(
        self,
        *,
        venv_timeout_s: float = DEFAULT_VENV_TIMEOUT_S,
        install_timeout_s: float = DEFAULT_INSTALL_TIMEOUT_S,
        pytest_timeout_s: float = DEFAULT_PYTEST_TIMEOUT_S,
        extra_pytest_args: tuple[str, ...] = ("--tb=short", "-q"),
    ) -> None:
        self.venv_timeout_s = venv_timeout_s
        self.install_timeout_s = install_timeout_s
        self.pytest_timeout_s = pytest_timeout_s
        self.extra_pytest_args = extra_pytest_args

    async def run(self, files: list[GeneratedFile]) -> TestRunResult:
        start = time.monotonic()

        with tempfile.TemporaryDirectory(prefix="orgos-test-") as tmp:
            project = Path(tmp)
            written = _materialize(files, project)
            if written == 0:
                return TestRunResult(
                    ran=False,
                    passed=False,
                    skip_reason="No safe files to materialize",
                    duration_s=time.monotonic() - start,
                )

            if not _has_python_tests(project):
                return TestRunResult(
                    ran=False,
                    passed=False,
                    skip_reason=(
                        "No Python tests found (need tests/ dir or test_*.py / *_test.py)"
                    ),
                    duration_s=time.monotonic() - start,
                )

            venv_dir = project / ".venv_test"
            code, venv_out = await _run_subprocess(
                sys.executable,
                "-m",
                "venv",
                str(venv_dir),
                timeout_s=self.venv_timeout_s,
            )
            if code != 0:
                return TestRunResult(
                    ran=False,
                    passed=False,
                    skip_reason=f"venv creation failed (exit={code})",
                    raw_output=_tail(venv_out, RAW_OUTPUT_TAIL_BYTES),
                    duration_s=time.monotonic() - start,
                )

            venv_py, venv_pip = _venv_executables(venv_dir)

            install_log: list[str] = []
            req = project / "requirements.txt"
            if req.exists():
                code, out = await _run_subprocess(
                    str(venv_pip),
                    "install",
                    "-q",
                    "--disable-pip-version-check",
                    "-r",
                    str(req),
                    timeout_s=self.install_timeout_s,
                )
                install_log.append(out)
                if code != 0:
                    return TestRunResult(
                        ran=False,
                        passed=False,
                        skip_reason=f"pip install -r requirements.txt failed (exit={code})",
                        raw_output=_tail("\n".join(install_log), RAW_OUTPUT_TAIL_BYTES),
                        duration_s=time.monotonic() - start,
                    )

            # Always make sure pytest itself is present in the venv.
            code, out = await _run_subprocess(
                str(venv_pip),
                "install",
                "-q",
                "--disable-pip-version-check",
                "pytest",
                timeout_s=self.install_timeout_s,
            )
            install_log.append(out)
            if code != 0:
                return TestRunResult(
                    ran=False,
                    passed=False,
                    skip_reason=f"pytest install failed (exit={code})",
                    raw_output=_tail("\n".join(install_log), RAW_OUTPUT_TAIL_BYTES),
                    duration_s=time.monotonic() - start,
                )

            code, out = await _run_subprocess(
                str(venv_py),
                "-m",
                "pytest",
                *self.extra_pytest_args,
                cwd=project,
                timeout_s=self.pytest_timeout_s,
            )

            if code is None:
                return TestRunResult(
                    ran=True,
                    passed=False,
                    skip_reason=f"pytest timed out after {self.pytest_timeout_s:.0f}s",
                    raw_output=_tail(out, RAW_OUTPUT_TAIL_BYTES),
                    duration_s=time.monotonic() - start,
                )

            failures = _parse_failures(out)
            return TestRunResult(
                ran=True,
                passed=code == 0,
                exit_code=code,
                failures=failures,
                raw_output=_tail(out, RAW_OUTPUT_TAIL_BYTES),
                duration_s=time.monotonic() - start,
            )


__all__ = ["TestRunner", "TestRunnerProto"]
