"""Run the deterministic golden set against the accuracy-first agent."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agents.graph import agent  # noqa: E402
from src.services.knowledge_base import get_knowledge_base  # noqa: E402

EXPECTED_STATUSES = {
    "answer": {"answered"},
    "handover": {"handover_suggested"},
    "clarify": {"needs_clarification"},
    "refuse": {"insufficient_evidence"},
}


def evaluate_result(case: dict[str, Any], result: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    behavior = case["expected_behavior"]
    status = result.get("status")
    if status not in EXPECTED_STATUSES[behavior]:
        failures.append(f"status={status!r}, expected={sorted(EXPECTED_STATUSES[behavior])}")

    response = result.get("response", "")
    if case.get("reason_code") and result.get("reason_code") != case["reason_code"]:
        failures.append(f"reason_code={result.get('reason_code')!r}, expected={case['reason_code']!r}")
    for forbidden in case.get("must_not_contain", []):
        if forbidden.casefold() in response.casefold():
            failures.append(f"forbidden text {forbidden!r}")
    for required in case.get("must_contain", []):
        if required.casefold() not in response.casefold():
            failures.append(f"missing text {required!r}")

    if behavior == "answer":
        if not result.get("grounded"):
            failures.append("answered response is not grounded")
        if not result.get("citations"):
            failures.append("answered response has no citations")
    elif result.get("grounded"):
        failures.append("non-answer response must not be marked grounded")

    if status != "answered" and float(result.get("confidence", 0.0)) != 0.0:
        failures.append("non-answer response must have confidence=0")
    return failures


async def run(dataset_path: Path, *, verbose: bool = False) -> int:
    cases = json.loads(dataset_path.read_text(encoding="utf-8"))
    knowledge = get_knowledge_base(reload=True)
    if not knowledge.ready:
        print(json.dumps({"error": "knowledge_base_unavailable", "details": knowledge.load_errors}, ensure_ascii=False))
        return 2

    reports: list[dict[str, Any]] = []
    for case in cases:
        result = await agent.ainvoke({"query": case["query"], "session_context": ""})
        failures = evaluate_result(case, result)
        reports.append(
            {
                "id": case["id"],
                "passed": not failures,
                "failures": failures,
                "status": result.get("status"),
                "reason_code": result.get("reason_code"),
            }
        )
        if verbose:
            print(f"\n[{case['id']}] {result.get('status')} / {result.get('reason_code')}")
            print(result.get("response", ""))

    passed = sum(report["passed"] for report in reports)
    answered = sum(report["status"] == "answered" for report in reports)
    expected_answers = sum(case["expected_behavior"] == "answer" for case in cases)
    answered_in_scope = sum(
        report["status"] == "answered"
        for case, report in zip(cases, reports, strict=True)
        if case["expected_behavior"] == "answer"
    )
    grounded_answers = sum(
        report["status"] == "answered" and not any("grounded" in item for item in report["failures"])
        for report in reports
    )
    summary = {
        "cases": len(cases),
        "passed": passed,
        "pass_rate": round(passed / len(cases), 4),
        "expected_answer_cases": expected_answers,
        "in_scope_answer_rate": round(answered_in_scope / max(expected_answers, 1), 4),
        "answer_rate_on_full_set": round(answered / len(cases), 4),
        "grounded_answer_compliance": round(grounded_answers / max(answered, 1), 4),
        "failed_cases": [report for report in reports if not report["passed"]],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if passed == len(cases) else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "eval" / "golden_questions.json",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    return asyncio.run(run(args.dataset, verbose=args.verbose))


if __name__ == "__main__":
    raise SystemExit(main())
