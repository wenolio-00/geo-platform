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


def test_run_diagnostic_job_retries_failed_samples_before_aggregation(monkeypatch):
    class FlakyClient:
        platform = "豆包"
        model = "doubao-test"

        def __init__(self):
            self.calls = []

        async def inspect(self, query, brand_config, options=None):
            self.calls.append(query["query_id"])
            if query["query_id"] == "q_002" and self.calls.count("q_002") == 1:
                raise RuntimeError("gateway returned invalid json")
            return {
                "provider": self.platform,
                "platform": self.platform,
                "web_search_enabled": True,
                "web_search_mode": "responses_web_search",
                "model": self.model,
                "raw_answer": "{}",
                "parsed": {"answer": "ok", "mentioned_brands": [], "citations": []},
                "usage": {},
            }

    run = {
        "run_id": "run_retry",
        "brand_config_id": "brand_001",
        "web_search_enabled": True,
        "llm_options": {"two_round_inspection": False},
    }
    queryset = {"queryset_id": "qs_001"}
    queries = [_query("q_001"), _query("q_002")]
    client = FlakyClient()
    writes = []
    aggregated = {}

    async def fake_resolve_queryset(brand_config, run_payload):
        return queryset

    def fake_get(run_id):
        return run

    def fake_upsert(run_id, payload):
        snapshot = payload.copy()
        run.clear()
        run.update(snapshot)
        return run

    def fake_aggregate_report(run_payload, brand_config, queryset_payload, results):
        aggregated["results"] = results
        return {"summary": "ok"}

    monkeypatch.setenv("MIN_INSPECTION_COMPLETION_RATE", "0.8")
    monkeypatch.setenv("MAX_CONCURRENCY", "2")
    monkeypatch.setattr(inspector.runs_store, "get", fake_get)
    monkeypatch.setattr(inspector.runs_store, "upsert", fake_upsert)
    monkeypatch.setattr(inspector, "get_brand_config", lambda brand_config_id: {"entity_name": "测试品牌"})
    monkeypatch.setattr(inspector, "requested_platforms", lambda run_payload: ["豆包"])
    monkeypatch.setattr(inspector, "create_platform_clients", lambda platforms: [client])
    monkeypatch.setattr(inspector, "validate_platform_clients", lambda clients: None)
    monkeypatch.setattr(inspector, "resolve_queryset", fake_resolve_queryset)
    monkeypatch.setattr(inspector, "validate_queryset_for_production", lambda queryset_payload: queryset_payload)
    monkeypatch.setattr(inspector, "active_queries_from", lambda queryset_payload: queries)
    monkeypatch.setattr(inspector, "aggregate_report", fake_aggregate_report)
    monkeypatch.setattr(inspector, "persist_dashboard_snapshot", lambda run_payload, report_data: None)
    monkeypatch.setattr(inspector.inspection_results_store, "upsert", lambda run_id, payload: writes.append(payload) or payload)

    asyncio.run(inspector.run_diagnostic_job("run_retry"))

    assert client.calls.count("q_002") == 2
    assert run["status"] == "completed"
    assert run["report_data"] == {"summary": "ok"}
    assert run["inspection_quality_gate"]["status"] == "pass"
    assert run["inspection_quality_gate"]["retry_attempted"] is True
    assert run["inspection_quality_gate"]["pre_retry_quality_gate"]["status"] == "failed"
    assert [result["status"] for result in aggregated["results"]] == ["completed", "completed"]
    assert any(result["query_id"] == "q_002" and result["status"] == "completed" for result in writes[-1]["results"])


def test_retry_samples_includes_rate_limited_failures():
    class Client:
        platform = "豆包"

    query = _query("q_rate")
    samples = inspector._retry_samples(
        [Client()],
        [query],
        [{"status": "failed", "platform": "豆包", "query_id": "q_rate", "error_type": "rate_limited"}],
    )

    assert len(samples) == 1
    assert samples[0][1] == query


def test_inspection_options_use_platform_provider_not_shared_llm_provider(monkeypatch):
    class RecordingClient:
        platform = "豆包"
        model = "doubao-test"

        def __init__(self):
            self.options = None

        async def inspect(self, query, brand_config, options=None):
            self.options = options
            return {
                "provider": self.platform,
                "platform": self.platform,
                "web_search_enabled": True,
                "web_search_mode": "responses_web_search",
                "model": self.model,
                "raw_answer": "{}",
                "parsed": {},
                "usage": {},
            }

    client = RecordingClient()
    run = {
        "run_id": "run_platform_provider",
        "llm_provider": "claude",
        "web_search_enabled": True,
        "llm_options": {"two_round_inspection": False, "provider": "claude"},
    }

    monkeypatch.setattr(inspector.runs_store, "get", lambda run_id: run)
    monkeypatch.setattr(inspector.inspection_results_store, "upsert", lambda run_id, payload: payload)
    monkeypatch.setattr(inspector, "_update_run", lambda run_id, patch: patch)

    results = asyncio.run(inspector._inspect_queries("run_platform_provider", [client], [_query()], {}))

    assert client.options["provider"] == "豆包"
    assert results[0]["platform"] == "豆包"
    assert results[0]["provider"] == "豆包"
    assert results[0]["llm_provider"] == "豆包"


def test_blind_assisted_inspection_strips_brand_context_from_blind_round():
    class RecordingClient:
        platform = "豆包"
        model = "doubao-test"

        def __init__(self):
            self.calls = []

        async def inspect(self, query, brand_config, options=None):
            self.calls.append({"query": query, "brand_config": brand_config, "options": options})
            if options.get("blind_mode"):
                return {
                    "provider": self.platform,
                    "platform": self.platform,
                    "model": self.model,
                    "raw_answer": "{}",
                    "parsed": {"answer": "自然回答", "mentioned_brands": [], "citations": []},
                    "usage": {"round": "blind"},
                }
            return {
                "provider": self.platform,
                "platform": self.platform,
                "model": self.model,
                "raw_answer": "{}",
                "parsed": {
                    "answer": "自然回答",
                    "mentioned_brands": [{"name": "兑吧", "position": 1, "sentiment": "neutral"}],
                    "citations": [],
                },
                "usage": {"round": "assisted"},
            }

    client = RecordingClient()
    query = {**_query(), "related_competitors": ["有赞"], "competitors": ["有赞"]}
    brand_config = {"entity_name": "兑吧", "entity_aliases": ["Duiba"], "competitors": [{"name": "有赞"}]}

    result = asyncio.run(inspector._inspect_blind_assisted(client, query, brand_config, {}, 1))

    assert result["inspection_design"] == "blind_assisted"
    assert client.calls[0]["brand_config"] == {}
    assert client.calls[0]["query"] == {
        "query_id": query["query_id"],
        "query_text": query["query_text"],
        "query_pattern": query["query_pattern"],
        "query_layer": query["query_layer"],
        "topic": query["topic"],
        "intent_type": query["intent_type"],
    }
    assert client.calls[0]["options"]["blind_mode"] is True
    assert client.calls[1]["brand_config"] == brand_config
    assert client.calls[1]["options"]["assisted_extraction"] is True


def test_inspection_falls_back_to_single_round_when_blind_assisted_fails(monkeypatch):
    class FallbackClient:
        platform = "豆包"
        model = "doubao-test"

        def __init__(self):
            self.calls = []

        async def inspect(self, query, brand_config, options=None):
            self.calls.append({"query": query, "brand_config": brand_config, "options": options})
            if options.get("blind_mode") and not options.get("two_round_fallback"):
                raise RuntimeError("provider returned empty content")
            return {
                "provider": self.platform,
                "platform": self.platform,
                "model": self.model,
                "raw_answer": "{}",
                "parsed": {"answer": "ok", "mentioned_brands": [], "citations": []},
                "usage": {},
            }

    run = {
        "run_id": "run_fallback",
        "web_search_enabled": True,
        "llm_options": {"two_round_inspection": True},
    }
    client = FallbackClient()

    monkeypatch.setattr(inspector.runs_store, "get", lambda run_id: run)
    monkeypatch.setattr(inspector.inspection_results_store, "upsert", lambda run_id, payload: payload)
    monkeypatch.setattr(inspector, "_update_run", lambda run_id, patch: patch)

    results = asyncio.run(inspector._inspect_queries("run_fallback", [client], [_query()], {"entity_name": "兑吧"}))

    assert results[0]["status"] == "completed"
    assert client.calls[0]["options"]["blind_mode"] is True
    assert client.calls[1]["options"]["two_round_fallback"] is True
    assert client.calls[1]["options"]["blind_mode"] is True
    assert client.calls[1]["brand_config"] == {}
    assert client.calls[1]["query"] == {
        "query_id": "q_001",
        "query_text": "金融场景积分商城有哪些成熟供应商？",
        "query_pattern": "category_rec",
        "query_layer": "core_anchor",
        "topic": "积分商城",
        "intent_type": "vendor_recommendation",
    }


def test_single_round_inspection_uses_blind_query_when_two_round_disabled(monkeypatch):
    class RecordingClient:
        platform = "豆包"
        model = "doubao-test"

        def __init__(self):
            self.calls = []

        async def inspect(self, query, brand_config, options=None):
            self.calls.append({"query": query, "brand_config": brand_config, "options": options})
            return {
                "provider": self.platform,
                "platform": self.platform,
                "model": self.model,
                "raw_answer": "{}",
                "parsed": {"answer": "ok", "mentioned_brands": [], "citations": []},
                "usage": {},
            }

    run = {
        "run_id": "run_single_blind",
        "web_search_enabled": True,
        "llm_options": {"two_round_inspection": False},
    }
    client = RecordingClient()

    monkeypatch.setattr(inspector.runs_store, "get", lambda run_id: run)
    monkeypatch.setattr(inspector.inspection_results_store, "upsert", lambda run_id, payload: payload)
    monkeypatch.setattr(inspector, "_update_run", lambda run_id, patch: patch)

    results = asyncio.run(inspector._inspect_queries("run_single_blind", [client], [_query()], {"entity_name": "兑吧"}))

    assert results[0]["status"] == "completed"
    assert client.calls[0]["options"]["blind_mode"] is True
    assert client.calls[0]["brand_config"] == {}
    assert client.calls[0]["query"] == {
        "query_id": "q_001",
        "query_text": "金融场景积分商城有哪些成熟供应商？",
        "query_pattern": "category_rec",
        "query_layer": "core_anchor",
        "topic": "积分商城",
        "intent_type": "vendor_recommendation",
    }


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


def test_recover_active_runs_after_restart_requeues_active_runs(monkeypatch):
    stored_runs = {
        "run_queued": {"run_id": "run_queued", "status": "queued", "progress": 0},
        "run_running": {"run_id": "run_running", "status": "running", "progress": 42, "recovery_attempt_count": 1},
        "run_cancelled": {
            "run_id": "run_cancelled",
            "status": "interrupted",
            "progress": 42,
            "terminal_reason": "task_cancelled",
            "retriable": True,
        },
        "run_completed": {"run_id": "run_completed", "status": "completed", "progress": 100},
    }
    updates = []

    def fake_update_run(run_id, patch):
        updates.append((run_id, patch))
        return {**stored_runs[run_id], **patch}

    monkeypatch.setenv("MAX_DIAGNOSTIC_RECOVERY_ATTEMPTS", "2")
    monkeypatch.setattr(inspector.runs_store, "read", lambda: stored_runs)
    monkeypatch.setattr(inspector, "_update_run", fake_update_run)

    recovered = inspector.recover_active_runs_after_restart()

    assert recovered == ["run_queued", "run_running", "run_cancelled"]
    assert [run_id for run_id, _patch in updates] == recovered
    assert updates[0][1]["status"] == "queued"
    assert updates[0][1]["progress"] == 0
    assert updates[0][1]["message"] == inspector.RECOVERED_MESSAGE
    assert updates[0][1]["recovery_attempt_count"] == 1
    assert updates[1][1]["recovery_attempt_count"] == 2
    assert updates[2][1]["error"] is None
    assert updates[2][1]["terminal_reason"] is None
    assert updates[2][1]["retriable"] is None


def test_recover_active_runs_after_restart_interrupts_exhausted_runs(monkeypatch):
    stored_runs = {
        "run_exhausted": {
            "run_id": "run_exhausted",
            "status": "running",
            "progress": 42,
            "recovery_attempt_count": 2,
        },
    }
    updates = []

    def fake_update_run(run_id, patch):
        updates.append((run_id, patch))
        return {**stored_runs[run_id], **patch}

    monkeypatch.setenv("MAX_DIAGNOSTIC_RECOVERY_ATTEMPTS", "2")
    monkeypatch.setattr(inspector.runs_store, "read", lambda: stored_runs)
    monkeypatch.setattr(inspector, "_update_run", fake_update_run)

    recovered = inspector.recover_active_runs_after_restart()

    assert recovered == []
    assert updates[0][0] == "run_exhausted"
    assert updates[0][1]["status"] == "interrupted"
    assert updates[0][1]["terminal_reason"] == "recovery_attempts_exhausted"
    assert updates[0][1]["retriable"] is True


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
