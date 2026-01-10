"""Ollama integration for Sakura."""

import logging
import random
import re

import ollama

from .config import OLLAMA_MODEL, SYSTEM_PROMPT, EMOTIONS, EMOTION_ALIASES, GREETING_PROMPT, GREETINGS

logger = logging.getLogger(__name__)


def _normalize_emotion(emotion: str) -> str:
    """Map emotion aliases to valid emotions."""
    emotion = emotion.lower()
    return EMOTION_ALIASES.get(emotion, emotion)


def parse_bilingual_response(response: str) -> tuple[str, str, str]:
    """Parse bilingual response with emotion tag.

    Expected format:
    [EMOTION:name]
    Japanese text
    ---
    English text

    Also handles alternate formats: [WORD:name], [name]

    Returns (japanese_text, english_text, emotion).

    Edge cases:
    - Multiple --- → use first separator only
    - Em-dash — → normalize to ---
    - Empty JP section → return empty string
    - No separator → treat entire text as English, JP empty
    """
    emotion = "neutral"

    # Normalize em-dash to triple hyphen
    response = response.replace("—", "---")

    # Extract emotion tag - try [EMOTION:name] first
    pattern = r'^\[EMOTION:(\w+)\]\s*'
    match = re.match(pattern, response, re.IGNORECASE)
    if match:
        emotion = _normalize_emotion(match.group(1))
        if emotion not in EMOTIONS:
            logger.warning(f"Invalid emotion '{emotion}', defaulting to neutral")
            emotion = "neutral"
        response = re.sub(pattern, '', response, flags=re.IGNORECASE)
    else:
        # Try alternate formats: [WORD:name] or [name]
        # Uses (?:\w+:)? to optionally match prefix like "HAPPY:"
        alt_pattern = r'^\[(?:\w+:)?(\w+)\]\s*'
        alt_match = re.match(alt_pattern, response)
        if alt_match:
            potential_emotion = _normalize_emotion(alt_match.group(1))
            if potential_emotion in EMOTIONS:
                emotion = potential_emotion
                response = re.sub(alt_pattern, '', response)

    # Split on --- separator
    if "---" in response:
        parts = response.split("---", 1)  # Split on first occurrence only
        japanese = parts[0].strip()
        english = parts[1].strip() if len(parts) > 1 else ""
    else:
        # No separator found - treat entire response as English (fallback)
        logger.warning("No --- separator found in response, treating as English only")
        japanese = ""
        english = response.strip()

    return japanese, english, emotion


def generate_greeting(
    summary_data: dict | None,
    recent_messages: list[dict]
) -> tuple[str, str, str]:
    """Generate a context-aware greeting using memory.

    Args:
        summary_data: Summary dict with 'summary' and 'key_facts', or None
        recent_messages: Recent conversation messages

    Returns:
        Tuple of (japanese_text, english_text, emotion).
    """
    # If no memory exists (first run), fallback to random greeting
    if not summary_data and not recent_messages:
        return random.choice(GREETINGS)

    # Build memory context
    memory_context = ""
    if summary_data:
        memory_context += f"Memory summary:\n{summary_data.get('summary', '')}\n"
        if summary_data.get('key_facts'):
            memory_context += "\nKey facts:\n"
            memory_context += "\n".join(f"- {fact}" for fact in summary_data['key_facts'])

    if recent_messages:
        # Add last few messages for immediate context
        memory_context += "\n\nRecent conversation:\n"
        for msg in recent_messages[-6:]:  # Last 3 exchanges
            role = "Goshujin-sama" if msg["role"] == "user" else "Sakura"
            memory_context += f"{role}: {msg['content']}\n"

    prompt = GREETING_PROMPT.format(memory_context=memory_context)

    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        raw_response = response['message']['content']
        return parse_bilingual_response(raw_response)
    except Exception as e:
        logger.warning(f"Failed to generate greeting: {e}")
        return random.choice(GREETINGS)


def generate_response(messages: list[dict], summary_data: dict | None = None) -> tuple[str, str, str]:
    """Generate a response from Sakura.

    Args:
        messages: List of message dicts with 'role' and 'content' keys.
                  Roles are 'user' or 'assistant'.
        summary_data: Optional summary dict with memory context.

    Returns:
        Tuple of (japanese_text, english_text, emotion).
    """
    # Build context prompt with memory if available
    context_prompt = SYSTEM_PROMPT
    if summary_data:
        memory_context = f"\n\nMemory of past conversations:\n{summary_data.get('summary', '')}"
        if summary_data.get('key_facts'):
            memory_context += f"\n\nKey facts about Goshujin-sama:\n"
            memory_context += "\n".join(f"- {fact}" for fact in summary_data['key_facts'])
        context_prompt += memory_context

    full_messages = [{"role": "system", "content": context_prompt}] + messages

    for attempt in range(2):
        try:
            response = ollama.chat(model=OLLAMA_MODEL, messages=full_messages)
            raw_response = response['message']['content']
            return parse_bilingual_response(raw_response)
        except Exception as e:
            if attempt == 0:
                logger.warning(f"Ollama request failed, retrying: {e}")
                continue
            logger.error(f"Ollama request failed after retry: {e}")
            return (
                "ちょっと今、考えがまとまらないの…べ、別に気にしてるわけじゃないんだから！",
                "Hmph, I'm having trouble thinking right now... N-not that I care or anything!",
                "confused",
            )
