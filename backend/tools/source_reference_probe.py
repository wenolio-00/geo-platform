from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from service.parser import parse_json_answer  # noqa: E402
from service.platform_clients.openai_compatible import OpenAICompatibleClient  # noqa: E402


URL_RE = re.compile(r"https?://[^\s\"'<>）)]+", re.I)
CITATION_KEY_RE = re.compile(r"(citation|source|reference|url|search|grounding|web)", re.I)


def _load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _urls_in(value: Any) -> list[str]:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return URL_RE.findall(text)


def _walk_citation_like(value: Any, path: str = "$") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if CITATION_KEY_RE.search(str(key)):
                rows.append(
                    {
                        "path": child_path,
                        "type": type(child).__name__,
                        "url_count": len(_urls_in(child)),
                        "preview": _preview(child),
                    }
                )
            rows.extend(_walk_citation_like(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value[:20]):
            rows.extend(_walk_citation_like(child, f"{path}[{index}]"))
    return rows


def _preview(value: Any, limit: int = 180) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value)
    text = " ".join(text.split())
    return text[:limit] + ("..." if len(text) > limit else "")


def _read_storage() -> tuple[dict[str, Any], dict[str, Any]]:
    runs = _load_json(BACKEND_DIR / "storage" / "diagnostic_runs.json")
    results = _load_json(BACKEND_DIR / "storage" / "inspection_results.json")
    return runs if isinstance(runs, dict) else {}, results if isinstance(results, dict) else {}


def inspect_storage() -> dict[str, Any]:
    runs, result_store = _read_storage()
    samples: list[dict[str, Any]] = []
    raw_url_but_no_parsed: list[dict[str, Any]] = []
    parsed_but_no_url: list[dict[str, Any]] = []

    for batch in result_store.values():
        if not isinstance(batch, dict):
            continue
        for result in batch.get("results") or []:
            if not isinstance(result, dict) or result.get("status") != "completed":
                continue
            raw_urls = _urls_in(result.get("raw_answer") or "")
            citations = result.get("parsed", {}).get("citations") or []
            row = {
                "run_id": batch.get("run_id"),
                "inspection_id": result.get("inspection_id"),
                "platform": result.get("platform"),
                "model": result.get("model"),
                "query_id": result.get("query_id"),
                "raw_url_count": len(raw_urls),
                "parsed_citation_count": len(citations),
                "raw_urls": raw_urls[:3],
                "citations": citations[:3],
            }
            samples.append(row)
            if raw_urls and not citations:
                raw_url_but_no_parsed.append(row)
            if citations and not raw_urls:
                parsed_but_no_url.append(row)

    completed_runs = [run for run in runs.values() if isinstance(run, dict) and run.get("status") == "completed"]
    latest_runs = sorted(completed_runs, key=lambda run: str(run.get("updated_at") or ""), reverse=True)[:5]
    report_rows = [
        {
            "run_id": run.get("run_id"),
            "updated_at": run.get("updated_at"),
            "sources": len(run.get("report_data", {}).get("sources") or []),
            "source_references": len(run.get("report_data", {}).get("source_references") or []),
            "own_citations": run.get("report_data", {}).get("global", {}).get("own_citations"),
            "empty_sections": run.get("report_data", {}).get("audit", {}).get("empty_sections") or [],
        }
        for run in latest_runs
    ]

    return {
        "storage_summary": {
            "completed_samples": len(samples),
            "samples_with_raw_urls": sum(1 for row in samples if row["raw_url_count"] > 0),
            "samples_with_parsed_citations": sum(1 for row in samples if row["parsed_citation_count"] > 0),
            "raw_url_but_no_parsed_count": len(raw_url_but_no_parsed),
            "parsed_citation_but_no_raw_url_count": len(parsed_but_no_url),
            "completed_runs": len(completed_runs),
            "total_report_sources": sum(len(run.get("report_data", {}).get("sources") or []) for run in completed_runs),
            "total_report_source_references": sum(
                len(run.get("report_data", {}).get("source_references") or []) for run in completed_runs
            ),
        },
        "latest_reports": report_rows,
        "examples": {
            "raw_url_but_no_parsed": raw_url_but_no_parsed[:3],
            "parsed_citations": [row for row in samples if row["parsed_citation_count"] > 0][:3],
        },
        "storage_diagnosis": _diagnose_storage(samples, completed_runs),
    }


def _diagnose_storage(samples: list[dict[str, Any]], completed_runs: list[dict[str, Any]]) -> str:
    raw_url_count = sum(1 for row in samples if row["raw_url_count"] > 0)
    parsed_count = sum(1 for row in samples if row["parsed_citation_count"] > 0)
    report_source_rows = sum(len(run.get("report_data", {}).get("sources") or []) for run in completed_runs)
    report_reference_rows = sum(len(run.get("report_data", {}).get("source_references") or []) for run in completed_runs)

    if not samples:
        return "no_completed_samples: 当前没有可检查的已完成巡检样本。"
    if raw_url_count == 0 and parsed_count == 0:
        return "upstream_no_url: 现有 raw_answer 没有 URL，parsed.citations 也为空；当前数据卡在模型/巡检返回阶段。"
    if raw_url_count > 0 and parsed_count == 0:
        return "parse_gap: raw_answer 出现 URL，但 parsed.citations 为空；优先检查 prompt JSON 输出和 parser。"
    if parsed_count > 0 and report_source_rows == 0 and report_reference_rows == 0:
        return "aggregation_gap: parsed.citations 有数据，但 report_data 没有 sources/source_references；优先检查聚合层。"
    return "passed_or_mixed: 现有样本中至少有引用进入后续链路；查看 examples 判断是否为个别平台差异。"


async def inspect_live(args: argparse.Namespace) -> dict[str, Any]:
    load_dotenv(BACKEND_DIR / ".env")
    client = OpenAICompatibleClient(
        platform=args.platform,
        env_prefix=args.env_prefix,
        default_base_url=args.base_url or "",
        default_model=args.model or "",
    )
    if args.base_url:
        client.base_url = args.base_url.rstrip("/")
    if args.model:
        client.model = args.model

    missing = [
        name
        for name, value in [
            (f"{args.env_prefix}_API_KEY", client.api_key),
            (f"{args.env_prefix}_BASE_URL", client.base_url),
            (f"{args.env_prefix}_MODEL", client.model),
        ]
        if not value
    ]
    if missing:
        return {
            "live_probe_skipped": True,
            "reason": f"missing_config: {', '.join(missing)}",
        }

    brand_config = {
        "entity_name": args.brand,
        "entity_aliases": [args.brand],
        "competitors": [{"name": item.strip(), "aliases": []} for item in args.competitors.split(",") if item.strip()],
    }
    query = {
        "query_id": "probe_source_reference",
        "query_text": args.query,
        "topic": "source_reference_probe",
        "intent_type": "evidence_check",
        "query_pattern": "source_reference_probe",
        "query_layer": "probe",
    }
    payload = client._payload(query, brand_config)
    try:
        raw_response = await client._post_with_retry(payload)
    except Exception as error:
        return {
            "live_probe_skipped": True,
            "reason": "provider_request_failed",
            "error": str(error),
            "platform": args.platform,
            "model": client.model,
            "base_url_host": client.base_url.split("//")[-1].split("/")[0],
        }
    message = (raw_response.get("choices") or [{}])[0].get("message") or {}
    content = message.get("content") or ""
    parsed = parse_json_answer(content, brand_config)
    content_urls = _urls_in(content)
    response_urls = _urls_in(raw_response)
    citation_like_paths = _walk_citation_like(raw_response)
    metadata_paths = [row for row in citation_like_paths if not row["path"].endswith(".content")]

    return {
        "live_probe_skipped": False,
        "platform": args.platform,
        "model": raw_response.get("model") or client.model,
        "content_url_count": len(content_urls),
        "response_url_count": len(response_urls),
        "parsed_citation_count": len(parsed.get("citations") or []),
        "content_url_examples": content_urls[:5],
        "parsed_citation_examples": (parsed.get("citations") or [])[:5],
        "citation_like_response_paths": metadata_paths[:20],
        "content_preview": _preview(content, 500),
        "live_diagnosis": _diagnose_live(content_urls, parsed.get("citations") or [], metadata_paths),
    }


async def inspect_responses_web_search(args: argparse.Namespace) -> dict[str, Any]:
    load_dotenv(BACKEND_DIR / ".env")
    api_key = os.getenv(f"{args.env_prefix}_API_KEY", "").strip()
    base_url = (args.base_url or os.getenv(f"{args.env_prefix}_BASE_URL", "")).rstrip("/")
    model = args.model or os.getenv(f"{args.env_prefix}_MODEL", "").strip()
    missing = [
        name
        for name, value in [
            (f"{args.env_prefix}_API_KEY", api_key),
            (f"{args.env_prefix}_BASE_URL", base_url),
            (f"{args.env_prefix}_MODEL", model),
        ]
        if not value
    ]
    if missing:
        return {
            "responses_web_search_skipped": True,
            "reason": f"missing_config: {', '.join(missing)}",
        }

    payload = {
        "model": model,
        "stream": False,
        "tools": [{"type": "web_search"}],
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": args.query,
                    }
                ],
            }
        ],
    }
    url = f"{base_url}/responses"
    timeout = float(os.getenv(f"{args.env_prefix}_TIMEOUT_SECONDS", os.getenv("REQUEST_TIMEOUT_SECONDS", "45")))
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        try:
            raw_response = response.json()
        except ValueError:
            raw_response = {"text": response.text}
        if response.status_code >= 400:
            return {
                "responses_web_search_skipped": True,
                "reason": "provider_request_failed",
                "status_code": response.status_code,
                "error": _preview(raw_response, 800),
                "platform": args.platform,
                "model": model,
                "base_url_host": base_url.split("//")[-1].split("/")[0],
            }
    except Exception as error:
        return {
            "responses_web_search_skipped": True,
            "reason": "provider_request_failed",
            "error": str(error),
            "platform": args.platform,
            "model": model,
            "base_url_host": base_url.split("//")[-1].split("/")[0],
        }

    output_text = _extract_response_text(raw_response)
    response_urls = _urls_in(raw_response)
    output_urls = _urls_in(output_text)
    citation_like_paths = _walk_citation_like(raw_response)
    metadata_paths = [row for row in citation_like_paths if not row["path"].endswith(".content")]
    return {
        "responses_web_search_skipped": False,
        "platform": args.platform,
        "model": raw_response.get("model") or model if isinstance(raw_response, dict) else model,
        "response_id": raw_response.get("id") if isinstance(raw_response, dict) else None,
        "status": raw_response.get("status") if isinstance(raw_response, dict) else None,
        "output_url_count": len(output_urls),
        "response_url_count": len(response_urls),
        "output_url_examples": output_urls[:5],
        "response_url_examples": response_urls[:10],
        "citation_like_response_paths": metadata_paths[:30],
        "output_preview": _preview(output_text, 700),
        "responses_web_search_diagnosis": _diagnose_responses_web_search(output_urls, response_urls, metadata_paths),
    }


def _extract_response_text(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    if isinstance(value.get("output_text"), str):
        return value["output_text"]
    parts: list[str] = []
    for output in value.get("output") or []:
        if not isinstance(output, dict):
            continue
        for content in output.get("content") or []:
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts)


def _diagnose_responses_web_search(output_urls: list[str], response_urls: list[str], metadata_paths: list[dict[str, Any]]) -> str:
    metadata_with_urls = [row for row in metadata_paths if row.get("url_count", 0) > 0]
    if output_urls:
        return "web_search_output_urls_ok: Responses API + web_search 已返回正文 URL，可接入报告引用链路。"
    if metadata_with_urls:
        return "web_search_metadata_urls_ok: Responses API + web_search 已返回引用/搜索 metadata URL，需要把这些字段映射为 citations。"
    if response_urls:
        return "web_search_response_urls_mixed: 完整响应中有 URL，但不在明显 citation/source 字段；需要人工查看路径。"
    if metadata_paths:
        return "web_search_metadata_without_url: 响应有 search/source 类字段但未见 URL；可能插件启用但资源未返回链接。"
    return "web_search_no_citation_signal: Responses API 调用成功但没有 URL 或 citation metadata；检查插件权限、模型是否支持 tools，或换更明确的实时查询。"


def _diagnose_live(content_urls: list[str], citations: list[dict[str, Any]], metadata_paths: list[dict[str, Any]]) -> str:
    metadata_with_urls = [row for row in metadata_paths if row.get("url_count", 0) > 0]
    if citations:
        return "provider_content_citations_ok: 模型 content 中返回了 citations，parser 能解析；若报告仍为空，查聚合/落库。"
    if content_urls:
        return "content_url_parse_gap: 模型正文里有 URL，但 parsed.citations 为空；查 prompt JSON 格式或 parser。"
    if metadata_with_urls:
        return "client_metadata_gap: 完整响应里疑似有引用 metadata/URL，但当前客户端只读 message.content，需要接入这些字段。"
    if metadata_paths:
        return "metadata_without_url: 完整响应有 citation/source/search 类字段，但未看到 URL；确认供应商字段语义。"
    return "provider_no_citation_signal: 完整响应没有 URL 或 citation metadata；当前模型/API调用方式大概率不支持真实引用来源。"


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe source-reference flow from model response to report_data.")
    parser.add_argument("--live", action="store_true", help="Call the configured OpenAI-compatible provider once.")
    parser.add_argument("--responses-web-search", action="store_true", help="Call Volcengine Responses API with tools=[web_search].")
    parser.add_argument("--env-prefix", default="DEEPSEEK", help="Provider env prefix, e.g. DEEPSEEK.")
    parser.add_argument("--platform", default="DeepSeek", help="Display platform name.")
    parser.add_argument("--base-url", default="", help="Override provider base URL.")
    parser.add_argument("--model", default="", help="Override provider model.")
    parser.add_argument("--brand", default="兑吧", help="Brand name used by the live probe.")
    parser.add_argument("--competitors", default="有赞,微盟", help="Comma-separated competitor names.")
    parser.add_argument(
        "--query",
        default="请列出金融场景积分商城管理工具供应商，并给出可核验的公开网页 URL 作为来源。",
        help="Live probe query.",
    )
    args = parser.parse_args()

    output: dict[str, Any] = {"storage_probe": inspect_storage()}
    if args.live:
        output["live_probe"] = asyncio.run(inspect_live(args))
    if args.responses_web_search:
        output["responses_web_search_probe"] = asyncio.run(inspect_responses_web_search(args))
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
