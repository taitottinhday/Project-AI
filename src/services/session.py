from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from src.config import get_settings
from src.services.query_understanding import resolve_reference

CONTEXT_REFERENCE_PHRASES = (
    "nganh nay",
    "nganh do",
    "chuong trinh nay",
    "chuong trinh do",
    "cai do",
    "con no",
    "thi sao",
    "con ve",
    "theo hoc ky",
    "theo nam",
)


@dataclass
class Turn:
    user: str
    assistant: str


@dataclass
class Session:
    session_id: str
    turns: list[Turn] = field(default_factory=list)
    unresolved_streak: int = 0
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.RLock()

    def get_or_create(self, session_id: str | None = None) -> Session:
        with self._lock:
            self._purge_expired()
            if session_id:
                session = self._sessions.get(session_id)
                if session is None:
                    # The browser owns this high-entropy anonymous identifier.
                    # Recreate its short-lived conversation state after a process
                    # restart while keeping ownership of persisted handover tickets.
                    session = Session(session_id=session_id)
                    self._sessions[session_id] = session
                session.updated_at = datetime.now(UTC)
                return session
            new_id = secrets.token_urlsafe(24)
            session = Session(session_id=new_id)
            self._sessions[new_id] = session
            return session

    def add_turn(self, session_id: str, user: str, assistant: str) -> None:
        settings = get_settings()
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = Session(session_id=session_id)
                self._sessions[session_id] = session
            session.turns.append(Turn(user=user, assistant=assistant))
            session.turns = session.turns[-settings.session_max_turns :]
            session.updated_at = datetime.now(UTC)

    def context(self, session_id: str) -> str:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return ""
            return "\n".join(f"Người dùng: {turn.user}\nTrợ lý: {turn.assistant}" for turn in session.turns[-3:])

    def get_unresolved_streak(self, session_id: str) -> int:
        with self._lock:
            session = self._sessions.get(session_id)
            return session.unresolved_streak if session else 0

    def record_outcome(self, session_id: str, *, answered: bool, unresolved: bool) -> None:
        """Track repeated unresolved turns without storing extra user content."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = Session(session_id=session_id)
                self._sessions[session_id] = session
            if answered:
                session.unresolved_streak = 0
            elif unresolved:
                session.unresolved_streak += 1
            session.updated_at = datetime.now(UTC)

    def clear(self, session_id: str) -> None:
        """Clear chat context while preserving the ID used to own tickets."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.turns.clear()
                session.unresolved_streak = 0
                session.updated_at = datetime.now(UTC)

    def _purge_expired(self) -> None:
        cutoff = datetime.now(UTC) - timedelta(minutes=get_settings().session_ttl_minutes)
        expired = [session_id for session_id, value in self._sessions.items() if value.updated_at < cutoff]
        for session_id in expired:
            del self._sessions[session_id]


def contextualize_query(query: str, session_context: str) -> str:
    return resolve_reference(query, session_context)


session_store = SessionStore()
