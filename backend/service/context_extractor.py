from __future__ import annotations

from typing import Any

from service.llm_tasks import invoke_json_task
from service.platform_registry import create_task_client, llm_task_options


class ContextExtractor:
    """从 brand_config.topics 提取 pain_point/goal，未配置时调用 shared LLM task 推断。"""

    def is_available(self) -> bool:
        provider = llm_task_options("context_extraction", {})["provider"]
        client = create_task_client(provider)
        return bool(
            str(getattr(client, "api_key", "") or "").strip()
            and str(getattr(client, "base_url", "") or "").strip()
            and str(getattr(client, "model", "") or "").strip()
        )

    async def extract_context(self, topic: dict, entity_name: str) -> dict[str, str | None]:
        pain_point = topic.get("pain_point")
        goal = topic.get("goal")

        if pain_point and goal:
            return {"pain_point": pain_point, "goal": goal}

        if not self.is_available():
            raise RuntimeError(
                f"Query mapping error: topic '{topic.get('topic_name', '')}' lacks pain_point/goal "
                "and the configured LLM is not available for context_extraction."
            )

        inferred = await self._infer_context(topic, entity_name)
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
        parsed = result.get("parsed") or {}
        return {
            "pain_point": _text(parsed.get("pain_point")),
            "goal": _text(parsed.get("goal")),
        }


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


def _text(value: object) -> str:
    return str(value or "").strip()
