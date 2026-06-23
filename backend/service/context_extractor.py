from __future__ import annotations

import logging
from typing import Any

from service.llm_tasks import invoke_json_task
from service.platform_registry import create_task_client, llm_task_options

logger = logging.getLogger(__name__)


class ContextExtractor:
    """从 brand_config.topics 提取 pain_point/goal，未配置时调用 shared LLM task 推断。"""

    def is_available(self, task_type: str = "context_extraction") -> bool:
        provider = llm_task_options(task_type, {})["provider"]
        client = create_task_client(provider)
        return bool(
            str(getattr(client, "api_key", "") or "").strip()
            and str(getattr(client, "base_url", "") or "").strip()
            and str(getattr(client, "model", "") or "").strip()
        )

    async def extract_context(self, topic: dict, entity_name: str) -> dict[str, str | None]:
        pain_point = topic.get("pain_point")
        goal = topic.get("goal")
        topic_name = str(topic.get("topic_name") or "")
        business_line = str(topic.get("business_line") or "")

        if pain_point and goal:
            return {"pain_point": pain_point, "goal": goal}

        if not self.is_available():
            logger.warning(
                "context_extraction_llm_unavailable_using_fallback",
                extra={"topic_name": topic_name, "business_line": business_line},
            )
            return {
                "pain_point": pain_point or self._infer_fallback_pain_point(topic_name, business_line),
                "goal": goal or self._infer_fallback_goal(topic_name, business_line),
            }

        try:
            inferred = await self._infer_context(topic, entity_name)
        except Exception as error:
            logger.warning(
                "context_extraction_llm_failed_using_fallback",
                extra={"topic_name": topic_name, "business_line": business_line, "error": str(error)},
            )
            inferred = {
                "pain_point": self._infer_fallback_pain_point(topic_name, business_line),
                "goal": self._infer_fallback_goal(topic_name, business_line),
            }
        return {
            "pain_point": pain_point or inferred.get("pain_point"),
            "goal": goal or inferred.get("goal"),
        }

    async def extract_all(self, topics: list[dict], entity_name: str) -> list[dict[str, Any]]:
        results = []
        for topic in topics:
            ctx = await self.extract_context(topic, entity_name)
            results.append({**topic, **ctx})
        return results

    async def extract_with_questions(
        self,
        *,
        topic_name: str,
        business_line: str | None = None,
        entity_name: str | None = None,
        pain_point: str | None = None,
        goal: str | None = None,
    ) -> dict[str, Any]:
        topic = {
            "topic_name": topic_name,
            "business_line": business_line or "",
            "pain_point": pain_point or None,
            "goal": goal or None,
        }
        brand_name = entity_name or "目标企业"
        context = await self.extract_context(topic, brand_name)
        if not self.is_available("intent_analysis"):
            raise RuntimeError(
                f"Intent analysis error: topic '{topic_name}' requires a configured LLM for intent_analysis."
            )
        return await self._infer_intent_analysis(topic, brand_name, context)

    async def generate_ai_questions(
        self,
        *,
        topic: dict,
        entity_name: str,
        pain_point: str,
        goal: str | None = None,
        audience_profile: str | None = None,
    ) -> list[dict[str, str]]:
        result = await invoke_json_task(
            task_type="intent_analysis",
            payload={
                "brand_config": {"entity_name": entity_name},
                "topic": topic,
                "pain_point": pain_point,
                "goal": goal,
                "audience_profile": audience_profile,
                "web_search_enabled": True,
            },
            system_prompt="你是 GEO/AI 搜索意图分析师，需要把业务痛点转化为真实用户会向 AI 平台提出的问题。只能返回合法 JSON 对象，不要输出 Markdown。",
            user_prompt=_questions_user_prompt(
                str(topic.get("topic_name") or ""),
                str(topic.get("business_line") or ""),
                entity_name,
                pain_point,
                goal or "",
                audience_profile or "",
            ),
        )
        _log_if_task_fallback(result, "intent_analysis")
        parsed = result.get("parsed") or {}
        raw_questions = parsed.get("ai_questions") if isinstance(parsed, dict) else []
        return _normalize_questions(raw_questions)

    async def _infer_context(self, topic: dict, entity_name: str) -> dict[str, str]:
        topic_name = topic.get("topic_name", "")
        business_line = topic.get("business_line", "")
        result = await invoke_json_task(
            task_type="context_extraction",
            payload={
                "brand_config": {"entity_name": entity_name},
                "topic": topic,
                "web_search_enabled": True,
            },
            system_prompt="你是业务分析师，需要根据业务线信息推断典型的业务痛点和发展目标。只能返回一个合法 JSON 对象，不要输出 Markdown。",
            user_prompt=_context_user_prompt(topic_name, business_line, entity_name),
        )
        _log_if_task_fallback(result, "context_extraction")
        parsed = result.get("parsed") or {}
        return {
            "pain_point": _text(parsed.get("pain_point")),
            "goal": _text(parsed.get("goal")),
        }

    def _infer_fallback_pain_point(self, topic_name: str, business_line: str) -> str:
        subject = _text(topic_name) or _text(business_line) or "当前业务"
        return f"{subject}效果不稳定"

    def _infer_fallback_goal(self, topic_name: str, business_line: str) -> str:
        subject = _text(business_line) or _text(topic_name) or "业务"
        return f"提升{subject}效果"

    async def _infer_intent_analysis(
        self,
        topic: dict,
        entity_name: str,
        context: dict[str, str | None],
    ) -> dict[str, Any]:
        topic_name = str(topic.get("topic_name") or "")
        business_line = str(topic.get("business_line") or "")
        base_pain_point = context.get("pain_point") or ""
        base_goal = context.get("goal") or ""
        result = await invoke_json_task(
            task_type="intent_analysis",
            payload={
                "brand_config": {"entity_name": entity_name},
                "topic": topic,
                "context": context,
                "web_search_enabled": True,
            },
            system_prompt="你是 GEO/AI 搜索意图分析师，需要分析目标受众、痛点强度和用户会向 AI 平台提出的问题。只能返回合法 JSON 对象，不要输出 Markdown。",
            user_prompt=_intent_user_prompt(topic_name, business_line, entity_name, base_pain_point, base_goal),
        )
        _log_if_task_fallback(result, "intent_analysis")
        parsed = result.get("parsed") or {}
        normalized = _normalize_intent_analysis(parsed, base_pain_point, base_goal, topic_name)
        warning = _quality_warning_from_task_result(result)
        if warning:
            normalized["quality_warning"] = warning
        return normalized


def _context_user_prompt(topic_name: str, business_line: str, entity_name: str) -> str:
    return f"""
品牌：{entity_name}
业务线全称：{topic_name}
业务线标签：{business_line}

请推断该业务线最典型的：
1. 业务痛点（用户/客户最常遇到的问题）
2. 业务目标（企业最想达成的效果）

请返回 JSON：
{{
  "pain_point": "典型的业务痛点描述，尽量简洁（20字以内）",
  "goal": "典型的业务目标描述，尽量简洁（20字以内）"
}}

注意：
- pain_point 应该从用户/客户视角描述问题
- goal 应该从企业/业务视角描述目标
- 不要编造，只基于业务线名称推断最常见的情况
"""


def _intent_user_prompt(
    topic_name: str,
    business_line: str,
    entity_name: str,
    base_pain_point: str,
    base_goal: str,
) -> str:
    return f"""
品牌：{entity_name}
业务线全称：{topic_name}
业务线标签：{business_line}
基础痛点：{base_pain_point}
基础目标：{base_goal}

请围绕该 topic 生成 Topic Intent Analysis，分析目标受众会在 AI 平台上提出哪些问题。

请返回 JSON：
{{
  "audience_profile": "目标受众画像，说明角色、场景和决策压力，40字以内",
  "pain_points": [
    {{
      "pain_point": "用户/客户视角的具体痛点，30字以内",
      "severity": 4,
      "goal": "企业希望达成的目标，30字以内",
      "ai_questions": [
        {{
          "question": "用户会向 AI 平台提出的自然语言问题",
          "intent_type": "scenario_diagnosis"
        }}
      ]
    }}
  ]
}}

要求：
- pain_points 返回 2-4 个，severity 为 1-5 的整数
- 每个 pain_point 返回 2-3 个 ai_questions
- intent_type 优先使用：{", ".join(_intent_types())}
- question 要像真实采购、运营或业务负责人会问 AI 的问题
- 不要编造具体厂商结论；可以描述「供应商」「平台」「方案」等泛称
"""


def _questions_user_prompt(
    topic_name: str,
    business_line: str,
    entity_name: str,
    pain_point: str,
    goal: str,
    audience_profile: str,
) -> str:
    return f"""
品牌：{entity_name}
业务线全称：{topic_name}
业务线标签：{business_line}
目标受众：{audience_profile}
痛点：{pain_point}
目标：{goal}

请只为该痛点生成 2-3 个用户会向 AI 平台提出的问题。

请返回 JSON：
{{
  "ai_questions": [
    {{"question": "问题文本", "intent_type": "scenario_diagnosis"}}
  ]
}}

intent_type 优先使用：{", ".join(_intent_types())}
"""


def _text(value: object) -> str:
    return str(value or "").strip()


def _log_if_task_fallback(result: dict[str, Any], task_type: str) -> None:
    warning = _quality_warning_from_task_result(result)
    if warning:
        logger.warning(
            "context_extractor_used_llm_provider_fallback",
            extra={"task_type": task_type, **warning},
        )


def _quality_warning_from_task_result(result: dict[str, Any]) -> dict[str, Any] | None:
    if not result.get("used_fallback"):
        return None
    return {
        "used_fallback": True,
        "primary_provider": result.get("primary_provider"),
        "fallback_provider": result.get("provider"),
        "fallback_reason": result.get("fallback_reason"),
    }


def _intent_types() -> list[str]:
    try:
        from service.rule_matrix import MATRIX_TEMPLATES

        values = [str(item.get("intent_type") or "").strip() for item in MATRIX_TEMPLATES]
        return list(dict.fromkeys(value for value in values if value))
    except Exception:
        return [
            "scenario_diagnosis",
            "vendor_recommendation",
            "competitive_comparison",
            "capability_assessment",
            "vendor_choice",
            "purchase_risk",
        ]


def _normalize_intent_analysis(
    parsed: object,
    base_pain_point: str,
    base_goal: str,
    topic_name: str,
) -> dict[str, Any]:
    data = parsed if isinstance(parsed, dict) else {}
    audience_profile = _text(data.get("audience_profile")) or f"{topic_name}相关业务负责人和运营决策者"
    raw_points = data.get("pain_points")
    if not isinstance(raw_points, list) or not raw_points:
        raw_points = [
            {
                "pain_point": base_pain_point or f"{topic_name}效果不稳定",
                "severity": 3,
                "goal": base_goal or "提升业务效果",
                "ai_questions": data.get("ai_questions") if isinstance(data.get("ai_questions"), list) else [],
            }
        ]

    pain_points: list[dict[str, Any]] = []
    for raw in raw_points[:4]:
        item = raw if isinstance(raw, dict) else {"pain_point": raw}
        pain_point = _text(item.get("pain_point")) or base_pain_point or f"{topic_name}效果不稳定"
        goal = _text(item.get("goal")) or base_goal or None
        questions = _normalize_questions(item.get("ai_questions"))
        if not questions:
            questions = _fallback_questions(topic_name, pain_point)
        pain_points.append(
            {
                "pain_point": pain_point,
                "severity": _bounded_int(item.get("severity"), default=3),
                "goal": goal,
                "ai_questions": questions[:3],
            }
        )
    return {"audience_profile": audience_profile, "pain_points": pain_points}


def _normalize_questions(raw_questions: object) -> list[dict[str, str]]:
    if not isinstance(raw_questions, list):
        return []
    questions: list[dict[str, str]] = []
    allowed_types = set(_intent_types())
    for raw in raw_questions:
        if isinstance(raw, str):
            question = _text(raw)
            intent_type = "scenario_diagnosis"
        elif isinstance(raw, dict):
            question = _text(raw.get("question"))
            intent_type = _text(raw.get("intent_type")) or "scenario_diagnosis"
        else:
            continue
        if not question:
            continue
        if intent_type not in allowed_types:
            intent_type = "scenario_diagnosis"
        questions.append({"question": question, "intent_type": intent_type})
    return questions


def _fallback_questions(topic_name: str, pain_point: str) -> list[dict[str, str]]:
    return [
        {
            "question": f"{topic_name}遇到{pain_point}，应该先排查哪些问题？",
            "intent_type": "scenario_diagnosis",
        },
        {
            "question": f"解决{pain_point}有哪些成熟的{topic_name}平台或方案？",
            "intent_type": "vendor_recommendation",
        },
    ]


def _bounded_int(value: object, *, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(1, min(5, number))
