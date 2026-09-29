from __future__ import annotations

import hmac
import logging
import time
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from src.agents.graph import agent
from src.config import get_settings
from src.models.schemas import (
    AnalyticsSummary,
    AnswerStatus,
    ChatRequest,
    ChatResponse,
    FeedbackRequest,
    FeedbackResponse,
    HandoverCreateRequest,
    KnowledgeStatus,
    StaffReplyRequest,
    StaffTicketAction,
    TicketResponse,
    TicketStatus,
)
from src.services.analytics import get_analytics_store
from src.services.knowledge_base import get_knowledge_base
from src.services.rate_limit import enforce_rate_limit
from src.services.response_cache import response_cache
from src.services.session import contextualize_query, session_store
from src.services.source_monitor import blocked_source_ids, monitor_report
from src.services.tickets import get_ticket_store

router = APIRouter(dependencies=[Depends(enforce_rate_limit)])
logger = logging.getLogger(__name__)

REPEATED_UNRESOLVED_REASONS = {
    "generation_failed",
    "insufficient_retrieval_evidence",
    "knowledge_base_unavailable",
    "model_insufficient_evidence",
    "official_sources_conflict",
    "unsafe_evidence_status",
    "unsupported_numeric_claim",
}


def require_staff(authorization: str | None = Header(default=None)) -> str | None:
    settings = get_settings()
    expected = settings.staff_api_token if settings.app_env != "production" else ""
    if not expected and not settings.staff_tokens:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STAFF_API_TOKEN chưa được cấu hình",
        )
    supplied = ""
    if authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:]
    if supplied:
        for staff_id, token in settings.staff_tokens.items():
            if token and hmac.compare_digest(supplied.encode(), token.encode()):
                return staff_id
        if expected and hmac.compare_digest(supplied.encode(), expected.encode()):
            return None
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Không có quyền truy cập")


def check_staff_identity(requested: str, authenticated: str | None) -> None:
    if authenticated is not None and requested != authenticated:
        raise HTTPException(status_code=403, detail="Mã cán bộ không khớp tài khoản đã xác thực")


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Accuracy-first chat: answer only when retrieved official evidence is sufficient."""
    started_at = time.perf_counter()
    settings = get_settings()
    session = session_store.get_or_create(request.session_id)
    request_id = str(uuid.uuid4())
    session_context = session_store.context(session.session_id)
    knowledge = get_knowledge_base()
    cache_namespace = "|".join(str(value) for value in (
        knowledge.fingerprint, settings.model_name, bool(settings.openai_api_key), settings.require_llm_for_answers,
        settings.retrieval_min_score, settings.retrieval_top_k, settings.knowledge_max_age_days,
        datetime.now(UTC).date().isoformat(), "pipeline-v2",
        sorted(blocked_source_ids()),
    ))
    cache_hit = False

    try:
        result = None
        if settings.response_cache_enabled and not session_context and knowledge.ready:
            result = response_cache.get(request.message, cache_namespace)
            cache_hit = result is not None
        if result is None:
            result = await agent.ainvoke(
                {
                    "query": request.message,
                    "session_context": session_context,
                }
            )
            if (
                settings.response_cache_enabled
                and not session_context
                and result.get("status") == AnswerStatus.ANSWERED.value
                and result.get("grounded")
            ):
                response_cache.set(request.message, cache_namespace, result)
    except Exception:
        logger.error("Safe chat pipeline failed for request_id=%s", request_id)
        raise HTTPException(status_code=503, detail="Không thể xử lý câu hỏi an toàn lúc này") from None

    reason_code = str(result.get("reason_code", "unknown_failure"))
    if reason_code in REPEATED_UNRESOLVED_REASONS and session_store.get_unresolved_streak(session.session_id) >= 1:
        result = {
            **result,
            "status": AnswerStatus.HANDOVER_SUGGESTED.value,
            "response": (
                "Hai lượt liên tiếp chưa tìm được căn cứ đủ chắc chắn trong dữ liệu đã kiểm chứng. "
                "Để tránh trả lời vòng vo hoặc suy đoán, bạn nên chuyển câu hỏi này cho cán bộ tuyển sinh."
            ),
            "reason_code": "repeated_unresolved",
            "confidence": 0.0,
            "grounded": False,
            "handover_recommended": True,
        }

    response_text = result.get(
        "response",
        "Tôi chưa có đủ căn cứ để trả lời chính xác. Vui lòng thử lại hoặc chuyển cán bộ phụ trách.",
    )
    response = ChatResponse(
        request_id=request_id,
        session_id=session.session_id,
        status=AnswerStatus(result.get("status", AnswerStatus.INSUFFICIENT_EVIDENCE.value)),
        response=response_text,
        citations=result.get("citations", []),
        confidence=float(result.get("confidence", 0.0)),
        grounded=bool(result.get("grounded", False)),
        reason_code=result.get("reason_code", "unknown_failure"),
        warnings=result.get("warnings", []),
        handover_recommended=bool(result.get("handover_recommended", False)),
        cache_hit=cache_hit,
        latency_ms=max(0, round((time.perf_counter() - started_at) * 1000)),
    )

    # Never retain a message after the privacy guardrail detects personal data.
    if response.reason_code not in {"sensitive_data_detected", "prompt_injection_blocked"}:
        resolved = contextualize_query(request.message, session_context)
        session_store.add_turn(session.session_id, resolved if response.grounded else request.message, response_text)
    session_store.record_outcome(
        session.session_id,
        answered=response.status == AnswerStatus.ANSWERED,
        unresolved=reason_code in REPEATED_UNRESOLVED_REASONS,
    )
    try:
        get_analytics_store().record_interaction(
            request_id=request_id,
            session_id=session.session_id,
            intent=str(result.get("intent", "unknown")),
            status=response.status.value,
            reason_code=response.reason_code,
            grounded=response.grounded,
            citation_count=len(response.citations),
            cache_hit=cache_hit,
            latency_ms=response.latency_ms,
        )
    except Exception:
        # Metrics must never make the user-facing answer unavailable.
        logger.exception("Could not record interaction metrics for request_id=%s", request_id)
    return response


@router.post("/feedback", response_model=FeedbackResponse)
async def record_feedback(request: FeedbackRequest) -> FeedbackResponse:
    try:
        get_analytics_store().record_feedback(
            request_id=request.request_id,
            session_id=request.session_id,
            rating=request.rating,
            reason=request.reason.value if request.reason else None,
        )
    except KeyError:
        # Same response prevents attaching feedback to another anonymous session.
        raise HTTPException(status_code=404, detail="Không tìm thấy lượt trả lời trong phiên này") from None
    return FeedbackResponse()


@router.get("/knowledge/status", response_model=KnowledgeStatus)
async def knowledge_status() -> KnowledgeStatus:
    knowledge = get_knowledge_base()
    return KnowledgeStatus(
        ready=knowledge.ready,
        dataset_id=knowledge.dataset_id,
        academic_year=knowledge.academic_year,
        verified_as_of=knowledge.verified_as_of,
        documents=knowledge.document_count,
        chunks=len(knowledge.chunks),
        sources=len(knowledge.sources),
        load_errors=knowledge.load_errors,
    )


@router.delete("/session/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def clear_session(session_id: str) -> None:
    """Forget conversation turns without invalidating owned handover tickets."""
    session_store.clear(session_id)


@router.post("/handover", response_model=TicketResponse, status_code=201)
async def create_handover(request: HandoverCreateRequest) -> TicketResponse:
    if not request.consent:
        raise HTTPException(status_code=400, detail="Cần sự đồng ý trước khi chuyển nội dung cho cán bộ")
    return get_ticket_store().create(
        session_id=request.session_id,
        question=request.question,
        reason=request.reason,
        contact=request.contact,
    )


@router.get("/handover/{ticket_id}", response_model=TicketResponse)
async def get_handover(
    ticket_id: str,
    session_id: str = Header(..., alias="X-Session-ID"),
) -> TicketResponse:
    try:
        return get_ticket_store().get_for_session(ticket_id, session_id)
    except KeyError:
        # Same response for missing and unauthorized tickets prevents ID probing.
        raise HTTPException(status_code=404, detail="Không tìm thấy ticket") from None


@router.get("/staff/tickets", response_model=list[TicketResponse], dependencies=[Depends(require_staff)])
async def list_tickets(
    ticket_status: TicketStatus | None = Query(default=None, alias="status"),
) -> list[TicketResponse]:
    return get_ticket_store().list_for_staff(ticket_status)


@router.get(
    "/staff/analytics",
    response_model=AnalyticsSummary,
    dependencies=[Depends(require_staff)],
)
async def staff_analytics(days: int = Query(default=30, ge=1, le=365)) -> AnalyticsSummary:
    return get_analytics_store().summary(days=days)


@router.get("/staff/source-monitor", dependencies=[Depends(require_staff)])
async def source_monitor_status() -> dict:
    return monitor_report()


@router.post(
    "/staff/tickets/{ticket_id}/claim",
    response_model=TicketResponse,
    dependencies=[Depends(require_staff)],
)
async def claim_ticket(ticket_id: str, request: StaffTicketAction, identity: str | None = Depends(require_staff)) -> TicketResponse:
    check_staff_identity(request.staff_id, identity)
    try:
        return get_ticket_store().claim(ticket_id, request.staff_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Không tìm thấy ticket") from None
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.post(
    "/staff/tickets/{ticket_id}/reply",
    response_model=TicketResponse,
    dependencies=[Depends(require_staff)],
)
async def reply_ticket(ticket_id: str, request: StaffReplyRequest, identity: str | None = Depends(require_staff)) -> TicketResponse:
    check_staff_identity(request.staff_id, identity)
    try:
        return get_ticket_store().reply(ticket_id, request.staff_id, request.reply)
    except KeyError:
        raise HTTPException(status_code=404, detail="Không tìm thấy ticket") from None
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.post(
    "/staff/tickets/{ticket_id}/resolve",
    response_model=TicketResponse,
    dependencies=[Depends(require_staff)],
)
async def resolve_ticket(ticket_id: str, request: StaffTicketAction, identity: str | None = Depends(require_staff)) -> TicketResponse:
    check_staff_identity(request.staff_id, identity)
    try:
        return get_ticket_store().resolve(ticket_id, request.staff_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Không tìm thấy ticket") from None
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.get("/status")
async def agent_status():
    knowledge = get_knowledge_base()
    return {
        "status": "ready" if knowledge.ready else "degraded",
        "agent": "VinUni Accuracy-First RAG v1",
        "knowledge_chunks": len(knowledge.chunks),
        "official_sources": len(knowledge.sources),
    }
