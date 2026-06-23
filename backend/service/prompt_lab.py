from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse
from uuid import uuid4

from service.platform_registry import PLATFORM_SPECS, _canonical_platform, create_platform_clients


DISPLAY_NAMES = {
    "GPT": "GPT",
    "claude": "Claude",
    "豆包": "豆包",
    "DeepSeek": "DeepSeek",
    "Tongyi": "通义千问(Qwen)",
}


async def run_prompt_lab(
    payload: dict[str, Any],
    *,
    is_disconnected: Callable[[], Awaitable[bool]] | None = None,
) -> dict[str, Any]:
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt is required")

    platforms = _normalize_platforms(payload.get("platforms"))
    rounds = _payload_int(payload, "rounds", _env_int("PROMPT_LAB_ROUNDS", 5))
    if not 1 <= rounds <= 5:
        raise ValueError("rounds must be between 1 and 5")

    options = {
        "web_search_enabled": _payload_bool(payload, "web_search_enabled", True),
        "temperature": _payload_float(payload, "temperature", 0.2),
        "max_tokens": _payload_int(payload, "max_tokens", 1600),
    }
    deadline_seconds = _env_int("PROMPT_LAB_DEADLINE_SECONDS", 120)
    max_concurrency = max(1, _env_int("PROMPT_LAB_MAX_CONCURRENCY", 5))
    semaphore = asyncio.Semaphore(max_concurrency)
    enabled_platforms = _enabled_prompt_lab_platforms()

    clients = create_platform_clients(platforms)
    groups = [_empty_platform_result(client, rounds) for client in clients]
    group_by_platform = {group["platform"]: group for group in groups}
    scheduled: list[tuple[asyncio.Task, str, int]] = []

    for client in clients:
        platform = getattr(client, "platform", "")
        if platform not in enabled_platforms:
            error = f"{platform} is not connected for Prompt Lab. Enable it with PROMPT_LAB_ENABLED_PLATFORMS when its API key is ready."
            group_by_platform[platform]["invocations"] = [_failed_invocation(round_number, error) for round_number in range(1, rounds + 1)]
            continue

        missing = _missing_config(client)
        if missing:
            error = f"{platform} configuration is incomplete. Missing: {', '.join(missing)}"
            group_by_platform[platform]["invocations"] = [_failed_invocation(round_number, error) for round_number in range(1, rounds + 1)]
            continue

        for round_number in range(1, rounds + 1):
            task = asyncio.create_task(_invoke_once(client, prompt, options, semaphore, is_disconnected))
            scheduled.append((task, platform, round_number))

    if scheduled:
        await _collect_invocations(scheduled, group_by_platform, deadline_seconds)

    for group in groups:
        group["invocations"].sort(key=lambda item: item["round"])
        group["success_count"] = sum(1 for item in group["invocations"] if item["status"] == "success")
        group["failed_count"] = sum(1 for item in group["invocations"] if item["status"] == "failed")
        group["status"] = "failed" if group["success_count"] == 0 else "completed"

    return {
        "run_id": f"plr_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}",
        "prompt": prompt,
        "rounds": rounds,
        "web_search_enabled": options["web_search_enabled"],
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "platform_results": groups,
    }


def _normalize_platforms(raw_value: object) -> list[str]:
    if not isinstance(raw_value, list) or not raw_value:
        raise ValueError("platforms is required and must contain at least one platform")

    platforms: list[str] = []
    for raw_platform in raw_value:
        platform = _canonical_platform(raw_platform)
        if not platform:
            raise ValueError(f"unsupported platform: {raw_platform}")
        platforms.append(platform)

    platforms = list(dict.fromkeys(platforms))
    if not platforms:
        raise ValueError("platforms is required and must contain a known platform")
    return platforms


async def _invoke_once(
    client: Any,
    prompt: str,
    options: dict[str, Any],
    semaphore: asyncio.Semaphore,
    is_disconnected: Callable[[], Awaitable[bool]] | None,
) -> dict[str, Any]:
    async with semaphore:
        if is_disconnected and await is_disconnected():
            raise asyncio.CancelledError()
        return await client.invoke_task({
            "user_prompt": prompt,
            "options": {
                "web_search_enabled": options["web_search_enabled"],
                "temperature": options["temperature"],
                "max_tokens": options["max_tokens"],
            },
        })


async def _collect_invocations(
    scheduled: list[tuple[asyncio.Task, str, int]],
    group_by_platform: dict[str, dict[str, Any]],
    deadline_seconds: int,
) -> None:
    task_meta = {task: (platform, round_number) for task, platform, round_number in scheduled}
    pending_tasks = set(task_meta)
    done_tasks: set[asyncio.Task] = set()

    if deadline_seconds > 0:
        done_tasks, pending_tasks = await asyncio.wait(pending_tasks, timeout=deadline_seconds)
    else:
        done_tasks, pending_tasks = await asyncio.wait(pending_tasks)

    for task in done_tasks:
        platform, round_number = task_meta[task]
        group_by_platform[platform]["invocations"].append(_task_invocation(task, round_number))

    if pending_tasks:
        for task in pending_tasks:
            task.cancel()
        await asyncio.gather(*pending_tasks, return_exceptions=True)
        for task in pending_tasks:
            platform, round_number = task_meta[task]
            group_by_platform[platform]["invocations"].append(
                _failed_invocation(round_number, "prompt lab deadline exceeded")
            )


def _task_invocation(task: asyncio.Task, round_number: int) -> dict[str, Any]:
    if task.cancelled():
        return _failed_invocation(round_number, "prompt lab request cancelled")
    try:
        result = task.result()
    except asyncio.CancelledError:
        return _failed_invocation(round_number, "prompt lab request cancelled")
    except Exception as exc:
        return _failed_invocation(round_number, str(exc) or type(exc).__name__)
    return _success_invocation(round_number, result)


def _empty_platform_result(client: Any, rounds: int) -> dict[str, Any]:
    platform = getattr(client, "platform", "")
    return {
        "platform": platform,
        "display_name": DISPLAY_NAMES.get(platform, platform),
        "configured_model": getattr(client, "model", "") or _spec_default_model(platform),
        "status": "pending",
        "success_count": 0,
        "failed_count": 0,
        "invocations": [],
    }


def _success_invocation(round_number: int, result: dict[str, Any]) -> dict[str, Any]:
    answer = result.get("raw_text") or ""
    citations = [
        _map_citation(citation)
        for citation in result.get("citations") or []
        if isinstance(citation, dict)
    ]
    citations = _dedup_mapped_citations(citations + _answer_url_citations(answer))
    return {
        "round": round_number,
        "status": "success",
        "model": result.get("model") or "",
        "answer": answer,
        "citations": citations,
        "usage": result.get("usage") or {},
        "error": None,
    }


def _failed_invocation(round_number: int, error: str) -> dict[str, Any]:
    return {
        "round": round_number,
        "status": "failed",
        "model": "",
        "answer": "",
        "citations": [],
        "usage": {},
        "error": error,
    }


def _map_citation(citation: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": citation.get("title"),
        "url": citation.get("url"),
        "snippet": citation.get("quoted_text") or citation.get("snippet"),
        "domain": citation.get("domain"),
        "source": "api_annotation",
    }


def _answer_url_citations(answer: str) -> list[dict[str, Any]]:
    if not answer:
        return []
    citations: list[dict[str, Any]] = []
    for match in re.finditer(r"https?://[^\s<>\]\)\"'，。、《》；;]+", answer):
        url = match.group(0).rstrip(".,!?，。！？、:：")
        if not url:
            continue
        citations.append({
            "title": url,
            "url": url,
            "snippet": _answer_excerpt(answer, match.start(), match.end()),
            "domain": _domain_from_url(url),
            "source": "answer_url",
        })
    return citations


def _answer_excerpt(answer: str, start: int, end: int) -> str:
    left = max(0, start - 80)
    right = min(len(answer), end + 80)
    return answer[left:right].strip()


def _domain_from_url(url: str) -> str | None:
    netloc = urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc or None


def _dedup_mapped_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for citation in citations:
        url = citation.get("url") if isinstance(citation.get("url"), str) else ""
        domain = citation.get("domain") if isinstance(citation.get("domain"), str) else ""
        key = url or domain
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        result.append(citation)
    return result


def _missing_config(client: Any) -> list[str]:
    env_prefix = str(getattr(client, "env_prefix", getattr(client, "platform", "PLATFORM")) or "PLATFORM").upper()
    missing: list[str] = []
    for attr, env_name in (
        ("api_key", f"{env_prefix}_API_KEY"),
        ("base_url", f"{env_prefix}_BASE_URL"),
        ("model", f"{env_prefix}_MODEL"),
    ):
        if not str(getattr(client, attr, "") or "").strip():
            missing.append(env_name)
    return missing


def _spec_default_model(platform: str) -> str:
    spec = PLATFORM_SPECS.get(platform)
    return spec.default_model if spec else ""


def _payload_int(payload: dict[str, Any], key: str, default: int) -> int:
    value = payload.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be an integer") from exc


def _payload_float(payload: dict[str, Any], key: str, default: float) -> float:
    value = payload.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a number") from exc


def _payload_bool(payload: dict[str, Any], key: str, default: bool) -> bool:
    value = payload.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _enabled_prompt_lab_platforms() -> set[str]:
    raw = os.getenv("PROMPT_LAB_ENABLED_PLATFORMS", "GPT,claude")
    platforms = {_canonical_platform(item) for item in raw.split(",")}
    return {platform for platform in platforms if platform}
