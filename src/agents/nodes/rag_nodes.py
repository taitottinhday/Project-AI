from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime

from src.agents.state import AgentState
from src.config import get_settings
from src.models.schemas import AnswerStatus, Citation
from src.services.answer_generator import generate_grounded_answer
from src.services.grounding import retrieval_confidence, validate_grounded_answer
from src.services.intent import Intent, classify_query, is_program_list_query
from src.services.knowledge_base import SOURCE_PRIORITY, SearchHit, get_knowledge_base, normalize_text
from src.services.query_understanding import normalize_query
from src.services.session import contextualize_query
from src.services.source_monitor import blocked_source_ids

INTENT_DOCUMENT_PREFIXES = {
    Intent.PROGRAMS: ("programs/", "academics/vinuni_undergraduate_minors"),
    # coverage/ and quality/ are internal inventories, not applicant-facing
    # evidence. They are audited by the coverage script but must never support
    # a chatbot answer in place of the canonical policy/program data.
    Intent.ADMISSIONS: ("admissions/", "programs/"),
    Intent.TUITION: ("tuition/", "financial_aid/", "programs/"),
    Intent.FINANCIAL_AID: ("financial_aid/", "tuition/", "governance/", "admissions/"),
    Intent.ACADEMIC_RULES: ("academics/",),
    Intent.STUDENT_LIFE: ("student_life/", "financial_aid/"),
    Intent.INTERNATIONAL: ("international/", "admissions/", "academics/"),
    Intent.EXCHANGE_INTERNSHIP: ("international/", "academics/", "financial_aid/"),
    Intent.GOVERNANCE: ("governance/", "academics/"),
}


def _fail_closed_response(reason_code: str) -> str:
    messages = {
        "knowledge_base_unavailable": "Kho dữ liệu chính thức hiện chưa sẵn sàng. Tôi chưa thể trả lời an toàn.",
        "insufficient_retrieval_evidence": (
            "Tôi chưa tìm thấy đủ căn cứ trong bộ dữ liệu VinUni đã kiểm chứng để trả lời chính xác câu hỏi này. "
            "Bạn có thể nêu rõ chương trình, năm học hoặc vấn đề cần hỏi; nếu đây là trường hợp cá nhân, hãy chuyển cho cán bộ phụ trách."
        ),
        "model_insufficient_evidence": (
            "Các nguồn truy xuất chưa đủ để tạo câu trả lời chắc chắn. Tôi sẽ không suy đoán; bạn nên hỏi rõ hơn hoặc chuyển cán bộ phụ trách."
        ),
        "official_sources_conflict": (
            "Các nguồn chính thức liên quan đang có thông tin chưa thống nhất. Tôi chưa thể chọn một kết quả chắc chắn; cần cán bộ có thẩm quyền xác nhận."
        ),
        "unsupported_numeric_claim": (
            "Câu trả lời dự thảo có con số không được chứng minh trực tiếp bởi nguồn truy xuất nên đã bị chặn. Vui lòng chuyển cán bộ để xác nhận."
        ),
        "generation_failed": "Không thể tạo câu trả lời đã kiểm chứng ở thời điểm này. Tôi sẽ không trả lời dựa trên suy đoán.",
    }
    return messages.get(reason_code, messages["generation_failed"])


async def classify_node(state: AgentState) -> dict:
    query = state.get("query", "")
    session_context = state.get("session_context", "")
    retrieval_query = contextualize_query(query, session_context)
    decision = classify_query(query, has_session_context=retrieval_query != query)
    if retrieval_query != query and not decision.message:
        decision = classify_query(retrieval_query, has_session_context=True)
    if decision.message:
        status = AnswerStatus.HANDOVER_SUGGESTED if decision.requires_handover else AnswerStatus.NEEDS_CLARIFICATION
        return {
            "intent": decision.intent.value,
            "status": status.value,
            "response": decision.message,
            "reason_code": decision.reason_code,
            "grounded": False,
            "confidence": 0.0,
            "citations": [],
            "warnings": [],
            "handover_recommended": decision.requires_handover,
            "short_circuit": True,
            "retrieval_query": retrieval_query,
        }
    if decision.intent == Intent.UNKNOWN:
        return {
            "intent": decision.intent.value,
            "status": AnswerStatus.INSUFFICIENT_EVIDENCE.value,
            "response": (
                "Tôi chỉ trả lời các câu hỏi có căn cứ trong bộ dữ liệu tuyển sinh, "
                "chương trình, học phí, học bổng, quy định học vụ và đời sống sinh viên VinUni. "
                "Vui lòng nêu rõ chủ đề VinUni bạn muốn tra cứu."
            ),
            "reason_code": "out_of_scope_or_unknown_intent",
            "grounded": False,
            "confidence": 0.0,
            "citations": [],
            "warnings": [],
            "handover_recommended": False,
            "short_circuit": True,
            "retrieval_query": retrieval_query,
        }
    return {
        "intent": decision.intent.value,
        "retrieval_query": retrieval_query,
        "short_circuit": False,
    }


async def retrieve_node(state: AgentState) -> dict:
    settings = get_settings()
    knowledge = get_knowledge_base()
    if not knowledge.ready:
        reason = "knowledge_base_unavailable"
        return {
            "status": AnswerStatus.INSUFFICIENT_EVIDENCE.value,
            "response": _fail_closed_response(reason),
            "reason_code": reason,
            "confidence": 0.0,
            "grounded": False,
            "citations": [],
            "warnings": knowledge.load_errors,
            "handover_recommended": True,
            "short_circuit": True,
        }

    try:
        age = (datetime.now(UTC).date() - date.fromisoformat(knowledge.verified_as_of or "")).days
    except ValueError:
        age = settings.knowledge_max_age_days + 1
    if age > settings.knowledge_max_age_days or age < 0:
        return {
            "status": AnswerStatus.HANDOVER_SUGGESTED.value, "reason_code": "knowledge_review_overdue",
            "response": "Kho dữ liệu đã đến hạn kiểm tra lại nguồn hoặc thiếu ngày kiểm chứng hợp lệ. Cần cán bộ xác nhận trước khi dùng các số liệu/chính sách này.",
            "confidence": 0.0, "grounded": False, "citations": [], "warnings": [],
            "handover_recommended": True, "short_circuit": True,
        }
    query = normalize_query(state.get("retrieval_query", state.get("query", "")))
    normalized_query = normalize_text(query)
    intent = Intent(state.get("intent", Intent.UNKNOWN.value))
    # The canonical VinUni dataset is intentionally small. Search every chunk
    # before intent/topic reranking so an exact, low-frequency policy field
    # cannot disappear behind several broad "học phí" matches. The final
    # context remains capped by ``retrieval_top_k`` below.
    candidates = knowledge.search(query, top_k=len(knowledge.chunks))
    prefixes = INTENT_DOCUMENT_PREFIXES.get(intent)
    if prefixes:
        relevant = [hit for hit in candidates if hit.chunk.document.startswith(prefixes)]
        if relevant:
            candidates = relevant

    def boost(hit: SearchHit) -> float:
        value = hit.score
        if intent == Intent.PROGRAMS and hit.chunk.document.startswith("programs/"):
            value *= 1.8
        if intent == Intent.PROGRAMS and "minor" in normalized_query:
            # "Minor Psychology" must not be answered with the undergraduate
            # Psychology major simply because both share a name.
            if hit.chunk.document.startswith("academics/vinuni_undergraduate_minors"):
                value *= 2.4
            elif hit.chunk.document.startswith("programs/"):
                value *= 0.35
        elif intent == Intent.ADMISSIONS and hit.chunk.document.startswith("admissions/"):
            value *= 1.5
            section = normalize_text(hit.chunk.section)
            if any(term in normalized_query for term in ("han nop", "deadline")) and section.startswith(
                "application rounds"
            ):
                value *= 3.0
            if any(term in normalized_query for term in ("quy trinh", "nop ho so")) and section in {
                "selection model",
                "application checklist",
            }:
                value *= 3.0
            if any(term in normalized_query for term in ("lien he", "contact")) and section == "contact":
                value *= 8.0
        elif intent == Intent.TUITION and hit.chunk.document.startswith("tuition/"):
            value *= 1.55
            section = normalize_text(hit.chunk.section)
            asks_included_items = (
                "includes" in normalized_query
                or (
                    "bao gom" in normalized_query
                    and "ho tro" not in normalized_query
                    and any(term in normalized_query for term in ("nhung gi", "dich vu", "quyen loi"))
                )
            )
            if asks_included_items and section == "tuition includes":
                value *= 8.0
            if any(term in normalized_query for term in ("khong bao gom", "exclusions")) and section == "important exclusions":
                value *= 8.0
            if any(term in normalized_query for term in ("thanh toan", "payment")) and section == "payment":
                value *= 8.0
            if "founder educational development grant" in normalized_query and section == "founder educational development grant":
                value *= 8.0
            if any(term in normalized_query for term in ("theo tin chi", "per credit")) and section == "per credit rate applies when":
                value *= 8.0
            if "bao nhieu" in normalized_query or "muc hoc phi" in normalized_query:
                if hit.chunk.section.startswith("listed tuition"):
                    value *= 2.2
                elif hit.chunk.section in {"important exclusions", "per credit rate applies when"}:
                    value *= 0.55
        elif intent == Intent.FINANCIAL_AID and hit.chunk.document.startswith("financial_aid/"):
            value *= 1.45
            section = normalize_text(hit.chunk.section)
            if "hoc bong" in normalized_query and hit.chunk.section == "scholarships":
                value *= 3.5
            if any(term in normalized_query for term in ("khoan vay", "student loan")) and section == "student loan":
                value *= 8.0
            if any(term in normalized_query for term in ("uu dai gia dinh", "cuu sinh vien", "discount combination")) and section == "discount combination rules":
                value *= 8.0
            if any(term in normalized_query for term in ("thu vien", "library")) and section == "library fees":
                value *= 8.0
            if any(term in normalized_query for term in ("hoan hoc phi", "refund")) and section == "refund policy":
                value *= 8.0
        elif intent == Intent.FINANCIAL_AID and hit.chunk.document.startswith("tuition/"):
            value *= 1.2
            if "founder educational development grant" in normalized_query and normalize_text(hit.chunk.section) == "founder educational development grant":
                value *= 8.0
        elif intent == Intent.TUITION and hit.chunk.document.startswith("financial_aid/"):
            value *= 1.2
            section = normalize_text(hit.chunk.section)
            if any(term in normalized_query for term in ("hoan hoc phi", "refund")) and section == "refund policy":
                value *= 8.0
        elif intent == Intent.ACADEMIC_RULES and hit.chunk.document.startswith("academics/"):
            value *= 1.4
            section = normalize_text(hit.chunk.section)
            if any(term in normalized_query for term in ("canh bao", "probation", "academic warning")) and "academic warning" in section:
                value *= 3.0
            if any(term in normalized_query for term in ("diem chu", "letter grade", "quy doi diem", "grade conversion")) and "letter grades" in section:
                value *= 8.0
            academic_section_cues = {
                "academic regulations > version": ("phien ban", "version"),
                "academic regulations > effective or last updated": ("hieu luc", "cap nhat", "effective"),
                "academic regulations > applies to": ("ap dung cho ai", "doi tuong", "applies to"),
                "academic regulations > language of instruction": ("ngon ngu giang day", "language of instruction"),
                "academic regulations > academic year structure": ("cau truc nam hoc", "hoc ky", "academic year structure"),
                "academic regulations > maximum candidature": ("thoi gian hoc toi da", "maximum candidature"),
                "academic regulations > deans list": ("deans list", "dean s list", "danh sach dean"),
                "academic regulations > double degree": ("bang kep", "double degree"),
                "academic regulations > grading notes": ("quy tac diem", "lam tron gpa", "grading notes"),
                "grade appeal": ("phuc khao", "grade appeal"),
                "leave withdrawal and return": ("bao luu", "xin nghi hoc", "leave withdrawal"),
            }
            if any(section == target and any(term in normalized_query for term in cues)
                   for target, cues in academic_section_cues.items()):
                value *= 8.0
            if "phuc khao" in normalized_query and section == "grade appeal":
                value *= 3.0
        elif intent == Intent.STUDENT_LIFE and hit.chunk.document.startswith("student_life/"):
            value *= 1.5
            if any(term in normalized_query for term in ("academic accommodation", "dieu chinh hoc tap")) and normalize_text(hit.chunk.section) == "academic accommodation":
                value *= 8.0
        elif intent == Intent.STUDENT_LIFE and hit.chunk.document.startswith("financial_aid/"):
            if any(term in normalized_query for term in ("ky tuc xa", "noi tru", "dorm")):
                if hit.chunk.section == "dormitory":
                    value *= 5.0
        elif intent in {Intent.INTERNATIONAL, Intent.EXCHANGE_INTERNSHIP} and hit.chunk.document.startswith(
            "international/"
        ):
            value *= 1.55
            section = normalize_text(hit.chunk.section)
            if intent == Intent.INTERNATIONAL and "visa" in normalized_query and section.startswith("study visa"):
                value *= 3.0
            if (
                intent == Intent.EXCHANGE_INTERNSHIP
                and any(term in normalized_query for term in ("trao doi", "exchange"))
                and section == "outbound exchange"
            ):
                value *= 3.0
            if intent == Intent.EXCHANGE_INTERNSHIP and any(term in normalized_query for term in ("thuc tap", "internship")) and section == "internships":
                value *= 8.0
        elif intent == Intent.GOVERNANCE and hit.chunk.document.startswith("governance/"):
            value *= 1.5
            section = normalize_text(hit.chunk.section)
            if any(term in normalized_query for term in ("quy tac ung xu", "student code of conduct")) and section == "student code of conduct":
                value *= 8.0
            if any(term in normalized_query for term in ("thong tin noi bo", "noi bo", "public vs internal")) and section == "public vs internal information":
                value *= 8.0
        if intent == Intent.ADMISSIONS and "chi tieu" in normalized_query:
            if hit.chunk.document.startswith("coverage/") and "admission quotas" in normalize_text(hit.chunk.section):
                value *= 5.0
        return value

    reranked = [SearchHit(chunk=hit.chunk, score=round(boost(hit), 4)) for hit in candidates]
    reranked.sort(key=lambda item: item.score, reverse=True)

    asks_letter_grade_scale = any(
        term in normalized_query for term in ("diem chu", "letter grade", "quy doi diem", "grade conversion")
    )
    if is_program_list_query(query):
        # Field-level conflict chunks (for example a disputed program code) are
        # deliberately deeper than the top-level program record. They must not
        # turn a safe list of confirmed program names into an unsafe answer.
        program_hits = [
            hit
            for hit in reranked
            if hit.chunk.section.startswith("programs >") and hit.chunk.section.count(" > ") == 1
        ]
        hits = program_hits[:12]
    elif asks_letter_grade_scale:
        # The grade scale is a table split into one chunk per grade. Return the
        # complete table (12 rows) rather than silently answering with the
        # first few grades only.
        hits = [
            hit
            for hit in reranked
            if "academic regulations > letter grades >" in hit.chunk.section
        ][:12]
    else:
        hits = reranked[: settings.retrieval_top_k]

    if not hits or hits[0].score < settings.retrieval_min_score:
        reason = "insufficient_retrieval_evidence"
        return {
            "hits": hits,
            "status": AnswerStatus.INSUFFICIENT_EVIDENCE.value,
            "response": _fail_closed_response(reason),
            "reason_code": reason,
            "confidence": 0.0,
            "grounded": False,
            "citations": [],
            "warnings": [],
            "handover_recommended": True,
            "short_circuit": True,
        }

    return {
        "hits": hits,
        "confidence": retrieval_confidence(hits, settings.retrieval_min_score),
        "short_circuit": False,
    }


async def generate_node(state: AgentState) -> dict:
    try:
        draft = await generate_grounded_answer(
            state.get("query", ""),
            state.get("hits", []),
            state.get("session_context", ""),
        )
        return {"draft": draft}
    except Exception:
        # Do not leak provider errors or credentials to clients.
        return {"error": "generation_failed"}


def _citations_and_warnings(evidence_ids: list[str], hits: list[SearchHit]) -> tuple[list[dict], list[str]]:
    knowledge = get_knowledge_base()
    selected = [hit for hit in hits if hit.chunk.chunk_id in evidence_ids]
    counts = Counter(source_id for hit in selected for source_id in hit.chunk.source_ids)
    source_sections: dict[str, str] = {}
    for hit in selected:
        for source_id in hit.chunk.source_ids:
            source_sections.setdefault(source_id, hit.chunk.section)

    ordered_ids = sorted(
        counts,
        key=lambda source_id: (
            counts[source_id],
            SOURCE_PRIORITY.get(knowledge.sources[source_id].source_type, 1.0),
        ),
        reverse=True,
    )
    citations: list[dict] = []
    warnings: list[str] = []
    for source_id in ordered_ids[:5]:
        source = knowledge.sources[source_id]
        citations.append(
            Citation(
                source_id=source.source_id,
                title=source.title,
                url=source.url,
                section=source_sections.get(source_id),
                published_or_updated=source.published_or_updated,
                version=source.version,
                warning=source.warning,
            ).model_dump()
        )
        if source.warning:
            warnings.append(source.warning)

    flags = {flag for hit in selected for flag in hit.chunk.flags}
    if flags:
        warnings.append("Nguồn/evidence có trạng thái cần lưu ý: " + ", ".join(sorted(flags)) + ".")
    return citations, list(dict.fromkeys(warnings))


async def validate_node(state: AgentState) -> dict:
    if state.get("error"):
        reason = "generation_failed"
        return {
            "status": AnswerStatus.INSUFFICIENT_EVIDENCE.value,
            "response": _fail_closed_response(reason),
            "reason_code": reason,
            "grounded": False,
            "citations": [],
            "warnings": [],
            "confidence": 0.0,
            "handover_recommended": True,
        }

    draft = state["draft"]
    hits = state.get("hits", [])
    selected_hits = [hit for hit in hits if hit.chunk.chunk_id in draft.evidence_ids]
    blocked = blocked_source_ids()
    if any(source_id in blocked for hit in selected_hits for source_id in hit.chunk.source_ids):
        return {
            "status": AnswerStatus.HANDOVER_SUGGESTED.value, "reason_code": "source_change_pending_review",
            "response": "Nguồn liên quan đã thay đổi hoặc đang không truy cập được khi kiểm tra gần nhất. Cần người phụ trách dữ liệu đối chiếu lại trước khi trả lời.",
            "grounded": False, "confidence": 0.0, "citations": [], "warnings": [], "handover_recommended": True,
        }
    blocking_flags = {
        flag
        for hit in selected_hits
        for flag in hit.chunk.flags
        if flag in {
            "draft",
            "tentative",
            "conflict",
            "unresolved",
            "not_publicly_verified",
            "restricted",
            "dynamic",
        }
    }
    if blocking_flags:
        citations, warnings = _citations_and_warnings(draft.evidence_ids, hits)
        warnings.append("Evidence bị chặn do trạng thái: " + ", ".join(sorted(blocking_flags)) + ".")
        return {
            "status": AnswerStatus.HANDOVER_SUGGESTED.value,
            "response": _fail_closed_response("model_insufficient_evidence"),
            "reason_code": "unsafe_evidence_status",
            "grounded": False,
            "citations": citations,
            "warnings": list(dict.fromkeys(warnings)),
            "confidence": 0.0,
            "handover_recommended": True,
        }
    if draft.support_status != "supported":
        reason = "official_sources_conflict" if draft.support_status == "conflicting" else "model_insufficient_evidence"
        citations, warnings = _citations_and_warnings(draft.evidence_ids, hits)
        return {
            "status": AnswerStatus.HANDOVER_SUGGESTED.value,
            "response": _fail_closed_response(reason),
            "reason_code": reason,
            "grounded": False,
            "citations": citations,
            "warnings": warnings,
            "confidence": 0.0,
            "handover_recommended": True,
        }

    check = validate_grounded_answer(draft.answer, draft.evidence_ids, hits)
    citations, warnings = _citations_and_warnings(draft.evidence_ids, hits)
    if not check.valid:
        if check.unsupported_numbers:
            warnings.append("Các con số bị chặn: " + ", ".join(check.unsupported_numbers))
        return {
            "status": AnswerStatus.HANDOVER_SUGGESTED.value,
            "response": _fail_closed_response(check.reason_code),
            "reason_code": check.reason_code,
            "grounded": False,
            "citations": citations,
            "warnings": warnings,
            "confidence": 0.0,
            "handover_recommended": True,
        }

    return {
        "status": AnswerStatus.ANSWERED.value,
        "response": draft.answer,
        "reason_code": "grounded_answer",
        "grounded": True,
        "citations": citations,
        "warnings": list(dict.fromkeys(warnings + [
            f"Phạm vi dữ liệu: {get_knowledge_base().academic_year}; kiểm chứng đến {get_knowledge_base().verified_as_of}."
        ])),
        "handover_recommended": False,
    }
