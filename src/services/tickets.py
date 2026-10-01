from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from src.config import get_settings
from src.models.schemas import (
    EscalationReason,
    HandoverEvidenceSnapshot,
    HandoverMessageSnapshot,
    KnowledgeGapItem,
    MetricBreakdown,
    StaffTicketMetrics,
    StaffTicketResponse,
    TicketActivity,
    TicketCategory,
    TicketEvidence,
    TicketMessage,
    TicketNote,
    TicketPriority,
    TicketResponse,
    TicketStatus,
)
from src.services.staff_assistant import build_suggested_reply, build_summary, classify_ticket


def _now_dt() -> datetime:
    return datetime.now(UTC)


def _now() -> str:
    return _now_dt().isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


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

    @staticmethod
    def _create_ticket_table(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS handover_tickets (
                ticket_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                question TEXT NOT NULL,
                reason TEXT NOT NULL,
                contact TEXT,
                user_email TEXT,
                status TEXT NOT NULL,
                assigned_to TEXT,
                assigned_department TEXT,
                category TEXT NOT NULL,
                priority TEXT NOT NULL,
                escalation_reason TEXT NOT NULL,
                ai_confidence REAL,
                ai_summary TEXT,
                suggested_reply TEXT,
                staff_reply TEXT,
                resolution_summary TEXT,
                resolution_type TEXT,
                knowledge_gap INTEGER NOT NULL DEFAULT 0,
                first_response_at TEXT,
                last_response_at TEXT,
                resolved_at TEXT,
                closed_at TEXT,
                email_delivery_status TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    def _migrate_legacy_table(self, connection: sqlite3.Connection) -> None:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='handover_tickets'"
        ).fetchone()
        if not exists:
            self._create_ticket_table(connection)
            return
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(handover_tickets)").fetchall()
        }
        if {"category", "priority", "escalation_reason", "user_email"}.issubset(columns):
            return

        connection.execute("ALTER TABLE handover_tickets RENAME TO handover_tickets_legacy")
        self._create_ticket_table(connection)
        rows = connection.execute("SELECT * FROM handover_tickets_legacy").fetchall()
        for row in rows:
            old_status = row["status"]
            mapped_status = {
                "waiting": TicketStatus.NEW.value,
                "in_progress": TicketStatus.IN_PROGRESS.value,
                "resolved": TicketStatus.RESOLVED.value,
            }.get(old_status, TicketStatus.NEW.value)
            if row["staff_reply"] and mapped_status == TicketStatus.IN_PROGRESS.value:
                mapped_status = TicketStatus.RESOLVED.value
            category, priority, escalation = classify_ticket(row["question"], row["reason"], None)
            contact = row["contact"]
            user_email = contact.strip().lower() if contact and "@" in contact else None
            connection.execute(
                """
                INSERT INTO handover_tickets (
                    ticket_id, session_id, question, reason, contact, user_email,
                    status, assigned_to, category, priority, escalation_reason,
                    staff_reply, resolved_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["ticket_id"], row["session_id"], row["question"], row["reason"],
                    contact, user_email, mapped_status, row["assigned_to"], category.value,
                    priority.value, escalation.value, row["staff_reply"],
                    row["updated_at"] if mapped_status == TicketStatus.RESOLVED.value else None,
                    row["created_at"], row["updated_at"],
                ),
            )
        connection.execute("DROP TABLE handover_tickets_legacy")

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            self._migrate_legacy_table(connection)
            connection.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_ticket_status_created
                    ON handover_tickets(status, created_at);
                CREATE INDEX IF NOT EXISTS idx_ticket_assignment
                    ON handover_tickets(assigned_to, status);
                CREATE INDEX IF NOT EXISTS idx_ticket_category_priority
                    ON handover_tickets(category, priority);

                CREATE TABLE IF NOT EXISTS ticket_messages (
                    message_id TEXT PRIMARY KEY,
                    ticket_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    author_id TEXT,
                    request_id TEXT,
                    confidence REAL,
                    grounded INTEGER,
                    reason_code TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(ticket_id) REFERENCES handover_tickets(ticket_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_ticket_messages
                    ON ticket_messages(ticket_id, created_at);

                CREATE TABLE IF NOT EXISTS ticket_evidence (
                    evidence_id TEXT PRIMARY KEY,
                    ticket_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    content_preview TEXT,
                    retrieval_score REAL,
                    source_category TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(ticket_id) REFERENCES handover_tickets(ticket_id) ON DELETE CASCADE
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_ticket_evidence_source
                    ON ticket_evidence(ticket_id, source_id, url);

                CREATE TABLE IF NOT EXISTS ticket_notes (
                    note_id TEXT PRIMARY KEY,
                    ticket_id TEXT NOT NULL,
                    author_id TEXT NOT NULL,
                    note TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(ticket_id) REFERENCES handover_tickets(ticket_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS ticket_activities (
                    activity_id TEXT PRIMARY KEY,
                    ticket_id TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    detail TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(ticket_id) REFERENCES handover_tickets(ticket_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_ticket_activities
                    ON ticket_activities(ticket_id, created_at);

                CREATE TABLE IF NOT EXISTS knowledge_gaps (
                    gap_id TEXT PRIMARY KEY,
                    ticket_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(ticket_id) REFERENCES handover_tickets(ticket_id) ON DELETE CASCADE
                );
                """
            )
            connection.execute(
                """
                UPDATE handover_tickets
                SET status = ?, resolved_at = COALESCE(resolved_at, updated_at)
                WHERE status = ? AND staff_reply IS NOT NULL AND first_response_at IS NULL
                """,
                (TicketStatus.RESOLVED.value, TicketStatus.IN_PROGRESS.value),
            )

    @staticmethod
    def _activity(
        connection: sqlite3.Connection,
        ticket_id: str,
        actor_id: str,
        action: str,
        detail: str | None = None,
    ) -> None:
        connection.execute(
            "INSERT INTO ticket_activities VALUES (?, ?, ?, ?, ?, ?)",
            (_id("activity"), ticket_id, actor_id, action, detail, _now()),
        )

    def create(
        self,
        session_id: str,
        question: str,
        reason: str,
        contact: str | None,
        conversation: list[HandoverMessageSnapshot] | None = None,
        evidence: list[HandoverEvidenceSnapshot] | None = None,
        ai_confidence: float | None = None,
    ) -> TicketResponse:
        conversation = conversation or []
        evidence = evidence or []
        ticket_id = f"VU-{uuid.uuid4().hex[:12].upper()}"
        timestamp = _now()
        category, priority, escalation = classify_ticket(question, reason, ai_confidence)
        summary = build_summary(question, conversation, evidence, escalation)
        suggestion = build_suggested_reply(question, evidence)
        user_email = contact.strip().lower() if contact and "@" in contact else None
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO handover_tickets (
                    ticket_id, session_id, question, reason, contact, user_email,
                    status, category, priority, escalation_reason, ai_confidence,
                    ai_summary, suggested_reply, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticket_id, session_id, question, reason, contact, user_email,
                    TicketStatus.NEW.value, category.value, priority.value,
                    escalation.value, ai_confidence, summary, suggestion, timestamp, timestamp,
                ),
            )
            snapshots = conversation or [
                HandoverMessageSnapshot(role="user", content=question, created_at=datetime.fromisoformat(timestamp))
            ]
            for item in snapshots:
                connection.execute(
                    """
                    INSERT INTO ticket_messages (
                        message_id, ticket_id, role, content, request_id, confidence,
                        grounded, reason_code, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _id("message"), ticket_id, item.role, item.content, item.request_id,
                        item.confidence, None if item.grounded is None else int(item.grounded),
                        item.reason_code, (item.created_at or datetime.fromisoformat(timestamp)).isoformat(),
                    ),
                )
            for item in evidence:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO ticket_evidence (
                        evidence_id, ticket_id, source_id, title, url, content_preview,
                        retrieval_score, source_category, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _id("evidence"), ticket_id, item.source_id, item.title, item.url,
                        item.content_preview, item.retrieval_score, item.source_category, timestamp,
                    ),
                )
            self._activity(connection, ticket_id, "system", "ticket_created", f"priority={priority.value}")
            self._activity(connection, ticket_id, "system", "ai_triage_completed", f"category={category.value}")
        return self.get_for_session(ticket_id, session_id)

    def get_for_session(self, ticket_id: str, session_id: str) -> TicketResponse:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM handover_tickets WHERE ticket_id = ? AND session_id = ?",
                (ticket_id, session_id),
            ).fetchone()
        if row is None:
            raise KeyError(ticket_id)
        return self._to_public(row)

    def list_for_staff(
        self,
        status: TicketStatus | None = None,
        *,
        category: TicketCategory | None = None,
        priority: TicketPriority | None = None,
        assigned_to: str | None = None,
        search: str | None = None,
        sort: str = "oldest",
    ) -> list[StaffTicketResponse]:
        where: list[str] = []
        parameters: list[str] = []
        if status:
            where.append("status = ?")
            parameters.append(status.value)
        if category:
            where.append("category = ?")
            parameters.append(category.value)
        if priority:
            where.append("priority = ?")
            parameters.append(priority.value)
        if assigned_to == "unassigned":
            where.append("assigned_to IS NULL")
        elif assigned_to:
            where.append("assigned_to = ?")
            parameters.append(assigned_to)
        if search:
            where.append("(ticket_id LIKE ? OR question LIKE ? OR contact LIKE ? OR ai_summary LIKE ?)")
            needle = f"%{search.strip()}%"
            parameters.extend([needle, needle, needle, needle])
        query = "SELECT * FROM handover_tickets"
        if where:
            query += " WHERE " + " AND ".join(where)
        if sort == "newest":
            query += " ORDER BY created_at DESC"
        elif sort == "priority":
            query += " ORDER BY CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, created_at ASC"
        else:
            query += " ORDER BY created_at ASC"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
            return [self._to_staff(connection, row) for row in rows]

    def get_for_staff(self, ticket_id: str) -> StaffTicketResponse:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM handover_tickets WHERE ticket_id = ?", (ticket_id,)
            ).fetchone()
            if row is None:
                raise KeyError(ticket_id)
            return self._to_staff(connection, row)

    def claim(self, ticket_id: str, staff_id: str) -> StaffTicketResponse:
        timestamp = _now()
        with self._connect() as connection:
            row = self._required_row(connection, ticket_id)
            self._assert_open(row)
            if row["assigned_to"] and row["assigned_to"] != staff_id:
                raise PermissionError("Ticket đang do cán bộ khác xử lý")
            connection.execute(
                "UPDATE handover_tickets SET status = ?, assigned_to = ?, updated_at = ? WHERE ticket_id = ?",
                (TicketStatus.IN_PROGRESS.value, staff_id, timestamp, ticket_id),
            )
            self._activity(connection, ticket_id, staff_id, "ticket_claimed")
        return self.get_for_staff(ticket_id)

    def assign(
        self,
        ticket_id: str,
        actor_id: str,
        assigned_to: str | None,
        department: str | None = None,
    ) -> StaffTicketResponse:
        timestamp = _now()
        with self._connect() as connection:
            row = self._required_row(connection, ticket_id)
            self._assert_open(row)
            new_status = TicketStatus.ASSIGNED.value if assigned_to else TicketStatus.NEW.value
            connection.execute(
                """
                UPDATE handover_tickets
                SET assigned_to = ?, assigned_department = ?, status = ?, updated_at = ?
                WHERE ticket_id = ?
                """,
                (assigned_to, department if assigned_to else None, new_status, timestamp, ticket_id),
            )
            action = "ticket_assigned" if assigned_to else "ticket_unassigned"
            self._activity(connection, ticket_id, actor_id, action, assigned_to or None)
        return self.get_for_staff(ticket_id)

    def set_status(self, ticket_id: str, staff_id: str, status: TicketStatus) -> StaffTicketResponse:
        if status in {TicketStatus.RESOLVED, TicketStatus.CLOSED}:
            raise ValueError("Dùng thao tác hoàn tất hoặc đóng ticket để bảo đảm có audit log")
        with self._connect() as connection:
            row = self._required_row(connection, ticket_id)
            self._assert_owner(row, staff_id)
            self._assert_open(row)
            connection.execute(
                "UPDATE handover_tickets SET status = ?, updated_at = ? WHERE ticket_id = ?",
                (status.value, _now(), ticket_id),
            )
            self._activity(connection, ticket_id, staff_id, "status_changed", status.value)
        return self.get_for_staff(ticket_id)

    def update_classification(
        self,
        ticket_id: str,
        staff_id: str,
        category: TicketCategory | None,
        priority: TicketPriority | None,
    ) -> StaffTicketResponse:
        if category is None and priority is None:
            raise ValueError("Cần chọn category hoặc priority")
        with self._connect() as connection:
            row = self._required_row(connection, ticket_id)
            self._assert_open(row)
            next_category = category.value if category else row["category"]
            next_priority = priority.value if priority else row["priority"]
            connection.execute(
                "UPDATE handover_tickets SET category = ?, priority = ?, updated_at = ? WHERE ticket_id = ?",
                (next_category, next_priority, _now(), ticket_id),
            )
            self._activity(
                connection, ticket_id, staff_id, "classification_updated",
                json.dumps({"category": next_category, "priority": next_priority}),
            )
        return self.get_for_staff(ticket_id)

    def add_note(self, ticket_id: str, staff_id: str, note: str) -> StaffTicketResponse:
        with self._connect() as connection:
            self._required_row(connection, ticket_id)
            connection.execute(
                "INSERT INTO ticket_notes VALUES (?, ?, ?, ?, ?)",
                (_id("note"), ticket_id, staff_id, note.strip(), _now()),
            )
            self._activity(connection, ticket_id, staff_id, "internal_note_added")
        return self.get_for_staff(ticket_id)

    def reply(self, ticket_id: str, staff_id: str, reply: str) -> StaffTicketResponse:
        timestamp = _now()
        with self._connect() as connection:
            row = self._required_row(connection, ticket_id)
            self._assert_open(row)
            self._assert_owner(row, staff_id)
            connection.execute(
                """
                UPDATE handover_tickets
                SET staff_reply = ?, status = ?, first_response_at = COALESCE(first_response_at, ?),
                    last_response_at = ?, email_delivery_status = 'pending', updated_at = ?
                WHERE ticket_id = ?
                """,
                (reply.strip(), TicketStatus.WAITING_FOR_USER.value, timestamp, timestamp, timestamp, ticket_id),
            )
            connection.execute(
                """
                INSERT INTO ticket_messages (message_id, ticket_id, role, content, author_id, created_at)
                VALUES (?, ?, 'staff', ?, ?, ?)
                """,
                (_id("message"), ticket_id, reply.strip(), staff_id, timestamp),
            )
            self._activity(connection, ticket_id, staff_id, "staff_reply_recorded")
        return self.get_for_staff(ticket_id)

    def record_email_delivery(
        self,
        ticket_id: str,
        *,
        delivered: bool,
        detail: str | None = None,
    ) -> StaffTicketResponse:
        with self._connect() as connection:
            self._required_row(connection, ticket_id)
            delivery = "sent" if delivered else "failed"
            connection.execute(
                "UPDATE handover_tickets SET email_delivery_status = ?, updated_at = ? WHERE ticket_id = ?",
                (delivery, _now(), ticket_id),
            )
            self._activity(connection, ticket_id, "system", f"email_{delivery}", detail)
        return self.get_for_staff(ticket_id)

    def regenerate_ai(self, ticket_id: str, staff_id: str) -> StaffTicketResponse:
        with self._connect() as connection:
            row = self._required_row(connection, ticket_id)
            messages = self._messages(connection, ticket_id)
            evidence = self._evidence(connection, ticket_id)
            message_snapshots = [
                HandoverMessageSnapshot(
                    role=item.role,
                    content=item.content,
                    created_at=item.created_at,
                    request_id=item.request_id,
                    confidence=item.confidence,
                    grounded=item.grounded,
                    reason_code=item.reason_code,
                )
                for item in messages if item.role in {"user", "assistant"}
            ]
            evidence_snapshots = [
                HandoverEvidenceSnapshot(
                    source_id=item.source_id, title=item.title, url=item.url,
                    content_preview=item.content_preview, retrieval_score=item.retrieval_score,
                    source_category=item.source_category,
                ) for item in evidence
            ]
            summary = build_summary(
                row["question"], message_snapshots, evidence_snapshots,
                EscalationReason(row["escalation_reason"]),
            )
            suggestion = build_suggested_reply(row["question"], evidence_snapshots)
            connection.execute(
                "UPDATE handover_tickets SET ai_summary = ?, suggested_reply = ?, updated_at = ? WHERE ticket_id = ?",
                (summary, suggestion, _now(), ticket_id),
            )
            self._activity(connection, ticket_id, staff_id, "ai_assistance_regenerated")
        return self.get_for_staff(ticket_id)

    def resolve(
        self,
        ticket_id: str,
        staff_id: str,
        resolution_summary: str | None = None,
        resolution_type: str = "answered",
        knowledge_gap: bool = False,
        knowledge_gap_description: str | None = None,
    ) -> StaffTicketResponse:
        timestamp = _now()
        with self._connect() as connection:
            row = self._required_row(connection, ticket_id)
            self._assert_owner(row, staff_id)
            self._assert_open(row)
            if not row["staff_reply"]:
                raise ValueError("Cần có phản hồi trước khi hoàn tất ticket")
            summary = (resolution_summary or row["staff_reply"]).strip()
            connection.execute(
                """
                UPDATE handover_tickets
                SET status = ?, resolution_summary = ?, resolution_type = ?, knowledge_gap = ?,
                    resolved_at = ?, updated_at = ? WHERE ticket_id = ?
                """,
                (
                    TicketStatus.RESOLVED.value, summary, resolution_type,
                    int(knowledge_gap), timestamp, timestamp, ticket_id,
                ),
            )
            if knowledge_gap:
                description = (knowledge_gap_description or summary).strip()
                connection.execute(
                    "INSERT INTO knowledge_gaps VALUES (?, ?, ?, ?, 'open', ?, ?)",
                    (_id("gap"), ticket_id, row["category"], description, staff_id, timestamp),
                )
            self._activity(connection, ticket_id, staff_id, "ticket_resolved", resolution_type)
        return self.get_for_staff(ticket_id)

    def close(self, ticket_id: str, staff_id: str) -> StaffTicketResponse:
        timestamp = _now()
        with self._connect() as connection:
            row = self._required_row(connection, ticket_id)
            if row["status"] != TicketStatus.RESOLVED.value:
                raise ValueError("Chỉ ticket đã hoàn tất mới có thể đóng")
            connection.execute(
                "UPDATE handover_tickets SET status = ?, closed_at = ?, updated_at = ? WHERE ticket_id = ?",
                (TicketStatus.CLOSED.value, timestamp, timestamp, ticket_id),
            )
            self._activity(connection, ticket_id, staff_id, "ticket_closed")
        return self.get_for_staff(ticket_id)

    def metrics(self) -> StaffTicketMetrics:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM handover_tickets").fetchall()
        now = _now_dt()
        open_rows = [row for row in rows if row["status"] not in {"resolved", "closed"}]
        response_minutes = [
            (datetime.fromisoformat(row["first_response_at"]) - datetime.fromisoformat(row["created_at"])).total_seconds() / 60
            for row in rows if row["first_response_at"]
        ]

        def breakdown(column: str) -> list[MetricBreakdown]:
            values: dict[str, int] = {}
            for row in rows:
                values[row[column]] = values.get(row[column], 0) + 1
            return [MetricBreakdown(key=key, count=count) for key, count in sorted(values.items())]

        return StaffTicketMetrics(
            open_count=len(open_rows),
            unassigned_count=sum(row["assigned_to"] is None for row in open_rows),
            overdue_count=sum(self._sla_deadline(row) < now for row in open_rows),
            resolved_today=sum(
                bool(row["resolved_at"]) and datetime.fromisoformat(row["resolved_at"]).date() == now.date()
                for row in rows
            ),
            average_first_response_minutes=(
                round(sum(response_minutes) / len(response_minutes), 1) if response_minutes else None
            ),
            by_status=breakdown("status"),
            by_category=breakdown("category"),
            by_priority=breakdown("priority"),
        )

    def list_knowledge_gaps(self) -> list[KnowledgeGapItem]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM knowledge_gaps ORDER BY created_at DESC").fetchall()
        return [
            KnowledgeGapItem(
                gap_id=row["gap_id"], ticket_id=row["ticket_id"],
                category=TicketCategory(row["category"]), description=row["description"],
                status=row["status"], created_by=row["created_by"],
                created_at=datetime.fromisoformat(row["created_at"]),
            ) for row in rows
        ]

    @staticmethod
    def _required_row(connection: sqlite3.Connection, ticket_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM handover_tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        if row is None:
            raise KeyError(ticket_id)
        return row

    @staticmethod
    def _assert_open(row: sqlite3.Row) -> None:
        if row["status"] in {TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value}:
            raise ValueError("Ticket đã kết thúc")

    @staticmethod
    def _assert_owner(row: sqlite3.Row, staff_id: str) -> None:
        if row["assigned_to"] != staff_id:
            raise PermissionError("Cán bộ phải được phân công ticket trước khi thao tác")

    def _messages(self, connection: sqlite3.Connection, ticket_id: str) -> list[TicketMessage]:
        rows = connection.execute(
            "SELECT * FROM ticket_messages WHERE ticket_id = ? ORDER BY created_at ASC", (ticket_id,)
        ).fetchall()
        return [
            TicketMessage(
                message_id=row["message_id"], role=row["role"], content=row["content"],
                author_id=row["author_id"], request_id=row["request_id"],
                confidence=row["confidence"],
                grounded=None if row["grounded"] is None else bool(row["grounded"]),
                reason_code=row["reason_code"], created_at=datetime.fromisoformat(row["created_at"]),
            ) for row in rows
        ]

    def _evidence(self, connection: sqlite3.Connection, ticket_id: str) -> list[TicketEvidence]:
        rows = connection.execute(
            "SELECT * FROM ticket_evidence WHERE ticket_id = ? ORDER BY created_at ASC", (ticket_id,)
        ).fetchall()
        return [
            TicketEvidence(
                evidence_id=row["evidence_id"], source_id=row["source_id"], title=row["title"],
                url=row["url"], content_preview=row["content_preview"],
                retrieval_score=row["retrieval_score"], source_category=row["source_category"],
                created_at=datetime.fromisoformat(row["created_at"]),
            ) for row in rows
        ]

    def _notes(self, connection: sqlite3.Connection, ticket_id: str) -> list[TicketNote]:
        rows = connection.execute(
            "SELECT * FROM ticket_notes WHERE ticket_id = ? ORDER BY created_at DESC", (ticket_id,)
        ).fetchall()
        return [
            TicketNote(
                note_id=row["note_id"], author_id=row["author_id"], note=row["note"],
                created_at=datetime.fromisoformat(row["created_at"]),
            ) for row in rows
        ]

    def _activities(self, connection: sqlite3.Connection, ticket_id: str) -> list[TicketActivity]:
        rows = connection.execute(
            "SELECT * FROM ticket_activities WHERE ticket_id = ? ORDER BY created_at DESC", (ticket_id,)
        ).fetchall()
        return [
            TicketActivity(
                activity_id=row["activity_id"], actor_id=row["actor_id"], action=row["action"],
                detail=row["detail"], created_at=datetime.fromisoformat(row["created_at"]),
            ) for row in rows
        ]

    @staticmethod
    def _sla_deadline(row: sqlite3.Row) -> datetime:
        hours = {"urgent": 2, "high": 8, "medium": 24, "low": 48}.get(row["priority"], 24)
        return datetime.fromisoformat(row["created_at"]) + timedelta(hours=hours)

    @classmethod
    def _sla_state(cls, row: sqlite3.Row) -> str:
        if row["status"] in {TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value}:
            return "completed"
        remaining = (cls._sla_deadline(row) - _now_dt()).total_seconds()
        if remaining <= 0:
            return "overdue"
        if remaining <= 60 * 60:
            return "due_soon"
        return "on_track"

    @staticmethod
    def _to_public(row: sqlite3.Row) -> TicketResponse:
        return TicketResponse(
            ticket_id=row["ticket_id"], status=TicketStatus(row["status"]),
            question=row["question"], reason=row["reason"], staff_reply=row["staff_reply"],
            assigned_to=row["assigned_to"], created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _to_staff(self, connection: sqlite3.Connection, row: sqlite3.Row) -> StaffTicketResponse:
        def optional_dt(name: str) -> datetime | None:
            return datetime.fromisoformat(row[name]) if row[name] else None

        return StaffTicketResponse(
            **self._to_public(row).model_dump(),
            contact=row["contact"], user_email=row["user_email"],
            assigned_department=row["assigned_department"], category=TicketCategory(row["category"]),
            priority=TicketPriority(row["priority"]), escalation_reason=EscalationReason(row["escalation_reason"]),
            ai_confidence=row["ai_confidence"], ai_summary=row["ai_summary"],
            suggested_reply=row["suggested_reply"], resolution_summary=row["resolution_summary"],
            resolution_type=row["resolution_type"], knowledge_gap=bool(row["knowledge_gap"]),
            first_response_at=optional_dt("first_response_at"), last_response_at=optional_dt("last_response_at"),
            resolved_at=optional_dt("resolved_at"), closed_at=optional_dt("closed_at"),
            email_delivery_status=row["email_delivery_status"], sla_deadline=self._sla_deadline(row),
            sla_state=self._sla_state(row), messages=self._messages(connection, row["ticket_id"]),
            evidence=self._evidence(connection, row["ticket_id"]), notes=self._notes(connection, row["ticket_id"]),
            activities=self._activities(connection, row["ticket_id"]),
        )


_ticket_store: TicketStore | None = None


def get_ticket_store() -> TicketStore:
    global _ticket_store
    if _ticket_store is None:
        _ticket_store = TicketStore()
    return _ticket_store
