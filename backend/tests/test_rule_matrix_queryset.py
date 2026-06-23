from service.queryset_policy import apply_query_quality_filters
from service import queryset as queryset_module
from service.queryset import QuerySetThresholdConfigurationError, generate_queryset
from collections import Counter

import pytest

from service.rule_matrix import MATRIX_TEMPLATES, allocate_matrix_cell_counts, generate_rule_matrix_queryset
from service.queryset_matrix_client import QuerySetMatrixClient, normalize_matrix_queryset


@pytest.fixture(autouse=True)
def disable_intent_analysis(monkeypatch):
    async def noop_extract_intent_analysis_batch(extractor, topics, entity_name):
        return {}

    monkeypatch.setattr("service.queryset._extract_intent_analysis_batch", noop_extract_intent_analysis_batch)


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


def test_queryset_context_extraction_uses_deterministic_fallback():
    import asyncio

    class FailingExtractor:
        async def extract_all(self, topics, entity_name):
            raise RuntimeError("claude returned an empty task content.")

    topics = [{"topic_name": "积分商城管理工具", "business_line": "积分商城"}]

    result = asyncio.run(queryset_module._extract_topic_contexts(FailingExtractor(), topics, "兑吧"))

    assert result[0]["pain_point"] == "积分商城管理工具效果不稳定"
    assert result[0]["goal"] == "提升积分商城管理工具业务效果"
    assert result[0]["context_fallback_used"] is True


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


def test_competitive_comp_queries_do_not_name_own_brand_or_competitors(monkeypatch):
    monkeypatch.delenv("MAX_QUERIES_PER_RUN", raising=False)
    prohibited_placeholders = {"{entity}", "{competitors}", "{primary_competitor}", "{secondary_competitor}"}
    prohibited_names = {"兑吧", "Duiba", "有赞", "微盟", "星耀"}

    competitive_templates = [
        template for template in MATRIX_TEMPLATES if template["query_pattern"] == "competitive_comp"
    ]
    assert competitive_templates
    assert all(
        placeholder not in template["text"]
        for template in competitive_templates
        for placeholder in prohibited_placeholders
    )

    queryset = generate_rule_matrix_queryset(_brand_config())
    competitive_queries = [
        query for query in queryset["queries"] if query["query_pattern"] == "competitive_comp"
    ]

    assert len(competitive_queries) == 10
    assert all(
        name not in query["query_text"]
        for query in competitive_queries
        for name in prohibited_names
    )
    assert all("related_competitors" not in query for query in competitive_queries)


def test_rule_matrix_operator_count_uses_weighted_allocation():
    assert sum(allocate_matrix_cell_counts(24).values()) == 24

    queryset = generate_rule_matrix_queryset(_brand_config(), candidate_count=24)

    assert len(queryset["queries"]) == 24
    assert queryset["allocation"]["requested_candidate_count"] == 24
    assert queryset["allocation"]["effective_candidate_count"] == 24


def test_matrix_normalization_drops_related_competitors():
    queryset = normalize_matrix_queryset(
        {
            "queryset_id": "qs_upstream",
            "queries": [
                {
                    "query_id": "q_001",
                    "query_text": "积分商城供应商怎么选？",
                    "topic": "积分商城",
                    "intent_type": "category_rec",
                    "query_pattern": "category_rec",
                    "related_competitors": ["有赞", "微盟"],
                    "competitors": ["有赞", "微盟"],
                }
            ],
        }
    )

    assert "related_competitors" not in queryset["queries"][0]


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


def test_rule_matrix_can_append_anonymous_negative_probes(monkeypatch):
    monkeypatch.delenv("MAX_QUERIES_PER_RUN", raising=False)
    prohibited_names = {"兑吧", "Duiba", "有赞", "微盟", "星耀"}

    queryset = generate_rule_matrix_queryset(_brand_config(), candidate_count=36, negative_probe_count=12)
    probes = [query for query in queryset["queries"] if query.get("metric_scope") == "negative_probe"]

    assert len(queryset["queries"]) == 48
    assert len(probes) == 12
    assert queryset["queries"][-1]["query_id"] == "q_048"
    assert all(query["sentiment_intent"] == "negative" for query in probes)
    assert all(
        name not in query["query_text"]
        for query in probes
        for name in prohibited_names
    )

    filtered, report = apply_query_quality_filters(queryset["queries"], _brand_config(), [], min_active_queries=48)
    assert report["status"] == "pass"
    assert len([query for query in filtered if query["lifecycle_status"] == "active"]) == 48


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


def test_generate_queryset_injects_intent_analysis_queries(monkeypatch):
    import asyncio

    class StubClient:
        async def generate(self, brand_config, run):
            return generate_rule_matrix_queryset(brand_config, candidate_count=3)

    async def fake_extract_intent_analysis_batch(extractor, topics, entity_name):
        return {
            "积分商城管理工具": {
                "audience_profile": "银行和App积分运营负责人",
                "pain_points": [
                    {
                        "pain_point": "积分消耗率低",
                        "severity": 5,
                        "goal": "提升用户活跃",
                        "ai_questions": [
                            {
                                "question": "银行积分商城积分消耗率低，应该优先优化哪些运营场景？",
                                "intent_type": "scenario_diagnosis",
                            }
                        ],
                    }
                ],
            }
        }

    monkeypatch.setattr("service.queryset.QuerySetMatrixClient", lambda: StubClient())
    monkeypatch.setattr("service.queryset._extract_intent_analysis_batch", fake_extract_intent_analysis_batch)

    queryset = asyncio.run(
        generate_queryset(
            _brand_config(),
            {
                "queryset_source": "matrix_api_v1",
                "queryset_strategy": "rule_matrix_v1",
                "queryset_policy": "create_new_version",
                "generation_constraints": {
                    "candidate_queries": 3,
                    "min_active_queries": 3,
                    "max_generation_attempts": 1,
                    "allow_small_queryset": True,
                },
            },
        )
    )

    intent_queries = [query for query in queryset["queries"] if query.get("metric_scope") == "intent_driven"]
    assert len(intent_queries) == 1
    assert intent_queries[0]["source"] == "intent_analysis"
    assert intent_queries[0]["pain_point"] == "积分消耗率低"
    assert intent_queries[0]["query_text"] == "银行积分商城积分消耗率低，应该优先优化哪些运营场景？"
    assert queryset["queryset_generation_mode"] == "intent_enhanced"
    assert queryset["query_candidates"][0]["query_id"].startswith("q_")


def test_generate_queryset_matrix_only_skips_intent_analysis(monkeypatch):
    import asyncio

    class StubClient:
        async def generate(self, brand_config, run):
            return generate_rule_matrix_queryset(brand_config, candidate_count=3)

    async def unexpected_extract_intent_analysis_batch(extractor, topics, entity_name):
        raise AssertionError("matrix_only must not call intent analysis")

    monkeypatch.setattr("service.queryset.QuerySetMatrixClient", lambda: StubClient())
    monkeypatch.setattr("service.queryset._extract_intent_analysis_batch", unexpected_extract_intent_analysis_batch)

    brand_config = _brand_config()
    brand_config["topics"][0]["intent_analysis"] = {
        "audience_profile": "运营负责人",
        "pain_points": [
            {
                "pain_point": "积分消耗率低",
                "severity": 5,
                "ai_questions": [
                    {"question": "这条问题不应该进入原矩阵版", "intent_type": "scenario_diagnosis"}
                ],
            }
        ],
    }
    queryset = asyncio.run(
        generate_queryset(
            brand_config,
            {
                "queryset_source": "matrix_api_v1",
                "queryset_strategy": "rule_matrix_v1",
                "queryset_policy": "create_new_version",
                "generation_constraints": {
                    "queryset_generation_mode": "matrix_only",
                    "candidate_queries": 3,
                    "min_active_queries": 3,
                    "max_generation_attempts": 1,
                    "allow_small_queryset": True,
                },
            },
        )
    )

    assert queryset["queryset_generation_mode"] == "matrix_only"
    assert all(query.get("metric_scope") != "intent_driven" for query in queryset["queries"])
    assert all(query.get("source") != "intent_analysis" for query in queryset["query_candidates"])


def test_generate_queryset_rejects_unknown_generation_mode(monkeypatch):
    import asyncio
    import pytest

    with pytest.raises(QuerySetThresholdConfigurationError, match="Unsupported queryset_generation_mode"):
        asyncio.run(
            generate_queryset(
                _brand_config(),
                {
                    "queryset_source": "matrix_api_v1",
                    "queryset_strategy": "rule_matrix_v1",
                    "generation_constraints": {
                        "queryset_generation_mode": "mystery_mode",
                        "candidate_queries": 3,
                        "min_active_queries": 3,
                        "allow_small_queryset": True,
                    },
                },
            )
        )


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
                "generation_constraints": {"allow_small_queryset": True},
            },
        )
    )

    assert queryset["quality_report"]["status"] == "pass"
    assert len(queryset["queries"]) == 3


def test_generate_queryset_rejects_small_production_thresholds_before_client(monkeypatch):
    import asyncio
    import pytest

    class StubClient:
        calls = 0

        async def generate(self, brand_config, run):
            self.calls += 1
            return generate_rule_matrix_queryset(brand_config, candidate_count=1)

    client = StubClient()
    monkeypatch.setattr("service.queryset.QuerySetMatrixClient", lambda: client)

    with pytest.raises(QuerySetThresholdConfigurationError, match="candidate_queries >= 30"):
        asyncio.run(
            generate_queryset(
                _brand_config(),
                {
                    "queryset_source": "matrix_api_v1",
                    "queryset_strategy": "rule_matrix_v1",
                    "generation_constraints": {
                        "candidate_queries": 1,
                        "min_active_queries": 1,
                    },
                },
            )
        )

    assert client.calls == 0


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
    monkeypatch.delenv("CLAUDE_BASE_URL", raising=False)
    monkeypatch.delenv("ALLOW_LOCAL_QUERYSET_FALLBACK", raising=False)

    with pytest.raises(RuntimeError, match="ALLOW_LOCAL_QUERYSET_FALLBACK=true"):
        asyncio.run(QuerySetMatrixClient().generate(_brand_config(), {"queryset_strategy": "rule_matrix_v1"}))


def test_matrix_client_local_fallback_has_lineage(monkeypatch):
    import asyncio

    monkeypatch.delenv("QUERYSET_MATRIX_API_URL", raising=False)
    monkeypatch.delenv("CLAUDE_BASE_URL", raising=False)
    monkeypatch.setenv("ALLOW_LOCAL_QUERYSET_FALLBACK", "true")

    queryset = asyncio.run(QuerySetMatrixClient().generate(_brand_config(), {"queryset_strategy": "rule_matrix_v1"}))

    assert queryset["matrix_api_request_id"].startswith("mx_local_")
    assert queryset["debug"]["transport"] == "local_rule_matrix"
    assert queryset["debug"]["fallback_reason"] == "missing_matrix_api_url"


def test_matrix_client_defaults_to_shared_claude_responses(monkeypatch):
    import asyncio
    import json

    calls = []

    class StubResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "model": "gpt-5.5",
                "output_text": json.dumps(
                    {
                        "queryset_id": "qs_shared_matrix",
                        "queryset_version": "rule_matrix_v1",
                        "matrix_api_request_id": "mx_shared_1",
                        "queries": [
                            {
                                "query_id": "q_001",
                                "query_text": "兑吧适合哪些积分商城运营场景？",
                                "query_layer": "core_anchor",
                                "run_scope": "production",
                                "metric_scope": "core_trend",
                                "journey_stage": "problem_discovery",
                                "topic": "积分商城",
                                "intent_type": "scenario_explore",
                                "query_pattern": "scenario_explore",
                                "matrix_cell_id": "problem_discovery:scenario_explore",
                                "lifecycle_status": "active",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
            }

    class StubAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, headers, json):
            calls.append({"url": url, "headers": headers, "json": json})
            return StubResponse()

    monkeypatch.delenv("QUERYSET_MATRIX_API_URL", raising=False)
    monkeypatch.setenv("QUERYSET_MATRIX_API_KEY", "")
    monkeypatch.setenv("QUERYSET_MATRIX_MODEL", "")
    monkeypatch.delenv("QUERYSET_MATRIX_API_STYLE", raising=False)
    monkeypatch.setenv("CLAUDE_BASE_URL", "https://newapi.ailyyzdk.xyz/")
    monkeypatch.setenv("CLAUDE_API_KEY", "sk-shared")
    monkeypatch.setenv("CLAUDE_MODEL", "gpt-5.5")
    monkeypatch.setenv("CLAUDE_RESPONSES_ENDPOINT", "/responses")
    monkeypatch.setattr("service.queryset_matrix_client.httpx.AsyncClient", StubAsyncClient)

    queryset = asyncio.run(
        QuerySetMatrixClient().generate(
            _brand_config(),
            {
                "queryset_strategy": "rule_matrix_v1",
                "generation_constraints": {"candidate_queries": 1, "allow_small_queryset": True},
            },
        )
    )

    assert queryset["queryset_id"] == "qs_shared_matrix"
    assert queryset["debug"]["transport"] == "openai_compatible_responses"
    assert queryset["debug"]["provider"] == "claude"
    assert queryset["debug"]["model"] == "gpt-5.5"
    assert calls[0]["url"] == "https://newapi.ailyyzdk.xyz/responses"
    assert calls[0]["headers"]["Authorization"] == "Bearer sk-shared"
    assert calls[0]["json"]["model"] == "gpt-5.5"
    assert "input" in calls[0]["json"]
    assert "messages" not in calls[0]["json"]


def test_matrix_client_falls_back_when_shared_responses_returns_empty_body(monkeypatch):
    import asyncio

    class EmptyResponse:
        status_code = 200
        text = ""
        headers = {"content-type": "text/plain"}

        def raise_for_status(self):
            return None

        def json(self):
            raise ValueError("Expecting value: line 1 column 1 (char 0)")

    class StubAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, headers, json):
            return EmptyResponse()

    monkeypatch.delenv("QUERYSET_MATRIX_API_URL", raising=False)
    monkeypatch.delenv("QUERYSET_MATRIX_API_STYLE", raising=False)
    monkeypatch.setenv("CLAUDE_BASE_URL", "https://newapi.ailyyzdk.xyz/")
    monkeypatch.setenv("CLAUDE_API_KEY", "sk-shared")
    monkeypatch.setenv("CLAUDE_MODEL", "gpt-5.5")
    monkeypatch.setenv("CLAUDE_RESPONSES_ENDPOINT", "/responses")
    monkeypatch.setenv("ALLOW_LOCAL_QUERYSET_FALLBACK", "true")
    monkeypatch.setattr("service.queryset_matrix_client.httpx.AsyncClient", StubAsyncClient)

    queryset = asyncio.run(QuerySetMatrixClient().generate(_brand_config(), {"queryset_strategy": "rule_matrix_v1"}))

    assert queryset["debug"]["transport"] == "local_rule_matrix"
    assert queryset["debug"]["fallback_reason"] == "matrix_api_failed"
    assert "empty response body" in queryset["debug"]["upstream_error"]
    assert len(queryset["queries"]) == 40


def test_matrix_client_empty_shared_response_reports_readable_error_without_fallback(monkeypatch):
    import asyncio
    import pytest

    class EmptyResponse:
        status_code = 200
        text = ""
        headers = {"content-type": "text/plain"}

        def raise_for_status(self):
            return None

        def json(self):
            raise ValueError("Expecting value: line 1 column 1 (char 0)")

    class StubAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, headers, json):
            return EmptyResponse()

    monkeypatch.delenv("QUERYSET_MATRIX_API_URL", raising=False)
    monkeypatch.delenv("QUERYSET_MATRIX_API_STYLE", raising=False)
    monkeypatch.setenv("CLAUDE_BASE_URL", "https://newapi.ailyyzdk.xyz/")
    monkeypatch.setenv("CLAUDE_API_KEY", "sk-shared")
    monkeypatch.setenv("CLAUDE_MODEL", "gpt-5.5")
    monkeypatch.setenv("CLAUDE_RESPONSES_ENDPOINT", "/responses")
    monkeypatch.delenv("ALLOW_LOCAL_QUERYSET_FALLBACK", raising=False)
    monkeypatch.setattr("service.queryset_matrix_client.httpx.AsyncClient", StubAsyncClient)

    with pytest.raises(RuntimeError, match="returned invalid JSON.*empty response body"):
        asyncio.run(QuerySetMatrixClient().generate(_brand_config(), {"queryset_strategy": "rule_matrix_v1"}))


def test_matrix_client_can_use_openai_compatible_claude_chat(monkeypatch):
    import asyncio
    import json

    calls = []

    class StubResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "model": "claude-test",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "queryset_id": "qs_claude_matrix",
                                    "queryset_version": "rule_matrix_v1",
                                    "matrix_api_request_id": "mx_claude_1",
                                    "queries": [
                                        {
                                            "query_id": "q_001",
                                            "query_text": "兑吧适合哪些积分商城运营场景？",
                                            "query_layer": "core_anchor",
                                            "run_scope": "production",
                                            "metric_scope": "core_trend",
                                            "journey_stage": "problem_discovery",
                                            "topic": "积分商城",
                                            "intent_type": "scenario_explore",
                                            "query_pattern": "scenario_explore",
                                            "matrix_cell_id": "problem_discovery:scenario_explore",
                                            "lifecycle_status": "active",
                                        }
                                    ],
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ],
            }

    class StubAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, headers, json):
            calls.append({"url": url, "headers": headers, "json": json})
            return StubResponse()

    monkeypatch.setenv("QUERYSET_MATRIX_API_URL", "https://active-claude.example/v1/chat/completions")
    monkeypatch.setenv("QUERYSET_MATRIX_API_KEY", "sk-matrix")
    monkeypatch.setenv("QUERYSET_MATRIX_MODEL", "claude-test")
    monkeypatch.setattr("service.queryset_matrix_client.httpx.AsyncClient", StubAsyncClient)

    queryset = asyncio.run(
        QuerySetMatrixClient().generate(
            _brand_config(),
            {
                "queryset_strategy": "rule_matrix_v1",
                "generation_constraints": {"candidate_queries": 1, "allow_small_queryset": True},
            },
        )
    )

    assert queryset["queryset_id"] == "qs_claude_matrix"
    assert queryset["matrix_api_request_id"] == "mx_claude_1"
    assert queryset["debug"]["transport"] == "openai_compatible_chat"
    assert queryset["debug"]["provider"] == "claude"
    assert calls[0]["url"] == "https://active-claude.example/v1/chat/completions"
    assert calls[0]["headers"]["Authorization"] == "Bearer sk-matrix"
    assert calls[0]["json"]["model"] == "claude-test"
    assert calls[0]["json"]["response_format"] == {"type": "json_object"}


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
