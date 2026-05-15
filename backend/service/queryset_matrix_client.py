from __future__ import annotations

import os
from uuid import uuid4

import httpx

from service.queryset_policy import (
    QUERY_LAYERS,
    RUN_SCOPES,
    matrix_cell_id,
    normalize_pattern,
    normalize_stage,
    policy_for,
)
from service.rule_matrix import generate_rule_matrix_queryset


class QuerySetMatrixClient:
    def __init__(self) -> None:
        self.url = os.getenv("QUERYSET_MATRIX_API_URL", "").strip()
        self.api_key = os.getenv("QUERYSET_MATRIX_API_KEY", "").strip()
        self.timeout = float(os.getenv("QUERYSET_MATRIX_TIMEOUT_SECONDS", "30"))

    async def generate(self, brand_config: dict, run: dict) -> dict:
        if not self.url:
            return generate_rule_matrix_queryset(
                brand_config,
                run.get("queryset_strategy", "rule_matrix_v1"),
            )

        payload = {
            "brand_config_id": brand_config.get("brand_config_id"),
            "entity_id": brand_config.get("entity_id"),
            "entity_name": brand_config.get("entity_name"),
            "entity_aliases": brand_config.get("entity_aliases", []),
            "industry_segments": brand_config.get("industry_segments", []),
            "topics": brand_config.get("topics", []),
            "competitors": brand_config.get("competitors", []),
            "queryset_strategy": run.get("queryset_strategy", "rule_matrix_v1"),
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        return normalize_matrix_queryset(data)


def normalize_matrix_queryset(data: object) -> dict:
    if not isinstance(data, dict):
        raise RuntimeError("Matrix QuerySet API response must be a JSON object.")

    raw_queries = data.get("queries") or data.get("queryset") or data.get("items")
    if not isinstance(raw_queries, list) or not raw_queries:
        raise RuntimeError("Matrix QuerySet API returned an empty QuerySet.")

    queries = [_normalize_query(item, index) for index, item in enumerate(raw_queries, start=1)]
    matrix_request_id = data.get("matrix_api_request_id") or data.get("request_id") or data.get("trace_id")
    return {
        "queryset_id": str(data.get("queryset_id") or f"qs_{uuid4().hex[:12]}"),
        "queryset_version": str(data.get("queryset_version") or data.get("version") or "rule_matrix_v1"),
        "matrix_api_request_id": str(matrix_request_id) if matrix_request_id else None,
        "queries": queries,
    }


def _normalize_query(item: object, index: int) -> dict:
    if not isinstance(item, dict):
        raise RuntimeError(f"Matrix QuerySet item #{index} must be a JSON object.")
    query_text = item.get("query_text") or item.get("text") or item.get("prompt")
    if not isinstance(query_text, str) or not query_text.strip():
        raise RuntimeError(f"Matrix QuerySet item #{index} is missing query_text.")

    query_pattern = normalize_pattern(item)
    stage = normalize_stage(item.get("journey_stage"), query_pattern)
    cell_id = str(item.get("matrix_cell_id") or item.get("cell_id") or matrix_cell_id(stage, query_pattern))
    policy = policy_for(stage, query_pattern)

    query_layer = item.get("query_layer") or item.get("layer") or policy["query_layer"]
    if query_layer not in QUERY_LAYERS:
        query_layer = policy["query_layer"]
    run_scope = item.get("run_scope") or policy["run_scope"]
    if run_scope not in RUN_SCOPES:
        run_scope = policy["run_scope"]

    competitors = item.get("related_competitors") or item.get("competitors") or []
    if not isinstance(competitors, list):
        competitors = []

    return {
        "query_id": str(item.get("query_id") or item.get("id") or f"q_{index:03d}"),
        "query_text": query_text.strip(),
        "query_layer": query_layer,
        "run_scope": run_scope,
        "journey_stage": stage,
        "metric_scope": str(item.get("metric_scope") or policy["metric_scope"]),
        "topic": str(item.get("business_line") or item.get("topic") or item.get("topic_name") or "品牌核心业务"),
        "intent_type": str(item.get("intent_type") or query_pattern),
        "query_pattern": query_pattern,
        "related_competitors": [str(value).strip() for value in competitors if str(value).strip()],
        "matrix_cell_id": cell_id,
        "prompt_template_id": item.get("prompt_template_id") or item.get("template_id"),
        "lifecycle_status": item.get("lifecycle_status") or "active",
        "source_dimension_json": {
            **(item.get("source_dimension_json") if isinstance(item.get("source_dimension_json"), dict) else {}),
            "journey_stage": stage,
            "matrix_cell_id": cell_id,
        },
    }
