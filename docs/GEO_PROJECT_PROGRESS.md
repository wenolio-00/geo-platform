# GEO Platform 项目进展

## 本轮完成内容（2026-05-09）

### 数据契约细化与杭州兑吧 Mock Data

将数据契约从“展示型 mock”升级为可落地的关键词/Prompt 端颗粒度，并以杭州兑吧网络科技有限公司为示例品牌，让本地能跑通完整流程。

**核心改动：**

1. **落地级关键词端契约** — 在 `src/mock/data.js` 中新增：
   - `SCENARIOS`（6个业务场景）：积分商城管理工具、会员权益运营平台、互动广告接入、金融场景运营、竞品对比与选型、权威信源覆盖
   - `KEYWORD_INTENTS`（12个落地意图）：每个意图包含 `intent_id`、`prompt_templates`、`must_match_entities`、`evaluation_rules`、`priority`
   - `SOURCE_TYPES`（6类信源）：官网、客户案例/白皮书、门户/新闻、技术社区、UGC/内容平台、问答平台
   - `BENCHMARKS`（行业标杆值）：Answer Share、信源覆盖率、场景覆盖率等核心指标的对手均值与 P75 基准

2. **Dashboard 数据契约**（只做数据，不做新 UI）：
   - `getDashboardContract()` 返回关键指标、关键问题（指标异常链路 + 竞品/标杆对比）、优化动作候选、跨话题通用规则、优化前后模拟
   - 关键问题链路：每个问题包含 `abnormal_metric`（兑吧当前值 vs 竞品均值 vs 行业标杆）、`business_pain`、`evidence`（关联 intent + 平台 + Prompt 样例）、`root_cause`、`recommended_actions`、`expected_metric_lift`
   - 3个跨话题优化规则：Claim-Fact-Proof 三段式、竞品能力边界对比、金融场景锚定

3. **每个现有数据产物补齐关键词端明细**：
   - `getOverview()` — 增加 `contract.keyword_scope`，包含场景数/意图数/Prompt 模板数、核心异常摘要
   - `getCompetitiveBrands()` — 每个品牌增加 `intent_breakdown`，竞品均值与兑吧 gap
   - `getModelBreakdown()` — 每个平台增加 `intent_breakdown`（提及率、平均位置、上下文类型、证据数）
   - `getBrandHistory()` — 增加 `by_metric` 和 `by_intent` 趋势，支持后续优化前后对比
   - `getCategoryHeatmap()` — 品牌和场景改成兑吧业务与竞品池
   - `getZeroAttribution()` — 改成低可见意图诊断，诊断动作关联信源类型

## 修改/新增文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/mock/data.js` | 重写 | 从信用卡示例完全替换为杭州兑吧；新增 SCENARIOS/KEYWORD_INTENTS/SOURCE_TYPES/BENCHMARKS；新增 getDashboardContract() |
| `src/api/geo.js` | 修改 | 新增 `fetchDashboardContract()` 导出 |
| `src/pages/VisibilityPage.jsx` | 修改 | 副标题轻量更新为“场景化回答占有率” |
| `docs/GEO_PROJECT_PROGRESS.md` | 新增 | 项目进展文档 |
| `src/prompts/rule_activation_evaluator_prompt_zh.md` | 新增 | 规则激活评估器中文 Prompt |
| `src/prompts/rule_activation_evaluator_prompt_en.md` | 新增 | 规则激活评估器英文 Prompt |
| `src/config/rule_activation_evaluator.config.json` | 新增 | 08.5 规则激活评估器配置 |
| `src/schemas/rule_activation_evaluation.schema.json` | 新增 | 规则激活评估输出 JSON Schema |
| `docs/rule_activation_integration_guide.md` | 新增 | Baseline Rule Activation Gate 集成说明 |
| `docs/rule_activation_flow_patch.md` | 新增 | GEO v6.2 流程补丁 |

### Rule Activation Evaluator（2026-05-09 追加）

已加入 `geo_rule_activation_package.zip` 中的规则激活评估器资产，并将其落在现有流程的 08 与 13 之间：

```text
08 Rule Extraction · 平台内容偏好规则提取
  ↓
08.5 Rule Activation Evaluator · 规则激活评估器
  ↓
13 生成 ActionTask · 按优先级互斥触发
```

核心逻辑已同步进 mock contract：Rule Extraction 生成的自动规则默认只进入 `platform_rules_store` 且状态为 `candidate`；`Rule Activation Evaluator` 会先与 `baseline_rules_store` 中的 Baseline Rule 对比，只有在 `effect_delta`、`utility_check`、平台拆分表现和风险检查都通过时，才写入 `active_rules_store`。ActionTask / 内容生成入口只读取 `active_rules_store`，如果没有匹配的 active auto rule，则回退到 active Baseline Rule。

当前前端落点：

- `getDashboardContract().rule_activation` 暴露 `baseline_rules_store`、`platform_rules_store`、`rule_activation_evaluations`、`active_rules_store`。
- `/content/generation` 的规则选择已改为读取 `active_rules_store`，并显示规则来源。
- 候选自动规则不会直接出现在内容生成规则下拉框中，除非有对应 activation evaluation 通过。

## 当前页面入口

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | 重定向 → `/brand/config` | — |
| `/brand/config` | 品牌配置页 | 兑吧预填数据（entity_name、aliases、industry_segments、topics、competitors） |
| `/dashboard` | Dashboard | 仍为旧版 UI（关键问题/信源 gap/平台健康度/调性）；新契约已备好，待接入 |
| `/monitor/visibility` | AI 可见度监测 | 已切换为兑吧数据；卡片指标/平台柱图/趋势/分模型/竞品排名均能正常加载 |

启动：`npm run dev` → http://127.0.0.1:5173/

## 未来待迭代板块

### Rule Store Lifecycle Design（未来迭代）

GEO 平台后续可将规则库设计为“持续累积、持续验证、持续衰减、持续更新”的动态规则资产，而不是一次性 Prompt 经验集合。

该能力当前定位为未来迭代方向，尚未作为已落地功能实现。设计目标是把每一次品牌诊断、内容优化和复测都记录为一次可追踪实验，并基于巡检结果、品牌样本、行业样本和复测数据，逐步沉淀可复用的内容优化规则。

#### 规则输入与规则体系

品牌层面的观测数据建议作为规则生成的输入层，而不是最终规则层。规则体系的长期目标可以收敛为三层：

| 层级 | 定义 | 主要作用 |
|---|---|---|
| `brand_level observations` | 单个品牌的 Query、内容、巡检和复测结果 | 作为候选规则的输入来源，帮助识别品牌特有表达、边界条件和临时优化策略 |
| `industry_level` | 同行业多个品牌的共性结果 | 总结某行业在 AI 平台回答中的稳定内容偏好，例如金融、保险、SaaS、医疗 |
| `platform_level` | 同一平台下跨品牌、跨行业仍稳定成立的规律 | 抽象不同 AI 平台自身的引用偏好，例如 DeepSeek、Kimi、豆包、通义千问、文心一言、混元元宝 |
| `cross_platform_level` | 跨平台后仍然稳定成立的规律 | 提炼不同平台共同认可的内容组织方式、事实表达方式和证据结构 |

#### 规则生命周期

完整生命周期建议如下：

```text
candidate
→ validated
→ promoted
→ active
→ monitoring
→ suspected_drift
→ deprecated
→ archived
```

各状态含义：

| 状态 | 含义 |
|---|---|
| `candidate` | 从单次或少量观察中提取出的候选规则，尚未完成复测验证 |
| `validated` | 已在限定范围内通过复测，确认对指标有正向影响 |
| `promoted` | 从品牌级或行业级经验晋级为更高层级规则的过渡状态 |
| `active` | 当前可被 ActionTask 调用的有效规则 |
| `monitoring` | 规则仍可用，但关键指标开始出现波动，需要进入观察窗口 |
| `suspected_drift` | 多个巡检窗口显示规则可能失效，需要专项复测确认 |
| `deprecated` | 复测确认效果下降或失效，不再作为默认优化依据 |
| `archived` | 历史规则归档，仅用于审计、回溯和模型行为变化分析 |

#### 数据分层建议

未来实现时建议先保留三层核心数据，确保规则能够被追踪、验证和更新：

```text
Observation Layer
→ Rule Snapshot Layer
→ Validation Event Layer
```

1. **Observation Layer**
   - 记录每次 AI 返回的原始观察事实。
   - 建议字段：`platform`、`model_used`、`model_version`、`request_at`、`returned_at`、`query_id`、`prompt_template_id`、`brand_id`、`content_version_id`、`answer_share`、`position_index`、`mention_context`、`sentiment_score`、`utility_check`、`source_url_types`。

2. **Rule Snapshot Layer**
   - 记录某条规则在某一时间点的版本、范围、状态和可信度。
   - 建议字段：`rule_id`、`rule_version`、`scope`、`status`、`applicable_platforms`、`applicable_action_types`、`confidence_score`、`decay_score`、`evidence_count`、`brand_count`、`extracted_at`、`last_validated_at`。

3. **Validation Event Layer**
   - 记录规则复测结果，用于判断规则是否仍然有效。
   - 建议字段：`validation_id`、`rule_id`、`rule_version`、`validated_at`、`platform`、`query_set_id`、`content_version_before`、`content_version_after`、`before_metric`、`after_metric`、`effect_delta`、`is_still_effective`、`drift_signal`。

#### ActionTask 调用逻辑

ActionTask 不应默认调用“最新规则”，而应优先选择最近验证有效、置信度高、衰减低、效果提升稳定，并且与当前 `platform`、`industry_segment`、`action_type` 匹配的 `active` 规则。

当多条规则同时命中时，建议按以下顺序排序：

1. `status = active`
2. `confidence_score` 高
3. `decay_score` 低
4. `last_validated_at` 近
5. 历史 `effect_delta` 稳定为正
6. 适用范围更贴近当前品牌或行业

#### Drift Detection

Drift Detection 的目标不是在指标波动时立即废弃规则，而是识别“内容未变化但 AI 平台引用偏好发生变化”的情况。

当同一平台、同一批 Query、同一内容版本在内容未更新的情况下，连续多个巡检窗口出现 `answer_share`、`position_index`、`mention_context`、`sentiment_score`、`utility_check` 或 `source_url_types` 异常波动时，规则应先进入 `monitoring` 状态。

如果后续观察仍显示波动扩大，再进入 `suspected_drift`。只有专项复测确认规则效果下降或失效后，才降低 `confidence_score`、提高 `decay_score`，并将规则标记为 `deprecated`。同时触发新一轮 Rule Extraction，生成新的 `rule_version`，避免规则库只累积不更新。

#### MVP 先做什么

未来迭代时，建议先实现最小可行版本，避免在早期引入过重的规则治理复杂度：

1. 先落三层数据：`Observation`、`Rule Snapshot`、`Validation Event`
2. 规则状态先保留：`candidate`、`active`、`monitoring`、`deprecated`
3. 先跑通核心字段：`status`、`confidence_score`、`decay_score`、`last_validated_at`
4. ActionTask 先按 `active_rules_store + platform + action_type` 选择规则；没有匹配时回退 `baseline_rules_store`
5. 后续再补 `validated`、`promoted`、`suspected_drift`、`archived` 等完整状态

#### 更新优先级提醒

下次继续更新这块内容时，建议优先级依次是：

1. 先补 **MVP 数据结构**，确保可落地
2. 再补 **规则验证与状态流转**，确保能持续更新
3. 最后补 **Drift Detection 细节**，避免过早复杂化

> 结论：规则库不是“越积越多”的静态集合，而是一个会沉淀、会验证、会晋级、会衰减、会更新的动态规则资产。


## 给 Codex 的接手提示

- **所有 mock 数据集中在 `src/mock/data.js`**，不拆分文件。后端开发参考此文件的数据结构，不删除/不重命名
- **`src/api/geo.js` 是 mock → 真实 API 的唯一切换点**，新增 API 只需在此文件添加函数，不要直接在组件里 fetch
- **Dashboard 新契约在 `getDashboardContract()`**，结构为 `key_metrics[]` / `key_issues[]` / `optimization_actions[]` / `cross_topic_rules[]` / `before_after_simulation[]`，UI 接入时应从此函数读取，不要硬编码
- **Rule Activation Gate 已接入 `getDashboardContract().rule_activation`**，ActionTask/内容生成应读取 `active_rules_store`，不要直接使用 `platform_rules_store` 的 candidate 自动规则
- **规则激活资产位置**：Prompt 在 `src/prompts/`，配置在 `src/config/rule_activation_evaluator.config.json`，输出 Schema 在 `src/schemas/rule_activation_evaluation.schema.json`，集成说明在 `docs/rule_activation_integration_guide.md`
- **BrandConfigPage 已有兑吧预填常量 `DUIBA`**，修改品牌配置时应以这里的语义为准（业务线：积分商城、会员权益、互动广告；竞品：有赞、微盟、星耀、灵智）
- **VisibilityPage 依赖 `overview.summary/trend_7d/platform_visibility/mention_context` 和 `competitive.rows.global/categories/platform_breakdown`**，修改这些字段的 shape 时需要同步检查页面渲染
- **CLAUDE.md** 中记载了当前项目定位、目录结构、Mock → 真实 API 对接指南，接手时应先读
- `docs/AGENT_RULES.md`、`docs/AUTO_GEO_LITE_RULES.md` 仍为空；`rule_activation_*` 文档已可作为规则激活链路参考
