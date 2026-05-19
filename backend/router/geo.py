from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query

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
    generate_optimized_draft,
    get_content_effect_attribution,
    get_content_generation_context,
    record_content_feedback,
    save_content_version_edit,
)
from service.inspector import create_run, get_report, get_run, latest_completed_run, run_diagnostic_job
from service.rule_activation import evaluate_rule_activation
from service.smart_prefill import smart_prefill_brand_config
from service.rule_matrix import generate_rule_matrix_queryset


router = APIRouter(prefix="/api/v1/geo", tags=["geo"])


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
    if not payload.entity_name.strip():
        raise HTTPException(status_code=422, detail="entity_name is required")
    brand_config = create_brand_config(payload)
    return {
        "brand_config_id": brand_config["brand_config_id"],
        "entity_id": brand_config["entity_id"],
        "brand_config": brand_config,
    }


@router.post("/diagnostic-runs", response_model=DiagnosticRunResponse)
async def post_diagnostic_run(payload: DiagnosticRunCreate) -> dict:
    if not get_brand_config(payload.brand_config_id):
        raise HTTPException(status_code=404, detail="brand_config_id not found")
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
    asyncio.create_task(run_diagnostic_job(run["run_id"]))
    return _diagnostic_run_response(run)


@router.post("/prefill/brand-config")
async def post_brand_config_prefill(payload: dict) -> dict:
    try:
        return await smart_prefill_brand_config(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/rule-activation/evaluate")
async def post_rule_activation_evaluate(payload: dict) -> dict:
    try:
        return await evaluate_rule_activation(payload)
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
    candidate_count = payload.get("candidate_queries") or generation_constraints.get("candidate_queries")
    return generate_rule_matrix_queryset(
        brand_config,
        str(payload.get("queryset_strategy") or "rule_matrix_v1"),
        candidate_count=candidate_count,
    )


@router.get("/diagnostic-runs/{run_id}", response_model=DiagnosticRunResponse)
async def get_diagnostic_run(run_id: str) -> dict:
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run_id not found")
    return _diagnostic_run_response(run)


@router.get("/diagnostic-report")
async def get_diagnostic_report(run_id: str) -> dict:
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run_id not found")
    if run.get("status") in {"failed", "interrupted"}:
        fallback = "diagnostic run interrupted" if run.get("status") == "interrupted" else "diagnostic run failed"
        raise HTTPException(status_code=409, detail=run.get("error") or fallback)
    report = get_report(run_id)
    if not report:
        raise HTTPException(status_code=409, detail=f"diagnostic run is not completed: {run.get('status')}")
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
async def get_content_context(brand_id: str | None = None) -> dict:
    context = get_content_generation_context(brand_id=brand_id)
    if context:
        return context
    raise HTTPException(status_code=404, detail="No completed diagnostic dashboard snapshot is available yet.")


@router.post("/content/generate")
async def post_content_generate(payload: dict) -> dict:
    try:
        return generate_optimized_draft(payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
