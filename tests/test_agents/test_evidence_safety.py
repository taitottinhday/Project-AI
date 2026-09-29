import pytest

from src.agents.graph import agent


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "Lịch học chính thức năm 2026-2027 là gì?",
        "Yêu cầu tiếng Anh đầu vào của VinUni là gì?",
        "Mã ngành Kỹ thuật Cơ khí là gì?",
        "Hạn quay lại sau khi nghỉ học là 1 tuần hay 1 tháng?",
        "Mã học phần của minor Psychology là gì?",
    ],
)
async def test_draft_or_conflicting_evidence_never_becomes_factual_answer(query):
    result = await agent.ainvoke({"query": query, "session_context": ""})

    assert result["status"] != "answered"
    assert result["grounded"] is False


@pytest.mark.asyncio
async def test_minor_query_prefers_minor_record_over_same_named_major():
    result = await agent.ainvoke({"query": "Minor Psychology tại VinUni là gì?", "session_context": ""})

    assert result["status"] == "answered"
    assert result["grounded"] is True
    assert any(hit.chunk.document.startswith("academics/vinuni_undergraduate_minors") for hit in result["hits"])
    assert any(
        evidence_id.startswith("vinuni_undergraduate_minors")
        for evidence_id in result["draft"].evidence_ids
    )
