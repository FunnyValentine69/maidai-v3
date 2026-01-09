"""Voice input handling for Sakura using silero-vad and mlx-whisper."""

import os
import tempfile

import numpy as np
import scipy.io.wavfile as wav
import sounddevice as sd
import torch

from .config import (
    MAX_RECORDING_S,
    SAMPLE_RATE,
    SILENCE_THRESHOLD_S,
    WHISPER_MODEL,
)

# Module-level state
_whisper_model = None
_vad_model = None
_vad_iterator = None
_speech_available = False


def _display_status(text: str) -> None:
    """Display status message (lazy import to avoid circular import)."""
    try:
        from .ui import display_status
        display_status(text)
    except ImportError:
        print(text)


def init() -> None:
    """Initialize voice input models. Call at startup."""
    global _whisper_model, _vad_model, _vad_iterator, _speech_available

    try:
        _load_vad_model()
        _load_whisper_model()
        _speech_available = True
    except Exception as e:
        _display_status(f"Voice input disabled: {e}")
        _speech_available = False


def _load_vad_model() -> None:
    """Load silero-vad model via torch.hub (avoids onnxruntime dependency)."""
    global _vad_model, _vad_iterator

    _vad_model, utils = torch.hub.load(
        repo_or_dir="snakers4/silero-vad",
        model="silero_vad",
        trust_repo=True,
    )
    # Get VADIterator from utils
    _, _, _, VADIterator, _ = utils
    _vad_iterator = VADIterator(_vad_model, sampling_rate=SAMPLE_RATE)


def _load_whisper_model() -> None:
    """Pre-warm mlx-whisper by importing it (model loads on first transcribe)."""
    global _whisper_model

    import mlx_whisper
    _whisper_model = mlx_whisper  # Store module reference


def is_available() -> bool:
    """Check if voice input is available."""
    return _speech_available


def _record_until_silence() -> np.ndarray | None:
    """Record audio until silence is detected after speech.

    Returns:
        Audio data as int16 numpy array, or None if no speech detected.
    """
    if _vad_iterator is None:
        return None

    # Reset VAD state
    _vad_iterator.reset_states()

    # Calculate chunk size (512 samples for 16kHz = 32ms)
    chunk_samples = 512
    max_samples = int(MAX_RECORDING_S * SAMPLE_RATE)
    silence_samples = int(SILENCE_THRESHOLD_S * SAMPLE_RATE)

    audio_chunks: list[np.ndarray] = []
    speech_started = False
    silence_after_speech = 0
    total_samples = 0

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=chunk_samples,
        ) as stream:
            while total_samples < max_samples:
                # Read audio chunk
                data, _ = stream.read(chunk_samples)
                audio_chunk = data.flatten()
                audio_chunks.append(audio_chunk)
                total_samples += len(audio_chunk)

                # Convert to float32 for VAD
                audio_float = audio_chunk.astype(np.float32) / 32768.0

                # Convert to torch tensor for VAD
                audio_tensor = torch.from_numpy(audio_float)

                # Feed to VAD
                speech_dict = _vad_iterator(audio_tensor, return_seconds=False)

                if speech_dict:
                    if "start" in speech_dict:
                        speech_started = True
                        silence_after_speech = 0
                    elif "end" in speech_dict:
                        # Speech ended - stop recording
                        break

                # Track silence after speech started (backup detection)
                if speech_started:
                    energy = np.abs(audio_float).mean()
                    if energy < 0.01:
                        silence_after_speech += len(audio_chunk)
                    else:
                        silence_after_speech = 0

                    if silence_after_speech >= silence_samples:
                        break

    except Exception as e:
        _display_status(f"Recording error: {e}")
        return None

    if not speech_started or len(audio_chunks) == 0:
        return None

    return np.concatenate(audio_chunks)


def _transcribe(audio: np.ndarray) -> str | None:
    """Transcribe audio using mlx-whisper.

    Args:
        audio: Audio data as int16 numpy array.

    Returns:
        Transcribed text, or None on error.
    """
    if _whisper_model is None:
        return None

    temp_path = None
    try:
        # Create temp file path
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name

        # Write WAV file (after closing the temp file)
        wav.write(temp_path, SAMPLE_RATE, audio)

        # Transcribe using mlx-whisper
        # path_or_hf_repo specifies the model (e.g., "mlx-community/whisper-small")
        result = _whisper_model.transcribe(
            temp_path,
            path_or_hf_repo=f"mlx-community/whisper-{WHISPER_MODEL}",
        )
        return result.get("text", "").strip()

    except Exception as e:
        _display_status(f"Transcription error: {e}")
        return None

    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def listen() -> str | None:
    """Record and transcribe user speech.

    Returns:
        Transcribed text, or None if failed/no speech.
    """
    if not _speech_available:
        return None

    _display_status("Listening...")

    audio = _record_until_silence()
    if audio is None or len(audio) < SAMPLE_RATE // 2:  # Less than 0.5s
        _display_status("No speech detected")
        return None

    _display_status("Processing...")

    text = _transcribe(audio)
    if not text:
        _display_status("Could not transcribe")
        return None

    return text
