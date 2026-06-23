import asyncio

from service import llm_tasks


class FakeTaskClient:
    def __init__(self, provider, calls, failures):
        self.provider = provider
        self.calls = calls
        self.failures = failures

    async def invoke_task(self, request):
        self.calls.append({"provider": self.provider, "options": request["options"]})
        error = self.failures.get(self.provider)
        if error:
            raise RuntimeError(error)
        return {"raw_text": f"{self.provider} ok", "model": f"{self.provider}-test"}


def test_invoke_llm_task_falls_back_to_configured_provider(monkeypatch):
    calls = []
    failures = {"claude": "claude request failed with HTTP 503: Service temporarily unavailable"}

    monkeypatch.setenv("LLM_PROVIDER_FALLBACK_ENABLED", "true")
    monkeypatch.setenv("LLM_PROVIDER_FALLBACK_LIST", "GPT,豆包")
    monkeypatch.delenv("DEFAULT_LLM_PROVIDER", raising=False)
    monkeypatch.setattr(
        llm_tasks,
        "create_task_client",
        lambda provider: FakeTaskClient(provider, calls, failures),
    )

    result = asyncio.run(
        llm_tasks.invoke_llm_task(
            task_type="prefill",
            payload={"web_search_enabled": True},
            system_prompt="system",
            user_prompt="user",
        )
    )

    assert [call["provider"] for call in calls] == ["claude", "GPT"]
    assert calls[1]["options"]["provider"] == "GPT"
    assert result["raw_text"] == "GPT ok"
    assert result["provider"] == "GPT"
    assert result["used_fallback"] is True
    assert result["primary_provider"] == "claude"
    assert "HTTP 503" in result["fallback_reason"]


def test_invoke_llm_task_preserves_error_when_fallback_disabled(monkeypatch):
    calls = []
    failures = {"claude": "claude request failed with HTTP 503: Service temporarily unavailable"}

    monkeypatch.delenv("LLM_PROVIDER_FALLBACK_ENABLED", raising=False)
    monkeypatch.setenv("LLM_PROVIDER_FALLBACK_LIST", "GPT")
    monkeypatch.delenv("DEFAULT_LLM_PROVIDER", raising=False)
    monkeypatch.setattr(
        llm_tasks,
        "create_task_client",
        lambda provider: FakeTaskClient(provider, calls, failures),
    )

    try:
        asyncio.run(
            llm_tasks.invoke_llm_task(
                task_type="prefill",
                payload={"web_search_enabled": True},
                system_prompt="system",
                user_prompt="user",
            )
        )
    except RuntimeError as error:
        assert str(error) == failures["claude"]
    else:
        raise AssertionError("expected primary provider error when fallback is disabled")

    assert [call["provider"] for call in calls] == ["claude"]


def test_invoke_llm_task_raises_when_all_providers_fail(monkeypatch):
    calls = []
    failures = {
        "claude": "claude request failed with HTTP 503",
        "GPT": "gpt request failed with HTTP 503",
    }

    monkeypatch.setenv("LLM_PROVIDER_FALLBACK_ENABLED", "true")
    monkeypatch.setenv("LLM_PROVIDER_FALLBACK_LIST", "GPT")
    monkeypatch.delenv("DEFAULT_LLM_PROVIDER", raising=False)
    monkeypatch.setattr(
        llm_tasks,
        "create_task_client",
        lambda provider: FakeTaskClient(provider, calls, failures),
    )

    try:
        asyncio.run(
            llm_tasks.invoke_llm_task(
                task_type="prefill",
                payload={"web_search_enabled": True},
                system_prompt="system",
                user_prompt="user",
            )
        )
    except RuntimeError as error:
        assert "All providers failed for task prefill" in str(error)
        assert "gpt request failed" in str(error)
    else:
        raise AssertionError("expected all providers exhausted error")

    assert [call["provider"] for call in calls] == ["claude", "GPT"]
