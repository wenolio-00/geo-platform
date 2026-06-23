# GEO Platform 产品功能技术落地文档（完整版）

**功能主题**：QuerySet 生成与质量过滤升级、品牌配置智能预填、LLM Provider 统一改造
**文档类型**：技术落地级别实现文档（可分享 Markdown）
**面向对象**：后端 / 前端 / 测试 / 产品
**文档目的**：在保留原始产品方案表达结构的前提下，明确两项能力的技术实现边界、处理链路、接口扩展、数据结构、LLM provider 改造、测试验收与风险控制，支持研发实施、联调与验收。
**版本说明**：整合了逻辑漏洞侦查结论与优化方案，已在原方案各环节嵌入对应修复设计。

---

# 一、文档背景

本次版本更新聚焦 GEO 平台诊断链路上游三项关键能力升级：

1. **QuerySet 生成与质量过滤升级**
2. **品牌配置智能预填**
3. **LLM Provider 统一改造**

两项能力分别作用于诊断链路的两个入口：

- **品牌配置智能预填**：解决品牌建档效率低、输入口径不统一、上游结构化程度不足的问题。
- **QuerySet 生成与质量过滤升级**：解决 Query 覆盖质量不稳定、硬过滤后总量不足即失败、过程不可观测的问题。

同时，这次技术方案还要显式补充两个新的落地要求：

1. **所有当前依赖本地 mock / 假数据 provider 的 LLM 能力，统一切换为真实 Qwen API 调用链路**，具体密钥与生产环境配置由技术团队后续补充；
2. **品牌配置智能预填当前不是完整闭环**，还需要补齐官网抓取、真实接口接线、`owned_domains` / `competitor owned_domains` / 其余 schema 字段补全策略，才能达到"输入品牌官网后自动形成完整配置草稿"的产品目标。

整体目标是把 GEO 平台从"可运行的诊断流程"提升为"上游输入可治理、生成过程可观测、失败链路可解释、LLM 调用真实可用、生产可稳定复用"的平台能力。

---

# 二、功能一：QuerySet 生成与质量过滤升级

## 2.1 功能背景

QuerySet 是 GEO 诊断链路的核心前置输入，决定后续巡检、聚合分析和报告输出质量。

旧版 / 当前基础实现已具备以下能力：

- 支持按 rule matrix 生成候选 query；
- 支持 QF-01 ~ QF-06 质量过滤；
- 支持多轮生成与累计 active queries；
- 支持质量报告、attempt report、candidate preview、debug context 回传；
- 支持 QuerySet 复用 / 派生 / 新建；
- 支持生产阈值门禁（默认 `candidate_queries >= 30`、`min_active_queries >= 30`）。

但当前实现仍存在一个关键能力缺口：

> 当 QuerySet 经过硬标准过滤后，如果 active query 数量低于阈值，系统当前只会继续"整批再生成一轮并累计幸存者"；如果多轮后仍不足，就直接抛出 `QuerySetGenerationFailed`，导致报告生成失败。

这意味着当前逻辑是：
- 能重试，
- 能累计，
- 但**不能识别到底是哪一类 query 被筛掉得最严重**，
- 也**不能在已通过硬标准的初代 QuerySet 基础上，定向补齐缺失类别，直到达到最小活跃阈值**。

因此，本次升级的核心不只是"多生成一点 query"，而是把 QuerySet 从"有门禁的生成能力"进一步升级为"**按类别缺口自动补齐的生产级治理能力**"。

### 2.1.1 逻辑漏洞侦查结论（已嵌入修复）

原始方案存在以下已在本文档中修复的漏洞：

**漏洞 A：Refill 阶段存在"自我嵌套失败"死循环风险**
> Refill 阶段生成的 query 仍在相同语义空间，仍被 QF 大量拒绝，系统进入"refill → 过滤 → 仍不足 → 再 refill"的死循环。

**修复方案：** 见 2.4 Process Step 5.2 — 引入自适应退出条件（通过率退化检测）与独立 refill QF 阈值，不允许 refill 无限循环。

**漏洞 B：QF 通过率与 min_active_queries 之间存在静默矛盾**
> 若 QF 通过率 < 25%，即使 `candidate_queries` 设置到 200，refill 也无法弥补缺口，这是一个结构性矛盾。

**修复方案：** 见 2.4 Process Step 4 — 引入"生成前校准"环节，动态计算所需候选数量，当 QF 通过率过低时主动预警并阻断进入生成阶段。

**漏洞 C：Refill 的 matrix cell 识别遗漏"零覆盖 cell"**
> 当前识别逻辑只统计"出现过的 cell 被过滤情况"，从未被生成的 cell 被静默遗漏。

**修复方案：** 见 2.4 Process Step 5.1 — 构建 refill plan 时显式探测零覆盖 cell 并纳入目标集合。

## 2.2 用大白话讲，这次改了什么

以前的逻辑更像是：

> 先生成一批问题，过滤一遍；如果活下来的不够，再整批重新生成一轮；如果几轮后还不够，就报错失败。

这次升级之后，逻辑会变成：

> 先做品牌配置健康度检查和生成前校准（预测 QF 通过率）；然后决定复用旧版本还是新生成；新生成时按 rule matrix 结构化产出候选 query；生成后做硬规则过滤；过滤后先评估通过率，如果通过率过低则主动预警（而不是等失败后才发现）；如果 active query 总数不足，识别"哪些 query 类别 / matrix cell 被硬标准打掉最多"，再在已通过硬标准的 active queryset 基础上，定向补齐这些类别；只有普通重试 + 定向补齐都失败，且通过自适应退出条件检测确认继续无意义时，才返回最终失败。

一句话总结：

> QuerySet 已从"可重试的问题集生成模块"，升级为"生成前可校准、过程可观测、缺口可识别、补齐有边界、失败有解释"的生产级 Query 治理能力。

## 2.3 功能目标

### 业务目标

- 提高 QuerySet 与真实用户提问场景的一致性；
- 降低低质量 query 对巡检结果和分析结果的污染；
- 降低因为"硬过滤后总量不足"而导致的诊断任务失败率；
- 提高最终诊断报告的稳定性与可用性。

### 工程目标

- 支持 QuerySet 复用、新建、派生的统一治理；
- 支持按 rule matrix 结构化生成 query；
- 支持自动质量过滤与生产阈值门禁；
- 支持 Brand Config 质量预检闸门；
- 支持生成前 QF 通过率预测与候选数动态校准；
- 支持识别被硬过滤打掉的 category / matrix cell；
- **支持识别零覆盖 matrix cell 并纳入 refill plan；**
- **支持在累计 active query 基础上做定向补齐，refill 有边界、不循环；**
- 支持普通重试与补齐失败过程完整回溯；
- 支持前端展示 QuerySet 生成状态、失败原因与补齐上下文。

## 2.4 IPO 说明

### I. Input（输入）

#### 1）品牌配置输入
来自品牌配置对象：

- `entity_name`
- `entity_aliases`
- `industry_segments`
- `topics`
- `competitors`

其中 `topics` 可包含：

- `topic_name`
- `business_line`
- `priority`
- `pain_point`
- `goal`

这些字段会参与 QuerySet 上下文增强与 rule matrix 变量注入。

#### 2）生成策略输入
来自诊断运行请求：

- `queryset_strategy`
- `queryset_source`
- `queryset_policy`
- `base_queryset_id`
- `queryset_change_reason`
- `queryset_approved_by`

#### 3）生成约束输入
来自 `generation_constraints`：

- `candidate_queries`
- `min_active_queries`
- `max_generation_attempts`
- `allow_small_queryset`

新增建议扩展字段（用于定向补齐阶段）：

- `refill_matrix_cells`
- `refill_candidate_queries`
- `refill_reason`
- `qf_pass_rate_history`（来自历史校准数据）

#### 4）Brand Config 质量预检输入（新增）

在进入 QuerySet 生成前，先执行健康度检查：

```python
BRAND_CONFIG_MINIMUM = {
    "topics": 2,
    "competitors": 1,
    "industry_segments": 1,
    "entity_name": 1,
}

def validate_brand_config(config: BrandConfig) -> list[str]:
    warnings = []
    if len(config.topics) < BRAND_CONFIG_MINIMUM["topics"]:
        warnings.append(f"topics 数量不足（当前 {len(config.topics)}，建议 >= 2）")
    if not config.topics[0].get("pain_point"):
        warnings.append("topics 缺少 pain_point，可能影响 QuerySet 上下文质量")
    if len(config.competitors) < BRAND_CONFIG_MINIMUM["competitors"]:
        warnings.append("competitors 数量为 0，QuerySet 将缺少竞品对比维度")
    if not config.topics[0].get("goal"):
        warnings.append("topics 缺少 goal，可能影响 QuerySet 目标导向性")
    return warnings
```

若返回 warnings 超过 2 条，**阻断进入生成流程**，提示人工先调整品牌配置。

#### 5）QF 通过率历史数据输入（新增）

用于生成前校准，基于同类品牌的历史 QF 通过率：

- 从历史 QuerySet 生成记录中提取 `qf_pass_rate`
- 按 `industry_segments` + `queryset_strategy` 聚合
- 作为生成前校准的参考概率

### P. Process（处理过程）

#### Step 1：确定 QuerySet 来源

系统先判断本次诊断使用哪种 QuerySet 获取方式：

- 复用最近可用版本
- 基于指定版本派生
- 强制创建新版本

作用：减少不必要的重复生成；保持周期性复测口径稳定；支持 QuerySet 版本治理与 lineage 追踪。

现有关键实现：

- `backend/service/queryset.py`
- `backend/service/queryset_library.py`
- `backend/service/inspector.py`

#### Step 2：Brand Config 质量预检（新增）

在进入 QuerySet 生成之前，执行 Brand Config 健康度检查：

```python
def preflight_brand_config_check(config: BrandConfig) -> PreFlightResult:
    warnings = validate_brand_config(config)
    if len(warnings) > 2:
        return PreFlightResult(
            status="blocked",
            message="品牌配置质量不满足最低要求，请先调整以下内容",
            warnings=warnings,
            block_reason="brand_config_insufficient"
        )
    elif len(warnings) > 0:
        return PreFlightResult(
            status="warning",
            message="品牌配置存在以下问题，建议人工确认后再继续",
            warnings=warnings
        )
    return PreFlightResult(status="pass", warnings=[])
```

**目的：** 将"品牌配置质量低洼是整个链路的上游毒药"这一问题显式建模，在生成之前阻断，而不是等生成失败后才发现根因。

#### Step 3：生成前校准 — QF 通过率预测与候选数动态计算（新增）

这是修复"QF 与 min_active_queries 静默矛盾"的核心新增步骤。

```python
def calibrate_before_generation(
    min_active_queries: int,
    historical_qf_pass_rate: float | None,
    matrix_cell_count: int,
) -> CalibrationResult:
    """
    在进入生成前，基于历史 QF 通过率和矩阵规模，
    动态计算需要生成的候选 query 数量。
    """

    # 取经验通过率，若无历史数据则使用保守默认值 30%
    base_pass_rate = historical_qf_pass_rate or 0.30

    # 如果通过率低于 15%，判定为结构性矛盾，不进入生成流程
    if base_pass_rate < 0.15:
        return CalibrationResult(
            status="blocked",
            message=(
                f"预估 QF 通过率 {base_pass_rate:.0%} 过低（< 15%），"
                "品牌配置可能覆盖度过窄，请先扩充 topics / competitors"
            ),
            block_reason="qf_threshold_contradiction",
            suggested_action="expand_topics_or_competitors"
        )

    # 动态计算所需候选数量：min_active / pass_rate，向上取整并加 20% buffer
    candidate_needed = math.ceil(min_active_queries / base_pass_rate * 1.2)

    # 估算所需轮数
    BATCH_SIZE = 30
    attempts_needed = math.ceil(candidate_needed / BATCH_SIZE)

    return CalibrationResult(
        status="ready",
        estimated_candidate_queries=candidate_needed,
        estimated_attempts=attempts_needed,
        estimated_pass_rate=base_pass_rate,
        warnings=(
            [] if base_pass_rate >= 0.30
            else [f"预估通过率 {base_pass_rate:.0%} 偏低，建议关注生成质量"]
        )
    )
```

**关键逻辑：**
- 不再把"候选数量不足"当作生成阶段的内生问题
- 把质量门禁校准提前到生成前
- 通过率低于 15% 时直接阻断，避免无效生成尝试

#### Step 4：按 rule matrix 生成候选 query

若不复用历史版本，且 Step 2 + Step 3 通过检查，则进入新生成流程。

生成时基于 rule matrix，从多个维度结构化铺开：

- `topic`
- `intent`
- `competitor context`
- `journey_stage`
- `query_pattern`
- `matrix_cell_id`

目标是保证 query 具有覆盖面，而不是无结构随机生成。

现有关键实现：

- `backend/service/rule_matrix.py`
- `backend/service/queryset_matrix_client.py`
- `backend/service/queryset.py:generate_queryset()`

#### Step 5：执行质量过滤

候选 query 生成后，执行 QF-01 ~ QF-06 过滤。

过滤后，query 进入三种状态：

- `active`
- `archived`
- `rejected`

现有关键实现：

- `backend/service/queryset_policy.py:apply_query_quality_filters()`
- `backend/service/queryset_policy.py:build_query_quality_report()`

#### Step 6：执行普通生产门禁

系统检查累计 active query 数是否达到最小生产门槛。

当前实现逻辑：

- 每次 attempt 生成一批候选 query；
- 过滤后只把 `active` 累积进可用集合；
- 若累计 active count 达到 `min_active_queries`，则通过；
- 若未达到，则继续下一轮生成；
- 当前 `generation_mode` 为 `accumulate_until_min_active`。

现有关键实现：

- `backend/service/queryset.py:generate_queryset()`

#### Step 7：类别缺口识别与零覆盖 cell 探测（修复版）

这是本次技术升级的核心新增步骤，修复了原方案中"遗漏零覆盖 cell"的漏洞。

当普通 attempts 用尽且累计 active query 仍低于 `min_active_queries` 时，不立即失败，而进入"category-aware replenish"阶段。

**处理逻辑如下：**

**7.1 统计每个 matrix_cell_id 的过滤情况**

```python
def build_cell_statistics(accumulated_candidates: list[QueryCandidate],
                           all_matrix_cells: list[MatrixCell]) -> CellStatistics:
    cell_stats = defaultdict(CellStats)
    for candidate in accumulated_candidates:
        stats = cell_stats[candidate.matrix_cell_id]
        stats.generated += 1
        if candidate.status == "active":
            stats.active += 1
        elif candidate.status == "archived":
            stats.archived += 1
        elif candidate.status == "rejected":
            stats.rejected += 1

    # 计算每个 cell 的过滤率
    for cell_id, stats in cell_stats.items():
        stats.filter_rate = (stats.archived + stats.rejected) / stats.generated if stats.generated > 0 else 1.0
        stats.qf_counts = {}  # 按 QF 类型聚合被拒原因

    return cell_stats
```

**7.2 识别高损耗 cell + 零覆盖 cell（新增零覆盖探测）**

```python
FILTER_RATE_THRESHOLD = 0.50  # 过滤率超过 50% 的 cell 视为高损耗

def identify_refill_targets(cell_stats: CellStatistics,
                            all_matrix_cells: list[MatrixCell],
                            current_active_count: int,
                            min_active: int) -> RefillPlan:
    # 统计已覆盖 cell 的过滤情况
    covered_cells = set(cell_stats.keys())

    # 【关键修复】探测零覆盖 cell：从未被生成过的 cell
    zero_coverage_cells = [
        cell for cell in all_matrix_cells
        if cell.matrix_cell_id not in covered_cells
    ]

    # 识别高损耗 cell（被硬过滤打掉最严重的类别）
    high_filter_cells = [
        cell_id for cell_id, stats in cell_stats.items()
        if stats.filter_rate > FILTER_RATE_THRESHOLD
    ]

    # 零覆盖 cell 优先级最高（从未出现意味着该维度完全缺失）
    # refill plan = 零覆盖 cell + 高损耗 cell（去重）
    target_cells = set(high_filter_cells) | {c.matrix_cell_id for c in zero_coverage_cells}

    # 计算剩余缺口
    remaining_needed = min_active - current_active_count

    return RefillPlan(
        target_cells=list(target_cells),
        zero_coverage_cells=zero_coverage_cells,
        high_filter_cells=high_filter_cells,
        remaining_needed=remaining_needed,
        refill_reason="post_qf_shortfall_with_zero_coverage"
    )
```

**关键改进：** 确保 zero_coverage cells 被显式纳入 refill plan，而不是依赖初始生成的偶然性。

**7.3 发起定向补齐生成**

```python
def execute_refill(refill_plan: RefillPlan,
                  accumulated_candidates: list[QueryCandidate],
                  generation_constraints: GenerationConstraints) -> RefillResult:
    refill_reports = []
    current_active = sum(1 for c in accumulated_candidates if c.status == "active")

    for round_num in range(1, REFILL_MAX_ROUNDS + 1):
        # 发起一轮补齐生成（只生成目标 cell 的 query）
        refill_candidates = queryset_matrix_client.generate(
            target_cells=refill_plan.target_cells,
            count=refill_plan.remaining_needed + 10,  # 多生成 10 个 buffer
            hints={"refill": True}
        )

        # 同样的 QF 过滤
        filtered = queryset_policy.apply_query_quality_filters(refill_candidates)
        new_active = [c for c in filtered if c.status == "active"]
        current_active += len(new_active)

        # 记录 attempt report
        report = RefillAttemptReport(
            round=round_num,
            candidates_generated=len(refill_candidates),
            active_generated=len(new_active),
            pass_rate=len(new_active) / len(refill_candidates) if refill_candidates else 0
        )
        refill_reports.append(report)

        # 【关键修复】自适应退出条件检测
        if not should_continue_refill(refill_reports):
            break

        if current_active >= generation_constraints.min_active_queries:
            break

    return RefillResult(
        total_active=current_active,
        refill_reports=refill_reports,
        refill_plan=refill_plan,
        terminal_reason=determine_terminal_reason(refill_reports, current_active)
    )
```

**7.4 自适应退出条件（新增 — 防止自我嵌套失败）**

这是修复"Refill 死循环"的核心机制。

```python
REFILL_MAX_ROUNDS = 2           # 最多两轮 refill
REFILL_QF_THRESHOLD = 0.05       # 单轮通过率低于 5% 则提前退出
REFILL_DEGRADATION_LIMIT = 0.50  # refill 通过率不能比首轮低超过 50%

def should_continue_refill(refill_reports: list[RefillAttemptReport]) -> bool:
    """
    检测是否应该继续 refill。
    如果 refill 本身的通过率在持续退化，说明继续也无济于事，应提前退出。
    """

    if len(refill_reports) >= REFILL_MAX_ROUNDS:
        return False  # 已达最大轮次

    latest = refill_reports[-1]

    # 单轮通过率过低，继续无意义
    if latest.pass_rate < REFILL_QF_THRESHOLD:
        return False

    # 通过率严重退化，停止（避免无效重试）
    if len(refill_reports) >= 2 and refill_reports[0].pass_rate > 0:
        degradation = latest.pass_rate / refill_reports[0].pass_rate
        if degradation < REFILL_DEGRADATION_LIMIT:
            return False

    return True
```

**关键改进：** 引入"通过率退化检测"，在 refill 效果显著下降时主动停止，避免在无效循环中消耗资源。

#### Step 8：记录过程与诊断上下文

无论成功还是失败，都需要记录并返回：

- 每轮 attempt 的质量报告；
- 候选 query 预览；
- debug context；
- 失败原因；
- 是否可重试；
- 补齐计划与补齐结果（新增）；
- **Brand Config 预检结果（新增）；**
- **生成前校准结果（新增）；**
- **自适应退出检测上下文（新增）。**

建议在现有运行态字段基础上补充：

- `preflight_check_result`（新增）
- `calibration_result`（新增）
- `refill_plan`
- `refill_attempt_reports`
- `shortfall_before_refill`
- `shortfall_after_refill`
- `disproportionately_filtered_cells`
- `zero_coverage_cells`（新增）
- `refill_exit_reason`（新增 — 记录触发自适应退出的具体条件）

### O. Output（输出）

#### 1）正式可用 QuerySet

输出进入诊断巡检流程的有效 query 集合，包括：

- `queryset_id`
- `queryset_version`
- `queries`（仅 active）
- `query_candidates`（保留 active / archived / rejected）
- `lineage`

#### 2）质量报告

包括但不限于：

- `active_count`
- `archived_count`
- `rejected_count`
- `qf_counts`
- `generation_attempt`
- `max_generation_attempts`
- `candidate_target`
- `generation_mode`
- `attempt_reports`

新增建议：

- `preflight_check_result`
- `calibration_result`
- `category_stats.by_matrix_cell`
- `category_stats.by_journey_stage`
- `category_stats.by_query_pattern`
- `zero_coverage_cells`
- `refill_plan`
- `refill_attempt_reports`
- `shortfall_before_refill`
- `shortfall_after_refill`
- `refill_exit_reason`

#### 3）运行态诊断信息

在诊断运行结果中输出过程字段，例如：

- `last_queryset_quality_report`
- `queryset_generation_attempt_reports`
- `last_queryset_id`
- `last_queryset_generation_result`
- `last_queryset_candidates_preview`
- `queryset_debug_context`
- `terminal_reason`
- `retriable`
- `preflight_check_result`（新增）
- `calibration_result`（新增）
- `refill_exit_reason`（新增）

#### 4）结构化 failure 枚举（新增 — 替代字符串驱动的 terminal_reason）

```python
class QuerySetFailureReason(str, Enum):
    """QuerySet 生成失败的枚举型结构化原因，用于前端精确展示"""

    # 生成前预检失败
    BRAND_CONFIG_BLOCKED = "brand_config_blocked"
    QF_RATE_STRUCTURAL_CONTRADICTION = "qf_rate_structural_contradiction"

    # 普通生成失败
    INSUFFICIENT_CANDIDATES = "insufficient_candidates"
    ALL_CELLS_FILTERED = "all_cells_filtered"
    MATRIX_API_ERROR = "matrix_api_error"

    # Refill 阶段（分层）
    REFILL_TRIGGERED = "refill_triggered"
    REFILL_PASS_RATE_TOO_LOW = "refill_pass_rate_too_low"
    REFILL_MAX_ROUNDS_EXCEEDED = "refill_max_rounds_exceeded"
    REFILL_DEGRADATION_DETECTED = "refill_degradation_detected"
    REFILL_ZERO_COVERAGE_PERSISTS = "refill_zero_coverage_persists"

    # 不可恢复
    UNRECOVERABLE_QF_CONTRADICTION = "unrecoverable_qf_contradiction"
```

**目的：** 解决原方案中 `terminal_reason` 字符串解析歧义问题，前端通过枚举类型直接渲染对应 UI。

## 2.5 业务价值

### 对业务侧
- Query 更接近真实用户提问；
- 提高诊断结果可信度；
- 降低因 QuerySet 数量不足导致的任务失败概率；
- 报告输出更稳定；
- **通过率过低时提前预警，避免无效等待。**

### 对技术侧
- QuerySet 生成与过滤过程更可控；
- 能定位是哪类 query 被 QF 打掉；
- 失败链路更透明；
- **Brand Config 质量预检在上游阻断，避免低质量配置污染链路；**
- **refill 自适应退出防止死循环，提升系统健壮性；**
- 为后续版本治理、AB 对比、矩阵策略优化提供依据。

### 对运营 / 实施侧
可更快判断问题出在：

- 品牌配置（预检阶段已提示）
- topic 上下文（预检阶段已提示）
- matrix cell 分布（refill plan 可见）
- query 文本质量
- 阈值策略（生成前校准已预警）
- 平台执行异常

## 2.6 落地级别判断

建议定义为：

> **生产级前置治理能力升级（增强版，含漏洞修复）**

理由：

- 不是简单的"增加 query 数量"；
- 不是单纯的"质量过滤补充"；
- 而是把 QuerySet 生成能力升级为"生成前校准 + Brand Config 预检 + 结构化生成 + 质量门禁 + 零覆盖探测 + 类别缺口识别 + 定向补齐（有限轮次）+ 自适应退出 + 可观测失败"的完整生产治理模块。

## 2.7 技术落地建议

### 后端

#### 现有能力复用
优先复用以下实现：

- `backend/service/queryset.py:generate_queryset()`
- `backend/service/queryset_policy.py:apply_query_quality_filters()`
- `backend/service/queryset_policy.py:build_query_quality_report()`
- `backend/service/rule_matrix.py` 的 matrix cell 结构与 allocation
- `backend/service/queryset_matrix_client.py` 的生成请求通道
- `backend/service/inspector.py` 的运行态错误回传结构

#### 重点新增 / 修改点

1. 在 `backend/service/queryset.py` 新增 `preflight_brand_config_check()` 函数；
2. 在 `backend/service/queryset.py` 新增 `calibrate_before_generation()` 函数 — 动态计算候选数；
3. 在 `backend/service/queryset_policy.py` 扩展 `build_query_quality_report()` — 新增零覆盖 cell 探测；
4. 在 `backend/service/queryset.py` 增加补齐阶段 `execute_refill()`，失败时机改为"普通 attempts + 自适应 refill 退出检测都失败"；
5. 新增 `should_continue_refill()` 自适应退出函数，防止死循环；
6. 新增 `QuerySetFailureReason` 枚举，替代 `terminal_reason` 字符串；
7. 在 `backend/service/queryset_matrix_client.py` 透传 refill hints 与目标 cell 列表；
8. 在 `backend/service/rule_matrix.py` 支持本地 fallback 的定向补齐；
9. 如 nested payload schema 有约束，在 `backend/models/schemas.py` 与 `backend/router/geo.py` 同步扩展。

### 前端
需要支持：

- 展示 Brand Config 预检结果（warning / blocked 状态）；
- 展示生成前校准结果（预估通过率、所需候选数）；
- 展示 QuerySet 生成状态；
- 展示普通 attempts 与 refill attempts 的区别；
- 展示高损耗 `matrix_cell_id` / **零覆盖** `matrix_cell_id` / 类别缺口；
- 展示质量报告摘要和失败上下文；
- 区分"普通失败"和"补齐后仍失败"；
- 通过 `QuerySetFailureReason` 枚举渲染对应 UI，而非解析字符串。

重点联动位置：

- `src/api/geo.js`
- 诊断执行 / 状态页
- 诊断报告页中的错误上下文展示

### 测试
重点覆盖：

- Brand Config 预检 warning / blocked 场景；
- 生成前校准通过率 < 15% 时的阻断场景；
- 复用历史 QuerySet；
- 新生成 QuerySet；
- **active query 不足且零覆盖 cell 探测正确的场景；**
- active query 不足但通过 refill 补齐成功；
- **active query 不足且 refill 通过率退化检测正确触发的场景；**
- active query 不足且 refill 后仍失败（包含各 refill_exit_reason）；
- 返回质量报告结构完整性；
- category stats、zero_coverage_cells 与 refill plan 的正确性；
- 本地 fallback 在 refill 模式下优先生成指定 cell；
- `QuerySetFailureReason` 枚举各值的正确渲染。

---

# 三、功能二：品牌配置智能预填

## 3.1 功能背景

品牌配置是 GEO 诊断链路的起点。旧流程完全依赖人工录入，常见问题包括：

- 首次建档耗时长；
- topic、competitor、industry 录入口径不统一；
- 输入质量波动大，影响后续 QuerySet 与诊断质量；
- 对批量品牌接入不友好。

新增智能预填能力的目标，是把"从原始品牌资料到结构化品牌配置"的过程自动化、标准化，并为 QuerySet 与诊断链路提供稳定上游输入。

但当前实现仍不是完整闭环，现状更接近：

> 具备"从文本资料生成品牌配置草稿"的后端能力，但前端仍存在 mock 预填表现，且官网抓取、真实接口接线、`owned_domains` / `competitor owned_domains` / 其他 schema 字段补全尚未完整打通。

因此，本次技术方案需要把品牌配置智能预填从"AI 辅助草稿"进一步推进到"**输入品牌官网或品牌资料后，可形成完整可编辑配置草稿**"的可落地方案。

### 3.1.1 逻辑漏洞侦查结论（已嵌入修复）

**漏洞：官网抓取失败回退设计存在逻辑断点**

> 原方案"若抓取失败，回退到用户手工粘贴文本"把失败责任转移给用户，用户体验断裂。

**修复方案：** 见 3.4 Process Step 2 — 引入渐进增强兜底策略，而非简单回退。

## 3.2 用大白话讲，这次改了什么

以前需要手工填写：

- 品牌名
- 别名
- 行业
- 话题
- 竞品

现在的目标是：

> 用户输入品牌官网 URL 或上传品牌资料，系统先抓取页面内容或读取文件，再调用真实 Qwen API 做结构化抽取，最后把结果自动回填到品牌配置表单，并尽可能补足当前 brand config schema 里的完整字段。若抓取全部失败，提供渐进增强兜底方案，而不是简单要求用户手工粘贴。

一句话总结：

> 把品牌配置从"手工录表"，升级为"真实 LLM 驱动的智能预填建档流程，配有完整的兜底策略"。

## 3.3 功能目标

### 业务目标
- 缩短品牌接入时间；
- 提高品牌配置初稿质量；
- 降低人工录入成本；
- 支持从品牌官网直接进入配置草稿生成。

### 工程目标
- 将品牌原始资料 / 官网文本转成统一结构；
- 输出可直接进入 brand config 表单；
- 补齐 `owned_domains` 等当前 schema 必需但未完整覆盖的字段；
- 为 QuerySet 与诊断链路提供更稳定的上游输入；
- **移除本地 mock provider / 假数据依赖，改走真实 Qwen API；**
- **官网抓取失败时提供渐进增强兜底，而非简单回退用户。**

## 3.4 IPO 说明

### I. Input（输入）

#### 核心输入
- `source_text`

#### 官网输入
- `source_url`

#### 可选输入
- `source_name`
- `llm_provider`（本次方案目标为统一改为 Qwen）
- 文件上传内容（PDF / DOCX / TXT / Markdown 等）

### P. Process（处理过程）

#### Step 1：接收品牌官网或品牌资料

系统接收用户输入的官网 URL、上传资料或粘贴的品牌文本。

#### Step 2：渐进增强式官网抓取与内容提取（修复版）

这是修复"回退设计断点"的核心改进。不再使用简单的"抓取失败 → 回退用户"，而是引入**渐进增强兜底策略**：

```python
FETCH_TIMEOUT_PRIMARY = 10    # 主流程超时 10s
FETCH_TIMEOUT_FALLBACK = 5    # 降级流程超时 5s

def fetch_brand_content(source_url: str) -> FetchResult:
    """
    渐进增强式内容抓取：
    1. 主流程 HTTP GET
    2. 降级：降低超时 + 尝试 sitemap
    3. 降级：Whois + 主页标题抽取
    4. 全部失败：进入精简表单兜底
    """

    # 策略 1：主流程
    try:
        content = fetch_url(source_url, timeout=FETCH_TIMEOUT_PRIMARY)
        if content and len(content) > 200:
            return FetchResult(status="success", content=content, strategy="primary")
    except FetchError:
        pass

    # 策略 2：降级抓取（sitemap + 正文抽取）
    try:
        sitemap_url = source_url.rstrip("/") + "/sitemap.xml"
        sitemap = fetch_url(sitemap_url, timeout=FETCH_TIMEOUT_FALLBACK)
        content = extract_from_sitemap(sitemap, source_url)
        if content and len(content) > 200:
            return FetchResult(status="partial", content=content, strategy="sitemap")
    except FetchError:
        pass

    # 策略 3：Whois + 标题降级
    try:
        domain = extract_domain(source_url)
        whois_info = query_whois(domain)
        title = fetch_page_title(source_url, timeout=FETCH_TIMEOUT_FALLBACK)
        content = f"{whois_info.get('org', '')} {title}"
        if content.strip():
            return FetchResult(status="partial", content=content, strategy="whois_title")
    except FetchError:
        pass

    # 策略 4：渐进增强兜底（全部失败后）
    # 不再简单要求用户手工粘贴，而是提供引导式精简表单
    return FetchResult(
        status="fallback",
        content="",
        strategy="guided_minimal_form",
        fallback_prompt=build_minimal_form_prompt(source_url)
    )
```

**精简表单兜底策略：**

当所有抓取策略均失败时，系统向用户展示引导式精简表单，而非"粘贴文本"的自由输入：

```python
def build_minimal_form_prompt(source_url: str) -> MinimalFormPrompt:
    """
    构建精简表单，引导用户提供最核心信息，
    后续由 LLM 基于这些信息 + source_url 增强生成完整配置草稿。
    """
    return MinimalFormPrompt(
        instruction=(
            "我们无法自动抓取该官网信息，请提供以下最基本的内容，"
            "AI 将基于这些信息为您生成完整的品牌配置草稿："
        ),
        fields=[
            FormField(name="brand_name", label="品牌名称", required=True),
            FormField(name="main_business", label="主要业务 / 产品描述", required=True, rows=3),
            FormField(name="target_audience", label="目标用户群体（可选）", required=False),
            FormField(name="key_topics", label="您最关注的 2-3 个业务话题（可选）", required=False),
        ],
        source_url=source_url,  # 保留 source_url 供 LLM 后续增强使用
        llm_enhance=True  # 标记为 LLM 增强模式，提交后调用 Qwen 补全
    )
```

**关键改进：** 把"回退手工粘贴"升级为"渐进增强兜底 + LLM 补全"，用户体验不中断，且保留了 source_url 上下文供后续增强。

#### Step 3：调用真实 Qwen API 进行结构化抽取

这是本次方案必须显式补充的技术要求。

当前所有涉及本地 mock / 假数据 provider 的 LLM 场景，特别是：

- 品牌配置智能预填
- QuerySet 相关生成任务中的 task provider
- 其他以本地伪 provider / 假模型代替真实调用的任务链路

都应统一切换到 **Qwen API**，且需配备三层容错架构（见 Section 四）。

落地要求：

1. 在 provider registry 中新增 Qwen provider；
2. 把 `prefill`、`content_generation`、`rule_activation`、`context_extraction`、`queryset_matrix` 等 task type 的默认真实调用链路切到 Qwen；
3. 删除或停用仅用于演示的本地 mock / 假数据 provider 依赖；
4. API key、base URL、model name 采用环境变量注入；
5. 保持调用接口风格与现有 `OpenAICompatibleClient` / provider registry 架构兼容。

#### Step 4：标准化输出品牌配置结构

将 Qwen 返回结果规整为系统可识别的品牌配置结构：

- `entity_name`
- `entity_aliases`
- `industry_segments`
- `topics`
- `competitors`

并进一步补齐当前 schema 字段：

- `owned_domains`
- `competitors[].owned_domains`

以及其他需要落库但当前 prefill 未直接产出的字段。

#### Step 5：补齐 schema 缺失字段策略

##### 1）品牌 `owned_domains`

补全策略：

- 若输入为 `source_url`，优先从 URL 主域名直接提取；
- 对官网正文中出现的同品牌二级域名 / 主站域名可做补充去重；
- 最终写入 `owned_domains`。

##### 2）竞品 `owned_domains`

补全策略：

- 第一阶段允许为空；
- 若资料中明确出现竞品官网，则提取主域名；
- 若后续需要提升完整度，可增加"竞品官网补查"子流程，但不作为第一版强依赖。

##### 3）其他 schema 字段

需明确区分：

- **可自动补全字段**：如 `owned_domains`、topic 默认 `priority`、空列表归一；
- **需人工确认字段**：如 competitors 范围、topic 优先级、business_line 精修；
- **系统生成字段**：如 brand_config 保存后的 `brand_config_id`、`entity_id`、`created_at`、`updated_at`。

这意味着预填的目标定义为：

> 自动生成尽可能完整、可直接编辑与保存的 brand config draft，而非最终自动定稿。

#### Step 6：真实接口接线并回填前端表单

前端需要：

- 从"点击预填直接灌本地样例"改为真正调用 `POST /api/v1/geo/prefill/brand-config`；
- 把官网 URL / 上传文件提取结果传给后端；
- 用后端返回结果回填表单；
- 明确哪些字段是 AI 草稿、哪些字段仍待人工确认。

### O. Output（输出）

最终输出为结构化品牌配置草稿，至少包括：

- `entity_name`
- `entity_aliases`
- `owned_domains`
- `industry_segments`
- `topics`
- `competitors`

其中：

- `topics` 可包含 `pain_point`、`goal`
- `competitors` 建议包含 `name`、`aliases`、`business_line`、`category`、`owned_domains`

同时返回执行上下文：

- `llm_provider`（应为 Qwen）
- `web_search_enabled`
- `web_search_mode`
- `source_url`
- `fetch_status`（建议新增 — 记录抓取策略成功 / 部分成功 / 兜底）
- `fetch_strategy`（建议新增 — 记录使用了哪种抓取策略）

## 3.5 业务价值

### 对业务侧
- 品牌建档更快；
- 降低人工整理成本；
- 支持从官网直接开始品牌 onboarding；
- 更适合批量品牌接入；
- **抓取失败时有渐进兜底，体验不中断。**

### 对产品侧
- 降低配置录入门槛；
- 提高输入一致性；
- 为后续模板化接入和半自动 onboarding 打基础。

### 对技术侧
- 上游输入更标准；
- 降低人工录入波动带来的连锁问题；
- 品牌配置 schema 覆盖度更完整；
- **真实 API 替换 mock 后，联调与验收口径更接近生产。**

## 3.6 功能边界说明

建议明确定位为：

> **AI 辅助预填 + 完整草稿生成 + 渐进增强兜底，不是最终自动定稿。**

仍需人工判断的内容包括：

- 竞品范围是否准确；
- topic 优先级如何排序；
- 哪些业务线需要纳入 GEO 监测；
- 行业标签是否符合当前客户口径；
- 竞品官网域名是否需要补全。

## 3.7 落地级别判断

建议定义为：

> **业务录入提效型功能升级（升级为真实接口闭环版 + 渐进兜底增强版）**

## 3.8 技术落地建议

### 后端

#### 现有能力复用
- `backend/service/smart_prefill.py`
- `backend/service/brand_config.py`
- `backend/service/platform_registry.py`
- `backend/service/platform_clients/openai_compatible.py`
- `backend/router/geo.py`

#### 重点新增 / 修改点
1. 新增官网抓取服务（渐进增强式，支持多策略降级），把 `source_url` 真正转换为 `source_text`；
2. 新增 `build_minimal_form_prompt()` 精简表单兜底函数（抓取全部失败后触发）；
3. 在 provider registry 中显式新增 Qwen provider；
4. 把 prefill 默认 provider 改为 Qwen，并确保 task options 能正确路由；
5. 移除 / 替换本地 mock / 假数据 provider 依赖；
6. 在 `smart_prefill_brand_config()` 中补全 `owned_domains`；
7. 扩展 competitor 结构支持 `owned_domains`；
8. 扩展 `fetch_status` / `fetch_strategy` 字段到响应结构；
9. 与 `BrandConfigCreate` / `BrandConfigResponse` schema 对齐。

### 前端
- 把品牌配置页中的 mock 智能预填流程替换为真实 API 调用；
- 支持输入官网 URL 与上传资料；
- 回填 `owned_domains`、topics、competitors 等字段；
- 清晰标识"AI 草稿"与"最终保存结果"；
- 对未能自动补齐的字段给予明显的人工确认提示；
- **监听 `fetch_status`，在抓取失败时展示精简表单兜底 UI，而非简单报错。**

### 测试
重点覆盖：

- 输入官网 URL 场景（各抓取策略成功 / 降级）；
- 输入品牌资料文本场景；
- 输入模糊资料场景；
- 抓取全部失败 → 精简表单兜底 → LLM 增强场景；
- `owned_domains` 自动提取正确性；
- `competitors[].owned_domains` 空 / 有值兼容性；
- Qwen provider 路由成功；
- 预填结果可直接保存为 brand config；
- brand config 可继续进入诊断链路。

---

# 四、LLM Provider 统一改造要求（新增专项 + 漏洞修复）

## 4.1 目标

本次版本中，所有当前依赖本地 mock / 假数据 provider 的 LLM 调用场景，都要统一切换为 **Qwen API**，同时建立完整的三层容错架构，避免单点故障导致链路卡死。

## 4.2 适用范围

至少包括以下任务类型：

- `prefill`
- `content_generation`
- `rule_activation`
- `context_extraction`
- `queryset_matrix`

如诊断巡检中的其他 task provider 也存在本地 mock / 伪实现，同样纳入统一改造范围。

## 4.3 三层容错架构（新增 — 修复单点故障漏洞）

```
Layer 1: Provider 路由层
  → 优先 Qwen
  → Qwen 不可用时降级到其他已配置 provider（避免链路完全卡死）

Layer 2: 请求容错层
  → 429 Rate Limit：指数退避重试（最多 3 次，间隔 2s/4s/8s）
  → 5xx 错误：超时 30s 重试一次，失败则降级
  → 4xx 业务错误：记录并返回明确错误，不重试

Layer 3: Mock 保留策略（仅限测试环境）
  → 测试环境下，未配置 Qwen key 时允许使用 mock（附明显警告标识）
  → 生产环境强制要求真实 key
  → 通过环境变量 QA_MOCK_ENABLED 控制
```

**实现示例：**

```python
class QwenProviderWithCircuitBreaker:
    def __init__(self, api_key: str, base_url: str, model: str):
        self.primary = QwenClient(api_key=api_key, base_url=base_url, model=model)
        self.fallback_providers: list[LLMProvider] = []
        self.circuit_open = False

    def generate(self, prompt: str, task_type: str) -> GenerationResult:
        # Layer 1: 优先 Qwen
        if self.circuit_open:
            return self._try_fallback(prompt, task_type)

        try:
            return self.primary.generate(prompt, task_type)
        except RateLimitError:
            # Layer 2: 指数退避重试
            for attempt in range(3):
                sleep(2 ** attempt)
                try:
                    result = self.primary.generate(prompt, task_type)
                    self.circuit_open = False
                    return result
                except RateLimitError:
                    continue
            self.circuit_open = True
            return self._try_fallback(prompt, task_type)

        except ServiceUnavailableError:
            # Layer 2: 5xx 降级
            self.circuit_open = True
            return self._try_fallback(prompt, task_type)

        except APIError as e:
            # Layer 2: 4xx 业务错误，不重试，返回明确错误
            return GenerationResult(error=str(e), retriable=False)

    def _try_fallback(self, prompt: str, task_type: str) -> GenerationResult:
        for fallback in self.fallback_providers:
            try:
                return fallback.generate(prompt, task_type)
            except Exception:
                continue
        return GenerationResult(
            error="All providers unavailable",
            retriable=False
        )
```

**测试环境 mock 保留：**

```python
def create_task_client(task_type: str) -> LLMProvider:
    if not is_production() and os.getenv("QA_MOCK_ENABLED") == "true":
        if not qwen_configured():
            logger.warning("QWEN not configured — using mock provider for testing")
            return MockProvider(warning=True)
    return QwenProviderWithCircuitBreaker(...)
```

**关键改进：**
- 未配置 Qwen key 时，测试环境允许使用 mock（避免联调完全卡死），但附明显警告标识；
- 生产环境强制要求真实 key，不允许静默 fallback 到假数据；
- Layer 2 的退避重试保证偶发限流不会直接导致链路失败。

## 4.4 落地原则

- 采用真实 API，不再依赖演示型假数据 provider；
- 保持现有 provider registry 架构可扩展；
- 配置走环境变量，不把 key 写死在代码或文档；
- 允许技术团队后续补充具体 `QWEN_API_KEY`、`QWEN_BASE_URL`、`QWEN_MODEL`；
- 代码层面应让"默认任务 provider = Qwen"成为显式配置，而不是隐含约定；
- Layer 3 容错仅限测试环境使用，附带明确警告标识。

## 4.5 建议改造位置

- `backend/service/platform_registry.py`
- `backend/service/platform_clients/openai_compatible.py`
- `backend/service/smart_prefill.py`
- `backend/service/content_generation.py`
- `backend/service/queryset_matrix_client.py`
- `backend/service/brand_config.py`
- 所有引用 `llm_task_options()` / `create_task_client()` 的任务入口

## 4.6 非目标说明

本方案不负责：

- 提供真实生产 key；
- 决定最终商用模型规格；
- 处理生产环境账号申请流程。

这些内容由技术团队在实施时补充。

---

# 五、两项功能的整体定位

从 GEO 链路看：

## 5.1 品牌配置智能预填

解决的是：

> 品牌接入阶段的录入效率、结构化标准化，以及从官网 / 品牌资料直达品牌配置草稿的问题，配备渐进增强兜底策略。

## 5.2 QuerySet 生成与质量过滤升级

解决的是：

> 诊断执行阶段的 query 质量、生产门禁与"硬过滤后数量不足"的可恢复性问题，配备生成前校准、零覆盖探测与自适应 refill 退出机制。

## 5.3 LLM Provider 统一改造

解决的是：

> 从演示 / mock 驱动链路升级为真实 Qwen API 驱动链路，配备三层容错架构，保证联调、验收、生产迁移的一致性。

三者组合之后，平台在：

> 品牌建档（智能预填 + 渐进兜底） → Brand Config 预检 → 生成前校准 → QuerySet 生成 → 巡检诊断 → 报告输出

这条链路上的上游质量、可执行性与生产可用性将明显增强。

---

# 六、结论

本次版本的升级不只是功能层面的优化，而是三项前置能力的联合增强：

1. **品牌配置智能预填**：从手工录表升级为真实接口驱动的智能建档草稿生成，配备渐进增强兜底策略；
2. **QuerySet 生成与质量过滤升级**：从"阈值不足直接失败"升级为"生成前可校准 + 零覆盖可探测 + 先识别缺口类别并定向补齐（有限轮次）+ 自适应退出检测 + 明确 failure reason 枚举"的生产级治理能力；
3. **LLM Provider 统一改造**：把所有依赖本地 mock / 假数据 provider 的关键链路统一切到 Qwen API，配备三层容错架构。

总体来看，这是一次典型的：

> **诊断前置能力升级 + QuerySet 生产治理能力增强（含漏洞修复）+ LLM 真实化接入改造（含容错保障）**。

---

# 附录 A：接口与字段清单

## A.1 QuerySet 生成与质量过滤升级相关接口

### 1）创建诊断任务
**接口**：`POST /api/v1/geo/diagnostic-runs`

**关键输入字段**：

- `brand_config_id`
- `queryset_strategy`
- `inspection_mode`
- `queryset_source`
- `platforms`
- `queryset_policy`
- `base_queryset_id`
- `queryset_change_reason`
- `queryset_approved_by`
- `generation_constraints`
- `llm_provider`
- `web_search_enabled`
- `llm_options`

**关键输出字段**：

- `run_id`
- `status`
- `progress`
- `message`
- `error`
- `terminal_reason`（**改用 `QuerySetFailureReason` 枚举值**）
- `retriable`
- `preflight_check_result`（新增）
- `calibration_result`（新增）
- `last_queryset_quality_report`
- `queryset_generation_attempt_reports`
- `last_queryset_id`
- `matrix_api_request_id`
- `last_queryset_generation_result`
- `last_queryset_candidates_preview`
- `queryset_debug_context`
- `zero_coverage_cells`（新增）
- `refill_exit_reason`（新增）

### 2）查询诊断任务状态
**接口**：`GET /api/v1/geo/diagnostic-runs/{run_id}`

**关键输出字段**：

- `run_id`
- `status`
- `progress`
- `message`
- `error`
- `terminal_reason`
- `retriable`
- `preflight_check_result`
- `calibration_result`
- `last_queryset_quality_report`
- `queryset_generation_attempt_reports`
- `last_queryset_id`
- `last_queryset_candidates_preview`
- `queryset_debug_context`
- `zero_coverage_cells`
- `refill_exit_reason`

### 3）手动生成 QuerySet
**接口**：`POST /api/v1/geo/querysets/generate`

**关键输入字段**：

- `brand_config_id`
- `entity_id`
- `entity_name`
- `entity_aliases`
- `industry_segments`
- `topics`
- `competitors`
- `generation_constraints`
- `candidate_queries`
- `queryset_strategy`

**关键输出**：

- 生成后的 QuerySet 结果
- 候选 query 集合
- 规则矩阵生成结果
- 质量报告 / attempt reports / **refill report**（新增）

## A.2 品牌配置智能预填相关接口

### 1）智能预填品牌配置
**接口**：`POST /api/v1/geo/prefill/brand-config`

**关键输入字段**：

- `source_text`
- `source_url`（可选，但本次建议升级为真实可用输入）
- `source_name`（可选）
- `llm_provider`（建议默认固定为 Qwen）

**关键输出字段**：

- `entity_name`
- `entity_aliases`
- `owned_domains`
- `industry_segments`
- `topics`
- `competitors`
- `llm_provider`
- `web_search_enabled`
- `web_search_mode`
- `fetch_status`（新增 — 记录抓取策略成功 / 部分成功 / 兜底）
- `fetch_strategy`（新增 — 记录使用了哪种抓取策略）

### 2）保存品牌配置
**接口**：`POST /api/v1/geo/brand-configs`

**关键输入字段**：

- `entity_name`
- `entity_aliases`
- `owned_domains`
- `industry_segments`
- `topics`
- `competitors`

**关键输出字段**：

- `brand_config_id`
- `entity_id`
- `brand_config`

## A.3 关键数据结构说明

### 1）BrandConfigTopic
字段：

- `topic_name`
- `business_line`
- `priority`
- `pain_point`
- `goal`

### 2）BrandConfigCompetitor
字段：

- `name`
- `aliases`
- `business_line`
- `category`
- `owned_domains`

### 3）DiagnosticRunCreate
关键字段：

- `brand_config_id`
- `queryset_strategy`
- `inspection_mode`
- `queryset_source`
- `queryset_policy`
- `base_queryset_id`
- `queryset_change_reason`
- `queryset_approved_by`
- `generation_constraints`
- `platforms`
- `llm_provider`
- `web_search_enabled`
- `llm_options`

### 4）DiagnosticRunResponse
关键字段：

- `run_id`
- `status`
- `progress`
- `message`
- `error`
- `terminal_reason`（`QuerySetFailureReason` 枚举）
- `retriable`
- `preflight_check_result`（新增）
- `calibration_result`（新增）
- `last_queryset_quality_report`
- `queryset_generation_attempt_reports`
- `last_queryset_id`
- `matrix_api_request_id`
- `last_queryset_generation_result`
- `last_queryset_candidates_preview`
- `queryset_debug_context`
- `zero_coverage_cells`（新增）
- `refill_exit_reason`（新增）

### 5）QuerySetFailureReason 枚举（新增）

```python
class QuerySetFailureReason(str, Enum):
    # 生成前预检失败
    BRAND_CONFIG_BLOCKED = "brand_config_blocked"
    QF_RATE_STRUCTURAL_CONTRADICTION = "qf_rate_structural_contradiction"

    # 普通生成失败
    INSUFFICIENT_CANDIDATES = "insufficient_candidates"
    ALL_CELLS_FILTERED = "all_cells_filtered"
    MATRIX_API_ERROR = "matrix_api_error"

    # Refill 阶段
    REFILL_TRIGGERED = "refill_triggered"
    REFILL_PASS_RATE_TOO_LOW = "refill_pass_rate_too_low"
    REFILL_MAX_ROUNDS_EXCEEDED = "refill_max_rounds_exceeded"
    REFILL_DEGRADATION_DETECTED = "refill_degradation_detected"
    REFILL_ZERO_COVERAGE_PERSISTS = "refill_zero_coverage_persists"

    # 不可恢复
    UNRECOVERABLE_QF_CONTRADICTION = "unrecoverable_qf_contradiction"
```

### 6）PreFlightResult（新增）

```python
class PreFlightResult(BaseModel):
    status: Literal["pass", "warning", "blocked"]
    message: str
    warnings: list[str]
    block_reason: QuerySetFailureReason | None = None
```

### 7）CalibrationResult（新增）

```python
class CalibrationResult(BaseModel):
    status: Literal["ready", "blocked"]
    estimated_candidate_queries: int | None = None
    estimated_attempts: int | None = None
    estimated_pass_rate: float | None = None
    message: str
    block_reason: QuerySetFailureReason | None = None
    suggested_action: str | None = None
    warnings: list[str] = []
```

### 8）RefillPlan（增强版）

```python
class RefillPlan(BaseModel):
    target_cells: list[str]
    zero_coverage_cells: list[MatrixCell]  # 新增
    high_filter_cells: list[str]
    remaining_needed: int
    refill_reason: str
```

### 9）RefillAttemptReport（新增）

```python
class RefillAttemptReport(BaseModel):
    round: int
    candidates_generated: int
    active_generated: int
    pass_rate: float
```

## A.4 前端联动点

### 1）API Client
前端 API 侧需关注：

- `startDiagnosticRun()`
- `fetchDiagnosticRun()`
- `prefillBrandConfig()`
- `createBrandConfig()`

### 2）品牌配置页面
需要支持：

- 品牌官网输入；
- 品牌资料上传；
- 智能预填触发；
- 预填结果回填；
- `owned_domains` 回填；
- 用户手动编辑后保存；
- **监听 `fetch_status`，在抓取失败时展示精简表单兜底 UI。**

### 3）诊断执行 / 任务状态页面
需要支持：

- 展示 Brand Config 预检结果（warning / blocked 状态）；
- 展示生成前校准结果（预估通过率、所需候选数）；
- 展示 QuerySet 生成状态；
- 展示普通 attempts 与 refill attempts 的区别；
- 展示失败上下文；
- 展示可重试性和质量报告摘要；
- 展示 category 缺口与补齐结果（如有）；
- **展示 zero_coverage_cells（如有）；**
- **通过 `QuerySetFailureReason` 枚举渲染失败原因 UI（而非字符串解析）。**

## A.5 测试验收建议

### QuerySet 生成与质量过滤升级
- Brand Config 预检 warning / blocked 场景正确触发；
- 生成前校准通过率 < 15% 时阻断进入生成流程；
- 可复用 QuerySet 时能直接复用；
- 不可复用时能按规则新生成；
- active query 不足时可继续普通重试；
- 普通重试不足时可识别缺口 cell **并探测零覆盖 cell**；
- **零覆盖 cell 被正确纳入 refill plan；**
- 普通重试不足时可识别缺口 cell 并定向补齐；
- **refill 通过率退化检测正确触发自适应退出；**
- 补齐成功后最终 active query 达标；
- 补齐失败后返回明确的 `terminal_reason`（枚举值）与 `refill_exit_reason`；
- `attempt report` / `quality report` / `refill report` 字段完整。

### 品牌配置智能预填
- 输入官网 URL 可抓取并生成品牌配置草稿（各策略成功 / 降级）；
- 输入品牌资料文本可成功预填；
- 输入模糊资料时仍能返回结构化草稿；
- `owned_domains` 自动提取正确；
- `topics` / `competitors` 字段结构正确；
- `competitors[].owned_domains` 空 / 有值兼容；
- 抓取全部失败时触发精简表单兜底 → LLM 增强场景；
- 预填结果可直接保存为 brand config；
- brand config 可继续进入诊断链路。

### LLM Provider 统一改造
- prefill 等关键任务默认走 Qwen provider；
- 本地 mock / 假 provider 不再参与核心业务链路；
- 429 限流时指数退避重试正确执行；
- 5xx 错误时降级到 fallback provider；
- **4xx 业务错误时不重试，直接返回明确错误；**
- 未配置 key 时返回明确错误（测试环境除外，需附警告标识）；
- Qwen API 路由与现有任务框架兼容。

---

# 附录 B：建议修改的关键实现文件

## QuerySet 能力升级
- `backend/service/queryset.py`（新增 `preflight_brand_config_check`、`calibrate_before_generation`、`execute_refill`、`should_continue_refill`、`determine_terminal_reason`）
- `backend/service/queryset_policy.py`（扩展 `build_query_quality_report` — 零覆盖 cell 探测）
- `backend/service/queryset_matrix_client.py`（透传 refill hints 与目标 cell 列表）
- `backend/service/rule_matrix.py`（本地 fallback 定向补齐 + 零覆盖探测）
- `backend/service/inspector.py`
- `backend/models/schemas.py`（新增 `QuerySetFailureReason`、`PreFlightResult`、`CalibrationResult`、`RefillAttemptReport` 等 schema）
- `backend/router/geo.py`
- `backend/tests/test_rule_matrix_queryset.py`
- `backend/tests/test_queryset_qf_filters.py`
- `backend/tests/test_geo_router.py`

## 品牌配置智能预填闭环
- `backend/service/smart_prefill.py`（渐进增强式抓取、精简表单兜底）
- `backend/service/brand_config.py`
- `backend/service/parser.py`
- `backend/router/geo.py`
- `backend/models/schemas.py`
- `src/api/geo.js`
- `src/pages/BrandConfigPage.jsx`（监听 `fetch_status`、精简表单兜底 UI）

## Qwen Provider 统一改造
- `backend/service/platform_registry.py`
- `backend/service/platform_clients/openai_compatible.py`
- `backend/service/content_generation.py`
- `backend/service/queryset_matrix_client.py`
- `backend/service/smart_prefill.py`
- 所有 `llm_task_options()` / `create_task_client()` 调用入口

## 新增文件
- `backend/service/fetch_strategies.py` — 渐进增强式抓取策略实现
- `backend/service/minimal_form.py` — 精简表单兜底逻辑
- `backend/service/queryset_failure_reason.py` — `QuerySetFailureReason` 枚举定义
- `backend/service/queryset_calibrator.py` — 生成前校准逻辑

---

# 附录 C：实施风险与权衡

## QuerySet 定向补齐

- 远端 matrix API 可能暂时不支持 refill hints，因此建议第一阶段先确保本地 fallback 可用；
- 若缺口识别逻辑过于复杂，会导致难解释、难测试，第一版建议只按 `matrix_cell_id` 维度补齐；
- 定向补齐仍可能继续命中相同 QF，需要限制 refill 轮次，并保留现有 QF / duplicate 保护；
- **已通过自适应退出条件（`should_continue_refill`）限制 refill 最大轮次为 2 轮，防止死循环；**
- **已通过生成前校准（`calibrate_before_generation`）提前识别 QF 通过率结构性矛盾，在进入生成前阻断；**
- 达标后可能带来轻微 cell 分布倾斜，第一版先优先保证"数量达标 + 补齐依据可解释"；
- **已修复零覆盖 cell 遗漏问题，确保 refill plan 包含从未生成的 cell。**

## 品牌配置智能预填

- 官网抓取质量受站点结构、反爬策略、内容完整度影响；
- **已通过渐进增强策略（主流程 → 降级 → Whois → 精简表单兜底）提供多层保障；**
- 智能抽取质量受输入文本完整度影响较大；
- 竞品与 topic 结构化结果仍需人工确认；
- 前端需明确"AI 草稿"边界，避免被误认为最终事实来源；
- **精简表单兜底策略提供引导式体验，用户无需面对空白输入框的自由发挥。**

## Qwen API 统一改造

- 需要技术团队补充真实 key、base URL、model 配置；
- 不同 Qwen 模型能力差异会影响 prefill / 生成效果；
- 从 mock 迁移到真实 API 后，测试环境需同步处理限流、超时、重试与成本控制；
- **已通过三层容错架构（Provider 路由 + 指数退避重试 + fallback providers）保证链路不因单点故障卡死；**
- **已区分测试环境 mock 保留（附警告标识）与生产环境强制真实 key，避免配置疏漏导致静默失败；**
- **Layer 2 重试逻辑确保偶发限流不会直接失败，而是通过指数退避和降级兜底。**

---

# 附录 D：漏洞修复汇总

| 漏洞 | 原方案风险 | 修复方案 | 修复位置 |
|------|-----------|---------|---------|
| Refill 自我嵌套失败死循环 | refill 通过率持续退化 → 无限循环 → 耗尽资源后失败 | `should_continue_refill()` 自适应退出，通过率退化超 50% 时提前退出 | `queryset.py` |
| QF 与 min_active 静默矛盾 | QF 通过率 < 25% 时，无论生成多少候选都无法达标 → 结构性失败 | `calibrate_before_generation()` 生成前校准，预测通过率 < 15% 时直接阻断 | `queryset.py` |
| matrix cell 零覆盖遗漏 | 从未被生成的 cell 完全被遗漏，导致覆盖度不足 | `identify_refill_targets()` 中显式探测 `zero_coverage_cells` 并纳入 refill plan | `queryset_policy.py` |
| 品牌配置质量低洼未被建模 | 低质量配置是上游毒药，生成失败后才发现根因 | `preflight_brand_config_check()` 生成前健康度检查，warning / blocked 分级处理 | `queryset.py` |
| Qwen 单点故障无容错 | Qwen API 限流 / 不可用时链路直接卡死 | `QwenProviderWithCircuitBreaker` 三层容错架构（路由 + 退避重试 + fallback） | `platform_clients/` |
| terminal_reason 字符串歧义 | 前端需反向解析文本字符串判断展示逻辑，易出错 | `QuerySetFailureReason` 枚举 + 前端按枚举渲染 | `models/schemas.py` |
| 官网抓取回退设计断点 | 抓取失败 → 要求用户手工粘贴 → 用户体验断裂 | 渐进增强兜底策略（4 级降级 → 精简表单引导 → LLM 增强） | `smart_prefill.py` / `fetch_strategies.py` |

---

**版本记录**

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0 | — | 原始方案 |
| 1.1 | 2026/05/25 | 整合逻辑漏洞侦查结论与优化方案，嵌入各对应章节，含 7 项漏洞修复与完整容错架构设计 |