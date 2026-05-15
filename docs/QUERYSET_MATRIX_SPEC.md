# QuerySet Matrix Backend Spec

## Context

QuerySet 是诊断链路的核心资产，决定后续 live inspection、report aggregation、dashboard snapshot 和归因解释的质量。这个规范把当前文档里分散的流程要求收口为一条统一后端链路，并显式区分三层状态：

- **运行态**：生成 QuerySet 的 service 入口与矩阵输入输出。
- **冻结态**：持久化后的 immutable QuerySet snapshot。
- **校验态**：QuerySet quality report 与 contract tests。

本规范与以下契约对齐：

- `docs/DIAGNOSTIC_API_CONTRACT.md`
- `docs/REPORT_GENERATOR_SOP.md`
- `docs/queryset-governance-future-plan.md`
- `src/schemas/report_data.schema.json`
- `src/pages/BrandConfigPage.jsx`
- `src/lib/reportDataAdapter.js`

## 1. Backend flow

```text
POST /api/v1/geo/brand-configs
  → save brand_config snapshot
POST /api/v1/geo/diagnostic-runs
  → create diagnostic_run
  → generate_queryset(brand_config_snapshot, run)
  → persist queryset + queryset_items snapshot
  → start inspection batch
  → persist inspection results
  → aggregate report_data_v1
  → persist diagnostic_report snapshot
GET /api/v1/geo/diagnostic-runs/{run_id}
GET /api/v1/geo/diagnostic-report?run_id={run_id}
GET /api/v1/geo/overview?brand_config_id=...
```

## 2. Runtime state

### 2.1 `QueryMatrixInput`

`QueryMatrixInput` is the only supported input to QuerySet generation.

Required fields:

- `brand_config_snapshot`
- `run_id`
- `queryset_strategy`
- `queryset_source`
- `inspection_mode`
- `platforms_requested`
- `generation_constraints`

Recommended shape:

```json
{
  "brand_config_snapshot": {
    "entity_name": "杭州XX科技有限公司",
    "entity_aliases": ["XX", "XX Network"],
    "industry_segments": ["金融场景"],
    "topics": [
      { "topic_name": "积分商城管理工具", "business_line": "积分商城", "priority": 1 }
    ],
    "competitors": [
      { "name": "有赞", "aliases": ["Youzan"], "business_line": "会员权益", "category": "泛电商 SaaS" }
    ]
  },
  "run_id": "run_123",
  "queryset_strategy": "rule_matrix_v1",
  "queryset_source": "matrix_api_v1",
  "inspection_mode": "multi_platform_live_v1",
  "platforms_requested": ["DeepSeek", "Kimi"],
  "generation_constraints": {
    "min_queries": 20,
    "layer_policy": {
      "core_anchor": "stable_trend",
      "adaptive": "new_business_coverage",
      "experimental": "shadow_only"
    }
  }
}
```

### 2.2 `QueryMatrixOutput`

`QueryMatrixOutput` is the normalized result of generation.

Required fields:

- `queryset_id`
- `queryset_version`
- `queryset_strategy`
- `queryset_source`
- `matrix_api_request_id`
- `brand_config_id`
- `run_id`
- `queries[]`
- `quality_report`

Recommended shape:

```json
{
  "queryset_id": "qs_123",
  "queryset_version": "rule_matrix_v1",
  "queryset_strategy": "rule_matrix_v1",
  "queryset_source": "matrix_api_v1",
  "matrix_api_request_id": "mx_req_123",
  "brand_config_id": "bc_123",
  "run_id": "run_123",
  "queries": [],
  "quality_report": {
    "status": "pass",
    "coverage": {},
    "dedupe": {},
    "notes": []
  }
}
```

### 2.3 `generate_queryset()`

`generate_queryset()` is the only service entry for QuerySet creation.

Responsibilities:

- load the immutable brand config snapshot;
- build `QueryMatrixInput`;
- call Matrix API or local rule matrix backend;
- normalize query items;
- run generation-time validation;
- emit `QueryMatrixOutput`;
- persist the frozen QuerySet snapshot.

It must not:

- mutate an existing persisted QuerySet;
- regenerate queries in multiple callers;
- skip quality validation;
- fabricate fallback sample data.

## 3. Frozen state

### 3.1 `querysets` table

One row per persisted QuerySet version.

Suggested columns:

- `queryset_id`
- `queryset_version`
- `brand_config_id`
- `run_id`
- `queryset_strategy`
- `queryset_source`
- `matrix_api_request_id`
- `status`
- `quality_status`
- `created_at`
- `frozen_at`
- `frozen_snapshot_json`

Immutability rules:

- once frozen, a QuerySet row is read-only;
- any change to logic or content creates a new `queryset_id` or `queryset_version`;
- downstream runs must reference the frozen snapshot only;
- `queryset_items` must be append-only for the owning snapshot.

### 3.2 `queryset_items` table

One row per query item.

Required fields:

- `queryset_id`
- `query_id`
- `query_text`
- `query_layer`
- `run_scope`
- `journey_stage`
- `metric_scope`
- `metric_weight`
- `topic`
- `intent_type`
- `query_pattern`
- `matrix_cell_id`
- `related_competitors`
- `source_dimension_json`
- `created_at`

Suggested `query_layer` values:

- `core_anchor`
- `adaptive`
- `experimental`

Suggested `run_scope` values:

- `production`
- `bridge`
- `shadow`

Suggested `metric_scope` values:

- `core_trend`
- `supporting_trend`
- `exploratory_coverage`

Suggested `query_pattern` values:

- `scenario_explore`
- `category_rec`
- `competitive_comp`
- `deep_background`
- `vendor_choice`
- `internal_justification`
- `purchase_risk`
- `commercial_terms`

## 4. Inspection state

Every inspection result must preserve QuerySet identity.

Required fields:

- `inspection_result_id`
- `inspection_batch_id`
- `run_id`
- `queryset_id`
- `query_id`
- `platform`
- `model`
- `status`
- `raw_answer`
- `parsed_answer`
- `error_message`
- `started_at`
- `completed_at`

Rules:

- a failed platform still writes an inspection result;
- `platform`, `model`, and `status` are mandatory for all results;
- aggregation consumes completed results only, while audit records failures and missing samples;
- no inspection result may detach from its `queryset_id` / `query_id` lineage.

## 5. Report lineage

`report_data_v1.lineage` must keep enough provenance to replay the report.

Required and recommended fields:

- `brand_config_id`
- `brand_config_snapshot`
- `entity_id`
- `queryset_id`
- `queryset_version`
- `queryset_strategy`
- `queryset_source`
- `matrix_api_request_id`
- `inspection_batch_id`
- `inspection_mode`
- `platforms_requested`
- `inspection_started_at`
- `inspection_completed_at`
- `aggregation_version`

The report must remain explainable even if the brand config changes later. Historical reports always reference the original frozen brand config snapshot and QuerySet snapshot.

## 6. Quality state

`query_quality_report` is the generation gate.

For the formal QF-01~06 pre-storage acceptance rules and the current
implementation gap, see `docs/QUERYSET_QF_ACCEPTANCE_CONTEXT.md`.

It should check at least:

- required fields present;
- query text deduplicated;
- topic coverage aligned to `brand_config.topics[].business_line`;
- intent distribution is non-degenerate;
- core_anchor / adaptive / experimental counts are explicit;
- run_scope distribution is explicit;
- competitor coverage is present when competitors exist;
- query patterns are assigned where relevant;
- empty QuerySet is rejected;
- quality failures block freezing.

Recommended output shape:

```json
{
  "status": "pass",
  "checks": [
    { "name": "required_fields", "status": "pass" },
    { "name": "dedupe", "status": "pass" },
    { "name": "topic_coverage", "status": "pass" },
    { "name": "intent_distribution", "status": "pass" }
  ],
  "warnings": [],
  "errors": []
}
```

## 7. Contract tests

Contract tests are the final gate before the backend exposes a new QuerySet shape.

Minimum coverage:

1. `BrandConfig` → `QueryMatrixInput` mapping.
2. `QueryMatrixInput` → `QueryMatrixOutput` shape.
3. `QuerySet` freeze immutability.
4. `InspectionResult` lineage completeness.
5. `report_data_v1.lineage` completeness.
6. `report_data.schema.json` compatibility.
7. `overview` payload compatibility.

## 8. Current contract alignment

This spec intentionally matches the current frontend and report contract:

- `queryset_strategy = rule_matrix_v1`
- `queryset_source = matrix_api_v1`
- `topic` comes from `brand_config.topics[].business_line`
- `report_data_v1` remains the report source of truth
- `brand_config` in the report must preserve user-submitted data
- live inspection must use real platform APIs

## 9. Open decisions

These items still need a final backend product decision before implementation:

- whether local rule matrix is a production fallback or only a non-production fallback;
- exact minimum query counts per topic and per intent;
- whether `report_data_v1` should embed the full frozen QuerySet or only reference it through lineage plus dashboard snapshot.
