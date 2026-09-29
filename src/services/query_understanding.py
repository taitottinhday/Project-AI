"""Conservative query interpretation; preferences/history never become evidence."""
from __future__ import annotations

import re

from src.services.knowledge_base import get_knowledge_base, normalize_text

ALIASES = {
    "tuition fees": "hoc phi", "tuition": "hoc phi", "scholarships": "hoc bong",
    "scholarship": "hoc bong", "application deadline": "han nop ho so",
    "dormitory fees": "phi ky tuc xa", "international exchange": "trao doi quoc te",
    "exchange requirements": "dieu kien trao doi", "requirements for exchange": "dieu kien trao doi",
    "undergraduate programs": "cac nganh dai hoc", "computer science": "khoa hoc may tinh",
    "nursing": "dieu duong", "medical doctor": "bac si y khoa", "ktx": "ky tuc xa",
    "cntt": "khoa hoc may tinh", "hoc phi bn": "hoc phi bao nhieu", "bn": "bao nhieu",
    "how much": "bao nhieu",
}
REFERENCE_PHRASES = (
    "nganh nay", "nganh do", "chuong trinh nay", "chuong trinh do", "cai do", "cai nay",
    "muc do", "muc nay", "con no", "theo hoc ky", "theo nam", "thi sao", "what about",
    "that program", "this program", "it cost",
)


def has_phrase(text: str, phrase: str) -> bool:
    return f" {phrase} " in f" {text} "


def normalize_query(query: str) -> str:
    value = normalize_text(query)
    for phrase, canonical in ALIASES.items():
        value = re.sub(rf"(?<!\w){re.escape(phrase)}(?!\w)", canonical, value)
    return value


def named_programs(query: str) -> list[dict]:
    text = normalize_query(query)
    matches = []
    for program in get_knowledge_base().programs:
        name = normalize_text(program["name_vi"])
        short = re.sub(r"^(cu nhan|bac si) ", "", name)
        english = normalize_query(program.get("degree_name_en", ""))
        if has_phrase(text, short) or (english and has_phrase(text, english)):
            matches.append(program)
    return matches


def needs_reference(query: str) -> bool:
    text = normalize_query(query)
    return any(has_phrase(text, phrase) for phrase in REFERENCE_PHRASES) or text in {"no", "con no", "the thi sao"}


def resolve_reference(query: str, context: str) -> str:
    if not context:
        return query
    previous = [line.removeprefix("Người dùng: ") for line in context.splitlines()
                if line.startswith("Người dùng: ")]
    if not previous:
        return query
    prior = previous[-1]
    current_programs = named_programs(query)
    # Switching to a named program must not carry the previous program's fee.
    if current_programs and needs_reference(query):
        topic = "Học phí" if "hoc phi" in normalize_query(prior) else ""
        return f"{topic} {query} bao nhieu".strip() if topic else query
    if needs_reference(query):
        # A list or greeting does not establish a unique program reference.
        prior_programs = named_programs(prior)
        if any(has_phrase(normalize_query(query), p) for p in ("nganh nay", "nganh do", "chuong trinh nay", "chuong trinh do")):
            return f"{prior} {query}" if len(prior_programs) == 1 else query
        if "hoc phi" in normalize_query(prior) and len(prior_programs) == 1:
            return f"{prior} {query}"
        return query
    # Complete an explicit clarification such as 'Ngành đó học phí bao nhiêu?' -> 'Điều dưỡng'.
    if current_programs and needs_reference(prior) and "hoc phi" in normalize_query(prior):
        return f"Học phí {query} bao nhiêu?"
    return query
