"""Evaluate deterministic behavior and optionally run an evidence-bound LLM judge.

The deterministic gate is always executed. LLM judging is opt-in because it costs
tokens and is not a substitute for independent human review.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path
from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.evaluate import evaluate_result  # noqa: E402
from src.agents.graph import agent  # noqa: E402
from src.config import get_settings  # noqa: E402
from src.services.answer_generator import build_context  # noqa: E402
from src.services.knowledge_base import get_knowledge_base  # noqa: E402


class QualityGrade(BaseModel):
    correctness: int = Field(ge=0, le=4)
    citation_support: int = Field(ge=0, le=4)
    relevance: int = Field(ge=0, le=4)
    safe_behavior: int = Field(ge=0, le=4)
    verdict: Literal["pass", "review", "fail"]
    rationale: str = Field(max_length=800)


JUDGE_PROMPT = """Bạn là người chấm độc lập cho trợ lý tuyển sinh accuracy-first.

Chỉ dùng EXPECTED CHECKS và RETRIEVED EVIDENCE bên dưới; không dùng kiến thức ngoài.
Chấm bốn tiêu chí từ 0 đến 4:
- correctness: claim có đúng theo evidence/expected checks không;
- citation_support: claim factual có được evidence và citation hỗ trợ không;
- relevance: trả lời trực tiếp, không vòng vo;
- safe_behavior: biết làm rõ, từ chối hoặc handover khi không đủ căn cứ.

Một con số, deadline, điều kiện hoặc cam kết không có evidence phải khiến verdict=fail.
Một lần từ chối/handover đúng thiết kế có thể đạt điểm tối đa. verdict=pass chỉ khi mọi
tiêu chí >=3 và không có lỗi nghiêm trọng. Nếu evidence hoặc expected checks chưa đủ để
kết luận, dùng verdict=review. Trả về đúng schema, không thêm văn bản ngoài.
"""


def _human_rows(reports: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for report in reports:
        rows.append(
            {
                "id": report["id"],
                "query": report["query"],
                "expected_behavior": report["expected_behavior"],
                "actual_status": report["status"],
                "answer": report["answer"],
                "citation_urls": " | ".join(report["citation_urls"]),
                "correctness_0_4": "",
                "citation_support_0_4": "",
                "relevance_0_4": "",
                "safe_behavior_0_4": "",
                "human_verdict": "",
                "reviewer_notes": "",
            }
        )
    return rows


async def _judge_case(
    case: dict[str, Any],
    result: dict[str, Any],
    judge: Any,
) -> QualityGrade:
    evidence = build_context(result.get("hits", []), max_chars=12_000)
    citations = json.dumps(result.get("citations", []), ensure_ascii=False)
    prompt = (
        f"QUESTION:\n{case['query']}\n\n"
        f"EXPECTED BEHAVIOR:\n{case['expected_behavior']}\n\n"
        f"EXPECTED CHECKS:\n{json.dumps(case.get('must_contain', []), ensure_ascii=False)}\n\n"
        f"ACTUAL STATUS:\n{result.get('status')}\n\n"
        f"ACTUAL ANSWER:\n{result.get('response', '')}\n\n"
        f"CITATIONS:\n{citations}\n\n"
        f"RETRIEVED EVIDENCE:\n{evidence or 'Không có evidence.'}"
    )
    grade = await judge.ainvoke([SystemMessage(content=JUDGE_PROMPT), HumanMessage(content=prompt)])
    return grade if isinstance(grade, QualityGrade) else QualityGrade.model_validate(grade)


async def run(args: argparse.Namespace) -> int:
    settings = get_settings()
    cases = json.loads(args.dataset.read_text(encoding="utf-8"))
    if args.max_cases:
        cases = cases[: args.max_cases]

    knowledge = get_knowledge_base(reload=True)
    if not knowledge.ready:
        print(json.dumps({"error": "knowledge_base_unavailable", "details": knowledge.load_errors}, ensure_ascii=False))
        return 2
    if args.judge and not settings.openai_api_key:
        print("OPENAI_API_KEY is required only when --judge is enabled.", file=sys.stderr)
        return 2

    judge = None
    if args.judge:
        judge = ChatOpenAI(
            model=settings.eval_judge_model,
            api_key=settings.openai_api_key,
            temperature=0,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        ).with_structured_output(QualityGrade, method="json_schema")

    reports: list[dict[str, Any]] = []
    for case in cases:
        result = await agent.ainvoke({"query": case["query"], "session_context": ""})
        failures = evaluate_result(case, result)
        grade = await _judge_case(case, result, judge) if judge else None
        reports.append(
            {
                "id": case["id"],
                "query": case["query"],
                "expected_behavior": case["expected_behavior"],
                "status": result.get("status", "unknown"),
                "answer": result.get("response", ""),
                "citation_urls": [item.get("url", "") for item in result.get("citations", [])],
                "deterministic_pass": not failures,
                "deterministic_failures": failures,
                "llm_judge": grade.model_dump() if grade else None,
            }
        )

    deterministic_passes = sum(item["deterministic_pass"] for item in reports)
    judged = [item for item in reports if item["llm_judge"]]
    judged_passes = sum(item["llm_judge"]["verdict"] == "pass" for item in judged)
    summary = {
        "dataset": str(args.dataset),
        "cases": len(reports),
        "deterministic_pass_rate": round(deterministic_passes / max(len(reports), 1), 4),
        "llm_judge_enabled": bool(judge),
        "llm_judge_model": settings.eval_judge_model if judge else None,
        "llm_judge_pass_rate": round(judged_passes / len(judged), 4) if judged else None,
        "warning": (
            "LLM-as-Judge is a quality signal, not ground truth. Use the human review template for final KPI sign-off."
        ),
    }
    payload = {"summary": summary, "cases": reports}
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.human_review_template:
        args.human_review_template.parent.mkdir(parents=True, exist_ok=True)
        rows = _human_rows(reports)
        with args.human_review_template.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    all_deterministic = deterministic_passes == len(reports)
    all_judged = not judged or judged_passes == len(judged)
    return 0 if all_deterministic and all_judged else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=PROJECT_ROOT / "eval" / "golden_questions.json")
    parser.add_argument("--judge", action="store_true", help="Run the paid, opt-in LLM-as-Judge stage")
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--human-review-template", type=Path)
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
