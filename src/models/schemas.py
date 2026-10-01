from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class AnswerStatus(StrEnum):
    ANSWERED = "answered"
    NEEDS_CLARIFICATION = "needs_clarification"
    HANDOVER_SUGGESTED = "handover_suggested"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class Citation(BaseModel):
    source_id: str
    title: str
    url: str
    section: str | None = None
    published_or_updated: str | None = None
    version: str | None = None
    warning: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="Câu hỏi của người dùng")
    session_id: str | None = Field(default=None, min_length=16, max_length=128)

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Tin nhắn không được để trống")
        return value


class ChatResponse(BaseModel):
    request_id: str
    session_id: str
    status: AnswerStatus
    response: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    grounded: bool
    reason_code: str
    warnings: list[str] = Field(default_factory=list)
    handover_recommended: bool = False
    cache_hit: bool = False
    latency_ms: int = Field(default=0, ge=0)


class FeedbackRating(StrEnum):
    HELPFUL = "helpful"
    UNHELPFUL = "unhelpful"


class FeedbackReason(StrEnum):
    INCORRECT = "incorrect"
    UNCLEAR = "unclear"
    MISSING_SOURCE = "missing_source"
    OUTDATED = "outdated"
    OTHER = "other"


class FeedbackRequest(BaseModel):
    request_id: str = Field(..., min_length=8, max_length=128)
    session_id: str = Field(..., min_length=16, max_length=128)
    rating: FeedbackRating
    reason: FeedbackReason | None = None


class FeedbackResponse(BaseModel):
    recorded: bool = True


class MetricBreakdown(BaseModel):
    key: str
    count: int = Field(ge=0)


class AnalyticsSummary(BaseModel):
    window_days: int = Field(ge=1, le=365)
    generated_at: datetime
    total_interactions: int = Field(ge=0)
    unique_sessions: int = Field(ge=0)
    answered: int = Field(ge=0)
    answer_rate: float = Field(ge=0.0, le=1.0)
    grounded_answer_compliance: float = Field(ge=0.0, le=1.0)
    handover_count: int = Field(ge=0)
    handover_rate: float = Field(ge=0.0, le=1.0)
    feedback_count: int = Field(ge=0)
    helpful_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    cache_hits: int = Field(ge=0)
    cache_hit_rate: float = Field(ge=0.0, le=1.0)
    average_latency_ms: float = Field(ge=0.0)
    status_breakdown: list[MetricBreakdown] = Field(default_factory=list)
    top_reason_codes: list[MetricBreakdown] = Field(default_factory=list)


class HandoverCreateRequest(BaseModel):
    session_id: str = Field(..., min_length=16, max_length=128)
    question: str = Field(..., min_length=1, max_length=2000)
    reason: str = Field(..., min_length=1, max_length=500)
    consent: bool
    contact: str | None = Field(default=None, max_length=255)
    conversation: list[HandoverMessageSnapshot] = Field(default_factory=list, max_length=50)
    evidence: list[HandoverEvidenceSnapshot] = Field(default_factory=list, max_length=30)
    ai_confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ClaimSessionRequest(BaseModel):
    session_id: str = Field(..., min_length=16, max_length=128)


class TicketStatus(StrEnum):
    NEW = "new"
    # Backward-compatible Python alias. API responses use `new`.
    WAITING = "new"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    WAITING_FOR_USER = "waiting_for_user"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketCategory(StrEnum):
    ADMISSIONS = "admissions"
    TUITION = "tuition"
    SCHOLARSHIP = "scholarship"
    PROGRAM = "program"
    APPLICATION = "application"
    TECHNICAL = "technical"
    OTHER = "other"


class TicketPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class StaffAvailability(StrEnum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"


class EscalationReason(StrEnum):
    LOW_CONFIDENCE = "low_confidence"
    MISSING_EVIDENCE = "missing_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    PERSONAL_CASE = "personal_case"
    OUTDATED_SOURCE = "outdated_source"
    USER_REQUESTED = "user_requested"
    OTHER = "other"


class HandoverMessageSnapshot(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=10000)
    created_at: datetime | None = None
    request_id: str | None = Field(default=None, max_length=128)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    grounded: bool | None = None
    reason_code: str | None = Field(default=None, max_length=128)


class HandoverEvidenceSnapshot(BaseModel):
    source_id: str = Field(..., min_length=1, max_length=255)
    title: str = Field(..., min_length=1, max_length=500)
    url: str = Field(..., min_length=1, max_length=2000)
    content_preview: str | None = Field(default=None, max_length=3000)
    retrieval_score: float | None = None
    source_category: str | None = Field(default=None, max_length=100)


class TicketResponse(BaseModel):
    ticket_id: str
    status: TicketStatus
    question: str
    reason: str
    staff_reply: str | None = None
    assigned_to: str | None = None
    created_at: datetime
    updated_at: datetime


class StaffTicketAction(BaseModel):
    staff_id: str = Field(..., min_length=2, max_length=100)


class StaffReplyRequest(StaffTicketAction):
    reply: str = Field(..., min_length=1, max_length=5000)


class StaffAssignmentRequest(StaffTicketAction):
    assigned_to: str | None = Field(default=None, min_length=2, max_length=100)
    department: str | None = Field(default=None, max_length=100)


class StaffAvailabilityRequest(BaseModel):
    availability: StaffAvailability


class AdminStaffUpsertRequest(BaseModel):
    staff_id: str = Field(..., min_length=2, max_length=100)
    display_name: str = Field(..., min_length=2, max_length=120)
    department: str = Field(..., min_length=2, max_length=100)
    specialties: list[TicketCategory] = Field(default_factory=list, max_length=7)
    availability: StaffAvailability = StaffAvailability.AVAILABLE
    active: bool = True


class AdminRoutingRuleRequest(BaseModel):
    department: str = Field(..., min_length=2, max_length=100)
    auto_assign: bool = True


class AdminTicketAssignmentRequest(BaseModel):
    assigned_to: str | None = Field(default=None, min_length=2, max_length=100)


class KnowledgeGapStatus(StrEnum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"


class KnowledgeGapUpdateRequest(BaseModel):
    status: KnowledgeGapStatus


class StaffMember(BaseModel):
    staff_id: str
    display_name: str
    department: str
    specialties: list[TicketCategory] = Field(default_factory=list)
    availability: StaffAvailability
    active: bool
    open_ticket_count: int = Field(ge=0)
    updated_at: datetime


class RoutingRule(BaseModel):
    category: TicketCategory
    department: str
    auto_assign: bool


class StaffStatusRequest(StaffTicketAction):
    status: TicketStatus


class StaffNoteRequest(StaffTicketAction):
    note: str = Field(..., min_length=1, max_length=5000)


class StaffClassificationRequest(StaffTicketAction):
    category: TicketCategory | None = None
    priority: TicketPriority | None = None


class StaffResolveRequest(StaffTicketAction):
    resolution_summary: str = Field(..., min_length=3, max_length=5000)
    resolution_type: str = Field(..., min_length=2, max_length=100)
    knowledge_gap: bool = False
    knowledge_gap_description: str | None = Field(default=None, max_length=3000)


class TicketMessage(BaseModel):
    message_id: str
    role: str
    content: str
    author_id: str | None = None
    request_id: str | None = None
    confidence: float | None = None
    grounded: bool | None = None
    reason_code: str | None = None
    created_at: datetime


class TicketEvidence(BaseModel):
    evidence_id: str
    source_id: str
    title: str
    url: str
    content_preview: str | None = None
    retrieval_score: float | None = None
    source_category: str | None = None
    created_at: datetime


class TicketNote(BaseModel):
    note_id: str
    author_id: str
    note: str
    created_at: datetime


class TicketActivity(BaseModel):
    activity_id: str
    actor_id: str
    action: str
    detail: str | None = None
    created_at: datetime


class StaffTicketResponse(TicketResponse):
    contact: str | None = None
    user_email: str | None = None
    assigned_department: str | None = None
    category: TicketCategory
    priority: TicketPriority
    escalation_reason: EscalationReason
    ai_confidence: float | None = None
    ai_summary: str | None = None
    suggested_reply: str | None = None
    resolution_summary: str | None = None
    resolution_type: str | None = None
    knowledge_gap: bool = False
    first_response_at: datetime | None = None
    last_response_at: datetime | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    email_delivery_status: str | None = None
    sla_deadline: datetime
    sla_state: str
    messages: list[TicketMessage] = Field(default_factory=list)
    evidence: list[TicketEvidence] = Field(default_factory=list)
    notes: list[TicketNote] = Field(default_factory=list)
    activities: list[TicketActivity] = Field(default_factory=list)


class StaffTicketMetrics(BaseModel):
    open_count: int = 0
    unassigned_count: int = 0
    team_queue_count: int = 0
    overdue_count: int = 0
    resolved_today: int = 0
    average_first_response_minutes: float | None = None
    by_status: list[MetricBreakdown] = Field(default_factory=list)
    by_category: list[MetricBreakdown] = Field(default_factory=list)
    by_priority: list[MetricBreakdown] = Field(default_factory=list)


class KnowledgeGapItem(BaseModel):
    gap_id: str
    ticket_id: str
    category: TicketCategory
    description: str
    status: str
    created_by: str
    created_at: datetime


class KnowledgeStatus(BaseModel):
    ready: bool
    dataset_id: str | None = None
    academic_year: str | None = None
    verified_as_of: str | None = None
    documents: int = 0
    chunks: int = 0
    sources: int = 0
    load_errors: list[str] = Field(default_factory=list)


class AuthUser(BaseModel):
    user_id: str
    email: str
    display_name: str


class AuthSessionResponse(BaseModel):
    access_token: str
    user: AuthUser


class RegisterOtpRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=254)
    display_name: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("Email không hợp lệ")
        return value


class VerifyOtpRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=254)
    code: str = Field(..., min_length=6, max_length=6)


class EmailLoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=254)
    password: str = Field(..., min_length=8, max_length=128)


class ExchangeCodeRequest(BaseModel):
    code: str = Field(..., min_length=20, max_length=200)
