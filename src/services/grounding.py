from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from src.services.knowledge_base import SearchHit

NUMBER_RE = re.compile(r"(?<![A-Za-z\d])\d+(?:[.,]\d+)*(?![A-Za-z\d])")


@dataclass(frozen=True)
class GroundingCheck:
    valid: bool
    reason_code: str
    unsupported_numbers: tuple[str, ...] = ()


def _canonical_number(value: str) -> str:
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", value):
        value = re.sub(r"[.,]", "", value)
    return str(Decimal(value.replace(",", ".")).normalize())


def validate_grounded_answer(answer: str, evidence_ids: list[str], hits: list[SearchHit]) -> GroundingCheck:
    available = {hit.chunk.chunk_id: hit for hit in hits}
    if not answer.strip():
        return GroundingCheck(False, "empty_model_answer")
    if not evidence_ids:
        return GroundingCheck(False, "missing_evidence_ids")
    if any(evidence_id not in available for evidence_id in evidence_ids):
        return GroundingCheck(False, "unknown_evidence_id")

    # Extract from the raw text. Normalizing first would erase punctuation and
    # turn values such as "2026-2027" into two unrelated numbers.
    evidence_text = "\n".join(available[item].chunk.text for item in evidence_ids)
    # Array positions in rendered JSON are not factual numeric evidence.
    evidence_text = re.sub(r"\[\d+\]", "", evidence_text)
    evidence_digits = {_canonical_number(item) for item in NUMBER_RE.findall(evidence_text)}
    # List markers ("1. Contact ..." / "services [1]: ...") are formatting,
    # not factual claims. The corpus renderer uses bracketed indices inside a
    # field name, so remove those on the answer side as well.
    answer = re.sub(r"(?m)^\s*\d+\.\s+", "", answer)
    answer = re.sub(r"\[\d+\]", "", answer)
    unsupported: list[str] = []
    for value in NUMBER_RE.findall(answer):
        canonical = _canonical_number(value)
        # Formatting may change (815850000 -> 815.850.000); compare digits only.
        if canonical not in evidence_digits:
            unsupported.append(value)

    if unsupported:
        return GroundingCheck(False, "unsupported_numeric_claim", tuple(sorted(set(unsupported))))
    return GroundingCheck(True, "grounded")


def retrieval_confidence(hits: list[SearchHit], minimum_score: float) -> float:
    if not hits or hits[0].score < minimum_score:
        return 0.0
    top = hits[0].score
    second = hits[1].score if len(hits) > 1 else 0.0
    absolute = min(1.0, top / max(minimum_score * 4, 1.0))
    separation = min(1.0, max(0.0, top - second) / max(top, 1.0) + 0.45)
    diversity = min(1.0, len({source_id for hit in hits[:3] for source_id in hit.chunk.source_ids}) / 3)
    # Never expose 1.0: retrieval confidence is a routing signal, not a probability of truth.
    return round(min(0.95, 0.55 * absolute + 0.25 * separation + 0.20 * diversity), 3)
