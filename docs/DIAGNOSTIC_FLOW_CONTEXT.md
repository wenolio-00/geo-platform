# GEO Diagnostic Flow Context

Last verified: 2026-05-15

This is the handoff context for Claude/Codex agents working on the local GEO
diagnostic project. It summarizes the full data chain from brand configuration
to generated report, and points to the source files that define each contract.

## Source Of Truth Files

- API contract: `docs/DIAGNOSTIC_API_CONTRACT.md`
- Report generation SOP: `docs/REPORT_GENERATOR_SOP.md`
- QuerySet backend contract: `docs/QUERYSET_MATRIX_SPEC.md`
- QuerySet weights and matrix policy: `docs/QUERYSET_MATRIX_WEIGHTING_SUMMARY.md`
- Query quality filters and acceptance context: `docs/QUERYSET_QF_ACCEPTANCE_CONTEXT.md`
- Backend API routes: `backend/router/geo.py`
- Backend request/response schemas: `backend/models/schemas.py`
- Storage layer: `backend/service/storage.py`
- Brand config service: `backend/service/brand_config.py`
- Diagnostic orchestration: `backend/service/inspector.py`
- QuerySet generation and quality gate: `backend/service/queryset.py`
- QuerySet Matrix API/local fallback client: `backend/service/queryset_matrix_client.py`
- Rule matrix templates and metric weights: `backend/service/rule_matrix.py`
- QuerySet library/frozen snapshots: `backend/service/queryset_library.py`
- Query quality filter policy: `backend/service/queryset_policy.py`
- Platform clients and parsing: `backend/service/platform_registry.py`, `backend/service/platform_clients/*`, `backend/service/parser.py`
- Report aggregation: `backend/service/aggregator.py`
- Dashboard snapshot derivation: `backend/service/dashboard_snapshots.py`
- Frontend API client: `src/api/geo.js`
- Brand config UI: `src/pages/BrandConfigPage.jsx`
- Diagnostic report UI: `src/pages/DiagnosticReportPage.jsx`
- Report display adapter/schema checks: `src/lib/reportDataAdapter.js`
- Static HTML report generator: `src/lib/reportGenerator.js`
- Report schema: `src/schemas/report_data.schema.json`
- Rule activation schema/prompt/config: `src/schemas/rule_activation_evaluation.schema.json`, `src/prompts/*`, `src/config/rule_activation_evaluator.config.json`

## End-To-End Flow

```text
BrandConfigPage
  -> POST /api/v1/geo/brand-configs
  -> backend/service/brand_config.py
  -> backend/storage/brand_configs.json

BrandConfigPage
  -> POST /api/v1/geo/diagnostic-runs
  -> backend/service/inspector.py:create_run()
  -> backend/storage/diagnostic_runs.json
  -> asyncio background run_diagnostic_job(run_id)

run_diagnostic_job()
  -> load immutable brand_config snapshot
  -> resolve_queryset()
  -> reuse latest frozen QuerySet OR generate new Matrix QuerySet
  -> validate production QuerySet gate
  -> inspect active queries across requested platforms
  -> persist raw inspection results
  -> apply inspection quality gate
  -> aggregate report_data_v1
  -> persist completed diagnostic run
  -> persist dashboard snapshot

DiagnosticReportPage
  -> poll GET /api/v1/geo/diagnostic-runs/{run_id}
  -> fetch GET /api/v1/geo/diagnostic-report?run_id=...
  -> buildReportDisplayData()
  -> render report UI
  -> generateReportHtml(report_data_v1) for standalone export

DashboardPage
  -> GET /api/v1/geo/dashboard-contract
  -> backend/storage/brand_dashboard_snapshots.json
  -> opens /report/diagnostic?run_id=...
```

## API Contract

The frontend must use real `/api/v1/geo/*` endpoints. It must not fall back to
fixture or mock report data after the live flow is connected.

Primary endpoints:

- `POST /api/v1/geo/brand-configs`
- `POST /api/v1/geo/diagnostic-runs`
- `GET /api/v1/geo/diagnostic-runs/{run_id}`
- `GET /api/v1/geo/diagnostic-report?run_id=...`
- `GET /api/v1/geo/dashboard-contract`
- `GET /api/v1/geo/overview`
- `GET /api/v1/geo/brands/{brand_id}/history`

Allowed diagnostic run statuses:

- `queued`
- `running`
- `aggregating`
- `completed`
- `failed`

## Runtime Data Stores

The current local implementation uses JSON stores under `backend/storage/`.
These files are the local persistence layer:

- `brand_configs.json`: submitted brand configuration snapshots.
- `diagnostic_runs.json`: run status, progress, lineage, QuerySet snapshot, final `report_data`.
- `querysets.json`: frozen QuerySet library records for reuse/versioning.
- `inspection_results.json`: raw per-run platform inspection rows while a run is executing.
- `brand_dashboard_snapshots.json`: report-derived dashboard snapshots and history.

The storage implementation is `backend/service/storage.py`.

## Brand Config Shape

Defined by `BrandConfigCreate` in `backend/models/schemas.py` and normalized by
`backend/service/brand_config.py`.

Required/high-value fields:

- `entity_name`
- `entity_aliases[]`
- `industry_segments[]`
- `topics[]`
  - `topic_name`
  - `business_line`
  - `priority`
- `competitors[]`
  - `name`
  - `aliases[]`
  - `business_line`
  - `category`

On write, the service adds:

- `brand_config_id`
- `entity_id`
- `aliases_count`
- `topics_monitored`
- `competitors_count`
- `created_at`
- `updated_at`

This brand config is also embedded back into `report_data.brand_config` together
with generated queries and `queries_count`.

## Diagnostic Run Shape

Created by `DiagnosticRunCreate` and `create_run()`.

Important fields:

- `run_id`
- `brand_config_id`
- `queryset_strategy`: currently `rule_matrix_v1`
- `queryset_source`: currently `matrix_api_v1`
- `queryset_policy`: `reuse_latest` or `create_new_version`
- `base_queryset_id`
- `queryset_change_reason`
- `queryset_approved_by`
- `inspection_mode`: `deepseek_live_v1` or `multi_platform_live_v1`
- `platforms`
- `inspection_batch_id`
- `status`
- `progress`
- `message`
- `report_data`

`POST /diagnostic-runs` returns immediately with a queued run and starts
`run_diagnostic_job(run_id)` in the background.

## QuerySet Resolution

The QuerySet chain is owned by `backend/service/inspector.py` and
`backend/service/queryset*.py`.

Resolution rules:

1. `resolve_queryset()` checks whether the run can reuse the latest frozen
   QuerySet for the same brand.
2. If `queryset_policy = reuse_latest` and a valid frozen QuerySet exists, it is
   normalized and reused with governance metadata.
3. If no valid reusable QuerySet exists, or the run requests a new version,
   `generate_queryset()` creates a new Matrix QuerySet.
4. New QuerySets are passed through quality filters and frozen in
   `querysets.json`.
5. Production inspection only uses active queries from the normalized snapshot.

Generation path:

```text
generate_queryset()
  -> QuerySetMatrixClient.generate()
  -> if QUERYSET_MATRIX_API_URL exists: call external Matrix API
  -> else: generate_rule_matrix_queryset() local fallback
  -> normalize_matrix_queryset()
  -> apply_query_quality_filters()
  -> build_query_quality_report()
  -> normalize_queryset_snapshot()
```

Current defaults:

- candidate queries per attempt: `40`
- minimum active queries: `30`
- max generation attempts: `3`
- production minimum active queries: `30`

Important environment variables:

- `QUERYSET_MATRIX_API_URL`
- `QUERYSET_MATRIX_API_KEY`
- `QUERYSET_MATRIX_TIMEOUT_SECONDS`
- `QUERYSET_CANDIDATE_QUERIES`
- `MIN_ACTIVE_QUERIES`
- `MAX_QUERYSET_GENERATION_ATTEMPTS`

## QuerySet Item Fields

The QuerySet matrix contract is documented in `docs/QUERYSET_MATRIX_SPEC.md`.
High-value fields on each query:

- `query_id`
- `query_text`
- `query_layer`: `core_anchor`, `adaptive`, `experimental`
- `run_scope`: `production`, `bridge`, `shadow`
- `journey_stage`
- `query_pattern`
- `matrix_cell_id`
- `metric_scope`: `core_trend`, `supporting_trend`, `exploratory_coverage`
- `metric_weight`
- `topic`
- `intent_type`
- `related_competitors[]`
- `prompt_template_id`
- `lifecycle_status`: active queries participate in inspection
- `quality_filter_status`
- `quality_filter_reasons[]`
- `source_query_id`
- `generation_attempt`

The matrix weights are defined in `backend/service/rule_matrix.py` and explained
in `docs/QUERYSET_MATRIX_WEIGHTING_SUMMARY.md`. The main Answer Share/GVI-style
metric source is the `core_trend` sample set after weight normalization.

## Query Quality Gates

Quality filter context is in `docs/QUERYSET_QF_ACCEPTANCE_CONTEXT.md`; code is
in `backend/service/queryset_policy.py`.

Generation must produce enough active queries after:

- required field normalization
- duplicate/reuse filtering
- brand/topic coverage checks
- competitor coverage checks when competitors exist
- matrix policy validation
- QF tone/formality filters
- metric weight validation

The production gate is enforced by
`validate_queryset_for_production(queryset, min_active_queries=30)`.

## Platform Inspection

Inspection is orchestrated by `backend/service/inspector.py`.

```text
active queries x requested platform clients
  -> client.inspect(query, brand_config)
  -> raw answer
  -> parsed mentioned brands/citations/sentiment
  -> inspection_results.json
```

Inspection row fields include:

- `inspection_id`
- `status`: `completed` or `failed`
- `platform`
- `model`
- `query_id`
- `query_text`
- `query_pattern`
- `query_layer`
- `topic`
- `intent_type`
- `request_at`
- `returned_at`
- `raw_answer`
- `parsed`
- `usage`
- `error`
- `error_type`

Completion gate:

- controlled by `MIN_INSPECTION_COMPLETION_RATE`
- default minimum completion rate: `0.8`
- task timeout controlled by `INSPECTION_TASK_TIMEOUT_SECONDS` or
  `REQUEST_TIMEOUT_SECONDS`
- default task timeout: `90s`

Failed platform samples are not aggregated into metrics, but failure counts and
types must appear in `report_data.audit`.

## Report Aggregation

Aggregation happens in `backend/service/aggregator.py` after inspection passes
the quality gate.

Inputs:

- completed diagnostic run
- brand config snapshot
- frozen/validated QuerySet
- inspection results

Output:

- `report_data_v1`, schema version `report_data_schema_v1`

Important report sections:

- `meta`
- `lineage`
- `audit`
- `executive_summary`
- `global`
- `competitor_ranking`
- `platforms`
- `sources`
- `source_references`
- `source_gap`
- `sentiment`
- `topics`
- `optimization_recommendations`
- `retest_plan`
- `brand_config`
- `insights`

Key metric formulas currently implemented:

- `natural_visibility = self_mentions / completed_samples`
- `rank = average self mention position`
- `visibility = natural_visibility / rank`, or `0` when rank is missing
- `sentiment_score = positive * 1.0 + neutral * 0.5 + negative * 0.1`
- `ai_recommend_score = visibility * sentiment_score * 100`
- `own_citations = count of official cited domains`
- `competitor_suppression_rate = competitor_only_samples / completed_samples`

Lineage must preserve:

- `brand_config_id`
- `entity_id`
- `queryset_id`
- `queryset_version`
- `parent_queryset_id`
- `inspection_batch_id`
- `inspection_started_at`
- `inspection_completed_at`
- `aggregation_version`
- `queryset_strategy`
- `queryset_source`
- `queryset_policy`
- `queryset_governance`
- `inspection_mode`
- `platforms_requested`
- `matrix_api_request_id`

## Dashboard Snapshot Chain

After report aggregation, `run_diagnostic_job()` calls
`persist_dashboard_snapshot(persisted_run, report_data)`.

Dashboard snapshot logic is in `backend/service/dashboard_snapshots.py`.

The snapshot stores:

- stable `brand_id`
- `brand_config_id`
- `entity_id`
- `run_id`
- `report_id`
- `main_brand`
- report-derived dashboard metrics
- QuerySet snapshot
- full `report_data`

The dashboard contract and overview endpoints read from persisted snapshots.
Completed runs can be re-synced into snapshots by
`sync_completed_run_snapshots()`.

## Frontend Flow

`src/pages/BrandConfigPage.jsx`:

1. normalizes form data
2. calls `createBrandConfig(payload)`
3. calls `startDiagnosticRun({ brand_config_id, queryset_strategy, queryset_source, queryset_policy, inspection_mode, platforms })`
4. navigates to `/report/diagnostic?run_id=...`

`src/pages/DiagnosticReportPage.jsx`:

1. reads `run_id` from URL
2. tries `fetchDiagnosticReportData({ run_id })`
3. polls `fetchDiagnosticRun(runId)` while the run is queued/running/aggregating
4. renders `buildReportDisplayData(rawData)`
5. exports standalone HTML via `generateReportHtml(rawData)`

`src/lib/reportDataAdapter.js`:

- validates required report paths
- normalizes display fields
- recomputes display-safe derived metrics where needed
- preserves audit state

## Non-Negotiable Invariants

- Do not use fixture/mock data for live diagnostic report pages.
- `report_data.brand_config` must be the submitted brand config plus generated
  queries, not a hardcoded demo brand.
- QuerySet generation must pass quality filters and production active-count
  gates before inspection.
- Frozen QuerySets should be reused for comparable retests unless a new version
  is explicitly requested or the reusable snapshot fails validation.
- Each completed report must include lineage tying together brand config,
  QuerySet, inspection batch, aggregation version, requested platforms, and
  Matrix API request id when present.
- Platform failures are allowed only when the inspection completion rate passes;
  failures must be recorded in `audit`.
- Dashboard panels should read persisted report-derived snapshots, not demo data.
- `report_data_v1` must stay compatible with `src/schemas/report_data.schema.json`
  and `docs/DIAGNOSTIC_API_CONTRACT.md`.

## Context Sync Package

Any Claude agent worktree that is expected to work independently on this flow
should have these docs in its `docs/` directory:

- `DIAGNOSTIC_FLOW_CONTEXT.md`
- `DIAGNOSTIC_API_CONTRACT.md`
- `REPORT_GENERATOR_SOP.md`
- `QUERYSET_MATRIX_SPEC.md`
- `QUERYSET_MATRIX_WEIGHTING_SUMMARY.md`
- `QUERYSET_QF_ACCEPTANCE_CONTEXT.md`
- `queryset-governance-future-plan.md`
- `rule_activation_flow_patch.md`
- `rule_activation_integration_guide.md`
- `GEO_PROJECT_PROGRESS.md`
- `diagnostic_report_flow.html`

`CLAUDE.md` should remain present at the worktree root.
