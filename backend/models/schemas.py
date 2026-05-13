from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class BrandConfigTopic(BaseModel):
    topic_name: str | None = None
    business_line: str | None = None
    priority: int | None = None


class BrandConfigCompetitor(BaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)
    business_line: str | None = None
    category: str | None = None


class BrandConfigCreate(BaseModel):
    entity_name: str
    entity_aliases: list[str] = Field(default_factory=list)
    industry_segments: list[str] = Field(default_factory=list)
    topics: list[BrandConfigTopic] = Field(default_factory=list)
    competitors: list[BrandConfigCompetitor] = Field(default_factory=list)


class BrandConfigResponse(BaseModel):
    brand_config_id: str
    entity_id: str
    brand_config: dict[str, Any]


class DiagnosticRunCreate(BaseModel):
    brand_config_id: str
    queryset_strategy: Literal["rule_matrix_v1"] = "rule_matrix_v1"
    inspection_mode: Literal["deepseek_live_v1", "multi_platform_live_v1"] = "multi_platform_live_v1"
    queryset_source: Literal["matrix_api_v1"] = "matrix_api_v1"
    platforms: list[str] | None = None


class DiagnosticRunResponse(BaseModel):
    run_id: str
    status: Literal["queued", "running", "aggregating", "completed", "failed"]
    progress: int = 0
    message: str | None = None
    error: str | None = None


class QuerySpec(BaseModel):
    query_id: str
    query_text: str
    query_layer: Literal["core_anchor", "adaptive", "experimental"]
    run_scope: Literal["production", "bridge", "shadow"]
    metric_scope: str
    topic: str
    intent_type: str
    related_competitors: list[str] = Field(default_factory=list)


class MentionedBrand(BaseModel):
    name: str
    aliases_matched: list[str] = Field(default_factory=list)
    position: int | None = None
    mention_context: Literal[
        "explicit_recommendation",
        "standard_listing",
        "incidental_mention",
        "not_mentioned",
    ] = "not_mentioned"
    sentiment: Literal["positive", "neutral", "negative"] = "neutral"
    evidence: str | None = None


class Citation(BaseModel):
    url: str | None = None
    domain: str | None = None
    title: str | None = None
    is_official: bool | None = None


class ParsedInspection(BaseModel):
    answer: str
    mentioned_brands: list[MentionedBrand] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    parse_confidence: Literal["high", "medium", "low"] = "medium"
    notes: str | None = None
