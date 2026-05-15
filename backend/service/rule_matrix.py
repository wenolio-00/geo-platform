from __future__ import annotations

import os
from uuid import uuid4

from service.queryset_policy import DECISION, DISCOVERY, EVALUATION, matrix_cell_id, policy_for

STAGE_TO_INTENT = {
    DISCOVERY: "awareness",
    EVALUATION: "consideration",
    DECISION: "decision",
}


DUiBA_SCENARIO_QUERIES = [
    {"text": "我们 App 日活下滑，用户打开一次就走了，积分体系能真的把人留住吗", "stage": DISCOVERY, "pattern": "scenario_explore", "brand_neutral": True, "context": "互联网App运营"},
    {"text": "银行 App 怎么做才能让用户每天打开，现在除了查余额没人用", "stage": DISCOVERY, "pattern": "scenario_explore", "brand_neutral": True, "context": "金融App"},
    {"text": "做 App 积分体系有哪些现成的 SaaS 工具，不想自研太费人力", "stage": DISCOVERY, "pattern": "category_rec", "brand_neutral": True, "context": "通用App运营"},
    {"text": "保险公司 App 想做签到积分兑换权益，有专门服务金融 App 的平台吗", "stage": DISCOVERY, "pattern": "category_rec", "brand_neutral": True, "context": "金融App"},
    {"text": "出行 App 想做里程积分换实物，有现成解决方案吗还是必须自研", "stage": DISCOVERY, "pattern": "category_rec", "brand_neutral": True, "context": "出行App"},
    {"text": "视频 App 想做付费会员积分权益，有没有成熟的第三方工具可以接", "stage": DISCOVERY, "pattern": "category_rec", "brand_neutral": True, "context": "内容/媒体App"},
    {"text": "接入第三方积分平台，用户数据安全怎么保障，金融行业合规怎么过", "stage": EVALUATION, "pattern": "scenario_explore", "brand_neutral": True, "context": "金融App"},
    {"text": "积分 SaaS 平台的 SDK 接入对 App 性能有多大影响，会拖慢启动速度吗", "stage": EVALUATION, "pattern": "scenario_explore", "brand_neutral": True, "context": "技术评估"},
    {"text": "用了积分 SaaS 之后，用户的积分行为数据能回传到我们自己的数仓吗", "stage": EVALUATION, "pattern": "scenario_explore", "brand_neutral": True, "context": "数据/技术"},
    {"text": "金融 App 积分运营平台有哪些成熟供应商，哪些更懂合规场景", "stage": EVALUATION, "pattern": "category_rec", "brand_neutral": True, "context": "金融App"},
    {"text": "面向互联网 App 的积分商城 SaaS，哪些平台适合高并发活动和权益兑换", "stage": EVALUATION, "pattern": "category_rec", "brand_neutral": True, "context": "互联网App运营"},
    {"text": "内容 App 想把会员权益和积分任务打通，有哪些第三方平台能覆盖完整流程", "stage": EVALUATION, "pattern": "category_rec", "brand_neutral": True, "context": "内容/媒体App"},
    {"text": "如果不想自建权益供应链，哪些积分运营服务商能提供商品和运营配置", "stage": EVALUATION, "pattern": "category_rec", "brand_neutral": True, "context": "权益供应链"},
    {"text": "有赞和兑吧都有积分功能，但我们是 App 不是微信小程序，选哪个更合适", "stage": EVALUATION, "pattern": "competitive_comp", "brand_neutral": False, "context": "App vs 小程序场景"},
    {"text": "微盟的用户运营工具和兑吧的区别是什么，我们是金融 App 不是零售商家", "stage": EVALUATION, "pattern": "competitive_comp", "brand_neutral": False, "context": "金融App选型"},
    {"text": "兑吧和有赞都能做会员积分，哪家更适合独立 App 的活跃和留存目标", "stage": EVALUATION, "pattern": "competitive_comp", "brand_neutral": False, "context": "App留存对比"},
    {"text": "兑吧、微盟、星耀这几类服务商在积分商城和用户运营上的定位差异是什么", "stage": EVALUATION, "pattern": "competitive_comp", "brand_neutral": False, "context": "市场定位对比"},
    {"text": "积分 SaaS 上线多久才能看到日活和留存的提升，怎么判断哪家平台更靠谱", "stage": DECISION, "pattern": "vendor_choice", "brand_neutral": True, "context": "效果预期"},
    {"text": "几家平台试下来功能差不多，最后怎么判断哪个更适合我们 App 的业务模式", "stage": DECISION, "pattern": "vendor_choice", "brand_neutral": True, "context": "选型决策"},
    {"text": "预算有限但希望积分商城和用户运营一起做，应该优先选哪类供应商", "stage": DECISION, "pattern": "vendor_choice", "brand_neutral": True, "context": "采购优先级"},
    {"text": "我们倾向选兑吧，但 CFO 问为什么不用有赞，说有赞更知名，我怎么解释两者的定位差异", "stage": DECISION, "pattern": "internal_justification", "brand_neutral": False, "context": "内部汇报"},
    {"text": "我们 App 自研积分跑了 3 年，兑吧销售给我们演示了功能基本够用，但迁移风险怎么评估，历史积分数据能平移吗", "stage": DECISION, "pattern": "purchase_risk", "brand_neutral": False, "context": "迁移决策"},
    {"text": "签了年度合同之后平台服务质量下降怎么办，SLA 和违约条款怎么谈", "stage": DECISION, "pattern": "commercial_terms", "brand_neutral": True, "context": "合同条款"},
    {"text": "兑吧接入超过 14000 个 App，但主要是哪类 App，互动广告和积分商城业务适合我们视频内容 App 吗", "stage": DECISION, "pattern": "competitive_comp", "brand_neutral": False, "context": "内容App适配性"},
    {"text": "银行 App 用积分运营 SaaS，兑吧和星耀谁的金融合规经验更丰富", "stage": DECISION, "pattern": "competitive_comp", "brand_neutral": False, "context": "金融合规对比"},
    {"text": "兑吧和微盟都说能做用户运营，我们是独立 App，最后采购时应该怎么取舍", "stage": DECISION, "pattern": "competitive_comp", "brand_neutral": False, "context": "最终竞品取舍"},
]


def generate_rule_matrix_queryset(brand_config: dict, strategy: str = "rule_matrix_v1") -> dict:
    if _is_duiba_app_ops_profile(brand_config):
        return _generate_duiba_queryset(brand_config, strategy)

    topics = _topics(brand_config)
    competitors = _competitor_names(brand_config)
    queries: list[dict] = []

    for topic in topics:
        related = competitors[:3]
        queries.extend(
            [
                _query(
                    topic,
                    f"{_segment_prefix(brand_config)}{topic}有哪些成熟供应商？",
                    DISCOVERY,
                    "category_rec",
                    "vendor_recommendation",
                    related,
                ),
                _query(
                    topic,
                    f"选择{topic}服务商时，应该重点比较哪些能力？",
                    DECISION,
                    "vendor_choice",
                    "decision_criteria",
                    related,
                ),
                _query(
                    topic,
                    f"{brand_config['entity_name']}和{_competitor_phrase(competitors)}在{topic}方面有什么差异？",
                    EVALUATION,
                    "competitive_comp",
                    "competitive_comparison",
                    related,
                ),
            ]
        )

    selected_queries = _select_with_topic_coverage(queries, topics, _max_queries(len(topics), "30"))
    normalized = []
    for index, query in enumerate(selected_queries, start=1):
        normalized.append({"query_id": f"q_{index:03d}", **query})

    return {
        "queryset_id": f"qs_{uuid4().hex[:12]}",
        "queryset_version": strategy,
        "matrix_api_request_id": f"mx_local_{uuid4().hex[:12]}",
        "queries": normalized,
    }


def _generate_duiba_queryset(brand_config: dict, strategy: str) -> dict:
    competitors = _competitor_names(brand_config)
    topics = _topics(brand_config)
    selected_items = _select_with_topic_coverage(
        [
            {
                **item,
                "topic": _duiba_topic_for_item(item["text"], item["context"], brand_config),
            }
            for item in DUiBA_SCENARIO_QUERIES
        ],
        topics,
        _max_queries(len(topics), str(len(DUiBA_SCENARIO_QUERIES))),
    )
    queries = []
    for index, item in enumerate(selected_items, start=1):
        stage = item["stage"]
        pattern = item["pattern"]
        cell_id = matrix_cell_id(stage, pattern)
        policy = policy_for(stage, pattern)
        queries.append(
            {
                "query_id": f"q_{index:03d}",
                "query_text": item["text"],
                "query_layer": policy["query_layer"],
                "run_scope": policy["run_scope"],
                "journey_stage": stage,
                "metric_scope": policy["metric_scope"],
                "topic": item["topic"],
                "query_pattern": pattern,
                "intent_type": f"{STAGE_TO_INTENT[stage]}_{pattern}",
                "related_competitors": _related_competitors_for_query(item["text"], competitors),
                "source_dimension_json": {
                    "journey_stage": stage,
                    "context": item["context"],
                    "brand_neutral": item["brand_neutral"],
                    "source_type": "duiba_scenario_library_v4",
                    "matrix_cell_id": cell_id,
                },
                "matrix_cell_id": cell_id,
                "prompt_template_id": "duiba_app_ops_v4",
                "lifecycle_status": "active",
            }
        )

    return {
        "queryset_id": f"qs_{uuid4().hex[:12]}",
        "queryset_version": f"{strategy}:duiba_app_ops_v4",
        "matrix_api_request_id": f"mx_local_duiba_{uuid4().hex[:12]}",
        "queries": queries,
    }


def _is_duiba_app_ops_profile(brand_config: dict) -> bool:
    names = [brand_config.get("entity_name"), *brand_config.get("entity_aliases", [])]
    if not any("兑吧" in str(name) or str(name).lower() == "duiba" for name in names):
        return False
    haystack = " ".join(
        [
            *[str(value) for value in brand_config.get("industry_segments", [])],
            *[
                str(item.get("business_line") or item.get("topic_name") or "")
                for item in brand_config.get("topics", [])
                if isinstance(item, dict)
            ],
        ]
    )
    return any(term in haystack for term in ("积分", "会员", "互动广告", "App", "运营"))


def _duiba_topic_for_item(text: str, context: str, brand_config: dict) -> str:
    topic_values = _topics(brand_config)
    if "互动广告" in text or "互动广告" in context:
        return "互动广告"
    if any(term in text or term in context for term in ("会员", "权益")):
        return "会员权益"
    if "积分" in text or "积分" in context:
        return "积分商城"
    if "广告" in text or "广告" in context:
        return "互动广告"
    if any(term in context for term in ("金融", "内容", "出行", "通用", "技术", "数据", "市场", "产品", "迁移", "内部", "效果", "选型", "定价", "合同")):
        return topic_values[0] if topic_values else "积分商城"
    return topic_values[0] if topic_values else "品牌核心业务"


def _max_queries(minimum_topics: int, default: str) -> int:
    configured = int(os.getenv("MAX_QUERIES_PER_RUN", default))
    return max(1, minimum_topics, configured)


def _select_with_topic_coverage(items: list[dict], topics: list[str], max_queries: int) -> list[dict]:
    if len(items) <= max_queries:
        return items

    selected = []
    selected_ids = set()
    for topic in topics:
        for index, item in enumerate(items):
            if index in selected_ids:
                continue
            if item.get("topic") == topic:
                selected.append(item)
                selected_ids.add(index)
                break

    for index, item in enumerate(items):
        if len(selected) >= max_queries:
            break
        if index in selected_ids:
            continue
        selected.append(item)
        selected_ids.add(index)

    return selected


def _related_competitors_for_query(text: str, competitors: list[str]) -> list[str]:
    mentioned = [competitor for competitor in competitors if competitor and competitor in text]
    if mentioned:
        return mentioned
    return competitors[:3]


def _topics(brand_config: dict) -> list[str]:
    values = [
        str(item.get("business_line") or item.get("topic_name") or "").strip()
        for item in brand_config.get("topics", [])
        if isinstance(item, dict)
    ]
    values = [value for value in values if value]
    return list(dict.fromkeys(values)) or ["品牌核心业务"]


def _competitor_names(brand_config: dict) -> list[str]:
    return [
        str(item.get("name", "")).strip()
        for item in brand_config.get("competitors", [])
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    ]


def _segment_prefix(brand_config: dict) -> str:
    segments = [str(value).strip() for value in brand_config.get("industry_segments", []) if str(value).strip()]
    return f"{segments[0]}里，" if segments else ""


def _competitor_phrase(competitors: list[str]) -> str:
    if competitors:
        return "、".join(competitors[:2])
    return "主要竞品"


def _query(
    topic: str,
    text: str,
    stage: str,
    query_pattern: str,
    intent_type: str,
    competitors: list[str],
) -> dict:
    policy = policy_for(stage, query_pattern)
    cell_id = matrix_cell_id(stage, query_pattern)
    return {
        "query_text": text,
        "query_layer": policy["query_layer"],
        "run_scope": policy["run_scope"],
        "journey_stage": stage,
        "metric_scope": policy["metric_scope"],
        "topic": topic,
        "query_pattern": query_pattern,
        "intent_type": intent_type,
        "related_competitors": competitors,
        "matrix_cell_id": cell_id,
        "source_dimension_json": {"matrix_cell_id": cell_id},
    }
