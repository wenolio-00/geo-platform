from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import os

from service.storage import querysets_store

MIN_PRODUCTION_ACTIVE_QUERIES = 30


def active_queries_from(queryset: dict) -> list[dict]:
    queries = queryset.get("queries")
    if not isinstance(queries, list):
        return []
    return [
        dict(query)
        for query in queries
        if isinstance(query, dict) and query.get("lifecycle_status", "active") == "active"
    ]


def normalize_queryset_snapshot(queryset: dict) -> dict:
    snapshot = deepcopy(queryset)
    candidates = snapshot.get("query_candidates")
    if not isinstance(candidates, list):
        candidates = [dict(query) for query in snapshot.get("queries", []) if isinstance(query, dict)]
    snapshot["query_candidates"] = candidates
    snapshot["queries"] = [
        dict(query)
        for query in candidates
        if isinstance(query, dict) and query.get("lifecycle_status", "active") == "active"
    ]
    return snapshot


def validate_queryset_for_production(
    queryset: dict,
    min_active_queries: int | None = None,
) -> dict:
    if min_active_queries is None:
        min_active_queries = _min_production_active_queries()
    snapshot = normalize_queryset_snapshot(queryset)
    active_queries = active_queries_from(snapshot)
    if len(active_queries) < min_active_queries:
        queryset_id = snapshot.get("queryset_id") or "<unknown>"
        raise RuntimeError(
            "QuerySet production gate failed: "
            f"queryset_id={queryset_id} has {len(active_queries)} active queries, "
            f"minimum required is {min_active_queries}."
        )
    snapshot["queries"] = active_queries
    governance = snapshot.get("governance") if isinstance(snapshot.get("governance"), dict) else {}
    snapshot["governance"] = {
        **governance,
        "quality_gate": {
            **(governance.get("quality_gate") if isinstance(governance.get("quality_gate"), dict) else {}),
            "status": "pass",
            "active_count": len(active_queries),
            "min_active_queries": min_active_queries,
        },
    }
    return snapshot


def _min_production_active_queries() -> int:
    try:
        return max(1, int(os.getenv("MIN_ACTIVE_QUERIES") or MIN_PRODUCTION_ACTIVE_QUERIES))
    except (TypeError, ValueError):
        return MIN_PRODUCTION_ACTIVE_QUERIES


def persist_frozen_queryset(brand_config: dict, queryset: dict) -> dict:
    snapshot = normalize_queryset_snapshot(queryset)
    now = datetime.now(timezone.utc).isoformat()
    snapshot.update(
        {
            "brand_config_id": brand_config.get("brand_config_id"),
            "entity_id": brand_config.get("entity_id"),
            "entity_name": brand_config.get("entity_name"),
            "status": "frozen",
            "frozen_at": snapshot.get("frozen_at") or now,
            "updated_at": now,
        }
    )
    key = str(snapshot.get("queryset_id") or "")
    if not key:
        raise RuntimeError("Cannot persist QuerySet without queryset_id.")
    return querysets_store.upsert(key, snapshot)


def latest_frozen_queryset(brand_config: dict, base_queryset_id: object | None = None) -> dict | None:
    records = [
        item
        for item in querysets_store.read().values()
        if isinstance(item, dict)
        and item.get("status", "frozen") == "frozen"
        and _same_brand(item, brand_config)
    ]
    if base_queryset_id:
        selected = next((item for item in records if item.get("queryset_id") == base_queryset_id), None)
        return normalize_queryset_snapshot(selected) if selected else None
    records.sort(key=lambda item: item.get("frozen_at") or item.get("updated_at") or "", reverse=True)
    return normalize_queryset_snapshot(records[0]) if records else None


def _same_brand(queryset: dict, brand_config: dict) -> bool:
    if queryset.get("brand_config_id") and queryset.get("brand_config_id") == brand_config.get("brand_config_id"):
        return True
    if queryset.get("entity_id") and queryset.get("entity_id") == brand_config.get("entity_id"):
        return True
    entity_name = str(brand_config.get("entity_name") or "").strip()
    return bool(entity_name and queryset.get("entity_name") == entity_name)
