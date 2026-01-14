# MaidAI v3 - Development Guidelines

## Project Overview

MaidAI v3 is a Japanese maid AI assistant named **Sakura** with a tsundere personality. She runs entirely on local AI (Ollama) with voice interaction capabilities.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Ensure Ollama is running with dolphin-mistral
ollama pull dolphin-mistral

# Generate emotion images (one-time setup)
python -m sakura.setup

# Run Sakura
python -m sakura
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| AI Model | Ollama + dolphin-mistral (local, uncensored) |
| Speech Recognition | faster-whisper (local) |
| Text-to-Speech | Edge TTS (ja-JP-NanamiNeural, pitch +25Hz, rate +5%) |
| Audio Playback | afplay (macOS) |
| Terminal UI | Rich |
| Emotion Images | Hugging Face Inference API (Animagine XL) |
| Python Version | 3.12+ |

## Development Rules

### 1. Simplicity First
- Every change should impact as little code as possible
- Avoid complex abstractions - prefer straightforward implementations
- If a solution feels complicated, step back and simplify

### 2. Code Style
- Use type hints for function signatures
- Minimal docstrings - only for non-obvious logic
- Follow PEP 8
- Keep functions small and focused (< 30 lines ideally)

### 3. Before Making Changes
- Read the relevant files first - never speculate about code you haven't opened
- Check in before making major changes
- Test the change manually before committing

### 4. Error Handling
- Handle errors gracefully - Sakura should not crash mid-conversation
- Provide fallbacks (e.g., text input if voice fails)
- Log errors but keep the conversation flowing

### 5. Testing
- Run `pytest` for core logic tests
- Manual testing for audio/TTS components
- Test the full conversation loop before committing

## Critical Implementation Notes (from v1/v2 lessons)

### Audio Playback
- **USE**: `afplay` (macOS native)
- **DO NOT USE**: pygame (caused issues in previous versions)

### Voice Recording
- Spacebar initiates listening mode
- Silence detection (VAD) ends recording automatically
- Suppress spacebar character output during recording

## Environment Variables

```bash
# Required
HF_API_TOKEN=your_huggingface_token

# Optional
OLLAMA_HOST=http://localhost:11434  # Default Ollama host
SAKURA_DEBUG=false                   # Enable debug logging
```

## File Structure

```
maidai-v3/
├── sakura/              # Main package
│   ├── __init__.py
│   ├── __main__.py      # Entry point
│   ├── setup.py         # One-time image generation
│   ├── core.py          # Main conversation loop
│   ├── ai.py            # Ollama integration
│   ├── speech.py        # Whisper STT + silence detection
│   ├── tts.py           # Edge TTS + afplay
│   ├── emotions.py      # Emotion detection + image display
│   ├── ui.py            # Rich terminal interface
│   ├── memory.py        # Conversation history persistence
│   └── config.py        # Configuration constants
├── assets/
│   └── cache/           # Cached emotion images
├── data/
│   └── history/         # Saved conversation history
├── tests/
├── requirements.txt
├── pyproject.toml
├── CLAUDE.md            # This file
└── ARCHITECTURE.md      # System architecture
```

## Common Issues & Fixes

### Sakura won't speak
- Check Edge TTS connectivity
- Verify afplay is available (macOS only)

### Voice recognition not working
- Ensure microphone permissions are granted
- Check faster-whisper model is downloaded
- Verify silence detection threshold

### Ollama connection failed
- Verify Ollama is running: `ollama list`
- Check OLLAMA_HOST environment variable

### Images not generating
- Verify HF_API_TOKEN is set
- Check Hugging Face API rate limits

## Git Workflow

- Commit small, focused changes
- Test before committing
- Use descriptive commit messages

## Key Principles

1. **Never crash** - Handle all errors gracefully
2. **Stay in character** - Sakura is a tsundere maid
3. **Keep conversations flowing** - Don't block on failures
4. **Memory matters** - Persist conversation history when possible
5. **macOS first** - Platform-specific features are OK for now
