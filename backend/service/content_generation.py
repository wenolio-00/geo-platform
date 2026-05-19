from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from service.aggregator import _round
from service.dashboard_snapshots import (
    METRIC_DEFINITIONS,
    get_dashboard_contract,
    persist_dashboard_snapshot,
    sync_completed_run_snapshots,
)
from service.inspector import get_run, latest_completed_run
from service.llm_tasks import brief_to_json_text, invoke_llm_task
from service.storage import content_feedback_store, content_versions_store, effect_attribution_store, runs_store


CONTENT_VERSION_SCHEMA_VERSION = "content_version_v1"
FEEDBACK_SCHEMA_VERSION = "content_feedback_v1"
EFFECT_ATTRIBUTION_SCHEMA_VERSION = "effect_attribution_v1"
DEFAULT_USER_ID = "local_user"
FORBIDDEN_META_PHRASES = {
    "建议围绕",
    "正文建议按",
    "建议同步覆盖",
    "可按以下结构",
    "以下为",
    "写作说明",
    "输出要求",
}


def get_content_generation_context(brand_id: str | None = None) -> dict[str, Any] | None:
    contract = _load_dashboard_contract(brand_id=brand_id)
    if not contract:
        return None

    actions = contract.get("optimization_actions") or []
    rules = contract.get("cross_topic_rules") or []
    rule_candidates = _rule_candidates(contract)
    default_action = actions[0] if actions else None
    default_rule = _resolve_rule(contract, None, default_action)

    return {
        "contract_version": contract.get("contract_version"),
        "snapshot_date": contract.get("snapshot_date"),
        "brand": contract.get("main_brand") or {},
        "actions": actions,
        "rules": rules,
        "rule_activation": contract.get("rule_activation"),
        "queryset": _queryset_summary(contract),
        "lineage": _content_lineage(contract),
        "content_versions": _versions_for_brand((contract.get("main_brand") or {}).get("brand_id")),
        "defaults": {
            "action_id": default_action.get("action_id") if default_action else None,
            "rule_id": default_rule.get("rule_id") if default_rule else None,
        },
        "available_rule_count": len(rule_candidates or rules),
    }


def generate_optimized_draft(payload: dict[str, Any]) -> dict[str, Any]:
    brand_id = str(payload.get("brand_id") or "").strip()
    action_id = str(payload.get("action_id") or "").strip()
    rule_id = str(payload.get("rule_id") or "").strip()

    contract = _load_dashboard_contract(brand_id=brand_id)
    if not contract:
        raise LookupError("No completed diagnostic dashboard snapshot is available yet.")

    actions = contract.get("optimization_actions") or []
    action = next((item for item in actions if item.get("action_id") == action_id), None)
    if not action:
        raise ValueError("action_id is not available in the latest content generation context.")

    rule = _resolve_rule(contract, rule_id, action)
    if not rule:
        raise ValueError("rule_id is not available in the latest content generation context.")

    generation_result = _generate_publish_ready_text(contract, action, rule)
    generated_text, generation_source, generation_metadata = _normalize_generation_result(generation_result)

    return _persist_content_version(
        contract=contract,
        action=action,
        rule=rule,
        generated_text=generated_text,
        generation_source=generation_source,
        generation_metadata=generation_metadata,
        parent_content_version_id=None,
    )


def save_content_version_edit(content_version_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    parent = content_versions_store.get(content_version_id)
    if not parent:
        raise LookupError("content_version_id not found.")

    generated_text = str(payload.get("generated_text") or "").strip()
    if not generated_text:
        raise ValueError("generated_text is required.")

    contract = _load_dashboard_contract(brand_id=parent.get("brand_id"))
    if not contract:
        raise LookupError("No completed diagnostic dashboard snapshot is available yet.")

    actions = contract.get("optimization_actions") or []
    action = next((item for item in actions if item.get("action_id") == parent.get("action_id")), None)
    if not action:
        raise ValueError("The parent action is not available in the latest content generation context.")

    rule = _resolve_rule(contract, parent.get("rule_id"), action)
    if not rule:
        raise ValueError("The parent rule is not available in the latest content generation context.")

    return _persist_content_version(
        contract=contract,
        action=action,
        rule=rule,
        generated_text=generated_text,
        generation_source="manual_edit",
        parent_content_version_id=content_version_id,
    )


def record_content_feedback(content_version_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    version = content_versions_store.get(content_version_id)
    if not version:
        raise LookupError("content_version_id not found.")

    signal = str(payload.get("signal") or "").strip()
    if signal not in {"helpful", "not_helpful"}:
        raise ValueError("signal must be helpful or not_helpful.")

    user_id = str(payload.get("user_id") or DEFAULT_USER_ID).strip() or DEFAULT_USER_ID
    feedback_id = f"fb_{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    feedback = {
        "feedback_id": feedback_id,
        "schema_version": FEEDBACK_SCHEMA_VERSION,
        "content_version_id": content_version_id,
        "brand_id": version.get("brand_id"),
        "action_id": version.get("action_id"),
        "rule_id": version.get("rule_id"),
        "signal": signal,
        "rating": 1 if signal == "helpful" else -1,
        "reason": payload.get("reason"),
        "user_id": user_id,
        "created_at": now,
    }
    content_feedback_store.upsert(feedback_id, feedback)

    summary = _feedback_summary(content_version_id)
    version["feedback_summary"] = summary
    version["updated_at"] = now
    content_versions_store.upsert(content_version_id, version)

    attribution = _attribution_for_content_version(content_version_id)
    if attribution:
        attribution["feedback_summary"] = summary
        attribution["updated_at"] = now
        effect_attribution_store.upsert(attribution["attribution_id"], attribution)

    return {"feedback": feedback, "feedback_summary": summary}


def compute_content_effect_attribution(content_version_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    version = content_versions_store.get(content_version_id)
    if not version:
        raise LookupError("content_version_id not found.")

    payload = payload or {}
    attribution = _attribution_for_content_version(content_version_id)
    if not attribution:
        attribution = _new_attribution(version, _load_dashboard_contract(brand_id=version.get("brand_id")))

    comparison_run_id = str(payload.get("comparison_run_id") or "").strip()
    if not comparison_run_id:
        comparison_run_id = _latest_comparison_run_id(attribution.get("baseline_run_id"), version.get("brand_config_id"))

    if not comparison_run_id:
        attribution.update(
            {
                "status": "awaiting_retest",
                "message": "No completed comparison run is available yet.",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        effect_attribution_store.upsert(attribution["attribution_id"], attribution)
        return attribution

    baseline_run = get_run(str(attribution.get("baseline_run_id") or ""))
    comparison_run = get_run(comparison_run_id)
    if not _completed_report(baseline_run) or not _completed_report(comparison_run):
        raise ValueError("baseline_run_id and comparison_run_id must reference completed diagnostic runs.")

    baseline_report = baseline_run["report_data"]
    comparison_report = comparison_run["report_data"]
    attribution.update(
        {
            "comparison_run_id": comparison_run_id,
            "effect_delta": _effect_delta(baseline_report, comparison_report),
            "comparability": _comparability(attribution, baseline_report, comparison_report),
            "status": "computed",
            "message": "effect_delta computed from persisted diagnostic reports.",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    effect_attribution_store.upsert(attribution["attribution_id"], attribution)
    return attribution


def get_content_effect_attribution(content_version_id: str) -> dict[str, Any]:
    attribution = _attribution_for_content_version(content_version_id)
    if attribution:
        return attribution
    version = content_versions_store.get(content_version_id)
    if not version:
        raise LookupError("content_version_id not found.")
    return _new_attribution(version, _load_dashboard_contract(brand_id=version.get("brand_id")))


def _persist_content_version(
    *,
    contract: dict[str, Any],
    action: dict[str, Any],
    rule: dict[str, Any],
    generated_text: str,
    generation_source: str,
    parent_content_version_id: str | None,
    generation_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    brand = contract.get("main_brand") or {}
    content_version_id = f"cv_{uuid4().hex[:12]}"
    version_number = _next_version_number(brand.get("brand_id"), action.get("action_id"), rule.get("rule_id"))
    version = {
        "content_version_id": content_version_id,
        "draft_id": content_version_id,
        "schema_version": CONTENT_VERSION_SCHEMA_VERSION,
        "brand_id": brand.get("brand_id"),
        "brand_config_id": brand.get("brand_config_id") or (contract.get("brand_config") or {}).get("brand_config_id"),
        "entity_id": brand.get("entity_id") or (contract.get("brand_config") or {}).get("entity_id"),
        "action_id": action.get("action_id"),
        "action_name": action.get("action_name"),
        "action_type": action.get("action_type"),
        "rule_id": rule.get("rule_id"),
        "source_rule_id": rule.get("source_rule_id"),
        "rule_version": rule.get("rule_version"),
        "rule_name": rule.get("rule_name"),
        "contract_version": contract.get("contract_version"),
        "baseline_run_id": contract.get("latest_run_id") or ((contract.get("diagnostic_run") or {}).get("run_id")),
        "report_id": (contract.get("report") or {}).get("report_id"),
        "queryset": _queryset_summary(contract),
        "lineage": _content_lineage(contract),
        "generated_text": generated_text,
        "publish_platforms": _publish_platforms(action, rule),
        "target_intents": action.get("related_intent_ids") or [],
        "generation_source": generation_source,
        "generation_metadata": generation_metadata or {},
        "version": version_number,
        "parent_content_version_id": parent_content_version_id,
        "parent_draft_id": parent_content_version_id,
        "status": "draft",
        "created_at": now,
        "updated_at": now,
        "feedback_summary": _empty_feedback_summary(),
    }
    content_versions_store.upsert(content_version_id, version)
    attribution = _new_attribution(version, contract)
    version["effect_attribution"] = attribution
    return version


def _load_dashboard_contract(brand_id: str | None = None) -> dict[str, Any] | None:
    sync_completed_run_snapshots()
    contract = get_dashboard_contract(brand_id=brand_id)
    if contract:
        return contract

    run = latest_completed_run()
    if run and isinstance(run.get("report_data"), dict):
        persist_dashboard_snapshot(run, run["report_data"])
        return get_dashboard_contract(brand_id=brand_id)
    return None


def _rule_candidates(contract: dict[str, Any]) -> list[dict[str, Any]]:
    active_rules = (
        ((contract.get("rule_activation") or {}).get("stores") or {}).get("active_rules_store")
        or []
    )
    candidates = [
        _normalize_active_rule(rule)
        for rule in active_rules
        if isinstance(rule, dict) and rule.get("status") == "active"
    ]
    if candidates:
        return sorted(candidates, key=lambda rule: rule.get("source_type") == "baseline")
    return contract.get("cross_topic_rules") or []


def _normalize_active_rule(rule: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(rule)
    normalized["rule_id"] = rule.get("active_rule_id") or rule.get("rule_id")
    normalized["source_rule_id"] = rule.get("source_rule_id")
    applies_to = rule.get("applies_to") or []
    normalized["applies_to"] = applies_to if applies_to else [rule.get("action_type")]
    return normalized


def _resolve_rule(contract: dict[str, Any], rule_id: str | None, action: dict[str, Any] | None) -> dict[str, Any] | None:
    rules = _rule_candidates(contract)
    if rule_id:
        direct = next(
            (
                rule
                for rule in rules
                if rule.get("rule_id") == rule_id or rule.get("source_rule_id") == rule_id
            ),
            None,
        )
        if direct:
            return direct
    if action:
        action_type = action.get("action_type")
        return next((rule for rule in rules if action_type in (rule.get("applies_to") or [])), None) or (rules[0] if rules else None)
    return rules[0] if rules else None


async def _generate_with_llm(contract: dict[str, Any], action: dict[str, Any], rule: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    brief = _build_generation_brief(contract, action, rule)
    result = await invoke_llm_task(
        task_type="content_generation",
        payload={
            "brand_config": contract.get("brand_config") or {},
            "llm_provider": brief.get("llm_provider"),
            "web_search_enabled": brief.get("web_search_enabled", True),
            "llm_options": {"web_search_mode": brief.get("web_search_mode", "responses_web_search")},
        },
        provider=brief.get("llm_provider"),
        system_prompt=_content_generation_system_prompt(),
        user_prompt=_content_generation_user_prompt(brief),
    )
    content = str(result.get("raw_text") or "").strip()
    if not content:
        raise RuntimeError("claude content_generation returned empty text.")
    return content, {
        "provider": result.get("provider", "claude"),
        "platform": result.get("platform", "claude"),
        "model": result.get("model"),
        "web_search_enabled": result.get("web_search_enabled", True),
        "web_search_mode": result.get("web_search_mode") or "responses_web_search",
    }


def _draft_text(contract: dict[str, Any], action: dict[str, Any], rule: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    try:
        generated, metadata = asyncio.run(_generate_with_llm(contract, action, rule))
        return _sanitize_generated_text(generated), "prompt_driven_backend", metadata
    except Exception as error:
        if not _allow_content_generation_fallback():
            raise RuntimeError(f"claude content_generation failed: {error}") from error
        return _fallback_draft_text(contract, action, rule), "prompt_fallback_backend", {
            "provider": "claude",
            "generation_source": "prompt_fallback_backend",
            "fallback_reason": str(error),
            "llm_error_type": type(error).__name__,
            "web_search_enabled": True,
            "web_search_mode": "responses_web_search",
        }


def _generate_publish_ready_text(contract: dict[str, Any], action: dict[str, Any], rule: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    return _draft_text(contract, action, rule)


def _build_generation_brief(contract: dict[str, Any], action: dict[str, Any], rule: dict[str, Any]) -> dict[str, Any]:
    brand = contract.get("main_brand") or {}
    brand_config = contract.get("brand_config") or {}
    report = contract.get("report") or {}
    queryset = contract.get("queryset") or {}
    lineage = contract.get("lineage") or {}
    global_metrics = report.get("global") or {}

    return {
        "brand": {
            "brand_name": brand.get("brand_name"),
            "short_name": brand.get("short_name"),
            "category": brand.get("category"),
            "entity_name": brand_config.get("entity_name"),
            "entity_aliases": brand_config.get("entity_aliases") or [],
            "industry_segments": brand_config.get("industry_segments") or [],
            "topics": [
                {
                    "topic_name": topic.get("topic_name"),
                    "business_line": topic.get("business_line"),
                    "priority": topic.get("priority"),
                }
                for topic in (brand_config.get("topics") or [])
                if isinstance(topic, dict)
            ],
        },
        "task": {
            "action_id": action.get("action_id"),
            "action_name": action.get("action_name"),
            "action_type": action.get("action_type"),
            "content_type": _content_type(action),
            "output_assets": action.get("output_assets") or [],
            "target_intents": action.get("related_intent_ids") or [],
            "target_sources": action.get("target_sources") or [],
        },
        "rule": {
            "rule_id": rule.get("rule_id"),
            "rule_name": rule.get("rule_name"),
            "template": rule.get("template"),
            "required_elements": rule.get("required_elements") or [],
            "applies_to": rule.get("applies_to") or [],
        },
        "available_facts": {
            "key_metrics": {
                metric_id: global_metrics.get(metric_id)
                for metric_id in (
                    "natural_visibility",
                    "rank",
                    "visibility",
                    "sentiment_score",
                    "ai_recommend_score",
                    "own_citations",
                    "competitor_suppression_rate",
                )
                if global_metrics.get(metric_id) is not None
            },
            "brand_summary": report.get("brand_summary"),
            "topics": report.get("topics") or [],
            "sources": report.get("sources") or [],
            "source_references": report.get("source_references") or [],
            "queryset": {
                "queryset_id": queryset.get("queryset_id") or lineage.get("queryset_id"),
                "queryset_version": queryset.get("queryset_version") or lineage.get("queryset_version"),
                "query_ids": [
                    query.get("query_id")
                    for query in (queryset.get("queries") or [])
                    if isinstance(query, dict) and query.get("query_id")
                ],
            },
        },
        "llm_provider": "claude",
        "web_search_enabled": (contract.get("lineage", {}) or {}).get("web_search_enabled", True),
        "web_search_mode": "responses_web_search",
        "lineage": _content_lineage(contract),
        "output_constraints": {
            "must_be_publish_ready": True,
            "language": "zh-CN",
            "forbidden_patterns": sorted(FORBIDDEN_META_PHRASES),
            "forbidden_content": [
                "未在 available_facts 中出现的数字、排名、客户名称、案例名称",
                "竞品攻击性表述或未证实的 superiority claims",
                "写作说明、提示词痕迹、内部流程描述",
            ],
        },
    }


def _normalize_generation_result(result: object) -> tuple[str, str, dict[str, Any]]:
    if isinstance(result, tuple) and len(result) == 3:
        return str(result[0]), str(result[1]), result[2] if isinstance(result[2], dict) else {}
    if isinstance(result, tuple) and len(result) == 2:
        return str(result[0]), str(result[1]), {}
    raise RuntimeError("content generation result must be a 2- or 3-item tuple.")


def _allow_content_generation_fallback() -> bool:
    return os.getenv("ALLOW_CONTENT_GENERATION_FALLBACK", "").strip().lower() in {"1", "true", "yes", "on"}


def _sanitize_generated_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    filtered = [line for line in lines if line and not _is_forbidden_meta_line(line)]
    content = "\n\n".join(filtered).strip()
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip()


def _is_forbidden_meta_line(line: str) -> bool:
    normalized = re.sub(r"\s+", "", line)
    if not normalized:
        return False
    if normalized.startswith("#"):
        return True
    return any(phrase in normalized for phrase in FORBIDDEN_META_PHRASES)


def _fallback_draft_text(contract: dict[str, Any], action: dict[str, Any], rule: dict[str, Any]) -> str:
    brand = (contract.get("main_brand") or {}).get("short_name") or (contract.get("main_brand") or {}).get("brand_name") or "该品牌"
    action_name = action.get("action_name") or "核心场景"
    business_lines = [
        topic.get("business_line")
        for topic in ((contract.get("brand_config") or {}).get("topics") or [])
        if isinstance(topic, dict) and topic.get("business_line")
    ]
    primary_line = business_lines[0] if business_lines else "核心业务场景"
    required = "、".join(rule.get("required_elements") or ["品牌定位", "业务场景", "能力事实"])

    return "\n\n".join(
        [
            f"{brand}聚焦{primary_line}场景，围绕{action_name}提供更清晰的官网说明，帮助潜在客户快速理解业务价值与落地方式。",
            f"在内容组织上，优先交代品牌定位、适用场景与可确认的产品能力，并用简洁表达覆盖{required}。",
            f"如缺少可公开验证的案例或数字，应使用保守表述，确保整段文本可以直接用于官网发布。",
        ]
    )


def _content_type(action: dict[str, Any]) -> str:
    action_type = str(action.get("action_type") or "").strip()
    asset = str(((action.get("output_assets") or [""])[0]) or "").strip()
    if action_type == "qa_answer":
        return "官网 FAQ / 问答答案"
    if action_type == "website_content":
        return "官网场景页 / 产品介绍正文"
    if asset:
        return asset
    return action_type or "官网正文"


def _content_generation_system_prompt() -> str:
    return (
        "你是一位中国 B2B SaaS 品牌官网内容写作专家。"
        "你的唯一任务是输出可直接发布到品牌官网的中文正文。"
        "不要输出写作说明、策略建议、标题标签、备注、项目符号解释或任何提示词痕迹。"
        "只能使用用户提供的事实；缺少证据时，改用保守、概括性表达，不要编造数字、客户、排名或案例。"
    )


def _content_generation_user_prompt(brief: dict[str, Any]) -> str:
    return (
        "请根据以下 Brief，直接写出可发布正文。\n\n"
        "【硬性要求】\n"
        "1. 只输出最终正文，不要解释你的写法。\n"
        "2. 不要出现“建议围绕”“正文建议按”“建议同步覆盖”“可按以下结构”“以下为”等元提示语。\n"
        "3. 不要编造 available_facts 之外的数字、客户名称、案例名称、排名。\n"
        "4. 如果某些证据不足，允许省略对应段落，也不要强行补全。\n"
        "5. 语气要像品牌官网正式对外文案，不要像内部策略说明。\n\n"
        f"{brief_to_json_text(brief)}"
    )


def _publish_platforms(action: dict[str, Any], rule: dict[str, Any]) -> list[str]:
    source_platforms = {
        "official_site": ["官网场景页"],
        "case_study": ["官网案例页"],
        "media_news": ["行业媒体稿"],
        "tech_community": ["技术社区内容"],
        "ugc_social": ["知乎", "小红书", "公众号"],
        "qa_forum": ["知乎问答", "行业问答平台"],
    }
    fallback = ["官网", "知乎", "公众号"]
    platforms: list[str] = []
    for source in action.get("target_sources") or []:
        platforms.extend(source_platforms.get(source, []))
    for applies_to in rule.get("applies_to") or []:
        platforms.extend(source_platforms.get(applies_to, []))
    unique = list(dict.fromkeys(platforms))
    return unique or fallback


def _versions_for_brand(brand_id: object) -> list[dict[str, Any]]:
    if not brand_id:
        return []
    versions = [
        _with_current_attribution(version)
        for version in content_versions_store.read().values()
        if isinstance(version, dict) and version.get("brand_id") == brand_id
    ]
    return sorted(versions, key=lambda item: item.get("created_at") or "", reverse=True)


def _with_current_attribution(version: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(version)
    attribution = _attribution_for_content_version(str(version.get("content_version_id") or ""))
    if attribution:
        enriched["effect_attribution"] = attribution
    return enriched


def _next_version_number(brand_id: object, action_id: object, rule_id: object) -> int:
    matches = [
        version
        for version in content_versions_store.read().values()
        if isinstance(version, dict)
        and version.get("brand_id") == brand_id
        and version.get("action_id") == action_id
        and version.get("rule_id") == rule_id
    ]
    versions = [int(item.get("version") or 0) for item in matches if str(item.get("version") or "").isdigit()]
    return (max(versions) if versions else 0) + 1


def _queryset_summary(contract: dict[str, Any] | None) -> dict[str, Any]:
    queryset = ((contract or {}).get("queryset") or {}) if isinstance(contract, dict) else {}
    queries = queryset.get("queries") or []
    return {
        "queryset_id": queryset.get("queryset_id"),
        "queryset_version": queryset.get("queryset_version"),
        "parent_queryset_id": queryset.get("parent_queryset_id"),
        "queries_count": len(queries),
        "query_ids": [query.get("query_id") for query in queries if isinstance(query, dict) and query.get("query_id")],
    }


def _content_lineage(contract: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(contract, dict):
        return {}
    lineage = contract.get("lineage") or {}
    return {
        "baseline_run_id": contract.get("latest_run_id") or ((contract.get("diagnostic_run") or {}).get("run_id")),
        "report_id": (contract.get("report") or {}).get("report_id"),
        "brand_config_id": lineage.get("brand_config_id") or ((contract.get("brand_config") or {}).get("brand_config_id")),
        "entity_id": lineage.get("entity_id") or ((contract.get("brand_config") or {}).get("entity_id")),
        "queryset_id": lineage.get("queryset_id") or _queryset_summary(contract).get("queryset_id"),
        "queryset_version": lineage.get("queryset_version") or _queryset_summary(contract).get("queryset_version"),
        "parent_queryset_id": lineage.get("parent_queryset_id") or _queryset_summary(contract).get("parent_queryset_id"),
        "aggregation_version": lineage.get("aggregation_version"),
        "inspection_batch_id": lineage.get("inspection_batch_id"),
        "llm_provider": "claude",
        "web_search_enabled": lineage.get("web_search_enabled", True),
        "web_search_mode": lineage.get("web_search_mode") or "responses_web_search",
    }


def _empty_feedback_summary() -> dict[str, int | float]:
    return {"helpful": 0, "not_helpful": 0, "total": 0, "net_score": 0}


def _feedback_summary(content_version_id: str) -> dict[str, int | float]:
    helpful = 0
    not_helpful = 0
    for feedback in content_feedback_store.read().values():
        if not isinstance(feedback, dict) or feedback.get("content_version_id") != content_version_id:
            continue
        if feedback.get("signal") == "helpful":
            helpful += 1
        elif feedback.get("signal") == "not_helpful":
            not_helpful += 1
    total = helpful + not_helpful
    return {"helpful": helpful, "not_helpful": not_helpful, "total": total, "net_score": helpful - not_helpful}


def _new_attribution(version: dict[str, Any], contract: dict[str, Any] | None) -> dict[str, Any]:
    existing = _attribution_for_content_version(str(version.get("content_version_id") or ""))
    if existing:
        return existing
    now = datetime.now(timezone.utc).isoformat()
    attribution_id = f"attr_{uuid4().hex[:12]}"
    lineage = version.get("lineage") or _content_lineage(contract)
    attribution = {
        "attribution_id": attribution_id,
        "schema_version": EFFECT_ATTRIBUTION_SCHEMA_VERSION,
        "content_version_id": version.get("content_version_id"),
        "brand_id": version.get("brand_id"),
        "brand_config_id": version.get("brand_config_id"),
        "action_id": version.get("action_id"),
        "action_type": version.get("action_type"),
        "rule_id": version.get("rule_id"),
        "rule_version": version.get("rule_version"),
        "baseline_run_id": version.get("baseline_run_id") or lineage.get("baseline_run_id"),
        "comparison_run_id": None,
        "queryset_id": lineage.get("queryset_id"),
        "queryset_version": lineage.get("queryset_version"),
        "parent_queryset_id": lineage.get("parent_queryset_id"),
        "target_intents": version.get("target_intents") or [],
        "target_query_ids": (version.get("queryset") or {}).get("query_ids") or [],
        "metric_scope": "targeted",
        "effect_delta": None,
        "feedback_summary": version.get("feedback_summary") or _empty_feedback_summary(),
        "comparability": {
            "same_queryset": None,
            "same_action": True,
            "same_rule": True,
            "confidence": "pending",
            "reason": "Awaiting comparison diagnostic run.",
        },
        "status": "awaiting_retest",
        "message": "Content version persisted; effect_delta will be computed after a comparison run.",
        "created_at": now,
        "updated_at": now,
    }
    effect_attribution_store.upsert(attribution_id, attribution)
    return attribution


def _attribution_for_content_version(content_version_id: str) -> dict[str, Any] | None:
    return next(
        (
            attribution
            for attribution in effect_attribution_store.read().values()
            if isinstance(attribution, dict) and attribution.get("content_version_id") == content_version_id
        ),
        None,
    )


def _latest_comparison_run_id(baseline_run_id: object, brand_config_id: object) -> str | None:
    candidates = []
    for run in runs_store.read().values():
        if not isinstance(run, dict) or run.get("status") != "completed" or not isinstance(run.get("report_data"), dict):
            continue
        if run.get("run_id") == baseline_run_id:
            continue
        report_brand_config = run["report_data"].get("brand_config") or {}
        if brand_config_id and run.get("brand_config_id") != brand_config_id and report_brand_config.get("brand_config_id") != brand_config_id:
            continue
        candidates.append(run)
    if not candidates:
        return None
    candidates.sort(key=lambda item: item.get("inspection_completed_at") or item.get("updated_at") or "", reverse=True)
    return candidates[0].get("run_id")


def _completed_report(run: dict[str, Any] | None) -> bool:
    return bool(isinstance(run, dict) and run.get("status") == "completed" and isinstance(run.get("report_data"), dict))


def _effect_delta(baseline_report: dict[str, Any], comparison_report: dict[str, Any]) -> dict[str, Any]:
    before = baseline_report.get("global") or {}
    after = comparison_report.get("global") or {}
    rows: dict[str, dict[str, Any]] = {}
    for metric_id, definition in METRIC_DEFINITIONS.items():
        before_value = _number(before.get(metric_id))
        after_value = _number(after.get(metric_id))
        if before_value is None or after_value is None:
            rows[metric_id] = {"before": before_value, "after": after_value, "delta": None, "direction": definition["direction"]}
            continue
        delta = after_value - before_value
        if definition["direction"] == "lower_is_better":
            delta = before_value - after_value
        rows[metric_id] = {
            "before": before_value,
            "after": after_value,
            "delta": _round(delta, 4),
            "direction": definition["direction"],
            "improved": delta > 0,
        }
    target_values = [row["delta"] for row in rows.values() if isinstance(row.get("delta"), (int, float))]
    return {
        "metrics": rows,
        "effect_delta_targeted": _round(sum(target_values) / len(target_values), 4) if target_values else None,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def _comparability(attribution: dict[str, Any], baseline_report: dict[str, Any], comparison_report: dict[str, Any]) -> dict[str, Any]:
    baseline_lineage = baseline_report.get("lineage") or {}
    comparison_lineage = comparison_report.get("lineage") or {}
    baseline_queryset_id = baseline_lineage.get("queryset_id")
    comparison_queryset_id = comparison_lineage.get("queryset_id")
    same_queryset = bool(baseline_queryset_id and baseline_queryset_id == comparison_queryset_id)
    same_parent = bool(
        baseline_queryset_id
        and baseline_queryset_id
        in {comparison_lineage.get("queryset_id"), comparison_lineage.get("parent_queryset_id")}
    )
    confidence = "high" if same_queryset else "medium" if same_parent else "low"
    reason = (
        "Same frozen QuerySet."
        if same_queryset
        else "Comparison run is linked to the baseline QuerySet parent."
        if same_parent
        else "QuerySet lineage differs; effect_delta should be treated as directional only."
    )
    return {
        "same_queryset": same_queryset,
        "same_action": bool(attribution.get("action_id")),
        "same_rule": bool(attribution.get("rule_id")),
        "confidence": confidence,
        "reason": reason,
        "baseline_queryset_id": baseline_queryset_id,
        "comparison_queryset_id": comparison_queryset_id,
    }


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
