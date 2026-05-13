# QuerySet Governance Future Plan

## MVP already implemented

- QuerySet composition summary is visible in the Visibility page.
- Core / Adaptive / Experimental counts are surfaced from mock data.
- effect_delta is broken down into core, targeted, adaptive, and full views.
- Attribution confidence and explanation are shown in the report UI.
- Rule Activation Evaluator assets are added as node 08.5 between Rule Extraction and ActionTask generation.
- The mock contract now separates `platform_rules_store` candidates from `active_rules_store`, with Baseline Rule fallback.

## Future action stages

### Stage 1 — Backend contract alignment

**Goal:** Keep frontend mock data aligned with the eventual backend response.

**Actions:**
- Mirror `queryset`, `metrics`, `attribution`, and `methodology_note` in the backend `/api/v1/geo/overview` payload.
- Keep `src/api/geo.js` as the single switch point between mock and real API.
- Ensure all report fields stay additive so the current frontend does not need a rewrite.

**Exit condition:**
- The backend can replace mock data without changing the Visibility page render logic.

### Stage 2 — Query lifecycle governance

**Goal:** Make QuerySet evolution auditable and repeatable.

**Actions:**
- Add `query_layer`, `run_scope`, `metric_scope`, and `lifecycle_status` to the query model.
- Define promotion rules for Experimental → Adaptive → Core Anchor.
- Add `change_type`, `change_reason`, and `approved_by` for query updates.

**Exit condition:**
- Query upgrades and retirements can be reviewed instead of patched manually.

### Stage 3 — Attribution mapping

**Goal:** Make ActionTask evaluation reflect the real target query population.

**Actions:**
- Add ActionTask-to-query mapping.
- Compute `effect_delta_targeted` from the mapped scope.
- Record attribution confidence and reason for each task result.
- Gate any Rule Extraction output through Rule Activation Evaluator before ActionTask can consume it.

**Exit condition:**
- A new-business optimization task can be judged without depending only on Core Anchor movement, and it only uses rules that have passed activation or the active Baseline Rule.

### Stage 4 — Bridge and lineage calibration

**Goal:** Preserve comparability across QuerySet versions.

**Actions:**
- Add `lineage_group_id` and `parent_query_id`.
- Compute bridge gap between old and new QuerySet versions.
- Apply comparison weights when a query is rewritten but still semantically related.

**Exit condition:**
- QuerySet migrations can be explained as structural changes rather than silent metric drift.

### Stage 5 — Report methodology disclosure

**Goal:** Make the metric basis understandable to business readers.

**Actions:**
- Add a report note that explains which queries are counted in core trend metrics.
- Show QuerySet composition and scope counts on the main dashboard.
- Label exploratory metrics clearly so they are not confused with core trend metrics.

**Exit condition:**
- Report readers can distinguish stable trend metrics from exploratory coverage metrics at a glance.

## Recommended order

1. Lock the frontend contract.
2. Add backend-compatible query metadata.
3. Add attribution mapping.
4. Add lineage and bridge calibration.
5. Expand report disclosure.
