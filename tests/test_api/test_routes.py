import pytest


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_readiness_requires_valid_fresh_knowledge(client, monkeypatch):
    from src.services.knowledge_base import get_knowledge_base

    ready = await client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["dataset_fingerprint"]

    monkeypatch.setattr(get_knowledge_base(), "verified_as_of", "2025-01-01")
    stale = await client.get("/ready")
    assert stale.status_code == 503


@pytest.mark.asyncio
async def test_chat_empty_message(client):
    response = await client.post("/api/v1/chat", json={"message": ""})
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_agent_status(client):
    response = await client.get("/api/v1/status")
    assert response.status_code == 200
    assert response.json()["official_sources"] >= 1


@pytest.mark.asyncio
async def test_knowledge_status_reports_verified_dataset(client):
    response = await client.get("/api/v1/knowledge/status")

    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    assert data["academic_year"] == "2026-2027"
    assert data["sources"] == 62
    assert data["load_errors"] == []


@pytest.mark.asyncio
async def test_chat_returns_session_grounding_and_sources(client):
    response = await client.post(
        "/api/v1/chat",
        json={"message": "VinUni co nhung nganh dai hoc nao?"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["session_id"]) >= 16
    assert data["status"] == "answered"
    assert data["grounded"] is True
    assert data["citations"]
    assert data["latency_ms"] >= 0
    assert data["cache_hit"] is False or data["cache_hit"] is True


@pytest.mark.asyncio
async def test_grounded_first_turn_answer_is_safely_cached(client):
    from src.services.response_cache import response_cache

    response_cache.clear()
    first = await client.post("/api/v1/chat", json={"message": "VinUni co nhung nganh dai hoc nao?"})
    second = await client.post("/api/v1/chat", json={"message": "VinUni co nhung nganh dai hoc nao?"})

    assert first.status_code == 200
    assert first.json()["cache_hit"] is False
    assert second.status_code == 200
    assert second.json()["cache_hit"] is True
    assert second.json()["response"] == first.json()["response"]


@pytest.mark.asyncio
async def test_feedback_is_bound_to_the_anonymous_session(client):
    chat = await client.post("/api/v1/chat", json={"message": "VinUni co nhung nganh dai hoc nao?"})
    result = chat.json()
    accepted = await client.post(
        "/api/v1/feedback",
        json={
            "request_id": result["request_id"],
            "session_id": result["session_id"],
            "rating": "helpful",
        },
    )
    rejected = await client.post(
        "/api/v1/feedback",
        json={
            "request_id": result["request_id"],
            "session_id": "different-session-123456789",
            "rating": "unhelpful",
            "reason": "incorrect",
        },
    )

    assert accepted.status_code == 200
    assert accepted.json() == {"recorded": True}
    assert rejected.status_code == 404


@pytest.mark.asyncio
async def test_chat_resolves_referential_follow_up_from_session(client):
    first = await client.post(
        "/api/v1/chat",
        json={"message": "Hoc phi Bac si Y khoa nam 2026-2027 bao nhieu?"},
    )
    session_id = first.json()["session_id"]

    follow_up = await client.post(
        "/api/v1/chat",
        json={"message": "Con theo hoc ky thi sao?", "session_id": session_id},
    )

    assert follow_up.status_code == 200
    data = follow_up.json()
    assert data["status"] == "answered"
    assert "Bác sĩ Y khoa" in data["response"]
    assert "407.925.000" in data["response"]
    assert "Cử nhân Điều dưỡng" not in data["response"]


@pytest.mark.asyncio
async def test_clear_session_removes_conversation_context(client):
    first = await client.post(
        "/api/v1/chat",
        json={"message": "Hoc phi Bac si Y khoa nam 2026-2027 bao nhieu?"},
    )
    session_id = first.json()["session_id"]

    cleared = await client.delete(f"/api/v1/session/{session_id}")
    assert cleared.status_code == 204

    follow_up = await client.post(
        "/api/v1/chat",
        json={"message": "Con theo hoc ky thi sao?", "session_id": session_id},
    )
    assert follow_up.json()["status"] == "needs_clarification"


@pytest.mark.asyncio
async def test_handover_requires_explicit_consent(client):
    response = await client.post(
        "/api/v1/handover",
        json={
            "session_id": "session-1234567890",
            "question": "Can bo vui long kiem tra ho so",
            "reason": "personal_case",
            "consent": False,
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_staff_queue_is_closed_when_token_not_configured(client):
    response = await client.get("/api/v1/staff/tickets")

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_rate_limit_returns_retry_after_header(client, monkeypatch):
    from src.config import get_settings

    monkeypatch.setattr(get_settings(), "rate_limit_per_minute", 1)
    first = await client.post("/api/v1/chat", json={"message": "Xin chào"})
    second = await client.post("/api/v1/chat", json={"message": "Xin chào lần nữa"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert int(second.headers["retry-after"]) >= 1


@pytest.mark.asyncio
async def test_changed_source_blocks_cached_and_new_answer(client):
    import json

    from src.config import get_settings

    question = "Học phí Bác sĩ Y khoa năm 2026-2027 bao nhiêu?"
    first = await client.post("/api/v1/chat", json={"message": question})
    assert first.status_code == 200
    source_id = first.json()["citations"][0]["source_id"]

    monitor_file = get_settings().sqlite_path.parent / "source_monitor.json"
    monitor_file.write_text(
        json.dumps({"sources": {source_id: {"review_required": True}}}), encoding="utf-8"
    )
    blocked = await client.post("/api/v1/chat", json={"message": question})

    assert blocked.status_code == 200
    assert blocked.json()["status"] == "handover_suggested"
    assert blocked.json()["reason_code"] == "source_change_pending_review"


@pytest.mark.asyncio
async def test_staff_token_cannot_claim_ticket_as_another_staff_member(client, monkeypatch):
    from src.config import get_settings

    monkeypatch.setattr(get_settings(), "staff_tokens", {"admissions-a": "token-for-a"})
    ticket = await client.post(
        "/api/v1/handover",
        json={
            "session_id": "session-1234567890",
            "question": "Cần cán bộ kiểm tra",
            "reason": "personal_case",
            "consent": True,
        },
    )
    response = await client.post(
        f"/api/v1/staff/tickets/{ticket.json()['ticket_id']}/claim",
        headers={"Authorization": "Bearer token-for-a"},
        json={"staff_id": "admissions-b"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_configure_specialist_and_auto_route_ticket(client, monkeypatch):
    from src.config import get_settings

    monkeypatch.setattr(get_settings(), "admin_tokens", {"admin-01": "admin-token"})
    headers = {"Authorization": "Bearer admin-token"}
    created = await client.post(
        "/api/v1/admin/staff",
        headers=headers,
        json={
            "staff_id": "tuition-01",
            "display_name": "Tuition specialist",
            "department": "Tài chính & Học phí",
            "specialties": ["tuition"],
            "availability": "available",
            "active": True,
        },
    )
    assert created.status_code == 200

    ticket = await client.post(
        "/api/v1/handover",
        json={
            "session_id": "session-1234567890",
            "question": "Học phí năm nay là bao nhiêu?",
            "reason": "insufficient_retrieval_evidence",
            "consent": True,
        },
    )
    assert ticket.status_code == 201
    queue = await client.get("/api/v1/admin/tickets", headers=headers)
    routed = next(item for item in queue.json() if item["ticket_id"] == ticket.json()["ticket_id"])
    assert routed["assigned_to"] == "tuition-01"
    assert routed["assigned_department"] == "Tài chính & Học phí"


@pytest.mark.asyncio
async def test_staff_human_in_the_loop_flow_keeps_internal_data_private(client, monkeypatch):
    from src.api import routes
    from src.config import get_settings

    monkeypatch.setattr(get_settings(), "staff_tokens", {"admissions-a": "token-for-a"})
    sent_emails = []
    monkeypatch.setattr(
        routes,
        "send_transactional_email",
        lambda email, subject, text: sent_emails.append((email, subject, text)),
    )
    ticket = await client.post(
        "/api/v1/handover",
        json={
            "session_id": "session-1234567890",
            "question": "Hoc phi nam 2026 la bao nhieu?",
            "reason": "insufficient_retrieval_evidence",
            "contact": "student@example.com",
            "consent": True,
            "ai_confidence": 0.2,
            "conversation": [
                {"role": "user", "content": "Hoc phi nam 2026 la bao nhieu?"},
                {
                    "role": "assistant",
                    "content": "Chua du can cu.",
                    "confidence": 0.2,
                    "grounded": False,
                },
            ],
            "evidence": [
                {
                    "source_id": "tuition-2026",
                    "title": "Bieu phi 2026",
                    "url": "https://vinuni.edu.vn/tuition",
                }
            ],
        },
    )
    ticket_id = ticket.json()["ticket_id"]
    headers = {"Authorization": "Bearer token-for-a"}

    queue = await client.get("/api/v1/staff/tickets?priority=high", headers=headers)
    assert queue.status_code == 200
    assert queue.json()[0]["messages"]
    assert queue.json()[0]["evidence"]

    claimed = await client.post(
        f"/api/v1/staff/tickets/{ticket_id}/claim",
        headers=headers,
        json={"staff_id": "admissions-a"},
    )
    assert claimed.json()["status"] == "in_progress"

    noted = await client.post(
        f"/api/v1/staff/tickets/{ticket_id}/notes",
        headers=headers,
        json={"staff_id": "admissions-a", "note": "Ghi chu noi bo"},
    )
    assert noted.json()["notes"][0]["note"] == "Ghi chu noi bo"

    public = await client.get(
        f"/api/v1/handover/{ticket_id}",
        headers={"X-Session-ID": "session-1234567890"},
    )
    assert "notes" not in public.json()
    assert "evidence" not in public.json()

    replied = await client.post(
        f"/api/v1/staff/tickets/{ticket_id}/reply",
        headers=headers,
        json={"staff_id": "admissions-a", "reply": "Cau tra loi da kiem tra"},
    )
    assert replied.json()["status"] == "waiting_for_user"
    assert replied.json()["email_delivery_status"] == "sent"
    assert sent_emails[0][0] == "student@example.com"

    resolved = await client.post(
        f"/api/v1/staff/tickets/{ticket_id}/resolve",
        headers=headers,
        json={
            "staff_id": "admissions-a",
            "resolution_summary": "Da tra loi day du",
            "resolution_type": "answered",
            "knowledge_gap": True,
            "knowledge_gap_description": "Can them du lieu hoc phi",
        },
    )
    assert resolved.json()["status"] == "resolved"

    gaps = await client.get("/api/v1/staff/knowledge-gaps", headers=headers)
    assert gaps.status_code == 200
    assert gaps.json()[0]["ticket_id"] == ticket_id

    metrics = await client.get("/api/v1/staff/tickets/metrics", headers=headers)
    assert metrics.status_code == 200
    assert metrics.json()["resolved_today"] == 1
