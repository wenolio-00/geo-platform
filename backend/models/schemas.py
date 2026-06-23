from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AIGeneratedQuestion(BaseModel):
    question: str
    intent_type: str


class BrandConfigTopic(BaseModel):
    topic_name: str | None = None
    business_line: str | None = None
    priority: int | None = None
    pain_point: str | None = None  # 用户通用痛点描述
    goal: str | None = None         # 业务目标描述


class PainPointAnalysis(BaseModel):
    pain_point: str
    severity: int = Field(ge=1, le=5)
    goal: str | None = None
    ai_questions: list[AIGeneratedQuestion] = Field(default_factory=list)


class IntentAnalysisResult(BaseModel):
    audience_profile: str
    pain_points: list[PainPointAnalysis] = Field(default_factory=list)


class BrandConfigCompetitor(BaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)
    business_line: str | None = None
    category: str | None = None
    owned_domains: list[str] = Field(default_factory=list)


class BrandConfigCreate(BaseModel):
    entity_name: str
    entity_aliases: list[str] = Field(default_factory=list)
    owned_domains: list[str] = Field(default_factory=list)
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
    queryset_policy: Literal["reuse_latest", "create_new_version"] = "reuse_latest"
    base_queryset_id: str | None = None
    queryset_change_reason: str | None = None
    queryset_approved_by: str | None = None
    generation_constraints: dict[str, Any] = Field(default_factory=dict)
    platforms: list[str] | None = None
    llm_provider: str | None = None
    web_search_enabled: bool = True
    llm_options: dict[str, Any] = Field(default_factory=dict)


class DiagnosticRunResponse(BaseModel):
    run_id: str
    status: Literal["queued", "running", "aggregating", "completed", "failed", "interrupted"]
    progress: int = 0
    message: str | None = None
    error: str | None = None
    terminal_reason: str | None = None
    retriable: bool | None = None
    last_queryset_quality_report: dict[str, Any] | None = None
    queryset_generation_attempt_reports: list[dict[str, Any]] = Field(default_factory=list)
    last_queryset_id: str | None = None
    matrix_api_request_id: str | None = None
    last_queryset_generation_result: dict[str, Any] | None = None
    last_queryset_candidates_preview: list[dict[str, Any]] = Field(default_factory=list)
    queryset_debug_context: dict[str, Any] | None = None


class QuerySpec(BaseModel):
    query_id: str
    query_text: str
    query_layer: Literal["core_anchor", "adaptive", "experimental"]
    run_scope: Literal["production", "bridge", "shadow"]
    metric_scope: str
    topic: str
    intent_type: str


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
    source_type: str | None = None
    ownership: str | None = None
    entity: str | None = None
    is_brand_owned: bool | None = None
    is_competitor_owned: bool | None = None
    quoted_text: str | None = None
    answer_excerpt: str | None = None


class ParsedInspection(BaseModel):
    answer: str
    mentioned_brands: list[MentionedBrand] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    parse_confidence: Literal["high", "medium", "low"] = "medium"
    notes: str | None = None


class InspectionResult(BaseModel):
    inspection_id: str
    status: Literal["completed", "failed"]
    platform: str
    provider: str | None = None
    llm_provider: str | None = None
    inspection_design: Literal["single_round", "blind_assisted"] = "single_round"
    web_search_enabled: bool | None = None
    web_search_mode: str | None = None
    model: str | None = None
    query_id: str
    query_text: str
    query_pattern: str | None = None
    query_layer: str | None = None
    topic: str
    intent_type: str
    request_at: str | None = None
    returned_at: str | None = None
    raw_answer: str = ""
    parsed: ParsedInspection | dict[str, Any] = Field(default_factory=dict)
    natural_raw_answer: str | None = None
    natural_parsed: ParsedInspection | dict[str, Any] | None = None
    assisted_raw_answer: str | None = None
    assisted_parsed: ParsedInspection | dict[str, Any] | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    error_type: str | None = None
