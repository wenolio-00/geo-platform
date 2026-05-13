from __future__ import annotations

import os
from uuid import uuid4


def generate_rule_matrix_queryset(brand_config: dict, strategy: str = "rule_matrix_v1") -> dict:
    topics = _topics(brand_config)
    competitors = _competitor_names(brand_config)
    queries: list[dict] = []

    for topic in topics:
        related = competitors[:3]
        queries.extend(
            [
                _query(
                    topic,
                    f"{_segment_prefix(brand_config)}{topic}有哪些成熟供应商？",
                    "core_anchor",
                    "production",
                    "core_trend",
                    "category_rec",
                    "vendor_recommendation",
                    related,
                ),
                _query(
                    topic,
                    f"选择{topic}服务商时，应该重点比较哪些能力？",
                    "core_anchor",
                    "production",
                    "core_trend",
                    "decision_confirm",
                    "decision_criteria",
                    related,
                ),
                _query(
                    topic,
                    f"{brand_config['entity_name']}和{_competitor_phrase(competitors)}在{topic}方面有什么差异？",
                    "adaptive",
                    "production",
                    "competitive_gap",
                    "competitive_comp",
                    "competitive_comparison",
                    related,
                ),
            ]
        )

    max_queries = max(1, int(os.getenv("MAX_QUERIES_PER_RUN", "12")))
    normalized = []
    for index, query in enumerate(queries[:max_queries], start=1):
        normalized.append({"query_id": f"q_{index:03d}", **query})

    return {
        "queryset_id": f"qs_{uuid4().hex[:12]}",
        "queryset_version": strategy,
        "matrix_api_request_id": f"mx_local_{uuid4().hex[:12]}",
        "queries": normalized,
    }


def _topics(brand_config: dict) -> list[str]:
    values = [
        str(item.get("business_line") or item.get("topic_name") or "").strip()
        for item in brand_config.get("topics", [])
        if isinstance(item, dict)
    ]
    values = [value for value in values if value]
    return list(dict.fromkeys(values)) or ["品牌核心业务"]


def _competitor_names(brand_config: dict) -> list[str]:
    return [
        str(item.get("name", "")).strip()
        for item in brand_config.get("competitors", [])
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    ]


def _segment_prefix(brand_config: dict) -> str:
    segments = [str(value).strip() for value in brand_config.get("industry_segments", []) if str(value).strip()]
    return f"{segments[0]}里，" if segments else ""


def _competitor_phrase(competitors: list[str]) -> str:
    if competitors:
        return "、".join(competitors[:2])
    return "主要竞品"


def _query(
    topic: str,
    text: str,
    layer: str,
    run_scope: str,
    metric_scope: str,
    query_pattern: str,
    intent_type: str,
    competitors: list[str],
) -> dict:
    return {
        "query_text": text,
        "query_layer": layer,
        "run_scope": run_scope,
        "metric_scope": metric_scope,
        "topic": topic,
        "query_pattern": query_pattern,
        "intent_type": intent_type,
        "related_competitors": competitors,
    }
