"""Rich terminal interface for Sakura."""

import sys
import termios
import tty
from typing import Literal

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme

from .emotions import display_emotion

# Cherry blossom theme
SAKURA_THEME = Theme({
    "sakura": "magenta",
    "sakura.name": "bold magenta",
    "sakura.emotion": "italic bright_magenta",
    "sakura.japanese": "bright_white",
    "sakura.english": "dim white",
    "user": "cyan",
    "user.name": "bold cyan",
    "status": "dim white",
    "error": "bold red",
})

console = Console(theme=SAKURA_THEME)


def display_bilingual_message(emotion: str, japanese: str, english: str) -> None:
    """Display Sakura's bilingual message in JRPG style.

    Shows emotion image above, then a panel with:
    - Header: 🌸 Sakura [emotion]
    - Japanese text (bright white)
    - English text (dim gray)
    """
    # Display emotion image first
    display_emotion(emotion)

    # Build header
    header = Text()
    header.append("🌸 Sakura", style="sakura.name")
    header.append(" ", style="default")
    header.append(f"[{emotion}]", style="sakura.emotion")

    # Build content with both languages
    content = Text()
    if japanese:
        content.append(japanese, style="sakura.japanese")
        content.append("\n\n", style="default")
    content.append(english, style="sakura.english")

    panel = Panel(
        content,
        title=header,
        title_align="left",
        border_style="magenta",
        padding=(0, 1),
    )
    console.print(panel)
    console.print()


def display_user_message(text: str) -> None:
    """Display a user message."""
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


def get_input_with_voice() -> tuple[str, Literal["text", "voice"]]:
    """Get user input, supporting both text and voice.

    Press SPACE as first character to trigger voice input.
    Otherwise, type normally.

    Returns:
        Tuple of (user_text, input_mode).
    """
    from .speech import is_available, listen

    # Show prompt with voice hint if available
    if is_available():
        console.print("[cyan]You[/cyan] [dim](SPACE=speak)[/dim]: ", end="")
    else:
        console.print("[cyan]You:[/cyan] ", end="")

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        tty.setcbreak(fd)
        buffer: list[str] = []

        while True:
            char = sys.stdin.read(1)

            # Space as first char = voice input
            if char == " " and not buffer and is_available():
                console.print()  # New line
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

                text = listen()
                if text:
                    return text, "voice"
                else:
                    # Fallback to text input
                    display_status("Please type instead")
                    return get_input(), "text"

            # Enter = submit
            elif char in ("\n", "\r"):
                console.print()  # New line
                return "".join(buffer).strip(), "text"

            # Backspace
            elif char == "\x7f":
                if buffer:
                    buffer.pop()
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()

            # Ctrl+C
            elif char == "\x03":
                console.print()
                raise KeyboardInterrupt

            # Regular character
            else:
                buffer.append(char)
                sys.stdout.write(char)
                sys.stdout.flush()

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


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
