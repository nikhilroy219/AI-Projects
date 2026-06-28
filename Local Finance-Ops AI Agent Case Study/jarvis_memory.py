"""
Jarvis persistent memory.
Stores durable facts in jarvis_memory.json next to this file, so Jarvis
remembers things across restarts. Plain JSON - you can open and edit it by hand.
"""

import json
import os
from datetime import datetime

_MEM_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_memory.json")
_MAX_FACTS = 200  # safety cap so the file never grows unbounded


def _load_raw() -> list[dict]:
    if not os.path.exists(_MEM_PATH):
        return []
    try:
        with open(_MEM_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_raw(facts: list[dict]) -> None:
    with open(_MEM_PATH, "w", encoding="utf-8") as f:
        json.dump(facts[-_MAX_FACTS:], f, ensure_ascii=False, indent=2)


def add_memory(text: str) -> bool:
    """Add a fact. Returns False if it's an obvious duplicate."""
    text = text.strip()
    if not text:
        return False
    facts = _load_raw()
    if any(f.get("text", "").lower() == text.lower() for f in facts):
        return False
    facts.append({"text": text, "added": datetime.now().strftime("%Y-%m-%d")})
    _save_raw(facts)
    return True


def list_memories() -> list[str]:
    return [f.get("text", "") for f in _load_raw()]


def forget(index: int) -> str | None:
    """Remove the fact at 1-based index. Returns the removed text or None."""
    facts = _load_raw()
    if 1 <= index <= len(facts):
        removed = facts.pop(index - 1)
        _save_raw(facts)
        return removed.get("text", "")
    return None


def forget_all() -> int:
    n = len(_load_raw())
    _save_raw([])
    return n


def memory_block() -> str:
    """Formatted block to inject into the system prompt."""
    facts = list_memories()
    if not facts:
        return "WHAT YOU'VE LEARNED ABOUT NIKHIL SO FAR:\n(nothing saved yet)"
    lines = "\n".join(f"- {t}" for t in facts)
    return "WHAT YOU'VE LEARNED ABOUT NIKHIL SO FAR (your saved memory):\n" + lines
