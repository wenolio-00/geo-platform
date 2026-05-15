from __future__ import annotations

from collections import Counter
from typing import Any


DISCOVERY = "problem_discovery"
EVALUATION = "solution_evaluation"
DECISION = "purchase_decision"

JOURNEY_STAGES = {DISCOVERY, EVALUATION, DECISION}

QUERY_PATTERNS = {
    "scenario_explore",
    "category_rec",
    "competitive_comp",
    "deep_background",
    "vendor_choice",
    "internal_justification",
    "purchase_risk",
    "commercial_terms",
}

LEGACY_QUERY_PATTERNS = {"decision_confirm"}

METRIC_SCOPES = {"core_trend", "supporting_trend", "exploratory_coverage"}
QUERY_LAYERS = {"core_anchor", "adaptive", "experimental"}
RUN_SCOPES = {"production", "bridge", "shadow"}

CELL_POLICIES = {
    f"{DISCOVERY}:scenario_explore": {
        "matrix_weight": 0.05,
        "metric_scope": "exploratory_coverage",
        "query_layer": "experimental",
        "run_scope": "production",
    },
    f"{DISCOVERY}:category_rec": {
        "matrix_weight": 0.15,
        "metric_scope": "core_trend",
        "query_layer": "core_anchor",
        "run_scope": "production",
    },
    f"{EVALUATION}:scenario_explore": {
        "matrix_weight": 0.10,
        "metric_scope": "supporting_trend",
        "query_layer": "adaptive",
        "run_scope": "production",
    },
    f"{EVALUATION}:category_rec": {
        "matrix_weight": 0.15,
        "metric_scope": "core_trend",
        "query_layer": "core_anchor",
        "run_scope": "production",
    },
    f"{EVALUATION}:deep_background": {
        "matrix_weight": 0.05,
        "metric_scope": "exploratory_coverage",
        "query_layer": "experimental",
        "run_scope": "production",
    },
    f"{EVALUATION}:competitive_comp": {
        "matrix_weight": 0.15,
        "metric_scope": "core_trend",
        "query_layer": "core_anchor",
        "run_scope": "production",
    },
    f"{DECISION}:vendor_choice": {
        "matrix_weight": 0.10,
        "metric_scope": "core_trend",
        "query_layer": "core_anchor",
        "run_scope": "production",
    },
    f"{DECISION}:internal_justification": {
        "matrix_weight": 0.05,
        "metric_scope": "core_trend",
        "query_layer": "core_anchor",
        "run_scope": "production",
    },
    f"{DECISION}:purchase_risk": {
        "matrix_weight": 0.05,
        "metric_scope": "supporting_trend",
        "query_layer": "adaptive",
        "run_scope": "production",
    },
    f"{DECISION}:commercial_terms": {
        "matrix_weight": 0.05,
        "metric_scope": "exploratory_coverage",
        "query_layer": "experimental",
        "run_scope": "shadow",
    },
    f"{DECISION}:competitive_comp": {
        "matrix_weight": 0.15,
        "metric_scope": "core_trend",
        "query_layer": "core_anchor",
        "run_scope": "production",
    },
}

CORE_MATRIX_WEIGHT_SUM = sum(
    policy["matrix_weight"]
    for policy in CELL_POLICIES.values()
    if policy["metric_scope"] == "core_trend"
)


def matrix_cell_id(stage: str, pattern: str) -> str:
    return f"{stage}:{pattern}"


def policy_for(stage: str, pattern: str) -> dict[str, Any]:
    return CELL_POLICIES.get(matrix_cell_id(stage, pattern), _fallback_policy(stage, pattern))


def normalize_stage(value: object, pattern: str | None = None) -> str:
    stage = str(value or "").strip()
    if stage in JOURNEY_STAGES:
        return stage
    if pattern in {"vendor_choice", "internal_justification", "purchase_risk", "commercial_terms"}:
        return DECISION
    if pattern in {"competitive_comp", "deep_background"}:
        return EVALUATION
    return DISCOVERY


def normalize_pattern(item: dict[str, Any]) -> str:
    pattern = str(item.get("query_pattern") or item.get("scenario") or item.get("scenario_key") or "").strip()
    if pattern in QUERY_PATTERNS:
        return pattern
    if pattern in LEGACY_QUERY_PATTERNS:
        return legacy_decision_pattern(item)
    inferred = _pattern_from_intent(item.get("intent_type"))
    if inferred in QUERY_PATTERNS:
        return inferred
    return "scenario_explore"


def legacy_decision_pattern(item: dict[str, Any]) -> str:
    text = " ".join(
        str(item.get(key) or "")
        for key in ("query_text", "text", "prompt", "intent_type", "context")
    ).lower()
    if any(term in text for term in ("sla", "合同", "违约", "收费", "费用", "定价", "价格", "成本")):
        return "commercial_terms"
    if any(term in text for term in ("迁移", "风险", "历史", "平移", "实施", "上线")):
        return "purchase_risk"
    if any(term in text for term in ("cfo", "汇报", "说服", "解释", "为什么不用", "内部")):
        return "internal_justification"
    return "vendor_choice"


def assign_metric_weights(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cell_counts = Counter(
        str(item.get("matrix_cell_id") or matrix_cell_id(item["journey_stage"], item["query_pattern"]))
        for item in items
    )
    present_core_weight_sum = sum(
        float(CELL_POLICIES.get(cell_id, _fallback_policy("", ""))["matrix_weight"])
        for cell_id in cell_counts
        if CELL_POLICIES.get(cell_id, _fallback_policy("", ""))["metric_scope"] == "core_trend"
    )
    weighted = []
    for item in items:
        cell_id = str(item.get("matrix_cell_id") or matrix_cell_id(item["journey_stage"], item["query_pattern"]))
        policy = CELL_POLICIES.get(cell_id, _fallback_policy(item["journey_stage"], item["query_pattern"]))
        matrix_weight = float(policy["matrix_weight"])
        if policy["metric_scope"] == "core_trend" and present_core_weight_sum:
            metric_weight = matrix_weight / present_core_weight_sum / max(1, cell_counts[cell_id])
        else:
            metric_weight = 0.0
        source_dimension = item.get("source_dimension_json")
        if not isinstance(source_dimension, dict):
            source_dimension = {}
        weighted.append(
            {
                **item,
                "metric_weight": round(metric_weight, 8),
                "source_dimension_json": {
                    **source_dimension,
                    "matrix_weight": matrix_weight,
                },
            }
        )
    return weighted


def _pattern_from_intent(intent_type: object) -> str:
    intent = str(intent_type or "").lower()
    if "compet" in intent or "comparison" in intent or "对比" in intent:
        return "competitive_comp"
    if "deep" in intent or "background" in intent or "背景" in intent:
        return "deep_background"
    if "justify" in intent or "internal" in intent or "汇报" in intent:
        return "internal_justification"
    if "risk" in intent or "迁移" in intent:
        return "purchase_risk"
    if "commercial" in intent or "terms" in intent or "合同" in intent:
        return "commercial_terms"
    if "vendor" in intent or "choice" in intent or "decision" in intent:
        return "vendor_choice"
    if "category" in intent or "recommend" in intent or "supplier" in intent:
        return "category_rec"
    return "scenario_explore"


def _fallback_policy(stage: str, pattern: str) -> dict[str, Any]:
    if pattern in {"category_rec", "competitive_comp", "vendor_choice"}:
        return {
            "matrix_weight": 0.0,
            "metric_scope": "core_trend",
            "query_layer": "core_anchor",
            "run_scope": "production",
        }
    if stage == DECISION:
        return {
            "matrix_weight": 0.0,
            "metric_scope": "supporting_trend",
            "query_layer": "adaptive",
            "run_scope": "production",
        }
    return {
        "matrix_weight": 0.0,
        "metric_scope": "exploratory_coverage",
        "query_layer": "experimental",
        "run_scope": "production",
    }
