"""Write the generated project to disk; optionally git-init and push.

Strict path safety: every relative path is resolved against `output_dir` and
must stay inside it. We never follow symlinks, never accept absolute paths,
and never accept '..' components.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Iterable

from .schemas import Finding, GeneratedFile, Plan, Spec

logger = logging.getLogger(__name__)


class UnsafePathError(ValueError):
    """Raised when a generated file path tries to escape the output directory."""


def _safe_join(base: Path, rel: str) -> Path:
    """Resolve `rel` under `base`, refusing absolute paths and traversals."""
    p = Path(rel)
    if p.is_absolute():
        raise UnsafePathError(f"absolute path not allowed: {rel}")
    parts = p.parts
    if any(part == ".." for part in parts):
        raise UnsafePathError(f"parent traversal not allowed: {rel}")
    candidate = (base / p).resolve()
    base_resolved = base.resolve()
    try:
        candidate.relative_to(base_resolved)
    except ValueError as e:
        raise UnsafePathError(f"path escapes output dir: {rel}") from e
    return candidate


def write_project(
    output_root: Path,
    project_name: str,
    files: Iterable[GeneratedFile],
    spec: Spec,
    plan: Plan,
    findings: Iterable[Finding],
    notes: Iterable[str] = (),
) -> Path:
    """Write all files plus a meta directory. Returns the project root path."""

    output_root.mkdir(parents=True, exist_ok=True)
    project_root = output_root / project_name
    project_root.mkdir(parents=True, exist_ok=True)

    for f in files:
        target = _safe_join(project_root, f.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f.content, encoding="utf-8")
        logger.debug("wrote %s (%d bytes)", target, len(f.content))

    meta_dir = project_root / ".orgos"
    meta_dir.mkdir(exist_ok=True)
    (meta_dir / "spec.json").write_text(spec.model_dump_json(indent=2), encoding="utf-8")
    (meta_dir / "plan.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    (meta_dir / "findings.json").write_text(
        json.dumps([f.model_dump() for f in findings], indent=2), encoding="utf-8"
    )
    if notes:
        (meta_dir / "notes.md").write_text(
            "\n".join(f"- {n}" for n in notes), encoding="utf-8"
        )

    return project_root


def git_init_and_commit(project_root: Path, message: str = "Initial commit by orgos-team") -> None:
    """Initialize git repo and make a single initial commit. Best-effort, never raises."""
    env = os.environ.copy()
    env.setdefault("GIT_AUTHOR_NAME", "orgos-team")
    env.setdefault("GIT_AUTHOR_EMAIL", "orgos-team@local")
    env.setdefault("GIT_COMMITTER_NAME", "orgos-team")
    env.setdefault("GIT_COMMITTER_EMAIL", "orgos-team@local")
    try:
        subprocess.run(["git", "init", "-q"], cwd=project_root, check=True, env=env)
        subprocess.run(["git", "add", "."], cwd=project_root, check=True, env=env)
        subprocess.run(
            ["git", "commit", "-q", "-m", message], cwd=project_root, check=True, env=env
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        logger.warning("git init/commit failed (non-fatal): %s", e)
