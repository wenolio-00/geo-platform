from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from models.schemas import BrandConfigCreate
from service.storage import brand_configs_store


def _clean_list(values: list[str]) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]


def create_brand_config(payload: BrandConfigCreate) -> dict:
    brand_config_id = f"bc_{uuid4().hex[:12]}"
    entity_id = f"entity_{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    topics = [
        {
            "topic_name": (topic.topic_name or "").strip(),
            "business_line": (topic.business_line or "").strip(),
            "priority": topic.priority,
            "pain_point": (topic.pain_point or "").strip() or None,
            "goal": (topic.goal or "").strip() or None,
        }
        for topic in payload.topics
        if (topic.topic_name or topic.business_line)
    ]
    competitors = [
        {
            "name": competitor.name.strip(),
            "aliases": _clean_list(competitor.aliases),
            "business_line": (competitor.business_line or "").strip(),
            "category": (competitor.category or "").strip(),
        }
        for competitor in payload.competitors
        if competitor.name.strip()
    ]
    brand_config = {
        "brand_config_id": brand_config_id,
        "entity_id": entity_id,
        "entity_name": payload.entity_name.strip(),
        "entity_aliases": _clean_list(payload.entity_aliases),
        "industry_segments": _clean_list(payload.industry_segments),
        "topics": topics,
        "competitors": competitors,
        "aliases_count": len(_clean_list(payload.entity_aliases)),
        "topics_monitored": len(topics),
        "competitors_count": len(competitors),
        "created_at": now,
        "updated_at": now,
    }
    return brand_configs_store.upsert(brand_config_id, brand_config)


def get_brand_config(brand_config_id: str) -> dict | None:
    return brand_configs_store.get(brand_config_id)
