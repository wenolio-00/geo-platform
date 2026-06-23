# GEO Platform 产品功能技术落地文档

**功能主题**：QuerySet 生成与质量过滤升级、品牌配置智能预填  
**文档类型**：技术落地级别实现文档（可分享 Markdown）  
**面向对象**：后端 / 前端 / 测试 / 产品  
**文档目的**：在保留原始产品方案表达结构的前提下，明确两项能力的技术实现边界、处理链路、接口扩展、数据结构、LLM provider 改造、测试验收与风险控制，支持研发实施、联调与验收。

---

# 一、文档背景

本次版本更新聚焦 GEO 平台诊断链路上游两项关键能力升级：

1. **QuerySet 生成与质量过滤升级**
2. **品牌配置智能预填**

两项能力分别作用于诊断链路的两个入口：

- **品牌配置智能预填**：解决品牌建档效率低、输入口径不统一、上游结构化程度不足的问题。
- **QuerySet 生成与质量过滤升级**：解决 Query 覆盖质量不稳定、硬过滤后总量不足即失败、过程不可观测的问题。

同时，这次技术方案还要显式补充两个新的落地要求：

1. **所有当前依赖本地 mock / 假数据 provider 的 LLM 能力，统一切换为真实 Qwen API 调用链路**，具体密钥与生产环境配置由技术团队后续补充；
2. **品牌配置智能预填当前不是完整闭环**，还需要补齐官网抓取、真实接口接线、`owned_domains` / `competitor owned_domains` / 其余 schema 字段补全策略，才能达到“输入品牌官网后自动形成完整配置草稿”的产品目标。

整体目标是把 GEO 平台从“可运行的诊断流程”提升为“上游输入可治理、生成过程可观测、失败链路可解释、LLM 调用真实可用、生产可稳定复用”的平台能力。

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

> 当 QuerySet 经过硬标准过滤后，如果 active query 数量低于阈值，系统当前只会继续“整批再生成一轮并累计幸存者”；如果多轮后仍不足，就直接抛出 `QuerySetGenerationFailed`，导致报告生成失败。

这意味着当前逻辑是：

- 能重试，
- 能累计，
- 但**不能识别到底是哪一类 query 被筛掉得最严重**，
- 也**不能在已通过硬标准的初代 QuerySet 基础上，定向补齐缺失类别，直到达到最小活跃阈值**。

因此，本次升级的核心不只是“多生成一点 query”，而是把 QuerySet 从“有门禁的生成能力”进一步升级为“**按类别缺口自动补齐的生产级治理能力**”。

## 2.2 用大白话讲，这次改了什么

以前的逻辑更像是：

> 先生成一批问题，过滤一遍；如果活下来的不够，再整批重新生成一轮；如果几轮后还不够，就报错失败。

这次升级之后，逻辑会变成：

> 先决定复用旧版本还是新生成；新生成时按 rule matrix 结构化产出候选 query；生成后做硬规则过滤；如果 active query 总数不足，不是立刻判定失败，而是先识别“哪些 query 类别 / matrix cell 被硬标准打掉最多”，再在已通过硬标准的 active queryset 基础上，定向补齐这些类别；只有普通重试 + 定向补齐都失败时，才返回最终失败。

一句话总结：

> QuerySet 已从“可重试的问题集生成模块”，升级为“可识别类别缺口、可定向补齐、可解释失败原因的生产级 Query 治理能力”。

## 2.3 功能目标

### 业务目标

- 提高 QuerySet 与真实用户提问场景的一致性；
- 降低低质量 query 对巡检结果和分析结果的污染；
- 降低因为“硬过滤后总量不足”而导致的诊断任务失败率；
- 提高最终诊断报告的稳定性与可用性。

### 工程目标

- 支持 QuerySet 复用、新建、派生的统一治理；
- 支持按 rule matrix 结构化生成 query；
- 支持自动质量过滤与生产阈值门禁；
- 支持识别被硬过滤打掉的 category / matrix cell；
- 支持在累计 active query 基础上做定向补齐；
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

说明：
- 这些字段优先作为内部运行态扩展参数透传，不要求前端第一阶段手工传入；
- 可由后端在普通 attempts 失败后自动生成并注入下一轮 refill 调用。

#### 4）辅助上下文输入
- topic 的 `pain_point`
- topic 的 `goal`
- 历史 QuerySet 版本信息（复用 / 派生场景）
- 历史 active query 文本（用于 QF-06 重复过滤）

### P. Process（处理过程）

#### Step 1：确定 QuerySet 来源
系统先判断本次诊断使用哪种 QuerySet 获取方式：

- 复用最近可用版本
- 基于指定版本派生
- 强制创建新版本

作用：

- 减少不必要的重复生成；
- 保持周期性复测口径稳定；
- 支持 QuerySet 版本治理与 lineage 追踪。

现有关键实现：

- `backend/service/queryset.py`
- `backend/service/queryset_library.py`
- `backend/service/inspector.py`

#### Step 2：按 rule matrix 生成候选 query
若不复用历史版本，则进入新生成流程。

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

#### Step 3：执行质量过滤
候选 query 生成后，执行 QF-01 ~ QF-06 过滤。

当前关注问题包括：

- 文本过短或过长；
- 命中行业禁用词；
- 营销词 / 广告感过强；
- 口语 cell 中出现过度正式表达；
- formal cell 中出现强情绪化表达；
- 与当前 brand 历史 active query 完全重复。

过滤后，query 进入三种状态：

- `active`
- `archived`
- `rejected`

现有关键实现：

- `backend/service/queryset_policy.py:apply_query_quality_filters()`
- `backend/service/queryset_policy.py:build_query_quality_report()`

#### Step 4：执行普通生产门禁
系统检查累计 active query 数是否达到最小生产门槛。

当前实现逻辑：

- 每次 attempt 生成一批候选 query；
- 过滤后只把 `active` 累积进可用集合；
- 若累计 active count 达到 `min_active_queries`，则通过；
- 若未达到，则继续下一轮生成；
- 当前 `generation_mode` 为 `accumulate_until_min_active`。

现有关键实现：

- `backend/service/queryset.py:generate_queryset()`

#### Step 5：新增类别缺口识别与定向补齐
这是本次技术升级的核心新增步骤。

当普通 attempts 用尽且累计 active query 仍低于 `min_active_queries` 时，不立即失败，而进入“category-aware replenish”阶段。

处理逻辑建议如下：

1. 基于累计候选集 `accumulated_candidates` 统计每个 `matrix_cell_id` 的：
   - `generated`
   - `active`
   - `archived`
   - `rejected`
   - `filtered_out`
   - `filter_rate`
   - `qf_counts`

2. 识别“被硬过滤打掉最严重”的类别：
   - `filtered_out` 高；
   - `active` 偏低；
   - 确实在本轮生成中出现过；
   - 与总体平均损耗相比明显不足。

3. 计算剩余缺口：
   - `remaining_needed = min_active_queries - current_active_count`

4. 形成定向补齐计划：
   - 按 `matrix_cell_id` 输出需要补齐的目标分布；
   - 只补缺口相关 cell，而不是再全量生成一整批。

5. 发起 1~2 轮补齐生成：
   - 透传 `refill_matrix_cells`、`refill_candidate_queries`、`refill_reason=post_qf_shortfall`；
   - 继续沿用现有 QF 过滤与重复过滤逻辑；
   - 将新一轮通过硬标准的 `active` query 累加到已有 active queryset 中。

6. 达标则通过；仍不达标才最终失败。

这一阶段的技术设计原则：

- **不推翻现有生成流程**，只在普通 attempts 之后新增补齐阶段；
- **不新建独立 QuerySet schema**，优先复用现有 `matrix_cell_id` 等字段；
- **不修改 QF 规则定义**，只增强质量报告与调度策略；
- **不牺牲可解释性**，补齐依据必须可在 quality report 中回看。

建议新增 / 扩展实现位置：

- `backend/service/queryset.py`
  - 在 `generate_queryset()` 中加入补齐阶段
  - 延后最终失败时机
  - 输出 `refill_plan` 与 `refill_attempt_reports`

- `backend/service/queryset_policy.py`
  - 扩展 `build_query_quality_report()`
  - 新增按 `matrix_cell_id` 聚合的 category report

- `backend/service/queryset_matrix_client.py`
  - 透传 refill hints 到远端 / fallback generation

- `backend/service/rule_matrix.py`
  - 本地 fallback 支持按指定 `matrix_cell_id` 优先补 query

#### Step 6：记录过程与诊断上下文
无论成功还是失败，都需要记录并返回：

- 每轮 attempt 的质量报告；
- 候选 query 预览；
- debug context；
- 失败原因；
- 是否可重试；
- 补齐计划与补齐结果（新增）。

建议在现有运行态字段基础上补充：

- `refill_plan`
- `refill_attempt_reports`
- `shortfall_before_refill`
- `shortfall_after_refill`
- `disproportionately_filtered_cells`

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

- `category_stats.by_matrix_cell`
- `category_stats.by_journey_stage`
- `category_stats.by_query_pattern`
- `refill_plan`
- `refill_attempt_reports`
- `shortfall_before_refill`
- `shortfall_after_refill`

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

## 2.5 业务价值

### 对业务侧
- Query 更接近真实用户提问；
- 提高诊断结果可信度；
- 降低因 QuerySet 数量不足导致的任务失败概率；
- 报告输出更稳定。

### 对技术侧
- QuerySet 生成与过滤过程更可控；
- 能定位是哪类 query 被 QF 打掉；
- 失败链路更透明；
- 为后续版本治理、AB 对比、矩阵策略优化提供依据。

### 对运营 / 实施侧
可更快判断问题出在：

- 品牌配置
- topic 上下文
- matrix cell 分布
- query 文本质量
- 阈值策略
- 平台执行异常

## 2.6 落地级别判断

建议定义为：

> **生产级前置治理能力升级（增强版）**

理由：

- 不是简单的“增加 query 数量”；
- 不是单纯的“质量过滤补充”；
- 而是把 QuerySet 生成能力升级为“结构化生成 + 质量门禁 + 类别缺口识别 + 定向补齐 + 可观测失败”的完整生产治理模块。

## 2.7 技术落地建议

### 后端

#### 现有能力复用
优先复用以下实现，而不是另起一套：

- `backend/service/queryset.py:generate_queryset()`
- `backend/service/queryset_policy.py:apply_query_quality_filters()`
- `backend/service/queryset_policy.py:build_query_quality_report()`
- `backend/service/rule_matrix.py` 的 matrix cell 结构与 allocation
- `backend/service/queryset_matrix_client.py` 的生成请求通道
- `backend/service/inspector.py` 的运行态错误回传结构

#### 重点新增 / 修改点
1. 在 `backend/service/queryset_policy.py` 增加按 `matrix_cell_id` 聚合的 category stats；
2. 在 `backend/service/queryset.py` 增加补齐阶段，失败时机改为“普通 attempts + replenish 都失败”；
3. 在 `backend/service/queryset_matrix_client.py` 透传 refill hints；
4. 在 `backend/service/rule_matrix.py` 支持本地 fallback 的定向补齐；
5. 如 nested payload schema 有约束，在 `backend/models/schemas.py` 与 `backend/router/geo.py` 同步扩展。

### 前端
需要支持：

- 展示 QuerySet 生成状态；
- 展示普通 attempts 与 refill attempts 的区别；
- 展示高损耗 `matrix_cell_id` / 类别缺口；
- 展示质量报告摘要和失败上下文；
- 区分“普通失败”和“补齐后仍失败”。

重点联动位置：

- `src/api/geo.js`
- 诊断执行 / 状态页
- 诊断报告页中的错误上下文展示

### 测试
重点覆盖：

- 复用历史 QuerySet；
- 新生成 QuerySet；
- active query 不足但通过 refill 补齐成功；
- active query 不足且 refill 后仍失败；
- 返回质量报告结构完整性；
- category stats 与 refill plan 的正确性；
- 本地 fallback 在 refill 模式下优先生成指定 cell。

---

# 三、功能二：品牌配置智能预填

## 3.1 功能背景

品牌配置是 GEO 诊断链路的起点。旧流程完全依赖人工录入，常见问题包括：

- 首次建档耗时长；
- topic、competitor、industry 录入口径不统一；
- 输入质量波动大，影响后续 QuerySet 与诊断质量；
- 对批量品牌接入不友好。

新增智能预填能力的目标，是把“从原始品牌资料到结构化品牌配置”的过程自动化、标准化，并为 QuerySet 与诊断链路提供稳定上游输入。

但当前实现仍不是完整闭环，现状更接近：

> 具备“从文本资料生成品牌配置草稿”的后端能力，但前端仍存在 mock 预填表现，且官网抓取、真实接口接线、`owned_domains` / `competitor owned_domains` / 其他 schema 字段补全尚未完整打通。

因此，本次技术方案需要把品牌配置智能预填从“AI 辅助草稿”进一步推进到“**输入品牌官网或品牌资料后，可形成完整可编辑配置草稿**”的可落地方案。

## 3.2 用大白话讲，这次改了什么

以前需要手工填写：

- 品牌名
- 别名
- 行业
- 话题
- 竞品

现在的目标是：

> 用户输入品牌官网 URL 或上传品牌资料，系统先抓取页面内容或读取文件，再调用真实 Qwen API 做结构化抽取，最后把结果自动回填到品牌配置表单，并尽可能补足当前 brand config schema 里的完整字段。

一句话总结：

> 把品牌配置从“手工录表”，升级为“真实 LLM 驱动的智能预填建档流程”。

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
- 移除本地 mock provider / 假数据依赖，改走真实 Qwen API。

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

#### Step 2：执行官网抓取 / 文件内容抽取
这是当前链路缺失的重要部分，需补齐。

建议新增能力：

- 对 `source_url` 执行官网抓取；
- 抽取首页正文、标题、关键信息区块；
- 对上传文件执行文本提取；
- 将页面正文 / 文件内容统一归一为 `source_text`。

要求：

- 若官网抓取失败，允许回退到用户手工粘贴文本；
- 保留抓取来源上下文，便于调试与排查。

#### Step 3：调用真实 Qwen API 进行结构化抽取
这是本次方案必须显式补充的技术要求。

当前所有涉及本地 mock / 假数据 provider 的 LLM 场景，特别是：

- 品牌配置智能预填
- QuerySet 相关生成任务中的 task provider
- 其他以本地伪 provider / 假模型代替真实调用的任务链路

都应统一切换到 **Qwen API**。

落地要求：

1. 在 provider registry 中新增 Qwen provider；
2. 把 `prefill`、`content_generation`、`rule_activation`、`context_extraction`、`queryset_matrix` 等 task type 的默认真实调用链路切到 Qwen；
3. 删除或停用仅用于演示的本地 mock / 假数据 provider 依赖；
4. API key、base URL、model name 采用环境变量注入，**具体 key 由技术团队后续补充，不在本方案中固化**；
5. 保持调用接口风格与现有 `OpenAICompatibleClient` / provider registry 架构兼容，避免大面积重写。

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
这是当前链路第二个必须补充的落地点。

##### 1）品牌 `owned_domains`
补全策略建议：

- 若输入为 `source_url`，优先从 URL 主域名直接提取；
- 对官网正文中出现的同品牌二级域名 / 主站域名可做补充去重；
- 最终写入 `owned_domains`。

##### 2）竞品 `owned_domains`
补全策略建议：

- 第一阶段允许为空；
- 若资料中明确出现竞品官网，则提取主域名；
- 若后续需要提升完整度，可增加“竞品官网补查”子流程，但不作为第一版强依赖。

##### 3）其他 schema 字段
需明确区分：

- **可自动补全字段**：如 `owned_domains`、topic 默认 `priority`、空列表归一；
- **需人工确认字段**：如 competitors 范围、topic 优先级、business_line 精修；
- **系统生成字段**：如 brand_config 保存后的 `brand_config_id`、`entity_id`、`created_at`、`updated_at`。

这意味着预填的目标不应定义成“自动生成最终 brand config 成品”，而应定义为：

> 自动生成尽可能完整、可直接编辑与保存的 brand config draft。

#### Step 6：真实接口接线并回填前端表单
当前前端存在 mock 预填表现，需要替换为真实链路。

前端需要：

- 从“点击预填直接灌本地样例”改为真正调用 `POST /api/v1/geo/prefill/brand-config`；
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
- 抓取 / 提取状态（建议新增）

## 3.5 业务价值

### 对业务侧
- 品牌建档更快；
- 降低人工整理成本；
- 支持从官网直接开始品牌 onboarding；
- 更适合批量品牌接入。

### 对产品侧
- 降低配置录入门槛；
- 提高输入一致性；
- 为后续模板化接入和半自动 onboarding 打基础。

### 对技术侧
- 上游输入更标准；
- 降低人工录入波动带来的连锁问题；
- 品牌配置 schema 覆盖度更完整；
- 真实 API 替换 mock 后，联调与验收口径更接近生产。

## 3.6 功能边界说明

建议明确定位为：

> **AI 辅助预填 + 完整草稿生成，不是最终自动定稿。**

仍需人工判断的内容包括：

- 竞品范围是否准确；
- topic 优先级如何排序；
- 哪些业务线需要纳入 GEO 监测；
- 行业标签是否符合当前客户口径；
- 竞品官网域名是否需要补全。

因此边界应保持：

- 系统负责“产出尽可能完整的初稿”；
- 用户负责“最终确认与修订”。

## 3.7 落地级别判断

建议定义为：

> **业务录入提效型功能升级（升级为真实接口闭环版）**

## 3.8 技术落地建议

### 后端

#### 现有能力复用
- `backend/service/smart_prefill.py`
- `backend/service/brand_config.py`
- `backend/service/platform_registry.py`
- `backend/service/platform_clients/openai_compatible.py`
- `backend/router/geo.py`

#### 重点新增 / 修改点
1. 新增官网抓取 / 文本提取能力，把 `source_url` 真正转换为 `source_text`；
2. 在 provider registry 中显式新增 Qwen provider；
3. 把 prefill 默认 provider 改为 Qwen，并确保 task options 能正确路由；
4. 移除 / 替换本地 mock / 假数据 provider 依赖；
5. 在 `smart_prefill_brand_config()` 中补全 `owned_domains`；
6. 扩展 competitor 结构支持 `owned_domains`；
7. 与 `BrandConfigCreate` / `BrandConfigResponse` schema 对齐，确保 prefill 输出能无缝进入保存接口。

### 前端
- 把品牌配置页中的 mock 智能预填流程替换为真实 API 调用；
- 支持输入官网 URL 与上传资料；
- 回填 `owned_domains`、topics、competitors 等字段；
- 清晰标识“AI 草稿”与“最终保存结果”；
- 对未能自动补齐的字段给予明显的人工确认提示。

### 测试
重点覆盖：

- 输入官网 URL 场景；
- 输入品牌资料文本场景；
- 输入模糊资料场景；
- 抓取失败回退场景；
- `owned_domains` 自动提取正确性；
- `competitors[].owned_domains` 空 / 有值兼容性；
- Qwen provider 路由成功；
- 预填结果可直接保存为 brand config；
- brand config 可继续进入诊断链路。

---

# 四、LLM Provider 统一改造要求（新增专项）

## 4.1 目标

本次版本中，所有当前依赖本地 mock / 假数据 provider 的 LLM 调用场景，都要统一切换为 **Qwen API**。

## 4.2 适用范围

至少包括以下任务类型：

- `prefill`
- `content_generation`
- `rule_activation`
- `context_extraction`
- `queryset_matrix`

如诊断巡检中的其他 task provider 也存在本地 mock / 伪实现，同样纳入统一改造范围。

## 4.3 落地原则

- 采用真实 API，不再依赖演示型假数据 provider；
- 保持现有 provider registry 架构可扩展；
- 配置走环境变量，不把 key 写死在代码或文档；
- 允许技术团队后续补充具体 `QWEN_API_KEY`、`QWEN_BASE_URL`、`QWEN_MODEL`；
- 代码层面应让“默认任务 provider = Qwen”成为显式配置，而不是隐含约定。

## 4.4 建议改造位置

- `backend/service/platform_registry.py`
- `backend/service/platform_clients/openai_compatible.py`
- `backend/service/smart_prefill.py`
- `backend/service/content_generation.py`
- `backend/service/queryset_matrix_client.py`
- `backend/service/brand_config.py`
- 所有引用 `llm_task_options()` / `create_task_client()` 的任务入口

## 4.5 非目标说明

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

> 品牌接入阶段的录入效率、结构化标准化，以及从官网 / 品牌资料直达品牌配置草稿的问题。

## 5.2 QuerySet 生成与质量过滤升级
解决的是：

> 诊断执行阶段的 query 质量、生产门禁与“硬过滤后数量不足”的可恢复性问题。

## 5.3 LLM Provider 统一改造
解决的是：

> 从演示 / mock 驱动链路升级为真实 Qwen API 驱动链路，保证联调、验收、生产迁移的一致性。

三者组合之后，平台在：

> 品牌建档 → QuerySet 生成 → 巡检诊断 → 报告输出

这条链路上的上游质量、可执行性与生产可用性将明显增强。

---

# 六、结论

本次版本的升级不只是功能层面的优化，而是三项前置能力的联合增强：

1. **品牌配置智能预填**：从手工录表升级为真实接口驱动的智能建档草稿生成；
2. **QuerySet 生成与质量过滤升级**：从“阈值不足直接失败”升级为“先识别缺口类别并定向补齐，再决定是否失败”；
3. **LLM Provider 统一改造**：把所有依赖本地 mock / 假数据 provider 的关键链路统一切到 Qwen API。

总体来看，这是一次典型的：

> **诊断前置能力升级 + QuerySet 生产治理能力增强 + LLM 真实化接入改造**。

---

# 附录 A：接口与字段清单

## A.1 QuerySet 生成与质量过滤升级相关接口

### 1）创建诊断任务
**接口**：`POST /api/v1/geo/diagnostic-runs`

**用途**：
发起一次诊断任务，同时决定 QuerySet 获取策略（复用 / 新建 / 派生）。

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
- `terminal_reason`
- `retriable`
- `last_queryset_quality_report`
- `queryset_generation_attempt_reports`
- `last_queryset_id`
- `matrix_api_request_id`
- `last_queryset_generation_result`
- `last_queryset_candidates_preview`
- `queryset_debug_context`

### 2）查询诊断任务状态
**接口**：`GET /api/v1/geo/diagnostic-runs/{run_id}`

**用途**：
查看 QuerySet 生成及诊断执行状态，获取失败信息、重试信息、质量报告。

**关键输出字段**：

- `run_id`
- `status`
- `progress`
- `message`
- `error`
- `terminal_reason`
- `retriable`
- `last_queryset_quality_report`
- `queryset_generation_attempt_reports`
- `last_queryset_id`
- `last_queryset_candidates_preview`
- `queryset_debug_context`

### 3）手动生成 QuerySet
**接口**：`POST /api/v1/geo/querysets/generate`

**用途**：
基于品牌配置和生成策略直接生成 rule matrix QuerySet。

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
- 质量报告 / attempt reports /（建议新增）refill report

## A.2 品牌配置智能预填相关接口

### 1）智能预填品牌配置
**接口**：`POST /api/v1/geo/prefill/brand-config`

**用途**：
基于品牌官网、品牌资料或原始文本自动生成结构化品牌配置草稿。

**关键输入字段**：

- `source_text`
- `source_url`（可选，但本次建议升级为真实可用输入）
- `source_name`（可选）
- `llm_provider`（建议默认固定为 Qwen）

**关键输出字段**：

- `entity_name`
- `entity_aliases`
- `owned_domains`（建议新增）
- `industry_segments`
- `topics`
- `competitors`
- `llm_provider`
- `web_search_enabled`
- `web_search_mode`

### 2）保存品牌配置
**接口**：`POST /api/v1/geo/brand-configs`

**用途**：
将预填后的品牌配置草稿正式保存为品牌配置对象。

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

说明：
表示品牌关注的话题 / 业务主题；`pain_point` 和 `goal` 可用于 QuerySet 上下文增强。

### 2）BrandConfigCompetitor
字段：

- `name`
- `aliases`
- `business_line`
- `category`
- `owned_domains`

说明：
表示竞品配置，用于 QuerySet 生成和后续竞品对比分析。`owned_domains` 当前建议作为增强字段纳入预填补全范围。

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

说明：
这是诊断运行创建的核心输入结构，QuerySet 治理能力主要体现在该对象上。

### 4）DiagnosticRunResponse
关键字段：

- `run_id`
- `status`
- `progress`
- `message`
- `error`
- `terminal_reason`
- `retriable`
- `last_queryset_quality_report`
- `queryset_generation_attempt_reports`
- `last_queryset_id`
- `matrix_api_request_id`
- `last_queryset_generation_result`
- `last_queryset_candidates_preview`
- `queryset_debug_context`

说明：
用于前端状态展示、异常提示、质量回溯和排查。若新增 refill 上下文，建议优先继续挂载在 `last_queryset_quality_report` / `queryset_debug_context` 的 nested payload 中，以减少 response schema 改造面。

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
- 用户手动编辑后保存。

### 3）诊断执行 / 任务状态页面
需要支持：

- 展示 QuerySet 生成状态；
- 展示普通 attempts 与 refill attempts；
- 展示失败上下文；
- 展示可重试性和质量报告摘要；
- 展示 category 缺口与补齐结果（如有）。

## A.5 测试验收建议

### QuerySet 生成与质量过滤升级
- 可复用 QuerySet 时能直接复用；
- 不可复用时能按规则新生成；
- active query 不足时可继续普通重试；
- 普通重试不足时可识别缺口 cell 并定向补齐；
- 补齐成功后最终 active query 达标；
- 补齐失败后返回明确 `terminal_reason` / failure context；
- `attempt report` / `quality report` / `refill report` 字段完整。

### 品牌配置智能预填
- 输入官网 URL 可抓取并生成品牌配置草稿；
- 输入品牌资料文本可成功预填；
- 输入模糊资料时仍能返回结构化草稿；
- `owned_domains` 自动提取正确；
- `topics` / `competitors` 字段结构正确；
- `competitors[].owned_domains` 空 / 有值兼容；
- 预填结果可直接保存为 brand config；
- brand config 可继续进入诊断链路。

### LLM Provider 统一改造
- prefill 等关键任务默认走 Qwen provider；
- 本地 mock / 假 provider 不再参与核心业务链路；
- 未配置 key 时返回明确错误，而不是静默 fallback 到假数据；
- Qwen API 路由与现有任务框架兼容。

---

# 附录 B：建议修改的关键实现文件

## QuerySet 能力升级
- `backend/service/queryset.py`
- `backend/service/queryset_policy.py`
- `backend/service/queryset_matrix_client.py`
- `backend/service/rule_matrix.py`
- `backend/service/inspector.py`
- `backend/models/schemas.py`
- `backend/router/geo.py`
- `backend/tests/test_rule_matrix_queryset.py`
- `backend/tests/test_queryset_qf_filters.py`
- `backend/tests/test_geo_router.py`

## 品牌配置智能预填闭环
- `backend/service/smart_prefill.py`
- `backend/service/brand_config.py`
- `backend/service/parser.py`
- `backend/router/geo.py`
- `backend/models/schemas.py`
- `src/api/geo.js`
- `src/pages/BrandConfigPage.jsx`
- 官网抓取 / 文本提取相关服务文件（建议新增）

## Qwen Provider 统一改造
- `backend/service/platform_registry.py`
- `backend/service/platform_clients/openai_compatible.py`
- `backend/service/content_generation.py`
- `backend/service/queryset_matrix_client.py`
- `backend/service/smart_prefill.py`
- 所有 `llm_task_options()` / `create_task_client()` 调用入口

---

# 附录 C：实施风险与权衡

## QuerySet 定向补齐
- 远端 matrix API 可能暂时不支持 refill hints，因此建议第一阶段先确保本地 fallback 可用；
- 若缺口识别逻辑过于复杂，会导致难解释、难测试，第一版建议只按 `matrix_cell_id` 维度补齐；
- 定向补齐仍可能继续命中相同 QF，需要限制 refill 轮次，并保留现有 QF / duplicate 保护；
- 达标后可能带来轻微 cell 分布倾斜，第一版先优先保证“数量达标 + 补齐依据可解释”。

## 品牌配置智能预填
- 官网抓取质量受站点结构、反爬策略、内容完整度影响；
- 智能抽取质量受输入文本完整度影响较大；
- 竞品与 topic 结构化结果仍需人工确认；
- 前端需明确“AI 草稿”边界，避免被误认为最终事实来源。

## Qwen API 统一改造
- 需要技术团队补充真实 key、base URL、model 配置；
- 不同 Qwen 模型能力差异会影响 prefill / 生成效果；
- 从 mock 迁移到真实 API 后，测试环境需同步处理限流、超时、重试与成本控制；
- 必须避免“未配置真实 key 时静默 fallback 到假数据”，否则会破坏联调真实性。
