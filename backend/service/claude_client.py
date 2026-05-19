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
        self.model = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001").strip()
        self.version = os.getenv("CLAUDE_ANTHROPIC_VERSION", "2023-06-01").strip()
        self.timeout = float(os.getenv("CLAUDE_TIMEOUT_SECONDS", os.getenv("REQUEST_TIMEOUT_SECONDS", "45")))
        self.web_search_enabled = _env_bool("CLAUDE_WEB_SEARCH_ENABLED", True)
        self.web_search_max_uses = int(os.getenv("CLAUDE_WEB_SEARCH_MAX_USES", "5"))
        self.api_style = os.getenv("CLAUDE_API_STYLE", "anthropic").strip().lower()
        self.web_search_mode = os.getenv("CLAUDE_WEB_SEARCH_MODE", "").strip().lower()
        self.messages_endpoint = os.getenv("CLAUDE_MESSAGES_ENDPOINT", "/v1/messages").strip() or "/v1/messages"
        self.chat_endpoint = os.getenv("CLAUDE_CHAT_COMPLETIONS_ENDPOINT", "/chat/completions").strip() or "/chat/completions"

    async def inspect(self, query: dict, brand_config: dict, options: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("CLAUDE_API_KEY is not configured; Claude inspection cannot run.")
        if not self.base_url:
            raise RuntimeError("CLAUDE_BASE_URL is not configured; Claude inspection cannot run.")
        if not self.model:
            raise RuntimeError("CLAUDE_MODEL is not configured; Claude inspection cannot run.")

        raw_response = await self._post_with_retry(self._payload(query, brand_config, options=options))
        content = _response_text(raw_response, self.api_style)
        if self.api_style == "anthropic" and not content and _has_unresolved_tool_use(raw_response):
            raw_response = await self._post_with_retry(self._payload(query, brand_config, include_tools=False, options=options))
            content = _response_text(raw_response, self.api_style)
        if not content:
            raise RuntimeError("Claude returned an empty message content.")

        parsed = parse_json_answer(content, brand_config)
        api_citations = _extract_citations(raw_response, self.api_style)
        if api_citations:
            parsed["citations"] = _merge_citations(parsed.get("citations", []), api_citations)
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

    async def invoke_task(self, task: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("CLAUDE_API_KEY is not configured; Claude task cannot run.")
        if not self.base_url:
            raise RuntimeError("CLAUDE_BASE_URL is not configured; Claude task cannot run.")
        if not self.model:
            raise RuntimeError("CLAUDE_MODEL is not configured; Claude task cannot run.")

        raw_response = await self._post_with_retry(self._task_payload(task))
        content = _response_text(raw_response, self.api_style).strip()
        if not content:
            raise RuntimeError("Claude returned an empty task content.")
        return {
            "platform": self.platform,
            "model": raw_response.get("model", self.model),
            "raw_text": content,
            "usage": raw_response.get("usage", {}),
            "citations": _extract_citations(raw_response, self.api_style),
            "raw_response": raw_response,
        }

    def _task_payload(self, task: dict[str, Any]) -> dict[str, Any]:
        system = str(task.get("system_prompt") or "").strip()
        user = str(task.get("user_prompt") or task.get("input_text") or "").strip()
        options = task.get("options") if isinstance(task.get("options"), dict) else {}
        temperature = options.get("temperature", 0)
        max_tokens = int(options.get("max_tokens", os.getenv("CLAUDE_MAX_TOKENS", "1600")))
        response_format = task.get("response_format") if isinstance(task.get("response_format"), dict) else None
        tools = task.get("tools") if isinstance(task.get("tools"), list) else None

        if self.api_style in {"openai", "chat", "chat_completions"}:
            payload: dict[str, Any] = {
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "stream": False,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if response_format:
                payload["response_format"] = response_format
            if tools:
                payload["tools"] = tools
            elif options.get("web_search_enabled") and self.web_search_enabled:
                mode = self.web_search_mode or "web_search_options"
                if mode == "web_search_options":
                    payload["web_search_options"] = _web_search_options()
                elif mode == "openai_tool":
                    payload["tools"] = [{"type": "web_search"}]
            return payload

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        if tools:
            payload["tools"] = tools
        elif options.get("web_search_enabled") and self.web_search_enabled:
            payload["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": self.web_search_max_uses}]
        return payload

    def _payload(self, query: dict, brand_config: dict, include_tools: bool = True, options: dict[str, Any] | None = None) -> dict[str, Any]:
        options = options or {}
        if self.api_style in {"openai", "chat", "chat_completions"}:
            return self._openai_payload(query, brand_config, include_tools, options)
        return self._anthropic_payload(query, brand_config, include_tools, options)

    def _anthropic_payload(self, query: dict, brand_config: dict, include_tools: bool = True, options: dict[str, Any] | None = None) -> dict[str, Any]:
        options = options or {}
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": int(options.get("max_tokens", os.getenv("CLAUDE_MAX_TOKENS", "1600"))),
            "temperature": options.get("temperature", 0),
            "system": _system_prompt(),
            "messages": [{"role": "user", "content": _user_prompt(self.platform, query, brand_config)}],
        }
        if include_tools and options.get("web_search_enabled", self.web_search_enabled):
            payload["tools"] = [
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": self.web_search_max_uses,
                }
            ]
        return payload

    def _openai_payload(self, query: dict, brand_config: dict, include_tools: bool = True, options: dict[str, Any] | None = None) -> dict[str, Any]:
        options = options or {}
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": _user_prompt(self.platform, query, brand_config)},
            ],
            "stream": False,
            "temperature": options.get("temperature", 0),
            "max_tokens": int(options.get("max_tokens", os.getenv("CLAUDE_MAX_TOKENS", "1600"))),
            "response_format": {"type": "json_object"},
        }
        if include_tools and options.get("web_search_enabled", self.web_search_enabled):
            mode = options.get("web_search_mode") or self.web_search_mode or "web_search_options"
            if mode == "web_search_options":
                payload["web_search_options"] = _web_search_options()
            elif mode == "anthropic_tool":
                payload["tools"] = [
                    {
                        "type": "web_search_20250305",
                        "name": "web_search",
                        "max_uses": self.web_search_max_uses,
                    }
                ]
            elif mode == "doubao_plugin":
                payload["plugins"] = [{"type": "web_search", "web_search": {"searcher": {"type": "web_searcher"}}}]
            elif mode == "openai_tool":
                payload["tools"] = [{"type": "web_search"}]
        return payload

    async def _post_with_retry(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.api_style in {"openai", "chat", "chat_completions"}:
            url = _join_url(self.base_url, self.chat_endpoint)
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        else:
            url = _join_url(self.base_url, self.messages_endpoint)
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
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as error:
                        raise RuntimeError(_http_error_message(self.platform, error)) from error
                    data = response.json()
                    if not isinstance(data, dict):
                        raise RuntimeError("Claude response was not a JSON object.")
                    return data
                except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.TransportError, ValueError, RuntimeError) as error:
                    last_error = error
                    if attempt < 2:
                        await asyncio.sleep(1.2 * (attempt + 1))
        raise RuntimeError(f"Claude request failed: {last_error}") from last_error


def _response_text(raw_response: dict, api_style: str) -> str:
    if api_style in {"openai", "chat", "chat_completions"}:
        return _openai_text_content(raw_response)
    return _anthropic_text_content(raw_response)


def _anthropic_text_content(raw_response: dict) -> str:
    parts = []
    for item in raw_response.get("content", []):
        if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
            parts.append(item["text"])
    return "\n".join(parts).strip()


def _openai_text_content(raw_response: dict) -> str:
    message = raw_response.get("choices", [{}])[0].get("message", {})
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
            elif isinstance(item, dict) and isinstance(item.get("content"), str):
                parts.append(item["content"])
        return "\n".join(parts).strip()
    return ""


def _has_unresolved_tool_use(raw_response: dict) -> bool:
    if raw_response.get("stop_reason") != "tool_use":
        return False
    return any(
        isinstance(item, dict) and item.get("type") == "tool_use"
        for item in raw_response.get("content", [])
    )


def _extract_citations(raw_response: dict, api_style: str = "anthropic") -> list[dict]:
    if api_style in {"openai", "chat", "chat_completions"}:
        return _extract_openai_citations(raw_response)
    return _extract_anthropic_citations(raw_response)


def _extract_anthropic_citations(raw_response: dict) -> list[dict]:
    citations: list[dict] = []
    for item in raw_response.get("content", []):
        if not isinstance(item, dict):
            continue
        for citation in item.get("citations", []) or []:
            if not isinstance(citation, dict):
                continue
            if citation.get("type") != "web_search_result_location":
                continue
            citations.append({
                "url": _str_or_none(citation.get("url")),
                "domain": _domain_from_url(_str_or_none(citation.get("url"))),
                "title": _str_or_none(citation.get("title")),
                "is_official": None,
                "quoted_text": _str_or_none(citation.get("cited_text")),
                "answer_excerpt": item.get("text") if isinstance(item.get("text"), str) else None,
            })
    return _dedup_citations(citations)


def _extract_openai_citations(raw_response: dict) -> list[dict]:
    choices = raw_response.get("choices")
    if not isinstance(choices, list) or not choices:
        return []
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return []

    citations: list[dict] = []
    citations.extend(_parse_openai_annotation_citations(message.get("annotations")))
    citations.extend(_parse_citation_list(message.get("citations")))

    search_info = message.get("search_info")
    if isinstance(search_info, dict):
        for key in ("sources", "citations", "urls", "references", "results"):
            citations.extend(_parse_citation_list(search_info.get(key)))

    citations.extend(_parse_citation_list(message.get("ref_content")))
    return _dedup_citations(citations)


def _parse_openai_annotation_citations(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    citations: list[dict] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        source = item.get("url_citation") if isinstance(item.get("url_citation"), dict) else item
        url = _first_str(source, ["url", "link", "source_url"])
        citations.append({
            "url": url,
            "domain": _first_str(source, ["domain"]) or _domain_from_url(url),
            "title": _first_str(source, ["title", "name"]),
            "is_official": None,
            "quoted_text": _first_str(source, ["quote", "quoted_text", "snippet", "content", "text"]),
            "answer_excerpt": None,
        })
    return citations


def _parse_citation_list(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    citations: list[dict] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        url = _first_str(item, ["url", "link", "source_url"])
        citations.append({
            "url": url,
            "domain": _first_str(item, ["domain", "source"]) or _domain_from_url(url),
            "title": _first_str(item, ["title", "name"]),
            "is_official": None,
            "quoted_text": _first_str(item, ["quoted_text", "quote", "snippet", "content", "text"]),
            "answer_excerpt": _first_str(item, ["answer_excerpt", "context"]),
        })
    return citations


def _merge_citations(model_citations: list[dict], api_citations: list[dict]) -> list[dict]:
    seen_urls: set[str] = set()
    merged: list[dict] = []
    for citation in model_citations:
        if not isinstance(citation, dict):
            continue
        url = citation.get("url") if isinstance(citation.get("url"), str) else None
        if url:
            seen_urls.add(url)
        merged.append(citation)
    for citation in api_citations:
        url = citation.get("url") if isinstance(citation.get("url"), str) else None
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        merged.append(citation)
    return merged


def _dedup_citations(citations: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for citation in citations:
        url = citation.get("url") if isinstance(citation.get("url"), str) else None
        if url and url in seen:
            continue
        if url:
            seen.add(url)
        result.append(citation)
    return result


def _str_or_none(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _first_str(obj: dict, keys: list[str]) -> str | None:
    for key in keys:
        value = obj.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _domain_from_url(url: str | None) -> str | None:
    if not url:
        return None
    from urllib.parse import urlparse

    netloc = urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _join_url(base_url: str, endpoint: str) -> str:
    if base_url.endswith(endpoint):
        return base_url
    return f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"


def _web_search_options() -> dict:
    return {
        "search_context_size": os.getenv("CLAUDE_WEB_SEARCH_CONTEXT_SIZE", "medium").strip() or "medium",
        "user_location": {
            "type": "approximate",
            "approximate": {
                "timezone": os.getenv("CLAUDE_WEB_SEARCH_TIMEZONE", "Asia/Shanghai").strip() or "Asia/Shanghai",
                "country": os.getenv("CLAUDE_WEB_SEARCH_COUNTRY", "CN").strip() or "CN",
            },
        },
    }


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
