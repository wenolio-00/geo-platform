from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from service.platform_registry import create_task_client, llm_task_options, serialize_task_brief
from service.parser import parse_json_answer


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
    client = create_task_client(options["provider"])
    result = await client.invoke_task(
        {
            "task_type": task_type,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "options": options,
            "response_format": response_format,
            "tools": tools,
        }
    )
    result["provider"] = options["provider"]
    result["web_search_enabled"] = options.get("web_search_enabled", False)
    result["web_search_mode"] = options.get("web_search_mode")
    return result


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
