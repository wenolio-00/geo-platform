from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from service.platform_clients.doubao_client import DoubaoClient
from service.platform_clients.openai_compatible import OpenAICompatibleClient


@dataclass(frozen=True)
class ProviderSpec:
    platform: str
    env_prefix: str
    default_base_url: str = ""
    default_model: str = ""
    client_kind: str = "openai_compatible"
    capabilities: dict[str, Any] = field(default_factory=dict)


LLM_TASK_TYPES = {"inspect", "content_generation", "prefill", "rule_activation", "context_extraction"}
DEFAULT_TASK_PROVIDER = "claude"

PLATFORM_SPECS: dict[str, ProviderSpec] = {
    "claude": ProviderSpec(
        platform="claude",
        env_prefix="CLAUDE",
        default_base_url="",
        default_model="claude-haiku-4-5-20251001",
        client_kind="openai_compatible",
        capabilities={
            "supports_web_search": True,
            "task_modes": ["inspect", "content_generation", "prefill", "rule_activation", "context_extraction"],
        },
    ),
    "GPT": ProviderSpec(
        platform="GPT",
        env_prefix="GPT",
        default_base_url="https://api.openai.com/v1",
        default_model="gpt-5.5",
        client_kind="openai_compatible",
        capabilities={
            "supports_web_search": True,
            "task_modes": ["inspect", "content_generation", "prefill", "rule_activation", "context_extraction"],
        },
    ),
    "DeepSeek": ProviderSpec(
        platform="DeepSeek",
        env_prefix="DEEPSEEK",
        default_base_url="https://api.deepseek.com",
        default_model="deepseek-v4-flash",
        client_kind="deepseek",
        capabilities={"supports_web_search": False, "task_modes": ["inspect"]},
    ),
    "Kimi": ProviderSpec(
        platform="Kimi",
        env_prefix="KIMI",
        default_base_url="",
        default_model="",
        capabilities={"supports_web_search": False, "task_modes": ["inspect"]},
    ),
    "豆包": ProviderSpec(
        platform="豆包",
        env_prefix="DOUBAO",
        default_base_url="https://ark.cn-beijing.volces.com/api/v3",
        default_model="doubao-seed-2-0-mini-260215",
        client_kind="doubao",
        capabilities={"supports_web_search": True, "task_modes": ["inspect", "content_generation", "prefill", "rule_activation"]},
    ),
    "Tongyi": ProviderSpec(
        platform="Tongyi",
        env_prefix="TONGYI",
        default_base_url="",
        default_model="",
        capabilities={"supports_web_search": False, "task_modes": ["inspect"]},
    ),
    "Wenxin": ProviderSpec(
        platform="Wenxin",
        env_prefix="WENXIN",
        default_base_url="",
        default_model="",
        capabilities={"supports_web_search": False, "task_modes": ["inspect"]},
    ),
    "Yuanbao": ProviderSpec(
        platform="Yuanbao",
        env_prefix="YUANBAO",
        default_base_url="",
        default_model="",
        capabilities={"supports_web_search": False, "task_modes": ["inspect"]},
    ),
}
ALIASES = {
    "gpt": "GPT",
    "openai": "GPT",
    "chatgpt": "GPT",
    "anthropic": "claude",
    "claude": "claude",
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
    return list(dict.fromkeys(platforms or ["claude"]))


def create_platform_clients(platforms: list[str]) -> list[OpenAICompatibleClient]:
    return [_client_for_platform(platform) for platform in platforms]


def create_task_client(provider: str | None = None) -> OpenAICompatibleClient:
    platform = _canonical_task_provider(provider)
    if not platform:
        raise RuntimeError(f"Unsupported LLM provider: {provider or DEFAULT_TASK_PROVIDER}")
    return _client_for_platform(platform)


def provider_capabilities(provider: str | None = None) -> dict[str, Any]:
    platform = _canonical_task_provider(provider)
    if not platform:
        return {}
    spec = PLATFORM_SPECS.get(platform)
    return dict(spec.capabilities) if spec else {}


def validate_platform_clients(clients: list[OpenAICompatibleClient]) -> None:
    missing: list[str] = []
    for client in clients:
        env_prefix = getattr(client, "env_prefix", getattr(client, "platform", "PLATFORM")).upper()
        platform = getattr(client, "platform", env_prefix)
        for attr, env_name in (
            ("api_key", f"{env_prefix}_API_KEY"),
            ("base_url", f"{env_prefix}_BASE_URL"),
            ("model", f"{env_prefix}_MODEL"),
        ):
            if not str(getattr(client, attr, "") or "").strip():
                missing.append(f"{platform}: {env_name}")
    if missing:
        raise RuntimeError(
            "Inspection platform configuration is incomplete. Missing: "
            + ", ".join(missing)
        )


def llm_task_options(task_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    provider = _task_provider_for(task_type, payload)
    capabilities = provider_capabilities(provider)
    request_web_search = bool(payload.get("web_search_enabled", True))
    use_web_search = request_web_search and bool(capabilities.get("supports_web_search"))
    options = {
        "provider": provider,
        "task_type": task_type,
        "web_search_enabled": use_web_search,
        "web_search_mode": "responses_web_search" if use_web_search else None,
    }
    for key in ("web_search_mode", "temperature", "max_tokens"):
        value = payload.get(key)
        if value is not None:
            options[key] = value
    extra = payload.get("llm_options")
    if isinstance(extra, dict):
        for key, value in extra.items():
            if key in {"provider", "llm_provider", "platform", "platforms"}:
                continue
            options[key] = value
    return options


def serialize_task_brief(brief: dict[str, Any]) -> str:
    return json.dumps(brief, ensure_ascii=False, indent=2)


def _client_for_platform(platform: str) -> OpenAICompatibleClient:
    platform = _canonical_platform(platform) or platform
    spec = PLATFORM_SPECS.get(platform)
    if not spec:
        raise RuntimeError(f"Unsupported inspection platform: {platform}")
    if spec.client_kind == "deepseek":
        from service.deepseek_client import DeepSeekClient

        return DeepSeekClient()
    if spec.client_kind == "doubao":
        return DoubaoClient()
    return OpenAICompatibleClient(platform, spec.env_prefix, spec.default_base_url, spec.default_model)


def _env_platforms() -> list[str]:
    text = os.getenv("INSPECTION_PLATFORMS", "claude")
    return [item.strip() for item in text.split(",") if item.strip()]


def _canonical_platform(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return ALIASES.get(text.lower(), text if text in PLATFORM_SPECS else None)


def _task_provider_for(task_type: str, payload: dict[str, Any]) -> str:
    candidates: list[object] = [
        payload.get("provider"),
        payload.get("llm_provider"),
        os.getenv("DEFAULT_LLM_PROVIDER"),
        *_env_platforms(),
        DEFAULT_TASK_PROVIDER,
    ]
    for candidate in candidates:
        provider = _canonical_platform(candidate)
        if not provider:
            continue
        spec = PLATFORM_SPECS.get(provider)
        task_modes = (spec.capabilities.get("task_modes") if spec else None) or []
        if task_type not in LLM_TASK_TYPES or task_type in task_modes:
            return provider
    return DEFAULT_TASK_PROVIDER


def _canonical_task_provider(value: object | None = None) -> str:
    raw = value if value is not None else os.getenv("DEFAULT_LLM_PROVIDER") or next(iter(_env_platforms()), None) or DEFAULT_TASK_PROVIDER
    provider = _canonical_platform(raw)
    return provider if provider in PLATFORM_SPECS else DEFAULT_TASK_PROVIDER
