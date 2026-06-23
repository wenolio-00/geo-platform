from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from service.platform_registry import (
    create_task_client,
    get_fallback_providers,
    llm_task_options,
    serialize_task_brief,
)
from service.parser import parse_json_answer


logger = logging.getLogger(__name__)
ROOT_DIR = Path(__file__).resolve().parents[2]
PROMPTS_DIR = ROOT_DIR / "src" / "prompts"
CONFIG_DIR = ROOT_DIR / "src" / "config"
SCHEMAS_DIR = ROOT_DIR / "src" / "schemas"


async def invoke_llm_task(
    *,
    task_type: str,
    payload: dict[str, Any],
    system_prompt: str,
    user_prompt: str,
    provider: str | None = None,
    response_format: dict[str, Any] | None = None,
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    options = llm_task_options(task_type, {**payload, "provider": provider} if provider else payload)
    primary_provider = options["provider"]
    fallback_providers = get_fallback_providers(task_type, primary_provider)
    providers = [primary_provider, *fallback_providers]
    last_error: RuntimeError | None = None

    for index, task_provider in enumerate(providers):
        attempt_options = llm_task_options(task_type, {**payload, "provider": task_provider})
        try:
            result = await _invoke_task_client(
                task_type=task_type,
                options=attempt_options,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_format=response_format,
                tools=tools,
            )
            result["provider"] = task_provider
            result["web_search_enabled"] = attempt_options.get("web_search_enabled", False)
            result["web_search_mode"] = attempt_options.get("web_search_mode")
            result["used_fallback"] = index > 0
            if index > 0:
                result["primary_provider"] = primary_provider
                result["fallback_reason"] = str(last_error or "")[:200]
            return result
        except RuntimeError as exc:
            last_error = exc
            if index == 0:
                logger.warning(
                    "llm_task_primary_provider_failed",
                    extra={"task_type": task_type, "provider": task_provider, "error": str(exc)},
                )
            else:
                logger.warning(
                    "llm_task_fallback_provider_failed",
                    extra={
                        "task_type": task_type,
                        "provider": task_provider,
                        "primary_provider": primary_provider,
                        "error": str(exc),
                    },
                )
            if index + 1 < len(providers):
                logger.info(
                    "llm_task_attempting_provider_fallback",
                    extra={
                        "task_type": task_type,
                        "provider": providers[index + 1],
                        "primary_provider": primary_provider,
                    },
                )
            continue

    if len(providers) == 1 and last_error:
        raise last_error
    raise RuntimeError(f"All providers failed for task {task_type}. Last error: {last_error}") from last_error


async def _invoke_task_client(
    *,
    task_type: str,
    options: dict[str, Any],
    system_prompt: str,
    user_prompt: str,
    response_format: dict[str, Any] | None = None,
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    client = create_task_client(options["provider"])
    return await client.invoke_task(
        {
            "task_type": task_type,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "options": options,
            "response_format": response_format,
            "tools": tools,
        }
    )


async def invoke_json_task(
    *,
    task_type: str,
    payload: dict[str, Any],
    system_prompt: str,
    user_prompt: str,
    provider: str | None = None,
) -> dict[str, Any]:
    result = await invoke_llm_task(
        task_type=task_type,
        payload=payload,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        provider=provider,
        response_format={"type": "json_object"},
    )
    parsed = parse_json_answer(result.get("raw_text", ""), payload.get("brand_config") or {})
    result["parsed"] = parsed
    return result


def load_project_asset(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_rule_activation_assets() -> dict[str, Any]:
    config = json.loads(load_project_asset(CONFIG_DIR / "rule_activation_evaluator.config.json"))
    schema = json.loads(load_project_asset(SCHEMAS_DIR / "rule_activation_evaluation.schema.json"))
    prompt = load_project_asset(PROMPTS_DIR / "rule_activation_evaluator_prompt_zh.md")
    return {"config": config, "schema": schema, "prompt": prompt}


def brief_to_json_text(brief: dict[str, Any]) -> str:
    return serialize_task_brief(brief)
