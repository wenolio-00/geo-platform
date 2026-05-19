from __future__ import annotations

import os
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from service.rule_matrix import generate_rule_matrix_queryset

QUERY_PATTERNS = {
    "scenario_explore",
    "category_rec",
    "competitive_comp",
    "deep_background",
    "decision_confirm",
    "vendor_choice",
    "internal_justification",
    "purchase_risk",
    "commercial_terms",
}
QUERY_LAYERS = {"core_anchor", "adaptive", "experimental"}
RUN_SCOPES = {"production", "bridge", "shadow"}


class QuerySetMatrixClient:
    def __init__(self) -> None:
        self.url = os.getenv("QUERYSET_MATRIX_API_URL", "").strip()
        self.api_key = os.getenv("QUERYSET_MATRIX_API_KEY", "").strip()
        self.timeout = float(os.getenv("QUERYSET_MATRIX_TIMEOUT_SECONDS", "30"))

    async def generate(self, brand_config: dict, run: dict) -> dict:
        constraints = run.get("generation_constraints") if isinstance(run.get("generation_constraints"), dict) else {}
        try:
            candidate_queries = max(1, int(constraints.get("candidate_queries") or os.getenv("QUERYSET_CANDIDATE_QUERIES", "40")))
        except (TypeError, ValueError):
            candidate_queries = 40
        self_call = _detect_self_call(self.url)
        if not self.url or self_call:
            if not _allow_local_fallback():
                reason = "QUERYSET_MATRIX_API_URL is not configured" if not self.url else f"QUERYSET_MATRIX_API_URL points to local service: {self.url}"
                raise RuntimeError(
                    f"{reason}. Set ALLOW_LOCAL_QUERYSET_FALLBACK=true to use the local rule matrix fallback explicitly."
                )
            fallback = generate_rule_matrix_queryset(
                brand_config,
                run.get("queryset_strategy", "rule_matrix_v1"),
                candidate_count=candidate_queries,
                generation_attempt=run.get("queryset_generation_attempt") or 1,
            )
            fallback["matrix_api_request_id"] = fallback.get("matrix_api_request_id") or f"mx_local_{uuid4().hex[:12]}"
            fallback["debug"] = {
                "transport": "local_rule_matrix",
                "fallback_reason": "missing_matrix_api_url" if not self.url else "self_call_matrix_api_url",
                "request_url": self.url or None,
                "request_host": urlparse(self.url).netloc if self.url else None,
                "self_call_detected": self_call,
                "candidate_queries": candidate_queries,
                "queryset_generation_attempt": run.get("queryset_generation_attempt") or 1,
            }
            return fallback

        payload = {
            "brand_config_id": brand_config.get("brand_config_id"),
            "entity_id": brand_config.get("entity_id"),
            "entity_name": brand_config.get("entity_name"),
            "entity_aliases": brand_config.get("entity_aliases", []),
            "industry_segments": brand_config.get("industry_segments", []),
            "topics": brand_config.get("topics", []),
            "competitors": brand_config.get("competitors", []),
            "queryset_strategy": run.get("queryset_strategy", "rule_matrix_v1"),
            "queryset_generation_attempt": run.get("queryset_generation_attempt"),
            "generation_constraints": {
                **constraints,
                "candidate_queries": candidate_queries,
                "min_active_queries": constraints.get("min_active_queries") or os.getenv("MIN_ACTIVE_QUERIES", "30"),
            },
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        normalized = normalize_matrix_queryset(data)
        normalized["debug"] = {
            "transport": "http",
            "request_url": self.url,
            "request_host": urlparse(self.url).netloc,
            "self_call_detected": self_call,
            "candidate_queries": candidate_queries,
            "queryset_generation_attempt": run.get("queryset_generation_attempt") or 1,
        }
        return normalized


def _detect_self_call(url: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "0.0.0.0"}


def _allow_local_fallback() -> bool:
    return os.getenv("ALLOW_LOCAL_QUERYSET_FALLBACK", "").strip().lower() in {"1", "true", "yes", "on"}


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
        "parent_queryset_id": data.get("parent_queryset_id"),
        "matrix_api_request_id": str(matrix_request_id) if matrix_request_id else None,
        "queries": queries,
    }


def _normalize_query(item: object, index: int) -> dict:
    if not isinstance(item, dict):
        raise RuntimeError(f"Matrix QuerySet item #{index} must be a JSON object.")
    query_text = item.get("query_text") or item.get("text") or item.get("prompt")
    if not isinstance(query_text, str) or not query_text.strip():
        raise RuntimeError(f"Matrix QuerySet item #{index} is missing query_text.")

    query_layer = item.get("query_layer") or item.get("layer") or "core_anchor"
    if query_layer not in QUERY_LAYERS:
        query_layer = "core_anchor"
    run_scope = item.get("run_scope") or "production"
    if run_scope not in RUN_SCOPES:
        run_scope = "production"
    query_pattern = item.get("query_pattern") or item.get("scenario") or item.get("scenario_key")
    if query_pattern not in QUERY_PATTERNS:
        query_pattern = _pattern_from_intent(item.get("intent_type"))

    competitors = item.get("related_competitors") or item.get("competitors") or []
    if not isinstance(competitors, list):
        competitors = []

    return {
        "query_id": str(item.get("query_id") or item.get("id") or f"q_{index:03d}"),
        "query_text": query_text.strip(),
        "query_layer": query_layer,
        "run_scope": run_scope,
        "metric_scope": str(item.get("metric_scope") or "core_trend"),
        "metric_weight": item.get("metric_weight"),
        "journey_stage": item.get("journey_stage") or item.get("funnel_stage"),
        "topic": str(item.get("business_line") or item.get("topic") or item.get("topic_name") or "品牌核心业务"),
        "intent_type": str(item.get("intent_type") or query_pattern),
        "query_pattern": query_pattern,
        "related_competitors": [str(value).strip() for value in competitors if str(value).strip()],
        "matrix_cell_id": item.get("matrix_cell_id") or item.get("cell_id"),
        "prompt_template_id": item.get("prompt_template_id") or item.get("template_id"),
        "lifecycle_status": item.get("lifecycle_status") or "active",
        "quality_filter_status": item.get("quality_filter_status"),
        "quality_filter_reasons": item.get("quality_filter_reasons") or [],
    }


def _pattern_from_intent(intent_type: object) -> str:
    intent = str(intent_type or "").lower()
    if "compet" in intent or "comparison" in intent:
        return "competitive_comp"
    if "deep" in intent or "background" in intent:
        return "deep_background"
    if "criteria" in intent or "decision" in intent:
        return "decision_confirm"
    if "vendor" in intent or "category" in intent or "recommend" in intent:
        return "category_rec"
    return "scenario_explore"
