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

# Generate animated character GIF (one-time setup)
python -m sakura.animate

# Run Sakura
python -m sakura
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| AI Model | Ollama + dolphin-mistral (local, uncensored) |
| Speech Recognition | mlx-whisper (Apple Silicon) |
| Text-to-Speech | Edge TTS (ja-JP-NanamiNeural, pitch +25Hz, rate +5%) |
| Audio Playback | afplay (macOS) |
| Terminal UI | Rich |
| Emotion Images | Local SDXL (Animagine XL 4.0 / NoobAI XL) |
| Character Animation | AnimateDiff + Counterfeit V3.0 (SD 1.5) |
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
# Optional
OLLAMA_HOST=http://localhost:11434  # Default Ollama host
SAKURA_DEBUG=1                       # Set any value to enable debug logging
SAKURA_NSFW=true                     # Enable NSFW image mode (requires setup)
```

## File Structure

```
maidai-v3/
├── sakura/              # Main package
│   ├── __init__.py
│   ├── __main__.py      # Entry point
│   ├── setup.py         # One-time image generation
│   ├── animate.py       # Animated GIF generation (AnimateDiff)
│   ├── core.py          # Main conversation loop
│   ├── ai.py            # Ollama integration
│   ├── speech.py        # Whisper STT + silence detection
│   ├── tts.py           # Edge TTS + afplay
│   ├── emotions.py      # Emotion detection + image display
│   ├── ui.py            # Rich terminal interface
│   ├── memory.py        # Conversation history persistence
│   ├── config.py        # Configuration constants
│   ├── nsfw_prompts.example.py  # NSFW prompt template
│   └── nsfw_prompts.py  # Local NSFW prompts (gitignored)
├── assets/
│   ├── sakura.gif       # Animated blinking character (README display, 45fps)
│   ├── sakura.png       # Static character art (animation source)
│   ├── cache/           # Cached SFW emotion images
│   └── emotions_nsfw/   # Cached NSFW emotion images (gitignored)
├── data/
│   └── history/         # Saved conversation history
├── requirements.txt
├── pyproject.toml
├── README.md
├── LICENSE
├── CLAUDE.md            # This file
└── ARCHITECTURE.md      # System architecture
```

## Dual Image System (SFW/NSFW)

Sakura supports two image modes:

| Mode | Model | Folder | Toggle |
|------|-------|--------|--------|
| SFW (default) | Animagine XL 4.0 | `assets/cache/` | Default |
| NSFW | NoobAI XL | `assets/emotions_nsfw/` | `SAKURA_NSFW=true` |

### Setup

```bash
# Generate SFW images (default)
python -m sakura.setup

# Generate NSFW images (requires local nsfw_prompts.py)
python -m sakura.setup --nsfw
```

### NSFW Configuration

1. Copy `sakura/nsfw_prompts.example.py` to `sakura/nsfw_prompts.py`
2. Customize prompts in the local file
3. Run setup with `--nsfw` flag
4. Enable with `SAKURA_NSFW=true` environment variable

**Note:** `nsfw_prompts.py` and `assets/emotions_nsfw/` are gitignored - content stays local.

## Common Issues & Fixes

### Sakura won't speak
- Check Edge TTS connectivity
- Verify afplay is available (macOS only)

### Voice recognition not working
- Ensure microphone permissions are granted
- Check mlx-whisper model downloads successfully on first run
- silero-vad requires internet on first launch (loaded via torch.hub)

### Ollama connection failed
- Verify Ollama is running: `ollama list`
- Check OLLAMA_HOST environment variable

### Images not generating
- Verify Hugging Face model is downloaded (`python -m sakura.setup`)
- Ensure sufficient disk space for SDXL model (~7GB)

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
