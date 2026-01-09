"""Main conversation loop for Sakura."""

import random

from .ai import generate_response
from .config import GREETINGS
from .emotions import display_emotion
from .speech import init as init_speech
from .tts import speak, stop_speaking
from .ui import (
    display_greeting,
    display_message,
    display_status,
    display_welcome,
    get_input_with_voice,
)


def run() -> None:
    """Run the main conversation loop."""
    # Track conversation history (in-memory for Phase 1)
    messages: list[dict] = []

    # Show welcome banner
    display_welcome()

    # Initialize voice input
    display_status("Loading voice models...")
    init_speech()

    # Pick random greeting and display
    greeting, emotion = random.choice(GREETINGS)
    display_emotion(emotion)
    display_greeting(greeting, emotion)
    if warning := speak(greeting):
        display_status(warning)

    display_status("Type message or press [SPACE] to speak. Ctrl+C to exit.")

    # Main conversation loop
    try:
        while True:
            # Get user input (text or voice)
            user_input, _ = get_input_with_voice()
            stop_speaking()

            # Skip empty input
            if not user_input:
                continue

            # Add user message to history
            messages.append({"role": "user", "content": user_input})

            # Generate response
            response_text, emotion = generate_response(messages)

            # Add assistant message to history (with emotion for Phase 4)
            messages.append({
                "role": "assistant",
                "content": response_text,
                "emotion": emotion,
            })

            # Display response
            display_message("assistant", response_text, emotion)
            if warning := speak(response_text):
                display_status(warning)

    except KeyboardInterrupt:
        print()  # New line after ^C
        display_status("Sayonara, Goshujin-sama~ 🌸")
