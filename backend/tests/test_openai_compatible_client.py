import asyncio

from service.platform_clients import openai_compatible as module
from service.platform_clients.openai_compatible import OpenAICompatibleClient


class FakeResponse:
    status_code = 200
    text = "{}"

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "model": "claude-test",
            "output_text": '{"answer":"ok","mentioned_brands":[],"citations":[],"parse_confidence":"high"}',
            "usage": {"total_tokens": 3},
        }


class FakeAsyncClient:
    requests = []

    def __init__(self, timeout):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, headers, json):
        self.requests.append({"url": url, "headers": headers, "json": json})
        return FakeResponse()


def _client(monkeypatch):
    monkeypatch.setenv("CLAUDE_API_KEY", "sk-test")
    monkeypatch.setenv("CLAUDE_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("CLAUDE_MODEL", "claude-test")
    monkeypatch.setenv("CLAUDE_RESPONSES_ENDPOINT", "/responses")
    monkeypatch.setenv("CLAUDE_WEB_SEARCH_ENABLED", "true")
    monkeypatch.setenv("CLAUDE_WEB_SEARCH_MODE", "responses_web_search")
    return OpenAICompatibleClient("claude", "CLAUDE")


def test_responses_inspect_uses_input_tools_and_responses_endpoint(monkeypatch):
    FakeAsyncClient.requests = []
    monkeypatch.setattr(module.httpx, "AsyncClient", FakeAsyncClient)
    client = _client(monkeypatch)

    result = asyncio.run(
        client.inspect(
            {
                "query_id": "q_001",
                "query_text": "test query",
                "topic": "topic",
                "intent_type": "category_rec",
            },
            {"entity_name": "兑吧", "entity_aliases": [], "competitors": []},
            options={"web_search_enabled": True, "web_search_mode": "responses_web_search"},
        )
    )

    request = FakeAsyncClient.requests[-1]
    assert request["url"] == "https://example.test/v1/responses"
    assert "input" in request["json"]
    assert "messages" not in request["json"]
    assert request["json"]["tools"] == [{"type": "web_search"}]
    assert result["provider"] == "claude"
    assert result["platform"] == "claude"
    assert result["web_search_mode"] == "responses_web_search"


def test_responses_task_uses_input_not_messages(monkeypatch):
    client = _client(monkeypatch)

    payload = client._task_payload(
        {
            "task_type": "content_generation",
            "system_prompt": "system",
            "user_prompt": "user",
            "options": {"web_search_enabled": True, "web_search_mode": "responses_web_search"},
        }
    )

    assert "input" in payload
    assert "messages" not in payload
    assert payload["tools"] == [{"type": "web_search"}]
