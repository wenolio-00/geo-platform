# GEO 现有流程加入 Baseline Rule Activation Gate 的集成说明

## 1. 要加入的是什么

本次新增模块建议命名为：

```text
Rule Activation Evaluator / 规则激活评估器
```

它的作用不是生成内容，而是在 **Auto-generated Rule Set** 进入内容生产前，判断它是否真的优于用户手动维护的 **Baseline Rule**。

MVP 阶段默认原则：

```text
没有充分数据证明自动规则更好时，继续使用 Baseline Rule。
```

---

## 2. 插入现有流程的位置

建议插入在：

```text
08 Rule Extraction · 平台内容偏好规则提取
        ↓
08.5 Rule Activation Evaluator · 规则激活评估器
        ↓
13 生成 ActionTask · 按优先级互斥触发
```

也就是说，Rule Extraction 产出的 platform_rules_store 不再直接被 ActionTask 调用，而是先进入 Rule Activation Evaluator。

---

## 3. 为什么放在这里

现有流程中，Rule Extraction 会提取平台内容偏好规则，并写入 platform_rules_store。ActionTask 生成时会从 platform_rules_store 拉取对应 action_type 的最新规则。

新增 Rule Activation Evaluator 后，流程改为：

1. Rule Extraction 生成候选规则；
2. Rule Activation Evaluator 将候选规则与 Baseline Rule 对比；
3. 只有通过评估的规则才进入 active_rules_store；
4. ActionTask 只读取 active_rules_store，而不是直接读取所有 platform_rules_store。

这样可以避免 MVP 阶段因样本不足，把不稳定的自动规则直接放入内容生产。

---

## 4. 建议新增数据表 / 配置对象

### 4.1 baseline_rules_store

用于存储用户手动输入的 Baseline Rule。

| 字段 | 说明 |
|---|---|
| rule_id | Baseline Rule ID |
| rule_version | 版本号，例如 baseline_v1.0 |
| rule_content | 规则正文 |
| maintained_by | 维护人 |
| updated_at | 更新时间 |
| status | active / archived |

### 4.2 rule_activation_evaluations

用于记录每次自动规则是否被启用。

| 字段 | 说明 |
|---|---|
| evaluation_id | 唯一 ID |
| baseline_rule_version | 对比的 Baseline Rule 版本 |
| auto_rule_version | 候选自动规则版本 |
| platform | 平台，可为空表示全局 |
| query_pattern | QuerySet 场景 |
| action_type | ActionTask 类型 |
| decision | activate_global / activate_platform_specific / activate_task_specific / merge_into_baseline / keep_baseline / reject_rule_set |
| confidence | high / medium / low |
| reason | 判断原因 |
| metric_snapshot | 指标快照 |
| risk_check | 风险检查结果 |
| created_at | 评估时间 |

### 4.3 active_rules_store

用于存储真正可被内容生产调用的规则。

| 字段 | 说明 |
|---|---|
| active_rule_id | 激活规则 ID |
| source_type | baseline / auto_generated / merged |
| rule_version | 规则版本 |
| platform | 适用平台 |
| query_pattern | 适用 Query 场景 |
| action_type | 适用 ActionTask 类型 |
| rules_json | 结构化规则 |
| activated_by_evaluation_id | 对应评估记录 |
| activated_at | 激活时间 |
| status | active / archived |

---

## 5. Decision Engine 和 ActionTask 的改动

### 当前逻辑

```text
Decision Engine → 生成 ActionTask → 从 platform_rules_store 拉取平台规则
```

### 建议改成

```text
Decision Engine → 生成 ActionTask → 从 active_rules_store 拉取已激活规则
```

如果没有匹配到 active auto rule：

```text
fallback = baseline_rule
```

这样 ActionTask 永远有规则可用，但不会被不稳定的自动规则污染。

---

## 6. 规则启用策略

### MVP 默认策略

| 情况 | 系统动作 |
|---|---|
| 自动规则缺少效果数据 | keep_baseline |
| 自动规则只在单平台有效 | activate_platform_specific |
| 自动规则只适合某类任务 | activate_task_specific |
| 自动规则有部分价值但整体不稳定 | merge_into_baseline |
| 自动规则造成 utility_check 下降 | reject_rule_set |
| 自动规则存在编造或证据风险 | reject_rule_set |
| 自动规则多平台、多场景稳定优于 Baseline | activate_global |

---

## 7. 前端页面建议

在后台管理页中增加一个轻量配置页：

```text
规则管理
├── Baseline Rule
├── Auto-generated Rule Set
├── Rule Activation Evaluation
└── Active Rules
```

MVP 阶段最小可实现：

1. Baseline Rule 文本输入框；
2. 当前 Auto-generated Rule Set 展示；
3. 评估结果展示；
4. 人工确认按钮：接受 / 合并 / 拒绝；
5. 版本记录。

---

## 8. 推荐接入步骤

### Step 1：先加入 Baseline Rule 存储
把用户手动维护的 Baseline Rule 存入 baseline_rules_store。

### Step 2：Rule Extraction 输出不直接进入内容生产
Rule Extraction 继续生成 platform_rules_store，但默认 status = candidate。

### Step 3：调用 Rule Activation Evaluator Prompt
把 baseline_rule、auto_generated_rule_set、evaluation_data、project_context 传入本包里的 prompt。

### Step 4：保存评估结果
将模型输出写入 rule_activation_evaluations。

### Step 5：生成 active_rules_store
根据 decision 写入 active_rules_store：

- activate_global：写入全局 active rule；
- activate_platform_specific：按平台写入；
- activate_task_specific：按 action_type 写入；
- merge_into_baseline：进入人工确认后更新 baseline_rule_version；
- keep_baseline：不写入自动规则；
- reject_rule_set：标记候选规则 rejected。

### Step 6：ActionTask 只读取 active_rules_store
如果没有命中 active rule，则读取 baseline_rules_store 的 active version。

---

## 9. 与后续 Phase 2 的衔接

Phase 2 可以进一步升级为：

1. Baseline Agent 自动联网更新 Baseline Rule；
2. 基于 effect_delta 自动校准规则权重；
3. utility_check 下降触发 P0 警报；
4. 按平台自动淘汰失效规则；
5. 将人工确认记录作为规则激活阈值校准样本。

---

## 10. 推荐文件放置路径

```text
/src/prompts/rule_activation_evaluator_prompt_zh.md
/src/prompts/rule_activation_evaluator_prompt_en.md
/src/config/rule_activation_evaluator.config.json
/src/schemas/rule_activation_evaluation.schema.json
/docs/rule_activation_integration_guide.md
```
