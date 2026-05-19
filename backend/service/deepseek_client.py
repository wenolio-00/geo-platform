from __future__ import annotations

from service.platform_clients.openai_compatible import OpenAICompatibleClient


class DeepSeekClient(OpenAICompatibleClient):
    def __init__(self) -> None:
        super().__init__("DeepSeek", "DEEPSEEK", "https://api.deepseek.com", "deepseek-v4-flash")
        self.thinking = __import__("os").getenv("DEEPSEEK_THINKING", "disabled")

    def _payload(self, query: dict, brand_config: dict, options: dict | None = None) -> dict:
        payload = super()._payload(query, brand_config, options=options)
        if self.thinking in {"enabled", "disabled"}:
            payload["thinking"] = {"type": self.thinking}
        return payload
