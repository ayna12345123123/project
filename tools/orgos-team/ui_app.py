"""Streamlit Web UI for orgos-team.

Run with:
    streamlit run ui_app.py

The UI exposes the same workflow as the CLI but with:
  * sidebar controls for API key, models per role, concurrency, temperature
  * live progress log that streams events as the agents work
  * tabbed result view: Files (with code preview) / Spec / Plan / Findings / Run log
  * one-click ZIP download of the generated project
"""

from __future__ import annotations

import asyncio
import dataclasses
import io
import json
import os
import queue
import threading
import time
import traceback
import zipfile
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from orgos.config import Config
from orgos.demo_client import DemoLLMClient, DemoTestRunner
from orgos.llm import LLMClient, LLMError
from orgos.output import git_init_and_commit, write_project
from orgos.schemas import Finding, GeneratedFile, Plan, Spec, TestRunResult
from orgos.test_runner import TestRunner
from orgos.workflow import run_workflow


# ─── page config ──────────────────────────────────────────────────────────


st.set_page_config(
    page_title="orgos-team",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ─── session-state init ───────────────────────────────────────────────────


def _init_state() -> None:
    defaults: dict[str, Any] = {
        "status": "idle",
        "events": [],
        "result": None,
        "error": None,
        "worker": None,
        "event_queue": None,
        "started_at": None,
        "finished_at": None,
        "project_root": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()


# ─── workers ──────────────────────────────────────────────────────────────


def _worker_target(
    config: Config,
    idea: str,
    do_git_init: bool,
    demo_mode: bool,
    auto_execute_tests: bool,
    event_q: "queue.Queue[tuple[str, Any]]",
) -> None:
    """Run the async workflow in a background thread.

    If ``demo_mode`` is True, swap in :class:`DemoLLMClient` so we never
    touch the network. Everything downstream — Chief, agents, schemas,
    output writer — is unchanged.

    If ``auto_execute_tests`` is True, also wire in a test runner. In
    demo mode that's :class:`DemoTestRunner` (instant pass); otherwise
    it's the real :class:`TestRunner` that spawns an isolated venv.
    """

    def progress(event: str, detail: str) -> None:
        event_q.put(("progress", (event, detail)))

    async def _go() -> dict[str, Any]:
        client: Any
        runner: Any | None
        if demo_mode:
            client = DemoLLMClient()
            runner = DemoTestRunner() if auto_execute_tests else None
        else:
            client = LLMClient(config)
            runner = TestRunner() if auto_execute_tests else None
        try:
            return await run_workflow(client, idea, progress, test_runner=runner)
        finally:
            await client.close()

    try:
        loop = asyncio.new_event_loop()
        try:
            final_state = loop.run_until_complete(_go())
        finally:
            loop.close()

        plan: Plan = final_state["plan"]
        spec: Spec = final_state["spec"]
        files_final: list[GeneratedFile] = (
            final_state.get("files_final") or final_state.get("files_v1") or []
        )
        findings: list[Finding] = final_state.get("findings", [])
        notes = final_state.get("notes", [])
        test_run: TestRunResult | None = final_state.get("test_run")
        test_findings: list[Finding] = final_state.get("test_findings", [])

        project_root = write_project(
            output_root=config.output_dir,
            project_name=plan.project_name,
            files=files_final,
            spec=spec,
            plan=plan,
            findings=findings,
            notes=notes,
        )
        if do_git_init:
            git_init_and_commit(project_root)

        event_q.put(
            (
                "done",
                {
                    "spec": spec,
                    "plan": plan,
                    "files_final": files_final,
                    "findings": findings,
                    "notes": notes,
                    "project_root": str(project_root),
                    "test_run": test_run,
                    "test_findings": test_findings,
                },
            )
        )
    except LLMError as e:
        event_q.put(("error", f"LLM call failed: {e}"))
    except Exception as e:  # noqa: BLE001
        event_q.put(("error", f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}"))


def _drain_queue() -> bool:
    """Pull pending events from the queue. Returns True if work is still ongoing."""
    q: queue.Queue | None = st.session_state.get("event_queue")
    if q is None:
        return False
    finished = False
    try:
        while True:
            kind, payload = q.get_nowait()
            if kind == "progress":
                st.session_state.events.append(payload)
            elif kind == "done":
                st.session_state.result = payload
                st.session_state.project_root = payload["project_root"]
                st.session_state.status = "done"
                st.session_state.finished_at = datetime.now()
                finished = True
            elif kind == "error":
                st.session_state.error = payload
                st.session_state.status = "error"
                st.session_state.finished_at = datetime.now()
                finished = True
    except queue.Empty:
        pass
    return not finished


# ─── helpers ──────────────────────────────────────────────────────────────


SEVERITY_COLOR = {
    "block": "red",
    "major": "orange",
    "minor": "blue",
    "nit": "gray",
}


def _zip_directory(root: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in root.rglob("*"):
            if path.is_dir():
                continue
            # Skip the local .git dir if any
            rel = path.relative_to(root)
            if rel.parts and rel.parts[0] == ".git":
                continue
            zf.write(path, arcname=str(Path(root.name) / rel))
    return buf.getvalue()


def _language_for(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".js": "javascript",
        ".jsx": "jsx",
        ".json": "json",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".toml": "toml",
        ".md": "markdown",
        ".sh": "bash",
        ".env": "bash",
        ".env.example": "bash",
        ".sql": "sql",
        ".html": "html",
        ".css": "css",
        ".rs": "rust",
        ".go": "go",
        ".dockerfile": "dockerfile",
        ".makefile": "makefile",
    }.get(suffix, "")


def _build_config_from_sidebar() -> Config | None:
    """Build a Config from sidebar overrides, falling back to .env."""
    api_key = st.session_state.get("api_key", "").strip()
    if not api_key:
        # Try .env / environment.
        env_key = os.environ.get("CANOPYWAVE_API_KEY", "").strip()
        if not env_key:
            try:
                from dotenv import dotenv_values  # type: ignore

                values = dotenv_values(".env")
                env_key = (values.get("CANOPYWAVE_API_KEY") or "").strip()
            except Exception:  # noqa: BLE001
                env_key = ""
        api_key = env_key

    if not api_key:
        # In demo mode we don't need a real key, but Config.load() still
        # demands SOMETHING in the env. Use a placeholder.
        if st.session_state.get("demo_mode", False):
            api_key = "demo-mode-no-network-calls"
        else:
            st.error(
                "No CANOPYWAVE_API_KEY provided. "
                "Either paste it in the sidebar or put it in `.env` next to this app, "
                "or enable 🎭 Demo mode in the sidebar."
            )
            return None

    os.environ["CANOPYWAVE_API_KEY"] = api_key

    # apply per-role overrides into env so Config.load picks them up
    default_model = st.session_state.get("default_model", "moonshotai/kimi-k2.6").strip()
    os.environ["ORGOS_DEFAULT_MODEL"] = default_model

    for role in (
        "product",
        "architect",
        "backend",
        "frontend",
        "devops",
        "qa",
        "reviewer",
        "security",
    ):
        key = f"role_{role}"
        val = st.session_state.get(key, "").strip()
        env_key = f"ORGOS_MODEL_{role.upper()}"
        if val:
            os.environ[env_key] = val
        else:
            os.environ.pop(env_key, None)

    os.environ["ORGOS_MAX_CONCURRENCY"] = str(st.session_state.get("max_concurrency", 4))
    os.environ["ORGOS_TEMPERATURE"] = str(st.session_state.get("temperature", 0.2))
    output_dir = st.session_state.get("output_dir", "output").strip() or "output"
    os.environ["ORGOS_OUTPUT_DIR"] = output_dir

    try:
        config = Config.load(env_file=Path(".env") if Path(".env").exists() else None)
    except RuntimeError as e:
        st.error(str(e))
        return None
    return config


# ─── sidebar ──────────────────────────────────────────────────────────────


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### 🎭 Demo mode")
        st.checkbox(
            "Demo mode (no API calls)",
            value=st.session_state.get("demo_mode", False),
            key="demo_mode",
            help=(
                "Replace the LLM client with a deterministic stub. The full "
                "5-phase pipeline runs in ~3 seconds and produces a real, "
                "runnable demo project. Useful for onboarding, demos, and "
                "trying the UI without an API key."
            ),
        )
        if st.session_state.get("demo_mode", False):
            st.info("🎭 Demo mode is ON — no network, no tokens spent.")

        st.markdown("### 🔑 API")
        st.text_input(
            "CANOPYWAVE_API_KEY",
            type="password",
            placeholder="Leave empty to use .env",
            key="api_key",
            disabled=st.session_state.get("demo_mode", False),
        )

        st.markdown("### 🧠 Models")
        st.text_input(
            "Default model (all roles)",
            value=st.session_state.get("default_model", "moonshotai/kimi-k2.6"),
            key="default_model",
        )
        with st.expander("Per-role overrides", expanded=False):
            for role in (
                "product",
                "architect",
                "backend",
                "frontend",
                "devops",
                "qa",
                "reviewer",
                "security",
            ):
                st.text_input(
                    f"{role}",
                    value=st.session_state.get(f"role_{role}", ""),
                    key=f"role_{role}",
                    placeholder="(use default)",
                )

        st.markdown("### ⚙️ Run")
        st.slider("Max concurrency", 1, 8, 4, key="max_concurrency")
        st.slider("Temperature", 0.0, 1.0, 0.2, step=0.05, key="temperature")
        st.text_input("Output dir", value="output", key="output_dir")
        st.checkbox(
            "git init + initial commit inside generated project",
            value=True,
            key="git_init",
        )

        st.markdown("### 🧪 Auto-execute tests")
        st.checkbox(
            "Run pytest after generation (+1 fix iteration)",
            value=st.session_state.get("auto_execute_tests", False),
            key="auto_execute_tests",
            help=(
                "After the fix pass, run pytest in an isolated venv. If "
                "tests fail, run an additional fixer pass with the "
                "failures fed back as findings.\n\n"
                "Real mode: spawns subprocess, creates fresh venv, "
                "installs requirements.txt + pytest, runs tests with "
                "timeout. Adds 30-90s.\n\n"
                "Demo mode: simulated, instant, deterministic."
            ),
        )
        if (
            st.session_state.get("auto_execute_tests", False)
            and not st.session_state.get("demo_mode", False)
        ):
            st.warning(
                "⚠️ Auto-execute will spawn a subprocess and **run "
                "AI-generated code** in an isolated venv. Default OFF for "
                "safety; you've turned it ON. Output is sandboxed in tmp "
                "dirs with 90s timeouts."
            )

        st.markdown("---")
        st.caption(
            "Canopy Wave: [docs](https://canopywave.com/docs/get-started/quick-start) · "
            "[models](https://canopywave.com/docs/kimi-k2.6)"
        )


# ─── main panel: idea input ───────────────────────────────────────────────


EXAMPLES = [
    ("Telegram bot — expense tracker", "Telegram-бот для учёта расходов на aiogram + Postgres. Команды: /add сумма категория, /stats за период, /export csv."),
    ("FastAPI URL shortener", "URL shortener на FastAPI с Postgres. POST /shorten возвращает короткий код, GET /{code} редиректит, GET /stats/{code} показывает количество кликов."),
    ("CLI markdown→PDF", "Python CLI на Click: принимает markdown-файл, конвертирует в PDF, поддерживает темы (light/dark) и подсветку синтаксиса в кодовых блоках."),
    ("Discord moderator bot", "Discord-бот на discord.py. Авто-удаление сообщений по regex-паттернам из конфига, логирование банов в Postgres, команда /warn user reason."),
]


def _render_idea_input() -> tuple[str, bool]:
    st.markdown("## 💡 Project idea")
    st.caption(
        "Describe what you want built, in any language. The team will produce a "
        "complete project (code + tests + README) in `output/<slug>/`."
    )

    cols = st.columns(len(EXAMPLES))
    for col, (label, text) in zip(cols, EXAMPLES, strict=False):
        if col.button(label, use_container_width=True):
            st.session_state.idea = text

    idea = st.text_area(
        "Idea",
        height=160,
        key="idea",
        placeholder="e.g. CLI tool for reading CSV files and exporting them to Postgres…",
    )

    running = st.session_state.status == "running"
    submit = st.button(
        "🚀 Generate project" if not running else "⏳ Running…",
        type="primary",
        disabled=running or not idea.strip(),
    )
    return idea, submit


# ─── main panel: progress ─────────────────────────────────────────────────


_BASE_PHASES = [
    ("spec", "🧾 Spec", "Product Lead writes the spec"),
    ("plan", "🗺️ Plan", "Architect decomposes into files"),
    ("implement", "⌨️ Implement", "Backend / Frontend / DevOps / QA — in parallel"),
    ("review", "🔍 Review", "Reviewer + Security audit"),
    ("fix", "🩹 Fix", "Implementers revise based on findings"),
]
_TEST_PHASES = [
    ("test", "🧪 Tests", "Run generated tests in isolated venv"),
    ("retest_fix", "🛠️ Test-fix", "Patch failing tests (only if needed)"),
]


def _render_progress() -> None:
    st.markdown("## 🛰️ Progress")
    events: list[tuple[str, str]] = st.session_state.events

    auto_tests = bool(st.session_state.get("auto_execute_tests", False))
    phases = list(_BASE_PHASES)
    if auto_tests:
        phases = phases + _TEST_PHASES

    phase_states = {p[0]: "pending" for p in phases}
    for ev_name, _ in events:
        for p, _, _ in phases:
            if ev_name.startswith(p):
                if ev_name.endswith(".start"):
                    phase_states[p] = "running"
                elif ev_name.endswith(".done"):
                    phase_states[p] = "done"
                elif ev_name.endswith(".failed"):
                    phase_states[p] = "failed"
                elif ev_name.endswith(".skipped"):
                    phase_states[p] = "skipped"

    glyph_map = {
        "pending": "⬜",
        "running": "🟡",
        "done": "✅",
        "failed": "❌",
        "skipped": "⏭️",
    }
    cols = st.columns(len(phases))
    for col, (p, label, desc) in zip(cols, phases, strict=False):
        state = phase_states[p]
        glyph = glyph_map[state]
        with col:
            st.markdown(f"### {glyph} {label}")
            st.caption(desc)

    if events:
        with st.expander(f"Event log ({len(events)} events)", expanded=True):
            for ev, detail in events[-100:]:
                st.text(f"  {ev:<30} {detail}")


# ─── main panel: results ──────────────────────────────────────────────────


def _render_results() -> None:
    result = st.session_state.result
    if result is None:
        return

    spec: Spec = result["spec"]
    plan: Plan = result["plan"]
    files: list[GeneratedFile] = result["files_final"]
    findings: list[Finding] = result["findings"]
    project_root = result["project_root"]

    st.success(f"Generated: `{project_root}`")
    elapsed = None
    if st.session_state.started_at and st.session_state.finished_at:
        elapsed = (st.session_state.finished_at - st.session_state.started_at).total_seconds()

    cols = st.columns(4)
    cols[0].metric("Files", len(files))
    cols[1].metric("Findings", len(findings))
    cols[2].metric(
        "Block/Major",
        sum(1 for f in findings if f.severity in ("block", "major")),
    )
    cols[3].metric("Elapsed", f"{elapsed:.1f}s" if elapsed is not None else "—")

    # Download as ZIP
    try:
        zip_bytes = _zip_directory(Path(project_root))
        st.download_button(
            "⬇️ Download project as .zip",
            data=zip_bytes,
            file_name=f"{Path(project_root).name}.zip",
            mime="application/zip",
            use_container_width=True,
        )
    except Exception as e:  # noqa: BLE001
        st.warning(f"Could not build ZIP: {e}")

    test_run: TestRunResult | None = result.get("test_run")
    test_findings: list[Finding] = result.get("test_findings", [])
    has_tests = test_run is not None

    tab_labels = ["📁 Files", "📜 Spec", "🗺️ Plan", "🔎 Findings"]
    if has_tests:
        tab_labels.append("🧪 Tests")
    tab_labels.append("📰 Run log")
    tabs = st.tabs(tab_labels)

    # Files tab
    with tabs[0]:
        if not files:
            st.info("No files were generated.")
        else:
            paths = sorted({f.path for f in files})
            choice = st.selectbox("Pick a file to preview", paths)
            picked = next((f for f in files if f.path == choice), None)
            if picked is not None:
                st.caption(f"owner: `{picked.owner}` · path: `{picked.path}`")
                st.code(picked.content, language=_language_for(picked.path))

    # Spec tab
    with tabs[1]:
        st.json(json.loads(spec.model_dump_json()))

    # Plan tab
    with tabs[2]:
        st.markdown(f"**{plan.project_name}** — {plan.summary}")
        st.markdown("**Files:**")
        for pf in plan.files:
            st.markdown(f"- `{pf.path}` · *{pf.owner}* — {pf.summary}")
        if plan.setup_commands:
            st.markdown("**Setup:**")
            st.code("\n".join(plan.setup_commands), language="bash")
        if plan.run_commands:
            st.markdown("**Run:**")
            st.code("\n".join(plan.run_commands), language="bash")

    # Findings tab
    with tabs[3]:
        if not findings:
            st.success("No findings raised. (clean review)")
        else:
            for sev in ("block", "major", "minor", "nit"):
                hits = [f for f in findings if f.severity == sev]
                if not hits:
                    continue
                color = SEVERITY_COLOR[sev]
                st.markdown(f"### :{color}[{sev.upper()}] ({len(hits)})")
                for f in hits:
                    where = f.file + (f":{f.line}" if f.line else "")
                    st.markdown(f"- `{where}` · `{f.rule}` — {f.message}")

    # Tests tab (only if we have test results)
    runlog_idx = 4
    if has_tests:
        with tabs[4]:
            assert test_run is not None
            if not test_run.ran:
                st.info(
                    f"⏭️ Test phase was skipped: {test_run.skip_reason or 'unknown'}"
                )
            elif test_run.passed:
                st.success(
                    f"✅ All tests passed (exit={test_run.exit_code}, "
                    f"{test_run.duration_s:.1f}s)"
                )
            else:
                st.error(
                    f"❌ Tests failed (exit={test_run.exit_code}, "
                    f"{len(test_run.failures)} failure(s), "
                    f"{test_run.duration_s:.1f}s)"
                )
                for tf in test_run.failures:
                    st.markdown(
                        f"- `{tf.file_path}::{tf.test_name}` — {tf.error_excerpt}"
                    )
                if test_findings:
                    st.markdown(
                        f"**Fed back to implementers as {len(test_findings)} "
                        f"finding(s).** A second-pass fix iteration ran on "
                        f"these failures."
                    )
            if test_run.raw_output:
                with st.expander("pytest output (last ~10kb)", expanded=False):
                    st.code(test_run.raw_output, language="text")
        runlog_idx = 5

    # Run log
    with tabs[runlog_idx]:
        for ev, detail in st.session_state.events:
            st.text(f"{ev:<30}  {detail}")


# ─── main ─────────────────────────────────────────────────────────────────


def main() -> None:
    st.title("🤖 orgos-team")
    st.caption(
        "Autonomous 8-agent code generator on Canopy Wave. "
        "MVP: Product → Architect → 4 implementers → Reviewer + Security → Fixers."
    )

    _render_sidebar()

    if st.session_state.get("demo_mode", False):
        st.warning(
            "🎭 **Demo mode is active.** No LLM calls will be made. "
            "Output is a deterministic demo project (`hello` CLI) so you can "
            "see the full UI flow without an API key."
        )

    idea, submit = _render_idea_input()

    if submit:
        config = _build_config_from_sidebar()
        if config is None:
            return

        # Reset state for a fresh run
        st.session_state.events = []
        st.session_state.result = None
        st.session_state.error = None
        st.session_state.project_root = None
        st.session_state.status = "running"
        st.session_state.started_at = datetime.now()
        st.session_state.finished_at = None

        q: queue.Queue = queue.Queue()
        st.session_state.event_queue = q

        do_git = bool(st.session_state.get("git_init", True))
        demo_mode = bool(st.session_state.get("demo_mode", False))
        auto_tests = bool(st.session_state.get("auto_execute_tests", False))
        t = threading.Thread(
            target=_worker_target,
            args=(config, idea, do_git, demo_mode, auto_tests, q),
            daemon=True,
        )
        t.start()
        st.session_state.worker = t
        st.rerun()

    if st.session_state.status == "running":
        still_running = _drain_queue()
        _render_progress()
        if still_running:
            time.sleep(0.5)
            st.rerun()
        else:
            st.rerun()
    elif st.session_state.status == "done":
        _render_progress()
        st.divider()
        _render_results()
    elif st.session_state.status == "error":
        _render_progress()
        st.divider()
        st.error(st.session_state.error or "Unknown error")
        if st.button("Reset"):
            for k in ("status", "events", "result", "error", "worker", "event_queue"):
                st.session_state[k] = None if k != "events" else []
            st.session_state.status = "idle"
            st.rerun()


if __name__ == "__main__":
    main()
