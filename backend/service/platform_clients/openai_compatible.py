from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

from service.parser import parse_json_answer


class OpenAICompatibleClient:
    def __init__(self, platform: str, env_prefix: str, default_base_url: str = "", default_model: str = "") -> None:
        self.platform = platform
        self.env_prefix = env_prefix
        self.api_key = os.getenv(f"{env_prefix}_API_KEY", "").strip()
        self.base_url = os.getenv(f"{env_prefix}_BASE_URL", default_base_url).rstrip("/")
        self.model = os.getenv(f"{env_prefix}_MODEL", default_model).strip()
        self.timeout = float(os.getenv(f"{env_prefix}_TIMEOUT_SECONDS", os.getenv("REQUEST_TIMEOUT_SECONDS", "45")))

    async def inspect(self, query: dict, brand_config: dict) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError(f"{self.env_prefix}_API_KEY is not configured; {self.platform} inspection cannot run.")
        if not self.base_url:
            raise RuntimeError(f"{self.env_prefix}_BASE_URL is not configured; {self.platform} inspection cannot run.")
        if not self.model:
            raise RuntimeError(f"{self.env_prefix}_MODEL is not configured; {self.platform} inspection cannot run.")

        payload = self._payload(query, brand_config)
        raw_response = await self._post_with_retry(payload)
        message = raw_response.get("choices", [{}])[0].get("message", {})
        content = message.get("content", "")
        if not content:
            raise RuntimeError(f"{self.platform} returned an empty message content.")

        parsed = parse_json_answer(content, brand_config)

        api_citations = self._extract_citations(raw_response, message)
        if api_citations:
            parsed["citations"] = _merge_citations(parsed.get("citations", []), api_citations)

        return {
            "platform": self.platform,
            "model": raw_response.get("model", self.model),
            "system_fingerprint": raw_response.get("system_fingerprint"),
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
        payload = {
            "model": self.model,
            "messages": self._messages(query, brand_config),
            "stream": False,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        plugins = self._web_search_plugins()
        if plugins:
            payload["plugins"] = plugins
        return payload

    def _extract_citations(self, raw_response: dict, message: dict) -> list[dict]:
        return []

    def _web_search_plugins(self) -> list[dict] | None:
        return None

    async def _post_with_retry(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(3):
                try:
                    response = await client.post(url, headers=headers, json=payload)
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as error:
                        raise RuntimeError(_http_error_message(self.platform, error)) from error
                    data = response.json()
                    if not isinstance(data, dict):
                        raise RuntimeError(f"{self.platform} response was not a JSON object.")
                    return data
                except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.TransportError, ValueError) as error:
                    last_error = error
                    if attempt < 2:
                        await asyncio.sleep(1.2 * (attempt + 1))
        raise RuntimeError(f"{self.platform} request failed: {last_error}") from last_error

    def _messages(self, query: dict, brand_config: dict) -> list[dict[str, str]]:
        brand = brand_config["entity_name"]
        aliases = brand_config.get("entity_aliases", [])
        competitors = brand_config.get("competitors", [])
        competitor_names = [item["name"] for item in competitors if item.get("name")]
        system = (
            "你是 GEO 品牌可见度巡检器。你必须先真实回答用户问题，再基于自己的回答抽取品牌提及情况。"
            "只能返回一个合法 JSON 对象，不要输出 Markdown。"
        )
        user = f"""
巡检平台：{self.platform}
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
      "is_official": true,
      "quoted_text": "该 URL 支撑的回答内容片段；必须来自 answer 或模型明确给出的引用片段",
      "answer_excerpt": "包含该 URL 或该引用判断的 answer 上下文，可为空"
    }}
  ],
  "parse_confidence": "high|medium|low",
  "notes": "可为空"
}}

约束：
1. mentioned_brands 只记录 answer 中真实出现或明确指代的品牌。
2. 不要为了满足字段而编造引用来源；没有 URL 就返回空 citations。
3. position 按 answer 中品牌首次出现或推荐顺序排序。
4. citations[].quoted_text 只能摘录 answer 中已有内容或平台返回的引用片段，不要凭空生成网页正文。
"""
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _merge_citations(model_citations: list[dict], api_citations: list[dict]) -> list[dict]:
    seen_urls: set[str] = set()
    merged: list[dict] = []
    for c in model_citations:
        url = c.get("url") if isinstance(c.get("url"), str) else None
        if url:
            seen_urls.add(url)
            merged.append(c)
    for c in api_citations:
        url = c.get("url") if isinstance(c.get("url"), str) else None
        if url and url not in seen_urls:
            seen_urls.add(url)
            merged.append(c)
        elif url is None and c.get("domain"):
            merged.append(c)
    return merged


def _http_error_message(platform: str, error: httpx.HTTPStatusError) -> str:
    response = error.response
    detail = response.text[:800]
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
        err = payload["error"]
        code = err.get("code") or err.get("type")
        message = err.get("message")
        if code or message:
            detail = f"{code}: {message}".strip(": ")
    return f"{platform} request failed with HTTP {response.status_code}: {detail}"
