from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse
from uuid import uuid4


REPORT_TEMPLATE_VERSION = "geo_report_generator_goose_yellow_20260509"
REPORT_SCHEMA_VERSION = "report_data_schema_v1"


def aggregate_report(
    run: dict,
    brand_config: dict,
    queryset: dict,
    all_results: list[dict],
) -> dict:
    now = datetime.now(timezone.utc)
    completed_results = [r for r in all_results if r.get("status") == "completed"]
    failed_results = [r for r in all_results if r.get("status") == "failed"]
    total = len(completed_results)
    platforms_requested = run.get("platforms_requested") or ["claude"]
    platforms_inspected = list(dict.fromkeys(r["platform"] for r in completed_results))
    platforms_failed = list(dict.fromkeys(r["platform"] for r in failed_results))
    expected_samples = total + len(failed_results)
    completion_rate = _round(total / expected_samples, 4) if expected_samples else 0
    failure_types = Counter(r.get("error_type") or "provider_error" for r in failed_results)

    competitor_names = [item["name"] for item in brand_config.get("competitors", []) if item.get("name")]
    brands = [brand_config["entity_name"], *competitor_names]
    brand_stats = {name: {"mentions": 0, "positions": []} for name in brands}
    brand_visibility_mentions = Counter()
    platform_brand_stats: dict[str, dict[str, dict]] = {}
    platform_sample_counts = Counter()
    platform_visibility_sample_counts = Counter()
    platform_visibility_mentions = Counter()
    platform_sentiments = defaultdict(Counter)
    self_sentiments = Counter()
    business_line_lookup = _business_line_lookup(brand_config)
    configured_business_lines = _configured_business_lines(brand_config)
    topic_sentiments = defaultdict(Counter)
    for business_line in configured_business_lines:
        topic_sentiments[business_line] = Counter()
    topic_platform_stats: dict[tuple[str, str], dict] = {}
    source_counts = Counter()
    official_source_counts = Counter()
    source_url_rows: dict[str, dict] = {}
    competitor_only = 0
    visibility_samples = 0
    visibility_mentions = 0
    query_text_by_id = {
        str(query.get("query_id")): query.get("query_text")
        for query in queryset.get("queries", [])
        if isinstance(query, dict) and query.get("query_id")
    }

    for result in completed_results:
        platform = result.get("platform", "unknown")
        platform_sample_counts[platform] += 1
        query_text = result.get("query_text") or query_text_by_id.get(str(result.get("query_id")))
        counts_for_visibility = not _query_mentions_self(query_text, brand_config)
        business_line = _business_line_for_result(result.get("topic"), business_line_lookup)
        topic_platform = None
        if business_line:
            topic_platform = topic_platform_stats.setdefault(
                (business_line, platform),
                {
                    "samples": 0,
                    "visibility_samples": 0,
                    "brand_mentions": Counter(),
                    "brand_visibility_mentions": Counter(),
                },
            )
            topic_platform["samples"] += 1
        if counts_for_visibility:
            visibility_samples += 1
            platform_visibility_sample_counts[platform] += 1
            if topic_platform:
                topic_platform["visibility_samples"] += 1
        if platform not in platform_brand_stats:
            platform_brand_stats[platform] = {name: {"mentions": 0, "positions": []} for name in brands}
        mentions = result.get("parsed", {}).get("mentioned_brands", [])
        mentioned_self = False
        mentioned_competitor = False
        seen_in_sample = set()

        for mention in mentions:
            matched = _canonical_brand(mention.get("name"), brand_config, competitor_names)
            if not matched or matched in seen_in_sample:
                continue
            seen_in_sample.add(matched)
            brand_stats.setdefault(matched, {"mentions": 0, "positions": []})
            brand_stats[matched]["mentions"] += 1
            platform_brand_stats[platform].setdefault(matched, {"mentions": 0, "positions": []})
            platform_brand_stats[platform][matched]["mentions"] += 1
            if mention.get("position"):
                brand_stats[matched]["positions"].append(mention["position"])
                platform_brand_stats[platform][matched]["positions"].append(mention["position"])
            if topic_platform:
                topic_platform["brand_mentions"][matched] += 1
            if counts_for_visibility:
                brand_visibility_mentions[matched] += 1
                if topic_platform:
                    topic_platform["brand_visibility_mentions"][matched] += 1
            if matched == brand_config["entity_name"]:
                mentioned_self = True
                self_sentiments[mention.get("sentiment") or "neutral"] += 1
                platform_sentiments[platform][mention.get("sentiment") or "neutral"] += 1
                if business_line:
                    topic_sentiments[business_line][mention.get("sentiment") or "neutral"] += 1
            elif matched in competitor_names:
                mentioned_competitor = True

        if not mentioned_self and mentioned_competitor:
            competitor_only += 1
        if counts_for_visibility and mentioned_self:
            visibility_mentions += 1
            platform_visibility_mentions[platform] += 1

        for citation in result.get("parsed", {}).get("citations", []):
            domain = citation.get("domain")
            if not domain:
                continue
            source_counts[domain] += 1
            if citation.get("is_official") is True:
                official_source_counts[domain] += 1
            _collect_source_reference(source_url_rows, result, citation)

        if business_line:
            topic_sentiments.setdefault(business_line, Counter())

    self_stats = brand_stats.get(brand_config["entity_name"], {"mentions": 0, "positions": []})
    avg_rank = _round(sum(self_stats["positions"]) / len(self_stats["positions"]), 2) if self_stats["positions"] else None
    visibility = _round(visibility_mentions / visibility_samples) if visibility_samples else 0
    sentiment_score = _sentiment_score(self_sentiments)
    ai_recommend_score = _round(visibility * sentiment_score * 100, 2)
    own_citations = sum(official_source_counts.values())
    platforms_rows = _build_platforms(
        platform_brand_stats,
        platform_sample_counts,
        platform_visibility_sample_counts,
        platform_visibility_mentions,
        platform_sentiments,
        brand_config["entity_name"],
    )

    report = {
        "meta": {
            "report_id": f"report_{uuid4().hex[:12]}",
            "contract_version": "report_data_v1",
            "template_version": REPORT_TEMPLATE_VERSION,
            "brand_name": brand_config["entity_name"],
            "brand_tagline": _brand_tagline(brand_config),
            "report_date": now.date().isoformat(),
            "generated_at": now.isoformat(),
            "total_queries": len(queryset.get("queries", [])),
            "total_competitors": len(competitor_names),
        },
        "lineage": {
            "brand_config_id": brand_config["brand_config_id"],
            "entity_id": brand_config["entity_id"],
            "queryset_id": queryset["queryset_id"],
            "queryset_version": queryset["queryset_version"],
            "parent_queryset_id": queryset.get("parent_queryset_id"),
            "inspection_batch_id": run["inspection_batch_id"],
            "inspection_started_at": run.get("inspection_started_at"),
            "inspection_completed_at": run.get("inspection_completed_at"),
            "aggregation_version": "report_aggregation_v2",
            "queryset_strategy": run["queryset_strategy"],
            "queryset_source": run.get("queryset_source"),
            "queryset_policy": run.get("queryset_policy"),
            "queryset_governance": queryset.get("governance"),
            "inspection_mode": run["inspection_mode"],
            "platforms_requested": platforms_requested,
            "llm_provider": "claude",
            "web_search_enabled": run.get("web_search_enabled", True),
            "web_search_mode": (run.get("llm_options") or {}).get("web_search_mode") or "responses_web_search",
            "llm_options": {**(run.get("llm_options") or {}), "web_search_mode": (run.get("llm_options") or {}).get("web_search_mode") or "responses_web_search"},
            "matrix_api_request_id": queryset.get("matrix_api_request_id"),
        },
        "audit": {
            "missing_fields": [],
            "empty_sections": [],
            "truncated": [],
            "validation_errors": [],
            "schema_version": REPORT_SCHEMA_VERSION,
            "source": "api",
            "raw_results_persisted": True,
            "platforms_inspected": platforms_inspected,
            "platforms_failed": platforms_failed,
            "inspection_failures_count": len(failed_results),
            "expected_samples": expected_samples,
            "completed_samples": total,
            "missing_samples": expected_samples - total,
            "sample_completion_rate": completion_rate,
            "failure_types": dict(failure_types),
            "inspection_quality_gate": run.get("inspection_quality_gate"),
            "visibility_eligible_samples": visibility_samples,
        },
        "executive_summary": _summary(brand_config["entity_name"], visibility, avg_rank, ai_recommend_score, total),
        "global": {
            "rank": avg_rank,
            "visibility": visibility,
            "sentiment_score": sentiment_score,
            "ai_recommend_score": ai_recommend_score,
            "own_citations": own_citations,
            "competitor_suppression_rate": _round(competitor_only / total) if total else 0,
            "summary_text": _summary(brand_config["entity_name"], visibility, avg_rank, ai_recommend_score, total),
        },
        "competitor_ranking": _competitor_ranking(brand_stats, total, brand_config["entity_name"], visibility_samples, brand_visibility_mentions),
        "topic_platform_visibility": _topic_platform_visibility(topic_platform_stats, brands, brand_config["entity_name"]),
        "platforms": platforms_rows,
        "sources": [
            {
                "domain": domain,
                "type": "自有" if official_source_counts[domain] else "第三方",
                "count": count,
                "is_cited": True,
                "is_official": bool(official_source_counts[domain]),
            }
            for domain, count in source_counts.most_common()
        ],
        "source_references": _source_reference_rows(source_url_rows),
        "source_gap": [],
        "sentiment": _sentiment_rates(self_sentiments),
        "topics": _topic_rows(topic_sentiments),
        "optimization_recommendations": _recommendations(visibility, own_citations),
        "retest_plan": {
            "next_queryset_strategy": "rule_matrix_v1",
            "next_inspection_mode": "multi_platform_live_v1",
            "recommended_interval_days": 7,
        },
        "brand_config": {
            **brand_config,
            "queries": queryset.get("queries", []),
            "queries_count": len(queryset.get("queries", [])),
        },
        "insights": _insights(brand_config["entity_name"], visibility, avg_rank, own_citations, platforms_inspected),
    }
    for section in ["sources", "source_references", "source_gap", "insights", "topics"]:
        if not report[section]:
            report["audit"]["empty_sections"].append(section)
    return report


def _collect_source_reference(rows: dict[str, dict], result: dict, citation: dict) -> None:
    url = _normalize_url(citation.get("url"))
    if not url:
        return
    domain = _normalize_domain(citation.get("domain")) or _domain_from_url(url)
    if not domain:
        return
    row = rows.setdefault(
        url,
        {
            "url": url,
            "domain": domain,
            "title": citation.get("title"),
            "type": "自有" if citation.get("is_official") is True else "第三方",
            "is_official": citation.get("is_official") is True,
            "references": [],
        },
    )
    if not row.get("title") and citation.get("title"):
        row["title"] = citation.get("title")
    if citation.get("is_official") is True:
        row["is_official"] = True
        row["type"] = "自有"
    answer = result.get("parsed", {}).get("answer") or result.get("raw_answer") or ""
    row["references"].append(
        {
            "inspection_id": result.get("inspection_id"),
            "platform": result.get("platform"),
            "model": result.get("model"),
            "query_id": result.get("query_id"),
            "query_text": result.get("query_text"),
            "query_pattern": result.get("query_pattern"),
            "query_layer": result.get("query_layer"),
            "topic": result.get("topic"),
            "intent_type": result.get("intent_type"),
            "quoted_text": _clean_text(citation.get("quoted_text")) or _clean_text(citation.get("answer_excerpt")) or _answer_excerpt(answer, citation),
            "answer_excerpt": _clean_text(citation.get("answer_excerpt")) or _answer_excerpt(answer, citation),
        }
    )


def _source_reference_rows(rows: dict[str, dict]) -> list[dict]:
    output = []
    for row in rows.values():
        references = row.get("references") or []
        output.append(
            {
                **row,
                "citation_count": len(references),
                "references": references,
            }
        )
    return sorted(output, key=lambda item: (-item["citation_count"], item["url"]))[:6]


def _normalize_url(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        return None
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parsed.path.rstrip("/") if parsed.path not in {"", "/"} else ""
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def _normalize_domain(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    domain = value.strip().lower()
    return domain[4:] if domain.startswith("www.") else domain


def _domain_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    return _normalize_domain(parsed.netloc)


def _clean_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    return text or None


def _answer_excerpt(answer: object, citation: dict) -> str | None:
    text = _clean_text(answer)
    if not text:
        return None
    needles = [citation.get("url"), citation.get("domain")]
    for needle in needles:
        if not isinstance(needle, str) or not needle.strip():
            continue
        index = text.find(needle.strip())
        if index >= 0:
            start = max(0, index - 120)
            end = min(len(text), index + len(needle.strip()) + 120)
            return text[start:end]
    return text[:240]


def _query_mentions_self(query_text: object, brand_config: dict) -> bool:
    if not isinstance(query_text, str) or not query_text.strip():
        return False
    text = query_text.casefold()
    for term in _self_terms(brand_config):
        normalized = str(term).strip().casefold()
        if normalized and normalized in text:
            return True
    return False


def _build_platforms(
    platform_brand_stats: dict,
    platform_sample_counts: Counter,
    platform_visibility_sample_counts: Counter,
    platform_visibility_mentions: Counter,
    platform_sentiments: dict,
    self_name: str,
) -> list[dict]:
    rows = []
    for platform, stats in platform_brand_stats.items():
        p_stats = stats.get(self_name, {"mentions": 0, "positions": []})
        p_total = platform_sample_counts[platform]
        mention_rate = _round(p_stats["mentions"] / p_total) if p_total else 0
        avg_pos = _round(sum(p_stats["positions"]) / len(p_stats["positions"]), 2) if p_stats["positions"] else None
        visibility_samples = platform_visibility_sample_counts[platform]
        vis = _round(platform_visibility_mentions[platform] / visibility_samples) if visibility_samples else 0
        rows.append(
            {
                "name": platform,
                "samples": p_total,
                "mention_rate": mention_rate,
                "visibility": vis,
                "rank": avg_pos,
                "ai_recommend_score": _round(vis * _sentiment_score(platform_sentiments[platform]) * 100, 2),
                "competitor_rank": _self_rank(stats, p_total, self_name),
            }
        )
    return rows


def _self_terms(brand_config: dict) -> list[str]:
    return [brand_config["entity_name"], *brand_config.get("entity_aliases", [])]


def _canonical_brand(name: str | None, brand_config: dict, competitors: list[str]) -> str | None:
    if not name:
        return None
    text = name.lower()
    for term in _self_terms(brand_config):
        if term and (text == term.lower() or term.lower() in text or text in term.lower()):
            return brand_config["entity_name"]
    for competitor in brand_config.get("competitors", []):
        terms = [competitor.get("name"), *competitor.get("aliases", [])]
        if any(term and (text == term.lower() or term.lower() in text or text in term.lower()) for term in terms):
            return competitor["name"]
    if name in competitors:
        return name
    return None


def _round(value: float, decimals: int = 4) -> float:
    return round(float(value), decimals)


def _sentiment_score(counter: Counter) -> float:
    total = sum(counter.values())
    if total <= 0:
        return 0
    return _round((counter["positive"] * 1 + counter["neutral"] * 0.5 + counter["negative"] * 0.1) / total)


def _sentiment_rates(counter: Counter) -> dict:
    total = sum(counter.values())
    if total <= 0:
        return {"positive_rate": 0, "neutral_rate": 0, "negative_rate": 0}
    return {
        "positive_rate": _round(counter["positive"] / total),
        "neutral_rate": _round(counter["neutral"] / total),
        "negative_rate": _round(counter["negative"] / total),
    }


def _competitor_ranking(
    stats: dict,
    total: int,
    self_name: str,
    visibility_total: int | None = None,
    visibility_mentions: Counter | None = None,
) -> list[dict]:
    rows = []
    for name, values in stats.items():
        rows.append(
            {
                "name": name,
                "mention_rate": _round(values["mentions"] / total) if total else 0,
                "visibility": _round((visibility_mentions or Counter())[name] / visibility_total) if visibility_total else 0,
                "is_self": name == self_name,
            }
        )
    return _sort_brand_rows(rows)


def _self_rank(stats: dict, total: int, self_name: str) -> int | None:
    ranking = _competitor_ranking(stats, total, self_name)
    for index, row in enumerate(ranking, start=1):
        if row["name"] == self_name:
            return index
    return None


def _sort_brand_rows(rows: list[dict]) -> list[dict]:
    return sorted(
        rows,
        key=lambda row: (
            -(row.get("visibility") or 0),
            -(row.get("mention_rate") or 0),
            str(row.get("name") or ""),
        ),
    )


def _topic_platform_visibility(topic_platform_stats: dict[tuple[str, str], dict], brands: list[str], self_name: str) -> list[dict]:
    by_topic: dict[str, list[dict]] = defaultdict(list)
    for (topic, platform), stats in topic_platform_stats.items():
        samples = stats["samples"]
        visibility_samples = stats["visibility_samples"]
        competitors = []
        for name in brands:
            mention_rate = _round(stats["brand_mentions"][name] / samples) if samples else 0
            visibility = _round(stats["brand_visibility_mentions"][name] / visibility_samples) if visibility_samples else 0
            competitors.append(
                {
                    "name": name,
                    "visibility": visibility,
                    "mention_rate": mention_rate,
                    "is_self": name == self_name,
                }
            )
        ranked = []
        for index, row in enumerate(_sort_brand_rows(competitors), start=1):
            ranked.append({**row, "rank": index})
        self_row = next((row for row in ranked if row["is_self"]), None)
        by_topic[topic].append(
            {
                "platform": platform,
                "samples": samples,
                "visibility_eligible_samples": visibility_samples,
                "visibility": self_row["visibility"] if self_row else 0,
                "competitor_rank": self_row["rank"] if self_row else None,
                "competitors": ranked,
            }
        )

    return [
        {
            "topic": topic,
            "platforms": sorted(platforms, key=lambda row: (-(row.get("visibility") or 0), str(row.get("platform") or ""))),
        }
        for topic, platforms in sorted(by_topic.items(), key=lambda item: item[0])
    ]


def _topic_rows(topic_sentiments: dict) -> list[dict]:
    rows = []
    for topic, counter in topic_sentiments.items():
        total = sum(counter.values())
        if total <= 0:
            rows.append({"name": topic, "positive": 0, "neutral": 0, "negative": 0, "change": "flat"})
        else:
            rows.append(
                {
                    "name": topic,
                    "positive": round(counter["positive"] / total * 100),
                    "neutral": round(counter["neutral"] / total * 100),
                    "negative": round(counter["negative"] / total * 100),
                    "change": "flat",
                }
            )
    return rows


def _configured_business_lines(brand_config: dict) -> list[str]:
    values = []
    for item in brand_config.get("topics", []):
        if not isinstance(item, dict):
            continue
        business_line = str(item.get("business_line") or "").strip()
        topic_name = str(item.get("topic_name") or "").strip()
        value = business_line or topic_name
        if value:
            values.append(value)
    return list(dict.fromkeys(values))


def _business_line_lookup(brand_config: dict) -> dict[str, str]:
    lookup = {}
    for item in brand_config.get("topics", []):
        if not isinstance(item, dict):
            continue
        business_line = str(item.get("business_line") or "").strip()
        topic_name = str(item.get("topic_name") or "").strip()
        canonical = business_line or topic_name
        if not canonical:
            continue
        for alias in (business_line, topic_name):
            if alias:
                lookup[alias] = canonical
    return lookup


def _business_line_for_result(topic: object, lookup: dict[str, str]) -> str | None:
    value = str(topic or "").strip()
    if not value:
        return None
    if not lookup:
        return value
    return lookup.get(value)


def _brand_tagline(brand_config: dict) -> str | None:
    topics = [item.get("topic_name") for item in brand_config.get("topics", []) if item.get("topic_name")]
    return " / ".join(topics[:2]) if topics else None


def _summary(brand: str, visibility: float, avg_rank: float | None, score: float, total: int) -> str:
    rank_text = f"平均位次 {avg_rank}" if avg_rank else "尚未形成稳定位次"
    return f"本次基于多平台真实 AI 回答完成 {total} 条查询巡检，{brand} 可见度为 {visibility:.1%}，{rank_text}，AI 推荐度为 {score:.1f}。"


def _insights(brand: str, visibility: float, avg_rank: float | None, own_citations: int, platforms: list[str]) -> list[dict]:
    rows = []
    if visibility < 0.5:
        rows.append({"priority": "P0", "text": f"{brand} 在本次真实回答中的出现比例低于 50%，需要补强核心场景下的实体识别和选型内容。"})
    if avg_rank and avg_rank > 2:
        rows.append({"priority": "P1", "text": f"{brand} 被提及时平均位次为 {avg_rank}，推荐顺序弱于理想阈值，需要强化差异化证据。"})
    if own_citations == 0:
        rows.append({"priority": "P1", "text": "本次 AI 回答未产生可归因为品牌自有信源的引用，官网、案例页和 FAQ 的可引用性仍需提升。"})
    if len(platforms) > 1:
        rows.append({"priority": "P2", "text": f"本次覆盖 {len(platforms)} 个平台：{', '.join(platforms)}。跨平台一致性需持续监测。"})
    return rows


def _recommendations(visibility: float, own_citations: int) -> list[dict]:
    rows = []
    if visibility < 0.5:
        rows.append({"priority": "P0", "title": "补齐核心选型问答", "text": "围绕低可见度话题发布明确的供应商定位、适用行业、能力边界和客户证据。"})
    if own_citations == 0:
        rows.append({"priority": "P1", "title": "增强自有信源", "text": "将产品页、案例页、FAQ 和白皮书改造成更容易被 AI 摘取的事实型内容。"})
    return rows
