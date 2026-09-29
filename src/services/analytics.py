from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from src.config import get_settings
from src.models.schemas import AnalyticsSummary, FeedbackRating, MetricBreakdown


def _now() -> datetime:
    return datetime.now(UTC)


def _session_hash(session_id: str) -> str:
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


class AnalyticsStore:
    """Privacy-minimized operational metrics; raw questions and answers are not stored."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or get_settings().sqlite_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS interaction_events (
                    request_id TEXT PRIMARY KEY,
                    session_hash TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason_code TEXT NOT NULL,
                    grounded INTEGER NOT NULL,
                    citation_count INTEGER NOT NULL,
                    cache_hit INTEGER NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    feedback TEXT,
                    feedback_reason TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_interaction_created ON interaction_events(created_at)")

    def record_interaction(
        self,
        *,
        request_id: str,
        session_id: str,
        intent: str,
        status: str,
        reason_code: str,
        grounded: bool,
        citation_count: int,
        cache_hit: bool,
        latency_ms: int,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO interaction_events (
                    request_id, session_hash, intent, status, reason_code, grounded,
                    citation_count, cache_hit, latency_ms, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    _session_hash(session_id),
                    intent,
                    status,
                    reason_code,
                    int(grounded),
                    citation_count,
                    int(cache_hit),
                    max(0, latency_ms),
                    _now().isoformat(),
                ),
            )

    def record_feedback(
        self,
        *,
        request_id: str,
        session_id: str,
        rating: FeedbackRating,
        reason: str | None,
    ) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE interaction_events
                SET feedback = ?, feedback_reason = ?
                WHERE request_id = ? AND session_hash = ?
                """,
                (rating.value, reason, request_id, _session_hash(session_id)),
            )
            if cursor.rowcount != 1:
                raise KeyError(request_id)

    def summary(self, *, days: int = 30) -> AnalyticsSummary:
        since = (_now() - timedelta(days=days)).isoformat()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM interaction_events WHERE created_at >= ?",
                (since,),
            ).fetchall()

        total = len(rows)
        answered = sum(row["status"] == "answered" for row in rows)
        grounded_answers = sum(row["status"] == "answered" and bool(row["grounded"]) for row in rows)
        handovers = sum(row["status"] == "handover_suggested" for row in rows)
        feedback_rows = [row for row in rows if row["feedback"]]
        helpful = sum(row["feedback"] == FeedbackRating.HELPFUL.value for row in feedback_rows)
        cache_hits = sum(bool(row["cache_hit"]) for row in rows)

        def breakdown(column: str, limit: int | None = None) -> list[MetricBreakdown]:
            counts: dict[str, int] = {}
            for row in rows:
                key = str(row[column])
                counts[key] = counts.get(key, 0) + 1
            values = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
            if limit is not None:
                values = values[:limit]
            return [MetricBreakdown(key=key, count=count) for key, count in values]

        return AnalyticsSummary(
            window_days=days,
            generated_at=_now(),
            total_interactions=total,
            unique_sessions=len({row["session_hash"] for row in rows}),
            answered=answered,
            answer_rate=round(answered / total, 4) if total else 0.0,
            grounded_answer_compliance=round(grounded_answers / answered, 4) if answered else 0.0,
            handover_count=handovers,
            handover_rate=round(handovers / total, 4) if total else 0.0,
            feedback_count=len(feedback_rows),
            helpful_rate=round(helpful / len(feedback_rows), 4) if feedback_rows else None,
            cache_hits=cache_hits,
            cache_hit_rate=round(cache_hits / total, 4) if total else 0.0,
            average_latency_ms=round(sum(row["latency_ms"] for row in rows) / total, 1) if total else 0.0,
            status_breakdown=breakdown("status"),
            top_reason_codes=breakdown("reason_code", limit=8),
        )


_analytics_store: AnalyticsStore | None = None


def get_analytics_store() -> AnalyticsStore:
    global _analytics_store
    if _analytics_store is None:
        _analytics_store = AnalyticsStore()
    return _analytics_store
