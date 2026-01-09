"""Emotion image display for Sakura using iTerm2 inline images."""

import base64
import logging
import os
import sys
from pathlib import Path

from .config import CACHE_DIR, EMOTIONS

logger = logging.getLogger(__name__)

# Display width in character cells
DISPLAY_WIDTH = 30


def is_iterm2() -> bool:
    """Check if running in iTerm2."""
    return os.environ.get("TERM_PROGRAM") == "iTerm.app"


def get_image_path(emotion: str) -> Path | None:
    """Get path to cached emotion image if exists."""
    if emotion not in EMOTIONS:
        logger.warning(f"Unknown emotion: {emotion}")
        return None

    image_path = CACHE_DIR / f"{emotion}.png"
    if not image_path.exists():
        logger.warning(f"Emotion image not found: {image_path}")
        return None

    return image_path


def _iterm2_display(image_path: Path, width: int = DISPLAY_WIDTH) -> None:
    """Display image using iTerm2 escape sequence.

    iTerm2 inline image protocol:
    ESC ] 1337 ; File = [args] : base64_data BEL

    Args:
        image_path: Path to the image file
        width: Display width in character cells
    """
    # Read and encode image
    with open(image_path, "rb") as f:
        image_data = f.read()
    encoded = base64.b64encode(image_data).decode("ascii")

    # Build escape sequence
    # inline=1 displays the image (vs downloading)
    # width specifies character cell width
    escape_seq = f"\033]1337;File=inline=1;width={width}:{encoded}\a"

    # Flush pending output (Rich console) before writing image
    sys.stdout.flush()

    # Write escape sequence and newline
    sys.stdout.write(escape_seq)
    sys.stdout.write("\n")
    sys.stdout.flush()


def display_emotion(emotion: str) -> None:
    """Display emotion image in terminal.

    Silently skips if not iTerm2 or image not found.
    """
    # Skip if not iTerm2
    if not is_iterm2():
        return

    # Get image path
    image_path = get_image_path(emotion)
    if image_path is None:
        return

    # Display image
    try:
        _iterm2_display(image_path)
    except Exception as e:
        logger.error(f"Failed to display emotion image: {e}")
