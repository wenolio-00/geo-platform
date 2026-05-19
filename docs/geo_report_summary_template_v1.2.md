# GEO 报告摘要模板框架
> 版本 v1.2 | 适用于 `report_data_v1` 的 AI 可见度诊断报告摘要生成
> 更新：主指标口径、数据质量边界、信源与优化建议已对齐真实报告链路

---

## 一、变量定义表

v1.2 不再用“各平台 GVI 均值”作为唯一总体结论。摘要主指标直接消费
`report_data_v1.global`、`audit`、`platforms`、`competitor_ranking`、`sources`、
`source_references`、`insights` 和 `optimization_recommendations`。

| 变量名 | 来源 | 说明 | 示例值 |
|--------|------|------|--------|
| `{report_date}` | `meta.report_date` | 报告日期 | `2026-05-19` |
| `{brand_name}` | `meta.brand_name` | 品牌名称 | `杭州兑吧` |
| `{completed_samples}` | `audit.completed_samples` | 已完成有效样本数 | `138` |
| `{expected_samples}` | `audit.expected_samples` | 预期样本数 | `150` |
| `{platform_count}` | `audit.platforms_inspected` 或 `platforms.length` | 已完成巡检平台数 | `6` |
| `{quality_note}` | `gen_quality_note(audit)` | 数据质量说明 | `样本完成率较高，结论可作为本次诊断依据` |
| `{visibility}` | `global.visibility` | 可见度：非品牌指定 query 中自然提及品牌的概率，值域 0~1 | `0.681` |
| `{avg_rank}` | `global.rank` | 平均位次：仅统计已提及且位次大于 0 的样本 | `1.37` |
| `{sentiment_score}` | `global.sentiment_score` | 舆情指数：正向=1.0、中立=0.5、负向=0.1 加权均值 | `0.70` |
| `{ai_recommend_score}` | `global.ai_recommend_score` | AI 推荐度：`visibility × sentiment_score × 100` | `47.7` |
| `{rank_tier}` | `competitor_ranking` | 配置竞品内相对层级 | `头部` |
| `{gap_description}` | `competitor_ranking` + `global.visibility` | 与头部/竞品均值的差距描述 | `接近第一梯队，但稳定性仍需提升` |
| `{platform_detail}` | `gen_platform_detail(platforms)` | 平台表现描述 | 文本 |
| `{source_detail}` | `gen_source_detail(sources, source_references)` | 信源与内容基础描述 | 文本 |
| `{priority_recommendations}` | `gen_priority_recommendations(insights, optimization_recommendations)` | 优先级建议 | 文本 |

---

## 二、摘要模板

```
本报告基于 {report_date} 的多平台真实 AI 回答巡检生成。本次完成
{completed_samples}/{expected_samples} 条有效样本，覆盖 {platform_count} 个平台；
{quality_note}

【总体表现】
{brand_name} 当前可见度为 {visibility_pct}，平均位次为 {avg_rank_text}，舆情指数为
{sentiment_score_pct}，AI 推荐度为 {ai_recommend_score}。在配置竞品中，品牌处于
{rank_tier}，{gap_description}。

【平台表现】
{platform_detail}

【信源与内容基础】
{source_detail}

【关键问题与优化建议】
{priority_recommendations}
```

---

## 三、生成规则

### 3.1 主指标口径

| 指标 | 生成口径 | 摘要用途 |
|------|----------|----------|
| 可见度 | `global.visibility` | 判断品牌是否能被 AI 自然看见 |
| 平均位次 | `global.rank` | 判断被提及时推荐顺序是否靠前 |
| 舆情指数 | `global.sentiment_score` | 判断被提及时评价倾向 |
| AI 推荐度 | `global.ai_recommend_score` | 作为综合健康评分 |

> 历史 GVI 可作为“可见度”的业务别名保留，但摘要生成不得再使用
> `mean(platform_scores)` 覆盖 `report_data_v1.global.visibility`。

```python
def fmt_pct(value: float | None, decimals: int = 1) -> str:
    if value is None:
        return "未采集"
    return f"{value:.{decimals}%}"


def fmt_score(value: float | None, decimals: int = 1) -> str:
    if value is None:
        return "未采集"
    return f"{value:.{decimals}f}"


def fmt_rank(value: float | None) -> str:
    if value is None or value <= 0:
        return "尚未形成稳定位次"
    return f"{value:.2f}"
```

### 3.2 `{quality_note}` — 数据质量边界

摘要必须先读取 `audit`。当样本不完整或有平台失败时，避免使用“全面诊断”“全平台结论”
等过强措辞。

| 条件 | 输出文本 |
|------|----------|
| `completed_samples == 0` | 本次没有可用于摘要判断的有效样本，以下仅保留数据结构说明 |
| 完成率 `< 60%` | 样本完成率偏低，结论仅可作为方向性参考 |
| 完成率 `60%~90%` 或存在失败平台 | 部分平台或样本未完成，结论基于本次有效样本生成 |
| 完成率 `>= 90%` 且无失败平台 | 样本完成率较高，结论可作为本次诊断依据 |

```python
def gen_quality_note(audit: dict) -> str:
    completed = int(audit.get("completed_samples") or 0)
    expected = int(audit.get("expected_samples") or 0)
    failed_platforms = audit.get("platforms_failed") or []
    completion_rate = audit.get("sample_completion_rate")

    if completed <= 0:
        return "本次没有可用于摘要判断的有效样本，以下仅保留数据结构说明"

    if completion_rate is None:
        completion_rate = completed / expected if expected else 0

    if completion_rate < 0.60:
        return "样本完成率偏低，结论仅可作为方向性参考"
    if completion_rate < 0.90 or failed_platforms:
        return "部分平台或样本未完成，结论基于本次有效样本生成"
    return "样本完成率较高，结论可作为本次诊断依据"
```

### 3.3 `{rank_tier}` 与 `{gap_description}` — 竞品相对位置

使用 `competitor_ranking` 判断配置竞品内的相对层级。若没有有效排名，不输出确定性层级。

```python
def self_ranking_info(competitor_ranking: list[dict]) -> tuple[int | None, int]:
    rows = [row for row in competitor_ranking if isinstance(row, dict)]
    for index, row in enumerate(rows, start=1):
        if row.get("is_self"):
            return index, len(rows)
    return None, len(rows)


def get_rank_tier(competitor_ranking: list[dict]) -> str:
    rank, total = self_ranking_info(competitor_ranking)
    if not rank or not total:
        return "暂无明确排名"
    pct = rank / total
    if pct <= 0.15:
        return "头部"
    if pct <= 0.35:
        return "中上游"
    if pct <= 0.65:
        return "中游"
    if pct <= 0.85:
        return "中下游"
    return "尾部"


def get_gap_description(competitor_ranking: list[dict]) -> str:
    rows = [row for row in competitor_ranking if isinstance(row, dict)]
    self_row = next((row for row in rows if row.get("is_self")), None)
    if not self_row or len(rows) < 2:
        return "暂无足够竞品样本判断差距"

    self_rate = self_row.get("mention_rate") or 0
    leader_rate = max((row.get("mention_rate") or 0 for row in rows), default=0)
    competitor_rates = [row.get("mention_rate") or 0 for row in rows if not row.get("is_self")]
    competitor_avg = sum(competitor_rates) / len(competitor_rates) if competitor_rates else 0

    if leader_rate <= 0:
        return "配置竞品整体可见度较低，暂无明确头部标杆"

    leader_ratio = self_rate / leader_rate
    avg_ratio = self_rate / competitor_avg if competitor_avg else 0

    if leader_ratio >= 0.90:
        return "接近第一梯队，需继续巩固跨平台稳定性"
    if leader_ratio >= 0.60:
        return "与头部存在一定差距，但已具备追赶基础"
    if avg_ratio >= 1.00:
        return "高于竞品均值，但距离头部仍需系统性提升"
    if avg_ratio >= 0.50:
        return "低于竞品均值，核心场景曝光仍需补强"
    return "与头部及竞品均值差距明显，AI 生态影响力尚未建立"
```

### 3.4 `{platform_detail}` — 平台表现

保留原有“最大值 + 离散度”的判断思路，但增加空平台、单平台、均值为 0 的保护逻辑。

```python
import statistics


def gen_platform_detail(platforms: list[dict]) -> str:
    rows = [row for row in platforms if isinstance(row, dict)]
    if not rows:
        return "本次未形成可用于平台对比的有效平台数据。"

    sorted_rows = sorted(rows, key=lambda row: row.get("visibility") or 0, reverse=True)
    listing = "、".join(
        f"{row.get('name', '未知平台')}（{fmt_pct(row.get('visibility'))}）"
        for row in sorted_rows
    )

    if len(sorted_rows) == 1:
        row = sorted_rows[0]
        return (
            f"本次仅覆盖 {row.get('name', '单个平台')}，可见度为 "
            f"{fmt_pct(row.get('visibility'))}，暂不判断跨平台均衡性。"
        )

    values = [row.get("visibility") or 0 for row in sorted_rows]
    best = sorted_rows[0]
    best_score = values[0]
    mean_v = statistics.mean(values)

    if best_score <= 0:
        conclusion = "各平台均未形成有效可见度，暂不存在平台优势"
    elif best_score < 0.01:
        conclusion = "不存在突出表现的平台，各平台整体处于极低可见度水平"
    elif best_score < 0.05:
        conclusion = "各平台均处于低可见度状态，尚未形成明确平台优势"
    elif mean_v <= 0:
        conclusion = "平台均值为 0，暂不计算跨平台离散度"
    else:
        cv = statistics.stdev(values) / mean_v
        if cv > 1.0:
            conclusion = (
                f"{best.get('name', '最高平台')}表现相对突出"
                f"（{fmt_pct(best_score)}），但平台间差异显著"
            )
        elif cv > 0.5:
            conclusion = (
                f"{best.get('name', '最高平台')}已有一定基础"
                f"（{fmt_pct(best_score)}），各平台发展不够均衡"
            )
        else:
            level = "较高" if mean_v >= 0.30 else "中等" if mean_v >= 0.15 else "偏低"
            conclusion = f"各平台可见度较为均衡，整体处于{level}水平"

    return f"从各 AI 平台表现来看，品牌在 {listing}；{conclusion}。"
```

### 3.5 `{source_detail}` — 信源与内容基础

信源段必须遵守“不编造来源”原则。`sources` 为空且 `source_references` 为空时，只说明未采集到
明确引用，不生成任何域名或 URL。

```python
def gen_source_detail(sources: list[dict], source_references: list[dict]) -> str:
    source_rows = [row for row in sources if isinstance(row, dict)]
    reference_rows = [row for row in source_references if isinstance(row, dict)]

    if not source_rows and not reference_rows:
        return (
            "本次巡检未采集到明确 URL 级引用或域名级信源，"
            "因此不输出信源排行；后续需增强官网、案例页、FAQ 和白皮书的可引用性。"
        )

    own_count = sum(row.get("count") or 0 for row in source_rows if row.get("is_official") or row.get("type") == "自有")
    domain_count = len(source_rows)
    url_count = len(reference_rows)

    if source_rows:
        top_sources = "、".join(
            f"{row.get('domain', '未知域名')}（{row.get('count') or 0}次）"
            for row in sorted(source_rows, key=lambda row: row.get("count") or 0, reverse=True)[:3]
        )
        base = f"本次共识别 {domain_count} 个引用域名，其中品牌自有引用 {own_count} 次；高频信源包括 {top_sources}。"
    else:
        base = "本次未形成域名级信源排行。"

    if reference_rows:
        return f"{base} 同时识别 {url_count} 条高频 URL 级引用，可作为内容优化和证据补强的优先入口。"
    return f"{base} 本次未采集到明确 URL 级引用，暂不输出具体链接排行。"
```

### 3.6 `{priority_recommendations}` — 关键问题与优化建议

优先使用上游 `insights` 和 `optimization_recommendations`，摘要层只做压缩和拼接，不重新发明业务结论。

```python
def infer_metric(text: str) -> str:
    if "引用" in text or "信源" in text:
        return "信源"
    if "舆情" in text or "负面" in text or "正面" in text:
        return "舆情"
    if "位次" in text or "排名" in text:
        return "位次"
    if "平台" in text:
        return "平台"
    return "可见度"


def gen_priority_recommendations(insights: list[dict], recommendations: list[dict], limit: int = 4) -> str:
    insight_rows = [row for row in insights if isinstance(row, dict)]
    action_rows = [row for row in recommendations if isinstance(row, dict)]

    if not insight_rows and not action_rows:
        return "本次上游诊断未提供明确关键问题或优化建议，建议先补齐有效样本与信源数据后复测。"

    actions_by_priority = {}
    for action in action_rows:
        priority = action.get("priority") or "P2"
        actions_by_priority.setdefault(priority, []).append(action)

    output = []
    for insight in insight_rows[:limit]:
        priority = insight.get("priority") or "P2"
        text = str(insight.get("text") or "").strip()
        action = (actions_by_priority.get(priority) or actions_by_priority.get("P1") or action_rows[:1] or [{}])[0]
        title = action.get("title") or "持续优化核心内容资产"
        action_text = action.get("text") or "围绕核心场景补齐事实型内容、客户证据和 FAQ。"
        output.append(f"{priority}：{infer_metric(text)}问题。{text} 建议动作：{title}，{action_text}")

    if not output:
        for action in action_rows[:limit]:
            priority = action.get("priority") or "P2"
            output.append(f"{priority}：优化建议。{action.get('title', '内容优化')}，{action.get('text', '补齐核心内容资产。')}")

    return "\n".join(output)
```

---

## 四、组装函数

```python
def generate_summary(report_data: dict) -> str:
    meta = report_data.get("meta") or {}
    audit = report_data.get("audit") or {}
    global_metrics = report_data.get("global") or {}
    platforms = report_data.get("platforms") or []
    competitor_ranking = report_data.get("competitor_ranking") or []
    sources = report_data.get("sources") or []
    source_references = report_data.get("source_references") or []
    insights = report_data.get("insights") or []
    recommendations = report_data.get("optimization_recommendations") or []

    completed = int(audit.get("completed_samples") or 0)
    expected = int(audit.get("expected_samples") or completed)
    platform_count = len(audit.get("platforms_inspected") or []) or len(platforms)

    if completed <= 0:
        rank_tier = "暂无明确排名"
        gap_desc = "暂无有效样本判断竞品差距"
        platform_detail = "本次没有可用于平台判断的有效样本。"
    else:
        rank_tier = get_rank_tier(competitor_ranking)
        gap_desc = get_gap_description(competitor_ranking)
        platform_detail = gen_platform_detail(platforms)

    return f"""本报告基于 {meta.get('report_date', '未采集日期')} 的多平台真实 AI 回答巡检生成。本次完成 {completed}/{expected} 条有效样本，覆盖 {platform_count} 个平台；{gen_quality_note(audit)}

【总体表现】
{meta.get('brand_name', '该品牌')} 当前可见度为 {fmt_pct(global_metrics.get('visibility'))}，平均位次为 {fmt_rank(global_metrics.get('rank'))}，舆情指数为 {fmt_pct(global_metrics.get('sentiment_score'))}，AI 推荐度为 {fmt_score(global_metrics.get('ai_recommend_score'))}。在配置竞品中，品牌处于{rank_tier}，{gap_desc}。

【平台表现】
{platform_detail}

【信源与内容基础】
{gen_source_detail(sources, source_references)}

【关键问题与优化建议】
{gen_priority_recommendations(insights, recommendations)}"""
```

---

## 五、测试场景

| 场景 | 输入特征 | 期望输出 |
|------|----------|----------|
| 完整样本报告 | 完成率 `>= 90%`，无失败平台 | 输出确定性总体结论、平台差异、信源排行和 P0/P1 建议 |
| 部分平台失败 | `platforms_failed` 非空或完成率 `< 90%` | 出现数据质量说明，不使用“全面诊断”等强结论 |
| 无引用报告 | `sources=[]` 且 `source_references=[]` | 明确说明未采集到引用，不生成假域名 |
| 低可见度高舆情 | `visibility` 低、`sentiment_score` 高 | 区分“看不见”和“被看见后评价尚可” |
| 单平台报告 | `platforms.length == 1` | 不计算 CV，输出“暂不判断跨平台均衡性” |
| 零有效样本 | `completed_samples == 0` | 不输出确定性排名、平台优势或竞品差距 |

---

## 六、实施边界

- 不新增后端字段，优先复用当前 `report_data_v1` 已有字段。
- 摘要生成层不得编造缺失的信源、URL、竞品排名或平台结果。
- v1.2 只调整摘要规则与生成口径，不改变现有报告页面视觉结构。
