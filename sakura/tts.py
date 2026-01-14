"""Text-to-speech output for Sakura using Edge TTS."""

import asyncio
import re
import logging
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Optional

import edge_tts
from pydub import AudioSegment

from .config import TTS_VOICE, TTS_PITCH, TTS_RATE

logger = logging.getLogger(__name__)

_current_playback: Optional[subprocess.Popen] = None
_tts_disabled: bool = False
_tts_warned: bool = False


def _clean_text_for_tts(text: str) -> str:
    """Remove action markers and problematic characters for TTS."""
    # Remove [EMOTION:xxx] tags specifically (in case any slipped through)
    text = re.sub(r'\[EMOTION:\w+\]', '', text, flags=re.IGNORECASE)
    # Remove any remaining square bracket content [like this] or [action]
    text = re.sub(r'\[[^\]]+\]', '', text)
    # Remove asterisk-wrapped actions like *blushes*, *looks away*
    text = re.sub(r'\*[^*]+\*', '', text)
    # Remove parenthetical notes like (Note: ...) or (Translation: ...)
    text = re.sub(r'\([^)]*\)', '', text)
    # Normalize curly quotes/apostrophes to straight (fixes Unicode mispronunciation)
    text = text.replace(''', "'").replace(''', "'")
    text = text.replace('"', '"').replace('"', '"')
    # Replace ellipsis with comma for natural pause (otherwise reads as "ten-ten")
    text = text.replace('...', ',')
    text = text.replace('…', ',')
    # Collapse adjacent commas to single comma with space (e.g., ", ," → ", ")
    text = re.sub(r',(\s*,)+', ', ', text)
    # Clean up extra whitespace
    text = ' '.join(text.split())
    # Remove leading/trailing commas
    return text.strip(' ,')


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

        if not asyncio.run(_generate_audio(_clean_text_for_tts(text), audio_path)):
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


async def _generate_bilingual_audio(
    japanese: str, english: str
) -> tuple[Path | None, Path | None]:
    """Generate audio files for both languages in parallel."""
    jp_path = Path(tempfile.mktemp(suffix="_jp.mp3"))
    en_path = Path(tempfile.mktemp(suffix="_en.mp3"))

    # Clean text for TTS
    jp_clean = _clean_text_for_tts(japanese) if japanese else ""
    en_clean = _clean_text_for_tts(english) if english else ""

    # Generate both audio files in parallel
    tasks = []
    if jp_clean:
        tasks.append(_generate_audio(jp_clean, jp_path))
    if en_clean:
        tasks.append(_generate_audio(en_clean, en_path))

    if not tasks:
        return None, None

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Determine which succeeded
    jp_success = False
    en_success = False
    result_idx = 0

    if jp_clean:
        jp_success = results[result_idx] is True
        result_idx += 1
    if en_clean:
        en_success = results[result_idx] is True

    return (
        jp_path if jp_success else None,
        en_path if en_success else None,
    )


def _concatenate_audio(jp_path: Path | None, en_path: Path | None) -> Path | None:
    """Concatenate JP + silence + EN audio into single file."""
    jp_segment = None
    en_segment = None

    # Load JP audio if available
    if jp_path and jp_path.exists():
        try:
            jp_segment = AudioSegment.from_mp3(str(jp_path))
        except Exception as e:
            logger.warning(f"Failed to load JP audio: {e}")

    # Load EN audio if available
    if en_path and en_path.exists():
        try:
            en_segment = AudioSegment.from_mp3(str(en_path))
        except Exception as e:
            logger.warning(f"Failed to load EN audio: {e}")

    # Build combined audio
    if not jp_segment and not en_segment:
        return None

    segments = []
    if jp_segment:
        segments.append(jp_segment)
    if jp_segment and en_segment:
        segments.append(AudioSegment.silent(duration=500))  # 0.5s pause
    if en_segment:
        segments.append(en_segment)

    # Combine all segments
    combined = segments[0]
    for segment in segments[1:]:
        combined = combined + segment

    # Export to temp file
    output_path = Path(tempfile.mktemp(suffix="_combined.mp3"))
    combined.export(str(output_path), format="mp3")

    return output_path


def speak_bilingual(japanese: str, english: str) -> Optional[str]:
    """Convert bilingual text to speech and play (non-blocking).

    Generates JP and EN audio in parallel, concatenates with 0.5s pause.
    Graceful degradation: plays whatever audio succeeds.

    Returns None on success, or a warning message on first failure.
    """
    global _tts_disabled, _current_playback, _tts_warned

    if _tts_disabled:
        return None

    stop_speaking()

    jp_path: Optional[Path] = None
    en_path: Optional[Path] = None
    combined_path: Optional[Path] = None

    try:
        # Generate audio files in parallel
        jp_path, en_path = asyncio.run(_generate_bilingual_audio(japanese, english))

        # If both failed
        if not jp_path and not en_path:
            if not _tts_warned:
                _tts_warned = True
                return "Hmph, my voice isn't working today... N-not that I wanted to talk to you anyway!"
            return None

        # Concatenate available audio
        combined_path = _concatenate_audio(jp_path, en_path)

        # Clean up individual files
        if jp_path:
            jp_path.unlink(missing_ok=True)
        if en_path:
            en_path.unlink(missing_ok=True)

        if not combined_path:
            if not _tts_warned:
                _tts_warned = True
                return "Hmph, my voice isn't working today... N-not that I wanted to talk to you anyway!"
            return None

        # Play combined audio
        _current_playback = _play_audio(combined_path)

        # Clean up after playback
        threading.Thread(
            target=_cleanup_temp_file,
            args=(combined_path, _current_playback),
            daemon=True,
        ).start()

        return None

    except FileNotFoundError:
        logger.error("afplay not found - TTS disabled")
        _tts_disabled = True
        for path in [jp_path, en_path, combined_path]:
            if path:
                path.unlink(missing_ok=True)
        if not _tts_warned:
            _tts_warned = True
            return "Hmph, my voice isn't working today... N-not that I wanted to talk to you anyway!"
        return None
    except Exception as e:
        logger.warning(f"Bilingual TTS failed: {e}")
        for path in [jp_path, en_path, combined_path]:
            if path:
                path.unlink(missing_ok=True)
        return None
