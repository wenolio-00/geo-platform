import asyncio
import logging

import pytest

from service.platform_clients import openai_compatible as module
from service.platform_clients.doubao_client import DoubaoClient
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
    monkeypatch.setenv("CLAUDE_MODEL", "gpt-5.5")
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


def test_responses_web_search_tool_accepts_search_controls(monkeypatch):
    monkeypatch.setenv("CLAUDE_WEB_SEARCH_MAX_KEYWORD", "2")
    monkeypatch.setenv("CLAUDE_WEB_SEARCH_LIMIT", "10")
    monkeypatch.setenv("CLAUDE_WEB_SEARCH_MAX_TOOL_CALLS", "3")
    monkeypatch.setenv("CLAUDE_WEB_SEARCH_SOURCES", "toutiao,douyin,moji")
    monkeypatch.setenv("CLAUDE_WEB_SEARCH_COUNTRY", "中国")
    monkeypatch.setenv("CLAUDE_WEB_SEARCH_REGION", "浙江")
    monkeypatch.setenv("CLAUDE_WEB_SEARCH_CITY", "杭州")
    client = _client(monkeypatch)

    payload = client._task_payload(
        {
            "task_type": "content_generation",
            "system_prompt": "system",
            "user_prompt": "user",
            "options": {"web_search_enabled": True, "web_search_mode": "responses_web_search"},
        }
    )

    assert payload["tools"] == [
        {
            "type": "web_search",
            "max_keyword": 2,
            "limit": 10,
            "sources": ["toutiao", "douyin", "moji"],
            "user_location": {"type": "approximate", "country": "中国", "region": "浙江", "city": "杭州"},
        }
    ]
    assert payload["max_tool_calls"] == 3


def test_doubao_client_accepts_ark_api_key_and_normalizes_legacy_search_mode(monkeypatch):
    monkeypatch.delenv("DOUBAO_API_KEY", raising=False)
    monkeypatch.setenv("ARK_API_KEY", "ark-test")
    monkeypatch.setenv("DOUBAO_WEB_SEARCH_MODE", "doubao_plugins")

    client = DoubaoClient()

    assert client.api_key == "ark-test"
    assert client.web_search_mode == "responses_web_search"


def test_blind_inspect_prompt_omits_brand_context(monkeypatch):
    client = _client(monkeypatch)
    payload = client._payload(
        {
            "query_id": "q_001",
            "query_text": "积分商城工具有哪些？",
            "topic": "积分商城",
            "intent_type": "category_rec",
        },
        {"entity_name": "兑吧", "entity_aliases": ["Duiba"], "competitors": [{"name": "有赞"}]},
        options={"web_search_enabled": True, "web_search_mode": "responses_web_search", "blind_mode": True},
    )

    prompt = payload["input"][1]["content"]
    assert "兑吧" not in prompt
    assert "Duiba" not in prompt
    assert "有赞" not in prompt
    assert "用户问题" in prompt


def test_assisted_payload_disables_web_search(monkeypatch):
    client = _client(monkeypatch)
    payload = client._payload(
        {
            "query_id": "q_001",
            "query_text": "积分商城工具有哪些？",
            "topic": "积分商城",
            "intent_type": "category_rec",
        },
        {"entity_name": "兑吧", "entity_aliases": ["Duiba"], "competitors": [{"name": "有赞"}]},
        options={
            "web_search_enabled": False,
            "web_search_mode": "responses_web_search",
            "assisted_extraction": True,
            "natural_answer": "自然回答",
            "natural_citations": [],
        },
    )

    assert "tools" not in payload
    assert "plugins" not in payload
    assert "web_search_options" not in payload
    prompt = payload["messages"][1]["content"]
    assert "自然回答" in prompt


def test_json_decode_error_includes_http_context(monkeypatch, caplog):
    class HtmlGatewayResponse:
        status_code = 502
        text = "<html>bad gateway</html>"
        headers = {"content-type": "text/html"}

        def raise_for_status(self):
            return None

        def json(self):
            raise ValueError("Expecting value: line 1 column 1 (char 0)")

    class HtmlGatewayClient(FakeAsyncClient):
        async def post(self, url, headers, json):
            return HtmlGatewayResponse()

    delays = []

    async def fake_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(module.httpx, "AsyncClient", HtmlGatewayClient)
    monkeypatch.setattr(module.asyncio, "sleep", fake_sleep)
    client = _client(monkeypatch)

    with caplog.at_level(logging.WARNING):
        with pytest.raises(RuntimeError) as excinfo:
            asyncio.run(client._post_with_retry({"model": "claude-test"}))

    message = str(excinfo.value)
    assert "claude request failed: JSON decode error" in message
    assert "HTTP status=502" in message
    assert 'body="<html>bad gateway</html>"' in message
    assert "attempt=3/3" in message
    assert delays == [3.0, 6.0]
    assert caplog.records[0].http_status == 502
    assert caplog.records[0].content_type == "text/html"
    assert caplog.records[0].response_body == "<html>bad gateway</html>"


def test_http_status_error_logging_includes_response_body(monkeypatch, caplog):
    class BadGatewayResponse:
        status_code = 502
        text = "upstream unavailable"
        headers = {"content-type": "text/plain"}

        def raise_for_status(self):
            request = module.httpx.Request("POST", "https://example.test/v1/responses")
            raise module.httpx.HTTPStatusError("bad gateway", request=request, response=self)

        def json(self):
            raise ValueError("not json")

    class BadGatewayClient(FakeAsyncClient):
        async def post(self, url, headers, json):
            return BadGatewayResponse()

    async def fake_sleep(delay):
        return None

    monkeypatch.setattr(module.httpx, "AsyncClient", BadGatewayClient)
    monkeypatch.setattr(module.asyncio, "sleep", fake_sleep)
    client = _client(monkeypatch)

    with caplog.at_level(logging.WARNING):
        with pytest.raises(RuntimeError) as excinfo:
            asyncio.run(client._post_with_retry({"model": "claude-test"}))

    message = str(excinfo.value)
    assert "HTTP status error. HTTP status=502" in message
    assert 'body="upstream unavailable"' in message
    assert caplog.records[-1].http_status == 502
    assert caplog.records[-1].content_type == "text/plain"
    assert caplog.records[-1].response_body == "upstream unavailable"


def test_rate_limited_http_status_uses_longer_retry_delay(monkeypatch):
    class RateLimitResponse:
        status_code = 429
        text = "rate limited"
        headers = {"content-type": "text/plain"}

        def raise_for_status(self):
            request = module.httpx.Request("POST", "https://example.test/v1/responses")
            raise module.httpx.HTTPStatusError("rate limited", request=request, response=self)

        def json(self):
            return {"error": {"message": "rate limited"}}

    class RateLimitClient(FakeAsyncClient):
        async def post(self, url, headers, json):
            return RateLimitResponse()

    delays = []

    async def fake_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(module.httpx, "AsyncClient", RateLimitClient)
    monkeypatch.setattr(module.asyncio, "sleep", fake_sleep)
    client = _client(monkeypatch)

    with pytest.raises(RuntimeError):
        asyncio.run(client._post_with_retry({"model": "claude-test"}))

    assert delays == [30.0, 60.0]


_RESPONSES_PAYLOAD_WITH_SOURCES = {
    "model": "doubao-seed-2-0-mini-260215",
    "output": [
        {
            "type": "web_search_call",
            "action": {
                "results": [
                    {"url": "https://www.example.com/a", "title": "示例 A", "snippet": "片段 A"},
                    {"url": "https://news.example.cn/b", "title": "示例 B"},
                ]
            },
        },
        {
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "output_text",
                    "text": '{"answer":"ok","mentioned_brands":[],"citations":[],"parse_confidence":"high"}',
                    "annotations": [
                        {
                            "type": "url_citation",
                            "url": "https://docs.example.org/c",
                            "title": "示例 C",
                        }
                    ],
                }
            ],
        },
    ],
    "usage": {"total_tokens": 5},
}


def test_responses_citations_extracts_annotations_and_web_search_results():
    citations = module._responses_citations(_RESPONSES_PAYLOAD_WITH_SOURCES)
    urls = {c["url"] for c in citations}
    assert urls == {
        "https://www.example.com/a",
        "https://news.example.cn/b",
        "https://docs.example.org/c",
    }


def test_doubao_extract_citations_reads_responses_output(monkeypatch):
    monkeypatch.setenv("DOUBAO_API_KEY", "ark-test")
    client = DoubaoClient()
    message = client._message(_RESPONSES_PAYLOAD_WITH_SOURCES)

    citations = client._extract_citations(_RESPONSES_PAYLOAD_WITH_SOURCES, message)

    urls = {c["url"] for c in citations}
    assert urls == {
        "https://www.example.com/a",
        "https://news.example.cn/b",
        "https://docs.example.org/c",
    }

