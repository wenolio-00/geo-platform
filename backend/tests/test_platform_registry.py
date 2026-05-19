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


def test_claude_client_uses_openai_compatible(monkeypatch):
    monkeypatch.setenv("CLAUDE_API_KEY", "sk-test")
    monkeypatch.setenv("CLAUDE_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("CLAUDE_MODEL", "claude-test")

    client = registry.create_task_client("Claude")

    assert type(client).__name__ == "OpenAICompatibleClient"
    assert client.platform == "claude"
    assert client.env_prefix == "CLAUDE"


def test_gpt_client_uses_gpt_env_prefix(monkeypatch):
    monkeypatch.setenv("GPT_API_KEY", "sk-test")
    monkeypatch.setenv("GPT_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("GPT_MODEL", "gpt-test")

    client = registry.create_platform_clients(["GPT"])[0]

    assert type(client).__name__ == "OpenAICompatibleClient"
    assert client.platform == "GPT"
    assert client.env_prefix == "GPT"
