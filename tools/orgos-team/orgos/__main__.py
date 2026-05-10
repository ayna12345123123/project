"""CLI entrypoint:  python -m orgos "your idea here" """

from __future__ import annotations

import asyncio
import dataclasses
import logging
from pathlib import Path
from typing import Optional

import typer

from .config import Config
from .llm import LLMClient, LLMError
from .output import git_init_and_commit, write_project
from .test_runner import TestRunner
from .ui import ProgressDisplay, print_banner, print_error, print_summary
from .workflow import run_workflow

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="orgos-team — autonomous 8-agent code generator on Canopy Wave / Kimi K2.",
)


@app.command()
def main(
    idea: str = typer.Argument(..., help="Project idea, free-form, any language."),
    env_file: Path = typer.Option(
        Path(".env"),
        "--env-file",
        help="Path to .env file. Defaults to ./.env in current directory.",
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        help="Override ORGOS_OUTPUT_DIR.",
    ),
    git_init: bool = typer.Option(
        True,
        "--git-init/--no-git-init",
        help="Run `git init` + initial commit inside the generated project.",
    ),
    auto_execute_tests: bool = typer.Option(
        False,
        "--auto-execute-tests/--no-auto-execute-tests",
        help=(
            "After the fix pass, materialize the project into a temporary "
            "directory, install dependencies in an isolated venv, and run "
            "pytest. If tests fail, run an additional fixer pass with the "
            "failures fed back as findings. Adds 30-90s in real mode."
        ),
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logs."),
) -> None:
    """Generate a complete project from a free-form idea."""

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    try:
        config = Config.load(env_file=env_file if env_file.exists() else None)
    except RuntimeError as e:
        print_error(str(e))
        raise typer.Exit(code=2) from e

    if output_dir is not None:
        config = dataclasses.replace(config, output_dir=output_dir)

    print_banner(idea)
    progress = ProgressDisplay()

    try:
        final_state = asyncio.run(_run(config, idea, progress, auto_execute_tests))
    except LLMError as e:
        print_error(f"LLM call failed: {e}")
        raise typer.Exit(code=1) from e
    except KeyboardInterrupt:
        print_error("Interrupted by user.")
        raise typer.Exit(code=130)

    spec = final_state["spec"]
    plan = final_state["plan"]
    files_final = final_state.get("files_final") or final_state.get("files_v1", [])
    findings = final_state.get("findings", [])
    notes = final_state.get("notes", [])

    project_root = write_project(
        output_root=config.output_dir,
        project_name=plan.project_name,
        files=files_final,
        spec=spec,
        plan=plan,
        findings=findings,
        notes=notes,
    )

    if git_init:
        git_init_and_commit(project_root)

    print_summary(str(project_root), file_count=len(files_final), finding_count=len(findings))


async def _run(
    config: Config,
    idea: str,
    progress: ProgressDisplay,
    auto_execute_tests: bool,
):
    client = LLMClient(config)
    runner = TestRunner() if auto_execute_tests else None
    try:
        return await run_workflow(client, idea, progress, test_runner=runner)
    finally:
        await client.close()


if __name__ == "__main__":
    app()
