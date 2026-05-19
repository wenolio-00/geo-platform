import asyncio
import time

import pytest

from service import inspector


def _query(query_id="q_001"):
    return {
        "query_id": query_id,
        "query_text": "金融场景积分商城有哪些成熟供应商？",
        "query_pattern": "category_rec",
        "query_layer": "core_anchor",
        "topic": "积分商城",
        "intent_type": "vendor_recommendation",
    }


def test_inspection_task_timeout_is_bounded(monkeypatch):
    class SlowClient:
        platform = "豆包"
        model = "doubao-test"

        async def inspect(self, query, brand_config, options=None):
            await asyncio.sleep(1)
            return {}

    writes = []
    updates = []

    monkeypatch.setenv("INSPECTION_TASK_TIMEOUT_SECONDS", "0.01")
    monkeypatch.setenv("MAX_CONCURRENCY", "1")
    monkeypatch.setattr(inspector.inspection_results_store, "upsert", lambda run_id, payload: writes.append(payload) or payload)
    monkeypatch.setattr(inspector, "_update_run", lambda run_id, patch: updates.append(patch) or patch)

    started = time.monotonic()
    results = asyncio.run(inspector._inspect_queries("run_timeout", [SlowClient()], [_query()], {}))
    elapsed = time.monotonic() - started

    assert elapsed < 0.5
    assert results[0]["status"] == "failed"
    assert results[0]["error_type"] == "timeout"
    assert "timed out after" in results[0]["error"]
    assert writes[-1]["results"][0]["error_type"] == "timeout"
    assert updates[-1]["progress"] == 90


def test_inspection_quality_gate_enforces_completion_rate(monkeypatch):
    monkeypatch.setenv("MIN_INSPECTION_COMPLETION_RATE", "0.8")

    passed = inspector._inspection_quality_gate([{"status": "completed"}] * 8, [{"status": "failed"}] * 2)
    failed = inspector._inspection_quality_gate([{"status": "completed"}] * 7, [{"status": "failed"}] * 3)

    assert passed["status"] == "pass"
    assert passed["completion_rate"] == 0.8
    assert failed["status"] == "failed"
    assert failed["minimum_completion_rate"] == 0.8


def test_reconcile_interrupted_runs_marks_only_active_statuses(monkeypatch):
    stored_runs = {
        "run_queued": {"run_id": "run_queued", "status": "queued", "progress": 0},
        "run_running": {"run_id": "run_running", "status": "running", "progress": 42},
        "run_aggregating": {"run_id": "run_aggregating", "status": "aggregating", "progress": 92},
        "run_completed": {"run_id": "run_completed", "status": "completed", "progress": 100},
        "run_failed": {"run_id": "run_failed", "status": "failed", "progress": 100},
    }
    updates = []

    def fake_update_run(run_id, patch):
        updates.append((run_id, patch))
        return {**stored_runs[run_id], **patch}

    monkeypatch.setattr(inspector.runs_store, "read", lambda: stored_runs)
    monkeypatch.setattr(inspector, "_update_run", fake_update_run)

    interrupted = inspector.reconcile_interrupted_runs()

    assert interrupted == ["run_queued", "run_running", "run_aggregating"]
    assert [run_id for run_id, _patch in updates] == interrupted
    for _run_id, patch in updates:
        assert patch["status"] == "interrupted"
        assert patch["terminal_reason"] == "process_restart"
        assert patch["retriable"] is True
        assert patch["message"] == inspector.INTERRUPTED_MESSAGE
        assert patch["error"] == inspector.INTERRUPTED_ERROR
        assert "progress" not in patch


def test_run_diagnostic_job_marks_cancelled_task_interrupted(monkeypatch):
    class SlowClient:
        platform = "豆包"
        model = "doubao-test"

        async def inspect(self, query, brand_config, options=None):
            await asyncio.sleep(10)
            return {}

    updates = []
    run = {"run_id": "run_cancelled", "brand_config_id": "brand_001"}

    async def fake_resolve_queryset(brand_config, run_payload):
        return {"queryset_id": "qs_001"}

    def fake_update_run(run_id, patch):
        updates.append(patch)
        return {**run, **patch}

    monkeypatch.setattr(inspector.runs_store, "get", lambda run_id: run)
    monkeypatch.setattr(inspector, "get_brand_config", lambda brand_config_id: {"entity_name": "测试品牌"})
    monkeypatch.setattr(inspector, "requested_platforms", lambda run_payload: ["豆包"])
    monkeypatch.setattr(inspector, "create_platform_clients", lambda platforms: [SlowClient()])
    monkeypatch.setattr(inspector, "validate_platform_clients", lambda clients: None)
    monkeypatch.setattr(inspector, "resolve_queryset", fake_resolve_queryset)
    monkeypatch.setattr(inspector, "validate_queryset_for_production", lambda queryset: queryset)
    monkeypatch.setattr(inspector, "active_queries_from", lambda queryset: [_query()])
    monkeypatch.setattr(inspector.inspection_results_store, "upsert", lambda run_id, payload: payload)
    monkeypatch.setattr(inspector, "_update_run", fake_update_run)

    async def run_and_cancel():
        task = asyncio.create_task(inspector.run_diagnostic_job("run_cancelled"))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run_and_cancel())

    assert updates[-1]["status"] == "interrupted"
    assert updates[-1]["terminal_reason"] == "task_cancelled"
    assert updates[-1]["retriable"] is True
