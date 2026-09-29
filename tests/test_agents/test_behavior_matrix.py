import json
from pathlib import Path

import pytest

from scripts.evaluate import evaluate_result
from src.agents.graph import agent

CASES = json.loads((Path(__file__).resolve().parents[2] / "eval/adversarial_questions.json").read_text(encoding="utf-8"))


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
async def test_behavior_matrix(case):
    result = await agent.ainvoke({"query": case["query"], "session_context": ""})
    assert evaluate_result(case, result) == []


@pytest.mark.asyncio
async def test_greeting_does_not_resolve_a_program_reference(client):
    initial = (await client.post("/api/v1/chat", json={"message": "Xin chào"})).json()
    result = (await client.post("/api/v1/chat", json={
        "message": "Ngành đó học phí bao nhiêu?", "session_id": initial["session_id"],
    })).json()
    assert result["status"] == "needs_clarification"
    assert not result["grounded"]


@pytest.mark.asyncio
async def test_three_turns_keep_correct_program_and_explicit_switch(client):
    session = None
    for question, expected, forbidden in (
        ("Học phí Y khoa bao nhiêu?", "815.850.000", "Điều dưỡng"),
        ("Còn theo học kỳ thì sao?", "407.925.000", "Điều dưỡng"),
        ("Mức đó đã bao gồm hỗ trợ 35% chưa?", "265.151.250", "Điều dưỡng"),
        ("Còn Điều dưỡng thì sao?", "349.650.000", "Bác sĩ Y khoa"),
    ):
        result = (await client.post("/api/v1/chat", json={"message": question, "session_id": session})).json()
        session = result["session_id"]
        assert result["status"] == "answered", result
        assert expected in result["response"]
        assert forbidden not in result["response"]


@pytest.mark.asyncio
async def test_sensitive_content_is_not_in_followup_context(client):
    from src.services.session import session_store
    result = (await client.post("/api/v1/chat", json={"message": "Email learner@example.com"})).json()
    assert session_store.context(result["session_id"]) == ""


@pytest.mark.asyncio
async def test_overdue_knowledge_is_blocked(monkeypatch):
    from src.services.knowledge_base import get_knowledge_base
    monkeypatch.setattr(get_knowledge_base(), "verified_as_of", "2025-01-01")
    result = await agent.ainvoke({"query": "Học phí Điều dưỡng bao nhiêu?"})
    assert result["reason_code"] == "knowledge_review_overdue"
    assert result["status"] == "handover_suggested"
