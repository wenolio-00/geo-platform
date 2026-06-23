# Report Generation Session Issue Definition

## 背景

本 session 基于最新完成的报告 `run_d41c6794b627` / `report_c9cfa1b19df2` 追查了 QuerySet、引用信源排行、高频引用网址，以及“query 不提兑吧但回答提到兑吧”的样本。

当前报告链路已经能通过 API 完成巡检、解析品牌提及、聚合报告和渲染信源模块。但本轮检查发现：当前结果更适合作为链路验证和带品牌上下文的可见度诊断，不能直接代表真实用户自然提问时的品牌自然可见度。

## 问题定义

### 1. 当前品牌提及率偏高，原因是巡检 prompt 暴露了品牌上下文

现象：

- 在 query 本身不包含“兑吧 / 杭州兑吧网络科技有限公司 / Duiba”的情况下，回答仍大量提到兑吧。
- 最新 run 中筛出 23 条“query 不提兑吧但回答提兑吧”的样本。
- 这个提及率明显高于真实用户自然搜索或自然提问时的直觉概率。

根因：

- 当前巡检阶段把品牌配置直接传给模型，包括：
  - 本品牌：杭州兑吧网络科技有限公司
  - 本品牌别名：兑吧、兑吧网络、Duiba
  - 竞品：有赞、微盟、星耀、灵智
- 模型在回答用户问题前已经知道“本轮正在巡检兑吧”，因此答案会被品牌上下文影响。

当前口径：

- 更接近 `assisted_visibility`，即带品牌上下文后的可见度。

真实目标口径：

- 应该是 `natural_visibility`，即用户自然提问、模型不知道被巡检品牌时，是否自然提到兑吧。

### 2. 引用信源偏官网，第三方媒体和 UGC 覆盖不足

现象：

- 高频引用主要集中在品牌官网、竞品官网或结构化官网页面。
- 几乎没有稳定看到知乎、小红书、社区、行业媒体等 UGC / third-party 来源。

可能原因：

- API web search 更容易返回可索引、权威、结构化页面，官网天然占优。
- 小红书、部分知乎、公众号等内容可能受登录、反爬、动态渲染和索引限制影响，搜索工具不一定稳定引用。
- 当前 prompt 没有要求覆盖第三方媒体、社区讨论或 UGC 视角。
- 当前信源分类比较粗，只区分“自有 / 第三方”，不足以解释信源结构。

### 3. “自有信源”定义存在歧义

现象：

- `youzan.com`、`weimob.com` 等竞品官网也可能被标成 `is_official=true`。
- 报告中如果直接把 `is_official=true` 显示为“自有”，会把竞品官网误读成品牌自有信源。

根因：

- 当前 `is_official` 只表达“是否为某个品牌/机构官网”，并不等于“是否为本品牌自有官网”。
- 缺少相对于本品牌的 source ownership 判断。

应该区分：

- `brand_owned`：兑吧自有官网 / 自有内容
- `competitor_owned`：有赞、微盟等竞品官网
- `third_party_media`：媒体、行业报告、新闻站点
- `ugc_community`：知乎、小红书、贴吧、CSDN、公众号等
- `unknown`：无法判断

### 4. 引用信源排行和高频引用网址容易被混淆

定义差异：

- 引用信源排行：按 `domain` 聚合，回答“AI 常引用哪些站点”。
- 高频引用网址：按完整 `url` 聚合，回答“AI 具体反复引用哪些页面”。

当前风险：

- 如果只看域名排行，会看不到具体页面是否集中在某几个官网页面。
- 如果只看 URL 排行，会忽略一个域名整体影响力。

## 方案

### 方案 A：将巡检拆成 Blind Answer 和 Extraction 两阶段

目标：

- 消除品牌上下文对自然回答的干扰。
- 得到真实的 natural visibility。

阶段 1：Blind Answer

- 输入只包含真实用户 query。
- 不传本品牌名称。
- 不传品牌别名。
- 不传竞品列表。
- 不告诉模型“这是 GEO 品牌巡检”。
- 输出自然回答和 API 原生引用。

阶段 2：Extraction

- 输入 Blind Answer 的 raw answer、引用结果、品牌配置。
- 只做结构化抽取：
  - 是否提到本品牌
  - 是否提到竞品
  - 提及位置
  - 情感倾向
  - 引用信源归属

新增指标：

- `natural_visibility`：Blind Answer 中自然提到品牌的比例。
- `assisted_visibility`：带品牌上下文时提到品牌的比例，可作为辅助诊断。
- `visibility_lift`：`assisted_visibility - natural_visibility`，衡量品牌上下文对答案的影响。

### 方案 B：重构信源分类

将当前粗粒度的 `type: 自有 / 第三方` 改为更清晰的结构：

```json
{
  "domain": "duiba.com.cn",
  "source_type": "official_site",
  "ownership": "brand_owned",
  "entity": "杭州兑吧网络科技有限公司",
  "count": 13
}
```

建议字段：

- `ownership`: `brand_owned | competitor_owned | third_party | unknown`
- `source_type`: `official_site | media | ugc_community | social | research_report | docs | unknown`
- `entity`: 该信源归属的品牌或机构
- `is_brand_owned`: 是否为本品牌自有信源
- `is_competitor_owned`: 是否为竞品自有信源

报告展示建议：

- 品牌自有引用量：只统计 `ownership=brand_owned`。
- 竞品官网引用量：单独展示 `ownership=competitor_owned`。
- 第三方媒体 / UGC 引用量：单独展示，用来判断外部口碑和内容渗透。

### 方案 C：增加第三方 / UGC 信源探测能力

目标：

- 不只验证“官网是否被引用”，还要验证“外部内容生态是否被模型引用”。

QuerySet 或巡检策略中增加 source-intent query：

- “知乎上关于积分商城平台的讨论里，常被提到的厂商有哪些？”
- “小红书/社区里，会员权益运营平台有哪些真实使用反馈？”
- “有哪些第三方媒体报道过积分商城或互动广告服务商？”
- “从行业报告或媒体角度，积分商城服务商有哪些代表公司？”

注意：

- 这类 query 应单独标记为 `source_discovery` 或 `ugc_discovery`。
- 不应混入主 Answer Share / GVI 指标，否则会改变原有业务问题样本口径。

### 方案 D：报告里明确区分指标口径

报告中建议增加方法说明：

- 当前结果是否为 `natural_visibility`。
- 是否使用 web search。
- 是否向模型暴露品牌配置。
- 引用信源是否来自模型原生 API citation、回答中显式 URL，还是后处理抽取。

短期文案修正：

- 如果仍使用当前链路，应把“品牌可见度”标注为“带品牌上下文巡检可见度”。
- 避免把它解释成“真实用户自然提问时的品牌提及概率”。

## 落地优先级

### P0：修正核心评估偏差

- 实现 Blind Answer 阶段。
- 将品牌配置从回答 prompt 中移除。
- 保留 Extraction 阶段使用品牌配置做解析。
- 报告新增 `natural_visibility` 字段。

### P1：修正信源归属

- 将 `is_official` 改造成相对本品牌的 ownership 判断。
- 修复竞品官网被展示为“自有”的问题。
- 报告中拆分品牌自有、竞品官网、第三方媒体、UGC。

### P2：增强第三方和 UGC 覆盖

- 增加 source discovery 类型 query。
- 单独输出第三方 / UGC 覆盖分析。
- 不把这类 query 直接并入主核心可见度指标。

## 验收标准

- query 不含兑吧时，Blind Answer 不应收到任何兑吧品牌配置。
- natural visibility 和 assisted visibility 可以同时输出，并且指标名称清晰。
- `brand_owned` 只包含兑吧自有域名。
- 有赞、微盟等竞品官网应归类为 `competitor_owned`。
- 高频引用网址能展示具体 URL、引用次数、引用片段和 query 来源。
- 报告方法说明能解释引用信源排行和高频引用网址的粒度差异。

## 本轮结论

这次报告生成链路已经证明 API、QuerySet、巡检、解析、聚合和报告渲染能跑通；但当前结果不应作为真实自然搜索可见度结论。下一步的关键不是继续优化展示，而是先修正评估实验设计：把“自然回答”和“品牌解析”拆开，避免品牌上下文污染回答结果。

## Review 后落地版

本轮 implementation 按 review 意见收敛为三条硬改造：

1. 巡检链路改为 blind + assisted extraction 两轮。
   - blind 轮只接收 query、topic、query pattern，不接收 `entity_name`、`entity_aliases`、`competitors`。
   - assisted extraction 轮接收 blind 轮自然回答和品牌配置，只做结构化抽取，不重新生成带品牌上下文的答案。
   - 单条 inspection result 保留 `natural_raw_answer` / `natural_parsed` 和 `assisted_raw_answer` / `assisted_parsed`，避免任务数翻倍污染质量门禁。

2. 信源 ownership 改为 backend 确定性解析。
   - `brand_config` 增加 `owned_domains`。
   - competitor 增加 `owned_domains`。
   - `aggregator.py` 通过域名匹配输出 `ownership = brand_owned | competitor_owned | third_party | unknown`。
   - 模型返回的 `is_official` 不再决定“品牌自有”，只作为 fallback evidence。

3. QuerySet 和 dashboard 指标合约显式支持新口径。
   - QuerySet normalization 保留 `source_discovery` / `ugc_discovery`，不再被 coerce 成默认 pattern。
   - `report_data.global` 输出 `natural_visibility`、`assisted_visibility`、`visibility_lift`。
   - dashboard `METRIC_DEFINITIONS` 注册新指标，snapshot 可持久化这些字段。
