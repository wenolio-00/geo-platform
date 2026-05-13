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
from service.inspector import create_run, get_report, get_run, latest_completed_run, run_diagnostic_job
from service.rule_matrix import generate_rule_matrix_queryset


router = APIRouter(prefix="/api/v1/geo", tags=["geo"])


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
        payload.brand_config_id,
        payload.queryset_strategy,
        payload.inspection_mode,
        payload.queryset_source,
        payload.platforms,
    )
    asyncio.create_task(run_diagnostic_job(run["run_id"]))
    return {
        "run_id": run["run_id"],
        "status": run["status"],
        "progress": run["progress"],
        "message": run["message"],
    }


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
    return generate_rule_matrix_queryset(
        brand_config,
        str(payload.get("queryset_strategy") or "rule_matrix_v1"),
    )


@router.get("/diagnostic-runs/{run_id}", response_model=DiagnosticRunResponse)
async def get_diagnostic_run(run_id: str) -> dict:
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run_id not found")
    return {
        "run_id": run["run_id"],
        "status": run["status"],
        "progress": run.get("progress", 0),
        "message": run.get("message"),
        "error": run.get("error"),
    }


@router.get("/diagnostic-report")
async def get_diagnostic_report(run_id: str) -> dict:
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run_id not found")
    if run.get("status") == "failed":
        raise HTTPException(status_code=409, detail=run.get("error") or "diagnostic run failed")
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
