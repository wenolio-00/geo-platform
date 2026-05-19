from __future__ import annotations

from typing import Any, Protocol


class LlmTaskClient(Protocol):
    platform: str
    model: str

    async def inspect(self, query: dict, brand_config: dict, options: dict[str, Any] | None = None) -> dict[str, Any]: ...

    async def invoke_task(self, task: dict[str, Any]) -> dict[str, Any]: ...
