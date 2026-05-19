from __future__ import annotations

from typing import Any

from service.platform_clients.openai_compatible import OpenAICompatibleClient


class DoubaoClient(OpenAICompatibleClient):
    def __init__(self) -> None:
        super().__init__(
            "豆包",
            "DOUBAO",
            "https://ark.cn-beijing.volces.com/api/v3",
            "doubao-seed-2-0-mini-260215",
        )

    def _web_search_plugins(self) -> list[dict]:
        return [{"type": "web_search", "web_search": {"searcher": {"type": "web_searcher"}}}]

    def _extract_citations(self, raw_response: dict, message: dict) -> list[dict]:
        citations: list[dict] = []

        # Try message.citations (ARK API standard)
        citations.extend(_parse_citations_list(message.get("citations")))

        # Try message.search_info
        search_info = message.get("search_info")
        if isinstance(search_info, dict):
            citations.extend(_parse_search_info(search_info))

        # Try message.ref_content
        ref_content = message.get("ref_content")
        if isinstance(ref_content, list):
            for item in ref_content:
                if isinstance(item, dict):
                    url = _first_str(item, ["url", "link"])
                    domain = _first_str(item, ["domain"]) or _domain_from_url(url)
                    citations.append({
                        "url": url,
                        "domain": domain,
                        "title": _first_str(item, ["title", "name"]),
                        "is_official": None,
                        "quoted_text": _first_str(item, ["quoted_text", "snippet", "content"]),
                        "answer_excerpt": _first_str(item, ["answer_excerpt", "context"]),
                    })

        return _dedup_citations(citations)


def _parse_citations_list(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    results: list[dict] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        url = _first_str(item, ["url", "link", "source_url"])
        domain = _first_str(item, ["domain", "source"]) or _domain_from_url(url)
        results.append({
            "url": url,
            "domain": domain,
            "title": _first_str(item, ["title", "name"]),
            "is_official": None,
            "quoted_text": _first_str(item, ["quoted_text", "snippet", "content", "text"]),
            "answer_excerpt": _first_str(item, ["answer_excerpt", "context"]),
        })
    return results


def _parse_search_info(info: dict) -> list[dict]:
    results: list[dict] = []
    for key in ("sources", "citations", "urls", "references"):
        value = info.get(key)
        if isinstance(value, list):
            results.extend(_parse_citations_list(value))
    # Try top-level URL fields
    for url_key in ("url", "source_url", "link"):
        url = _first_str(info, [url_key])
        if url:
            results.append({
                "url": url,
                "domain": _domain_from_url(url),
                "title": _first_str(info, ["title", "name"]),
                "is_official": None,
                "quoted_text": _first_str(info, ["snippet", "quoted_text"]),
                "answer_excerpt": None,
            })
            break
    return results


def _first_str(obj: dict, keys: list[str]) -> str | None:
    for key in keys:
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _domain_from_url(url: str | None) -> str | None:
    if not isinstance(url, str) or not url.strip():
        return None
    from urllib.parse import urlparse
    netloc = urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def _dedup_citations(citations: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for c in citations:
        url = c.get("url") if isinstance(c.get("url"), str) else None
        domain = c.get("domain") if isinstance(c.get("domain"), str) else None
        key = url or domain or ""
        if key and key not in seen:
            seen.add(key)
            result.append(c)
        elif not key:
            result.append(c)
    return result