from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from src.services.knowledge_base import get_knowledge_base, normalize_text
from src.services.query_understanding import has_phrase, named_programs, needs_reference, normalize_query


class Intent(StrEnum):
    PROGRAMS = "programs"
    ADMISSIONS = "admissions"
    TUITION = "tuition"
    FINANCIAL_AID = "financial_aid"
    ACADEMIC_RULES = "academic_rules"
    STUDENT_LIFE = "student_life"
    INTERNATIONAL = "international"
    EXCHANGE_INTERNSHIP = "exchange_internship"
    GOVERNANCE = "governance"
    UNKNOWN = "unknown"


INTENT_KEYWORDS = {
    Intent.TUITION: ("hoc phi", "chi phi", "bao nhieu tien", "dong tien", "hoan phi", "fee"),
    Intent.FINANCIAL_AID: (
        "hoc bong", "ho tro tai chinh", "khoan vay", "thu vien", "library", "scholarship", "financial aid",
    ),
    Intent.ADMISSIONS: (
        "tuyen sinh",
        "ung tuyen",
        "nop ho so",
        "dau vao",
        "chi tieu",
        "quota",
        "ielts",
        "sat",
        "tieng anh",
        "english language",
        "deadline",
        "han nop",
    ),
    Intent.PROGRAMS: (
        "nganh", "chuong trinh", "hoc gi", "major", "program", "tin chi cua nganh", "minor", "nganh phu",
    ),
    Intent.ACADEMIC_RULES: (
        "gpa",
        "tin chi",
        "phuc khao",
        "nghi hoc",
        "hoc lai",
        "tot nghiep",
        "bang kep",
        "doi nganh",
        "genai",
        "chatgpt",
        "quy dinh hoc vu",
        "quy che hoc vu",
        "academic regulations",
        "course load",
        "add drop",
        "rut mon",
        "diem chu",
        "academic standing",
        "deans list",
        "dean s list",
        "phien ban quy che",
        "hieu luc",
        "ngon ngu giang day",
        "cau truc nam hoc",
        "thoi gian hoc toi da",
        "hoc ky",
        "quy tac diem",
        "lam tron gpa",
        "bao luu",
        "xin nghi hoc",
    ),
    Intent.STUDENT_LIFE: (
        "ky tuc xa", "noi tru", "cau lac bo", "suc khoe", "tham van", "student life", "doi song sinh vien",
        "dich vu sinh vien", "ho tro sinh vien", "wellbeing", "accommodation", "fitness to study",
        "academic accommodation", "dieu chinh hoc tap",
    ),
    Intent.INTERNATIONAL: ("visa", "sinh vien quoc te", "tieng viet", "international student", "quoc te"),
    Intent.EXCHANGE_INTERNSHIP: ("trao doi", "exchange", "thuc tap", "internship"),
    Intent.GOVERNANCE: (
        "khieu nai", "ky luat", "quyen", "nghia vu", "conduct", "complaint", "quy dinh sinh vien", "quy tac ung xu",
        "thong tin noi bo",
        "noi bo",
    ),
}

GUARANTEE_PATTERNS = (
    "chac chan do",
    "chac chan trung tuyen",
    "bao dam do",
    "cam ket do",
    "co do khong",
    "em co do",
    "toi co do",
    "duoc hoc bong khong",
    "chac chan hoc bong",
    "admission chance",
)

PROMPT_INJECTION_PATTERNS = (
    "bo qua chi dan",
    "bo qua quy tac",
    "ignore previous",
    "ignore all",
    "system prompt",
    "tiet lo prompt",
    "reveal prompt",
    "developer message",
    "api key",
    "bo qua tat ca chi dan",
    "tu uoc tinh", "tu bia", "cu bia", "ignore the instructions",
    "khong can nguon", "du nguon mau thuan",
)

AMBIGUOUS_REFERENCE_PATTERNS = ("nganh nay", "chuong trinh nay", "chuong trinh do", "no", "cai do")

EMAIL_PATTERN = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w.-])", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?84|0)[\s.-]?(?:\d[\s.-]?){8,10}(?!\d)")
LONG_NUMBER_PATTERN = re.compile(r"(?<!\d)(?:\d[\s.-]?){12,19}(?!\d)")
PASSPORT_VALUE_PATTERN = re.compile(
    r"(?:passport|ho chieu)\s*(?:number|no|so|:|-)?\s*([a-z]{1,3}\d{5,9})",
    re.IGNORECASE,
)
FINANCIAL_ID_TERMS = ("so tai khoan", "the ngan hang", "credit card", "bank account")
NATIONAL_ID_TERMS = ("cccd", "cmnd", "can cuoc")


@dataclass(frozen=True)
class IntentDecision:
    intent: Intent
    requires_handover: bool = False
    needs_clarification: bool = False
    reason_code: str = "ok"
    message: str | None = None


def sensitive_data_types(query: str) -> tuple[str, ...]:
    """Detect values that should not be retained in an admissions chat."""
    normalized = normalize_text(query)
    detected: list[str] = []
    if EMAIL_PATTERN.search(query):
        detected.append("email")
    if PHONE_PATTERN.search(query):
        detected.append("phone")
    if PASSPORT_VALUE_PATTERN.search(normalized):
        detected.append("passport")
    if LONG_NUMBER_PATTERN.search(query) and any(term in normalized for term in NATIONAL_ID_TERMS):
        detected.append("national_id")
    if LONG_NUMBER_PATTERN.search(query) and any(term in normalized for term in FINANCIAL_ID_TERMS):
        detected.append("financial_identifier")
    return tuple(dict.fromkeys(detected))


def contains_sensitive_data(query: str) -> bool:
    return bool(sensitive_data_types(query))


def classify_query(query: str, *, has_session_context: bool = False) -> IntentDecision:
    normalized = normalize_query(query)

    if contains_sensitive_data(query):
        return IntentDecision(
            intent=Intent.UNKNOWN,
            requires_handover=False,
            needs_clarification=True,
            reason_code="sensitive_data_detected",
            message=(
                "Vì bảo mật, bạn không nên gửi email, số điện thoại, CCCD, hộ chiếu hoặc thông tin tài chính "
                "trực tiếp trong ô chat. Hãy xóa thông tin cá nhân rồi đặt lại câu hỏi. Nếu cần cán bộ liên hệ, "
                "chỉ cung cấp kênh liên hệ trong biểu mẫu handover có bước xác nhận đồng ý."
            ),
        )

    if any(pattern in normalized for pattern in PROMPT_INJECTION_PATTERNS):
        return IntentDecision(
            intent=Intent.UNKNOWN,
            requires_handover=False,
            reason_code="prompt_injection_blocked",
            message=(
                "Tôi không thể làm theo yêu cầu thay đổi quy tắc hệ thống hoặc tiết lộ cấu hình nội bộ. "
                "Bạn có thể hỏi về tuyển sinh và thông tin sinh viên VinUni."
            ),
        )

    if any(has_phrase(normalized, p) for p in ("gap can bo", "noi chuyen voi can bo", "can nguoi tu van", "human agent", "talk to a human")):
        return IntentDecision(Intent.ADMISSIONS, requires_handover=True, reason_code="user_requested_handover",
                              message="Bạn có thể chuyển câu hỏi cho cán bộ tuyển sinh bằng biểu mẫu bên dưới. Hãy kiểm tra nội dung và xác nhận đồng ý trước khi gửi.")

    if any(has_phrase(normalized, p) for p in ("chac chan", "bao dam", "dam bao", "guaranteed", "guarantee", "kha nang trung tuyen", "ho so cua em", "ho so cua toi")) and any(
        has_phrase(normalized, p) for p in ("do", "trung tuyen", "hoc bong", "duoc nhan", "du manh", "admission", "scholarship")
    ):
        return IntentDecision(Intent.ADMISSIONS, requires_handover=True, reason_code="personal_admission_decision",
                              message="Tôi không thể dự đoán hoặc cam kết kết quả trúng tuyển/học bổng của một hồ sơ cá nhân. Cán bộ tuyển sinh cần xem xét theo quy trình chính thức.")

    if any(has_phrase(normalized, p) for p in ("nam sau", "nam truoc", "next year", "last year")):
        return IntentDecision(Intent.UNKNOWN, needs_clarification=True, reason_code="ambiguous_academic_year",
                              message="Bạn muốn hỏi năm học hoặc khóa nhập học nào? Vui lòng ghi rõ, ví dụ 2026–2027, để tránh áp dụng nhầm chính sách.")

    if any(has_phrase(normalized, p) for p in ("lich hoc", "academic calendar", "lich thi", "exam schedule")):
        return IntentDecision(
            Intent.ACADEMIC_RULES,
            requires_handover=True,
            reason_code="academic_calendar_not_final",
            message=(
                "Lịch học/lịch thi là thông tin có thể thay đổi và bản 2026–2027 trong kho dữ liệu "
                "chưa được xác nhận là lịch cuối cùng. Tôi sẽ không tự khẳng định mốc thời gian; "
                "vui lòng kiểm tra thông báo chính thức mới nhất hoặc chuyển cán bộ xác nhận."
            ),
        )

    if any(has_phrase(normalized, term) for term in ("minor", "nganh phu")) and any(
        has_phrase(normalized, term) for term in ("ma hoc phan", "course code", "ma mon")
    ):
        return IntentDecision(
            Intent.PROGRAMS,
            requires_handover=True,
            reason_code="minor_course_code_requires_registrar_confirmation",
            message=(
                "Một số mã học phần minor trên trang công khai có thể lặp hoặc chưa nhất quán. "
                "Tôi sẽ không tự xác nhận mã môn; vui lòng đối chiếu SIS/trang nguồn mới nhất hoặc hỏi Registrar/College."
            ),
        )

    # The only extracted 2026–2027 English-entry requirement is deliberately
    # marked restricted in the official-data manifest.  Do not let a related,
    # public admissions chunk stand in for it: that would produce a fluent but
    # unsupported answer to a precise eligibility question.
    asks_english_entry_requirement = (
        any(has_phrase(normalized, term) for term in ("tieng anh", "english language"))
        and any(has_phrase(normalized, term) for term in ("dau vao", "dieu kien", "requirement"))
    )
    if asks_english_entry_requirement:
        return IntentDecision(
            Intent.ADMISSIONS,
            requires_handover=True,
            reason_code="english_entry_requirement_restricted",
            message=(
                "Bộ dữ liệu hiện có ghi nhận thông tin yêu cầu tiếng Anh đầu vào là nguồn hạn chế, "
                "chưa đủ để công khai một điều kiện cụ thể. Tôi sẽ không suy đoán điểm/chứng chỉ; "
                "vui lòng kiểm tra trang Admissions chính thức mới nhất hoặc chuyển cán bộ xác nhận."
            ),
        )

    academic_year = get_knowledge_base().academic_year or "2026-2027"
    pairs = re.findall(r"\b(20\d{2})\s*[-–/]\s*(20\d{2})\b", query)
    requested = re.findall(r"(?:nam hoc|nam|cohort|khoa|year|intake)\s+(20\d{2})\b", normalized)
    if any(f"{start}-{end}" != academic_year for start, end in pairs) or any(year != academic_year[:4] for year in requested):
        return IntentDecision(Intent.UNKNOWN, requires_handover=True, reason_code="unsupported_academic_year",
                              message=f"Kho dữ liệu hiện được kiểm chứng cho năm học {academic_year}. Tôi chưa có đủ căn cứ cho năm/khóa bạn yêu cầu; cần cán bộ xác nhận đúng phiên bản chính sách.")

    in_domain = any(has_phrase(normalized, term) for terms in INTENT_KEYWORDS.values() for term in terms)
    if in_domain and any(has_phrase(normalized, p) for p in ("gia han", "con nop", "con nhan ho so", "moi nhat", "hom nay", "extended", "still open", "latest")):
        return IntentDecision(Intent.ADMISSIONS, requires_handover=True, reason_code="live_information_required",
                              message="Thông tin này cần xác nhận tại thời điểm hiện tại. Kho dữ liệu là bản chụp đã kiểm chứng, chưa xác nhận các thay đổi hoặc gia hạn mới; vui lòng chuyển cán bộ hoặc kiểm tra thông báo chính thức mới nhất.")

    if "chi tieu" in normalized or "admission quota" in normalized:
        return IntentDecision(
            intent=Intent.ADMISSIONS,
            requires_handover=True,
            reason_code="admission_quota_not_publicly_verified",
            message=(
                "Bộ dữ liệu chính thức hiện chưa có chỉ tiêu tuyển sinh 2026–2027 đã được công khai "
                "và kiểm chứng theo từng chương trình. Tôi sẽ không suy đoán con số; bạn nên kiểm tra "
                "thông báo tuyển sinh mới nhất hoặc chuyển câu hỏi cho cán bộ Admissions."
            ),
        )

    if any(pattern in normalized for pattern in GUARANTEE_PATTERNS):
        return IntentDecision(
            intent=Intent.ADMISSIONS,
            requires_handover=True,
            reason_code="personal_admission_decision",
            message=(
                "Tôi không thể dự đoán hoặc cam kết kết quả trúng tuyển/học bổng cho một hồ sơ cá nhân. "
                "Tôi có thể giải thích tiêu chí chính thức; để đánh giá hồ sơ, bạn nên chuyển câu hỏi cho cán bộ tuyển sinh."
            ),
        )

    if needs_reference(query) and not has_session_context and not named_programs(query):
        return IntentDecision(
            intent=Intent.UNKNOWN,
            needs_clarification=True,
            reason_code="missing_conversation_reference",
            message="Bạn đang nói tới ngành hoặc chương trình nào? Vui lòng nêu tên cụ thể để tôi tra đúng dữ liệu.",
        )

    if normalized in {"dieu kien nhu the nao", "dieu kien la gi", "bao nhieu tien", "hi", "hello", "xin chao", "chao"}:
        return IntentDecision(Intent.UNKNOWN, needs_clarification=True, reason_code="missing_topic",
                              message="Bạn muốn tìm hiểu ngành học, học phí, học bổng hay hồ sơ tuyển sinh VinUni? Hãy nêu chủ đề và chương trình nếu có.")

    topics = [label for label, terms in (
        ("học phí", ("hoc phi",)), ("học bổng", ("hoc bong", "ho tro tai chinh")),
        ("hạn nộp hồ sơ", ("han nop", "deadline")),
    ) if any(has_phrase(normalized, term) for term in terms)]
    if len(topics) > 1:
        return IntentDecision(Intent.UNKNOWN, needs_clarification=True, reason_code="multiple_topics",
                              message=f"Bạn đang hỏi nhiều nội dung: {', '.join(topics)}. Bạn muốn tra cứu nội dung nào trước? Tôi sẽ đối chiếu từng chính sách và nguồn riêng.")

    scores = {
        intent: sum(2 if " " in keyword else 1 for keyword in keywords if has_phrase(normalized, keyword))
        for intent, keywords in INTENT_KEYWORDS.items()
    }
    if any(has_phrase(normalized, p) for p in ("trao doi", "exchange")):
        scores[Intent.EXCHANGE_INTERNSHIP] += 4
    if named_programs(query) and not any(scores.values()):
        scores[Intent.PROGRAMS] = 1
    best_intent, best_score = max(scores.items(), key=lambda item: item[1])
    return IntentDecision(intent=best_intent if best_score else Intent.UNKNOWN)


def is_program_list_query(query: str) -> bool:
    normalized = normalize_query(query)
    return any(
        phrase in normalized
        for phrase in ("co nhung nganh", "danh sach nganh", "bao nhieu nganh", "cac nganh", "program list")
    )
