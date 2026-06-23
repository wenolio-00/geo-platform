# Diagnostic API Contract

This frontend expects the diagnostic report flow to be backed by real
`/api/v1/geo/*` endpoints. It must not receive fixture-derived report data.

## Flow

1. `POST /api/v1/geo/brand-configs`
2. `POST /api/v1/geo/diagnostic-runs`
3. `GET /api/v1/geo/diagnostic-runs/{run_id}` until `completed`
4. `GET /api/v1/geo/diagnostic-report?run_id={run_id}`

## Endpoints

### POST /api/v1/geo/brand-configs

Request body:

```json
{
  "entity_name": "杭州XX科技有限公司",
  "entity_aliases": ["XX", "XX Network"],
  "industry_segments": ["金融场景", "互联网App运营"],
  "topics": [
    { "topic_name": "积分商城管理工具", "business_line": "积分商城", "priority": 1 }
  ],
  "competitors": [
    { "name": "有赞", "aliases": ["Youzan"], "business_line": "会员权益", "category": "泛电商 SaaS" }
  ]
}
```

Response body:

```json
{
  "brand_config_id": "bc_123",
  "entity_id": "entity_123",
  "brand_config": {}
}
```

### POST /api/v1/geo/diagnostic-runs

Request body:

```json
{
  "brand_config_id": "bc_123",
  "queryset_strategy": "rule_matrix_v1",
  "queryset_source": "matrix_api_v1",
  "queryset_policy": "reuse_latest",
  "base_queryset_id": "qs_previous_123",
  "queryset_change_reason": "scheduled_retest",
  "queryset_approved_by": "ops_owner",
  "inspection_mode": "multi_platform_live_v1",
  "platforms": ["claude"],
  "llm_provider": "claude",
  "web_search_enabled": true,
  "llm_options": {
    "web_search_mode": "responses_web_search"
  }
}
```

Response body:

```json
{
  "run_id": "run_123",
  "status": "queued"
}
```

### GET /api/v1/geo/diagnostic-runs/{run_id}

Response body:

```json
{
  "run_id": "run_123",
  "status": "running",
  "progress": 42,
  "message": "Inspecting model answers"
}
```

Allowed statuses: `queued`, `running`, `aggregating`, `completed`, `failed`.
For `failed`, include `error` or `message`.

### GET /api/v1/geo/diagnostic-report

Query params:

- `run_id`: required.

Response body must be a complete `report_data_v1` object matching
`src/schemas/report_data.schema.json`.

Required lineage additions:

```json
{
  "lineage": {
    "brand_config_id": "bc_123",
    "entity_id": "entity_123",
    "queryset_id": "qs_123",
    "queryset_version": "rule_matrix_v1.1",
    "parent_queryset_id": "qs_previous_123",
    "inspection_batch_id": "batch_123",
    "inspection_started_at": "2026-05-12T10:00:00+08:00",
    "inspection_completed_at": "2026-05-12T10:03:00+08:00",
    "aggregation_version": "report_aggregation_v2",
    "queryset_strategy": "rule_matrix_v1",
    "queryset_source": "matrix_api_v1",
    "queryset_policy": "reuse_latest",
    "queryset_governance": {
      "policy": "reuse_latest",
      "change_type": "reused",
      "reused_from_queryset_id": "qs_previous_123",
      "change_reason": "scheduled_retest"
    },
    "inspection_mode": "multi_platform_live_v1",
    "platforms_requested": ["DeepSeek", "Kimi"],
    "matrix_api_request_id": "mx_req_123"
  },
  "audit": {
    "source": "api",
    "platforms_inspected": ["DeepSeek"],
    "platforms_failed": ["Kimi"],
    "expected_samples": 20,
    "completed_samples": 10,
    "missing_samples": 10
  }
}
```

`report_data.brand_config` must contain the user-submitted brand config, not a
hardcoded demo brand.

`report_data.sources` remains a domain-level summary for backwards
compatibility. URL-level citation details are exposed through
`report_data.source_references`, sorted by `citation_count` descending and
limited to the Top 6 URLs used by the report UI:

```json
{
  "source_references": [
    {
      "url": "https://example.com/case",
      "domain": "example.com",
      "title": "Case page",
      "type": "第三方",
      "is_official": false,
      "citation_count": 3,
      "references": [
        {
          "inspection_id": "insp_123",
          "platform": "DeepSeek",
          "model": "deepseek-chat",
          "query_id": "q_001",
          "query_text": "金融场景积分商城管理工具有哪些？",
          "topic": "积分商城",
          "quoted_text": "AI 回答中引用该 URL 时对应的内容片段",
          "answer_excerpt": "包含该引用判断的更长回答上下文"
        }
      ]
    }
  ]
}
```

When a platform does not return URL-level citations, `source_references` may be
empty while `sources` still contains domain-level aggregation.

### GET /api/v1/geo/dashboard-contract

Query params:

- `brand_config_id`: optional, when opening a persisted dashboard for a known config.

Response body should include the existing dashboard contract and, when a report
is available, one of:

```json
{
  "latest_run_id": "run_123"
}
```

or:

```json
{
  "diagnostic_run": { "run_id": "run_123" }
}
```

The dashboard report button only opens `/report/diagnostic?run_id=...`.

When a diagnostic run reaches `completed`, the backend must persist a dashboard
snapshot under the brand account. The snapshot is derived from `report_data_v1`
and must include:

- `main_brand.brand_id`: stable brand account id used by dashboard/history APIs.
- `brand_config`: the submitted brand configuration plus generated queries.
- `key_metrics[].current_value`: metrics filled from `report_data.global`.
- `key_metrics[].previous_value`: the same metric from the previous persisted
  snapshot for this brand account, when available.
- `latest_run_id` or `diagnostic_run.run_id`: the completed diagnostic run id.

The persisted snapshot is the source of truth for workbench panels after report
generation. Frontend panels must not fall back to demo data when a persisted
snapshot exists.

### Content Generation Persistence

Content generation consumes the latest persisted dashboard snapshot. It must not
store generated versions or feedback only in frontend state.

`GET /api/v1/geo/content/context` returns:

```json
{
  "brand": {},
  "actions": [],
  "rules": [],
  "rule_activation": {},
  "queryset": {
    "queryset_id": "qs_123",
    "queryset_version": "rule_matrix_v1",
    "query_ids": ["q_001"]
  },
  "lineage": {
    "baseline_run_id": "run_123",
    "queryset_id": "qs_123"
  },
  "template_recommendation": {
    "template_id": "tpl_product_capability",
    "template_version": "1.0.0",
    "display_name": "产品能力介绍页",
    "matched_reason": "动作类型匹配，且素材覆盖 data_points。",
    "material_coverage": {
      "required_fields": ["products"],
      "available_fields": ["brand_name", "products", "data_points"],
      "missing_required_fields": []
    }
  },
  "template_candidates": [],
  "templates_by_action": {
    "action_1": {
      "template_recommendation": {},
      "template_candidates": []
    }
  },
  "brand_material_summary": {
    "source": "derived",
    "available_fields": ["brand_name", "products", "data_points"]
  },
  "content_versions": [],
  "defaults": {
    "action_id": "action_1",
    "rule_id": "active_baseline_geo_content_v1",
    "template_id": "tpl_product_capability"
  }
}
```

`POST /api/v1/geo/content/generate` accepts `brand_id` or `brand_config_id`,
`action_id`, `rule_id`, and optional `template_id` / `template_version`. If no
template is supplied, the backend selects one from the static
`geo_content_templates_v1` registry using action type, trigger cell, and derived
brand material coverage. It then persists a `content_version_v1` record:

```json
{
  "content_version_id": "cv_123",
  "brand_id": "brand_123",
  "action_id": "action_1",
  "rule_id": "active_baseline_geo_content_v1",
  "template_id": "tpl_product_capability",
  "template_version": "1.0.0",
  "template_display_name": "产品能力介绍页",
  "brand_material_source": "derived",
  "material_coverage": {},
  "baseline_run_id": "run_123",
  "queryset": { "queryset_id": "qs_123", "queryset_version": "rule_matrix_v1" },
  "generated_text": "...",
  "version": 1,
  "feedback_summary": { "helpful": 0, "not_helpful": 0, "total": 0, "net_score": 0 },
  "effect_attribution": {
    "content_version_id": "cv_123",
    "baseline_run_id": "run_123",
    "comparison_run_id": null,
    "status": "awaiting_retest"
  }
}
```

Additional content endpoints:

- `POST /api/v1/geo/content/versions/{content_version_id}/edits`: creates a
  child `content_version_v1` with `generation_source = manual_edit`.
- `POST /api/v1/geo/content/versions/{content_version_id}/feedback`: persists a
  `content_feedback_v1` event with `signal = helpful | not_helpful` and updates
  feedback summaries on the content version and attribution record.
- `GET /api/v1/geo/content/versions/{content_version_id}/effect-attribution`:
  reads the current attribution record.
- `POST /api/v1/geo/content/versions/{content_version_id}/effect-attribution`:
  computes `effect_delta` from the content version's `baseline_run_id` and a
  supplied or latest completed `comparison_run_id`.

The persisted stores are `content_versions.json`, `content_feedback.json`, and
`effect_attribution.json`. A valid effect attribution record must include
`content_version_id`, `action_id`, `rule_id`, `baseline_run_id`,
`comparison_run_id`, `queryset_id`, `queryset_version`, feedback summary, and
comparability confidence. When content is generated through a template, the
record must also carry `template_id`, `template_version`,
`template_display_name`, `brand_material_source`, and `material_coverage` so
template effectiveness can be attributed later.

### GET /api/v1/geo/brands/{brand_id}/history

Query params:

- `days`: optional, default `30`.

Response body:

```json
{
  "brand_id": "brand_123",
  "brand_name": "兑吧",
  "days": 30,
  "history": [
    {
      "date": "2026-05-13",
      "run_id": "run_123",
      "report_id": "report_123",
      "metrics": {
        "natural_visibility": 68.1,
        "rank": 4.8,
        "visibility": 14.2,
        "sentiment_score": 70,
        "ai_recommend_score": 9.9,
        "own_citations": 35,
        "competitor_suppression_rate": 24
      }
    }
  ],
  "by_metric": {
    "natural_visibility": [
      { "date": "2026-05-13", "value": 68.1, "run_id": "run_123" }
    ]
  },
  "by_intent": []
}
```

Dashboard before/after and "上期" values must come from these persisted brand
snapshots.

### GET /api/v1/geo/overview

Query params:

- `brand_config_id`: optional.

Response body should include `queryset`, `metrics`, `attribution`, and
`methodology_note` for the current or selected brand config.

## Rule Matrix QuerySet

The backend generates query objects from `entity_name`, aliases,
`industry_segments`, `topics`, and `competitors`.

Each query object should include:

```json
{
  "query_id": "q_001",
  "query_text": "银行积分商城系统有哪些成熟供应商？",
  "query_layer": "core_anchor",
  "run_scope": "production",
  "metric_scope": "core_trend",
  "topic": "积分商城",
  "intent_type": "vendor_recommendation",
  "related_competitors": ["有赞", "微盟"]
}
```

`topic` is the report topic dimension and must come from
`brand_config.topics[].business_line`. `topic_name` can still be used in prompt
wording, but report `topics[].name` must display the business line.

Layer policy:

- `core_anchor`: stable trend and default attribution.
- `adaptive`: new-business coverage analysis.
- `experimental`: shadow-only exploration.

## Shared LLM Provider And Pluggable Inspection Platforms

Shared LLM tasks use the canonical project-internal `claude` provider by
default. In this project, `claude` means the shared OpenAI-compatible upstream
configured by `CLAUDE_*`; it does not mean the native Anthropic Messages API.
The post-QuerySet inspection step remains platform-pluggable and must not be
collapsed into the shared provider.

Shared LLM scope:

- Provider: `claude`.
- Endpoint: `CLAUDE_RESPONSES_ENDPOINT=/responses`.
- Default model: `gpt-5.5`; deployments may override with `CLAUDE_MODEL`.
- Required environment variables: `CLAUDE_API_KEY`, `CLAUDE_BASE_URL`, and
  `CLAUDE_MODEL`.
- Recommended unified gateway config:
  - `CLAUDE_BASE_URL=https://newapi.ailyyzdk.xyz/`
  - `CLAUDE_MODEL=gpt-5.5`
  - URL / key / model must come from the same upstream provider account.
- Web search: `CLAUDE_WEB_SEARCH_ENABLED=true` and
  `CLAUDE_WEB_SEARCH_MODE=responses_web_search`.
- Shared callers include content generation, smart prefill, rule activation,
  topic context extraction, and QuerySet matrix generation.
- QuerySet matrix defaults to `CLAUDE_*`; `QUERYSET_MATRIX_*` is only an
  explicit override for separating that task from the shared upstream.

Inspection platform scope:

- `INSPECTION_PLATFORMS` controls only the per-query post-QuerySet inspection
  fan-out.
- Platform clients remain independently configurable for `claude`, `GPT`,
  `DeepSeek`, `Kimi`, `豆包`, `Tongyi`, `Wenxin`, and `Yuanbao`.
- `run.llm_provider` describes the shared LLM provider and must not override
  the actual inspection platform client.
- If a required API key/base URL/model is missing or a provider fails, the run
  must become `failed`. The backend must not fall back to mock data.

For every QuerySet item, the backend should persist an inspection record with:

```json
{
  "platform": "claude",
  "provider": "claude",
  "llm_provider": "claude",
  "model": "gpt-5.5",
  "query_id": "q_001",
  "query_text": "银行积分商城系统有哪些成熟供应商？",
  "raw_answer": "...",
  "parsed": {
    "answer": "...",
    "mentioned_brands": [
      {
        "name": "品牌名",
        "aliases_matched": [],
        "position": 1,
        "mention_context": "explicit_recommendation",
        "sentiment": "positive",
        "evidence": "..."
      }
    ],
    "citations": [],
    "parse_confidence": "high"
  }
}
```

Aggregation rules:

- `natural_visibility`: main brand mentioned samples / total samples.
- `rank`: average main brand position when mentioned.
- `visibility`: `natural_visibility / rank`; `0` when rank is missing.
- `sentiment_score`: positive `1.0`, neutral `0.5`, negative `0.1` weighted mean.
- `ai_recommend_score`: `visibility * sentiment_score * 100`.
- `competitor_ranking`: mention rate ranking for the main brand and configured competitors.
- `sources` and `source_gap` must stay empty when live model answers do not
  provide explicit source URLs; the backend must not fabricate domains.
