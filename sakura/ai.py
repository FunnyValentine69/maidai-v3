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


def _strip_duplicate_actions(text: str) -> str:
    """Remove duplicate *action* phrases, keeping first occurrence."""
    seen = set()

    def replace_duplicate(match: re.Match) -> str:
        action = match.group(1).lower()  # Case-insensitive comparison
        if action in seen:
            return ""  # Remove duplicate (and trailing space if present)
        seen.add(action)
        return match.group(0)  # Keep original with any trailing space

    # Match *action* patterns with optional trailing whitespace
    result = re.sub(r'(\*[^*]+\*)\s*', replace_duplicate, text)
    # Clean up any double spaces left behind
    result = re.sub(r'  +', ' ', result)
    return result.strip()


def _ensure_separator(text: str) -> str:
    """Insert --- separator if JP and EN are mixed without one.

    Handles case where model outputs both languages on same line:
    *にやりと笑う* 日本語テキスト *giggles* English text
    """
    if "---" in text:
        return text

    # Check for both Japanese and English content
    jp_chars = r'[\u3040-\u30ff\u4e00-\u9fff]'  # hiragana, katakana, kanji
    en_words = r'[a-zA-Z]{3,}'  # 3+ consecutive letters

    if not (re.search(jp_chars, text) and re.search(en_words, text)):
        return text

    # Find last Japanese character (including JP punctuation)
    jp_end_pattern = r'[\u3040-\u30ff\u4e00-\u9fff。、！？…]'

    last_jp_pos = -1
    for match in re.finditer(jp_end_pattern, text):
        last_jp_pos = match.end()

    if last_jp_pos > 0 and last_jp_pos < len(text) - 1:
        before = text[:last_jp_pos].strip()
        after = text[last_jp_pos:].strip()
        if before and after:
            logger.debug(f"Inserted --- separator at position {last_jp_pos}")
            return f"{before}\n---\n{after}"

    return text


# Priority-based keyword tiers for text emotion detection
_HIGH_PRIORITY_KEYWORDS = {
    "shy": ["blush", "redden", "fluster", "embarrass"],
    "sad": ["tear", "cry", "sob"],
    "angry": ["angry", "furious", "glare", "scowl"],
    "surprised": ["shock", "gasp", "stunned"],
}

_MEDIUM_PRIORITY_KEYWORDS = {
    "happy": ["giggle", "smile", "grin", "laugh", "happy"],
    "worried": ["nervous", "anxious", "worried", "uneasy"],
    "love": ["heart", "loving", "adoring"],
    "excited": ["excite", "bouncing", "sparkling"],
    "proud": ["proud", "smug", "triumphant"],
    "playful": ["wink", "tease", "mischiev"],
}

_LOW_PRIORITY_KEYWORDS = {
    "thinking": ["ponder", "hmm", "contemplate"],
    "tired": ["yawn", "sleepy", "exhaust"],
    "confused": ["puzzl", "bewilder"],
}


def detect_emotion_from_text(text: str) -> str | None:
    """Detect emotion from English text using keyword matching.

    Checks priority tiers in order: HIGH → MEDIUM → LOW.
    Returns first matched emotion or None.
    """
    text_lower = text.lower()

    for tier in (_HIGH_PRIORITY_KEYWORDS, _MEDIUM_PRIORITY_KEYWORDS, _LOW_PRIORITY_KEYWORDS):
        for emotion, keywords in tier.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return emotion

    return None


def parse_bilingual_response(response: str) -> tuple[str, str, str]:
    """Parse bilingual response with emotion tag.

    Expected format:
    [EMOTION:name]
    Japanese text
    ---
    English text

    Also handles:
    - Emotion tags appearing anywhere in text (extracts first, strips all)
    - Alternate formats: [WORD:name], [name]

    Returns (japanese_text, english_text, emotion).

    Edge cases:
    - Multiple --- → use first separator only
    - Em-dash — → normalize to ---
    - Empty JP section → return empty string
    - No separator → try to insert, else treat as English only
    - Multiple emotion tags → use first found, strip all
    """
    # Try to insert --- separator if missing but both JP/EN present
    response = _ensure_separator(response)

    emotion = "neutral"

    # Dedupe if prefix prompting caused double emotion tag
    response = re.sub(r'\[EMOTION:\[EMOTION:', '[EMOTION:', response, flags=re.IGNORECASE)

    # Normalize em-dash to triple hyphen
    response = response.replace("—", "---")

    # Find emotion tag ANYWHERE in text (not just start)
    # Capture only first word after EMOTION: (ignore commas, spaces, extra content)
    emotion_pattern = r'\[EMOTION:(\w+)[^\]]*\]'
    emotion_matches = re.findall(emotion_pattern, response, re.IGNORECASE)
    if emotion_matches:
        emotion = _normalize_emotion(emotion_matches[0])  # Use first found
        if emotion not in EMOTIONS:
            logger.warning(f"Invalid emotion '{emotion}', defaulting to neutral")
            emotion = "neutral"
    else:
        # Try alternate formats: [WORD:name] or [name] anywhere in text
        alt_pattern = r'\[(?:\w+:)?(\w+)\]'
        alt_matches = re.findall(alt_pattern, response)
        for match in alt_matches:
            potential_emotion = _normalize_emotion(match)
            if potential_emotion in EMOTIONS:
                emotion = potential_emotion
                break

    # Strip ALL emotion tags from response body (including multi-word variants)
    response = re.sub(r'\[EMOTION:\w+[^\]]*\]\s*', '', response, flags=re.IGNORECASE)

    # Strip alternate emotion formats that match valid emotions
    def strip_if_emotion(m: re.Match) -> str:
        word = m.group(1)
        if _normalize_emotion(word) in EMOTIONS:
            return ''
        return m.group(0)  # Keep non-emotion brackets

    response = re.sub(r'\[(?:\w+:)?(\w+)\]', strip_if_emotion, response)

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

    # Strip any remaining square bracket content from displayed text
    japanese = re.sub(r'\[[^\]]+\]', '', japanese).strip()
    english = re.sub(r'\[[^\]]+\]', '', english).strip()

    # Fallback: detect emotion from English text if no tag was found
    if emotion == "neutral":
        detected = detect_emotion_from_text(english)
        if detected:
            logger.debug(f"Detected emotion from text: {detected}")
            emotion = detected

    # Strip duplicate action phrases (e.g., *giggles softly* appearing multiple times)
    japanese = _strip_duplicate_actions(japanese)
    english = _strip_duplicate_actions(english)

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

    # Prefix prompting: add partial assistant message to force format start
    full_messages.append({"role": "assistant", "content": "[EMOTION:"})

    for attempt in range(2):
        try:
            response = ollama.chat(model=OLLAMA_MODEL, messages=full_messages)
            raw_response = response['message']['content']
            # Prepend the prefix we used (model continues from it)
            raw_response = "[EMOTION:" + raw_response
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
