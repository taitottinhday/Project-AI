from __future__ import annotations

import math
import threading
import time
from collections import deque

from fastapi import HTTPException, Request

from src.config import get_settings


class RateLimiter:
    """Bounded single-process sliding window; proxy IP trust belongs to deployment."""

    def __init__(self) -> None:
        self.entries: dict[str, deque[float]] = {}
        self.lock = threading.Lock()

    def check(self, key: str, limit: int, *, now: float | None = None) -> int:
        now = time.monotonic() if now is None else now
        with self.lock:
            expired = [k for k, values in self.entries.items() if not values or values[-1] <= now - 60]
            for k in expired:
                del self.entries[k]
            if key not in self.entries and len(self.entries) >= 10000:
                return 60
            window = self.entries.setdefault(key, deque())
            while window and window[0] <= now - 60:
                window.popleft()
            if len(window) >= limit:
                return max(1, math.ceil(60 - (now - window[0])))
            window.append(now)
            return 0

    def clear(self) -> None:
        with self.lock:
            self.entries.clear()


limiter = RateLimiter()


def enforce_rate_limit(request: Request) -> None:
    if request.method not in {"POST", "PUT", "PATCH"}:
        return
    client = request.client.host if request.client else "unknown"
    path = request.url.path
    category = "handover" if path.endswith("/handover") else "requests"
    limit = 5 if category == "handover" else get_settings().rate_limit_per_minute
    retry_after = limiter.check(f"{client}:{category}", limit)
    if retry_after:
        raise HTTPException(429, "Bạn gửi yêu cầu quá nhanh. Vui lòng chờ rồi thử lại.", headers={"Retry-After": str(retry_after)})
