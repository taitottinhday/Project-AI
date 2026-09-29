"""Detect upstream byte changes; never promote fetched content to canonical facts."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx

from src.config import get_settings


def allowed_source_url(url: str) -> bool:
    parsed = urlparse(url)
    try:
        return (parsed.scheme == "https" and bool(parsed.hostname)
                and (parsed.hostname == "vinuni.edu.vn" or parsed.hostname.endswith(".vinuni.edu.vn"))
                and parsed.port in (None, 443) and not parsed.username and not parsed.password)
    except ValueError:
        return False


async def fetch_digest(url: str, client: httpx.AsyncClient) -> str:
    for _ in range(5):
        if not allowed_source_url(url):
            raise ValueError("non_official_redirect")
        async with client.stream("GET", url, follow_redirects=False) as response:
            if response.is_redirect:
                url = urljoin(url, response.headers.get("location", ""))
                continue
            response.raise_for_status()
            digest = hashlib.sha256()
            size = 0
            async for part in response.aiter_bytes():
                size += len(part)
                if size > 16 * 1024 * 1024:
                    raise ValueError("source_too_large")
                digest.update(part)
            if not size:
                raise ValueError("empty_source")
            return digest.hexdigest()
    raise ValueError("too_many_redirects")


def observation(previous: dict, *, digest: str | None, error: str | None = None) -> dict:
    baseline = previous.get("baseline_sha256")
    state = "unavailable" if error else "first_observation" if not baseline else "unchanged" if digest == baseline else "changed"
    return {
        "baseline_sha256": baseline or digest, "last_sha256": digest, "state": state,
        "checked_at": datetime.now(UTC).isoformat(), "error": error,
        "review_required": state in {"changed", "unavailable"},
    }


def monitor_path() -> Path:
    return get_settings().sqlite_path.parent / "source_monitor.json"


def monitor_report(path: Path | None = None) -> dict:
    path = path or monitor_path()
    if not path.exists():
        return {"sources": {}, "note": "Chưa có lần kiểm tra thay đổi nguồn."}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"sources": {}, "error": "monitor_report_unreadable"}


def blocked_source_ids() -> set[str]:
    report = monitor_report()
    return {key for key, item in report.get("sources", {}).items() if item.get("review_required")}
