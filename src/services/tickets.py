from __future__ import annotations

import json
import secrets
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
    KnowledgeGapStatus,
    MetricBreakdown,
    RoutingRule,
    StaffAvailability,
    StaffMember,
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


DEFAULT_ROUTING_DEPARTMENTS: dict[TicketCategory, str] = {
    TicketCategory.ADMISSIONS: "Tuyển sinh",
    TicketCategory.TUITION: "Tài chính & Học phí",
    TicketCategory.SCHOLARSHIP: "Học bổng",
    TicketCategory.PROGRAM: "Chương trình đào tạo",
    TicketCategory.APPLICATION: "Hỗ trợ hồ sơ",
    TicketCategory.TECHNICAL: "Kỹ thuật",
    TicketCategory.OTHER: "Tuyển sinh",
}


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
                owner_user_id TEXT,
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
            if "owner_user_id" not in columns:
                connection.execute("ALTER TABLE handover_tickets ADD COLUMN owner_user_id TEXT")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_ticket_owner_user ON handover_tickets(owner_user_id, updated_at)"
            )
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
                    ticket_id, session_id, owner_user_id, question, reason, contact, user_email,
                    status, assigned_to, category, priority, escalation_reason,
                    staff_reply, resolved_at, created_at, updated_at
                ) VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                CREATE INDEX IF NOT EXISTS idx_ticket_owner_user
                    ON handover_tickets(owner_user_id, updated_at);
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
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS staff_members (
                    staff_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    department TEXT NOT NULL,
                    specialties_json TEXT NOT NULL DEFAULT '[]',
                    availability TEXT NOT NULL DEFAULT 'available',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_staff_members_routing
                    ON staff_members(active, availability, department);

                CREATE TABLE IF NOT EXISTS ticket_routing_rules (
                    category TEXT PRIMARY KEY,
                    department TEXT NOT NULL,
                    auto_assign INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                );
                """
            )
            timestamp = _now()
            for category, department in DEFAULT_ROUTING_DEPARTMENTS.items():
                connection.execute(
                    """
                    INSERT OR IGNORE INTO ticket_routing_rules
                        (category, department, auto_assign, updated_at)
                    VALUES (?, ?, 1, ?)
                    """,
                    (category.value, department, timestamp),
                )
            # Profiles are independent from secrets.  Bootstrap configured
            # staff identities as inactive routing profiles only when they do
            # not exist yet; Admin still chooses their team and specialties.
            for staff_id in get_settings().staff_tokens:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO staff_members
                        (staff_id, display_name, department, specialties_json, availability, active, created_at, updated_at)
                    VALUES (?, ?, 'Chưa phân nhóm', '[]', 'offline', 1, ?, ?)
                    """,
                    (staff_id, staff_id, timestamp, timestamp),
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

    @staticmethod
    def _member_from_row(connection: sqlite3.Connection, row: sqlite3.Row) -> StaffMember:
        try:
            specialties = [TicketCategory(value) for value in json.loads(row["specialties_json"])]
        except (TypeError, ValueError, json.JSONDecodeError):
            specialties = []
        open_ticket_count = connection.execute(
            """
            SELECT COUNT(*) FROM handover_tickets
            WHERE assigned_to = ? AND status IN (?, ?, ?)
            """,
            (
                row["staff_id"], TicketStatus.ASSIGNED.value,
                TicketStatus.IN_PROGRESS.value, TicketStatus.WAITING_FOR_USER.value,
            ),
        ).fetchone()[0]
        return StaffMember(
            staff_id=row["staff_id"], display_name=row["display_name"],
            department=row["department"], specialties=specialties,
            availability=StaffAvailability(row["availability"]), active=bool(row["active"]),
            open_ticket_count=open_ticket_count, updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def list_staff_members(self) -> list[StaffMember]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM staff_members ORDER BY department, display_name, staff_id"
            ).fetchall()
            return [self._member_from_row(connection, row) for row in rows]

    def get_staff_member(self, staff_id: str) -> StaffMember:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM staff_members WHERE staff_id = ?", (staff_id,)
            ).fetchone()
            if not row:
                raise KeyError(staff_id)
            return self._member_from_row(connection, row)

    def upsert_staff_member(
        self,
        staff_id: str,
        display_name: str,
        department: str,
        specialties: list[TicketCategory],
        availability: StaffAvailability,
        active: bool,
    ) -> StaffMember:
        timestamp = _now()
        encoded_specialties = json.dumps(sorted({item.value for item in specialties}))
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO staff_members
                    (staff_id, display_name, department, specialties_json, availability, active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(staff_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    department = excluded.department,
                    specialties_json = excluded.specialties_json,
                    availability = excluded.availability,
                    active = excluded.active,
                    updated_at = excluded.updated_at
                """,
                (staff_id.strip(), display_name.strip(), department.strip(), encoded_specialties,
                 availability.value, int(active), timestamp, timestamp),
            )
            if active and availability == StaffAvailability.AVAILABLE:
                self._dispatch_pending(connection, specialties)
        return self.get_staff_member(staff_id.strip())

    def set_staff_availability(self, staff_id: str, availability: StaffAvailability) -> StaffMember:
        with self._connect() as connection:
            updated = connection.execute(
                "UPDATE staff_members SET availability = ?, updated_at = ? WHERE staff_id = ?",
                (availability.value, _now(), staff_id),
            ).rowcount
            if not updated:
                raise KeyError(staff_id)
            if availability == StaffAvailability.AVAILABLE:
                row = connection.execute(
                    "SELECT specialties_json FROM staff_members WHERE staff_id = ?", (staff_id,)
                ).fetchone()
                specialties = [TicketCategory(value) for value in json.loads(row["specialties_json"])]
                self._dispatch_pending(connection, specialties)
        return self.get_staff_member(staff_id)

    def list_routing_rules(self) -> list[RoutingRule]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM ticket_routing_rules ORDER BY category"
            ).fetchall()
        return [
            RoutingRule(
                category=TicketCategory(row["category"]), department=row["department"],
                auto_assign=bool(row["auto_assign"]),
            )
            for row in rows
        ]

    def update_routing_rule(
        self, category: TicketCategory, department: str, auto_assign: bool
    ) -> RoutingRule:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ticket_routing_rules (category, department, auto_assign, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(category) DO UPDATE SET
                    department = excluded.department,
                    auto_assign = excluded.auto_assign,
                    updated_at = excluded.updated_at
                """,
                (category.value, department.strip(), int(auto_assign), _now()),
            )
            connection.execute(
                """
                UPDATE handover_tickets
                SET assigned_department = ?, updated_at = ?
                WHERE category = ? AND assigned_to IS NULL AND status = ?
                """,
                (department.strip(), _now(), category.value, TicketStatus.NEW.value),
            )
            if auto_assign:
                self._dispatch_pending(connection, [category])
        return RoutingRule(category=category, department=department.strip(), auto_assign=auto_assign)

    @staticmethod
    def _routing_rule(connection: sqlite3.Connection, category: TicketCategory) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM ticket_routing_rules WHERE category = ?", (category.value,)
        ).fetchone()
        if not row:
            raise KeyError(category.value)
        return row

    def _eligible_staff(
        self, connection: sqlite3.Connection, category: TicketCategory
    ) -> list[sqlite3.Row]:
        rows = connection.execute(
            "SELECT * FROM staff_members WHERE active = 1 AND availability = ?",
            (StaffAvailability.AVAILABLE.value,),
        ).fetchall()
        return [
            row for row in rows
            if category.value in json.loads(row["specialties_json"])
        ]

    def _auto_assign(
        self, connection: sqlite3.Connection, ticket_id: str, category: TicketCategory
    ) -> tuple[str | None, str]:
        rule = self._routing_rule(connection, category)
        department = rule["department"]
        if not bool(rule["auto_assign"]):
            return None, department
        candidates = self._eligible_staff(connection, category)
        if not candidates:
            return None, department
        open_counts = {
            row["staff_id"]: connection.execute(
                """
                SELECT COUNT(*) FROM handover_tickets
                WHERE assigned_to = ? AND status IN (?, ?, ?)
                """,
                (
                    row["staff_id"], TicketStatus.ASSIGNED.value,
                    TicketStatus.IN_PROGRESS.value, TicketStatus.WAITING_FOR_USER.value,
                ),
            ).fetchone()[0]
            for row in candidates
        }
        lowest = min(open_counts.values())
        least_loaded = [row["staff_id"] for row in candidates if open_counts[row["staff_id"]] == lowest]
        return secrets.choice(least_loaded), department

    def _dispatch_pending(
        self, connection: sqlite3.Connection, specialties: list[TicketCategory]
    ) -> None:
        """Fill the team queue when a specialist becomes available."""
        for category in set(specialties):
            rows = connection.execute(
                """
                SELECT ticket_id, priority FROM handover_tickets
                WHERE category = ? AND status = ? AND assigned_to IS NULL
                ORDER BY CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2 ELSE 3 END, created_at ASC
                """,
                (category.value, TicketStatus.NEW.value),
            ).fetchall()
            for row in rows:
                assigned_to, department = self._auto_assign(connection, row["ticket_id"], category)
                if not assigned_to:
                    continue
                connection.execute(
                    """
                    UPDATE handover_tickets
                    SET assigned_to = ?, assigned_department = ?, status = ?, updated_at = ?
                    WHERE ticket_id = ? AND assigned_to IS NULL
                    """,
                    (assigned_to, department, TicketStatus.ASSIGNED.value, _now(), row["ticket_id"]),
                )
                self._activity(connection, row["ticket_id"], "system", "ticket_auto_assigned", assigned_to)

    def create(
        self,
        session_id: str,
        question: str,
        reason: str,
        contact: str | None,
        conversation: list[HandoverMessageSnapshot] | None = None,
        evidence: list[HandoverEvidenceSnapshot] | None = None,
        ai_confidence: float | None = None,
        owner_user_id: str | None = None,
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
            assigned_to, assigned_department = self._auto_assign(connection, ticket_id, category)
            initial_status = TicketStatus.ASSIGNED.value if assigned_to else TicketStatus.NEW.value
            connection.execute(
                """
                INSERT INTO handover_tickets (
                    ticket_id, session_id, owner_user_id, question, reason, contact, user_email,
                    status, assigned_to, assigned_department, category, priority, escalation_reason, ai_confidence,
                    ai_summary, suggested_reply, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticket_id, session_id, owner_user_id, question, reason, contact, user_email,
                    initial_status, assigned_to, assigned_department, category.value, priority.value,
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
            self._activity(connection, ticket_id, "system", "ticket_routed", assigned_department)
            if assigned_to:
                self._activity(connection, ticket_id, "system", "ticket_auto_assigned", assigned_to)
            else:
                self._activity(connection, ticket_id, "system", "ticket_waiting_for_available_staff")
        return self.get_for_session(ticket_id, session_id)

    def claim_session(self, session_id: str, owner_user_id: str) -> int:
        """Attach anonymous tickets from a browser session to its signed-in owner."""
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE handover_tickets
                SET owner_user_id = ?
                WHERE session_id = ? AND (owner_user_id IS NULL OR owner_user_id = '')
                """,
                (owner_user_id, session_id),
            )
            return cursor.rowcount

    def list_for_user(self, owner_user_id: str) -> list[TicketResponse]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM handover_tickets WHERE owner_user_id = ? ORDER BY updated_at DESC",
                (owner_user_id,),
            ).fetchall()
        return [self._to_public(row) for row in rows]

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
        viewer_id: str | None = None,
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
        if viewer_id:
            with self._connect() as connection:
                member = connection.execute(
                    "SELECT specialties_json FROM staff_members WHERE staff_id = ? AND active = 1",
                    (viewer_id,),
                ).fetchone()
            specialties = []
            if member:
                try:
                    specialties = [TicketCategory(value).value for value in json.loads(member["specialties_json"])]
                except (TypeError, ValueError, json.JSONDecodeError):
                    specialties = []
            if specialties:
                placeholders = ", ".join("?" for _ in specialties)
                where.append(
                    f"(assigned_to = ? OR (assigned_to IS NULL AND status = ? AND category IN ({placeholders})))"
                )
                parameters.extend([viewer_id, TicketStatus.NEW.value, *specialties])
            else:
                where.append("assigned_to = ?")
                parameters.append(viewer_id)
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

    def get_for_staff(self, ticket_id: str, viewer_id: str | None = None) -> StaffTicketResponse:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM handover_tickets WHERE ticket_id = ?", (ticket_id,)
            ).fetchone()
            if row is None:
                raise KeyError(ticket_id)
            if viewer_id and row["assigned_to"] != viewer_id:
                member = connection.execute(
                    "SELECT active, specialties_json FROM staff_members WHERE staff_id = ?",
                    (viewer_id,),
                ).fetchone()
                try:
                    specialties = json.loads(member["specialties_json"]) if member else []
                except (TypeError, ValueError, json.JSONDecodeError):
                    specialties = []
                can_view_team_queue = bool(
                    row["assigned_to"] is None
                    and row["status"] == TicketStatus.NEW.value
                    and member
                    and bool(member["active"])
                    and row["category"] in specialties
                )
                if not can_view_team_queue:
                    raise PermissionError("Ticket không thuộc phạm vi nhóm chuyên môn của bạn")
            return self._to_staff(connection, row)

    def claim(self, ticket_id: str, staff_id: str) -> StaffTicketResponse:
        timestamp = _now()
        with self._connect() as connection:
            row = self._required_row(connection, ticket_id)
            self._assert_open(row)
            if row["assigned_to"] and row["assigned_to"] != staff_id:
                raise PermissionError("Ticket đang do cán bộ khác xử lý")
            member = connection.execute(
                "SELECT * FROM staff_members WHERE staff_id = ?", (staff_id,)
            ).fetchone()
            assigned_department = row["assigned_department"]
            if row["assigned_to"] is None and member:
                if not bool(member["active"]) or member["availability"] != StaffAvailability.AVAILABLE.value:
                    raise PermissionError("Bạn cần ở trạng thái sẵn sàng để nhận ticket")
                try:
                    specialties = json.loads(member["specialties_json"])
                except (TypeError, ValueError, json.JSONDecodeError):
                    specialties = []
                if row["category"] not in specialties:
                    raise PermissionError("Ticket không thuộc chuyên môn của bạn")
                assigned_department = member["department"]
            updated = connection.execute(
                """
                UPDATE handover_tickets
                SET status = ?, assigned_to = ?, assigned_department = ?, updated_at = ?
                WHERE ticket_id = ? AND (assigned_to IS NULL OR assigned_to = ?)
                """,
                (TicketStatus.IN_PROGRESS.value, staff_id, assigned_department, timestamp, ticket_id, staff_id),
            ).rowcount
            if not updated:
                raise PermissionError("Ticket vừa được cán bộ khác nhận")
            self._activity(connection, ticket_id, staff_id, "ticket_claimed", "staff_acknowledged")
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
            routing_department = self._routing_rule(connection, TicketCategory(row["category"]))["department"]
            connection.execute(
                """
                UPDATE handover_tickets
                SET assigned_to = ?, assigned_department = ?, status = ?, updated_at = ?
                WHERE ticket_id = ?
                """,
                (assigned_to, department or routing_department, new_status, timestamp, ticket_id),
            )
            action = "ticket_assigned" if assigned_to else "ticket_unassigned"
            self._activity(connection, ticket_id, actor_id, action, assigned_to or None)
        return self.get_for_staff(ticket_id)

    def assign_by_admin(
        self, ticket_id: str, admin_id: str, assigned_to: str | None
    ) -> StaffTicketResponse:
        """Assign or return a ticket to the queue with an auditable admin action."""
        timestamp = _now()
        with self._connect() as connection:
            row = self._required_row(connection, ticket_id)
            self._assert_open(row)
            department = self._routing_rule(connection, TicketCategory(row["category"]))["department"]
            if assigned_to:
                member = connection.execute(
                    "SELECT * FROM staff_members WHERE staff_id = ?", (assigned_to,)
                ).fetchone()
                if not member or not bool(member["active"]):
                    raise ValueError("Cán bộ được chọn không tồn tại hoặc đã ngừng hoạt động")
                if member["availability"] == StaffAvailability.OFFLINE.value:
                    raise ValueError("Không thể phân công ticket cho cán bộ đang offline")
                department = member["department"]
            new_status = TicketStatus.ASSIGNED.value if assigned_to else TicketStatus.NEW.value
            connection.execute(
                """
                UPDATE handover_tickets
                SET assigned_to = ?, assigned_department = ?, status = ?, updated_at = ?
                WHERE ticket_id = ?
                """,
                (assigned_to, department, new_status, timestamp, ticket_id),
            )
            self._activity(
                connection, ticket_id, admin_id,
                "admin_ticket_assigned" if assigned_to else "admin_ticket_unassigned",
                assigned_to,
            )
        return self.get_for_staff(ticket_id)

    def set_status(self, ticket_id: str, staff_id: str, status: TicketStatus) -> StaffTicketResponse:
        if status in {TicketStatus.RESOLVED, TicketStatus.CLOSED}:
            raise ValueError("Dùng thao tác hoàn tất hoặc đóng ticket để bảo đảm có audit log")
        with self._connect() as connection:
            row = self._required_row(connection, ticket_id)
            self._assert_owner(row, staff_id)
            self._assert_open(row)
            allowed_transitions = {
                TicketStatus.ASSIGNED.value: {TicketStatus.IN_PROGRESS.value},
                TicketStatus.IN_PROGRESS.value: {TicketStatus.WAITING_FOR_USER.value},
                TicketStatus.WAITING_FOR_USER.value: {TicketStatus.IN_PROGRESS.value},
            }
            if status.value not in allowed_transitions.get(row["status"], set()):
                raise ValueError(f"Không thể chuyển ticket từ {row['status']} sang {status.value}")
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
            self._assert_owner(row, staff_id)
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
            row = self._required_row(connection, ticket_id)
            self._assert_owner(row, staff_id)
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
            if row["status"] not in {
                TicketStatus.ASSIGNED.value,
                TicketStatus.IN_PROGRESS.value,
                TicketStatus.WAITING_FOR_USER.value,
            }:
                raise ValueError("Ticket chưa ở trạng thái có thể phản hồi")
            connection.execute(
                """
                UPDATE handover_tickets
                SET staff_reply = ?, status = ?, first_response_at = COALESCE(first_response_at, ?),
                    last_response_at = ?, email_delivery_status = 'pending', updated_at = ?
                WHERE ticket_id = ?
                """,
                (reply.strip(), TicketStatus.WAITING_FOR_USER.value, timestamp, timestamp, timestamp, ticket_id),
            )
            if row["status"] == TicketStatus.ASSIGNED.value:
                self._activity(connection, ticket_id, staff_id, "ticket_started_on_reply")
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
            self._assert_owner(row, staff_id)
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
            self._assert_owner(row, staff_id)
            if row["status"] != TicketStatus.RESOLVED.value:
                raise ValueError("Chỉ ticket đã hoàn tất mới có thể đóng")
            connection.execute(
                "UPDATE handover_tickets SET status = ?, closed_at = ?, updated_at = ? WHERE ticket_id = ?",
                (TicketStatus.CLOSED.value, timestamp, timestamp, ticket_id),
            )
            self._activity(connection, ticket_id, staff_id, "ticket_closed")
        return self.get_for_staff(ticket_id)

    def metrics(self, staff_id: str | None = None) -> StaffTicketMetrics:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM handover_tickets").fetchall()
            team_queue_rows: list[sqlite3.Row] = []
        if staff_id:
            rows = [row for row in rows if row["assigned_to"] == staff_id]
            with self._connect() as connection:
                member = connection.execute(
                    "SELECT active, specialties_json FROM staff_members WHERE staff_id = ?",
                    (staff_id,),
                ).fetchone()
            try:
                specialties = json.loads(member["specialties_json"]) if member and bool(member["active"]) else []
            except (TypeError, ValueError, json.JSONDecodeError):
                specialties = []
            if specialties:
                with self._connect() as connection:
                    team_queue_rows = connection.execute(
                        "SELECT * FROM handover_tickets WHERE assigned_to IS NULL AND status = ? AND category IN ({})".format(
                            ", ".join("?" for _ in specialties)
                        ),
                        [TicketStatus.NEW.value, *specialties],
                    ).fetchall()
        else:
            team_queue_rows = [
                row for row in rows
                if row["assigned_to"] is None and row["status"] not in {"resolved", "closed"}
            ]
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
            unassigned_count=len(team_queue_rows),
            team_queue_count=len(team_queue_rows),
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

    def list_knowledge_gaps(self, status: KnowledgeGapStatus | None = None) -> list[KnowledgeGapItem]:
        with self._connect() as connection:
            if status:
                rows = connection.execute(
                    "SELECT * FROM knowledge_gaps WHERE status = ? ORDER BY created_at DESC",
                    (status.value,),
                ).fetchall()
            else:
                rows = connection.execute("SELECT * FROM knowledge_gaps ORDER BY created_at DESC").fetchall()
        return [
            KnowledgeGapItem(
                gap_id=row["gap_id"], ticket_id=row["ticket_id"],
                category=TicketCategory(row["category"]), description=row["description"],
                status=row["status"], created_by=row["created_by"],
                created_at=datetime.fromisoformat(row["created_at"]),
            ) for row in rows
        ]

    def update_knowledge_gap(
        self, gap_id: str, status: KnowledgeGapStatus, actor_id: str
    ) -> KnowledgeGapItem:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_gaps WHERE gap_id = ?", (gap_id,)
            ).fetchone()
            if row is None:
                raise KeyError(gap_id)
            connection.execute(
                "UPDATE knowledge_gaps SET status = ? WHERE gap_id = ?",
                (status.value, gap_id),
            )
            self._activity(
                connection, row["ticket_id"], actor_id,
                "knowledge_gap_status_changed", status.value,
            )
            updated = connection.execute(
                "SELECT * FROM knowledge_gaps WHERE gap_id = ?", (gap_id,)
            ).fetchone()
        return KnowledgeGapItem(
            gap_id=updated["gap_id"], ticket_id=updated["ticket_id"],
            category=TicketCategory(updated["category"]), description=updated["description"],
            status=updated["status"], created_by=updated["created_by"],
            created_at=datetime.fromisoformat(updated["created_at"]),
        )

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
