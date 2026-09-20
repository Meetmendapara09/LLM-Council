"""Tests for backend.council (offline; query layer is mocked, no network)."""

import backend.council as council_mod
from backend.council import (
    calculate_aggregate_rankings,
    parse_ranking_from_text,
    run_full_council,
)


def test_parse_ranking_numbered_final_ranking():
    text = (
        "Response A is thorough but verbose. Response B is concise and accurate.\n\n"
        "FINAL RANKING:\n"
        "1. Response B\n"
        "2. Response C\n"
        "3. Response A\n"
    )
    assert parse_ranking_from_text(text) == ["Response B", "Response C", "Response A"]


def test_parse_ranking_fallback_extraction():
    # No FINAL RANKING header: labels are extracted in order of appearance.
    text = "I think Response C is best, followed by Response A."
    assert parse_ranking_from_text(text) == ["Response C", "Response A"]


def test_parse_ranking_no_match_returns_empty():
    assert parse_ranking_from_text("All answers look fine to me, no labels here.") == []


def test_calculate_aggregate_rankings_ordering_and_averages():
    label_to_model = {"Response A": "model-a", "Response B": "model-b"}
    stage2_results = [
        {
            "model": "model-a",
            "ranking": "Eval text.\nFINAL RANKING:\n1. Response A\n2. Response B",
            "parsed_ranking": ["Response A", "Response B"],
        },
        {
            "model": "model-b",
            "ranking": "Eval text.\nFINAL RANKING:\n1. Response A\n2. Response B",
            "parsed_ranking": ["Response A", "Response B"],
        },
        {
            "model": "model-c",
            "ranking": "Eval text.\nFINAL RANKING:\n1. Response B\n2. Response A",
            "parsed_ranking": ["Response B", "Response A"],
        },
    ]

    aggregate = calculate_aggregate_rankings(stage2_results, label_to_model)

    # model-a ranked 1,1,2 -> avg 1.33; model-b ranked 2,2,1 -> avg 1.67
    assert [entry["model"] for entry in aggregate] == ["model-a", "model-b"]
    assert aggregate[0]["average_rank"] == round((1 + 1 + 2) / 3, 2)
    assert aggregate[1]["average_rank"] == round((2 + 2 + 1) / 3, 2)
    assert aggregate[0]["rankings_count"] == 3
    assert aggregate[1]["rankings_count"] == 3


async def test_run_full_council_happy_path(monkeypatch):
    async def fake_parallel(models, messages):
        joined = " ".join(m.get("content", "") for m in messages)
        if "anonymized" in joined:
            # Stage 2 ranking call.
            return {
                "model-a": {
                    "content": "Eval.\nFINAL RANKING:\n1. Response B\n2. Response A"
                },
                "model-b": {
                    "content": "Eval.\nFINAL RANKING:\n1. Response A\n2. Response B"
                },
            }
        # Stage 1 answer call.
        return {
            "model-a": {"content": "Answer from A"},
            "model-b": {"content": "Answer from B"},
        }

    async def fake_chairman(model, messages, timeout=120.0):
        return {"content": "Final synthesis"}

    monkeypatch.setattr(council_mod, "query_models_parallel", fake_parallel)
    monkeypatch.setattr(council_mod, "query_model", fake_chairman)

    messages = [{"role": "user", "content": "What is 2+2?"}]
    stage1, stage2, stage3, metadata = await run_full_council(messages)

    assert len(stage1) == 2
    assert {r["model"] for r in stage1} == {"model-a", "model-b"}
    assert len(stage2) == 2
    assert all("parsed_ranking" in r for r in stage2)
    assert stage3["response"] == "Final synthesis"
    assert set(metadata["label_to_model"].values()) == {"model-a", "model-b"}
    assert len(metadata["aggregate_rankings"]) == 2


async def test_run_full_council_all_models_failed(monkeypatch):
    async def fake_parallel(models, messages):
        return {model: None for model in models}

    monkeypatch.setattr(council_mod, "query_models_parallel", fake_parallel)

    messages = [{"role": "user", "content": "What is 2+2?"}]
    stage1, stage2, stage3, metadata = await run_full_council(messages)

    assert stage1 == []
    assert stage2 == []
    assert stage3["model"] == "error"
    assert metadata == {}
