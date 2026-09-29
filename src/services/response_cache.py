from __future__ import annotations

import hashlib
import threading
import time
import unicodedata
from collections import OrderedDict
from copy import deepcopy
from typing import Any

from src.config import get_settings
from src.services.intent import contains_sensitive_data
from src.services.knowledge_base import normalize_text


class ResponseCache:
    """Small in-process cache for public, grounded, first-turn answers."""

    def __init__(self, *, ttl_seconds: int | None = None, max_entries: int | None = None) -> None:
        settings = get_settings()
        self.ttl_seconds = ttl_seconds or settings.response_cache_ttl_seconds
        self.max_entries = max_entries or settings.response_cache_max_entries
        self._items: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
        self._lock = threading.RLock()

    @staticmethod
    def is_cacheable_query(query: str) -> bool:
        normalized = normalize_text(query)
        return 3 <= len(normalized) <= 500 and not contains_sensitive_data(query)

    @staticmethod
    def _key(query: str, namespace: str) -> str:
        # Do not erase punctuation: 2.5 and 25, or quoted instructions, differ.
        canonical = " ".join(unicodedata.normalize("NFC", query).casefold().split())
        payload = f"{namespace}\n{canonical}".encode()
        return hashlib.sha256(payload).hexdigest()

    def get(self, query: str, namespace: str) -> dict[str, Any] | None:
        if not self.is_cacheable_query(query):
            return None
        key = self._key(query, namespace)
        now = time.monotonic()
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            expires_at, value = item
            if expires_at <= now:
                del self._items[key]
                return None
            self._items.move_to_end(key)
            return deepcopy(value)

    def set(self, query: str, namespace: str, value: dict[str, Any]) -> None:
        if (not self.is_cacheable_query(query) or value.get("status") != "answered"
                or not value.get("grounded") or not value.get("citations") or value.get("handover_recommended")):
            return
        safe_value = {
            key: deepcopy(value.get(key))
            for key in (
                "intent",
                "status",
                "response",
                "reason_code",
                "confidence",
                "grounded",
                "citations",
                "warnings",
                "handover_recommended",
            )
        }
        key = self._key(query, namespace)
        with self._lock:
            self._items[key] = (time.monotonic() + self.ttl_seconds, safe_value)
            self._items.move_to_end(key)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


response_cache = ResponseCache()
