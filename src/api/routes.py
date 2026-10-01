from __future__ import annotations

import hmac
import logging
import secrets
import smtplib
import time
import uuid
from datetime import UTC, datetime
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from src.agents.graph import agent
from src.config import get_settings
from src.models.schemas import (
    AnalyticsSummary,
    AnswerStatus,
    AuthSessionResponse,
    AuthUser,
    ChatRequest,
    ChatResponse,
    EmailLoginRequest,
    ExchangeCodeRequest,
    FeedbackRequest,
    FeedbackResponse,
    HandoverCreateRequest,
    KnowledgeGapItem,
    KnowledgeStatus,
    RegisterOtpRequest,
    StaffAssignmentRequest,
    StaffClassificationRequest,
    StaffNoteRequest,
    StaffReplyRequest,
    StaffResolveRequest,
    StaffStatusRequest,
    StaffTicketAction,
    StaffTicketMetrics,
    StaffTicketResponse,
    TicketCategory,
    TicketPriority,
    TicketResponse,
    TicketStatus,
    VerifyOtpRequest,
)
from src.services.analytics import get_analytics_store
from src.services.auth import (
    get_auth_store,
    hash_password,
    send_login_notification_email,
    send_otp_email,
    send_transactional_email,
)
from src.services.knowledge_base import get_knowledge_base
from src.services.rate_limit import enforce_rate_limit
from src.services.response_cache import response_cache
from src.services.session import contextualize_query, session_store
from src.services.source_monitor import blocked_source_ids, monitor_report
from src.services.tickets import get_ticket_store

router = APIRouter(dependencies=[Depends(enforce_rate_limit)])
logger = logging.getLogger(__name__)


def _auth_user_response(user: dict[str, str], token: str) -> AuthSessionResponse:
    return AuthSessionResponse(
        access_token=token,
        user=AuthUser(user_id=user["user_id"], email=user["email"], display_name=user["display_name"]),
    )


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Cần đăng nhập")
    return authorization[7:].strip()


@router.get("/auth/google/start", include_in_schema=False)
async def google_start() -> RedirectResponse:
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=503, detail="Google OAuth chưa được cấu hình trên backend")
    state = get_auth_store().save_oauth_state()
    query = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "online",
            # Always show account selection and the consent step so users know
            # exactly which profile/email they are sharing with this app.
            "prompt": "consent select_account",
            "include_granted_scopes": "true",
            "state": state,
        }
    )
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{query}")


@router.get("/auth/google/callback", include_in_schema=False)
async def google_callback(code: str | None = None, state: str | None = None, error: str | None = None) -> RedirectResponse:
    settings = get_settings()
    if error or not code or not state or not get_auth_store().consume_oauth_state(state):
        return RedirectResponse(f"{settings.frontend_url.rstrip('/')}/auth?error=google_login_failed")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_response.raise_for_status()
            access_token = token_response.json().get("access_token")
            if not access_token:
                raise ValueError("Google không trả access token")
            profile_response = await client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            profile_response.raise_for_status()
            profile = profile_response.json()
        email = str(profile.get("email", "")).strip().lower()
        if not email or profile.get("email_verified") is not True or not profile.get("sub"):
            raise ValueError("Google account chưa xác minh email")
        user = get_auth_store().create_or_update_google_user(email, str(profile.get("name") or email), str(profile["sub"]))
        try:
            send_login_notification_email(user["email"], user["display_name"])
        except (RuntimeError, OSError, smtplib.SMTPException):
            # OAuth login must remain available if the notification provider is
            # temporarily unavailable. The failure is visible in Railway logs.
            logger.warning("Could not send Google login notification to %s", email, exc_info=True)
        exchange_code = get_auth_store().save_exchange_code(user["user_id"])
        return RedirectResponse(f"{settings.frontend_url.rstrip('/')}/auth/callback?code={exchange_code}")
    except (httpx.HTTPError, ValueError, KeyError):
        logger.exception("Google OAuth callback failed")
        return RedirectResponse(f"{settings.frontend_url.rstrip('/')}/auth?error=google_login_failed")


@router.post("/auth/register/request-otp")
async def request_register_otp(request: RegisterOtpRequest) -> dict[str, str]:
    store = get_auth_store()
    if store.email_exists(request.email):
        raise HTTPException(status_code=409, detail="Email đã được đăng ký. Hãy đăng nhập.")
    code = f"{secrets.randbelow(1_000_000):06d}"
    store.save_otp(request.email, request.display_name.strip(), hash_password(request.password), code)
    try:
        send_otp_email(request.email, code)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    except smtplib.SMTPAuthenticationError:
        logger.exception("SMTP authentication failed while sending OTP")
        raise HTTPException(
            status_code=503,
            detail="Gmail từ chối xác thực SMTP. Hãy kiểm tra SMTP_USERNAME và dùng Google App Password, không dùng mật khẩu Gmail thường.",
        ) from None
    except smtplib.SMTPConnectError:
        logger.exception("SMTP connection failed while sending OTP")
        raise HTTPException(
            status_code=503,
            detail="Không kết nối được máy chủ Gmail SMTP. Hãy kiểm tra SMTP_HOST=smtp.gmail.com và SMTP_PORT=587.",
        ) from None
    except (OSError, TimeoutError):
        logger.exception("SMTP network failure while sending OTP")
        raise HTTPException(
            status_code=503,
            detail="Không thể kết nối Gmail SMTP từ backend. Hãy kiểm tra SMTP_HOST, SMTP_PORT và thử lại.",
        ) from None
    except smtplib.SMTPException:
        logger.exception("Could not send registration OTP")
        raise HTTPException(
            status_code=503,
            detail="Gmail SMTP không gửi được OTP. Kiểm tra lại tài khoản gửi và Google App Password.",
        ) from None
    return {"message": "Mã OTP đã được gửi tới email của bạn", "email": request.email}


@router.post("/auth/register/verify-otp", response_model=AuthSessionResponse)
async def verify_register_otp(request: VerifyOtpRequest) -> AuthSessionResponse:
    user = get_auth_store().verify_otp(request.email.strip().lower(), request.code)
    if user is None:
        raise HTTPException(status_code=400, detail="OTP không đúng, đã hết hạn hoặc vượt quá số lần thử")
    return _auth_user_response(user, get_auth_store().create_session(user["user_id"]))


@router.post("/auth/login", response_model=AuthSessionResponse)
async def email_login(request: EmailLoginRequest) -> AuthSessionResponse:
    email = request.email.strip().lower()
    store = get_auth_store()
    user = store.password_user(email, request.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không đúng")
    return _auth_user_response(user, store.create_session(user["user_id"]))


@router.post("/auth/google/exchange", response_model=AuthSessionResponse)
async def exchange_google_code(request: ExchangeCodeRequest) -> AuthSessionResponse:
    store = get_auth_store()
    user = store.consume_exchange_code(request.code)
    if user is None:
        raise HTTPException(status_code=400, detail="Mã đăng nhập Google không hợp lệ hoặc đã hết hạn")
    return _auth_user_response(user, store.create_session(user["user_id"]))


@router.get("/auth/me", response_model=AuthUser)
async def current_auth_user(authorization: str | None = Header(default=None)) -> AuthUser:
    user = get_auth_store().user_from_session(_bearer_token(authorization))
    if user is None:
        raise HTTPException(status_code=401, detail="Phiên đăng nhập đã hết hạn")
    return AuthUser(**user)


@router.post("/auth/logout", status_code=204)
async def logout(authorization: str | None = Header(default=None)) -> None:
    get_auth_store().revoke_session(_bearer_token(authorization))

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
        conversation=request.conversation,
        evidence=request.evidence,
        ai_confidence=request.ai_confidence,
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


@router.get("/staff/tickets", response_model=list[StaffTicketResponse])
async def list_tickets(
    ticket_status: TicketStatus | None = Query(default=None, alias="status"),
    category: TicketCategory | None = Query(default=None),
    priority: TicketPriority | None = Query(default=None),
    assigned_to: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    sort: str = Query(default="oldest", pattern="^(oldest|newest|priority)$"),
    _identity: str | None = Depends(require_staff),
) -> list[StaffTicketResponse]:
    return get_ticket_store().list_for_staff(
        ticket_status,
        category=category,
        priority=priority,
        assigned_to=assigned_to,
        search=search,
        sort=sort,
    )


@router.get("/staff/tickets/metrics", response_model=StaffTicketMetrics)
async def ticket_metrics(_identity: str | None = Depends(require_staff)) -> StaffTicketMetrics:
    return get_ticket_store().metrics()


@router.get("/staff/knowledge-gaps", response_model=list[KnowledgeGapItem])
async def knowledge_gaps(_identity: str | None = Depends(require_staff)) -> list[KnowledgeGapItem]:
    return get_ticket_store().list_knowledge_gaps()


@router.get("/staff/tickets/{ticket_id}", response_model=StaffTicketResponse)
async def get_staff_ticket(
    ticket_id: str,
    _identity: str | None = Depends(require_staff),
) -> StaffTicketResponse:
    try:
        return get_ticket_store().get_for_staff(ticket_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Không tìm thấy ticket") from None


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
    response_model=StaffTicketResponse,
)
async def claim_ticket(ticket_id: str, request: StaffTicketAction, identity: str | None = Depends(require_staff)) -> StaffTicketResponse:
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
    response_model=StaffTicketResponse,
)
async def reply_ticket(ticket_id: str, request: StaffReplyRequest, identity: str | None = Depends(require_staff)) -> StaffTicketResponse:
    check_staff_identity(request.staff_id, identity)
    try:
        store = get_ticket_store()
        updated = store.reply(ticket_id, request.staff_id, request.reply)
        if updated.user_email:
            try:
                send_transactional_email(
                    updated.user_email,
                    f"Phản hồi từ VinUni Guide · {updated.ticket_id}",
                    f"Xin chào,\n\nCán bộ tuyển sinh đã phản hồi yêu cầu {updated.ticket_id}:\n\n"
                    f"{request.reply.strip()}\n\nBạn có thể tiếp tục theo dõi yêu cầu trên VinUni Guide.",
                )
            except Exception as exc:
                logger.exception("Could not deliver staff reply for ticket_id=%s", ticket_id)
                return store.record_email_delivery(ticket_id, delivered=False, detail=str(exc)[:500])
            return store.record_email_delivery(ticket_id, delivered=True)
        return store.record_email_delivery(
            ticket_id,
            delivered=False,
            detail="Người dùng chưa cung cấp email",
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Không tìm thấy ticket") from None
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.post(
    "/staff/tickets/{ticket_id}/resolve",
    response_model=StaffTicketResponse,
)
async def resolve_ticket(
    ticket_id: str,
    request: StaffResolveRequest,
    identity: str | None = Depends(require_staff),
) -> StaffTicketResponse:
    check_staff_identity(request.staff_id, identity)
    try:
        return get_ticket_store().resolve(
            ticket_id,
            request.staff_id,
            request.resolution_summary,
            request.resolution_type,
            request.knowledge_gap,
            request.knowledge_gap_description,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Không tìm thấy ticket") from None
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.post("/staff/tickets/{ticket_id}/assign", response_model=StaffTicketResponse)
async def assign_ticket(
    ticket_id: str,
    request: StaffAssignmentRequest,
    identity: str | None = Depends(require_staff),
) -> StaffTicketResponse:
    check_staff_identity(request.staff_id, identity)
    try:
        return get_ticket_store().assign(
            ticket_id, request.staff_id, request.assigned_to, request.department
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Không tìm thấy ticket") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.post("/staff/tickets/{ticket_id}/status", response_model=StaffTicketResponse)
async def change_ticket_status(
    ticket_id: str,
    request: StaffStatusRequest,
    identity: str | None = Depends(require_staff),
) -> StaffTicketResponse:
    check_staff_identity(request.staff_id, identity)
    try:
        return get_ticket_store().set_status(ticket_id, request.staff_id, request.status)
    except KeyError:
        raise HTTPException(status_code=404, detail="Không tìm thấy ticket") from None
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.post("/staff/tickets/{ticket_id}/classification", response_model=StaffTicketResponse)
async def classify_ticket(
    ticket_id: str,
    request: StaffClassificationRequest,
    identity: str | None = Depends(require_staff),
) -> StaffTicketResponse:
    check_staff_identity(request.staff_id, identity)
    try:
        return get_ticket_store().update_classification(
            ticket_id, request.staff_id, request.category, request.priority
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Không tìm thấy ticket") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.post("/staff/tickets/{ticket_id}/notes", response_model=StaffTicketResponse)
async def add_ticket_note(
    ticket_id: str,
    request: StaffNoteRequest,
    identity: str | None = Depends(require_staff),
) -> StaffTicketResponse:
    check_staff_identity(request.staff_id, identity)
    try:
        return get_ticket_store().add_note(ticket_id, request.staff_id, request.note)
    except KeyError:
        raise HTTPException(status_code=404, detail="Không tìm thấy ticket") from None


@router.post("/staff/tickets/{ticket_id}/regenerate-ai", response_model=StaffTicketResponse)
async def regenerate_ticket_ai(
    ticket_id: str,
    request: StaffTicketAction,
    identity: str | None = Depends(require_staff),
) -> StaffTicketResponse:
    check_staff_identity(request.staff_id, identity)
    try:
        return get_ticket_store().regenerate_ai(ticket_id, request.staff_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Không tìm thấy ticket") from None


@router.post("/staff/tickets/{ticket_id}/close", response_model=StaffTicketResponse)
async def close_ticket(
    ticket_id: str,
    request: StaffTicketAction,
    identity: str | None = Depends(require_staff),
) -> StaffTicketResponse:
    check_staff_identity(request.staff_id, identity)
    try:
        return get_ticket_store().close(ticket_id, request.staff_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Không tìm thấy ticket") from None
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
