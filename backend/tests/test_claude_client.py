from service.claude_client import ClaudeClient

import asyncio


def test_claude_defaults_to_haiku_45_with_web_search(monkeypatch):
    monkeypatch.delenv("CLAUDE_MODEL", raising=False)
    monkeypatch.delenv("CLAUDE_API_STYLE", raising=False)
    monkeypatch.delenv("CLAUDE_WEB_SEARCH_ENABLED", raising=False)
    monkeypatch.delenv("CLAUDE_WEB_SEARCH_MODE", raising=False)
    monkeypatch.delenv("CLAUDE_WEB_SEARCH_MAX_USES", raising=False)

    client = ClaudeClient()
    payload = client._payload(
        {
            "query_id": "q_001",
            "query_text": "今天积分商城行业有什么新变化？",
            "topic": "积分商城",
            "intent_type": "trend_research",
        },
        {"entity_name": "兑吧"},
    )

    assert payload["model"] == "claude-haiku-4-5-20251001"
    assert payload["tools"] == [
        {
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 5,
        }
    ]


def test_claude_web_search_can_be_disabled(monkeypatch):
    monkeypatch.delenv("CLAUDE_API_STYLE", raising=False)
    monkeypatch.setenv("CLAUDE_WEB_SEARCH_ENABLED", "false")

    client = ClaudeClient()
    payload = client._payload(
        {
            "query_id": "q_001",
            "query_text": "积分商城工具有哪些？",
            "topic": "积分商城",
            "intent_type": "vendor_recommendation",
        },
        {"entity_name": "兑吧"},
    )

    assert "tools" not in payload


def test_claude_openai_style_uses_chat_completions_web_search_options(monkeypatch):
    monkeypatch.setenv("CLAUDE_API_STYLE", "openai")
    monkeypatch.delenv("CLAUDE_WEB_SEARCH_MODE", raising=False)

    client = ClaudeClient()
    payload = client._payload(
        {
            "query_id": "q_001",
            "query_text": "今天积分商城行业有什么新变化？",
            "topic": "积分商城",
            "intent_type": "trend_research",
        },
        {"entity_name": "兑吧"},
    )

    assert payload["messages"][0]["role"] == "system"
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["web_search_options"]["search_context_size"] == "medium"
    assert "tools" not in payload


def test_claude_retries_without_tools_when_gateway_returns_tool_use(monkeypatch):
    monkeypatch.setenv("CLAUDE_API_KEY", "sk-test")
    monkeypatch.setenv("CLAUDE_BASE_URL", "https://api.anthropic.com")
    monkeypatch.setenv("CLAUDE_API_STYLE", "anthropic")

    client = ClaudeClient()
    calls = []

    async def fake_post(payload):
        calls.append(payload)
        if len(calls) == 1:
            return {
                "model": payload["model"],
                "stop_reason": "tool_use",
                "content": [{"type": "tool_use", "name": "web_search", "input": {}}],
            }
        return {
            "model": payload["model"],
            "content": [{"type": "text", "text": '{"answer":"ok","mentioned_brands":[]}'}],
            "usage": {},
        }

    monkeypatch.setattr(client, "_post_with_retry", fake_post)
    result = asyncio.run(
        client.inspect(
            {
                "query_id": "q_001",
                "query_text": "积分商城工具有哪些？",
                "topic": "积分商城",
                "intent_type": "vendor_recommendation",
            },
            {"entity_name": "兑吧"},
        )
    )

    assert result["model"] == "claude-haiku-4-5-20251001"
    assert "tools" in calls[0]
    assert "tools" not in calls[1]
