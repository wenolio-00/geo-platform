from fastapi.testclient import TestClient

from main import app


def test_get_diagnostic_run_exposes_queryset_failure_diagnostics(monkeypatch):
    run = {
        "run_id": "run_failed",
        "status": "failed",
        "progress": 100,
        "message": "Diagnostic run failed",
        "error": "QuerySet generation failed quality gate",
        "terminal_reason": None,
        "retriable": None,
        "last_queryset_quality_report": {
            "status": "failed",
            "cumulative_active_count": 0,
        },
        "queryset_generation_attempt_reports": [
            {"generation_attempt": 1, "active_count": 0},
        ],
        "last_queryset_id": "qs_failed",
        "matrix_api_request_id": "mx_failed",
        "last_queryset_generation_result": {
            "queryset_id": "qs_failed",
            "query_count": 40,
        },
        "last_queryset_candidates_preview": [
            {
                "query_id": "q_001",
                "query_text": "银行积分商城系统有哪些成熟供应商？",
                "lifecycle_status": "archived",
                "quality_filter_status": "archived",
                "quality_filter_reasons": [{"rule_id": "QF-06", "reason": "upstream duplicate"}],
                "generation_attempt": 1,
            }
        ],
        "queryset_debug_context": {
            "queryset_source": "matrix_api_v1",
            "queryset_policy": "create_new_version",
            "existing_active_text_count": 0,
            "accumulated_active_count": 0,
        },
    }
    monkeypatch.setattr("router.geo.get_run", lambda run_id: run if run_id == "run_failed" else None)

    client = TestClient(app)
    response = client.get("/api/v1/geo/diagnostic-runs/run_failed")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "run_failed"
    assert payload["last_queryset_quality_report"]["cumulative_active_count"] == 0
    assert payload["queryset_generation_attempt_reports"][0]["active_count"] == 0
    assert payload["last_queryset_id"] == "qs_failed"
    assert payload["matrix_api_request_id"] == "mx_failed"
    assert payload["last_queryset_generation_result"]["query_count"] == 40
    assert payload["last_queryset_candidates_preview"][0]["quality_filter_reasons"][0]["rule_id"] == "QF-06"
    assert payload["queryset_debug_context"]["queryset_policy"] == "create_new_version"


def test_post_brand_config_preserves_topic_context():
    client = TestClient(app)
    response = client.post(
        "/api/v1/geo/brand-configs",
        json={
            "entity_name": "兑吧",
            "topics": [
                {
                    "topic_name": "积分商城管理工具",
                    "business_line": "积分商城",
                    "priority": 1,
                    "pain_point": "积分运营低效",
                    "goal": "提升用户活跃",
                }
            ],
            "competitors": [{"name": "有赞"}],
        },
    )

    assert response.status_code == 200
    topic = response.json()["brand_config"]["topics"][0]
    assert topic["pain_point"] == "积分运营低效"
    assert topic["goal"] == "提升用户活跃"


def test_post_diagnostic_run_returns_422_for_small_production_thresholds(monkeypatch):
    def unexpected_upsert(run_id, run):
        raise AssertionError("small production QuerySet thresholds should fail before persistence")

    monkeypatch.setattr("router.geo.get_brand_config", lambda brand_config_id: {"brand_config_id": brand_config_id})
    monkeypatch.setattr("service.inspector.runs_store.upsert", unexpected_upsert)
    monkeypatch.setenv("MAX_QUERIES_PER_RUN", "1")
    monkeypatch.setenv("MIN_ACTIVE_QUERIES", "1")

    client = TestClient(app)
    response = client.post(
        "/api/v1/geo/diagnostic-runs",
        json={
            "brand_config_id": "bc_test",
            "queryset_policy": "create_new_version",
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "candidate_queries >= 30" in detail
    assert "min_active_queries >= 30" in detail
    assert "generation_constraints.allow_small_queryset=true" in detail


def test_post_diagnostic_run_allows_explicit_small_queryset(monkeypatch):
    def fake_create_task(coro):
        coro.close()
        return None

    async def noop_run_diagnostic_job(run_id):
        return None

    monkeypatch.setattr("router.geo.get_brand_config", lambda brand_config_id: {"brand_config_id": brand_config_id})
    monkeypatch.setattr("service.inspector.runs_store.upsert", lambda run_id, run: run)
    monkeypatch.setattr("router.geo.run_diagnostic_job", noop_run_diagnostic_job)
    monkeypatch.setattr("router.geo.asyncio.create_task", fake_create_task)
    monkeypatch.setenv("MAX_QUERIES_PER_RUN", "1")
    monkeypatch.setenv("MIN_ACTIVE_QUERIES", "1")

    client = TestClient(app)
    response = client.post(
        "/api/v1/geo/diagnostic-runs",
        json={
            "brand_config_id": "bc_test",
            "queryset_policy": "create_new_version",
            "generation_constraints": {"allow_small_queryset": True},
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "queued"


def test_get_diagnostic_report_returns_structured_not_ready_state(monkeypatch):
    monkeypatch.setattr(
        "router.geo.get_run",
        lambda run_id: {
            "run_id": run_id,
            "status": "aggregating",
            "progress": 92,
            "report_data": None,
        },
    )

    client = TestClient(app)
    response = client.get("/api/v1/geo/diagnostic-report", params={"run_id": "run_pending"})

    assert response.status_code == 409
    payload = response.json()
    assert payload["error_code"] == "diagnostic_report_not_ready"
    assert payload["endpoint"] == "GET /diagnostic-report"
    assert payload["stage"] == "check_status"
    assert payload["run_id"] == "run_pending"
    assert payload["status"] == "aggregating"
    assert payload["has_report_data"] is False


def test_get_diagnostic_report_returns_structured_missing_data_after_completion(monkeypatch):
    monkeypatch.setattr(
        "router.geo.get_run",
        lambda run_id: {
            "run_id": run_id,
            "status": "completed",
            "progress": 100,
            "report_data": None,
        },
    )

    client = TestClient(app)
    response = client.get("/api/v1/geo/diagnostic-report", params={"run_id": "run_bad"})

    assert response.status_code == 409
    payload = response.json()
    assert payload["error_code"] == "report_data_missing_after_completion"
    assert payload["endpoint"] == "GET /diagnostic-report"
    assert payload["stage"] == "check_status"
    assert payload["run_id"] == "run_bad"


def test_post_content_generate_maps_runtime_failure_to_structured_503(monkeypatch):
    async def failing_generate(payload):
        raise RuntimeError("claude content_generation failed: provider unavailable")

    monkeypatch.setattr("router.geo.generate_optimized_draft_async", failing_generate)

    client = TestClient(app)
    response = client.post(
        "/api/v1/geo/content/generate",
        json={
            "brand_id": "brand_test",
            "brand_config_id": "bc_test",
            "action_id": "action_1",
            "rule_id": "rule_1",
        },
    )

    assert response.status_code == 503
    payload = response.json()
    assert payload["error_code"] == "content_generation_upstream_failed"
    assert payload["endpoint"] == "POST /content/generate"
    assert payload["stage"] == "generate_llm"
    assert payload["brand_id"] == "brand_test"
    assert payload["brand_config_id"] == "bc_test"
    assert payload["action_id"] == "action_1"
    assert payload["rule_id"] == "rule_1"


def test_get_iteration_priority_board_exposes_priority_items(monkeypatch):
    monkeypatch.setattr(
        "router.geo.get_iteration_priority_board",
        lambda: {
            "board_id": "geo_iteration_priority_board",
            "title": "GEO Iteration Priority Board",
            "items": [{"id": "report-contract-stabilization", "phase": "now", "title": "Report contract stabilization"}],
        },
    )

    client = TestClient(app)
    response = client.get("/api/v1/geo/iteration-priority-board")

    assert response.status_code == 200
    payload = response.json()
    assert payload["board_id"] == "geo_iteration_priority_board"
    assert payload["items"][0]["phase"] == "now"


def test_unhandled_backend_exception_returns_structured_500(monkeypatch):
    def failing_board():
        raise RuntimeError("boom")

    monkeypatch.setattr("router.geo.get_iteration_priority_board", failing_board)

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/v1/geo/iteration-priority-board")

    assert response.status_code == 500
    payload = response.json()
    assert payload["detail"] == "Internal backend error."
    assert payload["error_code"] == "internal_backend_error"
    assert payload["endpoint"] == "GET /api/v1/geo/iteration-priority-board"
    assert payload["stage"] == "unhandled_exception"
    assert payload["exception_type"] == "RuntimeError"


def test_put_iteration_priority_board_persists_payload(monkeypatch):
    captured = {}

    def fake_save(payload):
        captured["payload"] = payload
        return {**payload, "last_updated": "2026-05-21"}

    monkeypatch.setattr("router.geo.save_iteration_priority_board", fake_save)

    client = TestClient(app)
    response = client.put(
        "/api/v1/geo/iteration-priority-board",
        json={
            "title": "GEO Iteration Priority Board",
            "items": [
                {
                    "id": "dashboard-contract-adoption",
                    "phase": "now",
                    "title": "Dashboard contract adoption",
                    "exit_condition": "/dashboard uses the persisted snapshot contract.",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert captured["payload"]["items"][0]["id"] == "dashboard-contract-adoption"
    assert response.json()["last_updated"] == "2026-05-21"
