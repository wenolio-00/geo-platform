from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from models.schemas import BrandConfigCreate, BrandConfigResponse, DiagnosticRunCreate, DiagnosticRunResponse
from service.brand_config import create_brand_config, get_brand_config
from service.dashboard_snapshots import (
    get_brand_history,
    get_dashboard_contract as get_persisted_dashboard_contract,
    get_overview_payload,
    persist_dashboard_snapshot,
    sync_completed_run_snapshots,
)
from service.content_generation import (
    compute_content_effect_attribution,
    generate_optimized_draft_async,
    get_content_effect_attribution,
    get_content_generation_context,
    record_content_feedback,
    save_content_version_edit,
)
from service.inspector import create_run, get_report, get_run, latest_completed_run, run_diagnostic_job
from service.iteration_board import get_iteration_priority_board, save_iteration_priority_board
from service.queryset import QuerySetThresholdConfigurationError
from service.prompt_lab import run_prompt_lab
from service.rule_activation import evaluate_rule_activation
from service.smart_prefill import smart_prefill_brand_config
from service.rule_matrix import generate_rule_matrix_queryset


router = APIRouter(prefix="/api/v1/geo", tags=["geo"])
logger = logging.getLogger(__name__)


def _error_body(detail: str, error_code: str, endpoint: str, stage: str, **context: object) -> dict:
    body = {
        "detail": detail,
        "error_code": error_code,
        "endpoint": endpoint,
        "stage": stage,
    }
    body.update({key: value for key, value in context.items() if value is not None})
    return body


def _error_response(status_code: int, detail: str, error_code: str, endpoint: str, stage: str, **context: object) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=_error_body(detail, error_code, endpoint, stage, **context),
    )


def _log_endpoint_event(level: int, message: str, endpoint: str, stage: str, **context: object) -> None:
    extra = {"endpoint": endpoint, "stage": stage}
    extra.update({key: value for key, value in context.items() if value is not None})
    logger.log(level, message, extra=extra)


def _log_endpoint_exception(message: str, endpoint: str, stage: str, **context: object) -> None:
    extra = {"endpoint": endpoint, "stage": stage}
    extra.update({key: value for key, value in context.items() if value is not None})
    logger.exception(message, extra=extra)


def _diagnostic_run_response(run: dict) -> dict:
    return {
        "run_id": run["run_id"],
        "status": run["status"],
        "progress": run.get("progress", 0),
        "message": run.get("message"),
        "error": run.get("error"),
        "terminal_reason": run.get("terminal_reason"),
        "retriable": run.get("retriable"),
        "last_queryset_quality_report": run.get("last_queryset_quality_report"),
        "queryset_generation_attempt_reports": run.get("queryset_generation_attempt_reports") or [],
        "last_queryset_id": run.get("last_queryset_id"),
        "matrix_api_request_id": run.get("matrix_api_request_id"),
        "last_queryset_generation_result": run.get("last_queryset_generation_result"),
        "last_queryset_candidates_preview": run.get("last_queryset_candidates_preview") or [],
        "queryset_debug_context": run.get("queryset_debug_context"),
    }


@router.post("/brand-configs", response_model=BrandConfigResponse)
async def post_brand_config(payload: BrandConfigCreate) -> dict:
    endpoint = "POST /brand-configs"
    stage = "create_brand_config"
    entity_name = payload.entity_name.strip()
    if not payload.entity_name.strip():
        return _error_response(
            422,
            "entity_name is required",
            "brand_config_invalid_input",
            endpoint,
            stage,
            entity_name=entity_name,
        )
    try:
        brand_config = create_brand_config(payload)
    except Exception:
        _log_endpoint_exception("brand_config_create_failed", endpoint, stage, entity_name=entity_name)
        return _error_response(
            500,
            "Failed to create brand config.",
            "brand_config_create_failed",
            endpoint,
            stage,
            entity_name=entity_name,
        )
    _log_endpoint_event(
        logging.INFO,
        "brand_config_created",
        endpoint,
        stage,
        brand_config_id=brand_config.get("brand_config_id"),
        entity_name=brand_config.get("entity_name"),
    )
    return {
        "brand_config_id": brand_config["brand_config_id"],
        "entity_id": brand_config["entity_id"],
        "brand_config": brand_config,
    }


@router.post("/diagnostic-runs", response_model=DiagnosticRunResponse)
async def post_diagnostic_run(payload: DiagnosticRunCreate) -> dict:
    endpoint = "POST /diagnostic-runs"
    stage = "create_run"
    if not get_brand_config(payload.brand_config_id):
        return _error_response(
            404,
            "brand_config_id not found",
            "brand_config_not_found",
            endpoint,
            stage,
            brand_config_id=payload.brand_config_id,
        )
    try:
        run = create_run(
            brand_config_id=payload.brand_config_id,
            queryset_strategy=payload.queryset_strategy,
            inspection_mode=payload.inspection_mode,
            queryset_source=payload.queryset_source,
            platforms=payload.platforms,
            queryset_policy=payload.queryset_policy,
            base_queryset_id=payload.base_queryset_id,
            queryset_change_reason=payload.queryset_change_reason,
            queryset_approved_by=payload.queryset_approved_by,
            generation_constraints=payload.generation_constraints,
            llm_provider=payload.llm_provider,
            web_search_enabled=payload.web_search_enabled,
            llm_options=payload.llm_options,
        )
    except QuerySetThresholdConfigurationError as exc:
        return _error_response(
            422,
            str(exc),
            "queryset_threshold_configuration_invalid",
            endpoint,
            stage,
            brand_config_id=payload.brand_config_id,
        )
    except Exception:
        _log_endpoint_exception("diagnostic_run_create_failed", endpoint, stage, brand_config_id=payload.brand_config_id)
        return _error_response(
            500,
            "Failed to create diagnostic run.",
            "diagnostic_run_create_failed",
            endpoint,
            stage,
            brand_config_id=payload.brand_config_id,
        )
    stage = "start_background_task"
    try:
        asyncio.create_task(run_diagnostic_job(run["run_id"]))
    except Exception:
        _log_endpoint_exception(
            "diagnostic_run_start_task_failed",
            endpoint,
            stage,
            run_id=run.get("run_id"),
            brand_config_id=payload.brand_config_id,
        )
        return _error_response(
            500,
            "Failed to start diagnostic run background task.",
            "diagnostic_run_start_task_failed",
            endpoint,
            stage,
            run_id=run.get("run_id"),
            brand_config_id=payload.brand_config_id,
        )
    _log_endpoint_event(
        logging.INFO,
        "diagnostic_run_started",
        endpoint,
        stage,
        run_id=run.get("run_id"),
        brand_config_id=payload.brand_config_id,
    )
    return _diagnostic_run_response(run)


@router.post("/prefill/brand-config")
async def post_brand_config_prefill(payload: dict) -> dict:
    endpoint = "POST /prefill/brand-config"
    try:
        return await smart_prefill_brand_config(payload)
    except ValueError as exc:
        return _error_response(422, str(exc), "prefill_invalid_input", endpoint, "validate_input")
    except RuntimeError as exc:
        _log_endpoint_exception("prefill_upstream_failed", endpoint, "invoke_llm")
        return _error_response(503, str(exc), "prefill_upstream_failed", endpoint, "invoke_llm")
    except Exception:
        _log_endpoint_exception("prefill_unexpected_failed", endpoint, "smart_prefill")
        return _error_response(500, "Smart prefill failed due to an internal error.", "prefill_unexpected_failed", endpoint, "smart_prefill")


@router.post("/rule-activation/evaluate")
async def post_rule_activation_evaluate(payload: dict) -> dict:
    endpoint = "POST /rule-activation/evaluate"
    try:
        return await evaluate_rule_activation(payload)
    except ValueError as exc:
        return _error_response(422, str(exc), "rule_activation_invalid_input", endpoint, "validate_input")
    except RuntimeError as exc:
        _log_endpoint_exception("rule_activation_upstream_failed", endpoint, "invoke_llm")
        return _error_response(503, str(exc), "rule_activation_upstream_failed", endpoint, "invoke_llm")
    except Exception:
        _log_endpoint_exception("rule_activation_unexpected_failed", endpoint, "evaluate")
        return _error_response(500, "Rule activation evaluation failed.", "rule_activation_unexpected_failed", endpoint, "evaluate")


@router.post("/prompt-lab/runs")
async def post_prompt_lab_run(payload: dict, request: Request) -> dict:
    endpoint = "POST /prompt-lab/runs"
    try:
        return await run_prompt_lab(payload, is_disconnected=request.is_disconnected)
    except ValueError as exc:
        return _error_response(422, str(exc), "prompt_lab_invalid_input", endpoint, "validate_input")
    except Exception:
        _log_endpoint_exception("prompt_lab_failed", endpoint, "run")
        return _error_response(500, "Prompt lab run failed.", "prompt_lab_failed", endpoint, "run")


@router.get("/iteration-priority-board")
async def get_iteration_priority_board_endpoint() -> dict:
    return get_iteration_priority_board()


@router.put("/iteration-priority-board")
async def put_iteration_priority_board(payload: dict) -> dict:
    try:
        return save_iteration_priority_board(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/querysets/generate")
async def post_queryset_generate(payload: dict) -> dict:
    brand_config = {
        "brand_config_id": payload.get("brand_config_id"),
        "entity_id": payload.get("entity_id"),
        "entity_name": str(payload.get("entity_name") or "").strip(),
        "entity_aliases": payload.get("entity_aliases") or [],
        "industry_segments": payload.get("industry_segments") or [],
        "topics": payload.get("topics") or [],
        "competitors": payload.get("competitors") or [],
    }
    if not brand_config["entity_name"]:
        raise HTTPException(status_code=422, detail="entity_name is required")
    generation_constraints = (
        payload.get("generation_constraints") if isinstance(payload.get("generation_constraints"), dict) else {}
    )
    endpoint = "POST /querysets/generate"
    candidate_count = payload.get("candidate_queries") or generation_constraints.get("candidate_queries")
    try:
        return generate_rule_matrix_queryset(
            brand_config,
            str(payload.get("queryset_strategy") or "rule_matrix_v1"),
            candidate_count=candidate_count,
        )
    except Exception:
        _log_endpoint_exception("queryset_generate_failed", endpoint, "generate_rule_matrix")
        return _error_response(500, "QuerySet generation failed.", "queryset_generate_failed", endpoint, "generate_rule_matrix")


@router.get("/diagnostic-runs/{run_id}", response_model=DiagnosticRunResponse)
async def get_diagnostic_run(run_id: str) -> dict:
    endpoint = "GET /diagnostic-runs/{run_id}"
    stage = "get_run"
    try:
        run = get_run(run_id)
    except Exception:
        _log_endpoint_exception("diagnostic_run_read_failed", endpoint, stage, run_id=run_id)
        return _error_response(500, "Failed to read diagnostic run.", "diagnostic_run_read_failed", endpoint, stage, run_id=run_id)
    if not run:
        return _error_response(404, "run_id not found", "diagnostic_run_not_found", endpoint, stage, run_id=run_id)
    _log_endpoint_event(logging.INFO, "diagnostic_run_read", endpoint, stage, run_id=run_id, status=run.get("status"))
    return _diagnostic_run_response(run)


@router.get("/diagnostic-report")
async def get_diagnostic_report(run_id: str) -> dict:
    endpoint = "GET /diagnostic-report"
    stage = "get_report"
    try:
        run = get_run(run_id)
    except Exception:
        _log_endpoint_exception("diagnostic_report_run_read_failed", endpoint, stage, run_id=run_id)
        return _error_response(500, "Failed to read diagnostic run.", "diagnostic_report_run_read_failed", endpoint, stage, run_id=run_id)
    if not run:
        return _error_response(404, "run_id not found", "diagnostic_run_not_found", endpoint, stage, run_id=run_id)

    status = str(run.get("status") or "")
    has_report_data = isinstance(run.get("report_data"), dict)
    _log_endpoint_event(
        logging.INFO,
        "diagnostic_report_status_checked",
        endpoint,
        "check_status",
        run_id=run_id,
        status=status,
        has_report_data=has_report_data,
    )
    if status in {"queued", "running", "aggregating"}:
        return _error_response(
            409,
            f"diagnostic report is not ready: {status}",
            "diagnostic_report_not_ready",
            endpoint,
            "check_status",
            run_id=run_id,
            status=status,
            has_report_data=has_report_data,
        )
    if status == "failed":
        return _error_response(
            409,
            run.get("error") or "diagnostic run failed",
            "diagnostic_run_failed",
            endpoint,
            "check_status",
            run_id=run_id,
            status=status,
            has_report_data=has_report_data,
            run_error=run.get("error"),
        )
    if status == "interrupted":
        return _error_response(
            409,
            run.get("error") or "diagnostic run interrupted",
            "diagnostic_run_interrupted",
            endpoint,
            "check_status",
            run_id=run_id,
            status=status,
            has_report_data=has_report_data,
            terminal_reason=run.get("terminal_reason"),
            retriable=run.get("retriable"),
        )
    if status == "completed" and not has_report_data:
        return _error_response(
            409,
            "diagnostic run completed but report_data is missing",
            "report_data_missing_after_completion",
            endpoint,
            "check_status",
            run_id=run_id,
            status=status,
            has_report_data=has_report_data,
        )
    try:
        report = get_report(run_id)
    except Exception:
        _log_endpoint_exception("diagnostic_report_read_failed", endpoint, stage, run_id=run_id, status=status)
        return _error_response(
            500,
            "Failed to read diagnostic report.",
            "diagnostic_report_read_failed",
            endpoint,
            stage,
            run_id=run_id,
            status=status,
            has_report_data=has_report_data,
        )
    if not report:
        return _error_response(
            409,
            f"diagnostic run is not completed: {status}",
            "diagnostic_report_unavailable",
            endpoint,
            stage,
            run_id=run_id,
            status=status,
            has_report_data=has_report_data,
        )
    return report


@router.get("/dashboard-contract")
async def get_dashboard_contract(
    brand_config_id: str | None = None,
    brand_id: str | None = None,
) -> dict:
    sync_completed_run_snapshots()
    contract = get_persisted_dashboard_contract(brand_config_id=brand_config_id, brand_id=brand_id)
    if contract:
        return contract

    run = latest_completed_run()
    if run and isinstance(run.get("report_data"), dict):
        persist_dashboard_snapshot(run, run["report_data"])
        contract = get_persisted_dashboard_contract(brand_config_id=brand_config_id, brand_id=brand_id)
        if contract:
            return contract

    raise HTTPException(status_code=404, detail="No completed diagnostic dashboard snapshot is available yet.")


@router.get("/content/context")
async def get_content_context(
    brand_id: str | None = None,
    brand_config_id: str | None = None,
    action_id: str | None = None,
    rule_id: str | None = None,
) -> dict:
    context = get_content_generation_context(
        brand_id=brand_id,
        brand_config_id=brand_config_id,
        action_id=action_id,
        rule_id=rule_id,
    )
    if context:
        return context
    raise HTTPException(status_code=404, detail="No completed diagnostic dashboard snapshot is available yet.")


@router.post("/content/generate")
async def post_content_generate(payload: dict) -> dict:
    endpoint = "POST /content/generate"
    context = {
        "brand_config_id": payload.get("brand_config_id"),
        "brand_id": payload.get("brand_id"),
        "action_id": payload.get("action_id"),
        "rule_id": payload.get("rule_id"),
    }
    try:
        return await generate_optimized_draft_async(payload)
    except LookupError as exc:
        return _error_response(404, str(exc), "content_context_not_found", endpoint, "load_context", **context)
    except ValueError as exc:
        message = str(exc)
        stage = "resolve_rule" if "rule_id" in message else "resolve_action" if "action_id" in message else "validate_input"
        return _error_response(422, message, "content_generation_invalid_input", endpoint, stage, **context)
    except RuntimeError as exc:
        _log_endpoint_exception("content_generation_runtime_failed", endpoint, "generate_llm", **context)
        return _error_response(503, str(exc), "content_generation_upstream_failed", endpoint, "generate_llm", **context)
    except Exception:
        _log_endpoint_exception("content_generation_unexpected_failed", endpoint, "persist_content", **context)
        return _error_response(500, "Unexpected content generation failure.", "content_generation_unexpected_failed", endpoint, "persist_content", **context)


@router.post("/content/versions/{content_version_id}/edits")
async def post_content_version_edit(content_version_id: str, payload: dict) -> dict:
    try:
        return save_content_version_edit(content_version_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/content/versions/{content_version_id}/feedback")
async def post_content_feedback(content_version_id: str, payload: dict) -> dict:
    try:
        return record_content_feedback(content_version_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/content/versions/{content_version_id}/effect-attribution")
async def get_content_version_effect_attribution(content_version_id: str) -> dict:
    try:
        return get_content_effect_attribution(content_version_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/content/versions/{content_version_id}/effect-attribution")
async def post_content_version_effect_attribution(content_version_id: str, payload: dict | None = None) -> dict:
    try:
        return compute_content_effect_attribution(content_version_id, payload or {})
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/brands/{brand_id}/history")
async def get_brand_history_endpoint(brand_id: str, days: int = Query(default=30, ge=1, le=365)) -> dict:
    sync_completed_run_snapshots()
    history = get_brand_history(brand_id, days)
    if history:
        return history

    run = latest_completed_run()
    if run and isinstance(run.get("report_data"), dict):
        persist_dashboard_snapshot(run, run["report_data"])
        history = get_brand_history(brand_id, days)
        if history:
            return history

    raise HTTPException(status_code=404, detail="No history is available for this brand.")


@router.get("/overview")
async def get_overview(brand_config_id: str | None = None) -> dict:
    sync_completed_run_snapshots()
    overview = get_overview_payload(brand_config_id=brand_config_id)
    if overview:
        return overview

    run = latest_completed_run()
    if run and isinstance(run.get("report_data"), dict):
        persist_dashboard_snapshot(run, run["report_data"])
        overview = get_overview_payload(brand_config_id=brand_config_id)
        if overview:
            return overview

    return {
        "queryset": None,
        "metrics": None,
        "attribution": None,
        "methodology_note": "No completed live diagnostic run is available yet.",
    }
