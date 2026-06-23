# Content Generation Harness PRD v2

## 结论摘要

这版方案方向正确，但距离交给开发落地还缺 3 个关键颗粒度：

1. **缺少可执行的数据合同**：目前只写了“新增 batch API / readiness gate”，但没有定义 batch_run、batch_item、readiness_result、错误码、状态流转和持久化位置。开发会各自理解，前后端容易对不上。
2. **失败处理过粗**：只写“失败继续，跳过出错的”，但没有区分输入不可生成、LLM 工具失败、fallback 生成、持久化失败、用户取消、归因无 comparison run 等情况。Harness 的核心价值恰恰是稳定编排，所以必须把工具失败后的分支写成规则。
3. **UI 只写入口，没有写操作闭环**：批量入口、结果列表、重试、禁用态、warning 展示、局部失败后的用户动作都没有定义。开发能做出页面，但用户不知道哪些失败可重试、哪些要补素材、哪些已经成功保存。

本 v2 优先把 P0 拆到可开发程度；P1/P2 保留方向，但补充依赖和接口边界。

---

## 一、P0 范围重新定义

### 目标

让用户在内容生成工作台一次选择多个 `action_id`，系统自动为每个 action 选择可用规则和模板，先做 Readiness Gate，再逐条生成内容版本。任意 action 失败不影响其他 action，最终形成一个可查询、可重试、可审计的 batch run。

### 不做

- 不自动触发新诊断。
- 不做 Quality Gate 或 Compliance Gate。
- 不自动发布内容。
- 不自动把失败项改写成成功项。
- P0 不做 3 变体并行生成，仅预留字段。

---

## 二、核心数据结构

### 1. batch_run

建议新增 `content_batch_runs_store = JsonStore("content_batch_runs.json")`。

```json
{
  "batch_run_id": "cb_12ab34cd56ef",
  "schema_version": "content_batch_run_v1",
  "brand_id": "brand_x",
  "brand_config_id": "bc_x",
  "contract_version": "dashboard_from_report_data_v1",
  "baseline_run_id": "run_before",
  "requested_action_ids": ["action_1", "action_2"],
  "mode": "fill_gaps_first",
  "status": "running",
  "summary": {
    "total": 2,
    "pending": 0,
    "running": 1,
    "succeeded": 1,
    "blocked": 0,
    "failed": 0,
    "fallback_succeeded": 0,
    "cancelled": 0
  },
  "items": [],
  "created_at": "2026-05-26T10:00:00Z",
  "started_at": "2026-05-26T10:00:00Z",
  "completed_at": null,
  "updated_at": "2026-05-26T10:00:10Z"
}
```

`status` 取值：

| 状态 | 含义 | 终态 |
|---|---|---|
| `queued` | 已创建，尚未开始 | 否 |
| `running` | 至少一个 item 正在处理 | 否 |
| `completed` | 全部 item 已结束，且至少一个成功 | 是 |
| `completed_with_errors` | 全部 item 已结束，但存在 failed/blocked | 是 |
| `failed` | batch 初始化失败，未进入 item 编排 | 是 |
| `cancelled` | 用户取消，未开始的 item 不再运行 | 是 |

### 2. batch_item

```json
{
  "batch_item_id": "cbi_12ab34cd56ef",
  "batch_run_id": "cb_12ab34cd56ef",
  "action_id": "action_1",
  "rule_id": "rule_content",
  "template_id": "tpl_product_capability",
  "status": "succeeded",
  "readiness": {
    "level": "warning",
    "fatal_reasons": [],
    "warnings": ["missing_case_studies"],
    "material_gaps": ["case_studies"],
    "degrade_strategy": "omit_case_section"
  },
  "content_version_id": "cv_12ab34cd56ef",
  "generation_source": "prompt_driven_backend",
  "generation_metadata": {
    "provider": "claude",
    "model": "claude-test",
    "web_search_mode": "responses_web_search",
    "duration_ms": 8421
  },
  "error": null,
  "started_at": "2026-05-26T10:00:01Z",
  "completed_at": "2026-05-26T10:00:10Z"
}
```

`item.status` 取值：

| 状态 | 含义 | 是否生成 content_version |
|---|---|---|
| `pending` | 等待处理 | 否 |
| `running` | 正在处理 | 否 |
| `blocked` | Readiness fatal，未调用 LLM | 否 |
| `succeeded` | LLM 成功并已持久化 | 是 |
| `fallback_succeeded` | LLM 失败，但 fallback 生成并已持久化 | 是 |
| `failed` | 工具或持久化失败，未得到可用版本 | 否 |
| `cancelled` | 用户取消或 batch 停止前未执行 | 否 |

### 3. error

所有失败 item 统一返回结构化错误，前端不要只展示字符串。

```json
{
  "error_code": "content_generation_upstream_failed",
  "stage": "generate_llm",
  "message": "content_generation failed: provider unavailable",
  "retriable": true,
  "tool_name": "invoke_llm_task",
  "raw_error_type": "RuntimeError",
  "action_id": "action_1",
  "rule_id": "rule_content",
  "template_id": "tpl_product_capability"
}
```

---

## 三、Readiness Gate v1

### 输入

`_check_readiness(contract, action, rule, templates) -> readiness_result`

### 输出

```json
{
  "level": "pass",
  "fatal_reasons": [],
  "warnings": [],
  "material_gaps": [],
  "degrade_strategy": null,
  "checks": {
    "brand_identity": "pass",
    "action_available": "pass",
    "rule_active": "pass",
    "template_available": "pass",
    "required_material": "pass",
    "baseline_run": "pass",
    "queryset": "pass"
  }
}
```

### 判定规则

| 检查项 | fatal | warning | pass |
|---|---|---|---|
| brand_identity | 无 `brand_name` 且无 `entity_name` | 只有 alias，无主名称 | 有品牌或实体主名称 |
| action_available | `action_id` 不存在 | 无 | action 存在 |
| rule_active | 指定 rule 不存在，或 active_rules_store 有数据但 rule 非 active | 仅能回退到 `cross_topic_rules` | 可解析到 active rule |
| template_available | `template_id` 指定但不可用于当前 action/material | 模板不是第一推荐但可用 | 模板可用 |
| required_material | selected_template.required_material_fields 全缺 | 缺 optional_material_fields | required 满足 |
| baseline_run | 无 `latest_run_id` / 无 completed diagnostic run | 有 baseline 但报告字段不完整 | baseline run 可用于归因 |
| queryset | 无 queryset_id 或 query 数为 0 | query 数不足或 QuerySet 版本缺失 | QuerySet 完整 |

### 行为

- `fatal`：item 标记 `blocked`，不调用 LLM，不写 `content_versions_store`。
- `warning`：允许调用 LLM，把 `readiness.material_gaps` 和 `degrade_strategy` 写入 content version 的 metadata。
- `pass`：正常生成。

### 降级策略

| warning | degrade_strategy | 生成要求 |
|---|---|---|
| `missing_case_studies` | `omit_case_section` | 不编造客户案例，改成适用场景描述 |
| `missing_certifications` | `avoid_authority_claims` | 不写认证/资质背书 |
| `queryset_incomplete` | `limit_query_claims` | 不写“覆盖所有用户问题”类表述 |
| `fallback_rule_used` | `mark_rule_source` | metadata 标记规则来源 |

---

## 四、批量编排逻辑

### 排序

默认 `mode = fill_gaps_first`：

1. 没有任何 content version 的 action 优先。
2. 有旧版本但 `contract_version` 过期的 action 次之。
3. 已有当前 contract 可用版本的 action 最后。

### 并发

P0 建议串行或低并发。

- 默认串行，最稳定，便于排查。
- 后续可加 `max_concurrency`，默认 `1`，上限 `3`。
- 同一 batch 中相同 `action_id + rule_id + template_id` 去重，只生成一次。

### 幂等

`POST /content/batch-generate` 支持可选 `request_id`。

- 同一 `brand_config_id + request_id` 已存在未终结 batch：直接返回原 `batch_run_id`。
- 同一 `brand_config_id + request_id` 已完成：返回原结果，不重复生成。
- 未传 `request_id`：每次创建新 batch。

---

## 五、工具失败处理

Harness 调用的“工具”包括：上下文加载、模板匹配、Readiness Gate、LLM 生成、fallback 生成、持久化、归因计算、前端 API 请求。处理规则如下。

| 阶段 | 可能失败 | item/batch 状态 | 是否继续下一个 | 是否可重试 | 用户提示 |
|---|---|---|---|---|---|
| `load_context` | 无 dashboard contract / 无 completed run | batch `failed` | 否 | 是 | 先完成一次诊断或刷新 Dashboard |
| `resolve_action` | action_id 不存在 | item `blocked` | 是 | 否 | 当前诊断结果中已没有该 action |
| `resolve_rule` | rule 不存在或非 active | item `blocked` | 是 | 视情况 | 选择 active rule 或重新跑 Rule Activation |
| `match_template` | template_id 不可用 | item `blocked` | 是 | 是 | 换推荐模板或补齐素材 |
| `readiness` | 必填素材缺失 | item `blocked` | 是 | 是 | 补齐 data_points/products 等素材后重试 |
| `generate_llm` | provider 超时/限流/空文本 | item `failed` 或 `fallback_succeeded` | 是 | 是 | 生成服务失败，可重试 |
| `fallback_generate` | fallback 也失败 | item `failed` | 是 | 是 | 降级生成失败，可重试 |
| `persist_content` | JsonStore 写入失败 | item `failed` | 是 | 是 | 内容未保存，请重试 |
| `persist_batch` | batch_run 写入失败 | batch `failed` | 否 | 是 | 批次记录保存失败 |
| `compute_attribution` | 无 comparison run | attribution `awaiting_retest` | 是 | 是 | 等下一次手动诊断后刷新归因 |
| `frontend_request` | 网络中断/用户取消 | UI `error` 或 `cancelled` | 不确定 | 是 | 后端状态可通过 batch-status 找回 |

### LLM 失败时的明确规则

当前代码已有 `ALLOW_CONTENT_GENERATION_FALLBACK`：

- 若环境变量未开启：LLM 失败时 item = `failed`，记录 `error_code=content_generation_upstream_failed`。
- 若环境变量开启：LLM 失败后尝试 fallback。
- fallback 成功：item = `fallback_succeeded`，保存 content version，但 UI 必须显示“降级生成”，默认不自动视为高质量结果。
- fallback 失败：item = `failed`。

### 内容保存失败时的规则

- 如果 LLM 已经返回文本但 `content_versions_store.upsert` 失败，不能把 item 记为成功。
- item = `failed`，`stage=persist_content`。
- 不在前端展示未保存文本作为版本；最多在错误详情中提示“生成结果未落库”。

### 用户取消

P0 可不做真正取消后端任务，但前端至少支持“停止轮询”。

P1 再新增：

- `POST /content/batches/{batch_run_id}/cancel`
- 已在 running 的 item 允许跑完。
- pending item 标记 `cancelled`。

---

## 六、API 合同

### 创建批量生成

`POST /api/v1/geo/content/batch-generate`

Request:

```json
{
  "brand_id": "brand_x",
  "brand_config_id": "bc_x",
  "action_ids": ["action_1", "action_2"],
  "rule_id": null,
  "template_overrides": {
    "action_1": "tpl_product_capability"
  },
  "mode": "fill_gaps_first",
  "request_id": "ui_20260526_001"
}
```

Response:

```json
{
  "batch_run_id": "cb_12ab34cd56ef",
  "status": "running",
  "summary": {
    "total": 2,
    "pending": 1,
    "running": 1,
    "succeeded": 0,
    "blocked": 0,
    "failed": 0,
    "fallback_succeeded": 0,
    "cancelled": 0
  },
  "items": []
}
```

P0 可同步跑完整批再返回最终结果；如果耗时超过前端可接受范围，则返回 `running` 并由前端轮询。推荐开发直接按可轮询模型实现，后续不用改接口。

### 查询批次状态

`GET /api/v1/geo/content/batches/{batch_run_id}`

Response 返回完整 `batch_run`。

### 重试失败项

`POST /api/v1/geo/content/batches/{batch_run_id}/retry`

Request:

```json
{
  "item_statuses": ["failed"],
  "action_ids": ["action_2"]
}
```

规则：

- 默认只重试 `failed`，不重试 `blocked`。
- `blocked` 需要用户补素材或换 rule/template 后重新发起 batch。

---

## 七、前端 UI 要求

### 内容生成页新增区域

1. Action 多选列表
   - 默认选中当前 action。
   - 提供“选择所有可生成 action”。
   - fatal blocked 的 action 禁用并显示原因。

2. 批量生成按钮
   - 文案：`批量生成选中内容`
   - loading：显示当前进度 `3/10`
   - 有 running batch 时禁用重复提交。

3. Readiness 预览
   - pass：绿色/正常。
   - warning：黄色，展示素材缺口和降级策略。
   - fatal：红色，展示阻断原因，不参与提交。

4. 结果列表
   - 每行展示 action、template、status、content_version_id、provider/model、耗时。
   - 成功项可点击切换到该版本。
   - failed 项提供“重试”。
   - blocked 项提供“查看缺口”，不提供直接重试。

### 状态文案

| 状态 | UI 文案 |
|---|---|
| `succeeded` | 已生成 |
| `fallback_succeeded` | 已降级生成 |
| `blocked` | 已阻断 |
| `failed` | 生成失败 |
| `running` | 生成中 |
| `cancelled` | 已取消 |

---

## 八、后端落地清单

### 文件

- `backend/service/storage.py`
  - 新增 `content_batch_runs_store = JsonStore("content_batch_runs.json")`

- `backend/service/content_generation.py`
  - 新增 `_check_readiness(contract, action, rule, templates)`
  - 新增 `batch_generate_async(payload)`
  - 新增 `get_content_batch_run(batch_run_id)`
  - 新增 `retry_content_batch_items(batch_run_id, payload)`
  - 给 `_persist_content_version` 增加可选 `batch_run_id`、`batch_item_id`、`readiness`、`variant_group_id`、`variant_type`

- `backend/router/geo.py`
  - 新增 `POST /content/batch-generate`
  - 新增 `GET /content/batches/{batch_run_id}`
  - 新增 `POST /content/batches/{batch_run_id}/retry`

- `src/api/geo.js`
  - 新增 `batchGenerateContent`
  - 新增 `fetchContentBatchStatus`
  - 新增 `retryContentBatchItems`

- `src/hooks/useContentGenerationViewModel.js`
  - 新增 batch 状态、选择状态、轮询逻辑、重试逻辑

- `src/pages/ContentGenerationPage.jsx`
  - 新增批量生成 UI、Readiness 预览、结果列表

### 测试

- `backend/tests/test_content_generation_batch.py`
  - Readiness fatal 阻断且不调用 LLM。
  - warning 允许生成且 metadata 写入 material gaps。
  - 5 个 action 中 1 个 LLM 失败，其余继续成功。
  - fallback 开启时 LLM 失败生成 `fallback_succeeded`。
  - fallback 关闭时 LLM 失败生成 `failed`。
  - `request_id` 幂等。
  - batch summary 计数正确。

- `src` 测试
  - API 客户端能解析 batch 错误结构。
  - viewModel 能合并 batch 生成出的 content versions。
  - failed/blocked/succeeded 三类 UI 状态可区分。

---

## 九、P1 Retest Harness 补充

Retest 不需要定时器，和“下一次手动诊断完成”对齐。

### 队列模型

建议直接复用 `effect_attribution_store` 的 `awaiting_retest` 状态，不急着新增独立队列表；Dashboard 查询时聚合：

- `status = awaiting_retest`
- 有 `baseline_run_id`
- 无 `comparison_run_id`
- content version 仍存在

### Dashboard 提醒

显示：

- 待复测版本数。
- 最早等待时间。
- 对应 action 列表。
- 按钮：`完成新诊断后刷新归因`。

刷新归因时批量调用已有 `compute_content_effect_attribution`，无 comparison run 继续保持 `awaiting_retest`。

---

## 十、P2 Variant / Rule Learning 边界

P2 不应和 P0 混做，但 P0 需预留字段：

- `variant_group_id`
- `variant_type`
- `batch_run_id`
- `batch_item_id`
- `readiness`

Rule Learning 的触发条件暂定：

- `effect_attribution.status = computed`
- `effect_delta.overall_direction = positive`
- `feedback_summary.net_score > 0`
- 至少跨 2 次 batch 或 2 个 action 验证后才可进入 promoted 候选

---

## 十一、P0 验收标准

1. 选 5 个 action 批量生成，最终 batch summary 正确，成功版本都写入 `content_versions_store`。
2. 一个 action Readiness fatal 时被标记 `blocked`，不影响其他 action。
3. 一个 action LLM 失败时，其他 action 继续；失败 item 有结构化 error。
4. fallback 开启时，LLM 失败项可产生 `fallback_succeeded`，content version metadata 保留原始失败原因。
5. 前端能展示 pass/warning/fatal、成功/失败/降级生成、单项重试入口。
6. 重新打开页面后，可通过 `GET /content/batches/{batch_run_id}` 找回批次状态。
7. 归因无 comparison run 时，不算失败，保持 `awaiting_retest` 并在 Dashboard 提醒。
