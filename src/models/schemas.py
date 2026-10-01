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


class TicketStatus(StrEnum):
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


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
