from __future__ import annotations

import json
import os
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from service.parser import parse_json_answer
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
    "source_discovery",
    "ugc_discovery",
}
QUERY_LAYERS = {"core_anchor", "adaptive", "experimental"}
RUN_SCOPES = {"production", "bridge", "shadow"}


class QuerySetMatrixClient:
    def __init__(self) -> None:
        matrix_url = os.getenv("QUERYSET_MATRIX_API_URL", "").strip()
        self.uses_shared_provider = not bool(matrix_url)
        self.provider = os.getenv("QUERYSET_MATRIX_PROVIDER", "claude").strip() or "claude"
        self.url = matrix_url or os.getenv("CLAUDE_BASE_URL", "").strip()
        self.api_key = _first_env_value("QUERYSET_MATRIX_API_KEY", "CLAUDE_API_KEY")
        self.timeout = float(os.getenv("QUERYSET_MATRIX_TIMEOUT_SECONDS", "30"))
        configured_style = os.getenv("QUERYSET_MATRIX_API_STYLE", "").strip().lower()
        self.api_style = configured_style or ("responses" if self.uses_shared_provider else "")
        self.model = _first_env_value("QUERYSET_MATRIX_MODEL", "CLAUDE_MODEL", default="gpt-5.5")
        self.chat_endpoint = os.getenv(
            "QUERYSET_MATRIX_CHAT_COMPLETIONS_ENDPOINT",
            os.getenv("CLAUDE_CHAT_COMPLETIONS_ENDPOINT", "/chat/completions"),
        ).strip() or "/chat/completions"
        self.responses_endpoint = os.getenv(
            "QUERYSET_MATRIX_RESPONSES_ENDPOINT",
            os.getenv("CLAUDE_RESPONSES_ENDPOINT", "/responses"),
        ).strip() or "/responses"

    async def generate(self, brand_config: dict, run: dict) -> dict:
        constraints = run.get("generation_constraints") if isinstance(run.get("generation_constraints"), dict) else {}
        try:
            candidate_queries = max(1, int(constraints.get("candidate_queries") or os.getenv("QUERYSET_CANDIDATE_QUERIES", "40")))
        except (TypeError, ValueError):
            candidate_queries = 40
        self_call = _detect_self_call(self.url)
        if not self.url or self_call:
            if not _allow_local_fallback():
                reason = (
                    "CLAUDE_BASE_URL is not configured for shared QuerySet matrix generation"
                    if self.uses_shared_provider and not self.url
                    else "QUERYSET_MATRIX_API_URL is not configured"
                    if not self.url
                    else f"QUERYSET_MATRIX_API_URL points to local service: {self.url}"
                )
                raise RuntimeError(
                    f"{reason}. Set ALLOW_LOCAL_QUERYSET_FALLBACK=true to use the local rule matrix fallback explicitly."
                )
            return _local_rule_matrix_fallback(
                brand_config,
                run,
                candidate_queries,
                fallback_reason="missing_matrix_api_url" if not self.url else "self_call_matrix_api_url",
                request_url=self.url or None,
                self_call_detected=self_call,
            )

        try:
            if self._uses_openai_responses():
                return await self._generate_openai_responses(brand_config, run, candidate_queries)

            if self._uses_openai_chat():
                return await self._generate_openai_chat(brand_config, run, candidate_queries)

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
                data = _response_json(response, "Matrix QuerySet API")

            normalized = normalize_matrix_queryset(data)
            normalized["debug"] = {
                "transport": "http",
                "provider": self.provider,
                "request_url": self.url,
                "request_host": urlparse(self.url).netloc,
                "self_call_detected": self_call,
                "candidate_queries": candidate_queries,
                "queryset_generation_attempt": run.get("queryset_generation_attempt") or 1,
            }
            return normalized
        except Exception as error:
            if not _allow_local_fallback():
                raise RuntimeError(f"QuerySet matrix generation failed: {error}") from error
            return _local_rule_matrix_fallback(
                brand_config,
                run,
                candidate_queries,
                fallback_reason="matrix_api_failed",
                request_url=self.url,
                self_call_detected=self_call,
                upstream_error=str(error),
            )

    def _uses_openai_responses(self) -> bool:
        if self.api_style in {"responses", "openai_responses", "responses_api"}:
            return True
        return _url_path(self.url).endswith("/responses")

    def _uses_openai_chat(self) -> bool:
        if self.api_style in {"openai", "chat", "chat_completions", "openai_compatible"}:
            return True
        return _url_path(self.url).endswith("/chat/completions")

    async def _generate_openai_responses(self, brand_config: dict, run: dict, candidate_queries: int) -> dict:
        if not self.api_key:
            raise RuntimeError("CLAUDE_API_KEY is not configured; shared QuerySet matrix generation cannot run.")
        if not self.model:
            raise RuntimeError("CLAUDE_MODEL is not configured; shared QuerySet matrix generation cannot run.")

        url = self.url if _url_path(self.url).endswith("/responses") else _join_url(self.url, self.responses_endpoint)
        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": _matrix_system_prompt()},
                {"role": "user", "content": _matrix_user_prompt(brand_config, run, candidate_queries)},
            ],
            "stream": False,
            "temperature": 0.2,
            "max_output_tokens": int(os.getenv("QUERYSET_MATRIX_MAX_OUTPUT_TOKENS", os.getenv("CLAUDE_MAX_OUTPUT_TOKENS", "4000"))),
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            raw = _response_json(response, "Shared QuerySet matrix Responses API")
        content = _openai_responses_content(raw)
        if not content:
            raise RuntimeError("Shared QuerySet matrix API returned an empty message content.")

        data = parse_json_answer(content, brand_config)
        normalized = normalize_matrix_queryset(data)
        normalized["debug"] = {
            "transport": "openai_compatible_responses",
            "provider": self.provider,
            "request_url": url,
            "request_host": urlparse(url).netloc,
            "self_call_detected": False,
            "candidate_queries": candidate_queries,
            "queryset_generation_attempt": run.get("queryset_generation_attempt") or 1,
            "model": raw.get("model", self.model),
        }
        return normalized

    async def _generate_openai_chat(self, brand_config: dict, run: dict, candidate_queries: int) -> dict:
        if not self.api_key:
            env_name = "CLAUDE_API_KEY" if self.uses_shared_provider else "QUERYSET_MATRIX_API_KEY"
            raise RuntimeError(f"{env_name} is not configured; QuerySet matrix API cannot run.")
        if not self.model:
            raise RuntimeError("QUERYSET_MATRIX_MODEL or CLAUDE_MODEL is not configured; QuerySet matrix API cannot run.")

        url = self.url if _url_path(self.url).endswith("/chat/completions") else _join_url(self.url, self.chat_endpoint)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _matrix_system_prompt()},
                {"role": "user", "content": _matrix_user_prompt(brand_config, run, candidate_queries)},
            ],
            "stream": False,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            raw = _response_json(response, "QuerySet matrix Chat Completions API")
        content = _openai_chat_content(raw)
        if not content:
            raise RuntimeError("QuerySet matrix API returned an empty message content.")

        data = parse_json_answer(content, brand_config)
        normalized = normalize_matrix_queryset(data)
        normalized["debug"] = {
            "transport": "openai_compatible_chat",
            "provider": self.provider,
            "request_url": url,
            "request_host": urlparse(url).netloc,
            "self_call_detected": False,
            "candidate_queries": candidate_queries,
            "queryset_generation_attempt": run.get("queryset_generation_attempt") or 1,
            "model": raw.get("model", self.model),
        }
        return normalized


def _detect_self_call(url: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "0.0.0.0"}


def _first_env_value(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default


def _url_path(url: str) -> str:
    return urlparse(url).path.rstrip("/").lower()


def _join_url(base_url: str, endpoint: str) -> str:
    return f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"


def _openai_chat_content(raw_response: dict) -> str:
    if not isinstance(raw_response, dict):
        return ""
    message = raw_response.get("choices", [{}])[0].get("message", {})
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts).strip()
    return ""


def _openai_responses_content(raw_response: dict) -> str:
    if not isinstance(raw_response, dict):
        return ""
    output_text = raw_response.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()
    parts: list[str] = []
    for item in raw_response.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []) or []:
            if not isinstance(content, dict):
                continue
            text = content.get("text") or content.get("output_text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()


def _matrix_system_prompt() -> str:
    return (
        "You are a GEO QuerySet Matrix generator. Return only one valid JSON object. "
        "The object must contain queryset_id, queryset_version, matrix_api_request_id, and queries. "
        "Each query must include query_id, query_text, query_layer, run_scope, metric_scope, "
        "journey_stage, topic, intent_type, query_pattern, matrix_cell_id, and lifecycle_status."
    )


def _matrix_user_prompt(brand_config: dict, run: dict, candidate_queries: int) -> str:
    brief = {
        "brand_config": brand_config,
        "queryset_strategy": run.get("queryset_strategy", "rule_matrix_v1"),
        "queryset_generation_attempt": run.get("queryset_generation_attempt") or 1,
        "generation_constraints": run.get("generation_constraints") if isinstance(run.get("generation_constraints"), dict) else {},
        "candidate_queries": candidate_queries,
        "allowed_query_patterns": sorted(QUERY_PATTERNS),
        "allowed_query_layers": sorted(QUERY_LAYERS),
        "allowed_run_scopes": sorted(RUN_SCOPES),
        "requirements": [
            "Generate diverse Chinese diagnostic queries for brand visibility inspection.",
            "Use lifecycle_status=active for usable queries.",
            "Set matrix_cell_id as journey_stage:query_pattern.",
            "Avoid duplicate query_text values.",
            "Return exactly candidate_queries items in queries unless impossible and no additional query constraint is set.",
            "If generation_constraints.negative_probe_queries is set, include candidate_queries plus about that many negative-risk queries without naming the target brand.",
        ],
    }
    return json.dumps(brief, ensure_ascii=False, indent=2)


def _allow_local_fallback() -> bool:
    return os.getenv("ALLOW_LOCAL_QUERYSET_FALLBACK", "").strip().lower() in {"1", "true", "yes", "on"}


def _local_rule_matrix_fallback(
    brand_config: dict,
    run: dict,
    candidate_queries: int,
    *,
    fallback_reason: str,
    request_url: str | None,
    self_call_detected: bool,
    upstream_error: str | None = None,
) -> dict:
    fallback = generate_rule_matrix_queryset(
        brand_config,
        run.get("queryset_strategy", "rule_matrix_v1"),
        candidate_count=candidate_queries,
        generation_attempt=run.get("queryset_generation_attempt") or 1,
        negative_probe_count=_negative_probe_count(run),
    )
    fallback["matrix_api_request_id"] = fallback.get("matrix_api_request_id") or f"mx_local_{uuid4().hex[:12]}"
    fallback["debug"] = {
        "transport": "local_rule_matrix",
        "fallback_reason": fallback_reason,
        "request_url": request_url,
        "request_host": urlparse(request_url).netloc if request_url else None,
        "self_call_detected": self_call_detected,
        "candidate_queries": candidate_queries,
        "queryset_generation_attempt": run.get("queryset_generation_attempt") or 1,
    }
    if upstream_error:
        fallback["debug"]["upstream_error"] = upstream_error
    return fallback


def _negative_probe_count(run: dict) -> int:
    constraints = run.get("generation_constraints") if isinstance(run.get("generation_constraints"), dict) else {}
    value = constraints.get("negative_probe_queries")
    if value is None:
        value = constraints.get("additional_negative_queries")
    if value is True:
        return 12
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _response_json(response: httpx.Response, context: str) -> dict:
    try:
        data = response.json()
    except ValueError as error:
        body = response.text.strip()
        detail = "empty response body" if not body else f"non-JSON response body: {body[:300]}"
        content_type = response.headers.get("content-type", "")
        raise RuntimeError(
            f"{context} returned invalid JSON (HTTP {response.status_code}, content-type={content_type or '<missing>'}): {detail}"
        ) from error
    if not isinstance(data, dict):
        raise RuntimeError(f"{context} response must be a JSON object.")
    return data


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

    run_scope = item.get("run_scope") or "production"
    if run_scope not in RUN_SCOPES:
        run_scope = "production"
    query_pattern = item.get("query_pattern") or item.get("scenario") or item.get("scenario_key")
    if query_pattern not in QUERY_PATTERNS:
        query_pattern = _pattern_from_intent(item.get("intent_type"))
    query_layer = item.get("query_layer") or item.get("layer")
    if query_pattern == "source_discovery":
        query_layer = "adaptive"
    elif query_pattern == "ugc_discovery":
        query_layer = "experimental"
    elif query_layer not in QUERY_LAYERS:
        query_layer = "core_anchor"

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
