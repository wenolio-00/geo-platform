from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from uuid import uuid4

from service.aggregator import aggregate_report
from service.brand_config import get_brand_config
from service.dashboard_snapshots import persist_dashboard_snapshot
from service.platform_registry import create_platform_clients, requested_platforms, validate_platform_clients
from service.queryset import QuerySetGenerationFailed, generate_queryset
from service.queryset_library import (
    active_queries_from,
    latest_frozen_queryset,
    normalize_queryset_snapshot,
    persist_frozen_queryset,
    validate_queryset_for_production,
)
from service.storage import inspection_results_store, runs_store


DEFAULT_INSPECTION_TASK_TIMEOUT_SECONDS = 90
DEFAULT_MIN_INSPECTION_COMPLETION_RATE = 0.8
ACTIVE_RUN_STATUSES = {"queued", "running", "aggregating"}
INTERRUPTED_MESSAGE = "Diagnostic run interrupted by server restart"
INTERRUPTED_ERROR = "Background task was lost during process restart/reload before completion."


def create_run(
    brand_config_id: str,
    queryset_strategy: str,
    inspection_mode: str,
    queryset_source: str | None = None,
    platforms: list[str] | None = None,
    queryset_policy: str = "reuse_latest",
    base_queryset_id: str | None = None,
    queryset_change_reason: str | None = None,
    queryset_approved_by: str | None = None,
    generation_constraints: dict | None = None,
    llm_provider: str | None = None,
    web_search_enabled: bool = True,
    llm_options: dict | None = None,
) -> dict:
    run_id = f"run_{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    run = {
        "run_id": run_id,
        "brand_config_id": brand_config_id,
        "queryset_strategy": queryset_strategy,
        "inspection_mode": inspection_mode,
        "queryset_source": queryset_source or "matrix_api_v1",
        "queryset_policy": queryset_policy,
        "base_queryset_id": base_queryset_id,
        "queryset_change_reason": queryset_change_reason,
        "queryset_approved_by": queryset_approved_by,
        "generation_constraints": generation_constraints or {},
        "platforms": platforms,
        "llm_provider": llm_provider,
        "web_search_enabled": web_search_enabled,
        "llm_options": llm_options or {},
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
        platforms_requested = requested_platforms(run)
        clients = create_platform_clients(platforms_requested)
        validate_platform_clients(clients)

        queryset = await resolve_queryset(brand_config, run)
        queryset = validate_queryset_for_production(queryset)
        queries = active_queries_from(queryset)

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

        results = await _inspect_queries(run_id, clients, queries, brand_config)
        completed_results = [r for r in results if r.get("status") == "completed"]
        failed_results = [r for r in results if r.get("status") == "failed"]

        quality_gate = _inspection_quality_gate(completed_results, failed_results)
        if quality_gate["status"] != "pass":
            first_error = next((r.get("error") for r in failed_results if r.get("error")), None)
            detail = f" First failure: {first_error}" if first_error else ""
            raise RuntimeError(f"{quality_gate['message']}.{detail}")

        completed = datetime.now(timezone.utc).isoformat()
        run = runs_store.get(run_id) or run
        run["inspection_completed_at"] = completed
        run["queryset"] = queryset
        run["inspection_quality_gate"] = quality_gate
        run["status"] = "aggregating"
        run["progress"] = 92
        run["message"] = "Aggregating report_data_v1"
        run["updated_at"] = datetime.now(timezone.utc).isoformat()
        runs_store.upsert(run_id, run)

        queryset = validate_queryset_for_production(queryset)
        report_data = aggregate_report(run, brand_config, queryset, results)
        persisted_run = _update_run(
            run_id,
            {
                "status": "completed",
                "progress": 100,
                "message": "Diagnostic report completed",
                "inspection_completed_at": completed,
                "inspection_quality_gate": quality_gate,
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
                "inspection_quality_gate": quality_gate,
                "report_data": report_data,
                "dashboard_snapshot_persisted": True,
            },
        )
    except asyncio.CancelledError:
        _mark_run_interrupted(run_id, terminal_reason="task_cancelled")
        raise
    except Exception as error:
        failure_patch = {
            "status": "failed",
            "progress": 100,
            "message": "Diagnostic run failed",
            "error": str(error),
            "inspection_completed_at": datetime.now(timezone.utc).isoformat(),
        }
        if isinstance(error, QuerySetGenerationFailed):
            failure_patch.update(
                {
                    "last_queryset_quality_report": error.quality_report,
                    "queryset_generation_attempt_reports": error.attempt_reports,
                    "last_queryset_id": error.last_queryset_id,
                    "matrix_api_request_id": error.matrix_api_request_id,
                    "last_queryset_generation_result": error.last_final_result_summary,
                    "last_queryset_candidates_preview": error.last_query_candidates_preview,
                    "queryset_debug_context": error.debug_context,
                }
            )
        _update_run(run_id, failure_patch)


def reconcile_interrupted_runs() -> list[str]:
    interrupted_run_ids: list[str] = []
    for run_id, run in runs_store.read().items():
        if not isinstance(run, dict) or run.get("status") not in ACTIVE_RUN_STATUSES:
            continue
        _mark_run_interrupted(str(run_id), terminal_reason="process_restart")
        interrupted_run_ids.append(str(run_id))
    return interrupted_run_ids


def _mark_run_interrupted(run_id: str, terminal_reason: str) -> dict:
    return _update_run(
        run_id,
        {
            "status": "interrupted",
            "message": INTERRUPTED_MESSAGE,
            "error": INTERRUPTED_ERROR,
            "terminal_reason": terminal_reason,
            "retriable": True,
            "inspection_completed_at": datetime.now(timezone.utc).isoformat(),
        },
    )


async def _inspect_queries(
    run_id: str,
    clients: list,
    queries: list[dict],
    brand_config: dict,
) -> list[dict]:
    platforms = [getattr(client, "platform", str(client)) for client in clients]
    max_concurrency = max(1, int(os.getenv("MAX_CONCURRENCY", "4")))
    task_timeout = _inspection_task_timeout_seconds()
    semaphore = asyncio.Semaphore(max_concurrency)
    results: list[dict] = []
    total_tasks = len(queries) * len(clients)
    run = runs_store.get(run_id) or {}

    async def inspect_one(client, query: dict) -> dict:
        async with semaphore:
            inspection_id = f"insp_{uuid4().hex[:12]}"
            request_at = datetime.now(timezone.utc).isoformat()
            try:
                result = await asyncio.wait_for(
                    client.inspect(
                        query,
                        brand_config,
                        options={
                            "provider": run.get("llm_provider") or getattr(client, "platform", None),
                            "web_search_enabled": run.get("web_search_enabled", True),
                            **(run.get("llm_options") or {}),
                        },
                    ),
                    timeout=task_timeout,
                )
                return {
                    "inspection_id": inspection_id,
                    "status": "completed",
                    "platform": getattr(client, "platform", "unknown"),
                    "provider": result.get("provider", "claude"),
                    "llm_provider": result.get("provider", "claude"),
                    "web_search_enabled": result.get("web_search_enabled", True),
                    "web_search_mode": result.get("web_search_mode") or "responses_web_search",
                    "model": result.get("model", "unknown"),
                    "query_id": query["query_id"],
                    "query_text": query["query_text"],
                    "query_pattern": query.get("query_pattern"),
                    "query_layer": query.get("query_layer"),
                    "topic": query["topic"],
                    "intent_type": query["intent_type"],
                    "request_at": request_at,
                    "returned_at": datetime.now(timezone.utc).isoformat(),
                    "raw_answer": result.get("raw_answer", ""),
                    "parsed": result.get("parsed", {}),
                    "usage": result.get("usage", {}),
                    "error": None,
                }
            except Exception as exc:
                error_message = (
                    f"{getattr(client, 'platform', 'unknown')} inspection timed out after {task_timeout:g}s"
                    if isinstance(exc, asyncio.TimeoutError)
                    else str(exc)
                )
                return {
                    "inspection_id": inspection_id,
                    "status": "failed",
                    "platform": getattr(client, "platform", "unknown"),
                    "provider": getattr(client, "platform", "unknown"),
                    "llm_provider": getattr(client, "platform", "unknown"),
                    "web_search_enabled": run.get("web_search_enabled", True),
                    "web_search_mode": (run.get("llm_options") or {}).get("web_search_mode") or getattr(client, "web_search_mode", ""),
                    "model": getattr(client, "model", "unknown"),
                    "query_id": query["query_id"],
                    "query_text": query["query_text"],
                    "query_pattern": query.get("query_pattern"),
                    "query_layer": query.get("query_layer"),
                    "topic": query["topic"],
                    "intent_type": query["intent_type"],
                    "request_at": request_at,
                    "returned_at": datetime.now(timezone.utc).isoformat(),
                    "raw_answer": "",
                    "parsed": {},
                    "usage": {},
                    "error": error_message,
                    "error_type": _inspection_error_type(exc),
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
    except asyncio.CancelledError:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    except Exception:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    return results


def _inspection_task_timeout_seconds() -> float:
    raw = os.getenv("INSPECTION_TASK_TIMEOUT_SECONDS") or os.getenv("REQUEST_TIMEOUT_SECONDS")
    try:
        value = float(raw) if raw else DEFAULT_INSPECTION_TASK_TIMEOUT_SECONDS
    except ValueError:
        value = DEFAULT_INSPECTION_TASK_TIMEOUT_SECONDS
    return max(0.001, value)


def _inspection_error_type(error: Exception) -> str:
    if isinstance(error, asyncio.TimeoutError):
        return "timeout"
    text = str(error).lower()
    if "nodename nor servname" in text or "name or service not known" in text:
        return "dns_resolution"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if "401" in text or "unauthorized" in text:
        return "auth"
    if (
        "429" in text
        or "setlimitexceeded" in text
        or "rate limit" in text
        or "quota" in text
        or "inference limit" in text
        or "service has been paused" in text
    ):
        return "rate_limited"
    if "modelnotopen" in text or "model not" in text:
        return "model_unavailable"
    return "provider_error"


def _inspection_quality_gate(completed_results: list[dict], failed_results: list[dict]) -> dict:
    total = len(completed_results) + len(failed_results)
    completed = len(completed_results)
    minimum_rate = _minimum_completion_rate()
    completion_rate = completed / total if total else 0
    status = "pass" if completed and completion_rate >= minimum_rate else "failed"
    return {
        "status": status,
        "completed_samples": completed,
        "failed_samples": len(failed_results),
        "expected_samples": total,
        "completion_rate": round(completion_rate, 4),
        "minimum_completion_rate": minimum_rate,
        "message": (
            f"Inspection quality gate passed: {completed}/{total} samples completed"
            if status == "pass"
            else f"Inspection quality gate failed: {completed}/{total} samples completed; minimum rate is {minimum_rate:.0%}"
        ),
    }


def _minimum_completion_rate() -> float:
    raw = os.getenv("MIN_INSPECTION_COMPLETION_RATE")
    try:
        value = float(raw) if raw else DEFAULT_MIN_INSPECTION_COMPLETION_RATE
    except ValueError:
        value = DEFAULT_MIN_INSPECTION_COMPLETION_RATE
    return max(0.0, min(1.0, value))


def _update_run(run_id: str, patch: dict) -> dict:
    run = runs_store.get(run_id)
    if not run:
        raise RuntimeError(f"run_id not found: {run_id}")
    run.update(patch)
    run["updated_at"] = datetime.now(timezone.utc).isoformat()
    return runs_store.upsert(run_id, run)


async def resolve_queryset(brand_config: dict, run: dict) -> dict:
    reusable = _latest_reusable_queryset(run, brand_config)
    if run.get("queryset_policy") == "reuse_latest" and reusable:
        try:
            return _reuse_queryset(validate_queryset_for_production(reusable), run)
        except RuntimeError:
            if run.get("base_queryset_id"):
                raise
            run["base_queryset_id"] = reusable.get("queryset_id")
    if reusable and not run.get("base_queryset_id"):
        run["base_queryset_id"] = reusable.get("queryset_id")
    queryset = await generate_queryset(brand_config, run)
    return _govern_queryset(queryset, run, "created")


def _latest_reusable_queryset(run: dict, brand_config: dict) -> dict | None:
    base_queryset_id = run.get("base_queryset_id")
    library_queryset = latest_frozen_queryset(brand_config, base_queryset_id)
    if library_queryset:
        return library_queryset

    entity_name = str(brand_config.get("entity_name") or "").strip()
    completed = [
        item
        for item in runs_store.read().values()
        if isinstance(item, dict)
        and item.get("run_id") != run.get("run_id")
        and item.get("status") == "completed"
        and isinstance(item.get("queryset"), dict)
        and _same_brand_run(item, run, entity_name)
    ]
    if base_queryset_id:
        return next((item["queryset"] for item in completed if item["queryset"].get("queryset_id") == base_queryset_id), None)
    completed.sort(key=lambda item: item.get("inspection_completed_at") or item.get("updated_at") or "", reverse=True)
    return completed[0]["queryset"] if completed else None


def _same_brand_run(item: dict, run: dict, entity_name: str) -> bool:
    if item.get("brand_config_id") == run.get("brand_config_id"):
        return True
    report = item.get("report_data") or {}
    brand_config = report.get("brand_config") if isinstance(report, dict) else None
    return isinstance(brand_config, dict) and brand_config.get("entity_name") == entity_name


def _reuse_queryset(queryset: dict, run: dict) -> dict:
    reused = normalize_queryset_snapshot(queryset)
    governance = {**(queryset.get("governance") or {})}
    governance.update(
        {
            "policy": "reuse_latest",
            "change_type": "reused",
            "reused_from_queryset_id": queryset.get("queryset_id"),
            "reused_for_run_id": run.get("run_id"),
            "approved_by": run.get("queryset_approved_by"),
            "change_reason": run.get("queryset_change_reason") or "scheduled_retest",
        }
    )
    reused["governance"] = governance
    return reused


def _govern_queryset(queryset: dict, run: dict, change_type: str) -> dict:
    governed = normalize_queryset_snapshot(queryset)
    parent_queryset_id = run.get("base_queryset_id")
    governed["queryset_version"] = _next_queryset_version(governed.get("queryset_version"), parent_queryset_id)
    governed["parent_queryset_id"] = parent_queryset_id
    governed["governance"] = {
        "policy": run.get("queryset_policy") or "reuse_latest",
        "change_type": change_type,
        "change_reason": run.get("queryset_change_reason") or "initial_generation",
        "approved_by": run.get("queryset_approved_by"),
        "parent_queryset_id": parent_queryset_id,
        "source_run_id": run.get("run_id"),
    }
    return persist_frozen_queryset({"brand_config_id": run.get("brand_config_id"), **(get_brand_config(run["brand_config_id"]) or {})}, governed)


def _next_queryset_version(version: object, parent_queryset_id: object) -> str:
    text = str(version or "rule_matrix_v1")
    if not parent_queryset_id:
        return text
    if "." in text:
        prefix, suffix = text.rsplit(".", 1)
        if suffix.isdigit():
            return f"{prefix}.{int(suffix) + 1}"
    return f"{text}.1"


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
