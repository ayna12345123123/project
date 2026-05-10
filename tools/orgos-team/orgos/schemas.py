"""Typed schemas for every artifact agents produce.

These are the contracts. Agents return JSON that conforms to these models;
the orchestrator validates and rejects malformed output.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Domain = Literal["backend", "frontend", "devops", "qa"]
Severity = Literal["block", "major", "minor", "nit"]


class Spec(BaseModel):
    """Product-Lead-authored specification."""

    name: str = Field(description="Slug-like project name, e.g. 'expense-tracker-bot'")
    one_liner: str = Field(description="One-sentence description")
    description: str = Field(description="2-4 paragraph description")
    tech_stack: list[str] = Field(description="List of technologies")
    features: list[str] = Field(description="User-facing features")
    non_goals: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(description="Testable criteria")


class PlannedFile(BaseModel):
    path: str = Field(description="Relative path inside the project, e.g. 'app/main.py'")
    owner: Domain
    summary: str = Field(description="What this file does, in one sentence")


class Plan(BaseModel):
    """Architect-authored decomposition of a Spec into files-to-generate."""

    project_name: str
    summary: str
    files: list[PlannedFile]
    setup_commands: list[str] = Field(
        default_factory=list,
        description="Commands the user runs after generation, e.g. 'pip install -r requirements.txt'",
    )
    run_commands: list[str] = Field(
        default_factory=list,
        description="Commands to run the project, e.g. 'python main.py'",
    )


class GeneratedFile(BaseModel):
    path: str
    content: str
    owner: Domain


class ImplementerOutput(BaseModel):
    """What an implementer agent returns: a batch of files for its domain."""

    files: list[GeneratedFile]
    notes: str = Field(default="", description="Free-form notes / caveats")


class Finding(BaseModel):
    """A single issue raised by a reviewer."""

    file: str
    severity: Severity
    line: int | None = None
    rule: str = Field(
        description="Short rule code, e.g. 'AUTHZ', 'SQL_INJECT', 'TYPE_HINT'"
    )
    message: str


class ReviewOutput(BaseModel):
    """What a reviewer agent returns."""

    findings: list[Finding]
    summary: str = Field(default="")


class FixOutput(BaseModel):
    """Implementer's revised files after seeing review findings."""

    files: list[GeneratedFile]
    addressed_findings: list[str] = Field(
        default_factory=list,
        description="Rules/messages that were addressed in this revision",
    )
    deferred_findings: list[str] = Field(
        default_factory=list,
        description="Findings explicitly NOT addressed, with reasoning",
    )


class TestFailure(BaseModel):
    """A single failing test captured from pytest output."""

    # Tell pytest this is NOT a test class (the "Test" prefix triggers collection).
    __test__ = False

    test_name: str = Field(
        description="Pytest node id, e.g. 'tests/test_foo.py::test_bar'"
    )
    file_path: str = Field(description="Test file path inside the project")
    error_excerpt: str = Field(
        default="",
        description="Short excerpt from pytest output describing the failure",
    )


class TestRunResult(BaseModel):
    """Outcome of running the generated test suite in an isolated environment."""

    __test__ = False

    ran: bool = Field(
        description="True if pytest actually executed (False = skipped/setup error)"
    )
    passed: bool = Field(description="True if all executed tests passed")
    skip_reason: str | None = Field(
        default=None,
        description="If ran=False, why the run was skipped (no tests / install failed / timeout)",
    )
    failures: list[TestFailure] = Field(default_factory=list)
    raw_output: str = Field(
        default="", description="Last ~10kb of combined stdout+stderr"
    )
    duration_s: float = Field(
        default=0.0, description="Wall-clock time for the entire phase"
    )
    exit_code: int | None = Field(
        default=None, description="pytest exit code, when available"
    )
