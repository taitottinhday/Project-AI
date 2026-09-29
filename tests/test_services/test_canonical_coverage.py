from collections import Counter

from scripts.evaluate_canonical_coverage import UNSAFE_FLAGS, build_cases
from src.services.knowledge_base import get_knowledge_base


def test_canonical_coverage_suite_has_one_case_per_chunk_and_safe_flag_policy():
    knowledge = get_knowledge_base(reload=True)
    cases = build_cases()

    assert len(cases) == len(knowledge.chunks)
    assert {case.chunk_id for case in cases} == {chunk.chunk_id for chunk in knowledge.chunks}
    assert all(
        case.expected in {"safe", "metadata"}
        for case in cases
        if set(case.flags) & UNSAFE_FLAGS
    )
    assert Counter(case.expected for case in cases)["answer"] > 100
