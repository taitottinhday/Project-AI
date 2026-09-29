from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from src.config import get_settings
from src.models.schemas import TicketResponse, TicketStatus


def _now() -> str:
    return datetime.now(UTC).isoformat()


class TicketStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or get_settings().sqlite_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS handover_tickets (
                    ticket_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    contact TEXT,
                    status TEXT NOT NULL CHECK(status IN ('waiting', 'in_progress', 'resolved')),
                    assigned_to TEXT,
                    staff_reply TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_ticket_status_created ON handover_tickets(status, created_at)"
            )
            # Backfill tickets replied to by an earlier release, where staff
            # response and explicit closing were separate actions.
            connection.execute(
                "UPDATE handover_tickets SET status = 'resolved' "
                "WHERE status = 'in_progress' AND staff_reply IS NOT NULL"
            )

    def create(self, session_id: str, question: str, reason: str, contact: str | None) -> TicketResponse:
        ticket_id = f"VU-{uuid.uuid4().hex[:12].upper()}"
        timestamp = _now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO handover_tickets
                    (ticket_id, session_id, question, reason, contact, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'waiting', ?, ?)
                """,
                (ticket_id, session_id, question, reason, contact, timestamp, timestamp),
            )
        return self.get_for_session(ticket_id, session_id)

    def get_for_session(self, ticket_id: str, session_id: str) -> TicketResponse:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM handover_tickets WHERE ticket_id = ? AND session_id = ?",
                (ticket_id, session_id),
            ).fetchone()
        if row is None:
            raise KeyError(ticket_id)
        return self._to_response(row)

    def list_for_staff(self, status: TicketStatus | None = None) -> list[TicketResponse]:
        query = "SELECT * FROM handover_tickets"
        parameters: tuple[str, ...] = ()
        if status:
            query += " WHERE status = ?"
            parameters = (status.value,)
        query += " ORDER BY created_at ASC"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._to_response(row) for row in rows]

    def claim(self, ticket_id: str, staff_id: str) -> TicketResponse:
        timestamp = _now()
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM handover_tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
            if row is None:
                raise KeyError(ticket_id)
            if row["status"] == TicketStatus.RESOLVED.value:
                raise ValueError("Ticket đã được xử lý")
            if row["assigned_to"] and row["assigned_to"] != staff_id:
                raise PermissionError("Ticket đang do cán bộ khác xử lý")
            connection.execute(
                """
                UPDATE handover_tickets
                SET status = 'in_progress', assigned_to = ?, updated_at = ?
                WHERE ticket_id = ?
                """,
                (staff_id, timestamp, ticket_id),
            )
        return self.get_for_staff(ticket_id)

    def reply(self, ticket_id: str, staff_id: str, reply: str) -> TicketResponse:
        timestamp = _now()
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM handover_tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
            if row is None:
                raise KeyError(ticket_id)
            if row["status"] == TicketStatus.RESOLVED.value:
                raise ValueError("Ticket đã được đóng")
            if row["assigned_to"] != staff_id:
                raise PermissionError("Cán bộ phải nhận ticket trước khi phản hồi")
            connection.execute(
                "UPDATE handover_tickets SET staff_reply = ?, status = 'resolved', updated_at = ? WHERE ticket_id = ?",
                (reply, timestamp, ticket_id),
            )
        return self.get_for_staff(ticket_id)

    def resolve(self, ticket_id: str, staff_id: str) -> TicketResponse:
        timestamp = _now()
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM handover_tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
            if row is None:
                raise KeyError(ticket_id)
            if row["assigned_to"] != staff_id:
                raise PermissionError("Chỉ cán bộ đang xử lý mới được đóng ticket")
            if not row["staff_reply"]:
                raise ValueError("Cần có phản hồi trước khi đóng ticket")
            connection.execute(
                "UPDATE handover_tickets SET status = 'resolved', updated_at = ? WHERE ticket_id = ?",
                (timestamp, ticket_id),
            )
        return self.get_for_staff(ticket_id)

    def get_for_staff(self, ticket_id: str) -> TicketResponse:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM handover_tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
        if row is None:
            raise KeyError(ticket_id)
        return self._to_response(row)

    @staticmethod
    def _to_response(row: sqlite3.Row) -> TicketResponse:
        return TicketResponse(
            ticket_id=row["ticket_id"],
            status=TicketStatus(row["status"]),
            question=row["question"],
            reason=row["reason"],
            staff_reply=row["staff_reply"],
            assigned_to=row["assigned_to"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


_ticket_store: TicketStore | None = None


def get_ticket_store() -> TicketStore:
    global _ticket_store
    if _ticket_store is None:
        _ticket_store = TicketStore()
    return _ticket_store
