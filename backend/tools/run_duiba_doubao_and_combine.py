from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(BACKEND_DIR / ".env")

from service.aggregator import aggregate_report  # noqa: E402
from service.brand_config import get_brand_config  # noqa: E402
from service.dashboard_snapshots import persist_dashboard_snapshot  # noqa: E402
from service.inspector import create_run, run_diagnostic_job  # noqa: E402
from service.storage import inspection_results_store, runs_store  # noqa: E402


DEFAULT_GPT_RUN_ID = "run_2d6813904ab5"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _quality_gate(results: list[dict]) -> dict:
    completed = len([row for row in results if row.get("status") == "completed"])
    failed = len([row for row in results if row.get("status") == "failed"])
    expected = completed + failed
    completion_rate = round(completed / expected, 4) if expected else 0
    return {
        "status": "pass" if completed and completion_rate >= 0.8 else "failed",
        "completed_samples": completed,
        "failed_samples": failed,
        "expected_samples": expected,
        "completion_rate": completion_rate,
        "minimum_completion_rate": 0.8,
        "message": f"Combined inspection quality gate: {completed}/{expected} samples completed",
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpt-run-id", default=DEFAULT_GPT_RUN_ID)
    parser.add_argument("--timeout-seconds", type=int, default=240)
    parser.add_argument("--max-concurrency", type=int, default=1)
    args = parser.parse_args()

    os.environ["INSPECTION_TASK_TIMEOUT_SECONDS"] = str(args.timeout_seconds)
    os.environ["REQUEST_TIMEOUT_SECONDS"] = str(args.timeout_seconds)
    os.environ["DOUBAO_TIMEOUT_SECONDS"] = str(args.timeout_seconds)
    os.environ["MAX_CONCURRENCY"] = str(args.max_concurrency)

    gpt_run = runs_store.get(args.gpt_run_id)
    if not gpt_run:
        raise RuntimeError(f"gpt run not found: {args.gpt_run_id}")
    queryset = gpt_run.get("queryset")
    if not isinstance(queryset, dict) or not queryset.get("queryset_id"):
        raise RuntimeError(f"gpt run has no reusable queryset: {args.gpt_run_id}")

    doubao_run = create_run(
        brand_config_id=gpt_run["brand_config_id"],
        queryset_strategy="rule_matrix_v1",
        inspection_mode="multi_platform_live_v1",
        queryset_source="matrix_api_v1",
        queryset_policy="reuse_latest",
        base_queryset_id=queryset["queryset_id"],
        queryset_change_reason="doubao_platform_inspection_for_gpt_doubao_combined_report",
        queryset_approved_by="user",
        platforms=["豆包"],
        web_search_enabled=True,
        llm_options={
            "two_round_inspection": False,
            "web_search_mode": "doubao_plugins",
        },
    )
    await run_diagnostic_job(doubao_run["run_id"])
    doubao_run = runs_store.get(doubao_run["run_id"]) or doubao_run
    if doubao_run.get("status") != "completed":
        print(json.dumps({"doubao_run": doubao_run}, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    brand_config = get_brand_config(gpt_run["brand_config_id"])
    if not brand_config:
        raise RuntimeError(f"brand_config not found: {gpt_run['brand_config_id']}")

    gpt_results = (inspection_results_store.get(args.gpt_run_id) or {}).get("results") or []
    doubao_results = (inspection_results_store.get(doubao_run["run_id"]) or {}).get("results") or []
    combined_results = [*gpt_results, *doubao_results]
    combined_run_id = f"run_duiba_gpt_doubao_{uuid4().hex[:12]}"
    now = _now()
    combined_run = {
        "run_id": combined_run_id,
        "brand_config_id": gpt_run["brand_config_id"],
        "queryset_strategy": "rule_matrix_v1",
        "inspection_mode": "multi_platform_live_v1",
        "queryset_source": "matrix_api_v1",
        "queryset_policy": "reuse_latest",
        "base_queryset_id": queryset["queryset_id"],
        "queryset_change_reason": "combined_gpt_doubao_report_from_existing_gpt_and_doubao_runs",
        "queryset_approved_by": "user",
        "generation_constraints": {},
        "platforms": ["GPT", "豆包"],
        "platforms_requested": ["GPT", "豆包"],
        "llm_provider": "GPT+豆包",
        "web_search_enabled": True,
        "llm_options": {
            "two_round_inspection": False,
            "web_search_modes": {
                "GPT": "responses_web_search",
                "豆包": "doubao_plugins",
            },
        },
        "inspection_batch_id": f"batch_{uuid4().hex[:12]}",
        "status": "completed",
        "progress": 100,
        "message": "Combined GPT and Doubao diagnostic report completed",
        "created_at": now,
        "updated_at": now,
        "inspection_started_at": gpt_run.get("inspection_started_at") or doubao_run.get("inspection_started_at"),
        "inspection_completed_at": now,
        "queryset": queryset,
        "inspection_quality_gate": _quality_gate(combined_results),
    }
    report_data = aggregate_report(combined_run, brand_config, queryset, combined_results)
    report_data["lineage"]["platforms_requested"] = ["GPT", "豆包"]
    report_data["lineage"]["llm_provider"] = "GPT+豆包"
    report_data["lineage"]["source_runs"] = {
        "GPT": args.gpt_run_id,
        "豆包": doubao_run["run_id"],
    }
    combined_run["report_data"] = report_data
    runs_store.upsert(combined_run_id, combined_run)
    inspection_results_store.upsert(
        combined_run_id,
        {
            "run_id": combined_run_id,
            "results": combined_results,
            "source_runs": {
                "GPT": args.gpt_run_id,
                "豆包": doubao_run["run_id"],
            },
            "updated_at": now,
        },
    )
    persist_dashboard_snapshot(combined_run, report_data)
    print(
        json.dumps(
            {
                "gpt_run_id": args.gpt_run_id,
                "doubao_run_id": doubao_run["run_id"],
                "combined_run_id": combined_run_id,
                "queryset_id": queryset["queryset_id"],
                "doubao_status": doubao_run.get("status"),
                "doubao_quality_gate": doubao_run.get("inspection_quality_gate"),
                "combined_quality_gate": combined_run["inspection_quality_gate"],
                "report_id": report_data.get("meta", {}).get("report_id"),
                "platforms": report_data.get("lineage", {}).get("platforms_requested"),
                "completed_samples": report_data.get("audit", {}).get("completed_samples"),
                "expected_samples": report_data.get("audit", {}).get("expected_samples"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
