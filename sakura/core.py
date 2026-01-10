"""Main conversation loop for Sakura."""

from datetime import datetime

from .ai import generate_greeting, generate_response
from .config import MAX_RECENT_MESSAGES
from .memory import generate_session_id, load_memory, load_summary, save_session, summarize_if_needed
from .speech import init as init_speech
from .tts import speak_bilingual, stop_speaking
from .ui import (
    display_bilingual_message,
    display_status,
    display_welcome,
    get_input_with_voice,
)


def run() -> None:
    """Run the main conversation loop."""
    # Generate session ID and load memory
    session_id = generate_session_id()
    summary_data, recent_messages = load_memory()
    session_messages: list[dict] = []  # Current session only (this gets saved)

    # Show welcome banner
    display_welcome()

    # Initialize voice input
    display_status("Loading voice models...")
    init_speech()

    # Generate context-aware greeting (or random if no memory)
    display_status("Preparing greeting...")
    jp_greeting, en_greeting, emotion = generate_greeting(summary_data, recent_messages)
    display_bilingual_message(emotion, jp_greeting, en_greeting)
    if warning := speak_bilingual(jp_greeting, en_greeting):
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

            # Add user message to session history with timestamp
            session_messages.append({
                "role": "user",
                "content": user_input,
                "timestamp": datetime.now().isoformat(),
            })

            # Generate response (combine recent + session messages for context)
            all_messages = recent_messages + session_messages
            japanese, english, emotion = generate_response(all_messages, summary_data)

            # Add assistant message to session history (English only for AI context)
            session_messages.append({
                "role": "assistant",
                "content": english,
                "emotion": emotion,
                "timestamp": datetime.now().isoformat(),
            })

            # Display bilingual response
            display_bilingual_message(emotion, japanese, english)
            if warning := speak_bilingual(japanese, english):
                display_status(warning)

            # Auto-save every 10 messages for crash safety
            if len(session_messages) % 10 == 0:
                save_session(session_id, session_messages)

            # Check if total context exceeds limit
            total_context = len(recent_messages) + len(session_messages)
            if total_context > MAX_RECENT_MESSAGES:
                if summarize_if_needed(recent_messages, session_messages, force=False):
                    recent_messages = []  # Clear old messages
                    summary_data = load_summary()  # Reload fresh summary

    except KeyboardInterrupt:
        print()  # New line after ^C
        # Only save if we have messages (skip empty sessions)
        if session_messages:
            display_status("Saving conversation...")
            save_session(session_id, session_messages)
            summarize_if_needed(recent_messages, session_messages, force=True)
        display_status("Sayonara, Goshujin-sama~ 🌸")
