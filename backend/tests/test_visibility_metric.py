from service.aggregator import aggregate_report
from service.dashboard_snapshots import METRIC_DEFINITIONS


def _brand_config() -> dict:
    return {
        "brand_config_id": "bc_visibility",
        "entity_id": "entity_visibility",
        "entity_name": "兑吧",
        "entity_aliases": ["Duiba"],
        "owned_domains": ["duiba.com.cn"],
        "topics": [{"topic_name": "积分商城", "business_line": "积分商城", "priority": 1}],
        "competitors": [{"name": "有赞", "aliases": [], "owned_domains": ["youzan.com"]}],
    }


def _run() -> dict:
    return {
        "inspection_batch_id": "batch_visibility",
        "queryset_strategy": "rule_matrix_v1",
        "queryset_source": "matrix_api_v1",
        "queryset_policy": "reuse_latest",
        "inspection_mode": "multi_platform_live_v1",
        "platforms_requested": ["DeepSeek"],
    }


def _queryset() -> dict:
    return {
        "queryset_id": "qs_visibility",
        "queryset_version": "rule_matrix_v1",
        "queries": [
            {"query_id": "q_generic_mentioned", "query_text": "积分商城工具有哪些？"},
            {"query_id": "q_brand_mentioned", "query_text": "兑吧积分商城适合哪些场景？"},
            {"query_id": "q_generic_missed", "query_text": "会员运营系统供应商怎么选？"},
            {"query_id": "q_alias_mentioned", "query_text": "Duiba 有哪些产品优势？"},
        ],
    }


def _result(query_id: str, query_text: str, mentions: list[dict]) -> dict:
    return {
        "inspection_id": f"insp_{query_id}",
        "status": "completed",
        "platform": "DeepSeek",
        "model": "deepseek-chat",
        "query_id": query_id,
        "query_text": query_text,
        "query_pattern": "category_rec",
        "query_layer": "core_anchor",
        "topic": "积分商城",
        "intent_type": "category_rec",
        "raw_answer": "ok",
        "parsed": {
            "answer": "ok",
            "mentioned_brands": mentions,
            "citations": [],
        },
    }


def test_visibility_counts_brand_free_queries_only():
    report = aggregate_report(
        _run(),
        _brand_config(),
        _queryset(),
        [
            _result(
                "q_generic_mentioned",
                "积分商城工具有哪些？",
                [{"name": "兑吧", "position": 1, "sentiment": "neutral"}],
            ),
            _result(
                "q_brand_mentioned",
                "兑吧积分商城适合哪些场景？",
                [{"name": "兑吧", "position": 1, "sentiment": "neutral"}],
            ),
            _result(
                "q_generic_missed",
                "会员运营系统供应商怎么选？",
                [{"name": "有赞", "position": 1, "sentiment": "neutral"}],
            ),
            _result(
                "q_alias_mentioned",
                "Duiba 有哪些产品优势？",
                [{"name": "兑吧", "position": 1, "sentiment": "neutral"}],
            ),
        ],
    )

    assert report["audit"]["visibility_eligible_samples"] == 2
    assert report["global"]["visibility"] == 0.5
    assert report["global"]["natural_visibility"] == 0.5
    assert report["global"]["assisted_visibility"] == 0.5
    assert report["global"]["visibility_lift"] == 0
    assert report["platforms"][0]["visibility"] == 0.5
    assert report["competitor_ranking"][0]["name"] == "兑吧"
    assert report["competitor_ranking"][0]["visibility"] == 0.5
    assert report["competitor_ranking"][1]["name"] == "有赞"
    assert report["competitor_ranking"][1]["visibility"] == 0.5
    topic_visibility = report["topic_platform_visibility"][0]
    assert topic_visibility["topic"] == "积分商城"
    assert topic_visibility["platforms"][0]["platform"] == "DeepSeek"
    assert topic_visibility["platforms"][0]["visibility_eligible_samples"] == 2
    assert topic_visibility["platforms"][0]["visibility"] == 0.5
    assert topic_visibility["platforms"][0]["competitor_rank"] == 1
    assert "可见度为 50.0%" in report["executive_summary"]


def test_two_round_visibility_uses_natural_and_assisted_mentions_separately():
    report = aggregate_report(
        _run(),
        _brand_config(),
        _queryset(),
        [
            {
                **_result("q_generic_mentioned", "积分商城工具有哪些？", []),
                "inspection_design": "blind_assisted",
                "natural_parsed": {
                    "answer": "如果只看成熟度，可以优先评估有赞。",
                    "mentioned_brands": [{"name": "有赞", "position": 1, "sentiment": "neutral"}],
                    "citations": [],
                },
                "assisted_parsed": {
                    "answer": "如果只看成熟度，可以优先评估有赞。",
                    "mentioned_brands": [{"name": "兑吧", "position": 1, "sentiment": "neutral"}],
                    "citations": [],
                },
            }
        ],
    )

    assert report["audit"]["visibility_eligible_samples"] == 1
    assert report["audit"]["natural_visibility_mentions"] == 0
    assert report["audit"]["assisted_visibility_mentions"] == 1
    assert report["global"]["visibility"] == 0
    assert report["global"]["natural_visibility"] == 0
    assert report["global"]["assisted_visibility"] == 1
    assert report["global"]["visibility_lift"] == 1
    assert report["global"]["visibility_source"] == "natural"


def test_dashboard_metric_config_exposes_natural_visibility_metrics():
    assert "natural_visibility" in METRIC_DEFINITIONS
    assert "assisted_visibility" in METRIC_DEFINITIONS
    assert "visibility_lift" in METRIC_DEFINITIONS
    assert METRIC_DEFINITIONS["visibility"]["metric_name"] == "可见度"
    assert METRIC_DEFINITIONS["natural_visibility"]["metric_name"] == "自然可见度"
    assert METRIC_DEFINITIONS["visibility"]["benchmark_label"] == "≥ 50%"
