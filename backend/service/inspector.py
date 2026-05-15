from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from uuid import uuid4

from service.aggregator import aggregate_report
from service.brand_config import get_brand_config
from service.dashboard_snapshots import persist_dashboard_snapshot
from service.platform_registry import create_platform_clients, requested_platforms
from service.queryset import generate_queryset
from service.storage import inspection_results_store, runs_store


def create_run(
    brand_config_id: str,
    queryset_strategy: str,
    inspection_mode: str,
    queryset_source: str | None = None,
    platforms: list[str] | None = None,
) -> dict:
    run_id = f"run_{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    run = {
        "run_id": run_id,
        "brand_config_id": brand_config_id,
        "queryset_strategy": queryset_strategy,
        "inspection_mode": inspection_mode,
        "queryset_source": queryset_source or "matrix_api_v1",
        "platforms": platforms,
        "inspection_batch_id": f"batch_{uuid4().hex[:12]}",
        "status": "queued",
        "progress": 0,
        "message": "Diagnostic run queued",
        "created_at": now,
        "updated_at": now,
        "report_data": None,
    }
    return runs_store.upsert(run_id, run)


async def run_diagnostic_job(run_id: str) -> None:
    run = runs_store.get(run_id)
    if not run:
        return
    try:
        brand_config = get_brand_config(run["brand_config_id"])
        if not brand_config:
            raise RuntimeError(f"brand_config_id not found: {run['brand_config_id']}")

        started = datetime.now(timezone.utc).isoformat()
        queryset = await generate_queryset(brand_config, run)
        queries = [query for query in queryset.get("queries", []) if query.get("run_scope") != "shadow"]
        if not queries:
            raise RuntimeError("QuerySet is empty; add at least one topic or industry segment.")

        platforms_requested = requested_platforms(run)
        clients = create_platform_clients(platforms_requested)

        _update_run(
            run_id,
            {
                "status": "running",
                "progress": 3,
                "message": f"Generating QuerySet and inspecting {len(platforms_requested)} platform(s)",
                "inspection_started_at": started,
                "queryset": queryset,
                "platforms_requested": platforms_requested,
            },
        )

        results = await _inspect_queries(run_id, clients, queries, brand_config, queryset["queryset_id"])
        completed_results = [r for r in results if r.get("status") == "completed"]
        failed_results = [r for r in results if r.get("status") == "failed"]

        if not completed_results:
            first_error = next((r.get("error") for r in failed_results if r.get("error")), None)
            detail = f" First failure: {first_error}" if first_error else ""
            raise RuntimeError(
                f"All {len(failed_results)} inspection results failed; no completed results to aggregate.{detail}"
            )

        completed = datetime.now(timezone.utc).isoformat()
        run = runs_store.get(run_id) or run
        run["inspection_completed_at"] = completed
        run["queryset"] = queryset
        run["status"] = "aggregating"
        run["progress"] = 92
        run["message"] = "Aggregating report_data_v1"
        run["updated_at"] = datetime.now(timezone.utc).isoformat()
        runs_store.upsert(run_id, run)

        report_data = aggregate_report(run, brand_config, queryset, completed_results)
        persisted_run = _update_run(
            run_id,
            {
                "status": "completed",
                "progress": 100,
                "message": "Diagnostic report completed",
                "inspection_completed_at": completed,
                "report_data": report_data,
            },
        )
        persist_dashboard_snapshot(persisted_run, report_data)
        _update_run(
            run_id,
            {
                "status": "completed",
                "progress": 100,
                "message": "Diagnostic report completed",
                "inspection_completed_at": completed,
                "report_data": report_data,
                "dashboard_snapshot_persisted": True,
            },
        )
    except Exception as error:
        _update_run(
            run_id,
            {
                "status": "failed",
                "progress": 100,
                "message": "Diagnostic run failed",
                "error": str(error),
                "inspection_completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )


async def _inspect_queries(
    run_id: str,
    clients: list,
    queries: list[dict],
    brand_config: dict,
    queryset_id: str,
) -> list[dict]:
    platforms = [getattr(client, "platform", str(client)) for client in clients]
    run = runs_store.get(run_id) or {}
    max_concurrency = max(1, int(os.getenv("MAX_CONCURRENCY", "4")))
    semaphore = asyncio.Semaphore(max_concurrency)
    results: list[dict] = []
    total_tasks = len(queries) * len(clients)

    async def inspect_one(client, query: dict) -> dict:
        async with semaphore:
            inspection_id = f"insp_{uuid4().hex[:12]}"
            request_at = datetime.now(timezone.utc).isoformat()
            try:
                result = await client.inspect(query, brand_config)
                returned_at = datetime.now(timezone.utc).isoformat()
                parsed = result.get("parsed", {})
                return {
                    "inspection_result_id": inspection_id,
                    "inspection_id": inspection_id,
                    "status": "completed",
                    "inspection_batch_id": run.get("inspection_batch_id"),
                    "run_id": run_id,
                    "queryset_id": queryset_id,
                    "platform": getattr(client, "platform", "unknown"),
                    "model": result.get("model", "unknown"),
                    "query_id": query["query_id"],
                    "query_text": query["query_text"],
                    "query_pattern": query.get("query_pattern"),
                    "query_layer": query.get("query_layer"),
                    "journey_stage": query.get("journey_stage"),
                    "metric_scope": query.get("metric_scope"),
                    "metric_weight": query.get("metric_weight"),
                    "matrix_cell_id": query.get("matrix_cell_id"),
                    "run_scope": query.get("run_scope"),
                    "topic": query["topic"],
                    "intent_type": query["intent_type"],
                    "started_at": request_at,
                    "completed_at": returned_at,
                    "request_at": request_at,
                    "returned_at": returned_at,
                    "raw_answer": result.get("raw_answer", ""),
                    "parsed_answer": parsed,
                    "parsed": parsed,
                    "usage": result.get("usage", {}),
                    "error_message": None,
                    "error": None,
                }
            except Exception as exc:
                returned_at = datetime.now(timezone.utc).isoformat()
                return {
                    "inspection_result_id": inspection_id,
                    "inspection_id": inspection_id,
                    "status": "failed",
                    "inspection_batch_id": run.get("inspection_batch_id"),
                    "run_id": run_id,
                    "queryset_id": queryset_id,
                    "platform": getattr(client, "platform", "unknown"),
                    "model": getattr(client, "model", "unknown"),
                    "query_id": query["query_id"],
                    "query_text": query["query_text"],
                    "query_pattern": query.get("query_pattern"),
                    "query_layer": query.get("query_layer"),
                    "journey_stage": query.get("journey_stage"),
                    "metric_scope": query.get("metric_scope"),
                    "metric_weight": query.get("metric_weight"),
                    "matrix_cell_id": query.get("matrix_cell_id"),
                    "run_scope": query.get("run_scope"),
                    "topic": query["topic"],
                    "intent_type": query["intent_type"],
                    "started_at": request_at,
                    "completed_at": returned_at,
                    "request_at": request_at,
                    "returned_at": returned_at,
                    "raw_answer": "",
                    "parsed_answer": {},
                    "parsed": {},
                    "usage": {},
                    "error_message": str(exc),
                    "error": str(exc),
                }

    tasks = [asyncio.create_task(inspect_one(client, query)) for client in clients for query in queries]
    try:
        for index, task in enumerate(asyncio.as_completed(tasks), start=1):
            result = await task
            results.append(result)
            inspection_results_store.upsert(
                run_id,
                {
                    "run_id": run_id,
                    "results": results,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            progress = 5 + round(index / total_tasks * 85)
            platform_names = ", ".join(platforms)
            _update_run(
                run_id,
                {
                    "status": "running",
                    "progress": min(progress, 90),
                    "message": f"Inspecting {index}/{total_tasks} (platforms: {platform_names})",
                },
            )
    except Exception:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    return results


def _update_run(run_id: str, patch: dict) -> dict:
    run = runs_store.get(run_id)
    if not run:
        raise RuntimeError(f"run_id not found: {run_id}")
    run.update(patch)
    run["updated_at"] = datetime.now(timezone.utc).isoformat()
    return runs_store.upsert(run_id, run)


def get_run(run_id: str) -> dict | None:
    return runs_store.get(run_id)


def get_report(run_id: str) -> dict | None:
    run = runs_store.get(run_id)
    if not run:
        return None
    report = run.get("report_data")
    return report if isinstance(report, dict) else None


def latest_completed_run() -> dict | None:
    runs = runs_store.read().values()
    completed = [run for run in runs if isinstance(run, dict) and run.get("status") == "completed"]
    if not completed:
        return None
    return sorted(completed, key=lambda item: item.get("updated_at", ""), reverse=True)[0]
