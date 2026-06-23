import asyncio

from service import smart_prefill


def test_smart_prefill_continues_when_website_fetch_fails(monkeypatch):
    async def failing_fetch(url):
        raise RuntimeError("fetch blocked")

    async def fake_invoke_json_task(**kwargs):
        assert kwargs["task_type"] == "prefill"
        assert "官网 URL：https://www.example.com" in kwargs["user_prompt"]
        assert "页面正文抓取失败：fetch blocked" in kwargs["user_prompt"]
        return {
            "provider": "GPT",
            "web_search_enabled": True,
            "web_search_mode": "responses_web_search",
            "parsed": {
                "entity_name": "Example Domain",
                "entity_aliases": ["Example"],
                "industry_segments": ["文档示例"],
                "topics": [{"topic_name": "示例域名", "business_line": "示例", "priority": 1}],
                "competitors": [],
            },
        }

    monkeypatch.setattr(smart_prefill, "_fetch_website_text", failing_fetch)
    monkeypatch.setattr(smart_prefill, "invoke_json_task", fake_invoke_json_task)

    result = asyncio.run(
        smart_prefill.smart_prefill_brand_config({"website_url": "https://www.example.com"})
    )

    assert result["entity_name"] == "Example Domain"
    assert result["llm_provider"] == "GPT"
    assert result["topics"][0]["topic_name"] == "示例域名"
