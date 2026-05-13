from __future__ import annotations

from typing import Protocol, Any


class PlatformClient(Protocol):
    platform: str
    model: str

    async def inspect(self, query: dict, brand_config: dict) -> dict[str, Any]: ...
