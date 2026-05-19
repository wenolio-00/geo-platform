from __future__ import annotations

import json
import re
from urllib.parse import urlparse


def brand_terms(brand_config: dict) -> list[str]:
    terms = [brand_config.get("entity_name"), *brand_config.get("entity_aliases", [])]
    for competitor in brand_config.get("competitors", []):
        terms.append(competitor.get("name"))
        terms.extend(competitor.get("aliases", []))
    return [str(term).strip() for term in terms if str(term).strip()]


def parse_json_answer(raw_content: str, brand_config: dict) -> dict:
    parsed = _extract_json(raw_content)
    if parsed:
        return _normalize_parsed(parsed, raw_content)
    return _fallback_parse(raw_content, brand_config)


def _extract_json(raw_content: str) -> dict | None:
    text = raw_content.strip()
    candidates = [text]
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    if fenced:
        candidates.insert(0, fenced.group(1))
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start : end + 1])

    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _normalize_parsed(parsed: dict, raw_content: str) -> dict:
    answer = parsed.get("answer")
    mentioned = parsed.get("mentioned_brands")
    citations = parsed.get("citations")
    normalized = {
        "answer": answer if isinstance(answer, str) and answer.strip() else raw_content,
        "mentioned_brands": _normalize_mentions(mentioned),
        "citations": _normalize_citations(citations),
        "parse_confidence": parsed.get("parse_confidence") if parsed.get("parse_confidence") in {"high", "medium", "low"} else "high",
        "notes": parsed.get("notes") if isinstance(parsed.get("notes"), str) else None,
    }
    for key, value in parsed.items():
        normalized.setdefault(key, value)
    return normalized


def _normalize_mentions(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    rows = []
    for item in value:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        context = item.get("mention_context") or "standard_listing"
        if context not in {"explicit_recommendation", "standard_listing", "incidental_mention", "not_mentioned"}:
            context = "standard_listing"
        sentiment = item.get("sentiment") or "neutral"
        if sentiment not in {"positive", "neutral", "negative"}:
            sentiment = "neutral"
        position = item.get("position")
        try:
            position = int(position) if position is not None else None
        except (TypeError, ValueError):
            position = None
        rows.append(
            {
                "name": str(item["name"]).strip(),
                "aliases_matched": [str(alias).strip() for alias in item.get("aliases_matched", []) if str(alias).strip()]
                if isinstance(item.get("aliases_matched"), list)
                else [],
                "position": position,
                "mention_context": context,
                "sentiment": sentiment,
                "evidence": item.get("evidence") if isinstance(item.get("evidence"), str) else None,
            }
        )
    return rows


def _normalize_citations(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    rows = []
    for item in value:
        if not isinstance(item, dict):
            continue
        url = item.get("url") if isinstance(item.get("url"), str) else None
        domain = item.get("domain") if isinstance(item.get("domain"), str) else None
        if not domain and url:
            domain = urlparse(url).netloc
        if not domain:
            continue
        rows.append(
            {
                "url": url,
                "domain": domain.lower().replace("www.", ""),
                "title": item.get("title") if isinstance(item.get("title"), str) else None,
                "is_official": item.get("is_official") if isinstance(item.get("is_official"), bool) else None,
                "quoted_text": _first_text(item, ["quoted_text", "evidence", "snippet", "content"]),
                "answer_excerpt": _first_text(item, ["answer_excerpt", "context"]),
            }
        )
    return rows


def _first_text(item: dict, keys: list[str]) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _fallback_parse(raw_content: str, brand_config: dict) -> dict:
    mentions = []
    position = 1
    for term in brand_terms(brand_config):
        if term and term.lower() in raw_content.lower():
            mentions.append(
                {
                    "name": term,
                    "aliases_matched": [term],
                    "position": position,
                    "mention_context": "standard_listing",
                    "sentiment": "neutral",
                    "evidence": None,
                }
            )
            position += 1
    return {
        "answer": raw_content,
        "mentioned_brands": mentions,
        "citations": [],
        "parse_confidence": "low",
        "notes": "Provider did not return valid JSON; parsed conservatively from the raw answer.",
    }
