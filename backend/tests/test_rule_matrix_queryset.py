from service.queryset_policy import apply_query_quality_filters
from service.queryset import generate_queryset
from collections import Counter

from service.rule_matrix import allocate_matrix_cell_counts, generate_rule_matrix_queryset
from service.queryset_matrix_client import QuerySetMatrixClient


def _brand_config():
    return {
        "brand_config_id": "bc_duiba",
        "entity_id": "ent_duiba",
        "entity_name": "兑吧",
        "entity_aliases": ["Duiba"],
        "industry_segments": ["移动App用户运营"],
        "topics": [
            {"topic_name": "积分商城管理工具", "business_line": "积分商城", "pain_point": "积分运营低效", "goal": "提升用户活跃"},
            {"topic_name": "互动广告平台", "business_line": "互动广告", "pain_point": "广告转化不足", "goal": "提升营销收益"},
        ],
        "competitors": [
            {"name": "有赞"},
            {"name": "微盟"},
            {"name": "星耀"},
        ],
    }


def test_rule_matrix_generates_around_40_candidates_by_default(monkeypatch):
    monkeypatch.delenv("MAX_QUERIES_PER_RUN", raising=False)

    queryset = generate_rule_matrix_queryset(_brand_config())
    queries = queryset["queries"]

    assert len(queries) == 40
    assert queries[0]["query_id"] == "q_001"
    assert queries[-1]["query_id"] == "q_040"
    assert len({query["query_text"] for query in queries}) == 40
    assert all(query["matrix_cell_id"] == f"{query['journey_stage']}:{query['query_pattern']}" for query in queries)


def test_rule_matrix_default_allocation_matches_mvp_matrix(monkeypatch):
    monkeypatch.delenv("MAX_QUERIES_PER_RUN", raising=False)
    monkeypatch.delenv("QUERYSET_CANDIDATE_QUERIES", raising=False)

    queryset = generate_rule_matrix_queryset(_brand_config())
    counts = Counter(query["matrix_cell_id"] for query in queryset["queries"])

    assert queryset["allocation"]["strategy"] == "weighted_largest_remainder"
    assert queryset["allocation"]["default_candidate_count"] == 40
    assert dict(counts) == {
        "problem_discovery:scenario_explore": 3,
        "problem_discovery:category_rec": 6,
        "solution_evaluation:scenario_explore": 4,
        "solution_evaluation:category_rec": 5,
        "solution_evaluation:deep_background": 2,
        "solution_evaluation:competitive_comp": 6,
        "purchase_decision:vendor_choice": 4,
        "purchase_decision:internal_justification": 2,
        "purchase_decision:purchase_risk": 2,
        "purchase_decision:commercial_terms": 2,
        "purchase_decision:competitive_comp": 4,
    }


def test_rule_matrix_operator_count_uses_weighted_allocation():
    assert sum(allocate_matrix_cell_counts(24).values()) == 24

    queryset = generate_rule_matrix_queryset(_brand_config(), candidate_count=24)

    assert len(queryset["queries"]) == 24
    assert queryset["allocation"]["requested_candidate_count"] == 24
    assert queryset["allocation"]["effective_candidate_count"] == 24


def test_rule_matrix_queries_pass_qf_and_core_weights_sum_to_one(monkeypatch):
    monkeypatch.delenv("MAX_QUERIES_PER_RUN", raising=False)

    queryset = generate_rule_matrix_queryset(_brand_config())
    queries, report = apply_query_quality_filters(queryset["queries"], _brand_config(), [], min_active_queries=30)
    core_weight = sum(query["metric_weight"] for query in queries if query["metric_scope"] == "core_trend")

    assert report["status"] == "pass"
    assert report["active_count"] == 40
    assert report["archived_count"] == 0
    assert report["rejected_count"] == 0
    assert round(core_weight, 6) == 1


def test_rule_matrix_respects_max_queries_per_run(monkeypatch):
    monkeypatch.setenv("MAX_QUERIES_PER_RUN", "12")

    queryset = generate_rule_matrix_queryset(_brand_config())

    assert len(queryset["queries"]) == 12
    assert queryset["queries"][-1]["query_id"] == "q_012"


def test_generate_queryset_retries_until_minimum_active_queries(monkeypatch):
    import asyncio

    class StubClient:
        def __init__(self):
            self.calls = 0

        async def generate(self, brand_config, run):
            self.calls += 1
            if self.calls == 1:
                return {
                    "queryset_id": "qs_low_quality",
                    "queryset_version": "rule_matrix_v1",
                    "matrix_api_request_id": "mx_low_quality",
                    "queries": generate_rule_matrix_queryset(brand_config, candidate_count=5)["queries"],
                }
            return generate_rule_matrix_queryset(brand_config, candidate_count=40)

    client = StubClient()
    monkeypatch.setattr("service.queryset.QuerySetMatrixClient", lambda: client)
    queryset = asyncio.run(
        generate_queryset(
            _brand_config(),
            {
                "queryset_source": "matrix_api_v1",
                "queryset_strategy": "rule_matrix_v1",
                "generation_constraints": {
                    "candidate_queries": 40,
                    "min_active_queries": 30,
                    "max_generation_attempts": 2,
                },
            },
        )
    )

    assert client.calls == 2
    assert queryset["quality_report"]["status"] == "pass"
    assert queryset["quality_report"]["generation_attempt"] == 2
    assert queryset["quality_report"]["generation_mode"] == "accumulate_until_min_active"
    assert queryset["quality_report"]["attempt_reports"][0]["active_count"] == 5
    assert len(queryset["query_candidates"]) == 45
    assert len(queryset["queries"]) == 40
    assert len({query["query_id"] for query in queryset["query_candidates"]}) == 45
    assert all(query.get("generation_attempt") in {1, 2} for query in queryset["query_candidates"])


def test_generate_queryset_attempt_variants_avoid_existing_duplicate_texts(monkeypatch):
    import asyncio

    previous_texts = {
        query["query_text"]
        for query in generate_rule_matrix_queryset(_brand_config(), candidate_count=40)["queries"]
    }
    monkeypatch.setattr("service.queryset._collect_existing_active_texts", lambda brand_config, include_historical=True: previous_texts)
    monkeypatch.delenv("QUERYSET_MATRIX_API_URL", raising=False)
    monkeypatch.setenv("ALLOW_LOCAL_QUERYSET_FALLBACK", "true")

    queryset = asyncio.run(
        generate_queryset(
            _brand_config(),
            {
                "queryset_source": "matrix_api_v1",
                "queryset_strategy": "rule_matrix_v1",
                "generation_constraints": {
                    "candidate_queries": 40,
                    "min_active_queries": 30,
                    "max_generation_attempts": 3,
                },
            },
        )
    )

    assert queryset["quality_report"]["status"] == "pass"
    assert queryset["quality_report"]["generation_attempt"] == 2
    assert queryset["quality_report"]["attempt_reports"][0]["active_count"] == 0
    assert queryset["quality_report"]["attempt_reports"][0]["qf_counts"]["QF-06"] == 40
    assert queryset["quality_report"]["attempt_reports"][1]["active_count"] == 40
    assert len(queryset["queries"]) == 40


def test_generate_queryset_create_new_version_ignores_historical_duplicate_texts(monkeypatch):
    import asyncio

    previous_texts = {
        query["query_text"]
        for query in generate_rule_matrix_queryset(_brand_config(), candidate_count=40)["queries"]
    }
    monkeypatch.setattr(
        "service.queryset._collect_existing_active_texts",
        lambda brand_config, include_historical=True: previous_texts if include_historical else set(),
    )
    monkeypatch.delenv("QUERYSET_MATRIX_API_URL", raising=False)
    monkeypatch.setenv("ALLOW_LOCAL_QUERYSET_FALLBACK", "true")

    queryset = asyncio.run(
        generate_queryset(
            _brand_config(),
            {
                "queryset_source": "matrix_api_v1",
                "queryset_strategy": "rule_matrix_v1",
                "queryset_policy": "create_new_version",
                "generation_constraints": {
                    "candidate_queries": 40,
                    "min_active_queries": 30,
                    "max_generation_attempts": 3,
                },
            },
        )
    )

    assert queryset["quality_report"]["status"] == "pass"
    assert queryset["quality_report"]["generation_attempt"] == 1
    assert queryset["quality_report"]["attempt_reports"][0]["active_count"] == 40
    assert len(queryset["queries"]) == 40


def test_generate_queryset_candidate_default_honors_max_queries_per_run(monkeypatch):
    import asyncio

    monkeypatch.delenv("QUERYSET_CANDIDATE_QUERIES", raising=False)
    monkeypatch.setenv("MAX_QUERIES_PER_RUN", "3")
    monkeypatch.setenv("MIN_ACTIVE_QUERIES", "3")
    monkeypatch.delenv("QUERYSET_MATRIX_API_URL", raising=False)
    monkeypatch.setenv("ALLOW_LOCAL_QUERYSET_FALLBACK", "true")

    queryset = asyncio.run(
        generate_queryset(
            _brand_config(),
            {
                "queryset_source": "matrix_api_v1",
                "queryset_strategy": "rule_matrix_v1",
                "queryset_policy": "create_new_version",
            },
        )
    )

    assert queryset["quality_report"]["status"] == "pass"
    assert len(queryset["queries"]) == 3


def test_generate_queryset_create_new_version_rejudges_upstream_archived_candidates(monkeypatch):
    import asyncio

    class StubClient:
        async def generate(self, brand_config, run):
            queryset = generate_rule_matrix_queryset(brand_config, candidate_count=40)
            queryset["matrix_api_request_id"] = "mx_rejudge"
            queryset["queries"] = [
                {
                    **query,
                    "lifecycle_status": "archived",
                    "quality_filter_status": "archived",
                    "quality_filter_reasons": [{"rule_id": "QF-06", "reason": "upstream duplicate"}],
                }
                for query in queryset["queries"]
            ]
            return queryset

    monkeypatch.setattr("service.queryset.QuerySetMatrixClient", lambda: StubClient())

    queryset = asyncio.run(
        generate_queryset(
            _brand_config(),
            {
                "queryset_source": "matrix_api_v1",
                "queryset_strategy": "rule_matrix_v1",
                "queryset_policy": "create_new_version",
                "generation_constraints": {
                    "candidate_queries": 40,
                    "min_active_queries": 30,
                    "max_generation_attempts": 1,
                },
            },
        )
    )

    assert queryset["quality_report"]["status"] == "pass"
    assert queryset["quality_report"]["active_count"] == 40
    assert all(query["lifecycle_status"] == "active" for query in queryset["queries"])
    assert all(query["quality_filter_reasons"] == [] for query in queryset["queries"])


def test_matrix_client_requires_explicit_local_fallback(monkeypatch):
    import asyncio
    import pytest

    monkeypatch.delenv("QUERYSET_MATRIX_API_URL", raising=False)
    monkeypatch.delenv("ALLOW_LOCAL_QUERYSET_FALLBACK", raising=False)

    with pytest.raises(RuntimeError, match="ALLOW_LOCAL_QUERYSET_FALLBACK=true"):
        asyncio.run(QuerySetMatrixClient().generate(_brand_config(), {"queryset_strategy": "rule_matrix_v1"}))


def test_matrix_client_local_fallback_has_lineage(monkeypatch):
    import asyncio

    monkeypatch.delenv("QUERYSET_MATRIX_API_URL", raising=False)
    monkeypatch.setenv("ALLOW_LOCAL_QUERYSET_FALLBACK", "true")

    queryset = asyncio.run(QuerySetMatrixClient().generate(_brand_config(), {"queryset_strategy": "rule_matrix_v1"}))

    assert queryset["matrix_api_request_id"].startswith("mx_local_")
    assert queryset["debug"]["transport"] == "local_rule_matrix"
    assert queryset["debug"]["fallback_reason"] == "missing_matrix_api_url"


def test_generate_queryset_failure_exposes_last_attempt_diagnostics(monkeypatch):
    import asyncio
    import pytest

    from service.queryset import QuerySetGenerationFailed

    class StubClient:
        async def generate(self, brand_config, run):
            queryset = generate_rule_matrix_queryset(brand_config, candidate_count=40)
            queryset["queryset_id"] = "qs_failed"
            queryset["matrix_api_request_id"] = "mx_failed"
            queryset["queries"] = [
                {
                    **query,
                    "lifecycle_status": "archived",
                    "quality_filter_status": "archived",
                    "quality_filter_reasons": [{"rule_id": "QF-06", "reason": "upstream duplicate"}],
                }
                for query in queryset["queries"]
            ]
            return queryset

    monkeypatch.setattr("service.queryset.QuerySetMatrixClient", lambda: StubClient())

    with pytest.raises(QuerySetGenerationFailed) as exc_info:
        asyncio.run(
            generate_queryset(
                _brand_config(),
                {
                    "queryset_source": "matrix_api_v1",
                    "queryset_strategy": "rule_matrix_v1",
                    "generation_constraints": {
                        "candidate_queries": 40,
                        "min_active_queries": 30,
                        "max_generation_attempts": 1,
                    },
                },
            )
        )

    error = exc_info.value
    assert error.last_queryset_id == "qs_failed"
    assert error.matrix_api_request_id == "mx_failed"
    assert error.quality_report["cumulative_active_count"] == 0
    assert error.attempt_reports[0]["active_count"] == 0
    assert error.debug_context["queryset_policy"] == "reuse_latest"
    assert error.debug_context["accumulated_active_count"] == 0
    assert len(error.last_query_candidates_preview) == 40
    assert error.last_query_candidates_preview[0]["query_text"]
    assert error.last_query_candidates_preview[0]["quality_filter_reasons"][0]["rule_id"] == "QF-06"


def test_resolve_queryset_skips_invalid_reusable_queryset(monkeypatch):
    import asyncio
    from service import inspector

    monkeypatch.delenv("MIN_ACTIVE_QUERIES", raising=False)
    stale = {"queryset_id": "qs_stale", "queries": generate_rule_matrix_queryset(_brand_config(), candidate_count=3)["queries"]}
    regenerated = generate_rule_matrix_queryset(_brand_config(), candidate_count=40)

    async def fake_generate_queryset(brand_config, run):
        return regenerated

    monkeypatch.setattr(inspector, "_latest_reusable_queryset", lambda run, brand_config: stale)
    monkeypatch.setattr(inspector, "generate_queryset", fake_generate_queryset)
    monkeypatch.setattr(inspector, "_govern_queryset", lambda queryset, run, change_type: queryset)

    queryset = asyncio.run(inspector.resolve_queryset(_brand_config(), {"queryset_policy": "reuse_latest"}))

    assert queryset["queryset_id"] == regenerated["queryset_id"]
    assert len(queryset["queries"]) == 40
