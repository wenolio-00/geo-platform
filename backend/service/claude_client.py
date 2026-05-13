from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

from service.parser import parse_json_answer


class ClaudeClient:
    def __init__(self) -> None:
        self.platform = "Claude"
        self.env_prefix = "CLAUDE"
        self.api_key = os.getenv("CLAUDE_API_KEY", os.getenv("ANTHROPIC_API_KEY", "")).strip()
        self.base_url = os.getenv("CLAUDE_BASE_URL", "https://api.anthropic.com").rstrip("/")
        self.model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514").strip()
        self.version = os.getenv("CLAUDE_ANTHROPIC_VERSION", "2023-06-01").strip()
        self.timeout = float(os.getenv("CLAUDE_TIMEOUT_SECONDS", os.getenv("REQUEST_TIMEOUT_SECONDS", "45")))

    async def inspect(self, query: dict, brand_config: dict) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("CLAUDE_API_KEY is not configured; Claude inspection cannot run.")
        if not self.base_url:
            raise RuntimeError("CLAUDE_BASE_URL is not configured; Claude inspection cannot run.")
        if not self.model:
            raise RuntimeError("CLAUDE_MODEL is not configured; Claude inspection cannot run.")

        raw_response = await self._post_with_retry(self._payload(query, brand_config))
        content = _text_content(raw_response)
        if not content:
            raise RuntimeError("Claude returned an empty message content.")

        parsed = parse_json_answer(content, brand_config)
        return {
            "platform": self.platform,
            "model": raw_response.get("model", self.model),
            "query_id": query["query_id"],
            "query_text": query["query_text"],
            "query_pattern": query.get("query_pattern"),
            "query_layer": query.get("query_layer"),
            "topic": query["topic"],
            "intent_type": query["intent_type"],
            "raw_answer": content,
            "parsed": parsed,
            "usage": raw_response.get("usage", {}),
        }

    def _payload(self, query: dict, brand_config: dict) -> dict[str, Any]:
        return {
            "model": self.model,
            "max_tokens": int(os.getenv("CLAUDE_MAX_TOKENS", "1600")),
            "temperature": 0,
            "system": _system_prompt(),
            "messages": [{"role": "user", "content": _user_prompt(self.platform, query, brand_config)}],
        }

    async def _post_with_retry(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.version,
            "Content-Type": "application/json",
        }
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(3):
                try:
                    response = await client.post(url, headers=headers, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    if not isinstance(data, dict):
                        raise RuntimeError("Claude response was not a JSON object.")
                    return data
                except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.TransportError, ValueError) as error:
                    last_error = error
                    if attempt < 2:
                        await asyncio.sleep(1.2 * (attempt + 1))
        raise RuntimeError(f"Claude request failed: {last_error}") from last_error


def _text_content(raw_response: dict) -> str:
    parts = []
    for item in raw_response.get("content", []):
        if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
            parts.append(item["text"])
    return "\n".join(parts).strip()


def _system_prompt() -> str:
    return (
        "你是 GEO 品牌可见度巡检器。你必须先真实回答用户问题，再基于自己的回答抽取品牌提及情况。"
        "只能返回一个合法 JSON 对象，不要输出 Markdown。"
    )


def _user_prompt(platform: str, query: dict, brand_config: dict) -> str:
    brand = brand_config["entity_name"]
    aliases = brand_config.get("entity_aliases", [])
    competitors = brand_config.get("competitors", [])
    competitor_names = [item["name"] for item in competitors if item.get("name")]
    return f"""
巡检平台：{platform}
巡检对象：
- 本品牌：{brand}
- 本品牌别名：{aliases}
- 竞品：{competitor_names}
- 话题：{query["topic"]}
- QuerySet 场景：{query.get("query_pattern") or query.get("intent_type")}

用户问题：
{query["query_text"]}

请返回 JSON：
{{
  "answer": "面向用户的真实回答，保留完整业务判断",
  "mentioned_brands": [
    {{
      "name": "回答中出现的品牌名",
      "aliases_matched": ["命中的别名，可为空"],
      "position": 1,
      "mention_context": "explicit_recommendation|standard_listing|incidental_mention|not_mentioned",
      "sentiment": "positive|neutral|negative",
      "evidence": "从 answer 中摘取的一句依据"
    }}
  ],
  "citations": [
    {{
      "url": "只有 answer 中明确出现 URL 时才填写，否则不要编造",
      "domain": "域名",
      "title": "可为空",
      "is_official": true
    }}
  ],
  "parse_confidence": "high|medium|low",
  "notes": "可为空"
}}

约束：
1. mentioned_brands 只记录 answer 中真实出现或明确指代的品牌。
2. 不要为了满足字段而编造引用来源；没有 URL 就返回空 citations。
3. position 按 answer 中品牌首次出现或推荐顺序排序。
"""
