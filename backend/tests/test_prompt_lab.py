from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app
from service import prompt_lab


@pytest.fixture(autouse=True)
def enabled_prompt_lab_platforms(monkeypatch) -> None:
    monkeypatch.setenv("PROMPT_LAB_ENABLED_PLATFORMS", "GPT,claude")


class MockPromptLabClient:
    def __init__(
        self,
        platform: str,
        env_prefix: str,
        *,
        api_key: str = "test-key",
        base_url: str = "https://example.test/v1",
        model: str = "mock-model",
        fail_on_call: int | None = None,
        raw_text: str | None = None,
        citations: list[dict] | None = None,
    ) -> None:
        self.platform = platform
        self.env_prefix = env_prefix
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.fail_on_call = fail_on_call
        self.raw_text = raw_text
        self.citations = citations
        self.calls = 0

    async def invoke_task(self, task: dict) -> dict:
        self.calls += 1
        if self.fail_on_call == self.calls:
            raise RuntimeError(f"{self.platform} round failed")
        return {
            "platform": self.platform,
            "provider": self.platform,
            "model": self.model,
            "raw_text": self.raw_text or f"{self.platform} answer {self.calls}: {task['user_prompt']}",
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            "citations": self.citations if self.citations is not None else [
                {
                    "title": "Example",
                    "url": "https://example.com/source",
                    "domain": "example.com",
                    "quoted_text": "quoted citation text",
                    "answer_excerpt": "answer excerpt",
                }
            ],
            "raw_response": {},
        }


def test_prompt_lab_rejects_empty_prompt() -> None:
    response = TestClient(app).post("/api/v1/geo/prompt-lab/runs", json={"prompt": "", "platforms": ["GPT"]})

    assert response.status_code == 422
    assert response.json()["error_code"] == "prompt_lab_invalid_input"
    assert response.json()["detail"] == "prompt is required"


def test_prompt_lab_rejects_empty_or_unknown_platforms() -> None:
    client = TestClient(app)

    empty_response = client.post("/api/v1/geo/prompt-lab/runs", json={"prompt": "hello", "platforms": []})
    unknown_response = client.post("/api/v1/geo/prompt-lab/runs", json={"prompt": "hello", "platforms": ["unknown"]})

    assert empty_response.status_code == 422
    assert "platforms is required" in empty_response.json()["detail"]
    assert unknown_response.status_code == 422
    assert "unsupported platform" in unknown_response.json()["detail"]


def test_prompt_lab_rejects_rounds_over_five() -> None:
    response = TestClient(app).post(
        "/api/v1/geo/prompt-lab/runs",
        json={"prompt": "hello", "platforms": ["GPT"], "rounds": 6},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "rounds must be between 1 and 5"


def test_prompt_lab_normalizes_aliases_and_dedupes(monkeypatch) -> None:
    clients = {
        "Tongyi": MockPromptLabClient("Tongyi", "TONGYI", model="qwen-plus"),
        "豆包": MockPromptLabClient("豆包", "DOUBAO", model="doubao-test"),
    }
    requested_platforms: list[list[str]] = []

    def fake_create_platform_clients(platforms: list[str]) -> list[MockPromptLabClient]:
        requested_platforms.append(platforms)
        return [clients[platform] for platform in platforms]

    monkeypatch.setattr(prompt_lab, "create_platform_clients", fake_create_platform_clients)

    response = TestClient(app).post(
        "/api/v1/geo/prompt-lab/runs",
        json={"prompt": "hello", "platforms": ["qwen", "通义千问", "doubao", "豆包"], "rounds": 1},
    )

    assert response.status_code == 200
    assert requested_platforms == [["Tongyi", "豆包"]]
    assert [item["platform"] for item in response.json()["platform_results"]] == ["Tongyi", "豆包"]


def test_prompt_lab_missing_key_returns_platform_failures(monkeypatch) -> None:
    missing_client = MockPromptLabClient("GPT", "GPT", api_key="")
    monkeypatch.setattr(prompt_lab, "create_platform_clients", lambda platforms: [missing_client])

    response = TestClient(app).post(
        "/api/v1/geo/prompt-lab/runs",
        json={"prompt": "hello", "platforms": ["GPT"], "rounds": 5},
    )

    assert response.status_code == 200
    group = response.json()["platform_results"][0]
    assert group["status"] == "failed"
    assert group["success_count"] == 0
    assert group["failed_count"] == 5
    assert missing_client.calls == 0
    assert "GPT_API_KEY" in group["invocations"][0]["error"]


def test_prompt_lab_disabled_platform_keeps_result_shape_without_invoking(monkeypatch) -> None:
    disabled_client = MockPromptLabClient("DeepSeek", "DEEPSEEK")
    monkeypatch.setattr(prompt_lab, "create_platform_clients", lambda platforms: [disabled_client])

    response = TestClient(app).post(
        "/api/v1/geo/prompt-lab/runs",
        json={"prompt": "hello", "platforms": ["DeepSeek"], "rounds": 2},
    )

    assert response.status_code == 200
    group = response.json()["platform_results"][0]
    assert group["platform"] == "DeepSeek"
    assert group["status"] == "failed"
    assert len(group["invocations"]) == 2
    assert disabled_client.calls == 0
    assert "not connected for Prompt Lab" in group["invocations"][0]["error"]


def test_prompt_lab_invokes_each_round_and_maps_fields(monkeypatch) -> None:
    client = MockPromptLabClient("GPT", "GPT", model="gpt-test")
    monkeypatch.setattr(prompt_lab, "create_platform_clients", lambda platforms: [client])

    response = TestClient(app).post(
        "/api/v1/geo/prompt-lab/runs",
        json={"prompt": "hello", "platforms": ["GPT"], "rounds": 5},
    )

    assert response.status_code == 200
    group = response.json()["platform_results"][0]
    assert client.calls == 5
    assert group["success_count"] == 5
    first = group["invocations"][0]
    assert first["answer"].startswith("GPT answer")
    assert first["model"] == "gpt-test"
    assert first["usage"]["total_tokens"] == 30
    assert first["citations"][0]["snippet"] == "quoted citation text"
    assert first["citations"][0]["source"] == "api_annotation"


def test_prompt_lab_extracts_answer_urls_when_provider_returns_no_citations(monkeypatch) -> None:
    client = MockPromptLabClient(
        "GPT",
        "GPT",
        raw_text="可参考官网 https://www.duiba.com/ 和资料页 https://example.com/docs。",
        citations=[],
    )
    monkeypatch.setattr(prompt_lab, "create_platform_clients", lambda platforms: [client])

    response = TestClient(app).post(
        "/api/v1/geo/prompt-lab/runs",
        json={"prompt": "hello", "platforms": ["GPT"], "rounds": 1},
    )

    assert response.status_code == 200
    citations = response.json()["platform_results"][0]["invocations"][0]["citations"]
    assert len(citations) == 2
    assert citations[0]["url"] == "https://www.duiba.com/"
    assert citations[0]["domain"] == "duiba.com"
    assert citations[0]["source"] == "answer_url"
    assert "可参考官网" in citations[0]["snippet"]
    assert citations[1]["url"] == "https://example.com/docs"


def test_prompt_lab_single_round_failure_does_not_fail_group(monkeypatch) -> None:
    client = MockPromptLabClient("GPT", "GPT", fail_on_call=2)
    monkeypatch.setattr(prompt_lab, "create_platform_clients", lambda platforms: [client])

    response = TestClient(app).post(
        "/api/v1/geo/prompt-lab/runs",
        json={"prompt": "hello", "platforms": ["GPT"], "rounds": 3},
    )

    assert response.status_code == 200
    group = response.json()["platform_results"][0]
    assert group["status"] == "completed"
    assert group["success_count"] == 2
    assert group["failed_count"] == 1
    failed = [item for item in group["invocations"] if item["status"] == "failed"]
    assert len(failed) == 1
    assert "GPT round failed" in failed[0]["error"]
