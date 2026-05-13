from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
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
    platforms_requested = run.get("platforms_requested") or ["DeepSeek"]
    platforms_inspected = list(dict.fromkeys(r["platform"] for r in completed_results))
    platforms_failed = list(dict.fromkeys(r["platform"] for r in failed_results))
    expected_samples = total + len(failed_results)

    competitor_names = [item["name"] for item in brand_config.get("competitors", []) if item.get("name")]
    brands = [brand_config["entity_name"], *competitor_names]
    brand_stats = {name: {"mentions": 0, "positions": []} for name in brands}
    platform_brand_stats: dict[str, dict[str, dict]] = {}
    platform_sample_counts = Counter()
    platform_sentiments = defaultdict(Counter)
    self_sentiments = Counter()
    business_line_lookup = _business_line_lookup(brand_config)
    configured_business_lines = _configured_business_lines(brand_config)
    topic_sentiments = defaultdict(Counter)
    for business_line in configured_business_lines:
        topic_sentiments[business_line] = Counter()
    source_counts = Counter()
    official_source_counts = Counter()
    competitor_only = 0

    for result in completed_results:
        platform = result.get("platform", "unknown")
        platform_sample_counts[platform] += 1
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
            if matched == brand_config["entity_name"]:
                mentioned_self = True
                self_sentiments[mention.get("sentiment") or "neutral"] += 1
                platform_sentiments[platform][mention.get("sentiment") or "neutral"] += 1
                business_line = _business_line_for_result(result.get("topic"), business_line_lookup)
                if business_line:
                    topic_sentiments[business_line][mention.get("sentiment") or "neutral"] += 1
            elif matched in competitor_names:
                mentioned_competitor = True

        if not mentioned_self and mentioned_competitor:
            competitor_only += 1

        for citation in result.get("parsed", {}).get("citations", []):
            domain = citation.get("domain")
            if not domain:
                continue
            source_counts[domain] += 1
            if citation.get("is_official") is True:
                official_source_counts[domain] += 1

        business_line = _business_line_for_result(result.get("topic"), business_line_lookup)
        if business_line:
            topic_sentiments.setdefault(business_line, Counter())

    self_stats = brand_stats.get(brand_config["entity_name"], {"mentions": 0, "positions": []})
    natural_visibility = _round(self_stats["mentions"] / total) if total else 0
    avg_rank = _round(sum(self_stats["positions"]) / len(self_stats["positions"]), 2) if self_stats["positions"] else None
    visibility = _round(natural_visibility / avg_rank) if avg_rank else 0
    sentiment_score = _sentiment_score(self_sentiments)
    ai_recommend_score = _round(visibility * sentiment_score * 100, 2)
    own_citations = sum(official_source_counts.values())
    platforms_rows = _build_platforms(platform_brand_stats, platform_sample_counts, platform_sentiments, brand_config["entity_name"])

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
            "inspection_batch_id": run["inspection_batch_id"],
            "inspection_started_at": run.get("inspection_started_at"),
            "inspection_completed_at": run.get("inspection_completed_at"),
            "aggregation_version": "report_aggregation_v2",
            "queryset_strategy": run["queryset_strategy"],
            "queryset_source": run.get("queryset_source"),
            "inspection_mode": run["inspection_mode"],
            "platforms_requested": platforms_requested,
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
        },
        "executive_summary": _summary(brand_config["entity_name"], natural_visibility, avg_rank, ai_recommend_score, total),
        "global": {
            "natural_visibility": natural_visibility,
            "rank": avg_rank,
            "visibility": visibility,
            "sentiment_score": sentiment_score,
            "ai_recommend_score": ai_recommend_score,
            "own_citations": own_citations,
            "competitor_suppression_rate": _round(competitor_only / total) if total else 0,
            "summary_text": _summary(brand_config["entity_name"], natural_visibility, avg_rank, ai_recommend_score, total),
        },
        "competitor_ranking": _competitor_ranking(brand_stats, total),
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
        "source_gap": [],
        "sentiment": _sentiment_rates(self_sentiments),
        "topics": _topic_rows(topic_sentiments),
        "optimization_recommendations": _recommendations(natural_visibility, own_citations),
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
        "insights": _insights(brand_config["entity_name"], natural_visibility, avg_rank, own_citations, platforms_inspected),
    }
    for section in ["sources", "source_gap", "insights", "topics"]:
        if not report[section]:
            report["audit"]["empty_sections"].append(section)
    return report


def _build_platforms(platform_brand_stats: dict, platform_sample_counts: Counter, platform_sentiments: dict, self_name: str) -> list[dict]:
    rows = []
    for platform, stats in platform_brand_stats.items():
        p_stats = stats.get(self_name, {"mentions": 0, "positions": []})
        p_total = platform_sample_counts[platform]
        mention_rate = _round(p_stats["mentions"] / p_total) if p_total else 0
        avg_pos = _round(sum(p_stats["positions"]) / len(p_stats["positions"]), 2) if p_stats["positions"] else None
        vis = _round(mention_rate / avg_pos) if avg_pos else 0
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


def _competitor_ranking(stats: dict, total: int) -> list[dict]:
    rows = []
    for name, values in stats.items():
        rows.append({"name": name, "mention_rate": _round(values["mentions"] / total) if total else 0, "is_self": False})
    if rows:
        rows[0]["is_self"] = True
    return rows


def _self_rank(stats: dict, total: int, self_name: str) -> int | None:
    ranking = sorted(_competitor_ranking(stats, total), key=lambda row: row["mention_rate"], reverse=True)
    for index, row in enumerate(ranking, start=1):
        if row["name"] == self_name:
            return index
    return None


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
    return f"本次基于多平台真实 AI 回答完成 {total} 条查询巡检，{brand} 自然可见度为 {visibility:.1%}，{rank_text}，AI 推荐度为 {score:.1f}。"


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
