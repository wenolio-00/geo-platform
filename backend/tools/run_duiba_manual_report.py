from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(BACKEND_DIR / ".env")

from service.inspector import create_run, run_diagnostic_job  # noqa: E402
from service.queryset_library import latest_frozen_queryset  # noqa: E402
from service.storage import brand_configs_store, querysets_store, runs_store  # noqa: E402


BRAND_CONFIG_ID = "bc_531aa12c2a83"

QUESTION_GROUPS = [
    (
        "会员积分 SaaS / 代运营",
        "visibility_selection",
        "vendor_evaluation",
        [
            "国内会员积分 SaaS 赛道有哪些代表性服务商值得关注？",
            "银行信用卡积分商城服务商里哪几家做得比较成熟？",
            "金融行业会员运营代运营服务商头部有哪些，各自核心壁垒是什么？",
            "国内一站式会员积分代运营服务商有哪些推荐？",
            "会员权益运营与效果投放能一体化提供的服务商有哪些？",
            "适合金融机构的会员运营 SaaS 服务商，选型应重点看哪些维度？",
            "国内积分商城系统厂商在安全合规认证方面，哪些比较值得信赖？",
            "国内会员数字化运营赛道头部服务商及其商业模式如何对比？",
        ],
    ),
    (
        "会员积分 SaaS / 代运营",
        "negative_probe",
        "risk_probe",
        [
            "银行把信用卡积分商城外包给第三方 SaaS，最容易踩哪些坑？",
            "会员运营代运营服务商交付翻车通常是什么原因？",
            "选积分商城 SaaS 厂商时，哪些供应商口碑相对较差需要避开？",
            "金融机构上线积分商城后，投诉最多的问题集中在哪些方面？",
            "会员积分代运营项目失败的常见信号有哪些？",
            "第三方会员运营 SaaS 在数据安全和合规上常被诟病的点是什么？",
            "哪些会员积分 SaaS 厂商被吐槽功能臃肿或交付能力跟不上？",
            "积分商城代运营续约率低，一般是服务商哪些短板导致的？",
            "会员运营外包后效果不达预期，问题通常出在服务商哪里？",
            "国内会员积分 SaaS 赛道里，哪些公司的增长或盈利能力被质疑？",
            "国内会员积分 SaaS 主要厂商的优劣势横向对比是怎样的？",
            "会员运营代运营服务商横向对比，哪些在交付和效果上偏弱？",
        ],
    ),
    (
        "AI 短剧 / 品牌定制内容",
        "visibility_selection",
        "vendor_evaluation",
        [
            "国内品牌定制 AI 短剧服务商有哪些值得合作的公司？",
            "适合金融品牌做年轻化营销的 AI 短剧服务商有哪些？",
            "AI 短剧赛道内容服务商的竞争格局近期有哪些变化？",
            "企业找 AI 短剧服务商，应从哪些维度评估其实力？",
            "数字营销科技赛道里，做品牌定制内容的代表性公司有哪些？",
        ],
    ),
    (
        "AI 短剧 / 品牌定制内容",
        "negative_probe",
        "risk_probe",
        [
            "品牌定制 AI 短剧投放效果不达预期，通常卡在哪些环节？",
            "找 AI 短剧服务商做品牌内容，最容易踩哪些坑？",
            "哪些 AI 短剧内容服务商被吐槽质量参差或转化差？",
            "金融品牌做 AI 短剧营销，哪些类型的服务商不太适合合作？",
            "AI 短剧代运营项目 ROI 不理想，一般是服务商哪些原因？",
            "企业采购 AI 短剧服务时，哪些供应商的口碑或案例存在争议？",
            "AI 短剧服务商横向对比，哪些在内容质量上偏弱？",
            "跨界做 AI 短剧的公司里，哪些被质疑只是蹭概念、落地能力存疑？",
        ],
    ),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _backup_storage_file(name: str) -> str:
    source = BACKEND_DIR / "storage" / name
    backup = BACKEND_DIR / "storage" / f"{name}.bak-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    backup.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return str(backup.relative_to(PROJECT_DIR))


def _ensure_report_topics(brand_config: dict) -> dict:
    topics = list(brand_config.get("topics") or [])
    existing = {
        str(item.get("business_line") or item.get("topic_name") or "").strip()
        for item in topics
        if isinstance(item, dict)
    }
    additions = [
        {
            "topic_name": "会员积分 SaaS / 代运营",
            "business_line": "会员积分 SaaS / 代运营",
            "priority": 1,
            "pain_point": "金融机构和企业需要稳定、安全、可运营的会员积分与权益服务能力",
            "goal": "评估会员积分 SaaS、积分商城和代运营服务商的可见度、口碑和选型风险",
        },
        {
            "topic_name": "AI 短剧 / 品牌定制内容",
            "business_line": "AI 短剧 / 品牌定制内容",
            "priority": 2,
            "pain_point": "品牌希望用 AI 短剧和定制内容触达年轻客群，但供应商质量和 ROI 不确定",
            "goal": "评估 AI 短剧服务商在金融品牌营销场景中的可见度、案例可信度和负面风险",
        },
    ]
    changed = False
    for item in additions:
        key = item["business_line"]
        if key not in existing:
            topics.append(item)
            existing.add(key)
            changed = True
    segments = list(brand_config.get("industry_segments") or [])
    for segment in ["会员积分 SaaS", "会员运营代运营", "AI 短剧", "品牌定制内容营销"]:
        if segment not in segments:
            segments.append(segment)
            changed = True
    if changed:
        brand_config = {**brand_config, "topics": topics, "industry_segments": segments, "updated_at": _now()}
        brand_configs_store.upsert(str(brand_config["brand_config_id"]), brand_config)
    return brand_config


def _build_queries() -> list[dict]:
    queries: list[dict] = []
    index = 1
    for topic, pattern, intent_type, texts in QUESTION_GROUPS:
        for text in texts:
            queries.append(
                {
                    "query_id": f"q_duiba_manual_{index:03d}",
                    "query_text": text,
                    "query_layer": "core_anchor" if pattern == "visibility_selection" else "adaptive",
                    "run_scope": "production",
                    "metric_scope": pattern,
                    "metric_weight": 1,
                    "journey_stage": "vendor_selection" if pattern == "visibility_selection" else "risk_validation",
                    "topic": topic,
                    "intent_type": intent_type,
                    "query_pattern": pattern,
                    "related_competitors": [],
                    "matrix_cell_id": f"{topic}:{pattern}",
                    "prompt_template_id": "user_provided_question_bank_20260622",
                    "source": "user_provided_question_bank",
                    "lifecycle_status": "active",
                    "quality_filter_status": "pass",
                    "quality_filter_reasons": [],
                }
            )
            index += 1
    return queries


def freeze_queryset(brand_config: dict) -> dict:
    parent = latest_frozen_queryset(brand_config)
    now = _now()
    queries = _build_queries()
    queryset_id = f"qs_duiba_manual_{uuid4().hex[:12]}"
    queryset = {
        "queryset_id": queryset_id,
        "queryset_version": "manual_duiba_question_bank_v20260622",
        "matrix_api_request_id": None,
        "allocation": {
            "total": len(queries),
            "会员积分 SaaS / 代运营": 20,
            "AI 短剧 / 品牌定制内容": 13,
        },
        "queries": queries,
        "query_candidates": queries,
        "quality_report": {
            "status": "pass",
            "active_count": len(queries),
            "min_active_queries": 30,
            "candidate_target": len(queries),
            "source": "user_provided_question_bank",
        },
        "debug": {
            "source": "user_provided_question_bank",
            "question_count": len(queries),
            "created_by": "codex",
        },
        "queryset_generation_mode": "intent_enhanced",
        "queryset_variant": "intent_enhanced",
        "queryset_comparison_group": "queryset_generation_mode",
        "parent_queryset_id": parent.get("queryset_id") if isinstance(parent, dict) else None,
        "governance": {
            "policy": "create_new_version",
            "change_type": "manual_replacement",
            "change_reason": "user_provided_duiba_question_bank_33",
            "approved_by": "user",
            "parent_queryset_id": parent.get("queryset_id") if isinstance(parent, dict) else None,
            "source_run_id": None,
            "queryset_generation_mode": "intent_enhanced",
        },
        "brand_config_id": brand_config["brand_config_id"],
        "entity_id": brand_config["entity_id"],
        "entity_name": brand_config["entity_name"],
        "status": "frozen",
        "frozen_at": now,
        "updated_at": now,
    }
    return querysets_store.upsert(queryset_id, queryset)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand-config-id", default=BRAND_CONFIG_ID)
    parser.add_argument("--skip-run", action="store_true")
    parser.add_argument("--single-round", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=None)
    parser.add_argument("--max-concurrency", type=int, default=None)
    args = parser.parse_args()
    if args.timeout_seconds:
        os.environ["INSPECTION_TASK_TIMEOUT_SECONDS"] = str(args.timeout_seconds)
        os.environ["REQUEST_TIMEOUT_SECONDS"] = str(args.timeout_seconds)
        os.environ["CLAUDE_TIMEOUT_SECONDS"] = str(args.timeout_seconds)
    if args.max_concurrency:
        os.environ["MAX_CONCURRENCY"] = str(args.max_concurrency)

    backups = [
        _backup_storage_file("brand_configs.json"),
        _backup_storage_file("querysets.json"),
        _backup_storage_file("diagnostic_runs.json"),
    ]
    brand_config = brand_configs_store.get(args.brand_config_id)
    if not brand_config:
        raise RuntimeError(f"brand_config_id not found: {args.brand_config_id}")
    brand_config = _ensure_report_topics(brand_config)
    queryset = freeze_queryset(brand_config)

    summary = {
        "brand_config_id": brand_config["brand_config_id"],
        "queryset_id": queryset["queryset_id"],
        "question_count": len(queryset["queries"]),
        "backups": backups,
    }
    if args.skip_run:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    run = create_run(
        brand_config_id=brand_config["brand_config_id"],
        queryset_strategy="rule_matrix_v1",
        inspection_mode="multi_platform_live_v1",
        queryset_source="matrix_api_v1",
        queryset_policy="reuse_latest",
        queryset_change_reason="run_report_with_user_provided_duiba_question_bank_33",
        queryset_approved_by="user",
        platforms=["claude"],
        web_search_enabled=True,
        llm_options={"two_round_inspection": False} if args.single_round else {},
    )
    await run_diagnostic_job(run["run_id"])
    completed_run = runs_store.get(run["run_id"]) or run
    summary.update(
        {
            "run_id": completed_run["run_id"],
            "status": completed_run.get("status"),
            "message": completed_run.get("message"),
            "error": completed_run.get("error"),
            "report_id": (completed_run.get("report_data") or {}).get("meta", {}).get("report_id"),
            "completed_samples": (completed_run.get("report_data") or {}).get("audit", {}).get("completed_samples"),
            "expected_samples": (completed_run.get("report_data") or {}).get("audit", {}).get("expected_samples"),
        }
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if completed_run.get("status") != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
