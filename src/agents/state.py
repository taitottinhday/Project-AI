from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    query: str
    retrieval_query: str
    session_context: str
    intent: str
    hits: list[Any]
    confidence: float
    draft: Any
    status: str
    response: str
    reason_code: str
    citations: list[dict]
    warnings: list[str]
    grounded: bool
    handover_recommended: bool
    short_circuit: bool
    error: str
