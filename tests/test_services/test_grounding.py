from src.services.grounding import validate_grounded_answer
from src.services.knowledge_base import EvidenceChunk, SearchHit


def _hit(text: str) -> SearchHit:
    return SearchHit(
        chunk=EvidenceChunk(
            chunk_id="evidence-1",
            document="test.json",
            section="test",
            text=text,
            source_ids=("SRC-1",),
            tokens=("test",),
        ),
        score=10.0,
    )


def test_numeric_guard_accepts_formatting_changes():
    check = validate_grounded_answer(
        "Mức phí là 815.850.000 đồng cho năm 2026–2027.",
        ["evidence-1"],
        [_hit("per year: 815850000\nacademic year: 2026-2027")],
    )

    assert check.valid is True


def test_numeric_guard_rejects_invented_number():
    check = validate_grounded_answer(
        "Mức phí là 999.000.000 đồng.",
        ["evidence-1"],
        [_hit("per year: 815850000")],
    )

    assert check.valid is False
    assert check.reason_code == "unsupported_numeric_claim"
    assert check.unsupported_numbers == ("999.000.000",)


def test_grounding_rejects_unknown_evidence_id():
    check = validate_grounded_answer("Câu trả lời", ["missing"], [_hit("evidence")])

    assert check.valid is False
    assert check.reason_code == "unknown_evidence_id"


def test_single_digit_requirement_cannot_be_invented():
    check = validate_grounded_answer("Cần ít nhất 9 học kỳ.", ["evidence-1"], [_hit("eligibility: ít nhất 2 học kỳ")])
    assert not check.valid


def test_array_index_is_not_numeric_evidence():
    check = validate_grounded_answer("Cần 3 học kỳ.", ["evidence-1"], [_hit("requirements [3]: ít nhất 2 học kỳ")])
    assert not check.valid


def test_matching_array_index_in_answer_is_ignored_as_formatting():
    check = validate_grounded_answer(
        "Dịch vụ: services [1]: phòng khám trong khuôn viên.",
        ["evidence-1"],
        [_hit("services [1]: phòng khám trong khuôn viên")],
    )
    assert check.valid


def test_decimal_cannot_be_changed_to_integer():
    check = validate_grounded_answer("GPA tối thiểu 250.", ["evidence-1"], [_hit("GPA 2.50")])
    assert not check.valid
