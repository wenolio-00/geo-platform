from __future__ import annotations

import os
from uuid import uuid4

DEFAULT_QUERYSET_CANDIDATE_COUNT = 40

MATRIX_CELL_ORDER = (
    "problem_discovery:scenario_explore",
    "problem_discovery:category_rec",
    "solution_evaluation:scenario_explore",
    "solution_evaluation:category_rec",
    "solution_evaluation:deep_background",
    "solution_evaluation:competitive_comp",
    "purchase_decision:vendor_choice",
    "purchase_decision:internal_justification",
    "purchase_decision:purchase_risk",
    "purchase_decision:commercial_terms",
    "purchase_decision:competitive_comp",
)

# Allocation weights are the generation-side sampling frame. At the default
# total of 40 they reproduce the MVP module counts; for operator-selected totals
# the same weights are rounded with largest remainder.
MATRIX_CELL_ALLOCATION_FACTORS = {
    "problem_discovery:scenario_explore": {
        "user_frequency": 3,
        "ai_recommendation_trigger": 1,
        "commercial_decision_value": 1,
        "trend_comparability": 1,
    },
    "problem_discovery:category_rec": {
        "user_frequency": 3,
        "ai_recommendation_trigger": 2,
        "commercial_decision_value": 1,
        "trend_comparability": 1,
    },
    "solution_evaluation:scenario_explore": {
        "user_frequency": 2,
        "ai_recommendation_trigger": 1,
        "commercial_decision_value": 2,
        "trend_comparability": 1,
    },
    "solution_evaluation:category_rec": {
        "user_frequency": 5,
        "ai_recommendation_trigger": 1,
        "commercial_decision_value": 1,
        "trend_comparability": 1,
    },
    "solution_evaluation:deep_background": {
        "user_frequency": 2,
        "ai_recommendation_trigger": 1,
        "commercial_decision_value": 1,
        "trend_comparability": 1,
    },
    "solution_evaluation:competitive_comp": {
        "user_frequency": 3,
        "ai_recommendation_trigger": 1,
        "commercial_decision_value": 2,
        "trend_comparability": 1,
    },
    "purchase_decision:vendor_choice": {
        "user_frequency": 2,
        "ai_recommendation_trigger": 1,
        "commercial_decision_value": 2,
        "trend_comparability": 1,
    },
    "purchase_decision:internal_justification": {
        "user_frequency": 2,
        "ai_recommendation_trigger": 1,
        "commercial_decision_value": 1,
        "trend_comparability": 1,
    },
    "purchase_decision:purchase_risk": {
        "user_frequency": 2,
        "ai_recommendation_trigger": 1,
        "commercial_decision_value": 1,
        "trend_comparability": 1,
    },
    "purchase_decision:commercial_terms": {
        "user_frequency": 2,
        "ai_recommendation_trigger": 1,
        "commercial_decision_value": 1,
        "trend_comparability": 1,
    },
    "purchase_decision:competitive_comp": {
        "user_frequency": 2,
        "ai_recommendation_trigger": 1,
        "commercial_decision_value": 2,
        "trend_comparability": 1,
    },
}
MATRIX_CELL_ALLOCATION_SCORES = {
    cell_id: (
        factors["user_frequency"]
        * factors["ai_recommendation_trigger"]
        * factors["commercial_decision_value"]
        * factors["trend_comparability"]
    )
    for cell_id, factors in MATRIX_CELL_ALLOCATION_FACTORS.items()
}
ALLOCATION_SCORE_TOTAL = sum(MATRIX_CELL_ALLOCATION_SCORES.values()) or 1
MATRIX_CELL_ALLOCATION_WEIGHTS = {
    cell_id: score / ALLOCATION_SCORE_TOTAL
    for cell_id, score in MATRIX_CELL_ALLOCATION_SCORES.items()
}

CORE_CELL_WEIGHTS = {
    "problem_discovery:category_rec": 0.15,
    "solution_evaluation:category_rec": 0.15,
    "solution_evaluation:competitive_comp": 0.15,
    "purchase_decision:vendor_choice": 0.10,
    "purchase_decision:internal_justification": 0.05,
    "purchase_decision:competitive_comp": 0.15,
}
CORE_WEIGHT_TOTAL = sum(CORE_CELL_WEIGHTS.values())

MATRIX_TEMPLATES = [
    {
        "text": "我们的{topic}效果一般，应该从哪些用户场景先排查问题？",
        "journey_stage": "problem_discovery",
        "query_pattern": "scenario_explore",
        "query_layer": "experimental",
        "run_scope": "production",
        "metric_scope": "exploratory_coverage",
        "intent_type": "scenario_diagnosis",
    },
    {
        "text": "{segment}{topic}想提升活跃和留存，常见运营抓手有哪些？",
        "journey_stage": "problem_discovery",
        "query_pattern": "scenario_explore",
        "query_layer": "experimental",
        "run_scope": "production",
        "metric_scope": "exploratory_coverage",
        "intent_type": "scenario_explore",
    },
    {
        "text": "做{topic}有哪些成熟供应商可以参考？",
        "journey_stage": "problem_discovery",
        "query_pattern": "category_rec",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "vendor_recommendation",
    },
    {
        "text": "{segment}{topic}有没有现成平台，不想完全自研？",
        "journey_stage": "problem_discovery",
        "query_pattern": "category_rec",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "category_recommendation",
    },
    {
        "text": "适合中大型团队的{topic}工具有哪些？",
        "journey_stage": "problem_discovery",
        "query_pattern": "category_rec",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "vendor_recommendation",
    },
    {
        "text": "{segment}做{topic}，哪些第三方服务商经验比较多？",
        "journey_stage": "problem_discovery",
        "query_pattern": "category_rec",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "vendor_recommendation",
    },
    {
        "text": "预算有限但要快速上线{topic}，有哪些平台路线？",
        "journey_stage": "problem_discovery",
        "query_pattern": "category_rec",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "category_recommendation",
    },
    {
        "text": "评估{topic}平台时，数据安全和权限管理要看什么？",
        "journey_stage": "solution_evaluation",
        "query_pattern": "scenario_explore",
        "query_layer": "adaptive",
        "run_scope": "production",
        "metric_scope": "supporting_trend",
        "intent_type": "capability_assessment",
    },
    {
        "text": "{topic}接入第三方平台，对系统性能和稳定性有哪些影响？",
        "journey_stage": "solution_evaluation",
        "query_pattern": "scenario_explore",
        "query_layer": "adaptive",
        "run_scope": "production",
        "metric_scope": "supporting_trend",
        "intent_type": "technical_assessment",
    },
    {
        "text": "{topic}上线后，运营数据能不能回传到自己的数据平台？",
        "journey_stage": "solution_evaluation",
        "query_pattern": "scenario_explore",
        "query_layer": "adaptive",
        "run_scope": "production",
        "metric_scope": "supporting_trend",
        "intent_type": "data_integration",
    },
    {
        "text": "我们要采购{topic}平台，候选供应商怎么列清单？",
        "journey_stage": "solution_evaluation",
        "query_pattern": "category_rec",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "vendor_recommendation",
    },
    {
        "text": "面向{segment}{topic}，哪些服务商更适合长期合作？",
        "journey_stage": "solution_evaluation",
        "query_pattern": "category_rec",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "vendor_recommendation",
    },
    {
        "text": "{topic}平台选型，哪些厂商的实施经验更丰富？",
        "journey_stage": "solution_evaluation",
        "query_pattern": "category_rec",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "vendor_recommendation",
    },
    {
        "text": "需要兼顾增长和运营效率，{topic}该看哪些平台？",
        "journey_stage": "solution_evaluation",
        "query_pattern": "category_rec",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "vendor_recommendation",
    },
    {
        "text": "{segment}{topic}服务商里，谁更适合复杂业务场景？",
        "journey_stage": "solution_evaluation",
        "query_pattern": "category_rec",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "vendor_recommendation",
    },
    {
        "text": "{topic}这个赛道主要有哪些类型的服务商？",
        "journey_stage": "solution_evaluation",
        "query_pattern": "deep_background",
        "query_layer": "experimental",
        "run_scope": "bridge",
        "metric_scope": "exploratory_coverage",
        "intent_type": "market_landscape",
    },
    {
        "text": "{entity}和{competitors}在{topic}方面主要区别是什么？",
        "journey_stage": "solution_evaluation",
        "query_pattern": "competitive_comp",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "competitive_comparison",
    },
    {
        "text": "{entity}相比{primary_competitor}，更适合哪些{topic}场景？",
        "journey_stage": "solution_evaluation",
        "query_pattern": "competitive_comp",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "competitive_fit",
    },
    {
        "text": "{primary_competitor}和{entity}都能做{topic}，选型时怎么区分？",
        "journey_stage": "solution_evaluation",
        "query_pattern": "competitive_comp",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "competitive_comparison",
    },
    {
        "text": "{segment}{topic}项目里，{entity}和{secondary_competitor}各有什么优势？",
        "journey_stage": "solution_evaluation",
        "query_pattern": "competitive_comp",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "competitive_comparison",
    },
    {
        "text": "如果已有{primary_competitor}方案，还需要看{entity}的{topic}能力吗？",
        "journey_stage": "solution_evaluation",
        "query_pattern": "competitive_comp",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "competitive_gap",
    },
    {
        "text": "{topic}最终选型，应该优先考虑哪几家供应商？",
        "journey_stage": "purchase_decision",
        "query_pattern": "vendor_choice",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "vendor_choice",
    },
    {
        "text": "{segment}{topic}采购短名单里，{entity}是否值得重点评估？",
        "journey_stage": "purchase_decision",
        "query_pattern": "vendor_choice",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "vendor_choice",
    },
    {
        "text": "准备上线{topic}平台，怎么判断供应商能长期支撑业务？",
        "journey_stage": "purchase_decision",
        "query_pattern": "vendor_choice",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "vendor_choice",
    },
    {
        "text": "向管理层说明采购{entity}做{topic}，应该强调哪些理由？",
        "journey_stage": "purchase_decision",
        "query_pattern": "internal_justification",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "internal_justification",
    },
    {
        "text": "从自研迁移到第三方{topic}平台，主要风险怎么评估？",
        "journey_stage": "purchase_decision",
        "query_pattern": "purchase_risk",
        "query_layer": "adaptive",
        "run_scope": "production",
        "metric_scope": "supporting_trend",
        "intent_type": "purchase_risk",
    },
    {
        "text": "{topic}平台合同里，SLA、服务响应和费用条款怎么谈？",
        "journey_stage": "purchase_decision",
        "query_pattern": "commercial_terms",
        "query_layer": "experimental",
        "run_scope": "shadow",
        "metric_scope": "exploratory_coverage",
        "intent_type": "commercial_terms",
    },
    {
        "text": "最后在{entity}和{primary_competitor}之间选，{topic}该看哪些证据？",
        "journey_stage": "purchase_decision",
        "query_pattern": "competitive_comp",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "competitive_decision",
    },
    {
        "text": "{entity}、{primary_competitor}、{secondary_competitor}谁更适合{segment}{topic}？",
        "journey_stage": "purchase_decision",
        "query_pattern": "competitive_comp",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "competitive_decision",
    },
    {
        "text": "如果老板更熟悉{primary_competitor}，怎么客观比较{entity}的{topic}价值？",
        "journey_stage": "purchase_decision",
        "query_pattern": "competitive_comp",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "competitive_decision",
    },
    {
        "text": "App用户流失变快，{topic}应该先从哪些环节优化？",
        "journey_stage": "problem_discovery",
        "query_pattern": "scenario_explore",
        "query_layer": "experimental",
        "run_scope": "production",
        "metric_scope": "exploratory_coverage",
        "intent_type": "scenario_diagnosis",
    },
    {
        "text": "想做会员积分和任务体系，哪些{topic}平台能快速试点？",
        "journey_stage": "problem_discovery",
        "query_pattern": "category_rec",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "category_recommendation",
    },
    {
        "text": "评估{topic}方案时，活动配置和风控能力怎么验证？",
        "journey_stage": "solution_evaluation",
        "query_pattern": "scenario_explore",
        "query_layer": "adaptive",
        "run_scope": "production",
        "metric_scope": "supporting_trend",
        "intent_type": "capability_assessment",
    },
    {
        "text": "现在{segment}{topic}行业，常见部署模式有哪些？",
        "journey_stage": "solution_evaluation",
        "query_pattern": "deep_background",
        "query_layer": "experimental",
        "run_scope": "bridge",
        "metric_scope": "exploratory_coverage",
        "intent_type": "market_landscape",
    },
    {
        "text": "{entity}和{primary_competitor}在接入周期上差异大吗？",
        "journey_stage": "solution_evaluation",
        "query_pattern": "competitive_comp",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "competitive_comparison",
    },
    {
        "text": "采购{topic}前，短名单里应该保留哪些供应商？",
        "journey_stage": "purchase_decision",
        "query_pattern": "vendor_choice",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "vendor_choice",
    },
    {
        "text": "写内部采购说明时，怎么解释{entity}的{topic}价值？",
        "journey_stage": "purchase_decision",
        "query_pattern": "internal_justification",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "internal_justification",
    },
    {
        "text": "{topic}项目从老系统迁移，历史数据和权益库存怎么处理？",
        "journey_stage": "purchase_decision",
        "query_pattern": "purchase_risk",
        "query_layer": "adaptive",
        "run_scope": "production",
        "metric_scope": "supporting_trend",
        "intent_type": "purchase_risk",
    },
    {
        "text": "{topic}平台续费、扩容和服务边界通常怎么约定？",
        "journey_stage": "purchase_decision",
        "query_pattern": "commercial_terms",
        "query_layer": "experimental",
        "run_scope": "shadow",
        "metric_scope": "exploratory_coverage",
        "intent_type": "commercial_terms",
    },
    {
        "text": "同样预算下，{entity}和{competitors}谁的{topic}投入产出更清楚？",
        "journey_stage": "purchase_decision",
        "query_pattern": "competitive_comp",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "competitive_decision",
    },
    # === Pain Point / Goal 上下文模板 ===
    {
        "text": "遇到{pain_point}的问题，{topic}有没有现成方案？",
        "journey_stage": "problem_discovery",
        "query_pattern": "category_rec",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "pain_point_solution",
    },
    {
        "text": "为了解决{pain_point}，选哪家{topic}平台更靠谱？",
        "journey_stage": "solution_evaluation",
        "query_pattern": "category_rec",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "solution_recommendation",
    },
    {
        "text": "想通过{topic}达到{goal}，有哪些成功案例可以参考？",
        "journey_stage": "solution_evaluation",
        "query_pattern": "scenario_explore",
        "query_layer": "adaptive",
        "run_scope": "production",
        "metric_scope": "supporting_trend",
        "intent_type": "goal_case_study",
    },
    {
        "text": "{topic}方案能解决{pain_point}问题吗？哪家实施经验更丰富？",
        "journey_stage": "solution_evaluation",
        "query_pattern": "competitive_comp",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "pain_point_competitive",
    },
    {
        "text": "选{topic}平台来达成{goal}，{entity}和{primary_competitor}哪家更合适？",
        "journey_stage": "purchase_decision",
        "query_pattern": "vendor_choice",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "goal_vendor_choice",
    },
    {
        "text": "如何向领导说明采购{entity}做{topic}能解决{pain_point}、达成{goal}？",
        "journey_stage": "purchase_decision",
        "query_pattern": "internal_justification",
        "query_layer": "core_anchor",
        "run_scope": "production",
        "metric_scope": "core_trend",
        "intent_type": "goal_internal_justification",
    },
]


def generate_rule_matrix_queryset(
    brand_config: dict,
    strategy: str = "rule_matrix_v1",
    candidate_count: int | None = None,
    generation_attempt: int = 1,
) -> dict:
    topics = _topics(brand_config)  # 返回 [{topic, pain_point, goal}, ...]
    competitors = _competitor_names(brand_config)
    target_count = _target_candidate_count(candidate_count)
    cell_allocation = allocate_matrix_cell_counts(target_count)
    selected_templates = _select_templates_by_allocation(cell_allocation)
    cell_counts = _cell_counts(selected_templates)
    queries: list[dict] = []

    for index, template in enumerate(selected_templates):
        topic_ctx = topics[index % len(topics)]
        queries.append(_query(
            brand_config,
            topic_ctx["topic"],
            competitors,
            template,
            cell_counts,
            generation_attempt,
            pain_point=topic_ctx.get("pain_point", ""),
            goal=topic_ctx.get("goal", ""),
        ))

    normalized = []
    for index, query in enumerate(queries, start=1):
        normalized.append({"query_id": f"q_{index:03d}", **query})

    return {
        "queryset_id": f"qs_{uuid4().hex[:12]}",
        "queryset_version": strategy,
        "matrix_api_request_id": f"mx_local_{uuid4().hex[:12]}",
        "allocation": {
            "strategy": "weighted_largest_remainder",
            "default_candidate_count": DEFAULT_QUERYSET_CANDIDATE_COUNT,
            "requested_candidate_count": target_count,
            "effective_candidate_count": len(selected_templates),
            "cell_counts": cell_counts,
            "cell_allocation_scores": MATRIX_CELL_ALLOCATION_SCORES,
            "cell_weights": MATRIX_CELL_ALLOCATION_WEIGHTS,
        },
        "queries": normalized,
    }


def allocate_matrix_cell_counts(candidate_count: int | None = None) -> dict[str, int]:
    target_count = _target_candidate_count(candidate_count)
    available_counts = _available_cell_counts()
    target_count = min(target_count, sum(available_counts.values()))
    weight_total = sum(MATRIX_CELL_ALLOCATION_WEIGHTS.values()) or 1
    raw_allocations = [
        (
            cell_id,
            target_count * MATRIX_CELL_ALLOCATION_WEIGHTS.get(cell_id, 0) / weight_total,
            MATRIX_CELL_ORDER.index(cell_id),
        )
        for cell_id in MATRIX_CELL_ORDER
        if available_counts.get(cell_id, 0) > 0
    ]
    counts = {
        cell_id: min(int(raw_count), available_counts[cell_id])
        for cell_id, raw_count, _order in raw_allocations
    }
    remaining = target_count - sum(counts.values())
    remainders = sorted(
        raw_allocations,
        key=lambda item: (-(item[1] - int(item[1])), item[2]),
    )
    while remaining > 0:
        distributed = False
        for cell_id, _raw_count, _order in remainders:
            if counts[cell_id] >= available_counts[cell_id]:
                continue
            counts[cell_id] += 1
            remaining -= 1
            distributed = True
            if remaining == 0:
                break
        if not distributed:
            break
    return {cell_id: counts.get(cell_id, 0) for cell_id in MATRIX_CELL_ORDER if counts.get(cell_id, 0) > 0}


def _target_candidate_count(candidate_count: int | None) -> int:
    value = candidate_count
    if value is None:
        value = os.getenv("QUERYSET_CANDIDATE_QUERIES") or os.getenv("MAX_QUERIES_PER_RUN")
    try:
        configured_count = int(value) if value is not None else DEFAULT_QUERYSET_CANDIDATE_COUNT
    except (TypeError, ValueError):
        configured_count = DEFAULT_QUERYSET_CANDIDATE_COUNT
    return max(1, min(len(MATRIX_TEMPLATES), configured_count))


def _available_cell_counts() -> dict[str, int]:
    return _cell_counts(MATRIX_TEMPLATES)


def _select_templates_by_allocation(cell_allocation: dict[str, int]) -> list[dict]:
    templates_by_cell: dict[str, list[dict]] = {}
    for template in MATRIX_TEMPLATES:
        cell_id = f"{template['journey_stage']}:{template['query_pattern']}"
        templates_by_cell.setdefault(cell_id, []).append(template)

    selected: list[dict] = []
    for cell_id in MATRIX_CELL_ORDER:
        selected.extend(templates_by_cell.get(cell_id, [])[: cell_allocation.get(cell_id, 0)])
    return selected


def _topics(brand_config: dict) -> list[dict]:
    """提取 topics 列表，每个包含 topic、pain_point、goal"""
    result = []
    seen: set[str] = set()
    for item in brand_config.get("topics", []):
        if not isinstance(item, dict):
            continue
        topic_name = str(item.get("business_line") or item.get("topic_name") or "").strip()
        if not topic_name or topic_name in seen:
            continue
        seen.add(topic_name)
        result.append({
            "topic": topic_name,
            "pain_point": str(item.get("pain_point") or "").strip() or "",
            "goal": str(item.get("goal") or "").strip() or "",
        })
    return result if result else [{"topic": "品牌核心业务", "pain_point": "", "goal": ""}]


def _topics_with_context(brand_config: dict) -> list[dict]:
    """提取 topics 列表，每个包含完整上下文（已由 ContextExtractor 扩展）"""
    return [
        {
            "topic": str(item.get("business_line") or item.get("topic_name") or "品牌核心业务").strip(),
            "pain_point": str(item.get("pain_point") or "").strip(),
            "goal": str(item.get("goal") or "").strip(),
        }
        for item in brand_config.get("topics", [])
        if isinstance(item, dict)
    ] or [{"topic": "品牌核心业务", "pain_point": "", "goal": ""}]


def _attempt_focus(generation_attempt: int) -> str:
    try:
        attempt = max(1, int(generation_attempt))
    except (TypeError, ValueError):
        attempt = 1
    if attempt == 1:
        return ""
    variants = ["增长视角", "选型视角", "落地视角", "风控视角", "复盘视角"]
    return variants[(attempt - 2) % len(variants)]


def _competitor_names(brand_config: dict) -> list[str]:
    return [
        str(item.get("name", "")).strip()
        for item in brand_config.get("competitors", [])
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    ]


def _segment_label(brand_config: dict) -> str:
    segments = [str(value).strip() for value in brand_config.get("industry_segments", []) if str(value).strip()]
    return _short_name(segments[0], 10) if segments else "当前行业"


def _competitor_phrase(competitors: list[str], limit: int = 2) -> str:
    if competitors:
        return "、".join(_short_name(value, 10) for value in competitors[:limit])
    return "主要竞品"


def _query(
    brand_config: dict,
    topic: str,
    competitors: list[str],
    template: dict,
    cell_counts: dict[str, int],
    generation_attempt: int = 1,
    pain_point: str = "",
    goal: str = "",
) -> dict:
    entity = _short_name(str(brand_config.get("entity_name") or "本品牌").strip() or "本品牌", 14)
    primary_competitor = _short_name(competitors[0], 10) if competitors else "主要竞品"
    secondary_competitor = _short_name(competitors[1], 10) if len(competitors) > 1 else "另一家竞品"
    journey_stage = template["journey_stage"]
    query_pattern = template["query_pattern"]
    matrix_cell_id = f"{journey_stage}:{query_pattern}"
    text = template["text"].format(
        topic=_short_name(topic, 16),
        entity=entity,
        segment=_segment_label(brand_config),
        competitors=_competitor_phrase(competitors),
        primary_competitor=primary_competitor,
        secondary_competitor=secondary_competitor,
        pain_point=pain_point,
        goal=goal,
    )
    focus = _attempt_focus(generation_attempt)
    if focus:
        text = f"{focus}：{text}"

    return {
        "query_text": text,
        "query_layer": template["query_layer"],
        "run_scope": template["run_scope"],
        "metric_scope": template["metric_scope"],
        "metric_weight": _metric_weight(matrix_cell_id, cell_counts),
        "journey_stage": journey_stage,
        "topic": topic,
        "query_pattern": query_pattern,
        "matrix_cell_id": matrix_cell_id,
        "intent_type": template["intent_type"],
        "related_competitors": competitors[:3],
        "lifecycle_status": "active",
        "pain_point": pain_point,
        "goal": goal,
    }


def _cell_counts(templates: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for template in templates:
        cell_id = f"{template['journey_stage']}:{template['query_pattern']}"
        counts[cell_id] = counts.get(cell_id, 0) + 1
    return counts


def _metric_weight(matrix_cell_id: str, cell_counts: dict[str, int]) -> float:
    cell_weight = CORE_CELL_WEIGHTS.get(matrix_cell_id)
    if not cell_weight:
        return 0
    return cell_weight / CORE_WEIGHT_TOTAL / cell_counts[matrix_cell_id]


def _short_name(value: str, max_len: int) -> str:
    text = str(value or "").strip()
    return text if len(text) <= max_len else text[:max_len]
