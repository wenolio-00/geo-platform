import asyncio

from service import context_extractor as module
from service.context_extractor import ContextExtractor


def test_context_extractor_uses_shared_llm_task(monkeypatch):
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


def test_context_extractor_requires_configured_llm(monkeypatch):
    monkeypatch.setenv("INSPECTION_PLATFORMS", "GPT")
    monkeypatch.delenv("GPT_API_KEY", raising=False)
    monkeypatch.delenv("GPT_BASE_URL", raising=False)

    try:
        asyncio.run(
            ContextExtractor().extract_context(
                {"topic_name": "积分商城管理工具", "business_line": "积分商城"},
                "兑吧",
            )
        )
    except RuntimeError as error:
        assert "configured LLM is not available" in str(error)
    else:
        raise AssertionError("expected missing LLM configuration error")
