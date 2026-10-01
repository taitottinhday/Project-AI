from __future__ import annotations

import re
from collections.abc import Iterable

from src.models.schemas import (
    EscalationReason,
    HandoverEvidenceSnapshot,
    HandoverMessageSnapshot,
    TicketCategory,
    TicketPriority,
)


def _contains(text: str, terms: Iterable[str]) -> bool:
    normalized = text.casefold()
    return any(term in normalized for term in terms)


def normalize_escalation_reason(reason: str) -> EscalationReason:
    value = reason.casefold().strip()
    if value in {item.value for item in EscalationReason}:
        return EscalationReason(value)
    if "conflict" in value or "mâu thuẫn" in value:
        return EscalationReason.CONFLICTING_EVIDENCE
    if "outdated" in value or "source_change" in value or "hết hạn" in value:
        return EscalationReason.OUTDATED_SOURCE
    if "personal" in value or "hồ sơ" in value:
        return EscalationReason.PERSONAL_CASE
    if "user_requested" in value or "requested" in value:
        return EscalationReason.USER_REQUESTED
    if "confidence" in value:
        return EscalationReason.LOW_CONFIDENCE
    if "evidence" in value or "retrieval" in value or "knowledge" in value:
        return EscalationReason.MISSING_EVIDENCE
    return EscalationReason.OTHER


def classify_ticket(
    question: str,
    reason: str,
    confidence: float | None,
) -> tuple[TicketCategory, TicketPriority, EscalationReason]:
    text = f"{question} {reason}".casefold()
    if _contains(text, ("học phí", "hoc phi", "tuition", "chi phí", "thanh toán")):
        category = TicketCategory.TUITION
    elif _contains(text, ("học bổng", "hoc bong", "scholarship", "financial aid")):
        category = TicketCategory.SCHOLARSHIP
    elif _contains(text, ("ngành", "chương trình", "curriculum", "program", "major")):
        category = TicketCategory.PROGRAM
    elif _contains(text, ("hồ sơ", "application", "tài liệu", "nộp đơn", "portal")):
        category = TicketCategory.APPLICATION
    elif _contains(text, ("lỗi", "không đăng nhập", "technical", "otp", "website")):
        category = TicketCategory.TECHNICAL
    elif _contains(text, ("tuyển sinh", "điều kiện", "admission", "xét tuyển")):
        category = TicketCategory.ADMISSIONS
    else:
        category = TicketCategory.OTHER

    escalation = normalize_escalation_reason(reason)
    if _contains(text, ("hôm nay", "ngày mai", "khẩn", "urgent", "hạn chót")):
        priority = TicketPriority.URGENT
    elif confidence is not None and confidence < 0.25:
        priority = TicketPriority.HIGH
    elif escalation in {
        EscalationReason.CONFLICTING_EVIDENCE,
        EscalationReason.OUTDATED_SOURCE,
        EscalationReason.PERSONAL_CASE,
    }:
        priority = TicketPriority.HIGH
    elif escalation == EscalationReason.USER_REQUESTED:
        priority = TicketPriority.LOW
    else:
        priority = TicketPriority.MEDIUM
    return category, priority, escalation


def build_summary(
    question: str,
    conversation: list[HandoverMessageSnapshot],
    evidence: list[HandoverEvidenceSnapshot],
    escalation: EscalationReason,
) -> str:
    user_turns = [item.content.strip() for item in conversation if item.role == "user"]
    latest_context = " | ".join(user_turns[-3:]) if user_turns else question.strip()
    latest_context = re.sub(r"\s+", " ", latest_context)[:900]
    source_note = (
        f"Có {len(evidence)} nguồn được chuyển kèm để cán bộ kiểm tra."
        if evidence
        else "Chưa có nguồn đủ chắc chắn được chuyển kèm."
    )
    return (
        f"Ứng viên cần hỗ trợ về: {latest_context}. "
        f"Lý do chuyển người: {escalation.value}. {source_note}"
    )


def build_suggested_reply(
    question: str,
    evidence: list[HandoverEvidenceSnapshot],
) -> str:
    if not evidence:
        return (
            "Chào bạn, cảm ơn bạn đã liên hệ VinUni Guide. Cán bộ đã nhận được câu hỏi của bạn: "
            f"“{question.strip()[:600]}”. Hiện chưa có đủ nguồn đã kiểm chứng để kết luận. "
            "Chúng tôi sẽ kiểm tra với đơn vị phụ trách và phản hồi lại; vui lòng không coi nội dung này là xác nhận chính thức."
        )
    source_lines = "\n".join(
        f"- {item.title}: {item.url}" for item in evidence[:3]
    )
    return (
        "Chào bạn, cảm ơn bạn đã liên hệ VinUni Guide. Cán bộ đã kiểm tra câu hỏi của bạn. "
        "Dưới đây là các nguồn chính thức liên quan để bạn đối chiếu:\n"
        f"{source_lines}\n"
        "Vui lòng cho chúng tôi biết nếu bạn cần kiểm tra trường hợp hồ sơ cụ thể. "
        "Cán bộ cần rà soát và chỉnh sửa bản nháp này trước khi gửi."
    )
