# MaidAI v3 - Sakura

A tsundere Japanese maid AI that runs entirely on local AI. Voice chat with your own personal maid who speaks in bilingual JRPG-style dialogue.

## Features

- **Local AI** - Powered by Ollama (llama3.2), no cloud AI required
- **Bilingual Dialogue** - Japanese first, English translation below (JRPG style)
- **Voice Input** - Speak naturally with mlx-whisper + silero-vad (Apple Silicon optimized)
- **Text-to-Speech** - Nanami voice via Edge TTS (+25Hz pitch, +5% rate)
- **Emotion Images** - 14 emotion expressions generated with Animagine XL 4.0
- **Conversation Memory** - Persistent memory across sessions with automatic summarization
- **Tsundere Personality** - Sakura is cold at first but gradually warms up to you

## Screenshots

<!-- TODO: Add screenshots -->

## Installation

### Prerequisites

- Python 3.12+
- [Ollama](https://ollama.ai/) installed and running
- macOS (for afplay audio playback)
- iTerm2 (for emotion image display)
- [Hugging Face API token](https://huggingface.co/settings/tokens) (for image generation)

### Setup

```bash
# Clone the repository
git clone https://github.com/FunnyValentine69/maidai-v3.git
cd maidai-v3

# Install dependencies
pip install -r requirements.txt

# Pull the AI model
ollama pull llama3.2

# Set your Hugging Face token
export HF_API_TOKEN=your_token_here

# Generate emotion images (one-time setup)
python -m sakura.setup

# Run Sakura
python -m sakura
```

## Usage

```bash
# Start Sakura
python -m sakura
```

**Controls:**
- Type your message and press Enter
- Press `SPACE` as the first character to use voice input
- Press `Ctrl+C` to exit

## Project Structure

```
maidai-v3/
├── sakura/           # Main package
│   ├── ai.py         # Ollama integration + bilingual parsing
│   ├── speech.py     # Voice input (mlx-whisper + silero-vad)
│   ├── tts.py        # Text-to-speech (Edge TTS)
│   ├── emotions.py   # Emotion detection + image display
│   ├── memory.py     # Conversation persistence
│   ├── ui.py         # Rich terminal UI
│   └── core.py       # Main conversation loop
├── assets/cache/     # Cached emotion images
├── data/history/     # Saved conversations
└── requirements.txt
```

## Documentation

- [CLAUDE.md](CLAUDE.md) - Development guidelines
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture
- [TODO.md](TODO.md) - Project roadmap

## Credits

**Created by** [FunnyValentine69](https://github.com/FunnyValentine69)

**Built with:**
- [Ollama](https://ollama.ai/) - Local AI inference
- [Edge TTS](https://github.com/rany2/edge-tts) - Microsoft text-to-speech
- [mlx-whisper](https://github.com/ml-explore/mlx-examples) - Apple Silicon speech recognition
- [Animagine XL 4.0](https://huggingface.co/cagliostrolab/animagine-xl-4.0) - Anime image generation
- [Rich](https://github.com/Textualize/rich) - Terminal UI
- [silero-vad](https://github.com/snakers4/silero-vad) - Voice activity detection

## License

MIT
