# QuerySet QF-01~06 Acceptance Context

## Purpose

This document gives the missing context needed to judge whether the current QuerySet generation flow satisfies QF-01~06.

Primary source found outside this worktree:

- `/Users/duiba/Desktop/GEO_v2.0_AutoGEO整合版/AI_Query_Set_生成与管理方案_v2.md`
- Relevant section: `6.2 自动过滤规则（QF-01 ～ QF-06）`

Secondary context:

- `/Users/duiba/Desktop/mock数据/QuerysetDuiba.jsx`
- `docs/QUERYSET_MATRIX_SPEC.md`
- `docs/QUERYSET_MATRIX_WEIGHTING_SUMMARY.md`
- `backend/tests/test_queryset_contract.py`

Important: `/Users/duiba/Desktop/GEO_v2.0_AutoGEO整合版/geo-mvp-schedule-v6.2.html` and `/Users/duiba/Desktop/mock数据/数据实现逻辑.html` contain a conflicting older QF summary where QF-05 is described as "缺少实体或行业关键词". Do not use that as the source of truth unless product explicitly reverts to it. The formal md file above defines QF-05 as the formal-tone emotional-language filter.

## Generation Flow

The formal source defines the pre-storage flow as:

```text
二轴展开
  -> 模板调用
  -> 变量注入
  -> LLM 批量生成
  -> 字面去重（Exact Match）
  -> 硬规则过滤
  -> 入库
```

Semantic dedupe is explicitly deferred to Phase 2. MVP allows near-duplicate / semantically similar queries to coexist.

## Formal QF-01~06 Rules

| Rule | Trigger | Action |
|---|---|---|
| QF-01 | Query text length `< 8` or `> 80` characters | set status to `archived` |
| QF-02 | hits industry forbidden-word list | set status to `rejected`, record reason |
| QF-03 | contains advertising/marketing phrase markers, for example `免费`, `最好`, `第一`, `行业首选` | set status to `archived` |
| QF-04 | in an `oral_casual` matrix cell, hits formal-writing markers, for example `兹`, `贵司`, `敬请`, `核心差异`, `矩阵`, `综合评估` | set status to `archived` |
| QF-05 | in a `formal` matrix cell, hits strong-emotion markers, for example `啊啊啊`, `救救`, `崩溃了`, `坑死`, `垃圾` | set status to `archived` |
| QF-06 | under the same `entity_id`, text is exactly the same as an existing `active` Query | set status to `archived` by exact-match dedupe |

Tone comparison for QF-04/05 must use:

```text
get_tone(funnel_stage, query_pattern)
```

It must not use entity-level `dominant_tone`.

## Field Mapping Into Current Backend

The formal source uses old funnel names:

| Source field/value | Current backend field/value |
|---|---|
| `funnel_stage` | `journey_stage` |
| `tofu` | `problem_discovery` |
| `mofu` | `solution_evaluation` |
| `bofu` | `purchase_decision` |
| `decision_confirm` | split into `vendor_choice`, `internal_justification`, `purchase_risk`, `commercial_terms` |

Current backend matrix policy lives in:

- `backend/service/queryset_policy.py`
- `backend/service/rule_matrix.py`
- `backend/service/queryset.py`

Current output schema lives in:

- `backend/models/schemas.py`

## Required Acceptance Logic

To fully satisfy QF-01~06, the backend must support candidate-level filtering before freezing a QuerySet snapshot.

Minimum expected behavior:

- Preserve candidate status: `active`, `archived`, or `rejected`.
- Preserve rejection/archive reason, including the QF rule id.
- Only `active` queries should enter production inspection.
- `archived` / `rejected` candidates may be stored for audit, but must not silently appear as active QuerySet items.
- Exact text dedupe for QF-06 must compare against existing active queries for the same `entity_id`, not only inside the current generated batch.
- QF-04/05 require a matrix-cell tone function. The current code does not yet expose `get_tone(journey_stage, query_pattern)`.

Suggested normalized status payload:

```json
{
  "query_id": "q_001",
  "query_text": "做 App 积分体系有哪些现成的 SaaS 工具，不想自研太费人力",
  "lifecycle_status": "active",
  "quality_filter_status": "pass",
  "quality_filter_reasons": [],
  "journey_stage": "problem_discovery",
  "query_pattern": "category_rec",
  "matrix_cell_id": "problem_discovery:category_rec"
}
```

For a filtered candidate:

```json
{
  "query_text": "免费最好第一行业首选积分平台",
  "lifecycle_status": "archived",
  "quality_filter_status": "archived",
  "quality_filter_reasons": [
    { "rule_id": "QF-03", "reason": "contains advertising phrase marker: 免费 / 最好 / 第一 / 行业首选" }
  ]
}
```

## Current Code Coverage

As of this worktree, current backend code covers part of the broader QuerySet quality gate:

- required field normalization and Pydantic schema validation;
- duplicate `query_id` / duplicate `query_text` check inside a generated output;
- topic coverage against `brand_config.topics[].business_line`;
- non-degenerate intent distribution warning;
- matrix policy validation;
- core metric weight sum validation;
- competitor coverage warning;
- immutable QuerySet snapshot persistence;
- inspection lineage and report lineage contract tests.

Current backend code does not yet fully cover formal QF-01~06:

- no explicit QF-01 length gate;
- no configured industry forbidden-word table for QF-02;
- no advertising phrase marker gate for QF-03;
- no `get_tone()` function or tone-based QF-04/QF-05 filters;
- QF-06 only partially overlaps with duplicate text checks and does not yet compare against existing active queries by `entity_id`;
- no persisted per-candidate `archived` / `rejected` status with QF reason list before final freeze.

So the accurate judgment is:

```text
The current code has a QuerySet quality gate, but it is not yet a complete implementation of QF-01~06.
```

## Duiba Scenario Context

The 26-query Duiba scenario library originated from:

- `/Users/duiba/Desktop/mock数据/QuerysetDuiba.jsx`

Its business assumptions:

- Duiba focuses on mobile App user operation, interactive ads, points mall management, and retention tooling.
- Duiba is not primarily a WeChat mini-program / social-commerce SaaS vendor.
- Youzan / Weimob are treated as more WeChat/social-commerce oriented competitors.
- Scenario coverage includes internet App operations, financial App operations, travel / local services, content / video apps, technical integration, data warehouse sync, migration risk, internal justification, SLA / contract terms, and competitor comparison.

The current backend `backend/service/rule_matrix.py` intentionally uses a revised 26-query production set aligned with `docs/QUERYSET_MATRIX_WEIGHTING_SUMMARY.md`:

- `problem_discovery:scenario_explore`: 2
- `problem_discovery:category_rec`: 4
- `solution_evaluation:scenario_explore`: 3
- `solution_evaluation:category_rec`: 4
- `solution_evaluation:competitive_comp`: 4
- `purchase_decision:vendor_choice`: 3
- `purchase_decision:internal_justification`: 1
- `purchase_decision:purchase_risk`: 1
- `purchase_decision:commercial_terms`: 1 shadow
- `purchase_decision:competitive_comp`: 3

`solution_evaluation:deep_background` remains a defined matrix cell, but is not included in the current 26-query production set.

## Suggested Implementation Plan

1. Add `get_tone(journey_stage, query_pattern)` in `backend/service/queryset_policy.py`, preserving the old `funnel_stage` semantics through the current field mapping.
2. Add configurable marker lists for forbidden words, ad phrases, formal markers, and strong-emotion markers.
3. Add `apply_query_quality_filters(...)` before `QueryItem` freezing.
4. Store `quality_filter_status` and `quality_filter_reasons` either in first-class schema fields or inside `source_dimension_json` if schema churn should stay small.
5. Update `build_query_quality_report()` to expose QF pass/archive/reject counts.
6. Add contract tests for QF-01 through QF-06, including existing active query dedupe under the same `entity_id`.
