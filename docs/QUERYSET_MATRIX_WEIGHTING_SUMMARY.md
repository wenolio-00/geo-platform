# QuerySet 矩阵权重与命名调整总结

## 1. 本轮讨论结论

本轮讨论围绕 QuerySet 双轴矩阵的格子分配、权重合理性、核心趋势口径和阶段命名展开。核心结论是：当前 QuerySet 不能只按传统 ToFu / MoFu / BoFu 漏斗做简单映射，而应该以“用户真实决策阶段 + 问题类型 + 指标用途”共同决定权重和治理层级。

最终建议：

- 用更符合人类理解的阶段变量替代 `tofu / mofu / bofu`。
- QuerySet 矩阵不追求所有格子均匀填满，而应按业务价值加权。
- `core_anchor` 不应由阶段天然决定，而应由 query 是否适合长期趋势比较决定。
- 主 Answer Share / GVI 应主要由“推荐、对比、选型”类 query 构成。
- 泛方法论、行业背景、商务 FAQ 等 query 应更多用于探索覆盖和报告解释。

本轮已修正 3 个容易让实现跑偏的漏洞：

1. **权重口径不再并列**：矩阵格权重是唯一计算源，模块权重只做解释口径。
2. **字段语义不再互相覆盖**：`query_layer`、`metric_scope`、`journey_stage` 分别表达治理层、指标用途和用户阶段。
3. **主指标不再等权混算**：Answer Share / GVI 只消费 `core_trend` 样本，并按归一化后的 `metric_weight` 加权。

---

## 2. 阶段命名调整

原有命名：

```python
tofu
mofu
bofu
```

建议替换为：

```python
DISCOVERY = "problem_discovery"
EVALUATION = "solution_evaluation"
DECISION = "purchase_decision"
```

对应关系：

| 原阶段 | 新常量 | 新值 | 中文含义 | 用户状态 |
|---|---|---|---|---|
| `tofu` | `DISCOVERY` | `problem_discovery` | 问题发现期 | 用户意识到问题，正在找方向 |
| `mofu` | `EVALUATION` | `solution_evaluation` | 方案评估期 | 用户开始比较方案、能力、风险、案例 |
| `bofu` | `DECISION` | `purchase_decision` | 采购决策期 | 用户接近选型，关注供应商、成本、迁移、合同、内部说服 |

这样改的原因：

- `tofu / mofu / bofu` 是营销漏斗黑话，不够直观。
- `problem_discovery / solution_evaluation / purchase_decision` 能直接表达用户真实状态。
- 新命名更适合作为 QuerySet 矩阵、报告、后端字段和客户解释口径的长期字段。

---

## 3. 双轴矩阵逻辑

最新版 QuerySet 矩阵建议由两个主轴组成：

```text
journey_stage × query_pattern
```

其中：

```text
journey_stage = problem_discovery | solution_evaluation | purchase_decision
query_pattern = scenario_explore | category_rec | competitive_comp | deep_background | vendor_choice | internal_justification | purchase_risk | commercial_terms
```

示例矩阵格：

```text
problem_discovery:scenario_explore
problem_discovery:category_rec
solution_evaluation:category_rec
solution_evaluation:competitive_comp
purchase_decision:vendor_choice
purchase_decision:competitive_comp
```

每个 query 应至少携带：

```json
{
  "journey_stage": "solution_evaluation",
  "query_pattern": "competitive_comp",
  "matrix_cell_id": "solution_evaluation:competitive_comp",
  "metric_scope": "core_trend",
  "metric_weight": 0.25,
  "query_layer": "core_anchor"
}
```

---

## 4. 权重分配原则

本轮讨论确定的核心原则是：

```text
权重 = 用户真实发生频率 × AI 推荐触发概率 × 商业决策价值 × 趋势可比性
```

因此不应按矩阵格平均分配，也不应只按阶段平均分配。

判断一个矩阵格权重高低时，要看：

1. 用户是否真实会这样问。
2. AI 是否容易自然推荐品牌或服务商。
3. 该问题是否接近商业决策。
4. 该问题是否适合长期跨期复测。
5. 该问题是否能解释品牌差异化。

---

## 5. 三层指标口径

QuerySet 建议拆成三层，而不是所有 query 等权进入主指标。

| 层级 | 用途 | 是否进入主 Answer Share / GVI 趋势 |
|---|---|---|
| Core Trend | 核心趋势指标，长期可比 | 是 |
| Supporting Trend | 辅助解释指标，补充业务切面 | 部分进入或单独展示 |
| Exploratory Coverage | 探索覆盖，发现机会和盲区 | 否 |

### Core Trend

用于主指标，例如：

- Answer Share
- GVI
- 品牌自然推荐率
- 竞品排名
- 跨期趋势
- 规则激活后的 effect_delta

### Supporting Trend

用于解释能力认知和业务切面，例如：

- 金融合规
- 技术接入
- 数据回传
- 迁移风险
- 成本风险

### Exploratory Coverage

用于发现机会和盲区，例如：

- 泛方法论问题
- 行业背景问题
- 商务 FAQ
- AI 认知偏差
- 内容缺口分析

---

## 6. 模块权重解释口径

以下模块权重只用于客户解释和报告叙事，不作为独立计算源。真实计算以第 7 节的矩阵格权重表为准。

| 模块 | 建议权重 | 作用 |
|---|---:|---|
| 推荐入口类 | 30% | 衡量 AI 是否会主动推荐品牌 |
| 竞品对比类 | 25% | 衡量 AI 是否理解品牌差异化 |
| 决策选型类 | 20% | 衡量临近采购时品牌是否被认可 |
| 方案评估类 | 15% | 衡量能力、安全、接入、行业适配认知 |
| 问题发现 / 背景探索类 | 10% | 衡量早期认知覆盖，但不主导指标 |

核心倾向：

```text
不要让泛方法论题主导 Answer Share；
要让推荐、对比、选型成为主指标骨架。
```

---

## 7. 矩阵格权重表

| 阶段 | Pattern | Matrix Cell | 建议权重 | 层级 | 说明 |
|---|---|---|---:|---|---|
| DISCOVERY | `scenario_explore` | `problem_discovery:scenario_explore` | 5% | Exploratory Coverage | 方法论问题多，不一定触发品牌推荐 |
| DISCOVERY | `category_rec` | `problem_discovery:category_rec` | 15% | Core Trend | 早期自然推荐入口，适合测 AI 是否知道品牌属于该赛道 |
| EVALUATION | `scenario_explore` | `solution_evaluation:scenario_explore` | 10% | Supporting Trend | 看安全、接入、数据、性能等能力认知 |
| EVALUATION | `category_rec` | `solution_evaluation:category_rec` | 15% | Core Trend | 中期精准推荐入口，比早期推荐更贴近采购 |
| EVALUATION | `deep_background` | `solution_evaluation:deep_background` | 5% | Exploratory Coverage | 看行业认知，但不应主导推荐率 |
| EVALUATION | `competitive_comp` | `solution_evaluation:competitive_comp` | 15% | Core Trend | 品牌差异化最容易在这里被识别 |
| DECISION | `vendor_choice` | `purchase_decision:vendor_choice` | 10% | Core Trend | 直接衡量“最后选谁” |
| DECISION | `internal_justification` | `purchase_decision:internal_justification` | 5% | Core Trend | 衡量品牌能否支撑内部汇报和说服 |
| DECISION | `purchase_risk` | `purchase_decision:purchase_risk` | 5% | Supporting Trend | 迁移、实施、历史数据等风险问题 |
| DECISION | `commercial_terms` | `purchase_decision:commercial_terms` | 5% | Exploratory Coverage | 定价、SLA、合同，商业价值高但品牌触发不稳定，默认 `shadow` |
| DECISION | `competitive_comp` | `purchase_decision:competitive_comp` | 15% | Core Trend | 临门一脚竞品对比，商业价值最高之一 |

合计：100%。

---

## 8. 哪些进入 Core Trend

建议进入核心趋势的矩阵格：

| Matrix Cell | 原因 |
|---|---|
| `problem_discovery:category_rec` | 早期自然推荐入口 |
| `solution_evaluation:category_rec` | 中期精准推荐入口 |
| `solution_evaluation:competitive_comp` | 品牌差异化识别 |
| `purchase_decision:vendor_choice` | 最终选型 |
| `purchase_decision:internal_justification` | 内部说服 |
| `purchase_decision:competitive_comp` | 临门一脚竞品对比 |

Core Trend 合计权重：

```text
15 + 15 + 15 + 10 + 5 + 15 = 75%
```

这 75% 是主 Answer Share / GVI 的核心计算基础。落到单条 query 时，先按当前 QuerySet 中出现的 Core Trend 矩阵格重新归一，再除以该格内 query 数量，写入 `metric_weight`。Supporting / Exploratory query 的 `metric_weight = 0`，不直接拉高或拉低主指标。

---

## 9. 哪些只做探索覆盖

建议不进入主趋势，只用于报告解释的矩阵格：

| Matrix Cell | 原因 |
|---|---|
| `problem_discovery:scenario_explore` | 偏方法论，不一定触发品牌 |
| `solution_evaluation:deep_background` | 偏行业认知，不是直接推荐 |
| `purchase_decision:commercial_terms` | 偏商务常识，品牌触发不稳定 |

这些 query 适合用于：

- 机会发现
- 内容缺口分析
- 话题覆盖分析
- AI 认知偏差识别
- 报告中的辅助解释

但不应该直接拉低或拉高主 Answer Share。`purchase_decision:commercial_terms` 默认进入 `shadow`，保留在 QuerySet 快照中用于解释和后续扩展，但不进入常规巡检样本。

---

## 10. 对当前 26 条 Query 的建议分配

当前 26 条 query 采用“条数不等于权重”的结构：条数保证业务覆盖，权重只由矩阵格策略决定。

| Matrix Cell | 建议条数 | 权重约等 |
|---|---:|---:|
| `problem_discovery:scenario_explore` | 2 | 5% |
| `problem_discovery:category_rec` | 4 | 15% |
| `solution_evaluation:scenario_explore` | 3 | 10% |
| `solution_evaluation:category_rec` | 4 | 15% |
| `solution_evaluation:deep_background` | 0 | 5% |
| `solution_evaluation:competitive_comp` | 4 | 15% |
| `purchase_decision:vendor_choice` | 3 | 10% |
| `purchase_decision:internal_justification` | 1 | 5% |
| `purchase_decision:purchase_risk` | 1 | 5% |
| `purchase_decision:commercial_terms` | 1 shadow | 5% |
| `purchase_decision:competitive_comp` | 3 | 15% |

合计 26 条。`solution_evaluation:deep_background` 暂不进入当前 26 条生产集，保留矩阵格和权重定义，后续扩展 QuerySet 时再补。

---

## 11. 对当前逻辑的关键批评

### 11.1 已修正：当前矩阵更像业务清单，而不是严格抽样矩阵

当前 26 条 query 的设计有很强业务直觉，但更像“兑吧业务理解版 Query 清单”，还不是一个严谨的 Answer Share 抽样框架。

主要原因：

- 矩阵格权重已成为唯一计算源。
- 泛方法论和商务 FAQ 已从主指标中剥离。
- 推荐、对比、选型成为 `core_trend` 主骨架。
- `decision_confirm` 已拆成 `vendor_choice`、`internal_justification`、`purchase_risk`、`commercial_terms`。

### 11.2 已修正：`DISCOVERY = core_anchor` 不成立

旧逻辑相当于：

```text
problem_discovery -> core_anchor
solution_evaluation -> adaptive
purchase_decision -> adaptive
```

这个映射不合理，现已移除。`core_anchor` 由矩阵格策略决定，不再由 `journey_stage` 推导。

真正适合做 `core_anchor` 的，不是某个阶段，而是满足以下条件的 query：

- 品牌中性或稳定竞品对比；
- 长期稳定；
- 能自然触发供应商推荐；
- 不是一次性项目问题；
- 能代表核心商业需求；
- 跨期比较不会因为短期事件大幅漂移。

因此：

```text
problem_discovery 可以贡献 core_anchor，
但 problem_discovery 不天然等于 core_anchor。
```

### 11.3 高稳定推荐 / 对比题更适合做 core_anchor

更适合做 `core_anchor` 的是：

```text
problem_discovery:category_rec
solution_evaluation:category_rec
solution_evaluation:competitive_comp
purchase_decision:vendor_choice
purchase_decision:competitive_comp
```

不适合做 `core_anchor` 的是：

```text
problem_discovery:scenario_explore
solution_evaluation:deep_background
purchase_decision:commercial_terms
```

---

## 12. 建议的字段设计

不要只依赖 `query_layer`，而是明确拆出阶段、格子、指标用途和权重：

```json
{
  "journey_stage": "solution_evaluation",
  "query_pattern": "competitive_comp",
  "matrix_cell_id": "solution_evaluation:competitive_comp",
  "metric_scope": "core_trend",
  "metric_weight": 0.25,
  "query_layer": "core_anchor"
}
```

字段职责：

| 字段 | 含义 |
|---|---|
| `journey_stage` | 用户所处决策阶段 |
| `query_pattern` | 问题类型 |
| `matrix_cell_id` | 双轴矩阵格 ID |
| `metric_scope` | 是否进入核心趋势或只做辅助 / 探索 |
| `metric_weight` | 单条 query 对主指标的归一化权重；非 Core Trend 为 0 |
| `query_layer` | QuerySet 治理层级，如 core_anchor / adaptive / experimental |

---

## 13. 最终推荐规则

新版规则应改成：

```text
core_anchor 不由 journey_stage 决定；
core_anchor 由 query 是否适合长期趋势比较决定。
```

更具体地说：

| Query 类型 | 建议治理层级 |
|---|---|
| 品牌中性推荐题 | `core_anchor` |
| 高稳定竞品对比题 | `core_anchor` |
| 供应商选择题 | `core_anchor` |
| 内部说服题 | `core_anchor` 或 `adaptive` |
| 安全、接入、数据、迁移风险题 | `adaptive` / `supporting_trend` |
| 泛方法论题 | `exploratory` |
| 行业背景研究题 | `exploratory` |
| 商务 FAQ | `adaptive` / `exploratory` |

最终一句话：

```text
QuerySet 的核心趋势不应由早中晚阶段决定，而应由“稳定、可复测、能触发供应商推荐、具备商业解释力”的问题决定。
```
