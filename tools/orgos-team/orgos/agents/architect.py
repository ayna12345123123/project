"""Chief Architect agent — turns a Spec into a Plan (file list + setup)."""

from __future__ import annotations

from ..llm import LLMClient
from ..schemas import Plan, Spec


async def run_architect(client: LLMClient, spec: Spec) -> Plan:
    user = (
        "Spec:\n"
        "```json\n"
        f"{spec.model_dump_json(indent=2)}\n"
        "```\n\n"
        "Produce a Plan that decomposes the project into concrete files. "
        "Rules:\n"
        " - Aim for 6-20 files total. Quality over quantity.\n"
        " - Each file's owner MUST be one of: backend, frontend, devops, qa.\n"
        "    * backend = server-side code, DB schema, business logic\n"
        "    * frontend = UI, client-side code, templates, styling\n"
        "    * devops = Dockerfile, docker-compose, CI, Makefile, scripts, .env.example\n"
        "    * qa = tests, fixtures, README of testing\n"
        " - Include a README.md (owner=devops).\n"
        " - Include .env.example if any secrets/config exist (owner=devops).\n"
        " - For pure-backend projects (e.g. CLI, bot), 'frontend' may have zero files.\n"
        " - Setup_commands and run_commands must be runnable on a fresh Linux machine.\n"
        " - Path strings are POSIX-style relative paths; never absolute, never '..'."
    )
    return await client.call_structured(
        role="architect",
        user_message=user,
        schema=Plan,
    )
