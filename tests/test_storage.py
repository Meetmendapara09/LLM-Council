"""Tests for backend.storage (offline; DATA_DIR monkeypatched to tmp_path)."""

import pytest

import backend.storage as storage


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", str(tmp_path))
    return tmp_path


def test_create_and_get(data_dir):
    conv = storage.create_conversation("conv-1")
    assert conv["id"] == "conv-1"

    loaded = storage.get_conversation("conv-1")
    assert loaded is not None
    assert loaded["id"] == "conv-1"
    assert loaded["messages"] == []


def test_get_missing_returns_none(data_dir):
    assert storage.get_conversation("does-not-exist") is None


def test_add_user_and_assistant_messages(data_dir):
    storage.create_conversation("conv-1")
    storage.add_user_message("conv-1", "Hello council")

    stage1 = [{"model": "model-a", "response": "Answer A"}]
    stage2 = [{"model": "model-a", "ranking": "rank", "parsed_ranking": []}]
    stage3 = {"model": "chairman", "response": "Final"}
    storage.add_assistant_message("conv-1", stage1, stage2, stage3)

    conv = storage.get_conversation("conv-1")
    assert len(conv["messages"]) == 2
    assert conv["messages"][0]["role"] == "user"
    assert conv["messages"][0]["content"] == "Hello council"
    assert conv["messages"][1]["role"] == "assistant"
    assert conv["messages"][1]["stage1"] == stage1
    assert conv["messages"][1]["stage3"] == stage3


def test_list_conversations(data_dir):
    storage.create_conversation("conv-1")
    storage.create_conversation("conv-2")
    storage.add_user_message("conv-1", "hi")

    metas = storage.list_conversations()
    by_id = {m["id"]: m for m in metas}
    assert set(by_id) == {"conv-1", "conv-2"}
    assert by_id["conv-1"]["message_count"] == 1
    assert by_id["conv-2"]["message_count"] == 0


def test_delete_round_trip(data_dir):
    storage.create_conversation("conv-1")
    storage.add_user_message("conv-1", "hi")
    assert storage.get_conversation("conv-1") is not None

    assert storage.delete_conversation("conv-1") is True

    assert storage.get_conversation("conv-1") is None
    assert all(m["id"] != "conv-1" for m in storage.list_conversations())
    assert storage.delete_conversation("conv-1") is False
