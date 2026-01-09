"""Main conversation loop for Sakura."""

import random

from .ai import generate_response
from .config import GREETINGS
from .ui import (
    display_greeting,
    display_message,
    display_status,
    display_welcome,
    get_input,
)


def run() -> None:
    """Run the main conversation loop."""
    # Track conversation history (in-memory for Phase 1)
    messages: list[dict] = []

    # Show welcome banner
    display_welcome()

    # Pick random greeting and display
    greeting, emotion = random.choice(GREETINGS)
    display_greeting(greeting, emotion)

    display_status("Type your message and press Enter. Press Ctrl+C to exit.")

    # Main conversation loop
    try:
        while True:
            # Get user input
            user_input = get_input()

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

    except KeyboardInterrupt:
        print()  # New line after ^C
        display_status("Sayonara, Goshujin-sama~ 🌸")
