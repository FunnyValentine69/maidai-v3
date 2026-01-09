"""Memory persistence for Sakura - session saving and summarization."""

import json
import logging
from datetime import datetime

import ollama

from .config import (
    HISTORY_DIR,
    SESSIONS_DIR,
    OLLAMA_MODEL,
    MAX_RECENT_MESSAGES,
    MAX_SESSIONS_TO_LOAD,
    MAX_SUMMARY_WORDS,
    SUMMARIZATION_PROMPT,
)

logger = logging.getLogger(__name__)

SUMMARY_FILE = HISTORY_DIR / "summary.json"


def generate_session_id() -> str:
    """Generate a session ID from current timestamp."""
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def save_session(session_id: str, messages: list[dict]) -> None:
    """Save current session to disk."""
    try:
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

        # Parse session_id to get correct started_at timestamp
        dt = datetime.strptime(session_id, "%Y-%m-%d_%H-%M-%S")

        session_data = {
            "session_id": session_id,
            "started_at": dt.isoformat(),
            "messages": messages,
        }

        file_path = SESSIONS_DIR / f"session_{session_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)

        logger.debug(f"Session saved: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to save session: {e}")


def load_memory() -> tuple[dict | None, list[dict]]:
    """Load summary and recent messages from disk.

    Returns:
        (summary_data, recent_messages)
        - summary_data: {"summary": str, "key_facts": list} or None
        - recent_messages: Messages from recent sessions
    """
    summary_data = _load_summary()
    recent_messages = []

    try:
        if not SESSIONS_DIR.exists():
            return summary_data, recent_messages

        # Get session files sorted by mtime (newest first)
        session_files = sorted(
            SESSIONS_DIR.glob("session_*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )

        # Load sessions until we have ~50 messages or hit limit
        sessions_loaded = 0
        for session_file in session_files:
            if sessions_loaded >= MAX_SESSIONS_TO_LOAD:
                break
            if len(recent_messages) >= MAX_RECENT_MESSAGES:
                break

            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    session_data = json.load(f)

                messages = session_data.get("messages", [])
                # Prepend older messages (so newest are at end)
                recent_messages = messages + recent_messages
                sessions_loaded += 1
                logger.debug(f"Loaded session: {session_file.name}")
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Skipping corrupted session file {session_file}: {e}")
                continue

        # Trim to max if we loaded too many
        if len(recent_messages) > MAX_RECENT_MESSAGES:
            recent_messages = recent_messages[-MAX_RECENT_MESSAGES:]

    except Exception as e:
        logger.warning(f"Failed to load memory: {e}")

    return summary_data, recent_messages


def summarize_if_needed(
    recent_messages: list[dict],
    session_messages: list[dict],
    force: bool = False
) -> bool:
    """Summarize old messages if needed.

    Args:
        recent_messages: Messages from past sessions
        session_messages: Messages from current session
        force: If True, summarize regardless of count (for shutdown)

    Returns:
        True if summarization succeeded or wasn't needed, False on error.
    """
    # Nothing to summarize
    if not recent_messages:
        return True

    total_context = len(recent_messages) + len(session_messages)
    should_summarize = force or (total_context > MAX_RECENT_MESSAGES)

    if not should_summarize:
        return True

    try:
        logger.info("Starting summarization...")

        # Load existing summary
        existing_summary = _load_summary()

        # Summarize messages
        new_summary = _summarize_messages(recent_messages, existing_summary)

        # Save summary
        _save_summary(new_summary)

        # Delete old session files (keep only 1 most recent)
        _delete_old_sessions(keep_recent=1)

        logger.info("Summarization complete")
        return True

    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        return False


def load_summary() -> dict | None:
    """Load summary.json if it exists."""
    try:
        if SUMMARY_FILE.exists():
            with open(SUMMARY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load summary: {e}")
    return None


# Alias for internal use
_load_summary = load_summary


def _save_summary(summary_data: dict) -> None:
    """Save summary.json."""
    try:
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, ensure_ascii=False, indent=2)
        logger.debug("Summary saved")
    except Exception as e:
        logger.error(f"Failed to save summary: {e}")
        raise


def _delete_old_sessions(keep_recent: int = 1) -> None:
    """Delete old session files, keeping only the N most recent."""
    try:
        if not SESSIONS_DIR.exists():
            return

        # Get files sorted by mtime (newest first)
        session_files = sorted(
            SESSIONS_DIR.glob("session_*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )

        # Delete all but the most recent N
        for session_file in session_files[keep_recent:]:
            session_file.unlink()
            logger.debug(f"Deleted old session: {session_file.name}")

    except Exception as e:
        logger.warning(f"Failed to delete old sessions: {e}")


def _summarize_messages(messages: list[dict], existing_summary: dict | None) -> dict:
    """Call Ollama to summarize messages."""
    # Build existing summary context
    existing_context = ""
    if existing_summary:
        existing_context = f"\n\nExisting summary to update:\n{existing_summary.get('summary', '')}"
        if existing_summary.get('key_facts'):
            existing_context += f"\n\nExisting key facts:\n"
            existing_context += "\n".join(f"- {fact}" for fact in existing_summary['key_facts'])

        # Check if compression needed
        word_count = len(existing_summary.get('summary', '').split())
        if word_count > MAX_SUMMARY_WORDS:
            existing_context += (
                f"\n\nIMPORTANT: The existing summary is {word_count} words, which exceeds the limit. "
                f"Please compress the combined summary to under {MAX_SUMMARY_WORDS} words "
                "while preserving the most important information and key facts."
            )

    # Format messages for the prompt
    messages_text = ""
    for msg in messages:
        role = "Goshujin-sama" if msg["role"] == "user" else "Sakura"
        messages_text += f"{role}: {msg['content']}\n"

    # Build full prompt
    prompt = SUMMARIZATION_PROMPT.format(
        existing_summary_section=existing_context,
        messages_text=messages_text
    )

    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        raw_response = response['message']['content']

        # Try to parse JSON
        try:
            start = raw_response.find('{')
            end = raw_response.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = raw_response[start:end]
                result = json.loads(json_str)
                return {
                    "summary": result.get("summary", raw_response),
                    "key_facts": result.get("key_facts", []),
                    "last_summarized": datetime.now().isoformat(),
                }
        except json.JSONDecodeError:
            pass

        # Fallback: use raw response as summary
        logger.warning("Failed to parse summary JSON, using raw text")
        return {
            "summary": raw_response,
            "key_facts": [],
            "last_summarized": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Ollama summarization failed: {e}")
        raise
