from service.queryset_policy import apply_query_quality_filters, get_tone
from service.queryset import _collect_existing_active_texts
import pytest

from service.queryset_library import normalize_queryset_snapshot, validate_queryset_for_production


def _query(text, journey_stage="problem_discovery", query_pattern="category_rec"):
    return {
        "query_id": "q_001",
        "query_text": text,
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "topic": "积分商城",
        "intent_type": query_pattern,
        "journey_stage": journey_stage,
        "query_pattern": query_pattern,
        "related_competitors": [],
        "lifecycle_status": "active",
    }


def test_collect_existing_active_texts_can_skip_historical_queries():
    brand_config = {"brand_config_id": "bc_duiba", "entity_id": "ent_duiba", "entity_name": "兑吧"}

    assert _collect_existing_active_texts(brand_config, include_historical=False) == set()


def test_qf_01_archives_length_out_of_range():
    queries, report = apply_query_quality_filters([_query("太短")], {}, [])

    assert queries[0]["lifecycle_status"] == "archived"
    assert queries[0]["quality_filter_reasons"][0]["rule_id"] == "QF-01"
    assert report["qf_counts"]["QF-01"] == 1


def test_qf_02_rejects_forbidden_words():
    queries, report = apply_query_quality_filters([_query("银行积分商城如何避免洗钱风险")], {}, [])

    assert queries[0]["lifecycle_status"] == "rejected"
    assert queries[0]["quality_filter_status"] == "rejected"
    assert queries[0]["quality_filter_reasons"][0]["rule_id"] == "QF-02"
    assert report["rejected_count"] == 1


def test_qf_03_archives_ad_phrases():
    queries, report = apply_query_quality_filters([_query("免费最好第一行业首选积分平台")], {}, [])

    assert queries[0]["lifecycle_status"] == "archived"
    assert any(reason["rule_id"] == "QF-03" for reason in queries[0]["quality_filter_reasons"])
    assert report["qf_counts"]["QF-03"] == 1


def test_qf_04_uses_matrix_tone_for_oral_casual_cells():
    query = _query("贵司积分商城能力矩阵应该怎么综合评估", "problem_discovery", "category_rec")

    queries, _ = apply_query_quality_filters([query], {}, [])

    assert get_tone("problem_discovery", "category_rec") == "oral_casual"
    assert queries[0]["lifecycle_status"] == "archived"
    assert any(reason["rule_id"] == "QF-04" for reason in queries[0]["quality_filter_reasons"])


def test_qf_05_uses_matrix_tone_for_formal_cells():
    query = _query("内部立项时崩溃了救救怎么说明积分平台风险", "purchase_decision", "purchase_risk")

    queries, _ = apply_query_quality_filters([query], {}, [])

    assert get_tone("purchase_decision", "purchase_risk") == "formal"
    assert queries[0]["lifecycle_status"] == "archived"
    assert any(reason["rule_id"] == "QF-05" for reason in queries[0]["quality_filter_reasons"])


def test_qf_06_archives_existing_active_exact_duplicate():
    text = "银行积分商城系统有哪些成熟供应商？"

    queries, report = apply_query_quality_filters([_query(text)], {}, [text])

    assert queries[0]["lifecycle_status"] == "archived"
    assert any(reason["rule_id"] == "QF-06" for reason in queries[0]["quality_filter_reasons"])
    assert report["qf_counts"]["QF-06"] == 1


def test_qf_06_archives_duplicate_inside_generated_batch():
    text = "银行积分商城系统有哪些成熟供应商？"
    first = _query(text)
    second = {**_query(text), "query_id": "q_002"}

    queries, report = apply_query_quality_filters([first, second], {}, [])

    assert queries[0]["lifecycle_status"] == "active"
    assert queries[1]["lifecycle_status"] == "archived"
    assert report["active_count"] == 1
    assert report["archived_count"] == 1
    assert report["qf_counts"]["QF-06"] == 1


def test_quality_report_fails_when_no_active_queries_remain():
    queries, report = apply_query_quality_filters([_query("太短")], {}, [])

    assert queries[0]["lifecycle_status"] == "archived"
    assert report["status"] == "failed"
    assert report["errors"][0]["name"] == "active_queries"


def test_qf_recomputes_status_when_upstream_governance_is_preserved():
    query = {
        **_query("银行积分商城系统有哪些成熟供应商？"),
        "lifecycle_status": "archived",
        "quality_filter_status": "archived",
        "quality_filter_reasons": [{"rule_id": "QF-06", "reason": "upstream duplicate"}],
    }

    queries, report = apply_query_quality_filters([query], {}, [], min_active_queries=1)

    assert queries[0]["lifecycle_status"] == "archived"
    assert report["active_count"] == 0
    assert queries[0]["quality_filter_reasons"][0]["rule_id"] == "QF-06"


def test_quality_report_enforces_minimum_active_queries():
    queries, report = apply_query_quality_filters([_query("银行积分商城系统有哪些成熟供应商？")], {}, [], min_active_queries=30)

    assert queries[0]["lifecycle_status"] == "active"
    assert report["status"] == "failed"
    assert report["errors"][0]["minimum"] == 30
    assert report["errors"][0]["actual"] == 1


def test_queryset_snapshot_keeps_candidates_but_exposes_only_active_queries():
    active = _query("银行积分商城系统有哪些成熟供应商？")
    archived = {**_query("太短"), "query_id": "q_002", "lifecycle_status": "archived"}

    snapshot = normalize_queryset_snapshot({"queryset_id": "qs_test", "queries": [active, archived]})

    assert len(snapshot["query_candidates"]) == 2
    assert len(snapshot["queries"]) == 1
    assert snapshot["queries"][0]["query_id"] == "q_001"


def test_production_queryset_gate_rejects_active_count_below_30(monkeypatch):
    monkeypatch.delenv("MIN_ACTIVE_QUERIES", raising=False)
    queryset = {
        "queryset_id": "qs_small",
        "queries": [{**_query(f"银行积分商城系统有哪些成熟供应商{i:02d}？"), "query_id": f"q_{i:03d}"} for i in range(1, 4)],
    }

    with pytest.raises(RuntimeError, match="minimum required is 30"):
        validate_queryset_for_production(queryset)


def test_production_queryset_gate_passes_and_records_quality_gate(monkeypatch):
    monkeypatch.delenv("MIN_ACTIVE_QUERIES", raising=False)
    queryset = {
        "queryset_id": "qs_ready",
        "queries": [
            {**_query(f"银行积分商城系统有哪些成熟供应商{i:02d}？"), "query_id": f"q_{i:03d}"}
            for i in range(1, 31)
        ],
    }

    snapshot = validate_queryset_for_production(queryset)

    assert len(snapshot["queries"]) == 30
    assert snapshot["governance"]["quality_gate"]["status"] == "pass"
    assert snapshot["governance"]["quality_gate"]["active_count"] == 30


def test_production_queryset_gate_ignores_min_active_env_below_floor(monkeypatch):
    monkeypatch.setenv("MIN_ACTIVE_QUERIES", "1")
    queryset = {
        "queryset_id": "qs_dev",
        "queries": [{**_query("银行积分商城系统有哪些成熟供应商？"), "query_id": "q_001"}],
    }

    with pytest.raises(RuntimeError, match="minimum required is 30"):
        validate_queryset_for_production(queryset)


def test_production_queryset_gate_allows_min_active_env_to_raise_floor(monkeypatch):
    monkeypatch.setenv("MIN_ACTIVE_QUERIES", "31")
    queryset = {
        "queryset_id": "qs_ready",
        "queries": [
            {**_query(f"银行积分商城系统有哪些成熟供应商{i:02d}？"), "query_id": f"q_{i:03d}"}
            for i in range(1, 32)
        ],
    }

    snapshot = validate_queryset_for_production(queryset)

    assert len(snapshot["queries"]) == 31
    assert snapshot["governance"]["quality_gate"]["min_active_queries"] == 31
