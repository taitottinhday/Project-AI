from pathlib import Path

import pytest

from src.models.schemas import FeedbackRating
from src.services.analytics import AnalyticsStore


def test_analytics_summary_and_session_owned_feedback(tmp_path: Path):
    store = AnalyticsStore(tmp_path / "analytics.db")
    store.record_interaction(
        request_id="request-001",
        session_id="session-abcdefghijklmnop",
        intent="tuition",
        status="answered",
        reason_code="grounded_answer",
        grounded=True,
        citation_count=2,
        cache_hit=False,
        latency_ms=120,
    )
    store.record_interaction(
        request_id="request-002",
        session_id="session-abcdefghijklmnop",
        intent="admissions",
        status="handover_suggested",
        reason_code="personal_admission_decision",
        grounded=False,
        citation_count=0,
        cache_hit=True,
        latency_ms=20,
    )
    store.record_feedback(
        request_id="request-001",
        session_id="session-abcdefghijklmnop",
        rating=FeedbackRating.HELPFUL,
        reason=None,
    )

    summary = store.summary(days=30)
    assert summary.total_interactions == 2
    assert summary.unique_sessions == 1
    assert summary.answer_rate == 0.5
    assert summary.grounded_answer_compliance == 1.0
    assert summary.handover_rate == 0.5
    assert summary.helpful_rate == 1.0
    assert summary.cache_hit_rate == 0.5
    assert summary.average_latency_ms == 70.0

    with pytest.raises(KeyError):
        store.record_feedback(
            request_id="request-001",
            session_id="another-session-123456",
            rating=FeedbackRating.UNHELPFUL,
            reason="incorrect",
        )
