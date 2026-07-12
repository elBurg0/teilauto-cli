from __future__ import annotations

from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()
err_console = Console(stderr=True)


def fuel_text(fuel: float | None) -> Text:
    if fuel is None:
        return Text("?", style="dim")
    style = "green" if fuel >= 50 else "yellow" if fuel >= 25 else "red"
    return Text(f"{fuel:.0f}%", style=style)


def local_time(iso: str | None) -> str:
    """Render an API ISO/Z timestamp as local '%Y-%m-%d %H:%M'."""
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return "—"
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


def kv_panel(title: str, mapping: dict[str, object]) -> Panel:
    body = Text()
    width = max((len(key) for key in mapping), default=0)
    for key, value in mapping.items():
        body.append(f"{key.rjust(width)}  ", style="bold dim")
        body.append(f"{value}\n")
    return Panel(body, title=title, expand=False)
