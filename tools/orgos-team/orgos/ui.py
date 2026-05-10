"""Rich-based CLI display: progress events from the workflow rendered as a tree."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


class ProgressDisplay:
    """Lightweight progress reporter wired into workflow.run_workflow."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def __call__(self, event: str, detail: str) -> None:
        self.events.append((event, detail))
        symbol = self._symbol_for(event)
        console.print(f"[bold cyan]{symbol}[/bold cyan] [bold]{event}[/bold]  {detail}")

    @staticmethod
    def _symbol_for(event: str) -> str:
        if event.endswith(".start"):
            return "▶"
        if event.endswith(".done"):
            return "■"
        return "·"


def print_banner(idea: str) -> None:
    panel = Panel(
        Text(idea.strip(), style="bold white"),
        title="[bold cyan]orgos-team[/bold cyan]  •  idea",
        border_style="cyan",
    )
    console.print(panel)


def print_summary(project_root: str, file_count: int, finding_count: int) -> None:
    body = Text()
    body.append("project:   ", style="bold")
    body.append(project_root + "\n")
    body.append("files:     ", style="bold")
    body.append(f"{file_count}\n")
    body.append("findings:  ", style="bold")
    body.append(f"{finding_count}\n")
    body.append("next:      ", style="bold")
    body.append("cd into the project directory and follow its README.md")
    console.print(Panel(body, title="[bold green]done[/bold green]", border_style="green"))


def print_error(msg: str) -> None:
    console.print(Panel(Text(msg, style="bold red"), title="[bold red]error[/bold red]", border_style="red"))
