from __future__ import annotations

from typing import Any


TEMPLATE_SYSTEM_VERSION = "geo_content_templates_v1.0.0-mvp"

PLATFORM_RULES_DEFAULT = {
    "universal_rules": (
        "首句即结论；数据前置于修饰；优先使用 Markdown 标题、表格、列表；"
        "段落保持 80-150 字；实体名称保持一致；关键数据和声明需要可验证出处。"
    ),
    "platform_specific_hints": {
        "deepseek": "对比类内容倾向引用首句含量化结论的段落。",
        "kimi": "倾向引用段落末尾有明确推荐和适用场景说明的内容。",
        "doubao": "偏好完整的问答结构。",
        "tongyi": "对表格结构化数据引用率较高。",
        "wenxin": "倾向引用包含第三方来源标注的内容。",
        "yuanbao": "对列表结构引用率较高。",
    },
}

CONTENT_TEMPLATES: list[dict[str, Any]] = [
    {
        "template_id": "tpl_product_capability",
        "template_version": "1.0.0",
        "display_name": "产品能力介绍页",
        "description": "围绕产品定位、核心能力、适用场景和数据总结生成官网产品能力内容。",
        "action_types": ["foundational_content"],
        "target_funnel_stages": ["tofu", "mofu"],
        "target_query_patterns": ["scenario_explore", "category_rec"],
        "required_material_fields": ["products"],
        "optional_material_fields": ["data_points", "case_studies", "certifications"],
        "platform_rules_slot": True,
        "output_format": "markdown",
        "prompt_instruction": (
            "【模板要求：产品能力介绍页】\n"
            "按以下结构输出，每节使用 Markdown H2 分节（##）：\n"
            "## 产品定位 — 一句话定位，30 字以内\n"
            "## 核心能力 — 每项能力用 **特性名**：描述 格式列出\n"
            "## 适用场景 — 场景名 + 简短说明\n"
            "数据指标用粗体，数据后标注来源或标注「数据来源：诊断报告」。\n"
        ),
        "status": "active",
        "effectiveness": {"total_deployments": 0, "up_count": 0, "down_count": 0, "effectiveness_score": None},
    },
    {
        "template_id": "tpl_competitive_comparison",
        "template_version": "1.0.0",
        "display_name": "竞品对比页",
        "description": "面向竞品比较问题，生成客观、结构化、可验证的对比页内容。",
        "action_types": ["competitive_counter"],
        "target_funnel_stages": ["mofu", "bofu"],
        "target_query_patterns": ["competitive_comp", "decision_confirm"],
        "required_material_fields": ["competitors"],
        "optional_material_fields": ["products", "data_points", "case_studies"],
        "platform_rules_slot": True,
        "output_format": "markdown",
        "prompt_instruction": (
            "【模板要求：竞品对比页】\n"
            "1. 首段 2-3 句交代对比背景和结论。\n"
            "2. **必须使用 Markdown 表格**，格式：\n"
            "| 比较维度 | {品牌名} | 竞品A | 竞品B |\n"
            "|---|---|---|---|\n"
            "| 功能完整性 | ... | ... | ... |\n"
            "| 适用规模 | ... | ... | ... |\n"
            "（维度行可根据实际素材增删）\n"
            "3. 表格后附脚注说明数据来源，不编造对比数据。\n"
        ),
        "status": "active",
        "effectiveness": {"total_deployments": 0, "up_count": 0, "down_count": 0, "effectiveness_score": None},
    },
    {
        "template_id": "tpl_evidence_enhance",
        "template_version": "1.0.0",
        "display_name": "证据增强页",
        "description": "针对负面、缺失或误解信号，生成高事实密度的证据增强内容。",
        "action_types": ["evidence_enhance"],
        "target_funnel_stages": ["mofu", "bofu"],
        "target_query_patterns": ["deep_background", "decision_confirm", "category_rec"],
        "required_material_fields": ["data_points"],
        "optional_material_fields": ["certifications", "case_studies", "products"],
        "platform_rules_slot": True,
        "output_format": "markdown",
        "prompt_instruction": (
            "【模板要求：证据增强页】\n"
            "首句直接给出核心事实或量化结论（不要先说“本篇...”）。\n"
            "后续段落逐一列出 3-5 条可验证证据，每条注明来源或标注「数据来源：诊断报告」。\n"
            "避免纯案例堆砌，优先用数据、排名、引用量等量化证据。\n"
        ),
        "status": "active",
        "effectiveness": {"total_deployments": 0, "up_count": 0, "down_count": 0, "effectiveness_score": None},
    },
    {
        "template_id": "tpl_scenario_solution",
        "template_version": "1.0.0",
        "display_name": "场景解决方案页",
        "description": "围绕场景痛点、方案映射和客户案例生成官网解决方案页。",
        "action_types": ["foundational_content"],
        "target_funnel_stages": ["tofu", "mofu"],
        "target_query_patterns": ["scenario_explore", "category_rec"],
        "required_material_fields": ["products"],
        "optional_material_fields": ["case_studies", "data_points", "competitors"],
        "platform_rules_slot": True,
        "output_format": "markdown",
        "prompt_instruction": (
            "【模板要求：场景解决方案页】\n"
            "按以下结构输出：\n"
            "## 场景痛点 — 列出主要场景及其对应的核心痛点\n"
            "## 方案映射 — 每项场景用 **场景**：描述 → **方案**：描述 格式\n"
            "## 客户案例 — 1-2 个案例摘要（需有来源）\n"
        ),
        "status": "active",
        "effectiveness": {"total_deployments": 0, "up_count": 0, "down_count": 0, "effectiveness_score": None},
    },
    {
        "template_id": "tpl_brand_authority",
        "template_version": "1.0.0",
        "display_name": "品牌实力页",
        "description": "围绕品牌背景、核心数据、认证与客户矩阵生成权威事实页。",
        "action_types": ["evidence_enhance", "foundational_content"],
        "target_funnel_stages": ["tofu", "mofu", "bofu"],
        "target_query_patterns": ["deep_background", "decision_confirm", "category_rec"],
        "required_material_fields": ["brand_story"],
        "optional_material_fields": ["data_points", "certifications", "case_studies", "products"],
        "platform_rules_slot": True,
        "output_format": "markdown",
        "prompt_instruction": (
            "【模板要求：品牌实力页】\n"
            "1. 首段给出品牌定位句/核心差异化声明（一句定性）。\n"
            "2. 用 Markdown 表格展示 4-6 个品牌关键指标（成立年份/覆盖客户数/行业排名等），\n"
            "   格式：指标名 | 数值/描述 | 说明\n"
            "3. 认证资质节：列表格式列出已验证的认证或合作。\n"
            "4. 核心价值主张：1-2 句收尾。\n"
        ),
        "status": "active",
        "effectiveness": {"total_deployments": 0, "up_count": 0, "down_count": 0, "effectiveness_score": None},
    },
]


def build_brand_material(contract: dict[str, Any]) -> dict[str, Any]:
    brand = contract.get("main_brand") or {}
    brand_config = contract.get("brand_config") or {}
    report = contract.get("report") or {}
    topics = [topic for topic in brand_config.get("topics") or [] if isinstance(topic, dict)]
    global_metrics = report.get("global") or _metrics_from_contract_rows(contract.get("key_metrics") or [])
    competitors = _competitors_from_report(report)
    sources = report.get("sources") or []
    data_points = _data_points(global_metrics)

    products = [
        {
            "name": topic.get("business_line") or topic.get("topic_name"),
            "one_liner": topic.get("topic_name") or topic.get("business_line") or "核心业务场景",
            "core_features": [topic.get("topic_name")] if topic.get("topic_name") else [],
            "target_users": [],
            "differentiators": [],
        }
        for topic in topics
        if topic.get("business_line") or topic.get("topic_name")
    ]

    brand_story = {
        "founded_year": None,
        "headquarters": None,
        "employee_count": None,
        "mission_statement": brand_config.get("description"),
        "milestones": [],
        "ecosystem_partners": [],
    }
    field_coverage = {
        "brand_name": bool(brand.get("brand_name") or brand.get("short_name")),
        "products": bool(products),
        "data_points": bool(data_points),
        "competitors": bool(competitors),
        "certifications": False,
        "case_studies": bool(report.get("source_references")),
        "brand_story": bool(brand_story.get("mission_statement") or brand_story.get("milestones") or brand_story.get("ecosystem_partners")),
    }

    return {
        "brand_name": brand.get("brand_name") or brand.get("short_name"),
        "brand_aliases": brand.get("aliases") or brand_config.get("entity_aliases") or [],
        "industry": _first(brand_config.get("industry_segments")) or brand.get("category"),
        "brand_domain": _brand_domain(sources),
        "source": "derived",
        "products": products,
        "data_points": data_points,
        "competitors": competitors,
        "certifications": [],
        "case_studies": _case_studies(report),
        "brand_story": brand_story,
        "field_coverage": field_coverage,
        "content_priority_gaps": _priority_gaps(field_coverage, report),
    }


def brand_material_summary(brand_material: dict[str, Any]) -> dict[str, Any]:
    coverage = brand_material.get("field_coverage") or {}
    return {
        "source": brand_material.get("source") or "derived",
        "field_coverage": coverage,
        "available_fields": [field for field, present in coverage.items() if present],
        "content_priority_gaps": brand_material.get("content_priority_gaps") or [],
    }


def template_context(
    contract: dict[str, Any],
    action: dict[str, Any] | None,
    template_id: str | None = None,
    template_version: str | None = None,
) -> dict[str, Any]:
    brand_material = build_brand_material(contract)
    candidates = template_candidates(action, brand_material)
    selected = resolve_template(action, brand_material, template_id=template_id, template_version=template_version)
    if template_id and not selected:
        raise ValueError("template_id is not available for this action and material context.")
    return {
        "template_recommendation": selected,
        "template_candidates": candidates,
        "brand_material_summary": brand_material_summary(brand_material),
        "brand_material": brand_material,
        "platform_rules_default": PLATFORM_RULES_DEFAULT,
        "template_system_version": TEMPLATE_SYSTEM_VERSION,
    }


def resolve_template(
    action: dict[str, Any] | None,
    brand_material: dict[str, Any],
    template_id: str | None = None,
    template_version: str | None = None,
) -> dict[str, Any] | None:
    candidates = template_candidates(action, brand_material)
    if template_id:
        return next(
            (
                candidate
                for candidate in candidates
                if candidate.get("template_id") == template_id
                and (not template_version or candidate.get("template_version") == template_version)
            ),
            None,
        )
    return candidates[0] if candidates else None


def template_candidates(action: dict[str, Any] | None, brand_material: dict[str, Any]) -> list[dict[str, Any]]:
    semantic_action_type = _semantic_action_type(action)
    if not semantic_action_type:
        return []
    trigger_cell = _trigger_cell(action, semantic_action_type)
    preferred_template_id = _preferred_template_id(action, semantic_action_type)
    funnel_stage, query_pattern = _split_trigger_cell(trigger_cell)
    available_fields = {
        field for field, present in (brand_material.get("field_coverage") or {}).items() if present
    }
    highest_priority_gaps = {
        gap.get("field")
        for gap in brand_material.get("content_priority_gaps") or []
        if isinstance(gap, dict) and gap.get("priority") == "highest"
    }

    action_matches = [
        template
        for template in CONTENT_TEMPLATES
        if template.get("status") == "active" and semantic_action_type in (template.get("action_types") or [])
    ]
    qualified = [
        template
        for template in action_matches
        if all(field in available_fields for field in template.get("required_material_fields") or [])
    ]
    if not qualified and "brand_name" in available_fields:
        qualified = action_matches

    enriched = [
        _candidate_summary(
            template,
            available_fields=available_fields,
            highest_priority_gaps=highest_priority_gaps,
            funnel_stage=funnel_stage,
            query_pattern=query_pattern,
            semantic_action_type=semantic_action_type,
            preferred_template_id=preferred_template_id,
        )
        for template in qualified
    ]
    enriched.sort(key=lambda item: item.get("match_score", 0), reverse=True)
    return enriched


def compact_template(template: dict[str, Any] | None) -> dict[str, Any] | None:
    if not template:
        return None
    keys = (
        "template_id",
        "template_version",
        "display_name",
        "description",
        "action_types",
        "target_funnel_stages",
        "target_query_patterns",
        "required_material_fields",
        "optional_material_fields",
        "platform_rules_slot",
        "output_format",
        "prompt_instruction",
        "matched_reason",
        "material_coverage",
        "match_score",
    )
    return {key: template.get(key) for key in keys if key in template}


def _candidate_summary(
    template: dict[str, Any],
    *,
    available_fields: set[str],
    highest_priority_gaps: set[str],
    funnel_stage: str,
    query_pattern: str,
    semantic_action_type: str,
    preferred_template_id: str | None,
) -> dict[str, Any]:
    required = template.get("required_material_fields") or []
    optional = template.get("optional_material_fields") or []
    missing_required = [field for field in required if field not in available_fields]
    optional_hit = [field for field in optional if field in available_fields]
    score = 0.0
    if funnel_stage in (template.get("target_funnel_stages") or []):
        score += 10
    if query_pattern in (template.get("target_query_patterns") or []):
        score += 10
    score += len(optional_hit) * 3
    for field in highest_priority_gaps:
        if field in required:
            score += 25
    if preferred_template_id and template.get("template_id") == preferred_template_id:
        score += 8
    effectiveness_score = (template.get("effectiveness") or {}).get("effectiveness_score")
    score += float(effectiveness_score) * 20 if effectiveness_score is not None else 5
    deployments = int((template.get("effectiveness") or {}).get("total_deployments") or 0)
    if deployments < 5:
        score += (5 - deployments) * 2
    if not missing_required:
        score += 6

    summary = compact_template(template) or {}
    summary.update(
        {
            "semantic_action_type": semantic_action_type,
            "match_score": round(score, 2),
            "matched_reason": _matched_reason(template, missing_required, optional_hit),
            "material_coverage": {
                "required_fields": required,
                "optional_fields": optional,
                "available_fields": sorted(available_fields),
                "missing_required_fields": missing_required,
                "optional_hits": optional_hit,
            },
        }
    )
    return summary


def _matched_reason(template: dict[str, Any], missing_required: list[str], optional_hit: list[str]) -> str:
    if missing_required:
        return f"素材字段不足，按品牌基础信息降级匹配：缺少 {', '.join(missing_required)}。"
    if optional_hit:
        return f"动作类型匹配，且素材覆盖 {', '.join(optional_hit)}。"
    return f"动作类型匹配 {template.get('display_name')}。"


def _semantic_action_type(action: dict[str, Any] | None) -> str | None:
    if not action:
        return None
    action_type = str(action.get("action_type") or "").strip()
    if action_type in {"evidence_enhance", "foundational_content", "competitive_counter"}:
        return action_type
    text = " ".join(
        str(value or "")
        for value in (
            action_type,
            action.get("action_name"),
            action.get("description"),
            " ".join(action.get("output_assets") or []),
        )
    )
    if action_type == "content_optimization":
        if any(keyword in text for keyword in ("竞品", "对比", "压制", "competitive")):
            return "competitive_counter"
        if any(keyword in text for keyword in ("证据", "信源", "引用", "负面", "澄清", "权威", "evidence")):
            return "evidence_enhance"
        return "foundational_content"
    return None


def _trigger_cell(action: dict[str, Any] | None, semantic_action_type: str) -> str:
    explicit = str((action or {}).get("trigger_cell") or "").strip()
    if "×" in explicit:
        return explicit
    if semantic_action_type == "competitive_counter":
        return "mofu×competitive_comp"
    if semantic_action_type == "evidence_enhance":
        return "mofu×deep_background"
    return "mofu×category_rec"


def _preferred_template_id(action: dict[str, Any] | None, semantic_action_type: str) -> str | None:
    text = " ".join(
        str(value or "")
        for value in (
            (action or {}).get("action_name"),
            (action or {}).get("description"),
            " ".join((action or {}).get("output_assets") or []),
        )
    )
    if semantic_action_type == "competitive_counter":
        return "tpl_competitive_comparison"
    if semantic_action_type == "evidence_enhance":
        return "tpl_brand_authority" if any(keyword in text for keyword in ("品牌实力", "背景", "权威")) else "tpl_evidence_enhance"
    if any(keyword in text for keyword in ("场景", "解决方案")):
        return "tpl_scenario_solution"
    return "tpl_product_capability" if semantic_action_type == "foundational_content" else None


def _split_trigger_cell(trigger_cell: str) -> tuple[str, str]:
    parts = trigger_cell.split("×", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return "mofu", "category_rec"


def _data_points(global_metrics: dict[str, Any]) -> list[dict[str, Any]]:
    labels = {
        "visibility": "可见度",
        "natural_visibility": "自然可见度",
        "assisted_visibility": "解析可见度",
        "visibility_lift": "品牌上下文提升",
        "rank": "平均位次",
        "sentiment_score": "舆情指数",
        "ai_recommend_score": "AI 推荐度",
        "own_citations": "品牌自有引用",
        "competitor_suppression_rate": "竞品压制率",
    }
    points = []
    for key, label in labels.items():
        value = global_metrics.get(key)
        if value is None:
            continue
        points.append({"metric": label, "value": str(value), "source_url": None, "verified": True})
    return points


def _metrics_from_contract_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for row in rows:
        if not isinstance(row, dict) or not row.get("metric_id"):
            continue
        value = row.get("current_value")
        if value is not None:
            metrics[str(row["metric_id"])] = value
    return metrics


def _competitors_from_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    competitors = []
    for item in report.get("competitor_ranking") or []:
        if not isinstance(item, dict):
            continue
        name = item.get("brand") or item.get("name")
        if name:
            competitors.append({"name": name, "aliases": [], "key_strengths": [], "key_weaknesses": []})
    return competitors


def _case_studies(report: dict[str, Any]) -> list[dict[str, Any]]:
    cases = []
    for ref in report.get("source_references") or []:
        if not isinstance(ref, dict):
            continue
        url = ref.get("url")
        if url:
            cases.append({"client_name": ref.get("domain") or "公开引用页面", "summary": ref.get("snippet") or url, "source_url": url})
    return cases[:5]


def _priority_gaps(field_coverage: dict[str, bool], report: dict[str, Any]) -> list[dict[str, Any]]:
    gaps = []
    if not field_coverage.get("data_points") and report.get("insights"):
        gaps.append({"field": "data_points", "in_uploaded": False, "in_crawled": False, "priority": "highest", "reason": "诊断报告存在待优化项，但缺少可引用量化数据。"})
    if not field_coverage.get("case_studies") and field_coverage.get("products"):
        gaps.append({"field": "case_studies", "in_uploaded": False, "in_crawled": False, "priority": "high", "reason": "已有产品/场景信息，但缺少案例证据。"})
    return gaps


def _brand_domain(sources: Any) -> str | None:
    for source in sources or []:
        if isinstance(source, dict) and source.get("domain") and (
            source.get("ownership") == "brand_owned"
            or source.get("is_brand_owned") is True
            or source.get("type") in {"品牌自有", "自有"}
        ):
            return source.get("domain")
    return None


def _first(values: Any) -> Any:
    if isinstance(values, list) and values:
        return values[0]
    return None
