"""Security Lead agent — security-only review pass."""

from __future__ import annotations

from ..llm import LLMClient
from ..schemas import GeneratedFile, ReviewOutput, Spec


async def run_security(
    client: LLMClient,
    spec: Spec,
    files: list[GeneratedFile],
) -> ReviewOutput:
    files_block = "\n".join(
        f"--- FILE: {f.path} (owner={f.owner}) ---\n{f.content}\n--- END {f.path} ---"
        for f in files
    )
    user = (
        "You are the Security Lead. Audit the generated project for security issues. "
        "Focus on real, exploitable problems, NOT theoretical paranoia.\n\n"
        "Watch for:\n"
        " - Hardcoded secrets, API keys, or credentials in source files\n"
        " - SQL injection (string-formatted queries instead of parameterized)\n"
        " - Broken auth / authz (missing ownership checks, missing CSRF, weak password handling)\n"
        " - XSS via unescaped user input in templates\n"
        " - Path traversal in file handlers\n"
        " - Open redirects, SSRF, deserialization issues\n"
        " - Sensitive data in logs\n"
        " - Missing input validation on API endpoints\n"
        " - Dependencies pinned to known-vulnerable versions (only flag if obvious)\n\n"
        f"Spec one-liner: {spec.one_liner}\n"
        "Files:\n"
        + files_block
        + "\n\nReturn structured findings. Use rule codes like 'AUTHZ', 'SQL_INJECT', "
        "'HARDCODED_SECRET', 'XSS', 'PATH_TRAVERSAL', 'INPUT_VALIDATION'. "
        "If clean, return an empty list."
    )
    return await client.call_structured(
        role="security",
        user_message=user,
        schema=ReviewOutput,
        max_tokens=8000,
    )
