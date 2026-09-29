"""Read-only official source checks; write only a local change-detection report."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from src.services.knowledge_base import get_knowledge_base  # noqa: E402
from src.services.source_monitor import fetch_digest, monitor_path, monitor_report, observation  # noqa: E402


async def run(args: argparse.Namespace) -> int:
    path = args.output or monitor_path()
    report = monitor_report(path)
    if report.get("error"):
        print(json.dumps(report))
        return 2
    sources = report.setdefault("sources", {})
    if args.approve:
        item = sources.get(args.approve)
        if not item or not args.expected_sha256 or item.get("last_sha256") != args.expected_sha256:
            print("Approval requires the source ID and exact last observed SHA256 after human review.")
            return 2
        item.update(baseline_sha256=args.expected_sha256, state="reviewed_baseline", review_required=False)
    else:
        knowledge = get_knowledge_base()
        if not knowledge.ready:
            print("Canonical data unavailable; cannot identify approved source URLs.")
            return 2
        selected = list(knowledge.sources.values())
        if args.source:
            selected = [s for s in selected if s.source_id in args.source]
        if args.limit:
            selected = selected[:args.limit]
        report["dataset_fingerprint"] = knowledge.fingerprint
        async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "VinUni-Admissions-SourceMonitor/1.0"}) as client:
            for source in selected:
                digest, error = None, None
                try:
                    digest = await fetch_digest(source.url, client)
                except (httpx.HTTPError, ValueError) as exc:
                    # No response bodies, credentials or raw documents in error output.
                    error = type(exc).__name__
                sources[source.source_id] = {
                    **observation(sources.get(source.source_id, {}), digest=digest, error=error),
                    "url": source.url,
                }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    print(json.dumps({"checked_sources": len(sources), "review_required": [sid for sid, item in sources.items()
                      if item.get("review_required")], "report": str(path)}, ensure_ascii=False, indent=2))
    return 1 if any(item.get("review_required") for item in sources.values()) else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", action="append")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--approve", help="Source ID manually checked by the data owner")
    parser.add_argument("--expected-sha256", help="Exact digest being approved, prevents blind approval")
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
