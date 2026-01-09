"""Rich terminal interface for Sakura."""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme

# Cherry blossom theme
SAKURA_THEME = Theme({
    "sakura": "magenta",
    "sakura.name": "bold magenta",
    "sakura.emotion": "italic bright_magenta",
    "user": "cyan",
    "user.name": "bold cyan",
    "status": "dim white",
    "error": "bold red",
})

console = Console(theme=SAKURA_THEME)


def display_greeting(text: str, emotion: str = "neutral") -> None:
    """Display Sakura's greeting message."""
    header = Text()
    header.append("🌸 Sakura", style="sakura.name")
    header.append(" ", style="default")
    header.append(f"[{emotion}]", style="sakura.emotion")

    panel = Panel(
        Text(text, style="sakura"),
        title=header,
        title_align="left",
        border_style="magenta",
        padding=(0, 1),
    )
    console.print(panel)
    console.print()


def display_message(role: str, text: str, emotion: str | None = None) -> None:
    """Display a conversation message."""
    if role == "assistant":
        header = Text()
        header.append("🌸 Sakura", style="sakura.name")
        if emotion:
            header.append(" ", style="default")
            header.append(f"[{emotion}]", style="sakura.emotion")

        panel = Panel(
            Text(text, style="sakura"),
            title=header,
            title_align="left",
            border_style="magenta",
            padding=(0, 1),
        )
        console.print(panel)
    else:
        header = Text()
        header.append("You", style="user.name")

        panel = Panel(
            Text(text, style="user"),
            title=header,
            title_align="left",
            border_style="cyan",
            padding=(0, 1),
        )
        console.print(panel)

    console.print()


def get_input() -> str:
    """Get user text input."""
    try:
        user_input = console.input("[cyan]You:[/cyan] ")
        console.print()
        return user_input.strip()
    except EOFError:
        return ""
    except KeyboardInterrupt:
        raise


def display_status(text: str) -> None:
    """Display a status message."""
    console.print(f"[status]{text}[/status]")


def display_error(text: str) -> None:
    """Display an error message."""
    console.print(f"[error]{text}[/error]")


def display_welcome() -> None:
    """Display welcome banner."""
    banner = Text()
    banner.append("🌸 MaidAI v3 🌸\n", style="bold magenta")
    banner.append("Your Tsundere Maid Assistant", style="italic magenta")

    console.print()
    console.print(Panel(
        banner,
        border_style="magenta",
        padding=(0, 2),
    ))
    console.print()


def clear_screen() -> None:
    """Clear the terminal screen."""
    console.clear()
