"""Tests for backend.memory local mode (offline; storage dir monkeypatched)."""

import re

import backend.memory as memory_module
import backend.storage as storage


def _sentence_count(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return len([p for p in parts if p.strip()])


async def test_local_summary_nonempty_and_trims_short_buffer(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(memory_module, "RUNTIME_MEMORY_MODE", "local")

    storage.create_conversation("mem-1")

    summary = await memory_module.add_exchange_and_update_summary(
        "mem-1",
        "My name is Alice. I prefer the color blue.",
        "Hello Alice! Noted your preference.",
    )
    assert isinstance(summary, str)
    assert summary.strip() != ""

    # Flood the short-term buffer well past its limit.
    for i in range(30):
        await memory_module.add_exchange_and_update_summary(
            "mem-1",
            f"User message number {i} about topic {i}.",
            f"Assistant reply number {i}.",
        )

    mem = memory_module.get_memory("mem-1")
    assert len(mem["short"]) <= memory_module.MEMORY_SHORT_LIMIT
    assert mem["summary"].strip() != ""

    from backend.config import MEMORY_LOCAL_MAX_SENTENCES

    assert _sentence_count(mem["summary"]) <= MEMORY_LOCAL_MAX_SENTENCES
