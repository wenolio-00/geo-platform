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
  "platforms": ["DeepSeek", "Kimi"]
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

## DeepSeek Live Inspection

`deepseek_live_v1` runs as a backend diagnostic job and must call the real
DeepSeek Chat Completions API. It must not use fixture-derived, random, or
deterministic simulated inspection data.

MVP scope:

- Platform: DeepSeek only.
- API base URL: `https://api.deepseek.com` by default.
- Default model: `deepseek-v4-flash`; deployments may override with
  `DEEPSEEK_MODEL`.
- Required environment variable: `DEEPSEEK_API_KEY`.
- If the API key is missing or DeepSeek fails, the run must become `failed`.
  The backend must not fall back to mock data.

For every QuerySet item, the backend should persist an inspection record with:

```json
{
  "platform": "DeepSeek",
  "model": "deepseek-v4-flash",
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
