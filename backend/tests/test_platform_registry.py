from service import platform_registry as registry


def test_provider_aliases_canonicalize_to_claude():
    for alias in ("anthropic", "Claude", "CLAUDE", "claude"):
        assert registry._canonical_platform(alias) == "claude"


def test_openai_aliases_canonicalize_to_gpt():
    for alias in ("gpt", "openai", "chatgpt", "GPT"):
        assert registry._canonical_platform(alias) == "GPT"


def test_default_requested_platform_is_claude(monkeypatch):
    monkeypatch.delenv("INSPECTION_PLATFORMS", raising=False)

    assert registry.DEFAULT_TASK_PROVIDER == "claude"
    assert registry.requested_platforms({}) == ["claude"]
    assert registry.requested_platforms({"inspection_mode": "deepseek_live_v1"}) == ["claude"]


def test_llm_task_options_use_configured_provider(monkeypatch):
    monkeypatch.setenv("INSPECTION_PLATFORMS", "GPT")
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "GPT")
    options = registry.llm_task_options(
        "content_generation",
        {
            "web_search_enabled": True,
            "llm_options": {
                "web_search_mode": "responses_web_search",
            },
        },
    )

    assert options["provider"] == "GPT"
    assert options["web_search_enabled"] is True
    assert options["web_search_mode"] == "responses_web_search"


def test_shared_task_default_ignores_inspection_platforms(monkeypatch):
    monkeypatch.delenv("DEFAULT_LLM_PROVIDER", raising=False)
    monkeypatch.setenv("INSPECTION_PLATFORMS", "豆包")

    for task_type in (
        "content_generation",
        "prefill",
        "rule_activation",
        "context_extraction",
        "queryset_matrix",
        "intent_analysis",
    ):
        options = registry.llm_task_options(task_type, {"web_search_enabled": True})
        assert options["provider"] == "claude"

    assert registry.requested_platforms({}) == ["豆包"]


def test_claude_client_uses_openai_compatible(monkeypatch):
    monkeypatch.setenv("CLAUDE_API_KEY", "sk-test")
    monkeypatch.setenv("CLAUDE_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("CLAUDE_MODEL", "gpt-5.5")

    client = registry.create_task_client("Claude")

    assert type(client).__name__ == "OpenAICompatibleClient"
    assert client.platform == "claude"
    assert client.env_prefix == "CLAUDE"
    assert client.model == "gpt-5.5"


def test_gpt_client_uses_gpt_env_prefix(monkeypatch):
    monkeypatch.setenv("GPT_API_KEY", "sk-test")
    monkeypatch.setenv("GPT_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("GPT_MODEL", "gpt-test")

    client = registry.create_platform_clients(["GPT"])[0]

    assert type(client).__name__ == "OpenAICompatibleClient"
    assert client.platform == "GPT"
    assert client.env_prefix == "GPT"


def test_intent_analysis_is_registered_for_supported_providers(monkeypatch):
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "豆包")

    assert "intent_analysis" in registry.LLM_TASK_TYPES
    assert "intent_analysis" in registry.provider_capabilities("claude")["task_modes"]
    assert "intent_analysis" in registry.provider_capabilities("GPT")["task_modes"]
    assert "intent_analysis" in registry.provider_capabilities("豆包")["task_modes"]
    assert registry.llm_task_options("intent_analysis", {"web_search_enabled": True})["provider"] == "豆包"


def test_fallback_providers_are_disabled_by_default(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER_FALLBACK_ENABLED", raising=False)
    monkeypatch.setenv("LLM_PROVIDER_FALLBACK_LIST", "GPT,豆包")

    assert registry.get_fallback_providers("prefill", "claude") == []


def test_fallback_providers_filter_by_task_capability(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER_FALLBACK_ENABLED", "true")
    monkeypatch.setenv("LLM_PROVIDER_FALLBACK_LIST", "DeepSeek,GPT,豆包,gpt,claude")

    assert registry.get_fallback_providers("prefill", "claude") == ["GPT", "豆包"]
    assert registry.get_fallback_providers("queryset_matrix", "claude") == ["GPT"]
