"""Product Lead agent — turns a free-form idea into a Spec."""

from __future__ import annotations

from ..llm import LLMClient
from ..schemas import Spec


async def run_product(client: LLMClient, idea: str) -> Spec:
    user = (
        "Project idea (in any language):\n"
        "---\n"
        f"{idea}\n"
        "---\n\n"
        "Write a tight Spec. Be specific. Pick a sensible tech stack. "
        "Acceptance criteria must be testable. "
        "Use English for field values (project name, paths) so file generation "
        "downstream is consistent, but you may quote the original idea verbatim "
        "in `description` if it helps."
    )
    return await client.call_structured(
        role="product",
        user_message=user,
        schema=Spec,
    )
