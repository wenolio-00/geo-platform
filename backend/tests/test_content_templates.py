from service.content_templates import build_brand_material, template_candidates, template_context


def _contract(action_type="content_optimization", action_name="补齐核心选型问答", description="补充产品能力和 FAQ"):
    return {
        "main_brand": {"brand_name": "兑吧", "short_name": "兑吧", "aliases": ["Duiba"]},
        "brand_config": {
            "entity_name": "杭州兑吧网络科技有限公司",
            "industry_segments": ["企业服务SaaS"],
            "topics": [{"topic_name": "积分商城", "business_line": "会员权益运营"}],
        },
        "key_metrics": [{"metric_id": "visibility", "current_value": 32.5}],
        "optimization_actions": [
            {
                "action_id": "action_1",
                "action_name": action_name,
                "action_type": action_type,
                "description": description,
                "output_assets": ["官网 FAQ"],
            }
        ],
        "report": {},
    }


def test_template_selector_matches_content_optimization_to_foundational_template():
    contract = _contract()
    action = contract["optimization_actions"][0]
    material = build_brand_material(contract)

    candidates = template_candidates(action, material)

    assert candidates
    assert candidates[0]["semantic_action_type"] == "foundational_content"
    assert candidates[0]["template_id"] in {"tpl_product_capability", "tpl_scenario_solution"}
    assert "products" in candidates[0]["material_coverage"]["available_fields"]


def test_template_selector_uses_competitive_template_for_competitor_actions():
    contract = _contract(action_name="补强竞品对比内容", description="降低竞品压制")
    contract["report"] = {"competitor_ranking": [{"brand": "有赞"}]}
    action = contract["optimization_actions"][0]
    material = build_brand_material(contract)

    candidates = template_candidates(action, material)

    assert candidates[0]["template_id"] == "tpl_competitive_comparison"
    assert candidates[0]["semantic_action_type"] == "competitive_counter"


def test_template_selector_falls_back_when_required_material_is_missing():
    contract = _contract(action_type="content_optimization", action_name="补充证据引用", description="证据和信源不足")
    contract["brand_config"]["topics"] = []
    contract["key_metrics"] = []
    action = contract["optimization_actions"][0]
    material = build_brand_material(contract)

    candidates = template_candidates(action, material)

    assert candidates
    assert candidates[0]["material_coverage"]["missing_required_fields"]
    assert "降级匹配" in candidates[0]["matched_reason"]


def test_template_selector_returns_no_template_for_unknown_action_type():
    contract = _contract(action_type="video_asset", action_name="生成视频脚本", description="短视频素材")
    action = contract["optimization_actions"][0]
    material = build_brand_material(contract)

    assert template_candidates(action, material) == []


def test_template_context_validates_explicit_template_id():
    contract = _contract()
    action = contract["optimization_actions"][0]

    try:
        template_context(contract, action, template_id="tpl_missing")
    except ValueError as error:
        assert "template_id" in str(error)
    else:
        raise AssertionError("expected invalid template_id to raise")
