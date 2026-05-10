"""Code Reviewer agent — runs over all generated files, emits findings."""

from __future__ import annotations

from ..llm import LLMClient
from ..schemas import GeneratedFile, ReviewOutput, Spec


async def run_reviewer(
    client: LLMClient,
    spec: Spec,
    files: list[GeneratedFile],
) -> ReviewOutput:
    files_block = "\n".join(
        f"--- FILE: {f.path} (owner={f.owner}) ---\n{f.content}\n--- END {f.path} ---"
        for f in files
    )
    user = (
        "Review the generated project against the spec. "
        "Be the second pair of eyes — focus on real bugs, missing imports, broken "
        "wiring between files, unhandled errors, type issues, and acceptance-criteria "
        "gaps. Skip subjective style preferences.\n\n"
        f"Spec one-liner: {spec.one_liner}\n"
        f"Acceptance criteria:\n"
        + "".join(f" - {c}\n" for c in spec.acceptance_criteria)
        + "\nFiles:\n"
        + files_block
        + "\n\nReturn structured findings. Severity guide:\n"
        " - block:  acceptance criterion clearly not met OR code will not run\n"
        " - major:  important defect that should be fixed before merge\n"
        " - minor:  small bug or oversight, fix recommended\n"
        " - nit:    cosmetic only — use sparingly\n"
        "Cap total findings at 30. If clean, return an empty list."
    )
    return await client.call_structured(
        role="reviewer",
        user_message=user,
        schema=ReviewOutput,
        max_tokens=8000,
    )
