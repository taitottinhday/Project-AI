from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from src.config import get_settings

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "at",
    "be",
    "by",
    "cho",
    "co",
    "cua",
    "duoc",
    "em",
    "gi",
    "how",
    "i",
    "in",
    "is",
    "la",
    "mot",
    "nao",
    "nhung",
    "of",
    "or",
    "the",
    "thi",
    "to",
    "toi",
    "trong",
    "va",
    "ve",
    "what",
    "with",
}

QUERY_EXPANSIONS = {
    "hoc phi": {"tuition", "fee", "fees", "chi phi", "financial"},
    "chi phi": {"tuition", "fee", "fees", "hoc phi", "financial"},
    "hoc bong": {"scholarship", "financial aid", "award", "ho tro tai chinh"},
    "ho tro tai chinh": {"financial aid", "scholarship", "need based"},
    "nganh": {"program", "programs", "degree", "major", "chuong trinh"},
    "chuong trinh": {"program", "programs", "degree", "major", "nganh"},
    "ky tuc xa": {"dormitory", "residential", "housing", "noi tru"},
    "noi tru": {"dormitory", "residential", "housing", "ky tuc xa"},
    "tuyen sinh": {"admissions", "application", "applicant", "ung tuyen"},
    "nop ho so": {"application", "checklist", "admissions", "deadline"},
    "han nop": {"deadline", "closes", "application round"},
    "diem": {"grade", "grading", "gpa", "assessment"},
    "tin chi": {"credit", "credits", "course load"},
    "tot nghiep": {"graduation", "degree conferral", "award"},
    "nghi hoc": {"leave", "withdrawal", "return"},
    "phuc khao": {"grade appeal", "appeal"},
    "trao doi": {"exchange", "outbound", "credit transfer"},
    "thuc tap": {"internship", "placement"},
    "visa": {"study visa", "international student"},
    "khieu nai": {"complaint", "appeal", "escalation"},
    "tri tue nhan tao": {"genai", "generative artificial intelligence", "chatgpt"},
    # Vietnamese applicant phrasing -> canonical English policy headings.
    # These are retrieval aliases only; they never add factual content.
    "lien he": {"contact", "hotline", "email", "address"},
    "khoan vay": {"student loan", "financing", "interest", "repayment", "collateral"},
    "lai suat": {"interest", "subsidized", "rate"},
    "thu vien": {"library", "overdue", "material", "equipment"},
    "phi phat": {"overdue", "damage", "lost", "fee"},
    "hoan hoc phi": {"refund", "withdraw", "processing fee"},
    "quy che hoc vu": {"academic regulations", "academic", "regulations"},
    "phien ban": {"version"},
    "hieu luc": {"effective", "updated"},
    "ap dung cho ai": {"applies", "students"},
    "doi tuong ap dung": {"applies", "students"},
    "doi tuong": {"applies", "students"},
    "ngon ngu giang day": {"language", "instruction", "english"},
    "mot nam hoc": {"academic year", "semester", "fall", "spring"},
    "thoi gian hoc toi da": {"maximum candidature", "four year", "semester"},
    "danh sach dean": {"deans list", "sgpa"},
    "quy tac diem": {"grading", "gpa", "grade"},
    "bao luu": {"leave", "withdrawal", "return"},
    "dieu chinh hoc tap": {"academic accommodation", "eligible", "adjustment"},
    "quy tac ung xu": {"student code", "conduct", "responsibilities"},
    "thong tin noi bo": {"public", "internal", "information"},
}

SOURCE_PRIORITY = {
    "official_policy_pdf": 1.25,
    "official_policy_webpage": 1.22,
    "official_procedure_webpage": 1.20,
    "official_guideline_webpage": 1.18,
    "official_curriculum_pdf": 1.18,
    "official_catalog_index": 1.10,
    "official_dated_announcement": 1.08,
    "official_program_webpage": 1.05,
    "official_webpage": 1.0,
    "official_faq": 0.88,
}


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFD", value.lower())
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    # Vietnamese đ/Đ is a separate letter, not a base character plus combining
    # mark, so NFD does not turn it into d. Normalize it explicitly before the
    # ASCII token regex; otherwise phrases such as "trao đổi" become "trao oi".
    value = value.replace("đ", "d")
    return " ".join(TOKEN_RE.findall(value))


def tokenize(value: str) -> list[str]:
    return [token for token in normalize_text(value).split() if token not in STOPWORDS and len(token) > 1]


def _humanize(key: str) -> str:
    return key.replace("_", " ")


def _identifier(value: Any, fallback: str) -> str:
    if not isinstance(value, dict):
        return fallback
    for key in ("name_vi", "name", "title", "label_vi", "id", "topic", "classification", "round", "level"):
        if value.get(key):
            return str(value[key])
    return fallback


def _collect_source_ids(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if (key == "source_ids" or key.endswith("_source_ids")) and isinstance(child, list):
                found.update(item for item in child if isinstance(item, str))
            found.update(_collect_source_ids(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_collect_source_ids(child))
    return found


def _render(value: Any, prefix: str = "", depth: int = 0) -> list[str]:
    if depth > 6:
        return [f"{prefix}: {json.dumps(value, ensure_ascii=False)}"]
    if isinstance(value, dict):
        lines: list[str] = []
        for key, child in value.items():
            if key == "source_ids":
                continue
            label = f"{prefix} > {_humanize(key)}" if prefix else _humanize(key)
            if isinstance(child, (dict, list)):
                lines.extend(_render(child, label, depth + 1))
            else:
                lines.append(f"{label}: {child}")
        return lines
    if isinstance(value, list):
        lines = []
        for index, child in enumerate(value, 1):
            label = f"{prefix} [{index}]"
            if isinstance(child, (dict, list)):
                lines.extend(_render(child, label, depth + 1))
            else:
                lines.append(f"{label}: {child}")
        return lines
    return [f"{prefix}: {value}"]


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    title: str
    url: str
    source_type: str
    published_or_updated: str | None = None
    version: str | None = None
    warning: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> SourceRecord:
        return cls(
            source_id=value["id"],
            title=value.get("title", value["id"]),
            url=value["url"],
            source_type=value.get("source_type", "official_webpage"),
            published_or_updated=(
                value.get("effective_date") or value.get("published_or_updated") or value.get("document_version")
            ),
            version=value.get("version") or value.get("reference_number"),
            warning=value.get("warning"),
        )


@dataclass(frozen=True)
class EvidenceChunk:
    chunk_id: str
    document: str
    section: str
    text: str
    source_ids: tuple[str, ...]
    tokens: tuple[str, ...]
    flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class SearchHit:
    chunk: EvidenceChunk
    score: float


@dataclass
class KnowledgeBase:
    root: Path
    sources: dict[str, SourceRecord] = field(default_factory=dict)
    chunks: list[EvidenceChunk] = field(default_factory=list)
    document_frequencies: Counter[str] = field(default_factory=Counter)
    dataset_id: str | None = None
    academic_year: str | None = None
    verified_as_of: str | None = None
    document_count: int = 0
    load_errors: list[str] = field(default_factory=list)
    programs: list[dict] = field(default_factory=list)
    fingerprint: str = ""
    file_signatures: dict[str, tuple[int, int]] = field(default_factory=dict)

    def load(self) -> None:
        self.sources.clear()
        self.chunks.clear()
        self.document_frequencies.clear()
        self.load_errors.clear()
        self.programs.clear()
        self.document_count = 0
        self.file_signatures.clear()
        self.fingerprint = ""

        manifest_path = self.root / "vinuni_undergraduate_2026_2027_manifest.json"
        source_path = self.root / "sources" / "vinuni_official_sources_2026_2027.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            source_payload = json.loads(source_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.load_errors.append(f"Không thể nạp manifest/source registry: {exc}")
            return

        self.dataset_id = manifest.get("dataset_id")
        self.academic_year = manifest.get("academic_year")
        self.verified_as_of = manifest.get("verified_as_of")
        self.sources = {source["id"]: SourceRecord.from_dict(source) for source in source_payload.get("sources", [])}
        for source in self.sources.values():
            parsed = urlparse(source.url)
            if (parsed.scheme != "https" or not parsed.hostname
                    or not (parsed.hostname == "vinuni.edu.vn" or parsed.hostname.endswith(".vinuni.edu.vn"))
                    or parsed.username or parsed.password or parsed.port not in (None, 443)):
                self.load_errors.append(f"Nguồn không thuộc tên miền chính thức: {source.source_id}")

        digest = hashlib.sha256()
        for path in (manifest_path, source_path):
            digest.update(path.read_bytes())
            self.file_signatures[str(path)] = (path.stat().st_mtime_ns, path.stat().st_size)

        data_files = [item for item in manifest.get("files", []) if not item.startswith("sources/")]
        for relative in data_files:
            path = (self.root / relative).resolve()
            if not path.is_relative_to(self.root.resolve()):
                self.load_errors.append(f"Đường dẫn ngoài kho dữ liệu: {relative}")
                continue
            try:
                raw = path.read_bytes()
                payload = json.loads(raw)
                digest.update(relative.encode())
                digest.update(raw)
                self.file_signatures[str(path)] = (path.stat().st_mtime_ns, path.stat().st_size)
                unknown = _collect_source_ids(payload) - self.sources.keys()
                if unknown:
                    self.load_errors.append(f"{relative}: source ID không tồn tại: {sorted(unknown)}")
                if relative.startswith("programs/"):
                    self.programs.extend(payload.get("programs", []))
                self._add_document(relative, payload)
                self.document_count += 1
            except (OSError, json.JSONDecodeError) as exc:
                self.load_errors.append(f"{relative}: {exc}")

        for chunk in self.chunks:
            self.document_frequencies.update(set(chunk.tokens))
        self.fingerprint = digest.hexdigest()

    def files_changed(self) -> bool:
        try:
            return any((Path(p).stat().st_mtime_ns, Path(p).stat().st_size) != signature
                       for p, signature in self.file_signatures.items())
        except OSError:
            return True

    @property
    def ready(self) -> bool:
        return bool(self.sources and self.chunks) and not self.load_errors

    def _add_document(self, document: str, payload: dict[str, Any]) -> None:
        metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
        metadata_ids = set(metadata.get("source_ids", [])) if isinstance(metadata, dict) else set()
        all_document_ids = _collect_source_ids(payload)

        for key, value in payload.items():
            if key in {"metadata", "source_ids"}:
                continue
            sibling_ids = payload.get(f"{key}_source_ids", [])
            base_ids = metadata_ids | set(sibling_ids)
            if not base_ids and len(all_document_ids) <= 5:
                base_ids = all_document_ids
            self._chunk_value(document, _humanize(key), value, base_ids, depth=0)

    def _chunk_value(
        self,
        document: str,
        section: str,
        value: Any,
        inherited_ids: set[str],
        depth: int,
    ) -> None:
        local_ids = set(inherited_ids)
        if isinstance(value, dict):
            local_ids.update(value.get("source_ids", []))
        descendant_ids = _collect_source_ids(value)
        if len(descendant_ids) <= 5:
            local_ids.update(descendant_ids)

        # A record can contain both ordinary facts and one explicitly disputed
        # field. Keep that disputed field isolated: a conflict about a program
        # code must not make the program name/duration unusable, while a direct
        # question about the code must still fail closed. The same rule applies
        # to the documented leave-return deadline conflict.
        if isinstance(value, dict) and value.get("status") == "confirmed_current_with_code_conflict":
            disputed_keys = {"program_code", "program_code_status", "status", "data_note"}
            safe_value = {key: child for key, child in value.items() if key not in disputed_keys}
            disputed_value = {key: child for key, child in value.items() if key in disputed_keys}
            self._append_chunk(document, section, safe_value, local_ids)
            self._append_chunk(document, f"{section} > disputed program code", disputed_value, local_ids)
            return
        if isinstance(value, dict) and "return_deadline_conflict" in value:
            safe_value = {key: child for key, child in value.items() if key != "return_deadline_conflict"}
            self._append_chunk(document, section, safe_value, local_ids)
            self._append_chunk(
                document,
                f"{section} > disputed return deadline",
                {"return_deadline_conflict": value["return_deadline_conflict"]},
                local_ids,
            )
            return

        # Lists of records are independent facts. Keeping them in one chunk can
        # mix a safe record with an unresolved/restricted one and weakens both
        # retrieval precision and status handling.
        if isinstance(value, list) and len(value) > 1 and any(isinstance(child, (dict, list)) for child in value):
            for index, child in enumerate(value, 1):
                child_name = _humanize(_identifier(child, str(index)))
                self._chunk_value(document, f"{section} > {child_name}", child, local_ids, depth + 1)
            return

        serialized_length = len(json.dumps(value, ensure_ascii=False))
        if serialized_length <= 3200 or depth >= 4 or not isinstance(value, (dict, list)):
            self._append_chunk(document, section, value, local_ids)
            return

        if isinstance(value, list):
            for index, child in enumerate(value, 1):
                child_name = _humanize(_identifier(child, str(index)))
                self._chunk_value(document, f"{section} > {child_name}", child, local_ids, depth + 1)
            return

        for key, child in value.items():
            if key == "source_ids" or key.endswith("_source_ids"):
                continue
            sibling_ids = value.get(f"{key}_source_ids", [])
            child_ids = local_ids | set(sibling_ids)
            self._chunk_value(document, f"{section} > {_humanize(key)}", child, child_ids, depth + 1)

    def _append_chunk(self, document: str, section: str, value: Any, source_ids: set[str]) -> None:
        valid_ids = tuple(sorted(source_id for source_id in source_ids if source_id in self.sources))
        if not valid_ids:
            return
        lines = _render(value)
        rendered_value = "\n".join(lines)
        text = f"Tài liệu: {document}\nMục: {section}\n" + rendered_value
        # Status flags belong to the record itself. Inspecting the section name
        # (for example "known gaps or dynamic topics") would incorrectly mark
        # every child record as dynamic.
        normalized = normalize_text(rendered_value)
        flag_phrases = {
            "draft": ("draft",),
            "tentative": ("tentative",),
            "unresolved": ("unresolved",),
            "not_publicly_verified": ("not publicly verified", "not publicly final"),
            "restricted": ("restricted", "internal or restricted"),
            "dynamic": ("dynamic", "authenticated dynamic"),
            "conflict": ("official source conflict", "deadline conflict", "code conflict"),
        }
        flags = [flag for flag, phrases in flag_phrases.items() if any(phrase in normalized for phrase in phrases)]
        chunk_id = f"{Path(document).stem}:{len(self.chunks) + 1}"
        self.chunks.append(
            EvidenceChunk(
                chunk_id=chunk_id,
                document=document,
                section=section,
                text=text,
                source_ids=valid_ids,
                tokens=tuple(tokenize(text)),
                flags=tuple(flags),
            )
        )

    def search(self, query: str, top_k: int = 6) -> list[SearchHit]:
        if not self.chunks:
            return []
        normalized_query = normalize_text(query)
        expanded = list(tokenize(query))
        for phrase, terms in QUERY_EXPANSIONS.items():
            if phrase in normalized_query:
                for term in terms:
                    expanded.extend(tokenize(term))
        query_counts = Counter(expanded)
        if not query_counts:
            return []

        total_docs = len(self.chunks)
        average_length = sum(len(chunk.tokens) for chunk in self.chunks) / max(total_docs, 1)
        hits: list[SearchHit] = []
        for chunk in self.chunks:
            frequencies = Counter(chunk.tokens)
            score = 0.0
            for term, query_frequency in query_counts.items():
                tf = frequencies.get(term, 0)
                if not tf:
                    continue
                df = self.document_frequencies.get(term, 0)
                idf = math.log(1 + (total_docs - df + 0.5) / (df + 0.5))
                denominator = tf + 1.2 * (1 - 0.75 + 0.75 * len(chunk.tokens) / max(average_length, 1))
                score += idf * (tf * 2.2 / denominator) * min(query_frequency, 2)

            section_normalized = normalize_text(chunk.section)
            for phrase in QUERY_EXPANSIONS:
                if phrase in normalized_query and any(token in section_normalized for token in tokenize(phrase)):
                    score += 1.2
            if normalized_query and normalized_query in normalize_text(chunk.text):
                score += 3.0

            priority = max(
                (SOURCE_PRIORITY.get(self.sources[source_id].source_type, 1.0) for source_id in chunk.source_ids),
                default=1.0,
            )
            score *= priority
            if score > 0:
                hits.append(SearchHit(chunk=chunk, score=round(score, 4)))

        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:top_k]


_knowledge_base: KnowledgeBase | None = None


def get_knowledge_base(*, reload: bool = False) -> KnowledgeBase:
    global _knowledge_base
    if _knowledge_base is None or reload or _knowledge_base.files_changed():
        settings = get_settings()
        _knowledge_base = KnowledgeBase(settings.resolved_knowledge_base_dir)
        _knowledge_base.load()
    return _knowledge_base
