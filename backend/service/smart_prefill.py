from __future__ import annotations

import re
from typing import Any

import httpx

from service.llm_tasks import invoke_json_task


SMART_PREFILL_SYSTEM_PROMPT = (
    "你是品牌信息结构化提取助手。"
    "请根据用户提供的官网简介、资料摘要或原始文本，提取品牌配置所需字段。"
    "只能返回一个合法 JSON 对象，不要输出 Markdown。"
)

_FETCH_TIMEOUT = 15
_MAX_TEXT_CHARS = 6000


def _extract_text_from_html(html: str) -> str:
    # pull meta description / keywords before stripping tags
    parts: list[str] = []
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    if title_m:
        parts.append(title_m.group(1).strip())

    for m in re.finditer(r"<meta\b[^>]+>", html, re.I):
        tag = m.group(0)
        name_m = re.search(r'name=["\']([^"\']+)["\']', tag, re.I)
        content_m = re.search(r'content=["\']([^"\']+)["\']', tag, re.I)
        if name_m and content_m and name_m.group(1).lower() in ("description", "keywords"):
            parts.append(content_m.group(1).strip())

    # strip script / style / noscript blocks
    clean = re.sub(r"<(script|style|noscript)\b[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    # strip remaining tags
    clean = re.sub(r"<[^>]+>", " ", clean)
    # decode common entities
    clean = clean.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    # collapse whitespace
    clean = re.sub(r"\s{2,}", " ", clean).strip()
    if clean:
        parts.append(clean)

    combined = " ".join(parts)
    return re.sub(r"\s{2,}", " ", combined).strip()[:_MAX_TEXT_CHARS]


async def _fetch_website_text(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=_FETCH_TIMEOUT) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        html = resp.text

    return _extract_text_from_html(html)


async def smart_prefill_brand_config(payload: dict[str, Any]) -> dict[str, Any]:
    source_text = str(payload.get("source_text") or "").strip()
    website_url = str(payload.get("website_url") or "").strip()

    if not source_text and website_url:
        try:
            source_text = await _fetch_website_text(website_url)
        except Exception as exc:
            source_text = _website_fetch_fallback_text(website_url, exc)

    if not source_text:
        raise ValueError("请提供 source_text 或 website_url。")

    brief = {
        "source_url": payload.get("source_url"),
        "source_name": payload.get("source_name"),
        "source_text": source_text,
        "constraints": {
            "language": "zh-CN",
            "max_topics": 5,
            "max_competitors": 8,
        },
    }
    result = await invoke_json_task(
        task_type="prefill",
        payload=payload,
        provider=payload.get("llm_provider"),
        system_prompt=SMART_PREFILL_SYSTEM_PROMPT,
        user_prompt=_smart_prefill_user_prompt(brief),
    )
    parsed = result.get("parsed") or {}
    response = {
        "entity_name": _text(parsed.get("entity_name")),
        "entity_aliases": _clean_list(parsed.get("entity_aliases")),
        "industry_segments": _clean_list(parsed.get("industry_segments")),
        "topics": _normalize_topics(parsed.get("topics")),
        "competitors": _normalize_competitors(parsed.get("competitors")),
        "llm_provider": result.get("provider"),
        "web_search_enabled": result.get("web_search_enabled", False),
        "web_search_mode": result.get("web_search_mode"),
    }
    if result.get("used_fallback"):
        response["quality_warning"] = {
            "used_fallback": True,
            "primary_provider": result.get("primary_provider"),
            "fallback_provider": result.get("provider"),
            "fallback_reason": result.get("fallback_reason"),
        }
    return response


def _smart_prefill_user_prompt(brief: dict[str, Any]) -> str:
    return f"""
请从以下资料中抽取品牌配置字段。

资料来源：{brief.get('source_name') or brief.get('source_url') or '未命名资料'}
原始内容：
{brief.get('source_text')}

请返回 JSON：
{{
  "entity_name": "企业全称",
  "entity_aliases": ["品牌简称", "英文名"],
  "industry_segments": ["行业细分1", "行业细分2"],
  "topics": [
    {{
      "topic_name": "话题全称",
      "business_line": "话题简称",
      "priority": 1,
      "pain_point": "用户通用痛点",
      "goal": "业务目标"
    }}
  ],
  "competitors": [
    {{
      "name": "竞品名称",
      "aliases": ["竞品别名"],
      "business_line": "相关话题",
      "category": "竞品类别"
    }}
  ]
}}

要求：
1. 只提取资料中明确支持或可高置信推断的信息。
2. 不确定时返回空数组或空字符串，不要编造。
3. topics 最多返回 5 条，competitors 最多返回 8 条。
4. 输出必须是合法 JSON 对象。
"""


def _website_fetch_fallback_text(website_url: str, error: Exception) -> str:
    error_text = str(error).strip() or type(error).__name__
    return (
        f"官网 URL：{website_url}\n"
        f"页面正文抓取失败：{error_text}\n"
        "请优先依据官网 URL、域名、品牌名线索和可用网络搜索能力推断品牌配置字段。"
        "无法确认的信息返回空数组或空字符串，不要编造。"
    )


def _normalize_topics(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(value[:5], start=1):
        if not isinstance(item, dict):
            continue
        topic_name = _text(item.get("topic_name"))
        business_line = _text(item.get("business_line"))
        if not topic_name and not business_line:
            continue
        rows.append(
            {
                "topic_name": topic_name,
                "business_line": business_line,
                "priority": _int(item.get("priority"), index),
                "pain_point": _nullable_text(item.get("pain_point")),
                "goal": _nullable_text(item.get("goal")),
            }
        )
    return rows


def _normalize_competitors(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        name = _text(item.get("name"))
        if not name:
            continue
        rows.append(
            {
                "name": name,
                "aliases": _clean_list(item.get("aliases")),
                "business_line": _nullable_text(item.get("business_line")) or "",
                "category": _nullable_text(item.get("category")) or "",
            }
        )
    return rows


def _clean_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := _text(item))]


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _nullable_text(value: object) -> str | None:
    text = _text(value)
    return text or None


def _int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
