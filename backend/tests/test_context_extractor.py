import asyncio

from service import context_extractor as module
from service.context_extractor import ContextExtractor


def test_context_extractor_uses_shared_llm_task(monkeypatch):
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "GPT")
    monkeypatch.setenv("INSPECTION_PLATFORMS", "GPT")
    monkeypatch.setenv("GPT_API_KEY", "sk-test")
    monkeypatch.setenv("GPT_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("GPT_MODEL", "gpt-test")
    calls = []

    async def fake_invoke_json_task(**kwargs):
        calls.append(kwargs)
        return {"parsed": {"pain_point": "运营低效", "goal": "提升活跃"}}

    monkeypatch.setattr(module, "invoke_json_task", fake_invoke_json_task)

    result = asyncio.run(
        ContextExtractor().extract_context(
            {"topic_name": "积分商城管理工具", "business_line": "积分商城"},
            "兑吧",
        )
    )

    assert result == {"pain_point": "运营低效", "goal": "提升活跃"}
    assert calls[0]["task_type"] == "context_extraction"
    assert calls[0]["payload"]["web_search_enabled"] is True


def test_context_extractor_uses_fallback_when_llm_is_unavailable(monkeypatch):
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "GPT")
    monkeypatch.setenv("INSPECTION_PLATFORMS", "GPT")
    monkeypatch.delenv("GPT_API_KEY", raising=False)
    monkeypatch.delenv("GPT_BASE_URL", raising=False)
    monkeypatch.delenv("GPT_MODEL", raising=False)

    result = asyncio.run(
        ContextExtractor().extract_context(
            {"topic_name": "积分商城管理工具", "business_line": "积分商城"},
            "兑吧",
        )
    )

    assert result == {"pain_point": "积分商城管理工具效果不稳定", "goal": "提升积分商城效果"}


def test_context_extractor_uses_fallback_when_llm_inference_fails(monkeypatch):
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "GPT")
    monkeypatch.setenv("GPT_API_KEY", "sk-test")
    monkeypatch.setenv("GPT_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("GPT_MODEL", "gpt-test")

    async def failing_invoke_json_task(**kwargs):
        raise RuntimeError("429 rate limit")

    monkeypatch.setattr(module, "invoke_json_task", failing_invoke_json_task)

    result = asyncio.run(
        ContextExtractor().extract_context(
            {"topic_name": "积分商城管理工具", "business_line": "积分商城", "pain_point": "运营效率低"},
            "兑吧",
        )
    )

    assert result == {"pain_point": "运营效率低", "goal": "提升积分商城效果"}


def test_context_extractor_generates_intent_analysis(monkeypatch):
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "GPT")
    monkeypatch.setenv("GPT_API_KEY", "sk-test")
    monkeypatch.setenv("GPT_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("GPT_MODEL", "gpt-test")
    calls = []

    async def fake_invoke_json_task(**kwargs):
        calls.append(kwargs)
        if kwargs["task_type"] == "context_extraction":
            return {"parsed": {"pain_point": "线索跟进低效", "goal": "提升成交率"}}
        return {
            "parsed": {
                "audience_profile": "销售运营和业务负责人",
                "pain_points": [
                    {
                        "pain_point": "客户线索分散",
                        "severity": 5,
                        "goal": "统一线索管理",
                        "ai_questions": [
                            {
                                "question": "CRM系统如何解决客户线索分散的问题？",
                                "intent_type": "scenario_diagnosis",
                            }
                        ],
                    }
                ],
            }
        }

    monkeypatch.setattr(module, "invoke_json_task", fake_invoke_json_task)

    result = asyncio.run(
        ContextExtractor().extract_with_questions(
            topic_name="CRM系统",
            business_line="客户关系管理",
            entity_name="测试品牌",
        )
    )

    assert [call["task_type"] for call in calls] == ["context_extraction", "intent_analysis"]
    assert result["audience_profile"] == "销售运营和业务负责人"
    assert result["pain_points"][0]["severity"] == 5
    assert result["pain_points"][0]["ai_questions"][0]["intent_type"] == "scenario_diagnosis"
