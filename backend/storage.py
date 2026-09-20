"""JSON-based storage for conversations."""

import json
import os
from asyncio import Lock
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path
from .config import DATA_DIR

_locks: Dict[str, Lock] = {}


def get_lock(conversation_id: str) -> Lock:
    """Return (creating if needed) the asyncio lock for a conversation."""
    lock = _locks.get(conversation_id)
    if lock is None:
        lock = Lock()
        _locks[conversation_id] = lock
    return lock


def ensure_data_dir():
    """Ensure the data directory exists."""
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def get_conversation_path(conversation_id: str) -> str:
    """Get the file path for a conversation."""
    return os.path.join(DATA_DIR, f"{conversation_id}.json")


def create_conversation(conversation_id: str) -> Dict[str, Any]:
    """
    Create a new conversation.

    Args:
        conversation_id: Unique identifier for the conversation

    Returns:
        New conversation dict
    """
    ensure_data_dir()

    conversation = {
        "id": conversation_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": "New Conversation",
        "messages": [],
        # Lightweight per-conversation memory
        "memory": {
            "short": [],  # recent short entries
            "summary": "",  # concise long-term summary
        },
    }

    # Save to file
    path = get_conversation_path(conversation_id)
    with open(path, "w") as f:
        json.dump(conversation, f, indent=2)

    return conversation


def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    Load a conversation from storage.

    Args:
        conversation_id: Unique identifier for the conversation

    Returns:
        Conversation dict or None if not found
    """
    path = get_conversation_path(conversation_id)

    if not os.path.exists(path):
        return None

    with open(path, "r") as f:
        return json.load(f)


def save_conversation(conversation: Dict[str, Any]):
    """
    Save a conversation to storage.

    Args:
        conversation: Conversation dict to save
    """
    ensure_data_dir()

    path = get_conversation_path(conversation["id"])
    with open(path, "w") as f:
        json.dump(conversation, f, indent=2)


def list_conversations() -> List[Dict[str, Any]]:
    """
    List all conversations (metadata only).

    Returns:
        List of conversation metadata dicts
    """
    ensure_data_dir()

    conversations = []
    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".json"):
            path = os.path.join(DATA_DIR, filename)
            with open(path, "r") as f:
                data = json.load(f)
                # Return metadata only
                conversations.append(
                    {
                        "id": data["id"],
                        "created_at": data["created_at"],
                        "title": data.get("title", "New Conversation"),
                        "message_count": len(data["messages"]),
                    }
                )

    # Sort by creation time, newest first
    conversations.sort(key=lambda x: x["created_at"], reverse=True)

    return conversations


def add_user_message(conversation_id: str, content: str):
    """
    Add a user message to a conversation.

    Args:
        conversation_id: Conversation identifier
        content: User message content
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["messages"].append(
        {
            "role": "user",
            "content": content,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    save_conversation(conversation)


def add_assistant_message(
    conversation_id: str,
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any],
):
    """
    Add an assistant message with all 3 stages to a conversation.

    Args:
        conversation_id: Conversation identifier
        stage1: List of individual model responses
        stage2: List of model rankings
        stage3: Final synthesized response
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["messages"].append(
        {
            "role": "assistant",
            "stage1": stage1,
            "stage2": stage2,
            "stage3": stage3,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    save_conversation(conversation)


def update_conversation_title(conversation_id: str, title: str):
    """
    Update the title of a conversation.

    Args:
        conversation_id: Conversation identifier
        title: New title for the conversation
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["title"] = title
    save_conversation(conversation)


def delete_conversation(conversation_id: str) -> bool:
    """
    Delete a conversation's JSON file.

    Args:
        conversation_id: Conversation identifier

    Returns:
        True if deleted, False if the file did not exist
    """
    path = get_conversation_path(conversation_id)
    if not os.path.exists(path):
        return False
    os.remove(path)
    _locks.pop(conversation_id, None)
    return True
