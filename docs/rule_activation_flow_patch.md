# GEO v6.2 Flow Patch: 加入 Rule Activation Evaluator

## 原流程片段

```text
07 InspectionResult 存库 + utility_check
  ↓
08 Rule Extraction · 平台内容偏好规则提取
  ↓
09 每周定时巡检
  ↓
10 Decision Engine · 矩阵格聚合评估
  ↓
13 生成 ActionTask · 按优先级互斥触发
  ↓
14 内容团队执行 · 规则驱动 + Claim+Fact+Proof
```

## 修改后流程片段

```text
07 InspectionResult 存库 + utility_check
  ↓
08 Rule Extraction · 平台内容偏好规则提取
  ↓
08.5 Rule Activation Evaluator · 规则激活评估器
  ↓
09 每周定时巡检
  ↓
10 Decision Engine · 矩阵格聚合评估
  ↓
13 生成 ActionTask · 按优先级互斥触发
  ↓
14 内容团队执行 · Baseline Rule / Active Rules + Claim+Fact+Proof
```

## 新增节点：08.5 Rule Activation Evaluator

**节点 Key：** `rule_activation_evaluator`  
**弹窗 Badge：** 规则闸门

### 步骤定义

Rule Activation Evaluator 用于判断自动生成的内容优化规则是否可以进入内容生产流程。系统将 Auto-generated Rule Set 与用户维护的 Baseline Rule 进行对比，只有当自动规则在关键指标上明确优于 Baseline Rule，且没有事实、证据、品牌一致性和 utility_check 风险时，才允许激活。

### 输入

| 字段 | 说明 |
|---|---|
| baseline_rule | 用户手动维护的基础规则 |
| auto_generated_rule_set | Rule Extraction 生成的候选规则 |
| evaluation_data | InspectionResult、effect_delta、utility_check、平台拆分结果 |
| project_context | 品牌、行业、竞品、QuerySet 场景、ActionTask 类型 |

### 输出

| 字段 | 说明 |
|---|---|
| decision | activate_global / activate_platform_specific / activate_task_specific / merge_into_baseline / keep_baseline / reject_rule_set |
| confidence | high / medium / low |
| activation_scope | 平台、query_pattern、action_type 适用范围 |
| risk_check | 风险检查结果 |
| recommended_next_action | 下一步动作 |

### 默认决策

MVP 阶段默认采用保守策略：

```text
如果数据不足，继续使用 Baseline Rule。
```

### 与 ActionTask 的关系

ActionTask 不再直接拉取所有 platform_rules_store 规则，而是只拉取 active_rules_store 中已经通过评估的规则。如果没有匹配的 active rule，则回退到 Baseline Rule。
