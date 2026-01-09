"""Ollama integration for Sakura."""

import logging
import re

import ollama

from .config import OLLAMA_MODEL, SYSTEM_PROMPT, EMOTIONS

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


def generate_response(messages: list[dict]) -> tuple[str, str]:
    """Generate a response from Sakura.

    Args:
        messages: List of message dicts with 'role' and 'content' keys.
                  Roles are 'user' or 'assistant'.

    Returns:
        Tuple of (response_text, emotion).
    """
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

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
