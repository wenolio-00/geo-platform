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


class QueryItem(BaseModel):
    query_id: str
    query_text: str
    query_layer: Literal["core_anchor", "adaptive", "experimental"]
    run_scope: Literal["production", "bridge", "shadow"]
    journey_stage: Literal["problem_discovery", "solution_evaluation", "purchase_decision"]
    metric_scope: Literal["core_trend", "supporting_trend", "exploratory_coverage"]
    metric_weight: float = 0.0
    topic: str
    intent_type: str
    query_pattern: Literal[
        "scenario_explore",
        "category_rec",
        "competitive_comp",
        "deep_background",
        "vendor_choice",
        "internal_justification",
        "purchase_risk",
        "commercial_terms",
    ]
    related_competitors: list[str] = Field(default_factory=list)
    source_dimension_json: dict[str, Any] = Field(default_factory=dict)
    matrix_cell_id: str | None = None
    prompt_template_id: str | None = None
    lifecycle_status: str = "active"


class QuerySpec(QueryItem):
    pass


class QueryQualityCheck(BaseModel):
    name: str
    status: Literal["pass", "warn", "fail"]
    detail: str | None = None


class QueryQualityReport(BaseModel):
    status: Literal["pass", "warn", "fail"]
    checks: list[QueryQualityCheck] = Field(default_factory=list)
    coverage: dict[str, Any] = Field(default_factory=dict)
    dedupe: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class QuerySet(BaseModel):
    queryset_id: str
    queryset_version: str
    queryset_strategy: str
    queryset_source: str
    matrix_api_request_id: str | None = None
    brand_config_id: str
    run_id: str
    queries: list[QueryItem]
    quality_report: QueryQualityReport


class QueryMatrixInput(BaseModel):
    brand_config_snapshot: dict[str, Any]
    run_id: str
    queryset_strategy: Literal["rule_matrix_v1"] = "rule_matrix_v1"
    queryset_source: Literal["matrix_api_v1"] = "matrix_api_v1"
    inspection_mode: Literal["deepseek_live_v1", "multi_platform_live_v1"] = "multi_platform_live_v1"
    platforms_requested: list[str] = Field(default_factory=list)
    generation_constraints: dict[str, Any] = Field(default_factory=dict)


class QueryMatrixOutput(QuerySet):
    pass


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
