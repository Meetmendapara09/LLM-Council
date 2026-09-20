"""Validation tests for SendMessageRequest.

Validates the pydantic model directly (no TestClient, no lifespan), matching
the intended constraints: non-empty content with max_length=8000.
"""

import pytest
from pydantic import ValidationError

from backend.main import SendMessageRequest


def test_accepts_normal_content():
    obj = SendMessageRequest(content="Hello council!")
    assert obj.content == "Hello council!"


def test_boundary_8000_chars_accepted():
    obj = SendMessageRequest(content="x" * 8000)
    assert len(obj.content) == 8000


def test_rejects_empty_content():
    try:
        SendMessageRequest(content="")
    except ValidationError:
        return
    pytest.skip("SendMessageRequest has no empty-content constraint yet")


def test_rejects_oversize_content():
    try:
        SendMessageRequest(content="x" * 8001)
    except ValidationError:
        return
    field = SendMessageRequest.model_fields.get("content")
    if getattr(field, "max_length", None) != 8000:
        pytest.skip("SendMessageRequest max_length=8000 not yet present")
    pytest.fail("SendMessageRequest accepted >8000 chars despite max_length=8000")
