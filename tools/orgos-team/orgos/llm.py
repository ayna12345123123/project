"""Thin async wrapper around Canopy Wave (OpenAI-compatible) chat completions.

Agents always request structured JSON output. The wrapper:
  * loads the prompt template for a role from prompts/<role>.md
  * calls the LLM with JSON response_format
  * retries on transient errors with exponential backoff
  * validates the JSON against the requested Pydantic schema
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from pathlib import Path
from typing import TypeVar

from openai import APIConnectionError, APIError, AsyncOpenAI, RateLimitError
from pydantic import BaseModel, ValidationError

from .config import Config

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Raised after we've exhausted retries or got unrecoverable output."""


class LLMClient:
    """One client per OrgOS run. Internally serializes via a semaphore."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.client = AsyncOpenAI(api_key=config.api_key, base_url=config.base_url)
        self._semaphore = asyncio.Semaphore(config.max_concurrency)
        self._prompt_cache: dict[str, str] = {}

    def load_prompt(self, role: str) -> str:
        if role in self._prompt_cache:
            return self._prompt_cache[role]
        path: Path = self.config.prompts_dir / f"{role}.md"
        if not path.exists():
            raise LLMError(f"Prompt file not found for role '{role}': {path}")
        text = path.read_text(encoding="utf-8")
        self._prompt_cache[role] = text
        return text

    async def call_structured(
        self,
        *,
        role: str,
        user_message: str,
        schema: type[T],
        max_retries: int = 3,
        max_tokens: int | None = None,
    ) -> T:
        """Call the model, parse JSON, validate against `schema`, return instance."""

        system_prompt = self.load_prompt(role)
        model = self.config.model_for(role)

        # Append a short JSON-shape hint so even models without strict
        # response_format support emit valid JSON.
        json_hint = (
            "\n\nRespond ONLY with a single JSON object that matches this schema:\n"
            f"{json.dumps(schema.model_json_schema(), indent=2)}\n"
            "Do not wrap it in markdown fences. Do not add commentary."
        )
        full_system = system_prompt + json_hint

        last_err: Exception | None = None
        for attempt in range(1, max_retries + 1):
            async with self._semaphore:
                try:
                    response = await self.client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": full_system},
                            {"role": "user", "content": user_message},
                        ],
                        temperature=self.config.temperature,
                        response_format={"type": "json_object"},
                        max_tokens=max_tokens,
                    )
                except (RateLimitError, APIConnectionError, APIError) as e:
                    last_err = e
                    delay = self._backoff(attempt)
                    logger.warning(
                        "LLM call %s failed (%s). Attempt %d/%d. Retrying in %.1fs",
                        role,
                        type(e).__name__,
                        attempt,
                        max_retries,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue

            content = response.choices[0].message.content or ""
            try:
                parsed = json.loads(_strip_fences(content))
            except json.JSONDecodeError as e:
                last_err = e
                logger.warning(
                    "LLM call %s returned non-JSON (attempt %d/%d): %s",
                    role,
                    attempt,
                    max_retries,
                    content[:200],
                )
                continue

            try:
                return schema.model_validate(parsed)
            except ValidationError as e:
                last_err = e
                logger.warning(
                    "LLM call %s failed schema validation (attempt %d/%d): %s",
                    role,
                    attempt,
                    max_retries,
                    e,
                )
                continue

        raise LLMError(
            f"Role '{role}' exhausted retries (last error: {last_err})"
        )

    @staticmethod
    def _backoff(attempt: int) -> float:
        base = 2.0 ** (attempt - 1)
        jitter = random.uniform(0, 0.5)
        return min(base + jitter, 30.0)

    async def close(self) -> None:
        await self.client.close()


def _strip_fences(text: str) -> str:
    """Some models still wrap JSON in ``` fences; strip them defensively."""
    s = text.strip()
    if s.startswith("```"):
        # find the first newline after the opening fence
        nl = s.find("\n")
        if nl != -1:
            s = s[nl + 1 :]
        if s.endswith("```"):
            s = s[:-3]
    return s.strip()
