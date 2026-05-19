from service import content_generation as cg


class MemoryStore:
    def __init__(self):
        self.data = {}

    def read(self):
        return dict(self.data)

    def get(self, key):
        value = self.data.get(key)
        return dict(value) if isinstance(value, dict) else None

    def upsert(self, key, value):
        self.data[key] = dict(value)
        return value


def _contract():
    return {
        "contract_version": "dashboard_from_report_data_v1",
        "latest_run_id": "run_before",
        "report": {"report_id": "report_before"},
        "main_brand": {
            "brand_id": "brand_test",
            "brand_config_id": "bc_test",
            "entity_id": "entity_test",
            "brand_name": "兑吧",
            "short_name": "兑吧",
        },
        "brand_config": {"brand_config_id": "bc_test", "entity_id": "entity_test"},
        "queryset": {
            "queryset_id": "qs_test",
            "queryset_version": "rule_matrix_v1",
            "queries": [{"query_id": "q_001"}],
        },
        "lineage": {
            "brand_config_id": "bc_test",
            "entity_id": "entity_test",
            "queryset_id": "qs_test",
            "queryset_version": "rule_matrix_v1",
            "aggregation_version": "report_aggregation_v2",
        },
        "optimization_actions": [
            {
                "action_id": "action_1",
                "action_name": "补齐核心选型问答",
                "action_type": "content_optimization",
                "output_assets": ["FAQ"],
                "related_intent_ids": ["intent_1"],
            }
        ],
        "cross_topic_rules": [
            {
                "rule_id": "rule_content",
                "rule_name": "内容规则",
                "applies_to": ["content_optimization"],
                "template": "主张 + 事实 + 证据",
                "required_elements": ["事实", "证据"],
            }
        ],
        "rule_activation": {"stores": {"active_rules_store": []}},
    }


def _run(run_id, visibility, rank):
    return {
        "run_id": run_id,
        "status": "completed",
        "report_data": {
            "lineage": {"queryset_id": "qs_test", "queryset_version": "rule_matrix_v1"},
            "global": {
                "visibility": visibility,
                "rank": rank,
                "sentiment_score": 0.5,
                "ai_recommend_score": 10,
                "own_citations": 1,
                "competitor_suppression_rate": 0.2,
            },
        },
    }


def test_content_generation_prefers_prompt_output_and_sanitizes_meta_lines(monkeypatch):
    versions = MemoryStore()
    feedback = MemoryStore()
    attribution = MemoryStore()
    monkeypatch.setattr(cg, "content_versions_store", versions)
    monkeypatch.setattr(cg, "content_feedback_store", feedback)
    monkeypatch.setattr(cg, "effect_attribution_store", attribution)
    monkeypatch.setattr(cg, "_load_dashboard_contract", lambda brand_id=None: _contract())

    async def fake_invoke_llm_task(**kwargs):
        assert kwargs["task_type"] == "content_generation"
        assert kwargs["payload"]["llm_provider"] == "claude"
        assert kwargs["payload"]["llm_options"]["web_search_mode"] == "responses_web_search"
        return {
            "provider": "claude",
            "platform": "claude",
            "model": "claude-test",
            "web_search_enabled": True,
            "web_search_mode": "responses_web_search",
            "raw_text": "以下为官网正文\n\n兑吧聚焦积分商城场景，持续优化品牌官网内容表达，帮助潜在客户更快理解产品能力与业务价值。\n\n在官网内容中，我们以清晰的场景说明、稳定的能力介绍和审慎的事实表达，呈现更适合金融机构评估与决策的信息。",
        }

    monkeypatch.setattr(cg, "invoke_llm_task", fake_invoke_llm_task)

    draft = cg.generate_optimized_draft(
        {"brand_id": "brand_test", "action_id": "action_1", "rule_id": "rule_content"}
    )

    assert draft["generation_source"] == "prompt_driven_backend"
    assert "以下为官网正文" not in draft["generated_text"]
    assert "建议围绕" not in draft["generated_text"]
    assert "兑吧聚焦积分商城场景" in draft["generated_text"]
    assert draft["generation_metadata"]["provider"] == "claude"
    assert draft["generation_metadata"]["web_search_mode"] == "responses_web_search"


def test_content_generation_fallback_requires_explicit_opt_in(monkeypatch):
    versions = MemoryStore()
    monkeypatch.setattr(cg, "content_versions_store", versions)
    monkeypatch.setattr(cg, "_load_dashboard_contract", lambda brand_id=None: _contract())

    async def failing_invoke_llm_task(**kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(cg, "invoke_llm_task", failing_invoke_llm_task)
    monkeypatch.delenv("ALLOW_CONTENT_GENERATION_FALLBACK", raising=False)

    try:
        cg.generate_optimized_draft(
            {"brand_id": "brand_test", "action_id": "action_1", "rule_id": "rule_content"}
        )
    except RuntimeError as error:
        assert "claude content_generation failed" in str(error)
    else:
        raise AssertionError("expected content generation failure without fallback opt-in")

    monkeypatch.setenv("ALLOW_CONTENT_GENERATION_FALLBACK", "true")
    draft = cg.generate_optimized_draft(
        {"brand_id": "brand_test", "action_id": "action_1", "rule_id": "rule_content"}
    )

    assert draft["generation_source"] == "prompt_fallback_backend"
    assert draft["generation_metadata"]["provider"] == "claude"
    assert draft["generation_metadata"]["llm_error_type"] == "RuntimeError"


def test_content_version_feedback_and_effect_attribution_are_persisted(monkeypatch):
    versions = MemoryStore()
    feedback = MemoryStore()
    attribution = MemoryStore()
    monkeypatch.setattr(cg, "content_versions_store", versions)
    monkeypatch.setattr(cg, "content_feedback_store", feedback)
    monkeypatch.setattr(cg, "effect_attribution_store", attribution)
    monkeypatch.setattr(cg, "_load_dashboard_contract", lambda brand_id=None: _contract())
    monkeypatch.setattr(
        cg,
        "get_run",
        lambda run_id: {
            "run_before": _run("run_before", 0.2, 3),
            "run_after": _run("run_after", 0.5, 2),
        }.get(run_id),
    )
    monkeypatch.setattr(cg, "_generate_publish_ready_text", lambda contract, action, rule: ("官网正文", "prompt_fallback_backend"))

    draft = cg.generate_optimized_draft(
        {"brand_id": "brand_test", "action_id": "action_1", "rule_id": "rule_content"}
    )
    content_version_id = draft["content_version_id"]

    assert content_version_id in versions.read()
    assert draft["effect_attribution"]["baseline_run_id"] == "run_before"
    assert draft["effect_attribution"]["status"] == "awaiting_retest"

    result = cg.record_content_feedback(content_version_id, {"signal": "helpful"})

    assert result["feedback_summary"]["helpful"] == 1
    assert versions.get(content_version_id)["feedback_summary"]["net_score"] == 1

    computed = cg.compute_content_effect_attribution(
        content_version_id,
        {"comparison_run_id": "run_after"},
    )

    assert computed["status"] == "computed"
    assert computed["comparison_run_id"] == "run_after"
    assert computed["comparability"]["confidence"] == "high"
    assert computed["effect_delta"]["metrics"]["visibility"]["delta"] == 0.3
    assert computed["effect_delta"]["metrics"]["rank"]["delta"] == 1.0
