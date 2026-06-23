from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import httpx

from service.parser import parse_json_answer


logger = logging.getLogger(__name__)


class OpenAICompatibleClient:
    def __init__(self, platform: str, env_prefix: str, default_base_url: str = "", default_model: str = "") -> None:
        self.platform = platform
        self.env_prefix = env_prefix
        self.api_key = _env_value(env_prefix, "API_KEY", "").strip()
        self.base_url = _env_value(env_prefix, "BASE_URL", default_base_url).rstrip("/")
        self.model = _env_value(env_prefix, "MODEL", default_model).strip()
        self.timeout = float(_env_value(env_prefix, "TIMEOUT_SECONDS", os.getenv("REQUEST_TIMEOUT_SECONDS", "45")))
        self.chat_endpoint = _env_value(env_prefix, "CHAT_COMPLETIONS_ENDPOINT", "/chat/completions").strip() or "/chat/completions"
        self.responses_endpoint = _env_value(env_prefix, "RESPONSES_ENDPOINT", "/responses").strip() or "/responses"
        self.web_search_enabled = _env_bool(f"{env_prefix}_WEB_SEARCH_ENABLED", False)
        self.web_search_mode = _env_value(env_prefix, "WEB_SEARCH_MODE", "").strip().lower()

    async def inspect(self, query: dict, brand_config: dict, options: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError(f"{self.env_prefix}_API_KEY is not configured; {self.platform} inspection cannot run.")
        if not self.base_url:
            raise RuntimeError(f"{self.env_prefix}_BASE_URL is not configured; {self.platform} inspection cannot run.")
        if not self.model:
            raise RuntimeError(f"{self.env_prefix}_MODEL is not configured; {self.platform} inspection cannot run.")

        options = options or {}
        payload = self._payload(query, brand_config, options=options)
        raw_response = await self._post_with_retry(payload, options=options)
        message = self._message(raw_response)
        content = message.get("content", "")
        if not content:
            raise RuntimeError(f"{self.platform} returned an empty message content.")

        parse_config = {} if options.get("blind_mode") else brand_config
        parsed = parse_json_answer(content, parse_config)

        api_citations = self._extract_citations(raw_response, message)
        if api_citations:
            parsed["citations"] = _merge_citations(parsed.get("citations", []), api_citations)

        return {
            "platform": self.platform,
            "provider": self.platform,
            "web_search_enabled": bool(options.get("web_search_enabled", self.web_search_enabled)),
            "web_search_mode": options.get("web_search_mode") or self.web_search_mode,
            "inspection_round": _inspection_round(options),
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

    async def invoke_task(self, task: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError(f"{self.env_prefix}_API_KEY is not configured; {self.platform} task cannot run.")
        if not self.base_url:
            raise RuntimeError(f"{self.env_prefix}_BASE_URL is not configured; {self.platform} task cannot run.")
        if not self.model:
            raise RuntimeError(f"{self.env_prefix}_MODEL is not configured; {self.platform} task cannot run.")

        payload = self._task_payload(task)
        options = task.get("options") if isinstance(task.get("options"), dict) else {}
        raw_response = await self._post_with_retry(payload, options=options)
        message = self._message(raw_response)
        content = message.get("content", "")
        if not content:
            raise RuntimeError(f"{self.platform} returned an empty task content.")
        return {
            "platform": self.platform,
            "provider": self.platform,
            "web_search_enabled": bool(options.get("web_search_enabled", self.web_search_enabled)),
            "web_search_mode": options.get("web_search_mode") or self.web_search_mode,
            "model": raw_response.get("model", self.model),
            "raw_text": content,
            "usage": raw_response.get("usage", {}),
            "citations": self._extract_citations(raw_response, message),
            "raw_response": raw_response,
        }

    def _task_payload(self, task: dict[str, Any]) -> dict[str, Any]:
        system = str(task.get("system_prompt") or "").strip()
        user = str(task.get("user_prompt") or task.get("input_text") or "").strip()
        options = task.get("options") if isinstance(task.get("options"), dict) else {}
        temperature = options.get("temperature", 0)
        max_tokens = int(options.get("max_tokens", _env_value(self.env_prefix, "MAX_OUTPUT_TOKENS", os.getenv("MAX_OUTPUT_TOKENS", "1600"))))
        tools = task.get("tools") if isinstance(task.get("tools"), list) else None
        response_format = task.get("response_format") if isinstance(task.get("response_format"), dict) else None

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        if self._uses_responses_api(options):
            if not tools:
                tool = {"type": "web_search_preview"} if (options.get("web_search_mode") or self.web_search_mode) == "responses_web_search_preview" else self._responses_web_search_tool(options)
                tools = [tool]
            payload: dict[str, Any] = {
                "model": self.model,
                "input": messages,
                "stream": False,
                "temperature": temperature,
                "max_output_tokens": max_tokens,
                "tools": tools,
            }
            max_tool_calls = _env_int(self.env_prefix, "WEB_SEARCH_MAX_TOOL_CALLS", options.get("max_tool_calls"))
            if max_tool_calls:
                payload["max_tool_calls"] = max_tool_calls
            if response_format:
                payload["response_format"] = response_format
            return payload

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format
        if tools:
            payload["tools"] = tools
        elif options.get("web_search_enabled") and self.web_search_enabled:
            payload["tools"] = [{"type": "web_search"}]
        if max_tokens:
            payload["max_tokens"] = max_tokens
        plugins = self._web_search_plugins()
        if plugins and options.get("web_search_enabled"):
            payload.setdefault("plugins", plugins)
        if options.get("web_search_enabled") and self.web_search_mode == "web_search_options":
            payload["web_search_options"] = _web_search_options(self.env_prefix)
        return payload

    def _payload(self, query: dict, brand_config: dict, options: dict[str, Any] | None = None) -> dict[str, Any]:
        options = options or {}
        if self._uses_responses_api(options):
            return self._responses_payload(query, brand_config, options)

        payload = {
            "model": self.model,
            "messages": self._messages(query, brand_config, options),
            "stream": False,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        plugins = self._web_search_plugins()
        if plugins and options.get("web_search_enabled", self.web_search_enabled):
            payload["plugins"] = plugins
        if options.get("web_search_enabled", self.web_search_enabled):
            mode = options.get("web_search_mode") or self.web_search_mode or "web_search_options"
            if mode == "web_search_options":
                payload["web_search_options"] = _web_search_options(self.env_prefix)
            elif mode == "openai_tool":
                payload["tools"] = [{"type": "web_search"}]
        return payload

    def _responses_payload(self, query: dict, brand_config: dict, options: dict[str, Any] | None = None) -> dict[str, Any]:
        options = options or {}
        messages = self._messages(query, brand_config, options)
        payload: dict[str, Any] = {
            "model": self.model,
            "input": messages,
            "stream": False,
            "temperature": 0,
            "max_output_tokens": int(_env_value(self.env_prefix, "MAX_OUTPUT_TOKENS", os.getenv("MAX_OUTPUT_TOKENS", "1600"))),
        }
        if options.get("web_search_enabled", self.web_search_enabled):
            payload["tools"] = [self._responses_web_search_tool(options)]
            max_tool_calls = _env_int(self.env_prefix, "WEB_SEARCH_MAX_TOOL_CALLS", options.get("max_tool_calls"))
            if max_tool_calls:
                payload["max_tool_calls"] = max_tool_calls
            if (options.get("web_search_mode") or self.web_search_mode) == "responses_web_search_preview":
                payload["tools"] = [{"type": "web_search_preview"}]
        return payload

    def _extract_citations(self, raw_response: dict, message: dict) -> list[dict]:
        citations: list[dict] = []
        citations.extend(_parse_openai_annotation_citations(message.get("annotations")))
        citations.extend(_parse_citations_list(message.get("citations")))

        search_info = message.get("search_info")
        if isinstance(search_info, dict):
            for key in ("sources", "citations", "urls", "references", "results"):
                citations.extend(_parse_citations_list(search_info.get(key)))

        citations.extend(_parse_citations_list(message.get("ref_content")))
        citations.extend(_responses_citations(raw_response))
        return _dedup_citations(citations)

    def _web_search_plugins(self) -> list[dict] | None:
        return None

    def _responses_web_search_tool(self, options: dict[str, Any] | None = None) -> dict[str, Any]:
        options = options or {}
        tool: dict[str, Any] = {"type": "web_search"}
        max_keyword = _env_int(self.env_prefix, "WEB_SEARCH_MAX_KEYWORD", options.get("web_search_max_keyword"))
        if max_keyword:
            tool["max_keyword"] = max_keyword
        limit = _env_int(self.env_prefix, "WEB_SEARCH_LIMIT", options.get("web_search_limit"))
        if limit:
            tool["limit"] = limit
        sources = _env_list(self.env_prefix, "WEB_SEARCH_SOURCES", options.get("web_search_sources"))
        if sources:
            tool["sources"] = sources
        user_location = _web_search_user_location(self.env_prefix, options)
        if user_location:
            tool["user_location"] = user_location
        return tool

    async def _post_with_retry(self, payload: dict[str, Any], options: dict[str, Any] | None = None) -> dict[str, Any]:
        endpoint = self.responses_endpoint if self._uses_responses_api(options) or "input" in payload else self.chat_endpoint
        url = _join_url(self.base_url, endpoint)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(3):
                response: httpx.Response | None = None
                try:
                    response = await client.post(url, headers=headers, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    if not isinstance(data, dict):
                        raise RuntimeError(f"{self.platform} response was not a JSON object.")
                    return data
                except httpx.HTTPStatusError as error:
                    last_error = RuntimeError(_http_retry_error_message(self.platform, error.response, attempt, 3))
                    _log_retry_failure(self.platform, error, error.response, attempt, 3)
                    if attempt < 2:
                        await asyncio.sleep(_retry_delay(attempt, is_rate_limited=error.response.status_code == 429))
                except ValueError as error:
                    last_error = RuntimeError(_json_decode_error_message(response, attempt, 3))
                    _log_retry_failure(self.platform, error, response, attempt, 3)
                    if attempt < 2:
                        await asyncio.sleep(_retry_delay(attempt))
                except (httpx.TimeoutException, httpx.TransportError, RuntimeError) as error:
                    last_error = error
                    _log_retry_failure(self.platform, error, response, attempt, 3)
                    if attempt < 2:
                        await asyncio.sleep(_retry_delay(attempt))
        raise RuntimeError(f"{self.platform} request failed: {last_error}") from last_error

    def _uses_responses_api(self, options: dict[str, Any] | None = None) -> bool:
        options = options or {}
        mode = options.get("web_search_mode") or self.web_search_mode
        enabled = options.get("web_search_enabled", self.web_search_enabled)
        return enabled and mode in {"responses_web_search", "responses_web_search_preview"}

    def _message(self, raw_response: dict) -> dict:
        message = raw_response.get("choices", [{}])[0].get("message", {})
        if isinstance(message, dict) and message.get("content"):
            return message

        content = _responses_text(raw_response)
        if content:
            return {"role": "assistant", "content": content}
        return {}

    def _messages(self, query: dict, brand_config: dict, options: dict[str, Any] | None = None) -> list[dict[str, str]]:
        options = options or {}
        if options.get("blind_mode"):
            return _blind_messages(self.platform, query)
        if options.get("assisted_extraction"):
            return _assisted_extraction_messages(self.platform, query, brand_config, options)
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
5. 不要判断 URL 是否官方或自有，信源归属由后端确定性解析。
        """
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _inspection_round(options: dict[str, Any]) -> str:
    if options.get("blind_mode"):
        return "blind"
    if options.get("assisted_extraction"):
        return "assisted"
    return "single"


def _blind_messages(platform: str, query: dict) -> list[dict[str, str]]:
    system = (
        "你是真实用户问题回答器。你只需要回答用户问题，不要揣测正在评估哪个品牌，"
        "也不要引入未被问题自然触发的品牌上下文。只能返回一个合法 JSON 对象，不要输出 Markdown。"
    )
    user = f"""
用户问题：
{query["query_text"]}

请返回 JSON：
{{
  "answer": "面向用户的真实自然回答，保留完整业务判断",
  "mentioned_brands": [
    {{
      "name": "answer 中自然出现的品牌名",
      "aliases_matched": ["answer 中命中的别名，可为空"],
      "position": 1,
      "mention_context": "explicit_recommendation|standard_listing|incidental_mention|not_mentioned",
      "sentiment": "positive|neutral|negative",
      "evidence": "从 answer 中摘取的一句依据"
    }}
  ],
  "citations": [
    {{
      "url": "只有 answer 中明确出现 URL 或平台返回原生引用时才填写，否则不要编造",
      "domain": "域名",
      "title": "可为空",
      "quoted_text": "该 URL 支撑的回答内容片段；必须来自 answer 或平台明确给出的引用片段",
      "answer_excerpt": "包含该 URL 或该引用判断的 answer 上下文，可为空"
    }}
  ],
  "parse_confidence": "high|medium|low",
  "notes": "可为空"
}}

约束：
1. 不要读取或推断任何本品牌、竞品或别名配置。
2. mentioned_brands 只记录 answer 中自然出现或明确指代的品牌；不要为了评估而补充品牌。
3. 不要为了满足字段而编造引用来源；没有 URL 就返回空 citations。
4. 不要判断 URL 是否官方或自有，信源归属由后端确定性解析。
"""
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _assisted_extraction_messages(platform: str, query: dict, brand_config: dict, options: dict[str, Any]) -> list[dict[str, str]]:
    brand = brand_config["entity_name"]
    aliases = brand_config.get("entity_aliases", [])
    competitors = brand_config.get("competitors", [])
    competitor_names = [item["name"] for item in competitors if item.get("name")]
    natural_answer = str(options.get("natural_answer") or "").strip()
    natural_citations = options.get("natural_citations") or []
    system = (
        "你是 GEO 品牌提及结构化抽取器。你只能基于给定的自然回答和引用做抽取，"
        "不得改写自然回答，不得新增自然回答中没有的品牌、URL 或证据。只能返回一个合法 JSON 对象。"
    )
    user = f"""
巡检平台：{platform}
巡检对象：
- 本品牌：{brand}
- 本品牌别名：{aliases}
- 竞品：{competitor_names}
- 话题：{query["topic"]}
- QuerySet 场景：{query.get("query_pattern") or query.get("intent_type")}

用户问题：
{query["query_text"]}

自然回答：
{natural_answer}

自然回答引用：
{natural_citations}

请返回 JSON：
{{
  "answer": "原样返回自然回答",
  "mentioned_brands": [
    {{
      "name": "自然回答中出现或明确指代的品牌名",
      "aliases_matched": ["命中的别名，可为空"],
      "position": 1,
      "mention_context": "explicit_recommendation|standard_listing|incidental_mention|not_mentioned",
      "sentiment": "positive|neutral|negative",
      "evidence": "从自然回答中摘取的一句依据"
    }}
  ],
  "citations": [
    {{
      "url": "自然回答或自然回答引用中已有的 URL",
      "domain": "域名",
      "title": "可为空",
      "quoted_text": "该 URL 支撑的回答内容片段",
      "answer_excerpt": "包含该 URL 或该引用判断的自然回答上下文，可为空"
    }}
  ],
  "parse_confidence": "high|medium|low",
  "notes": "可为空"
}}

约束：
1. mentioned_brands 只记录自然回答中真实出现或明确指代的品牌。
2. 不要为了满足字段而编造引用来源；没有 URL 就返回空 citations。
3. position 按自然回答中品牌首次出现或推荐顺序排序。
4. 不要判断 URL 是否官方或自有，信源归属由后端确定性解析。
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


def _parse_citations_list(value: object) -> list[dict]:
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


def _dedup_citations(citations: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for citation in citations:
        url = citation.get("url") if isinstance(citation.get("url"), str) else None
        domain = citation.get("domain") if isinstance(citation.get("domain"), str) else None
        key = url or domain or ""
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        result.append(citation)
    return result


def _first_str(obj: dict, keys: list[str]) -> str | None:
    for key in keys:
        value = obj.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _domain_from_url(url: str | None) -> str | None:
    if not isinstance(url, str) or not url.strip():
        return None
    from urllib.parse import urlparse

    netloc = urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def _join_url(base_url: str, endpoint: str) -> str:
    if base_url.endswith(endpoint):
        return base_url
    return f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"


def _web_search_options(env_prefix: str) -> dict:
    return {
        "search_context_size": _env_value(env_prefix, "WEB_SEARCH_CONTEXT_SIZE", "medium").strip() or "medium",
    }


def _responses_text(raw_response: dict) -> str:
    if isinstance(raw_response.get("output_text"), str):
        return raw_response["output_text"].strip()
    parts: list[str] = []
    for output in raw_response.get("output") or []:
        if not isinstance(output, dict):
            continue
        for content in output.get("content") or []:
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
    return "\n".join(parts)


def _responses_citations(raw_response: dict) -> list[dict]:
    """Extract web-search sources from a /responses payload.

    Responses-API replies carry sources in two places the chat-completions
    parsing never reaches: per-message content-part `annotations`
    (`url_citation`) and dedicated web-search output items. Both are scanned
    here so platforms that don't inline URLs into the answer (e.g. 豆包/ARK)
    still surface real citations.
    """
    citations: list[dict] = []
    output = raw_response.get("output")
    if not isinstance(output, list):
        return citations
    for item in output:
        if not isinstance(item, dict):
            continue
        for part in item.get("content") or []:
            if isinstance(part, dict):
                citations.extend(_parse_openai_annotation_citations(part.get("annotations")))
        item_type = str(item.get("type") or "").lower()
        if "search" not in item_type:
            continue
        action = item.get("action") if isinstance(item.get("action"), dict) else {}
        for container in (item, action):
            if not isinstance(container, dict):
                continue
            for key in ("results", "sources", "search_results", "citations", "references", "reference_list"):
                citations.extend(_parse_citations_list(container.get(key)))
    return citations


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        parts = name.split("_", 1)
        if len(parts) == 2:
            value = os.getenv(f"{parts[0].lower()}_{parts[1]}")
    if value is None:
        value = os.getenv(name.lower())
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_value(env_prefix: str, suffix: str, default: str) -> str:
    upper = f"{env_prefix}_{suffix}"
    mixed = f"{env_prefix.lower()}_{suffix}"
    lower = upper.lower()
    value = os.getenv(upper)
    if value is None:
        value = os.getenv(mixed)
    if value is None:
        value = os.getenv(lower)
    return default if value is None else value


def _env_int(env_prefix: str, suffix: str, default: object = None) -> int | None:
    value = _env_value(env_prefix, suffix, "" if default is None else str(default)).strip()
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _env_list(env_prefix: str, suffix: str, default: object = None) -> list[str]:
    value = _env_value(env_prefix, suffix, "" if default is None else str(default)).strip()
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _web_search_user_location(env_prefix: str, options: dict[str, Any]) -> dict[str, str] | None:
    configured = options.get("web_search_user_location")
    if isinstance(configured, dict):
        location = {str(key): str(value) for key, value in configured.items() if value is not None and str(value).strip()}
        return location or None

    country = _env_value(env_prefix, "WEB_SEARCH_COUNTRY", str(options.get("web_search_country") or "")).strip()
    region = _env_value(env_prefix, "WEB_SEARCH_REGION", str(options.get("web_search_region") or "")).strip()
    city = _env_value(env_prefix, "WEB_SEARCH_CITY", str(options.get("web_search_city") or "")).strip()
    if not any((country, region, city)):
        return None
    location: dict[str, str] = {"type": "approximate"}
    if country:
        location["country"] = country
    if region:
        location["region"] = region
    if city:
        location["city"] = city
    return location


def _retry_delay(attempt: int, is_rate_limited: bool = False) -> float:
    if is_rate_limited:
        return min(300.0, 30.0 * (2**attempt))
    return min(60.0, 3.0 * (2**attempt))


def _log_retry_failure(
    platform: str,
    error: Exception,
    response: httpx.Response | None,
    attempt: int,
    max_attempts: int,
) -> None:
    logger.warning(
        "%s request attempt failed: %s",
        platform,
        error,
        extra={
            "platform": platform,
            "attempt": attempt + 1,
            "max_attempts": max_attempts,
            "http_status": getattr(response, "status_code", None),
            "content_type": _response_content_type(response),
            "response_body": _response_body_excerpt(response),
        },
    )


def _http_retry_error_message(platform: str, response: httpx.Response, attempt: int, max_attempts: int) -> str:
    return (
        f"HTTP status error. HTTP status={response.status_code}, "
        f"content_type={_response_content_type(response) or 'unknown'}, "
        f"body={_quote_body(_response_body_excerpt(response))}, "
        f"attempt={attempt + 1}/{max_attempts}: {_http_error_detail(platform, response)}"
    )


def _json_decode_error_message(response: httpx.Response | None, attempt: int, max_attempts: int) -> str:
    status = getattr(response, "status_code", None)
    return (
        f"JSON decode error. HTTP status={status if status is not None else 'unknown'}, "
        f"body={_quote_body(_response_body_excerpt(response))}, "
        f"attempt={attempt + 1}/{max_attempts}"
    )


def _response_content_type(response: httpx.Response | None) -> str | None:
    if response is None:
        return None
    return response.headers.get("content-type")


def _response_body_excerpt(response: httpx.Response | None, limit: int = 300) -> str:
    if response is None:
        return ""
    return response.text[:limit]


def _quote_body(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _http_error_message(platform: str, error: httpx.HTTPStatusError) -> str:
    return _http_error_detail(platform, error.response)


def _http_error_detail(platform: str, response: httpx.Response) -> str:
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
