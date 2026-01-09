"""Ollama integration for Sakura."""

import logging
import random
import re

import ollama

from .config import OLLAMA_MODEL, SYSTEM_PROMPT, EMOTIONS, GREETING_PROMPT, GREETINGS

logger = logging.getLogger(__name__)


def parse_emotion(response: str) -> tuple[str, str]:
    """Parse emotion tag from response.

    Handles multiple formats:
    - [EMOTION:name] (intended format)
    - [WORD:name] (fallback, uses second word)
    - [name] (simple bracket format)

    Returns (clean_text, emotion).
    """
    # Try [EMOTION:name] format first
    pattern1 = r'^\[EMOTION:(\w+)\]\s*'
    match = re.match(pattern1, response, re.IGNORECASE)
    if match:
        emotion = match.group(1).lower()
        clean_text = re.sub(pattern1, '', response, flags=re.IGNORECASE).strip()
        if emotion in EMOTIONS:
            return clean_text, emotion
        logger.warning(f"Invalid emotion '{emotion}', defaulting to neutral")
        return clean_text, "neutral"

    # Try [WORD:name] format (e.g., [HAPPY:excited])
    pattern2 = r'^\[\w+:(\w+)\]\s*'
    match = re.match(pattern2, response)
    if match:
        emotion = match.group(1).lower()
        clean_text = re.sub(pattern2, '', response).strip()
        if emotion in EMOTIONS:
            return clean_text, emotion
        logger.warning(f"Invalid emotion '{emotion}' from alternate format, defaulting to neutral")
        return clean_text, "neutral"

    # Try [name] format
    pattern3 = r'^\[(\w+)\]\s*'
    match = re.match(pattern3, response)
    if match:
        emotion = match.group(1).lower()
        clean_text = re.sub(pattern3, '', response).strip()
        if emotion in EMOTIONS:
            return clean_text, emotion
        logger.debug(f"Found [{match.group(1)}] but not a valid emotion, ignoring")

    # No emotion tag found, default to neutral
    logger.debug("No emotion tag found in response, defaulting to neutral")
    return response.strip(), "neutral"


def generate_greeting(
    summary_data: dict | None,
    recent_messages: list[dict]
) -> tuple[str, str]:
    """Generate a context-aware greeting using memory.

    Args:
        summary_data: Summary dict with 'summary' and 'key_facts', or None
        recent_messages: Recent conversation messages

    Returns:
        Tuple of (greeting_text, emotion).
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
        return parse_emotion(raw_response)
    except Exception as e:
        logger.warning(f"Failed to generate greeting: {e}")
        return random.choice(GREETINGS)


def generate_response(messages: list[dict], summary_data: dict | None = None) -> tuple[str, str]:
    """Generate a response from Sakura.

    Args:
        messages: List of message dicts with 'role' and 'content' keys.
                  Roles are 'user' or 'assistant'.
        summary_data: Optional summary dict with memory context.

    Returns:
        Tuple of (response_text, emotion).
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
            return parse_emotion(raw_response)
        except Exception as e:
            if attempt == 0:
                logger.warning(f"Ollama request failed, retrying: {e}")
                continue
            logger.error(f"Ollama request failed after retry: {e}")
            return (
                "Hmph, I'm having trouble thinking right now... "
                "N-not that I care or anything!",
                "confused"
            )
