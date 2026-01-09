"""Text-to-speech output for Sakura using Edge TTS."""

import asyncio
import logging
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Optional

import edge_tts

from .config import TTS_VOICE, TTS_PITCH, TTS_RATE

logger = logging.getLogger(__name__)

_current_playback: Optional[subprocess.Popen] = None
_tts_disabled: bool = False
_tts_warned: bool = False


async def _generate_audio(text: str, output_path: Path) -> bool:
    """Generate audio file using Edge TTS."""
    try:
        communicate = edge_tts.Communicate(
            text,
            TTS_VOICE,
            pitch=TTS_PITCH,
            rate=TTS_RATE,
        )
        await communicate.save(str(output_path))
        return True
    except Exception as e:
        logger.warning(f"Edge TTS generation failed: {e}")
        return False


def _play_audio(audio_path: Path) -> subprocess.Popen:
    """Start afplay in background."""
    return subprocess.Popen(
        ["afplay", str(audio_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _cleanup_temp_file(path: Path, process: subprocess.Popen) -> None:
    """Wait for process and clean up temp file."""
    try:
        process.wait()
    except Exception:
        pass
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


def stop_speaking() -> None:
    """Stop any currently playing audio."""
    global _current_playback
    if _current_playback is not None:
        try:
            _current_playback.terminate()
        except Exception:
            pass
        _current_playback = None


def is_speaking() -> bool:
    """Check if audio is currently playing."""
    if _current_playback is None:
        return False
    return _current_playback.poll() is None


def speak(text: str) -> Optional[str]:
    """Convert text to speech and play (non-blocking).

    Returns None on success, or a warning message on first failure.
    """
    global _tts_disabled, _current_playback, _tts_warned

    if _tts_disabled:
        return None

    stop_speaking()

    audio_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            audio_path = Path(f.name)

        if not asyncio.run(_generate_audio(text, audio_path)):
            audio_path.unlink(missing_ok=True)
            if not _tts_warned:
                _tts_warned = True
                return "Hmph, my voice isn't working today... N-not that I wanted to talk to you anyway!"
            return None

        _current_playback = _play_audio(audio_path)

        threading.Thread(
            target=_cleanup_temp_file,
            args=(audio_path, _current_playback),
            daemon=True,
        ).start()
        return None

    except FileNotFoundError:
        logger.error("afplay not found - TTS disabled")
        _tts_disabled = True
        if audio_path:
            audio_path.unlink(missing_ok=True)
        if not _tts_warned:
            _tts_warned = True
            return "Hmph, my voice isn't working today... N-not that I wanted to talk to you anyway!"
        return None
    except Exception as e:
        logger.warning(f"TTS failed: {e}")
        if audio_path:
            audio_path.unlink(missing_ok=True)
        return None
