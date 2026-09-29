"""Measure evidence and safe-answer coverage for the complete canonical dataset.

This is deliberately different from a small hand-written golden set.  It derives
one representative, user-shaped query for every canonical evidence chunk, checks
that every chunk is structurally valid, and distinguishes three results:

* answer coverage: public, unflagged facts must be answered using the target chunk;
* safety coverage: flagged facts must never become a factual ``answered`` response;
* excluded metadata: quality/coverage inventories are structurally audited but are
  not applicant-facing facts and must not inflate the answer KPI.

It does not prove all possible phrasings are correct.  It makes the scope,
coverage denominator, and failing chunks explicit so a reviewer can extend the
scenario templates or add human-labelled questions without hiding gaps.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agents.graph import agent  # noqa: E402
from src.services.knowledge_base import EvidenceChunk, get_knowledge_base  # noqa: E402

META_DOCUMENT_PREFIXES = ("coverage/", "quality/")
UNSAFE_FLAGS = frozenset({
    "draft",
    "tentative",
    "conflict",
    "unresolved",
    "not_publicly_verified",
    "restricted",
    "dynamic",
})


@dataclass(frozen=True)
class CoverageCase:
    chunk_id: str
    document: str
    section: str
    flags: tuple[str, ...]
    query: str
    expected: Literal["answer", "safe", "metadata"]


def _leaf(chunk: EvidenceChunk) -> str:
    return chunk.section.rsplit(" > ", maxsplit=1)[-1].strip()


def query_for(chunk: EvidenceChunk) -> str:
    """Use one clear, normal user question per data domain, not JSON field syntax."""
    subject = _leaf(chunk)
    document = chunk.document
    if subject == "english language requirements":
        return "Yêu cầu tiếng Anh đầu vào của VinUni là gì?"
    if subject == "academic calendar 2026 2027":
        return "Lịch học chính thức năm 2026-2027 là gì?"
    if subject == "disputed program code":
        return "Mã ngành Kỹ thuật Cơ khí của VinUni là gì?"
    if subject == "disputed return deadline":
        return "Hạn quay lại sau khi nghỉ học là 1 tuần hay 1 tháng?"
    if "academic regulations > letter grades >" in chunk.section:
        return "Thang quy đổi điểm chữ sang GPA của VinUni như thế nào?"
    direct_queries = {
        "contact": "Thông tin liên hệ tuyển sinh VinUni là gì?",
        "scholarships": "VinUni có những học bổng nào?",
        "student loan": "Khoản vay sinh viên VinUni có lãi suất và thời hạn thế nào?",
        "discount combination rules": "Ưu đãi gia đình và cựu sinh viên có được cộng với học bổng không?",
        "dormitory": "Phí ký túc xá VinUni bao nhiêu?",
        "library fees": "Phí phạt thư viện VinUni được tính như thế nào?",
        "refund policy": "Chính sách hoàn học phí của VinUni như thế nào?",
        "academic regulations > version": "Quy chế học vụ VinUni hiện là phiên bản nào?",
        "academic regulations > effective or last updated": "Quy chế học vụ VinUni có hiệu lực hoặc được cập nhật ngày nào?",
        "academic regulations > applies to": "Quy chế học vụ VinUni áp dụng cho những đối tượng nào?",
        "academic regulations > language of instruction": "Ngôn ngữ giảng dạy chính thức tại VinUni là gì?",
        "academic regulations > academic year structure": "Một năm học VinUni gồm các học kỳ nào?",
        "academic regulations > maximum candidature": "Thời gian học tối đa tại VinUni là bao lâu?",
        "academic regulations > deans list": "Điều kiện để vào Dean’s List là gì?",
        "academic regulations > double degree": "Điều kiện học bằng kép tại VinUni là gì?",
        "academic regulations > grading notes": "Quy tắc điểm đỗ và làm tròn GPA của VinUni là gì?",
        "grade appeal": "Quy trình phúc khảo điểm tại VinUni là gì?",
        "leave withdrawal and return": "Quy định xin nghỉ học hoặc bảo lưu tại VinUni là gì?",
        "minor count": "VinUni hiện có bao nhiêu chương trình minor?",
        "official page data quality note": "Mã học phần của minor có thông tin nào cần xác nhận với Registrar không?",
        "academic accommodation": "Chính sách điều chỉnh học tập cho sinh viên có nhu cầu hỗ trợ là gì?",
        "internships": "Quy định thực tập tại VinUni là gì?",
        "student code of conduct": "Quy tắc ứng xử dành cho sinh viên VinUni là gì?",
        "public vs internal information": "Những thông tin nào của VinUni chỉ dành cho nội bộ?",
    }
    if chunk.section in direct_queries:
        return direct_queries[chunk.section]
    if document.startswith("programs/"):
        if chunk.section.startswith("programs >"):
            return f"Chương trình {subject} tại VinUni học mấy năm?"
        return "VinUni có những chương trình nào không được tính là ngành tuyển sinh riêng?"
    if document.startswith("tuition/"):
        if subject == "founder educational development grant":
            return "Hỗ trợ tài chính Founder Educational Development Grant của VinUni là gì?"
        if subject == "tuition includes":
            return "Học phí VinUni bao gồm những gì?"
        if subject == "per credit rate applies when":
            return "Học phí theo tín chỉ tại VinUni được áp dụng khi nào?"
        if subject == "payment":
            return "Cách thanh toán học phí tại VinUni như thế nào?"
        if subject == "important exclusions":
            return "Học phí VinUni không bao gồm những gì?"
        return f"Học phí VinUni cho {subject} năm 2026-2027 là bao nhiêu?"
    if document.startswith("admissions/"):
        return f"Thông tin tuyển sinh VinUni 2026-2027 về {subject} là gì?"
    if document.startswith("financial_aid/"):
        return f"Thông tin học bổng hoặc chi phí VinUni về {subject} là gì?"
    if document.startswith("academics/vinuni_undergraduate_minors"):
        return f"Minor {subject} tại VinUni là gì?"
    if document.startswith("academics/"):
        return f"Quy định học vụ VinUni về {subject} là gì?"
    if document.startswith("student_life/"):
        return f"Dịch vụ sinh viên VinUni về {subject} là gì?"
    if document.startswith("international/"):
        return f"Thông tin quốc tế VinUni về {subject} là gì?"
    if document.startswith("governance/"):
        return f"Quy định sinh viên VinUni về {subject} là gì?"
    return f"Thông tin VinUni về {subject} là gì?"


def build_cases() -> list[CoverageCase]:
    knowledge = get_knowledge_base(reload=True)
    cases: list[CoverageCase] = []
    for chunk in knowledge.chunks:
        if chunk.document.startswith(META_DOCUMENT_PREFIXES):
            expected: Literal["answer", "safe", "metadata"] = "metadata"
        elif set(chunk.flags) & UNSAFE_FLAGS or chunk.section == "official page data quality note":
            expected = "safe"
        else:
            expected = "answer"
        cases.append(
            CoverageCase(
                chunk_id=chunk.chunk_id,
                document=chunk.document,
                section=chunk.section,
                flags=chunk.flags,
                query=query_for(chunk),
                expected=expected,
            )
        )
    return cases


def _draft_evidence_ids(result: dict) -> list[str]:
    draft = result.get("draft")
    if draft is None:
        return []
    return list(getattr(draft, "evidence_ids", []))


async def run(*, strict: bool = False, max_cases: int = 0) -> tuple[dict, int]:
    knowledge = get_knowledge_base(reload=True)
    if not knowledge.ready:
        return {"error": "knowledge_base_unavailable", "load_errors": knowledge.load_errors}, 2

    cases = build_cases()
    if max_cases:
        cases = cases[:max_cases]
    source_errors = [
        chunk.chunk_id
        for chunk in knowledge.chunks
        if not chunk.source_ids or any(source_id not in knowledge.sources for source_id in chunk.source_ids)
    ]
    reports: list[dict] = []
    for case in cases:
        result = await agent.ainvoke({"query": case.query, "session_context": ""})
        hit_ids = [hit.chunk.chunk_id for hit in result.get("hits", [])]
        evidence_ids = _draft_evidence_ids(result)
        retrieved_target = case.chunk_id in hit_ids
        if case.expected == "answer":
            passed = (
                result.get("status") == "answered"
                and bool(result.get("grounded"))
                and bool(result.get("citations"))
                and case.chunk_id in evidence_ids
            )
        elif case.expected == "safe":
            passed = result.get("status") != "answered" and not result.get("grounded")
        else:
            # Metadata is audited structurally rather than claimed as applicant-facing coverage.
            passed = True
        reports.append(
            {
                **asdict(case),
                "status": result.get("status"),
                "reason_code": result.get("reason_code"),
                "grounded": bool(result.get("grounded")),
                "retrieved_target": retrieved_target,
                "draft_evidence_ids": evidence_ids,
                "passed": passed,
            }
        )

    groups: dict[str, list[dict]] = defaultdict(list)
    for report in reports:
        groups[report["expected"]].append(report)
    summary = {
        "dataset_id": knowledge.dataset_id,
        "academic_year": knowledge.academic_year,
        "dataset_fingerprint": knowledge.fingerprint,
        "total_canonical_chunks": len(knowledge.chunks),
        "all_chunks_have_valid_source_mapping": not source_errors,
        "invalid_source_mapping_chunk_ids": source_errors,
        "case_counts": dict(Counter(item["expected"] for item in reports)),
        "answer_coverage": {
            "passed": sum(item["passed"] for item in groups["answer"]),
            "total": len(groups["answer"]),
            "retrieved_target": sum(item["retrieved_target"] for item in groups["answer"]),
        },
        "safety_coverage": {
            "passed": sum(item["passed"] for item in groups["safe"]),
            "total": len(groups["safe"]),
            "retrieved_target": sum(item["retrieved_target"] for item in groups["safe"]),
        },
        "metadata_structurally_audited": len(groups["metadata"]),
        "failures": [item for item in reports if not item["passed"]],
    }
    healthy = not source_errors and not summary["failures"]
    return {"summary": summary, "cases": reports}, 0 if healthy or not strict else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when a coverage scenario fails")
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "eval" / "results" / "canonical_coverage_report.json")
    args = parser.parse_args()
    payload, status = asyncio.run(run(strict=args.strict, max_cases=args.max_cases))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # ``ensure_ascii`` keeps this CLI usable in Windows terminals configured
    # with a legacy code page; the JSON report itself remains UTF-8 Vietnamese.
    console_summary = {key: value for key, value in payload["summary"].items() if key != "failures"}
    console_summary["failure_count"] = len(payload["summary"]["failures"])
    print(json.dumps(console_summary, ensure_ascii=True, indent=2))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
