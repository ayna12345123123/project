"""Configuration loader.

Reads .env (or environment variables), exposes a typed Config object that the
rest of the system imports. Per-role model overrides fall back to the default.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROLES = (
    "product",
    "architect",
    "backend",
    "frontend",
    "devops",
    "qa",
    "reviewer",
    "security",
)


@dataclass(frozen=True)
class Config:
    api_key: str
    base_url: str
    default_model: str
    role_models: dict[str, str]
    max_concurrency: int
    temperature: float
    output_dir: Path
    github_token: str | None
    github_owner: str | None
    prompts_dir: Path

    @classmethod
    def load(cls, env_file: str | os.PathLike[str] | None = None) -> "Config":
        load_dotenv(env_file, override=False)

        api_key = os.environ.get("CANOPYWAVE_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "CANOPYWAVE_API_KEY is not set. Copy .env.example to .env and "
                "fill in your Canopy Wave API key, or export it in your shell."
            )

        base_url = os.environ.get(
            "CANOPYWAVE_BASE_URL", "https://inference.canopywave.io/v1"
        ).strip()
        default_model = os.environ.get(
            "ORGOS_DEFAULT_MODEL", "moonshotai/kimi-k2.6"
        ).strip()

        role_models: dict[str, str] = {}
        for role in ROLES:
            override = os.environ.get(f"ORGOS_MODEL_{role.upper()}", "").strip()
            role_models[role] = override or default_model

        max_concurrency = int(os.environ.get("ORGOS_MAX_CONCURRENCY", "4"))
        temperature = float(os.environ.get("ORGOS_TEMPERATURE", "0.2"))

        output_dir = Path(os.environ.get("ORGOS_OUTPUT_DIR", "output")).expanduser()

        github_token = os.environ.get("GITHUB_TOKEN", "").strip() or None
        github_owner = os.environ.get("GITHUB_OWNER", "").strip() or None

        prompts_dir = Path(__file__).resolve().parent.parent / "prompts"

        return cls(
            api_key=api_key,
            base_url=base_url,
            default_model=default_model,
            role_models=role_models,
            max_concurrency=max_concurrency,
            temperature=temperature,
            output_dir=output_dir,
            github_token=github_token,
            github_owner=github_owner,
            prompts_dir=prompts_dir,
        )

    def model_for(self, role: str) -> str:
        return self.role_models.get(role, self.default_model)
