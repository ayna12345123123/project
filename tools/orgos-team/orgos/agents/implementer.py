"""Domain implementer agents (backend / frontend / devops / qa).

All four share one function — they differ only in which prompt-role file is
loaded and which subset of `Plan.files` they own. The fixer is the same agent
running a second pass after seeing review findings.
"""

from __future__ import annotations

from ..llm import LLMClient
from ..schemas import (
    Domain,
    FixOutput,
    Finding,
    GeneratedFile,
    ImplementerOutput,
    Plan,
    Spec,
)


async def run_implementer(
    client: LLMClient,
    spec: Spec,
    plan: Plan,
    domain: Domain,
) -> ImplementerOutput:
    """Generate the first version of all files owned by `domain`."""

    owned = [f for f in plan.files if f.owner == domain]
    if not owned:
        # Domain has no files in this plan — return empty.
        return ImplementerOutput(files=[], notes="No files assigned to this domain.")

    files_listing = "\n".join(f"- {f.path} — {f.summary}" for f in owned)
    user = (
        f"You are the {domain} implementer. Generate complete, runnable file "
        f"contents for ALL files below. Do not skip any.\n\n"
        f"Project: {plan.project_name}\n"
        f"Spec one-liner: {spec.one_liner}\n"
        f"Tech stack: {', '.join(spec.tech_stack)}\n\n"
        f"Files you own:\n{files_listing}\n\n"
        f"Constraints:\n"
        f" - Every file must be syntactically valid and importable on a fresh machine.\n"
        f" - No placeholder content, TODOs, or 'fill this in' comments.\n"
        f" - Use the exact paths listed above. Do not rename, add, or drop files.\n"
        f" - Pin dependency versions in requirements.txt / package.json / Dockerfile.\n"
        f" - For Python/Node code: include real implementations, not stubs.\n"
        f" - Acceptance criteria the project must meet:\n"
        + "".join(f"   * {c}\n" for c in spec.acceptance_criteria)
    )
    out = await client.call_structured(
        role=domain,
        user_message=user,
        schema=ImplementerOutput,
        max_tokens=16000,
    )
    # Force domain on every returned file (model sometimes echoes wrong owner).
    out = ImplementerOutput(
        files=[GeneratedFile(path=f.path, content=f.content, owner=domain) for f in out.files],
        notes=out.notes,
    )
    return out


async def run_fixer(
    client: LLMClient,
    spec: Spec,
    plan: Plan,
    domain: Domain,
    previous_files: list[GeneratedFile],
    findings: list[Finding],
) -> FixOutput:
    """Second pass: fix the implementer's files given reviewer findings."""

    if not previous_files:
        return FixOutput(files=[], addressed_findings=[], deferred_findings=[])

    relevant_paths = {f.path for f in previous_files}
    relevant_findings = [f for f in findings if f.file in relevant_paths]

    if not relevant_findings:
        # No findings on this domain's files — return them unchanged.
        return FixOutput(
            files=list(previous_files),
            addressed_findings=[],
            deferred_findings=["(no findings against this domain's files)"],
        )

    findings_block = "\n".join(
        f"- [{f.severity}] {f.file}"
        + (f":{f.line}" if f.line else "")
        + f" — {f.rule}: {f.message}"
        for f in relevant_findings
    )
    files_block = "\n".join(
        f"--- FILE: {f.path} ---\n{f.content}\n--- END {f.path} ---"
        for f in previous_files
    )

    user = (
        f"You are the {domain} implementer. Reviewers raised the following findings "
        f"on your files. Fix them.\n\n"
        f"Project: {plan.project_name}\n\n"
        f"Findings against your files:\n{findings_block}\n\n"
        f"Your previous files:\n{files_block}\n\n"
        f"Rules:\n"
        f" - Address every 'block' and 'major' finding. Defer only 'minor'/'nit' "
        f"   if a fix would break something else; document the deferral.\n"
        f" - Return the FULL revised content of each file (not a diff).\n"
        f" - Keep the same paths and the same set of files unless absolutely necessary.\n"
        f" - Preserve the parts that were correct."
    )
    out = await client.call_structured(
        role=domain,
        user_message=user,
        schema=FixOutput,
        max_tokens=16000,
    )
    out = FixOutput(
        files=[GeneratedFile(path=f.path, content=f.content, owner=domain) for f in out.files],
        addressed_findings=out.addressed_findings,
        deferred_findings=out.deferred_findings,
    )
    return out
