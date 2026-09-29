import pytest

from src.models.schemas import TicketStatus
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
    resolved = store.resolve(ticket.ticket_id, "staff-1")
    assert resolved.status == TicketStatus.RESOLVED


def test_ticket_cannot_resolve_without_reply(tmp_path):
    store = TicketStore(tmp_path / "tickets.db")
    ticket = store.create("session-owner-1234", "Question", "Reason", None)
    store.claim(ticket.ticket_id, "staff-1")

    with pytest.raises(ValueError, match="phản hồi"):
        store.resolve(ticket.ticket_id, "staff-1")
