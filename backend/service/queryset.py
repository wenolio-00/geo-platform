from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from models.schemas import QueryItem, QueryMatrixInput, QueryMatrixOutput, QueryQualityCheck, QueryQualityReport
from service.platform_registry import requested_platforms
from service.queryset_policy import (
    CELL_POLICIES,
    METRIC_SCOPES,
    QUERY_LAYERS,
    RUN_SCOPES,
    assign_metric_weights,
    matrix_cell_id,
    normalize_pattern,
    normalize_stage,
    policy_for,
)
from service.queryset_matrix_client import QuerySetMatrixClient
from service.storage import queryset_items_store, querysets_store


async def generate_queryset(brand_config: dict, run: dict) -> dict:
    matrix_input = build_query_matrix_input(brand_config, run)
    if matrix_input.queryset_source != "matrix_api_v1":
        raise RuntimeError(f"Unsupported queryset_source: {matrix_input.queryset_source}")

    generated = await QuerySetMatrixClient().generate(matrix_input.brand_config_snapshot, matrix_input.model_dump())
    output = normalize_query_matrix_output(generated, matrix_input)
    persist_queryset_snapshot(output, matrix_input.brand_config_snapshot)
    return output.model_dump()


def build_query_matrix_input(brand_config: dict, run: dict) -> QueryMatrixInput:
    snapshot = _json_snapshot(brand_config)
    return QueryMatrixInput(
        brand_config_snapshot=snapshot,
        run_id=str(run["run_id"]),
        queryset_strategy=run.get("queryset_strategy") or "rule_matrix_v1",
        queryset_source=run.get("queryset_source") or "matrix_api_v1",
        inspection_mode=run.get("inspection_mode") or "multi_platform_live_v1",
        platforms_requested=requested_platforms(run),
        generation_constraints={
            "min_queries": int(run.get("min_queries") or 1),
            "layer_policy": {
                "core_anchor": "stable_trend",
                "adaptive": "new_business_coverage",
                "experimental": "shadow_only",
            },
        },
    )


def normalize_query_matrix_output(data: dict, matrix_input: QueryMatrixInput) -> QueryMatrixOutput:
    if not isinstance(data, dict):
        raise RuntimeError("QuerySet generation must return a JSON object.")
    raw_queries = data.get("queries")
    if not isinstance(raw_queries, list):
        raise RuntimeError("QuerySet generation output is missing queries[].")

    normalized_items = [_normalize_query_item(item, index) for index, item in enumerate(raw_queries, start=1)]
    queries = [QueryItem(**item) for item in assign_metric_weights(normalized_items)]
    quality_report = build_query_quality_report(queries, matrix_input.brand_config_snapshot)
    if quality_report.status == "fail":
        detail = "; ".join(quality_report.errors) or "QuerySet quality gate failed."
        raise RuntimeError(detail)

    brand_config_id = matrix_input.brand_config_snapshot.get("brand_config_id")
    if not brand_config_id:
        raise RuntimeError("brand_config_snapshot.brand_config_id is required.")
    queryset_id = str(data.get("queryset_id") or "").strip()
    if not queryset_id:
        raise RuntimeError("QueryMatrixOutput.queryset_id is required.")

    return QueryMatrixOutput(
        queryset_id=queryset_id,
        queryset_version=str(data.get("queryset_version") or matrix_input.queryset_strategy),
        queryset_strategy=matrix_input.queryset_strategy,
        queryset_source=matrix_input.queryset_source,
        matrix_api_request_id=data.get("matrix_api_request_id"),
        brand_config_id=str(brand_config_id),
        run_id=matrix_input.run_id,
        queries=queries,
        quality_report=quality_report,
    )


def build_query_quality_report(queries: list[QueryItem], brand_config: dict) -> QueryQualityReport:
    checks: list[QueryQualityCheck] = []
    warnings: list[str] = []
    errors: list[str] = []

    if not queries:
        errors.append("QuerySet is empty.")
        checks.append(QueryQualityCheck(name="non_empty_queryset", status="fail", detail="No query items generated."))
    else:
        checks.append(QueryQualityCheck(name="non_empty_queryset", status="pass"))

    required_missing = []
    for query in queries:
        for field in (
            "query_id",
            "query_text",
            "query_layer",
            "run_scope",
            "journey_stage",
            "metric_scope",
            "topic",
            "intent_type",
            "query_pattern",
        ):
            if not getattr(query, field):
                required_missing.append(f"{query.query_id or '<missing-query-id>'}.{field}")
    if required_missing:
        errors.append(f"Missing required query fields: {', '.join(required_missing)}")
        checks.append(QueryQualityCheck(name="required_fields", status="fail"))
    else:
        checks.append(QueryQualityCheck(name="required_fields", status="pass"))

    text_counts = Counter(_dedupe_key(query.query_text) for query in queries)
    duplicate_texts = [text for text, count in text_counts.items() if count > 1]
    query_id_counts = Counter(query.query_id for query in queries)
    duplicate_ids = [query_id for query_id, count in query_id_counts.items() if count > 1]
    if duplicate_texts or duplicate_ids:
        errors.append("Duplicate query_id or query_text detected.")
        checks.append(QueryQualityCheck(name="dedupe", status="fail"))
    else:
        checks.append(QueryQualityCheck(name="dedupe", status="pass"))

    expected_topics = _expected_topics(brand_config)
    covered_topics = {query.topic for query in queries if query.topic}
    missing_topics = [topic for topic in expected_topics if topic not in covered_topics]
    if missing_topics:
        errors.append(f"Missing topic coverage: {', '.join(missing_topics)}")
        checks.append(QueryQualityCheck(name="topic_coverage", status="fail"))
    else:
        checks.append(QueryQualityCheck(name="topic_coverage", status="pass"))

    intent_counts = Counter(query.intent_type for query in queries)
    if len(intent_counts) <= 1 and len(queries) > 1:
        warnings.append("Intent distribution is degenerate.")
        checks.append(QueryQualityCheck(name="intent_distribution", status="warn"))
    else:
        checks.append(QueryQualityCheck(name="intent_distribution", status="pass"))

    layer_counts = Counter(query.query_layer for query in queries)
    run_scope_counts = Counter(query.run_scope for query in queries)
    pattern_counts = Counter(query.query_pattern for query in queries)
    cell_counts = Counter(query.matrix_cell_id or matrix_cell_id(query.journey_stage, query.query_pattern) for query in queries)
    metric_scope_counts = Counter(query.metric_scope for query in queries)
    core_weight_sum = round(sum(query.metric_weight for query in queries if query.metric_scope == "core_trend"), 6)
    if not pattern_counts:
        errors.append("Query patterns are missing.")
        checks.append(QueryQualityCheck(name="query_patterns", status="fail"))
    else:
        checks.append(QueryQualityCheck(name="query_patterns", status="pass"))

    invalid_metric_scopes = sorted({query.metric_scope for query in queries if query.metric_scope not in METRIC_SCOPES})
    invalid_cells = sorted(cell for cell in cell_counts if cell not in CELL_POLICIES)
    if invalid_metric_scopes or invalid_cells:
        detail = ", ".join([*invalid_metric_scopes, *invalid_cells])
        errors.append(f"Invalid matrix policy fields: {detail}")
        checks.append(QueryQualityCheck(name="matrix_policy", status="fail"))
    elif abs(core_weight_sum - 1.0) > 0.001 and any(query.metric_scope == "core_trend" for query in queries):
        errors.append(f"Core Trend metric_weight must sum to 1.0, got {core_weight_sum}.")
        checks.append(QueryQualityCheck(name="matrix_policy", status="fail"))
    else:
        checks.append(QueryQualityCheck(name="matrix_policy", status="pass"))

    competitors = [
        str(item.get("name", "")).strip()
        for item in brand_config.get("competitors", [])
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    ]
    if competitors and not any(query.related_competitors for query in queries):
        warnings.append("Competitors exist but no query carries related_competitors.")
        checks.append(QueryQualityCheck(name="competitor_coverage", status="warn"))
    else:
        checks.append(QueryQualityCheck(name="competitor_coverage", status="pass"))

    status = "fail" if errors else "warn" if warnings else "pass"
    return QueryQualityReport(
        status=status,
        checks=checks,
        coverage={
            "expected_topics": expected_topics,
            "covered_topics": sorted(covered_topics),
            "missing_topics": missing_topics,
            "intent_counts": dict(intent_counts),
            "query_layer_counts": dict(layer_counts),
            "run_scope_counts": dict(run_scope_counts),
            "query_pattern_counts": dict(pattern_counts),
            "matrix_cell_counts": dict(cell_counts),
            "metric_scope_counts": dict(metric_scope_counts),
            "core_weight_sum": core_weight_sum,
            "competitors_configured": competitors,
        },
        dedupe={
            "total_queries": len(queries),
            "unique_query_texts": len(text_counts),
            "duplicate_query_texts": duplicate_texts,
            "duplicate_query_ids": duplicate_ids,
        },
        warnings=warnings,
        errors=errors,
    )


def persist_queryset_snapshot(output: QueryMatrixOutput, brand_config_snapshot: dict) -> None:
    now = datetime.now(timezone.utc).isoformat()
    existing = querysets_store.get(output.queryset_id)
    if existing and existing.get("frozen_at"):
        raise RuntimeError(f"QuerySet snapshot is immutable and already frozen: {output.queryset_id}")

    item_table = queryset_items_store.read()
    for query in output.queries:
        item_key = _item_key(output.queryset_id, query.query_id)
        if item_key in item_table:
            raise RuntimeError(f"QuerySet item snapshot is immutable and already exists: {item_key}")

    snapshot = output.model_dump()
    frozen_row = {
        "queryset_id": output.queryset_id,
        "queryset_version": output.queryset_version,
        "brand_config_id": output.brand_config_id,
        "run_id": output.run_id,
        "queryset_strategy": output.queryset_strategy,
        "queryset_source": output.queryset_source,
        "matrix_api_request_id": output.matrix_api_request_id,
        "status": "frozen",
        "quality_status": output.quality_report.status,
        "created_at": now,
        "frozen_at": now,
        "brand_config_snapshot": _json_snapshot(brand_config_snapshot),
        "frozen_snapshot_json": snapshot,
    }
    querysets_store.upsert(output.queryset_id, frozen_row)

    for query in output.queries:
        row = {
            **query.model_dump(),
            "queryset_id": output.queryset_id,
            "created_at": now,
        }
        item_table[_item_key(output.queryset_id, query.query_id)] = row
    queryset_items_store.write(item_table)


def get_queryset_snapshot(queryset_id: str) -> dict | None:
    return querysets_store.get(queryset_id)


def _normalize_query_item(item: Any, index: int) -> dict:
    if isinstance(item, QueryItem):
        item = item.model_dump()
    if not isinstance(item, dict):
        raise RuntimeError(f"QuerySet item #{index} must be a JSON object.")
    source_dimension = item.get("source_dimension_json")
    if not isinstance(source_dimension, dict):
        source_dimension = {
            key: item.get(key)
            for key in ("journey_stage", "matrix_cell_id", "prompt_template_id", "lifecycle_status")
            if item.get(key) is not None
        }
    pattern = normalize_pattern(item)
    stage = normalize_stage(item.get("journey_stage") or source_dimension.get("journey_stage"), pattern)
    cell_id = str(item.get("matrix_cell_id") or source_dimension.get("matrix_cell_id") or matrix_cell_id(stage, pattern))
    policy = policy_for(stage, pattern)
    query_layer = item.get("query_layer") or policy["query_layer"]
    if query_layer not in QUERY_LAYERS:
        query_layer = policy["query_layer"]
    run_scope = item.get("run_scope") or policy["run_scope"]
    if run_scope not in RUN_SCOPES:
        run_scope = policy["run_scope"]
    metric_scope = str(item.get("metric_scope") or policy["metric_scope"])
    if metric_scope not in METRIC_SCOPES:
        metric_scope = policy["metric_scope"]
    return {
        **item,
        "query_id": str(item.get("query_id") or f"q_{index:03d}"),
        "query_text": str(item.get("query_text") or "").strip(),
        "query_layer": query_layer,
        "run_scope": run_scope,
        "journey_stage": stage,
        "metric_scope": metric_scope,
        "topic": str(item.get("topic") or "品牌核心业务"),
        "intent_type": str(item.get("intent_type") or pattern),
        "query_pattern": pattern,
        "related_competitors": [
            str(value).strip()
            for value in (item.get("related_competitors") or [])
            if str(value).strip()
        ],
        "source_dimension_json": {
            **source_dimension,
            "journey_stage": stage,
            "matrix_cell_id": cell_id,
        },
        "matrix_cell_id": cell_id,
        "lifecycle_status": item.get("lifecycle_status") or "active",
    }


def _expected_topics(brand_config: dict) -> list[str]:
    topics = [
        str(item.get("business_line") or item.get("topic_name") or "").strip()
        for item in brand_config.get("topics", [])
        if isinstance(item, dict)
    ]
    topics = [topic for topic in topics if topic]
    return list(dict.fromkeys(topics)) or ["品牌核心业务"]


def _dedupe_key(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _item_key(queryset_id: str, query_id: str) -> str:
    return f"{queryset_id}:{query_id}"


def _json_snapshot(value: dict) -> dict:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))
