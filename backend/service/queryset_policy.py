from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Iterable

INDUSTRY_FORBIDDEN_WORDS = {"博彩", "赌博", "洗钱", "高利贷", "套路贷"}
AD_PHRASE_MARKERS = {"免费", "最好", "第一", "行业首选"}
FORMAL_WRITING_MARKERS = {"兹", "贵司", "敬请", "核心差异", "矩阵", "综合评估"}
STRONG_EMOTION_MARKERS = {"啊啊啊", "救救", "崩溃了", "坑死", "垃圾"}
QF_RULE_IDS = ["QF-01", "QF-02", "QF-03", "QF-04", "QF-05", "QF-06"]

TONE_BY_CELL = {
    ("problem_discovery", "scenario_explore"): "oral_casual",
    ("problem_discovery", "category_rec"): "oral_casual",
    ("solution_evaluation", "scenario_explore"): "oral_casual",
    ("solution_evaluation", "category_rec"): "neutral",
    ("solution_evaluation", "competitive_comp"): "neutral",
    ("solution_evaluation", "deep_background"): "formal",
    ("purchase_decision", "vendor_choice"): "formal",
    ("purchase_decision", "internal_justification"): "formal",
    ("purchase_decision", "purchase_risk"): "formal",
    ("purchase_decision", "commercial_terms"): "formal",
    ("purchase_decision", "competitive_comp"): "formal",
    ("purchase_decision", "decision_confirm"): "formal",
}


def get_tone(journey_stage: object, query_pattern: object) -> str:
    return TONE_BY_CELL.get((str(journey_stage or ""), str(query_pattern or "")), "neutral")


def apply_query_quality_filters(
    queries: list[dict],
    brand_config: dict,
    existing_active_texts: Iterable[str] | None = None,
    min_active_queries: int = 1,
) -> tuple[list[dict], dict]:
    existing_texts = {str(text).strip() for text in existing_active_texts or [] if str(text).strip()}
    seen_texts: set[str] = set()
    filtered_queries: list[dict] = []

    for query in queries:
        filtered = deepcopy(query)
        text = str(filtered.get("query_text") or "").strip()
        reasons = list(filtered.get("quality_filter_reasons") or [])

        _apply_text_rules(text, filtered, reasons)
        if text in seen_texts:
            reasons.append(
                {
                    "rule_id": "QF-06",
                    "reason": "duplicate active query text in current generated batch",
                    "matched_terms": [text],
                }
            )
        if text in existing_texts:
            reasons.append(
                {
                    "rule_id": "QF-06",
                    "reason": "duplicate active query text under the same entity_id",
                    "matched_terms": [text],
                }
            )
        seen_texts.add(text)

        _finalize_status(filtered, reasons)
        filtered_queries.append(filtered)

    return filtered_queries, build_query_quality_report(filtered_queries, min_active_queries=min_active_queries)


def build_query_quality_report(queries: list[dict], min_active_queries: int = 1) -> dict:
    qf_counts = Counter(
        reason.get("rule_id")
        for query in queries
        for reason in query.get("quality_filter_reasons", [])
        if isinstance(reason, dict) and reason.get("rule_id")
    )
    active_count = sum(1 for query in queries if query.get("lifecycle_status") == "active")
    archived_count = sum(1 for query in queries if query.get("lifecycle_status") == "archived")
    rejected_count = sum(1 for query in queries if query.get("lifecycle_status") == "rejected")
    errors = []
    if active_count < min_active_queries:
        errors.append(
            {
                "name": "active_queries",
                "message": f"active QuerySet candidates must be at least {min_active_queries}",
                "minimum": min_active_queries,
                "actual": active_count,
            }
        )

    return {
        "status": "failed" if errors else "pass",
        "total_candidates": len(queries),
        "active_count": active_count,
        "archived_count": archived_count,
        "rejected_count": rejected_count,
        "min_active_queries": min_active_queries,
        "qf_counts": {rule_id: qf_counts.get(rule_id, 0) for rule_id in QF_RULE_IDS},
        "checks": [
            {"name": "qf_filters", "status": "failed" if errors else "pass"},
        ],
        "warnings": [],
        "errors": errors,
    }


def _apply_text_rules(text: str, query: dict, reasons: list[dict]) -> None:
    if len(text) < 8 or len(text) > 80:
        reasons.append(
            {
                "rule_id": "QF-01",
                "reason": "query_text length must be between 8 and 80 characters",
                "matched_terms": [str(len(text))],
            }
        )

    forbidden_words = _matched_terms(text, INDUSTRY_FORBIDDEN_WORDS)
    if forbidden_words:
        reasons.append(
            {
                "rule_id": "QF-02",
                "reason": "hits industry forbidden-word list",
                "matched_terms": forbidden_words,
            }
        )

    ad_markers = _matched_terms(text, AD_PHRASE_MARKERS)
    if ad_markers:
        reasons.append(
            {
                "rule_id": "QF-03",
                "reason": "contains advertising phrase marker",
                "matched_terms": ad_markers,
            }
        )

    tone = get_tone(query.get("journey_stage"), query.get("query_pattern"))
    formal_markers = _matched_terms(text, FORMAL_WRITING_MARKERS)
    if tone == "oral_casual" and formal_markers:
        reasons.append(
            {
                "rule_id": "QF-04",
                "reason": "oral_casual matrix cell contains formal-writing marker",
                "matched_terms": formal_markers,
            }
        )

    emotion_markers = _matched_terms(text, STRONG_EMOTION_MARKERS)
    if tone == "formal" and emotion_markers:
        reasons.append(
            {
                "rule_id": "QF-05",
                "reason": "formal matrix cell contains strong-emotion marker",
                "matched_terms": emotion_markers,
            }
        )


def _matched_terms(text: str, markers: Iterable[str]) -> list[str]:
    return [marker for marker in markers if marker and marker in text]


def _finalize_status(query: dict, reasons: list[dict]) -> None:
    if not reasons:
        query["lifecycle_status"] = "active"
        query["quality_filter_status"] = "pass"
        query["quality_filter_reasons"] = []
        return

    rule_ids = {reason.get("rule_id") for reason in reasons if isinstance(reason, dict)}
    if "QF-02" in rule_ids:
        status = "rejected"
    else:
        status = "archived"
    query["lifecycle_status"] = status
    query["quality_filter_status"] = status
    query["quality_filter_reasons"] = reasons
