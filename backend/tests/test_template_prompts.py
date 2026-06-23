from service import content_generation as cg
from service.content_templates import CONTENT_TEMPLATES, compact_template


EXPECTED_TEMPLATE_IDS = {
    "tpl_product_capability",
    "tpl_competitive_comparison",
    "tpl_evidence_enhance",
    "tpl_scenario_solution",
    "tpl_brand_authority",
}


def _template_by_id(template_id: str) -> dict:
    return next(template for template in CONTENT_TEMPLATES if template.get("template_id") == template_id)


def test_all_content_templates_have_prompt_instruction():
    templates_by_id = {template.get("template_id"): template for template in CONTENT_TEMPLATES}

    assert EXPECTED_TEMPLATE_IDS <= set(templates_by_id)
    for template_id in EXPECTED_TEMPLATE_IDS:
        instruction = templates_by_id[template_id].get("prompt_instruction")
        assert isinstance(instruction, str)
        assert instruction.strip()


def test_compact_template_preserves_prompt_instruction():
    template = _template_by_id("tpl_competitive_comparison")

    compacted = compact_template(template)

    assert compacted is not None
    assert compacted["prompt_instruction"] == template["prompt_instruction"]
    assert "|---|---|---|---|" in compacted["prompt_instruction"]


def test_template_instruction_from_brief_returns_known_instruction():
    template = compact_template(_template_by_id("tpl_brand_authority"))
    brief = {"content_template": template}

    instruction = cg._template_instruction_from_brief(brief)

    assert "【模板要求：品牌实力页】" in instruction
    assert "Markdown 表格展示 4-6 个品牌关键指标" in instruction


def test_template_instruction_from_brief_returns_empty_for_missing_or_unknown_template():
    assert cg._template_instruction_from_brief({}) == ""
    assert cg._template_instruction_from_brief({"content_template": {"template_id": "tpl_missing"}}) == ""


def test_content_generation_user_prompt_injects_template_instruction_before_brief_json():
    template = compact_template(_template_by_id("tpl_scenario_solution"))
    brief = {
        "brand": {"brand_name": "兑吧"},
        "task": {"action_id": "action_1"},
        "content_template": template,
        "available_facts": {},
    }

    prompt = cg._content_generation_user_prompt(brief)

    instruction_index = prompt.index("【模板要求：场景解决方案页】")
    brief_index = prompt.index('"content_template"')
    assert instruction_index < brief_index
    assert "## 方案映射" in prompt
    assert "**场景**：描述 → **方案**：描述" in prompt
