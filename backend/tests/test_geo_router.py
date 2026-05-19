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
