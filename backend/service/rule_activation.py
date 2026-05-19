from __future__ import annotations

import json
from typing import Any

from service.llm_tasks import invoke_json_task, load_rule_activation_assets


async def evaluate_rule_activation(payload: dict[str, Any]) -> dict[str, Any]:
    assets = load_rule_activation_assets()
    result = await invoke_json_task(
        task_type="rule_activation",
        payload=payload,
        provider=payload.get("llm_provider"),
        system_prompt=_rule_activation_system_prompt(assets["config"]),
        user_prompt=_rule_activation_user_prompt(payload, assets["prompt"], assets["schema"]),
    )
    parsed = result.get("parsed") or {}
    return {
        "decision": parsed.get("decision"),
        "confidence": parsed.get("parse_confidence", parsed.get("confidence")),
        "activation_scope": parsed.get("activation_scope") or {},
        "reason": parsed.get("reason"),
        "metric_comparison": parsed.get("metric_comparison") or [],
        "risk_check": parsed.get("risk_check") or [],
        "rules_to_keep": parsed.get("rules_to_keep") or [],
        "rules_to_merge_into_baseline": parsed.get("rules_to_merge_into_baseline") or [],
        "rules_to_reject": parsed.get("rules_to_reject") or [],
        "recommended_next_action": parsed.get("recommended_next_action") or [],
        "llm_provider": result.get("provider"),
        "web_search_enabled": result.get("web_search_enabled", False),
        "web_search_mode": result.get("web_search_mode"),
    }


def _rule_activation_system_prompt(config: dict[str, Any]) -> str:
    policy = config.get("default_decision_policy") or {}
    return (
        "你是 GEO Rule Activation Evaluator。"
        f"默认决策策略是 {policy.get('mvp_default', 'keep_baseline')}。"
        "必须严格遵守风险阻断、平台拆分和 query pattern 拆分要求。"
        "只返回合法 JSON 对象，不要输出 Markdown。"
    )


def _rule_activation_user_prompt(payload: dict[str, Any], prompt_template: str, schema: dict[str, Any]) -> str:
    return (
        f"{prompt_template}\n\n"
        "请依据以下输入完成规则激活评估，并严格按照 JSON Schema 输出。\n\n"
        f"JSON Schema:\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        f"评估输入:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
