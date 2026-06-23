from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(BACKEND_DIR / ".env")

from service.aggregator import aggregate_report  # noqa: E402
from service.brand_config import get_brand_config  # noqa: E402
from service.dashboard_snapshots import persist_dashboard_snapshot  # noqa: E402
from service.inspector import _retry_failed_samples  # noqa: E402
from service.platform_registry import create_platform_clients  # noqa: E402
from service.storage import inspection_results_store, runs_store  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    parser.add_argument("--timeout-seconds", type=int, default=None)
    args = parser.parse_args()

    if args.timeout_seconds:
        os.environ["INSPECTION_TASK_TIMEOUT_SECONDS"] = str(args.timeout_seconds)
        os.environ["REQUEST_TIMEOUT_SECONDS"] = str(args.timeout_seconds)
        os.environ["CLAUDE_TIMEOUT_SECONDS"] = str(args.timeout_seconds)
    os.environ["MAX_CONCURRENCY"] = "1"

    run = runs_store.get(args.run_id)
    if not run:
        raise RuntimeError(f"run_id not found: {args.run_id}")
    brand_config = get_brand_config(run["brand_config_id"])
    if not brand_config:
        raise RuntimeError(f"brand_config_id not found: {run['brand_config_id']}")

    queryset = run.get("queryset") or {}
    results_record = inspection_results_store.get(args.run_id) or {}
    results = results_record.get("results") or []
    clients = create_platform_clients(run.get("platforms_requested") or ["claude"])
    merged = await _retry_failed_samples(args.run_id, clients, queryset.get("queries") or [], brand_config, results)

    completed = [row for row in merged if row.get("status") == "completed"]
    failed = [row for row in merged if row.get("status") == "failed"]
    quality_gate = {
        "status": "pass" if completed and len(completed) / len(merged) >= 0.8 else "failed",
        "completed_samples": len(completed),
        "failed_samples": len(failed),
        "expected_samples": len(merged),
        "completion_rate": round(len(completed) / len(merged), 4) if merged else 0,
        "minimum_completion_rate": 0.8,
        "message": f"Manual retry completed: {len(completed)}/{len(merged)} samples completed",
        "manual_retry_attempted": True,
    }
    run["inspection_quality_gate"] = quality_gate
    report = aggregate_report(run, brand_config, queryset, merged)
    run["report_data"] = report
    run["status"] = "completed"
    run["progress"] = 100
    run["message"] = "Diagnostic report completed after manual retry"
    runs_store.upsert(args.run_id, run)
    persist_dashboard_snapshot(run, report)
    print(
        json.dumps(
            {
                "run_id": args.run_id,
                "completed_samples": len(completed),
                "failed_samples": len(failed),
                "failed": [
                    {
                        "query_id": row.get("query_id"),
                        "query_text": row.get("query_text"),
                        "error_type": row.get("error_type"),
                    }
                    for row in failed
                ],
                "report_id": report.get("meta", {}).get("report_id"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
