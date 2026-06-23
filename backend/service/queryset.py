from __future__ import annotations

import logging
from uuid import uuid4

from service.context_extractor import ContextExtractor
from service.queryset_matrix_client import QuerySetMatrixClient
from service.queryset_library import normalize_queryset_snapshot
from service.queryset_policy import apply_query_quality_filters, build_query_quality_report

logger = logging.getLogger(__name__)

DEFAULT_CANDIDATE_QUERIES = 40
DEFAULT_MIN_ACTIVE_QUERIES = 30
DEFAULT_MAX_GENERATION_ATTEMPTS = 3
PRODUCTION_MIN_CANDIDATE_QUERIES = 30
PRODUCTION_MIN_ACTIVE_QUERIES = 30
RESET_LOCAL_GOVERNANCE_POLICIES = {"create_new_version"}
QUERYSET_FAILURE_PREVIEW_LIMIT = 40
QUERYSET_GENERATION_MODES = {"matrix_only", "intent_enhanced"}
DEFAULT_QUERYSET_GENERATION_MODE = "intent_enhanced"


class QuerySetGenerationFailed(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        quality_report: dict | None = None,
        attempt_reports: list[dict] | None = None,
        last_queryset_id: str | None = None,
        matrix_api_request_id: str | None = None,
        last_final_result_summary: dict | None = None,
        last_query_candidates_preview: list[dict] | None = None,
        debug_context: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.quality_report = quality_report or {}
        self.attempt_reports = attempt_reports or []
        self.last_queryset_id = last_queryset_id
        self.matrix_api_request_id = matrix_api_request_id
        self.last_final_result_summary = last_final_result_summary or {}
        self.last_query_candidates_preview = last_query_candidates_preview or []
        self.debug_context = debug_context or {}


class QuerySetThresholdConfigurationError(ValueError):
    pass


def resolve_queryset_thresholds(run: dict) -> tuple[int, int]:
    min_active_queries = _int_setting(run, "min_active_queries", "MIN_ACTIVE_QUERIES", DEFAULT_MIN_ACTIVE_QUERIES)
    candidate_queries = _int_setting(
        run,
        "candidate_queries",
        "QUERYSET_CANDIDATE_QUERIES",
        _env_int("MAX_QUERIES_PER_RUN", DEFAULT_CANDIDATE_QUERIES),
    )
    return candidate_queries, min_active_queries


def validate_production_queryset_thresholds(
    *,
    candidate_queries: int,
    min_active_queries: int,
    generation_constraints: dict | None = None,
) -> None:
    constraints = generation_constraints if isinstance(generation_constraints, dict) else {}
    if constraints.get("allow_small_queryset") is True:
        return
    violations = []
    if candidate_queries < PRODUCTION_MIN_CANDIDATE_QUERIES:
        violations.append(f"candidate_queries={candidate_queries}")
    if min_active_queries < PRODUCTION_MIN_ACTIVE_QUERIES:
        violations.append(f"min_active_queries={min_active_queries}")
    if not violations:
        return
    raise QuerySetThresholdConfigurationError(
        "Production diagnostic QuerySet thresholds require "
        f"candidate_queries >= {PRODUCTION_MIN_CANDIDATE_QUERIES} and "
        f"min_active_queries >= {PRODUCTION_MIN_ACTIVE_QUERIES}, unless explicitly setting "
        "generation_constraints.allow_small_queryset=true. "
        f"Received {', '.join(violations)}."
    )


def validate_run_queryset_thresholds(run: dict) -> tuple[int, int]:
    candidate_queries, min_active_queries = resolve_queryset_thresholds(run)
    queryset_generation_mode(run)
    constraints = run.get("generation_constraints") if isinstance(run.get("generation_constraints"), dict) else {}
    validate_production_queryset_thresholds(
        candidate_queries=candidate_queries,
        min_active_queries=min_active_queries,
        generation_constraints=constraints,
    )
    return candidate_queries, min_active_queries


def queryset_generation_mode(run: dict) -> str:
    constraints = run.get("generation_constraints") if isinstance(run.get("generation_constraints"), dict) else {}
    mode = str(
        run.get("queryset_generation_mode")
        or constraints.get("queryset_generation_mode")
        or constraints.get("queryset_mode")
        or DEFAULT_QUERYSET_GENERATION_MODE
    ).strip()
    if mode not in QUERYSET_GENERATION_MODES:
        raise QuerySetThresholdConfigurationError(
            "Unsupported queryset_generation_mode: "
            f"{mode}. Expected one of: {', '.join(sorted(QUERYSET_GENERATION_MODES))}."
        )
    return mode


def _collect_existing_active_texts(brand_config: dict, include_historical: bool = True) -> set[str]:
    if not include_historical:
        return set()
    entity_name = str(brand_config.get("entity_name") or "").strip()
    existing: set[str] = set()
    try:
        from service.storage import querysets_store, runs_store

        for qs in querysets_store.read().values():
            if not isinstance(qs, dict) or not _same_brand_queryset(qs, brand_config, entity_name):
                continue
            for query in qs.get("queries", []):
                if isinstance(query, dict) and query.get("lifecycle_status", "active") == "active":
                    text = str(query.get("query_text") or "").strip()
                    if text:
                        existing.add(text)
        for item in runs_store.read().values():
            if not isinstance(item, dict) or item.get("status") != "completed":
                continue
            qs = item.get("queryset")
            if not isinstance(qs, dict):
                continue
            report_brand_config = (item.get("report_data") or {}).get("brand_config") or {}
            same_brand_config_id = item.get("brand_config_id") == brand_config.get("brand_config_id")
            same_entity_id = report_brand_config.get("entity_id") == brand_config.get("entity_id")
            same_entity_name = report_brand_config.get("entity_name") == entity_name
            if not (same_brand_config_id or same_entity_id or same_entity_name):
                continue
            for query in qs.get("queries", []):
                if isinstance(query, dict) and query.get("lifecycle_status") == "active":
                    text = str(query.get("query_text") or "").strip()
                    if text:
                        existing.add(text)
    except Exception:
        pass
    return existing


def _same_brand_queryset(queryset: dict, brand_config: dict, entity_name: str) -> bool:
    return bool(
        queryset.get("brand_config_id") == brand_config.get("brand_config_id")
        or queryset.get("entity_id") == brand_config.get("entity_id")
        or (entity_name and queryset.get("entity_name") == entity_name)
    )


async def generate_queryset(brand_config: dict, run: dict) -> dict:
    candidate_queries, min_active_queries = validate_run_queryset_thresholds(run)
    generation_mode = queryset_generation_mode(run)
    max_attempts = _int_setting(
        run,
        "max_generation_attempts",
        "MAX_QUERYSET_GENERATION_ATTEMPTS",
        DEFAULT_MAX_GENERATION_ATTEMPTS,
    )

    # 提取/推断 pain_point 和 goal
    entity_name = str(brand_config.get("entity_name") or "").strip()
    topics = brand_config.get("topics", [])
    if topics:
        extractor = ContextExtractor()
        brand_config["topics"] = await _extract_topic_contexts(extractor, topics, entity_name)
        if generation_mode == "intent_enhanced":
            intent_analysis_results = await _extract_intent_analysis_batch(
                extractor,
                brand_config["topics"],
                entity_name,
            )
            for topic in brand_config["topics"]:
                if not isinstance(topic, dict):
                    continue
                topic_name = str(topic.get("topic_name") or topic.get("business_line") or "").strip()
                analysis = intent_analysis_results.get(topic_name)
                if analysis:
                    topic["intent_analysis"] = analysis

    include_historical_duplicates = (run.get("queryset_policy") or "reuse_latest") != "create_new_version"
    existing_active_texts = _collect_existing_active_texts(
        brand_config,
        include_historical=include_historical_duplicates,
    )
    accumulated_active_texts = set(existing_active_texts)
    accumulated_candidates: list[dict] = []
    active_queries: list[dict] = []
    failed_reports: list[dict] = []
    attempt_reports: list[dict] = []
    final_result: dict | None = None

    for attempt in range(1, max_attempts + 1):
        result = await _generate_matrix_queryset(brand_config, run, attempt, candidate_queries)
        final_result = result
        candidates = _sanitize_local_governance_fields(result.get("queries", []), run)
        filtered_candidates, quality_report = apply_query_quality_filters(
            candidates,
            brand_config,
            accumulated_active_texts,
            min_active_queries=min_active_queries,
        )
        quality_report["generation_attempt"] = attempt
        quality_report["max_generation_attempts"] = max_attempts
        quality_report["candidate_target"] = candidate_queries
        quality_report["cumulative_active_count_before_attempt"] = len(active_queries)
        quality_report["queryset_generation_mode"] = generation_mode

        appended = _append_attempt_candidates(accumulated_candidates, filtered_candidates, attempt)
        new_active = [
            dict(query)
            for query in appended
            if isinstance(query, dict) and query.get("lifecycle_status") == "active"
        ]
        active_queries.extend(new_active)
        for query in new_active:
            text = str(query.get("query_text") or "").strip()
            if text:
                accumulated_active_texts.add(text)

        cumulative_report = build_query_quality_report(
            accumulated_candidates,
            min_active_queries=min_active_queries,
        )
        cumulative_report.update(
            {
                "generation_attempt": attempt,
                "max_generation_attempts": max_attempts,
                "candidate_target": candidate_queries,
                "attempt_active_count": quality_report.get("active_count", 0),
                "cumulative_active_count": len(active_queries),
                    "generation_mode": "accumulate_until_min_active",
                    "queryset_generation_mode": generation_mode,
                    "attempt_reports": [*attempt_reports, quality_report],
                }
        )
        attempt_reports.append(quality_report)
        if cumulative_report["status"] == "pass":
            capped_candidates = _cap_active_candidates(accumulated_candidates, candidate_queries)
            capped_active_queries = [
                dict(query)
                for query in capped_candidates
                if isinstance(query, dict) and query.get("lifecycle_status") == "active"
            ]
            capped_report = build_query_quality_report(
                capped_candidates,
                min_active_queries=min_active_queries,
            )
            capped_report.update(
                {
                    "generation_attempt": attempt,
                    "max_generation_attempts": max_attempts,
                    "candidate_target": candidate_queries,
                    "attempt_active_count": quality_report.get("active_count", 0),
                    "cumulative_active_count": len(capped_active_queries),
                    "generation_mode": "accumulate_until_min_active",
                    "queryset_generation_mode": generation_mode,
                    "attempt_reports": [*attempt_reports],
                }
            )
            result["query_candidates"] = capped_candidates
            result["queries"] = capped_active_queries
            result["quality_report"] = capped_report
            result["queryset_generation_mode"] = generation_mode
            result["queryset_variant"] = generation_mode
            result["queryset_comparison_group"] = "queryset_generation_mode"
            result["debug"] = {
                **(result.get("debug") if isinstance(result.get("debug"), dict) else {}),
                "queryset_generation_mode": generation_mode,
            }
            return normalize_queryset_snapshot(result)
        failed_reports.append(quality_report)

    failure_report = _build_failure_quality_report(
        accumulated_candidates,
        attempt_reports,
        min_active_queries=min_active_queries,
        candidate_queries=candidate_queries,
        max_attempts=max_attempts,
        active_queries=active_queries,
    )
    last_queryset_id = final_result.get("queryset_id") if isinstance(final_result, dict) else None
    raise QuerySetGenerationFailed(
        "QuerySet generation failed quality gate: "
        f"active queries stayed below {min_active_queries} after {max_attempts} attempt(s). "
        f"Last cumulative_active_count={len(active_queries)}. "
        f"Last attempt_active_count={failed_reports[-1].get('active_count', 0) if failed_reports else 0}. "
        f"Last queryset_id={last_queryset_id or '<unknown>'}.",
        quality_report=failure_report,
        attempt_reports=list(attempt_reports),
        last_queryset_id=last_queryset_id,
        matrix_api_request_id=_extract_matrix_api_request_id(final_result),
        last_final_result_summary=_summarize_final_result(final_result),
        last_query_candidates_preview=_preview_query_candidates(final_result),
        debug_context={
            "queryset_source": run.get("queryset_source") or "matrix_api_v1",
            "queryset_policy": run.get("queryset_policy") or "reuse_latest",
            "min_active_queries": min_active_queries,
            "candidate_queries": candidate_queries,
            "max_generation_attempts": max_attempts,
            "queryset_generation_mode": generation_mode,
            "existing_active_text_count": len(existing_active_texts),
            "accumulated_candidate_count": len(accumulated_candidates),
            "accumulated_active_count": len(active_queries),
        },
    )


async def _extract_topic_contexts(
    extractor: ContextExtractor,
    topics: list[dict],
    entity_name: str,
) -> list[dict]:
    try:
        return await extractor.extract_all(topics, entity_name)
    except Exception as error:
        logger.warning(
            "queryset_context_extraction_failed_using_fallback",
            extra={"entity_name": entity_name, "error": str(error)},
        )
        return [_topic_with_fallback_context(topic) for topic in topics if isinstance(topic, dict)]


def _topic_with_fallback_context(topic: dict) -> dict:
    topic_name = str(topic.get("topic_name") or topic.get("business_line") or "").strip()
    label = topic_name or "品牌核心业务"
    return {
        **topic,
        "pain_point": str(topic.get("pain_point") or "").strip() or f"{label}效果不稳定",
        "goal": str(topic.get("goal") or "").strip() or f"提升{label}业务效果",
        "context_fallback_used": True,
    }


def _append_attempt_candidates(
    accumulated_candidates: list[dict],
    filtered_candidates: list[dict],
    attempt: int,
) -> list[dict]:
    appended: list[dict] = []
    for candidate in filtered_candidates:
        if not isinstance(candidate, dict):
            continue
        next_index = len(accumulated_candidates) + 1
        query = {
            **candidate,
            "source_query_id": candidate.get("source_query_id") or candidate.get("query_id"),
            "query_id": f"q_{next_index:03d}",
            "generation_attempt": attempt,
        }
        accumulated_candidates.append(query)
        appended.append(query)
    return appended


def _should_reset_local_governance(run: dict) -> bool:
    return (run.get("queryset_policy") or "reuse_latest") in RESET_LOCAL_GOVERNANCE_POLICIES


def _sanitize_local_governance_fields(queries: list[dict], run: dict) -> list[dict]:
    sanitized: list[dict] = []
    for query in queries:
        if not isinstance(query, dict):
            continue
        candidate = dict(query)
        if _should_reset_local_governance(run):
            candidate.pop("lifecycle_status", None)
            candidate.pop("quality_filter_status", None)
            candidate.pop("quality_filter_reasons", None)
        sanitized.append(candidate)
    return sanitized


def _build_failure_quality_report(
    accumulated_candidates: list[dict],
    attempt_reports: list[dict],
    *,
    min_active_queries: int,
    candidate_queries: int,
    max_attempts: int,
    active_queries: list[dict],
) -> dict:
    failure_report = build_query_quality_report(
        accumulated_candidates,
        min_active_queries=min_active_queries,
    )
    failure_report.update(
        {
            "generation_attempt": len(attempt_reports),
            "max_generation_attempts": max_attempts,
            "candidate_target": candidate_queries,
            "attempt_active_count": attempt_reports[-1].get("active_count", 0) if attempt_reports else 0,
            "cumulative_active_count": len(active_queries),
            "generation_mode": "accumulate_until_min_active",
            "attempt_reports": list(attempt_reports),
        }
    )
    return failure_report


def _extract_matrix_api_request_id(final_result: dict | None) -> str | None:
    if not isinstance(final_result, dict):
        return None
    value = final_result.get("matrix_api_request_id")
    return str(value) if value else None


def _summarize_final_result(final_result: dict | None) -> dict:
    if not isinstance(final_result, dict):
        return {}
    queries = final_result.get("queries") if isinstance(final_result.get("queries"), list) else []
    preview = []
    for query in queries[:5]:
        if not isinstance(query, dict):
            continue
        preview.append(
            {
                "query_id": query.get("query_id"),
                "query_text": query.get("query_text"),
                "lifecycle_status": query.get("lifecycle_status"),
                "quality_filter_status": query.get("quality_filter_status"),
                "quality_filter_reasons": list(query.get("quality_filter_reasons") or []),
            }
        )
    return {
        "queryset_id": final_result.get("queryset_id"),
        "queryset_version": final_result.get("queryset_version"),
        "parent_queryset_id": final_result.get("parent_queryset_id"),
        "matrix_api_request_id": _extract_matrix_api_request_id(final_result),
        "query_count": len(queries),
        "preview": preview,
    }


def _preview_query_candidates(final_result: dict | None) -> list[dict]:
    if not isinstance(final_result, dict):
        return []
    preview: list[dict] = []
    for query in final_result.get("queries", [])[:QUERYSET_FAILURE_PREVIEW_LIMIT]:
        if not isinstance(query, dict):
            continue
        preview.append(
            {
                "query_id": query.get("query_id"),
                "source_query_id": query.get("source_query_id"),
                "query_text": query.get("query_text"),
                "lifecycle_status": query.get("lifecycle_status"),
                "quality_filter_status": query.get("quality_filter_status"),
                "quality_filter_reasons": list(query.get("quality_filter_reasons") or []),
                "generation_attempt": query.get("generation_attempt"),
            }
        )
    return preview


def _cap_active_candidates(candidates: list[dict], candidate_target: int) -> list[dict]:
    capped: list[dict] = []
    active_count = 0
    for candidate in candidates:
        query = dict(candidate)
        if query.get("lifecycle_status") == "active":
            active_count += 1
            if active_count > candidate_target:
                reasons = list(query.get("quality_filter_reasons") or [])
                reasons.append(
                    {
                        "rule_id": "TARGET-CAP",
                        "reason": f"active query exceeds candidate target {candidate_target}",
                    }
                )
                query["lifecycle_status"] = "archived"
                query["quality_filter_status"] = "archived"
                query["quality_filter_reasons"] = reasons
        capped.append(query)
    return capped


async def _generate_matrix_queryset(brand_config: dict, run: dict, attempt: int, candidate_queries: int) -> dict:
    source = run.get("queryset_source") or "matrix_api_v1"
    if source != "matrix_api_v1":
        raise RuntimeError(f"Unsupported queryset_source: {source}")
    attempt_run = {
        **run,
        "queryset_generation_attempt": attempt,
        "queryset_generation_mode": queryset_generation_mode(run),
        "generation_constraints": {
            **(run.get("generation_constraints") or {}),
            "candidate_queries": candidate_queries,
            "queryset_generation_mode": queryset_generation_mode(run),
        },
    }
    result = await QuerySetMatrixClient().generate(brand_config, attempt_run)
    mode = queryset_generation_mode(run)
    result = {
        **result,
        "queryset_generation_mode": mode,
        "queryset_variant": mode,
        "queryset_comparison_group": "queryset_generation_mode",
        "debug": {
            **(result.get("debug") if isinstance(result.get("debug"), dict) else {}),
            "queryset_generation_mode": mode,
            "intent_analysis_injected": False,
            "intent_query_count": 0,
        },
    }
    if mode == "matrix_only":
        return result
    intent_queries = _build_intent_queries_from_topics(brand_config.get("topics", []))
    if not intent_queries:
        return result

    matrix_queries = result.get("queries") if isinstance(result.get("queries"), list) else []
    debug = result.get("debug") if isinstance(result.get("debug"), dict) else {}
    return {
        **result,
        "queries": [*intent_queries, *matrix_queries],
        "debug": {
            **debug,
            "intent_query_count": len(intent_queries),
            "intent_analysis_injected": True,
        },
    }


async def _extract_intent_analysis_batch(
    extractor: ContextExtractor,
    topics: list[dict],
    entity_name: str,
) -> dict[str, dict | None]:
    results: dict[str, dict | None] = {}
    if not extractor.is_available("intent_analysis"):
        logger.info("queryset_intent_analysis_skipped", extra={"reason": "llm_unavailable"})
        return results

    for topic in topics:
        if not isinstance(topic, dict):
            continue
        topic_name = str(topic.get("topic_name") or topic.get("business_line") or "").strip()
        if not topic_name:
            continue
        try:
            analysis = await extractor.extract_with_questions(
                topic_name=topic_name,
                business_line=str(topic.get("business_line") or "").strip() or None,
                entity_name=entity_name,
                pain_point=str(topic.get("pain_point") or "").strip() or None,
                goal=str(topic.get("goal") or "").strip() or None,
            )
            results[topic_name] = analysis
            logger.info(
                "queryset_intent_analysis_extracted",
                extra={
                    "topic_name": topic_name,
                    "pain_point_count": len(analysis.get("pain_points") or []),
                    "ai_question_count": sum(
                        len(point.get("ai_questions") or [])
                        for point in analysis.get("pain_points", [])
                        if isinstance(point, dict)
                    ),
                },
            )
        except Exception as error:
            logger.warning(
                "queryset_intent_analysis_failed",
                extra={"topic_name": topic_name, "error": str(error)},
            )
            results[topic_name] = None
    return results


def _build_intent_queries_from_topics(topics: list[dict]) -> list[dict]:
    queries: list[dict] = []
    seen_texts: set[str] = set()
    for topic in topics:
        if not isinstance(topic, dict):
            continue
        analysis = topic.get("intent_analysis")
        if not isinstance(analysis, dict):
            continue
        audience_profile = str(analysis.get("audience_profile") or "").strip()
        pain_points = analysis.get("pain_points")
        if not isinstance(pain_points, list):
            continue
        for pain_point in pain_points:
            if not isinstance(pain_point, dict):
                continue
            questions = pain_point.get("ai_questions")
            if not isinstance(questions, list):
                continue
            for question in questions:
                query = _intent_query_from_question(topic, pain_point, question, audience_profile)
                if not query:
                    continue
                text = query["query_text"]
                if text in seen_texts:
                    continue
                seen_texts.add(text)
                queries.append(query)
    return queries


def _intent_query_from_question(
    topic: dict,
    pain_point: dict,
    question: object,
    audience_profile: str,
) -> dict | None:
    if isinstance(question, str):
        query_text = question.strip()
        intent_type = "scenario_diagnosis"
    elif isinstance(question, dict):
        query_text = str(question.get("question") or "").strip()
        intent_type = str(question.get("intent_type") or "scenario_diagnosis").strip()
    else:
        return None
    if not query_text:
        return None

    query_pattern = _query_pattern_for_intent(intent_type)
    journey_stage = _journey_stage_for_intent(intent_type)
    topic_name = str(topic.get("topic_name") or topic.get("business_line") or "").strip()
    return {
        "query_id": f"intent_{uuid4().hex[:8]}",
        "query_text": query_text,
        "query_layer": "adaptive",
        "run_scope": "production",
        "metric_scope": "intent_driven",
        "metric_weight": None,
        "journey_stage": journey_stage,
        "topic": topic_name or "品牌核心业务",
        "intent_type": intent_type or "scenario_diagnosis",
        "query_pattern": query_pattern,
        "matrix_cell_id": f"{journey_stage}:{query_pattern}",
        "prompt_template_id": "intent_analysis_seed",
        "lifecycle_status": "active",
        "quality_filter_status": None,
        "quality_filter_reasons": [],
        "source": "intent_analysis",
        "pain_point": str(pain_point.get("pain_point") or "").strip() or None,
        "severity": pain_point.get("severity"),
        "audience_profile": audience_profile or None,
    }


def _query_pattern_for_intent(intent_type: str) -> str:
    intent = intent_type.lower()
    if "compet" in intent or "comparison" in intent or "gap" in intent:
        return "competitive_comp"
    if intent in {"vendor_choice", "goal_vendor_choice"}:
        return "vendor_choice"
    if "internal_justification" in intent:
        return "internal_justification"
    if "purchase_risk" in intent:
        return "purchase_risk"
    if "commercial_terms" in intent:
        return "commercial_terms"
    if "vendor" in intent or "category" in intent or "recommendation" in intent or "solution" in intent:
        return "category_rec"
    return "scenario_explore"


def _journey_stage_for_intent(intent_type: str) -> str:
    intent = intent_type.lower()
    if any(marker in intent for marker in ("choice", "justification", "purchase", "commercial", "decision")):
        return "purchase_decision"
    if any(marker in intent for marker in ("competitive", "capability", "technical", "data_", "solution")):
        return "solution_evaluation"
    return "problem_discovery"


def _int_setting(run: dict, key: str, env_name: str, default: int) -> int:
    constraints = run.get("generation_constraints") if isinstance(run.get("generation_constraints"), dict) else {}
    value = run.get(key) or constraints.get(key)
    if value is None:
        import os

        value = os.getenv(env_name)
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def _env_int(env_name: str, default: int) -> int:
    import os

    try:
        return max(1, int(os.getenv(env_name) or default))
    except (TypeError, ValueError):
        return default
