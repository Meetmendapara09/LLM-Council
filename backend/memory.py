"""Simple per-conversation memory (mem0).

This module provides lightweight short-term memory and a model-generated summary
that can be used to provide persistent context across turns.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from . import storage
from .openrouter import query_model
from .config import CHAIRMAN_MODEL, MEMORY_MODE as DEFAULT_MEMORY_MODE, MEMORY_LOCAL_MAX_SENTENCES

# Runtime memory mode can be toggled at runtime via API
RUNTIME_MEMORY_MODE = DEFAULT_MEMORY_MODE

MEMORY_SHORT_LIMIT = 20


def get_runtime_mode() -> str:
    return RUNTIME_MEMORY_MODE


def set_runtime_mode(mode: str):
    global RUNTIME_MEMORY_MODE
    if mode not in ("local", "model"):
        raise ValueError("Invalid memory mode")
    RUNTIME_MEMORY_MODE = mode


def _ensure_memory_structure(conversation: Dict[str, Any]):
    if "memory" not in conversation:
        conversation["memory"] = {"short": [], "summary": ""}


def get_memory(conversation_id: str) -> Dict[str, Any]:
    conv = storage.get_conversation(conversation_id)
    if conv is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    _ensure_memory_structure(conv)
    return conv["memory"]


def clear_memory(conversation_id: str):
    conv = storage.get_conversation(conversation_id)
    if conv is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conv["memory"] = {"short": [], "summary": ""}
    storage.save_conversation(conv)


def add_to_short_memory(conversation_id: str, role: str, content: str):
    """Append an entry to short-term memory (keeps last N entries)."""
    conv = storage.get_conversation(conversation_id)
    if conv is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    _ensure_memory_structure(conv)
    entry = {
        "role": role,
        "content": content,
        "at": datetime.utcnow().isoformat()
    }

    conv["memory"]["short"].append(entry)
    # Trim to last N entries
    conv["memory"]["short"] = conv["memory"]["short"][-MEMORY_SHORT_LIMIT:]

    storage.save_conversation(conv)


async def update_memory_summary(
    conversation_id: str,
    summarization_model: Optional[str] = None,
    timeout: float = 30.0
) -> str:
    """Regenerate the long-term memory summary.

    Modes:
    - Local mem0 summarizer (fast, runs on-device) when config.MEMORY_MODE == 'local' or summarization_model == 'local'
    - Model-based summarization when config.MEMORY_MODE == 'model' or summarization_model provided

    The summary should be concise (1-3 sentences) capturing user preferences,
    ongoing tasks, and crucial facts to remember.
    """
    from .config import MEMORY_MODE, MEMORY_LOCAL_MAX_SENTENCES

    conv = storage.get_conversation(conversation_id)
    if conv is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    _ensure_memory_structure(conv)

    short = conv["memory"]["short"]
    existing_summary = conv["memory"].get("summary", "")

    if not short:
        return existing_summary

    # If configured to use local summarizer or explicitly requested, run the local mem0 summarizer
    use_local = False
    # prefer explicit parameter, otherwise rely on runtime mode
    if summarization_model == "local" or summarization_model == "mem0":
        use_local = True
    else:
        # use runtime mode (set via API or env)
        use_local = (RUNTIME_MEMORY_MODE == "local")

    if use_local:
        # Simple extractive / heuristic summarizer suitable for on-device use
        def _split_sentences(text: str):
            import re
            parts = re.split(r"(?<=[.!?])\s+", text.strip())
            return [p.strip() for p in parts if p.strip()]

        candidates = []
        # Build candidate sentences with recency info
        for idx, item in enumerate(short):
            sentences = _split_sentences(item.get('content', ''))
            for s in sentences:
                candidates.append({
                    'sentence': s,
                    'role': item.get('role'),
                    'recency': idx  # later items have higher idx
                })

        # Scoring heuristics
        keywords = [
            'prefer', 'preference', 'favorite', 'like', 'dislike', 'my name is', 'i am', 'i have',
            'i live', 'i work', 'born', 'located', 'from', 'project', 'goal', 'task'
        ]

        def score_sentence(c):
            s = c['sentence'].lower()
            score = 0
            # personal statements more likely (contain 'i' or 'my')
            if ' i ' in f" {s} " or s.startswith('i ') or 'my ' in s:
                score += 3
            # keywords
            for kw in keywords:
                if kw in s:
                    score += 4
            # reasonable length
            if 10 < len(s) < 300:
                score += 1
            # recency boost
            score += (c['recency'] / max(1, len(short)))
            return score

        scored = [dict(c, score=score_sentence(c)) for c in candidates]
        # Sort by score desc, then by recency desc
        scored.sort(key=lambda x: (x['score'], x['recency']), reverse=True)

        # Build unique sentences up to limit
        seen = set()
        chosen = []
        for c in scored:
            s = c['sentence'].strip()
            # normalize to avoid duplicates
            key = s.lower()
            if key in seen:
                continue
            chosen.append(s if s.endswith('.') or s.endswith('!') or s.endswith('?') else s + '.')
            seen.add(key)
            if len(chosen) >= MEMORY_LOCAL_MAX_SENTENCES:
                break

        new_summary = ' '.join(chosen).strip()

        if new_summary:
            conv["memory"]["summary"] = new_summary
            storage.save_conversation(conv)
            return new_summary

        return existing_summary

    # Fallback: model-based summarization (unchanged)
    recent_text = "\n".join([
        f"{item['role'].capitalize()}: {item['content']}" for item in short
    ])

    summary_prompt = f"""You are creating a concise memory summary for a conversation.
Keep it to 1-3 short sentences. Include user preferences, ongoing tasks, or facts
that should be remembered across future turns. Do NOT include transient details
or full excerpts of messages.

Existing summary: {existing_summary}

Recent interactions:
{recent_text}

New concise summary:"""

    model = summarization_model or CHAIRMAN_MODEL
    messages = [{"role": "user", "content": summary_prompt}]

    try:
        response = await query_model(model, messages, timeout=timeout)
        if response is None:
            return existing_summary

        new_summary = response.get("content", "").strip()
        if new_summary:
            conv["memory"]["summary"] = new_summary
            storage.save_conversation(conv)
            return new_summary

    except Exception:
        # On failure, keep the old summary
        return existing_summary

    return existing_summary


async def add_exchange_and_update_summary(
    conversation_id: str,
    user_message: str,
    assistant_response: str,
    summarization_model: Optional[str] = None
) -> str:
    """Convenience method to add the latest exchange and update the summary."""
    add_to_short_memory(conversation_id, "user", user_message)
    if assistant_response:
        add_to_short_memory(conversation_id, "assistant", assistant_response)

    summary = await update_memory_summary(conversation_id, summarization_model)
    return summary
