from __future__ import annotations

import os

from service.claude_client import ClaudeClient
from service.deepseek_client import DeepSeekClient
from service.platform_clients.doubao_client import DoubaoClient
from service.platform_clients.openai_compatible import OpenAICompatibleClient

PLATFORM_SPECS = {
    "DeepSeek": ("DEEPSEEK", "https://api.deepseek.com", "deepseek-v4-flash"),
    "Claude": ("CLAUDE", "https://api.anthropic.com", "claude-sonnet-4-20250514"),
    "Kimi": ("KIMI", "", ""),
    "豆包": ("DOUBAO", "https://ark.cn-beijing.volces.com/api/v3", "doubao-seed-2-0-mini-260215"),
    "Tongyi": ("TONGYI", "", ""),
    "Wenxin": ("WENXIN", "", ""),
    "Yuanbao": ("YUANBAO", "", ""),
}
ALIASES = {
    "anthropic": "Claude",
    "claude": "Claude",
    "deepseek": "DeepSeek",
    "kimi": "Kimi",
    "doubao": "豆包",
    "豆包": "豆包",
    "tongyi": "Tongyi",
    "通义": "Tongyi",
    "通义千问": "Tongyi",
    "wenxin": "Wenxin",
    "文心": "Wenxin",
    "文心一言": "Wenxin",
    "yuanbao": "Yuanbao",
    "混元": "Yuanbao",
    "混元元宝": "Yuanbao",
}


def requested_platforms(run: dict) -> list[str]:
    values = run.get("platforms") or _env_platforms()
    platforms = [_canonical_platform(value) for value in values]
    platforms = [platform for platform in platforms if platform]
    if run.get("inspection_mode") == "deepseek_live_v1":
        return ["DeepSeek"]
    return list(dict.fromkeys(platforms or ["DeepSeek"]))


def create_platform_clients(platforms: list[str]) -> list[OpenAICompatibleClient]:
    clients = []
    for platform in platforms:
        if platform == "DeepSeek":
            clients.append(DeepSeekClient())
            continue
        if platform == "Claude":
            clients.append(ClaudeClient())
            continue
        if platform == "豆包":
            clients.append(DoubaoClient())
            continue
        spec = PLATFORM_SPECS.get(platform)
        if not spec:
            raise RuntimeError(f"Unsupported inspection platform: {platform}")
        env_prefix, default_base_url, default_model = spec
        clients.append(OpenAICompatibleClient(platform, env_prefix, default_base_url, default_model))
    return clients


def _env_platforms() -> list[str]:
    text = os.getenv("INSPECTION_PLATFORMS", "DeepSeek")
    return [item.strip() for item in text.split(",") if item.strip()]


def _canonical_platform(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return ALIASES.get(text.lower(), text if text in PLATFORM_SPECS else None)
