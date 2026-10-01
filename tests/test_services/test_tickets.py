import sqlite3

import pytest

from src.models.schemas import StaffAvailability, TicketCategory, TicketStatus
from src.services.session import SessionStore
from src.services.tickets import TicketStore


def test_ticket_lifecycle_and_session_isolation(tmp_path):
    store = TicketStore(tmp_path / "tickets.db")
    ticket = store.create(
        session_id="session-owner-1234",
        question="Can bo kiem tra ho so",
        reason="personal_case",
        contact=None,
    )

    assert ticket.status == TicketStatus.WAITING
    with pytest.raises(KeyError):
        store.get_for_session(ticket.ticket_id, "session-other-1234")

    claimed = store.claim(ticket.ticket_id, "staff-1")
    assert claimed.status == TicketStatus.IN_PROGRESS
    with pytest.raises(PermissionError):
        store.claim(ticket.ticket_id, "staff-2")

    replied = store.reply(ticket.ticket_id, "staff-1", "Da kiem tra")
    assert replied.staff_reply == "Da kiem tra"
    assert replied.status == TicketStatus.WAITING_FOR_USER

    resolved = store.resolve(
        ticket.ticket_id,
        "staff-1",
        resolution_summary="Da tra loi ung vien",
        resolution_type="answered",
    )
    assert resolved.status == TicketStatus.RESOLVED
    assert resolved.resolution_summary == "Da tra loi ung vien"


def test_ticket_cannot_resolve_without_reply(tmp_path):
    store = TicketStore(tmp_path / "tickets.db")
    ticket = store.create("session-owner-1234", "Question", "Reason", None)
    store.claim(ticket.ticket_id, "staff-1")

    with pytest.raises(ValueError, match="phản hồi"):
        store.resolve(ticket.ticket_id, "staff-1")


def test_legacy_replied_ticket_is_backfilled_to_resolved(tmp_path):
    path = tmp_path / "tickets.db"
    store = TicketStore(path)
    ticket = store.create("session-owner-1234", "Question", "Reason", None)
    store.claim(ticket.ticket_id, "staff-1")
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE handover_tickets SET staff_reply = ? WHERE ticket_id = ?",
            ("Legacy reply", ticket.ticket_id),
        )

    migrated_store = TicketStore(path)
    assert migrated_store.get_for_staff(ticket.ticket_id).status == TicketStatus.RESOLVED


def test_legacy_ticket_table_is_migrated_without_losing_data(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE handover_tickets (
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
            "INSERT INTO handover_tickets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "VU-LEGACY",
                "session-owner-1234",
                "Hoc phi nam nay?",
                "missing_evidence",
                "student@example.com",
                "waiting",
                None,
                None,
                "2026-09-01T00:00:00+00:00",
                "2026-09-01T00:00:00+00:00",
            ),
        )

    store = TicketStore(path)
    migrated = store.get_for_staff("VU-LEGACY")

    assert migrated.status == TicketStatus.NEW
    assert migrated.question == "Hoc phi nam nay?"
    assert migrated.user_email == "student@example.com"
    assert migrated.category.value == "tuition"


def test_anonymous_session_identifier_survives_process_restart():
    """A persisted ticket remains readable when the API process recreates session memory."""
    session_id = "anonymous-owner-token-1234567890"
    first_process = SessionStore()
    assert first_process.get_or_create(session_id).session_id == session_id

    restarted_process = SessionStore()
    assert restarted_process.get_or_create(session_id).session_id == session_id


def test_ticket_persists_context_evidence_notes_and_audit(tmp_path):
    from datetime import UTC, datetime

    from src.models.schemas import HandoverEvidenceSnapshot, HandoverMessageSnapshot

    store = TicketStore(tmp_path / "tickets.db")
    ticket = store.create(
        session_id="session-owner-1234",
        question="Hoc phi Bac si Y khoa bao nhieu?",
        reason="insufficient_retrieval_evidence",
        contact="student@example.com",
        ai_confidence=0.2,
        conversation=[
            HandoverMessageSnapshot(
                role="user",
                content="Hoc phi Bac si Y khoa bao nhieu?",
                created_at=datetime.now(UTC),
            ),
            HandoverMessageSnapshot(
                role="assistant",
                content="Chua du can cu.",
                confidence=0.2,
                grounded=False,
                reason_code="insufficient_retrieval_evidence",
                created_at=datetime.now(UTC),
            ),
        ],
        evidence=[
            HandoverEvidenceSnapshot(
                source_id="tuition-2026",
                title="Bieu phi 2026",
                url="https://vinuni.edu.vn/tuition",
            )
        ],
    )

    detail = store.get_for_staff(ticket.ticket_id)
    assert detail.category.value == "tuition"
    assert detail.priority.value == "high"
    assert detail.user_email == "student@example.com"
    assert len(detail.messages) == 2
    assert len(detail.evidence) == 1
    assert detail.ai_summary
    assert detail.suggested_reply
    assert detail.activities

    store.claim(ticket.ticket_id, "staff-1")
    store.add_note(ticket.ticket_id, "staff-1", "Can doi chieu phong tai chinh")
    assert store.get_for_staff(ticket.ticket_id).notes[0].note == "Can doi chieu phong tai chinh"


def test_assignment_email_state_and_knowledge_gap(tmp_path):
    store = TicketStore(tmp_path / "tickets.db")
    ticket = store.create("session-owner-1234", "Question", "personal_case", "student@example.com")

    assigned = store.assign(ticket.ticket_id, "lead-1", "staff-1", "Admissions")
    assert assigned.status == TicketStatus.ASSIGNED
    assert assigned.assigned_to == "staff-1"

    store.set_status(ticket.ticket_id, "staff-1", TicketStatus.IN_PROGRESS)
    store.reply(ticket.ticket_id, "staff-1", "Da kiem tra")
    delivery = store.record_email_delivery(ticket.ticket_id, delivered=True)
    assert delivery.email_delivery_status == "sent"

    resolved = store.resolve(
        ticket.ticket_id,
        "staff-1",
        resolution_summary="Thieu huong dan cho truong hop ca nhan",
        resolution_type="answered",
        knowledge_gap=True,
        knowledge_gap_description="Can bo sung FAQ cho truong hop ca nhan",
    )
    assert resolved.knowledge_gap is True
    assert store.list_knowledge_gaps()[0].ticket_id == ticket.ticket_id


def test_ticket_is_routed_to_available_specialist_with_lowest_load(tmp_path):
    store = TicketStore(tmp_path / "tickets.db")
    store.upsert_staff_member(
        "tuition-a", "Tuition A", "Tài chính & Học phí",
        [TicketCategory.TUITION], StaffAvailability.AVAILABLE, True,
    )
    store.upsert_staff_member(
        "tuition-b", "Tuition B", "Tài chính & Học phí",
        [TicketCategory.TUITION], StaffAvailability.BUSY, True,
    )

    ticket = store.create(
        "session-owner-1234", "Học phí năm nay là bao nhiêu?",
        "insufficient_retrieval_evidence", None,
    )
    routed = store.get_for_staff(ticket.ticket_id)

    assert routed.status == TicketStatus.ASSIGNED
    assert routed.assigned_to == "tuition-a"
    assert routed.assigned_department == "Tài chính & Học phí"

    store.set_staff_availability("tuition-a", StaffAvailability.BUSY)
    waiting = store.create(
        "session-owner-5678", "Học phí chương trình MBA?",
        "insufficient_retrieval_evidence", None,
    )
    assert waiting.status == TicketStatus.NEW
    assert store.get_for_staff(waiting.ticket_id).assigned_department == "Tài chính & Học phí"

    store.set_staff_availability("tuition-a", StaffAvailability.AVAILABLE)
    assert store.get_for_staff(waiting.ticket_id).assigned_to == "tuition-a"
    assert store.get_for_staff(waiting.ticket_id).status == TicketStatus.ASSIGNED


def test_staff_sees_and_claims_only_matching_team_queue(tmp_path):
    store = TicketStore(tmp_path / "tickets.db")
    store.upsert_staff_member(
        "tuition-a", "Tuition A", "Tài chính & Học phí",
        [TicketCategory.TUITION], StaffAvailability.AVAILABLE, True,
    )
    store.update_routing_rule(TicketCategory.TUITION, "Tài chính & Học phí", False)
    ticket = store.create(
        "session-team-1234", "Học phí năm nay là bao nhiêu?",
        "insufficient_retrieval_evidence", None,
    )

    queue = store.list_for_staff(viewer_id="tuition-a")
    assert [item.ticket_id for item in queue] == [ticket.ticket_id]
    assert queue[0].status == TicketStatus.NEW
    claimed = store.claim(ticket.ticket_id, "tuition-a")
    assert claimed.status == TicketStatus.IN_PROGRESS
    assert claimed.assigned_to == "tuition-a"


def test_staff_status_transition_does_not_skip_workflow(tmp_path):
    store = TicketStore(tmp_path / "tickets.db")
    ticket = store.create("session-transition-1234", "Question", "Reason", None)
    store.assign(ticket.ticket_id, "admin-1", "staff-1", "Admissions")
    store.set_status(ticket.ticket_id, "staff-1", TicketStatus.IN_PROGRESS)

    with pytest.raises(ValueError, match="Không thể chuyển ticket"):
        store.set_status(ticket.ticket_id, "staff-1", TicketStatus.ASSIGNED)
