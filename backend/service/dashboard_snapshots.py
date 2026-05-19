from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from service.storage import brand_dashboard_snapshots_store, runs_store


METRIC_DEFINITIONS = {
    "visibility": {
        "metric_name": "可见度",
        "unit": "%",
        "direction": "higher_is_better",
        "benchmark_value": 50.0,
        "benchmark_label": "≥ 50%",
        "scale": 100,
    },
    "rank": {
        "metric_name": "平均位次",
        "unit": "rank",
        "direction": "lower_is_better",
        "benchmark_value": 2,
        "benchmark_label": "≤ 2",
        "scale": 1,
    },
    "sentiment_score": {
        "metric_name": "舆情指数",
        "unit": "%",
        "direction": "higher_is_better",
        "benchmark_value": 60,
        "benchmark_label": "≥ 60%",
        "scale": 100,
    },
    "ai_recommend_score": {
        "metric_name": "AI 推荐度",
        "unit": "score",
        "direction": "higher_is_better",
        "benchmark_value": 90,
        "benchmark_label": "≥ 90",
        "scale": 1,
    },
    "own_citations": {
        "metric_name": "品牌自有引用",
        "unit": "count",
        "direction": "higher_is_better",
        "benchmark_value": 3,
        "benchmark_label": "≥ 3",
        "scale": 1,
    },
    "competitor_suppression_rate": {
        "metric_name": "竞品压制率",
        "unit": "%",
        "direction": "lower_is_better",
        "benchmark_value": 30,
        "benchmark_label": "< 30%",
        "scale": 100,
    },
}


def persist_dashboard_snapshot(run: dict[str, Any], report_data: dict[str, Any]) -> dict[str, Any]:
    snapshot = _build_snapshot(run, report_data)
    store = brand_dashboard_snapshots_store.read()
    account = store.get(snapshot["brand_id"])
    if not isinstance(account, dict):
        account = {
            "brand_id": snapshot["brand_id"],
            "brand_name": snapshot["main_brand"]["brand_name"],
            "snapshots": [],
        }

    snapshots = [item for item in account.get("snapshots", []) if item.get("run_id") != snapshot["run_id"]]
    snapshots.append(snapshot)
    snapshots.sort(key=lambda item: item.get("generated_at") or item.get("snapshot_date") or "")

    account.update(
        {
            "brand_id": snapshot["brand_id"],
            "brand_name": snapshot["main_brand"]["brand_name"],
            "latest_run_id": snapshot["run_id"],
            "latest_brand_config_id": snapshot["brand_config_id"],
            "latest_entity_id": snapshot["entity_id"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "snapshots": snapshots,
        }
    )
    store[snapshot["brand_id"]] = account
    brand_dashboard_snapshots_store.write(store)
    return snapshot


def sync_completed_run_snapshots() -> int:
    synced = 0
    runs = runs_store.read().values()
    completed_runs = [
        run
        for run in runs
        if isinstance(run, dict) and run.get("status") == "completed" and isinstance(run.get("report_data"), dict)
    ]
    completed_runs.sort(key=lambda item: item.get("updated_at") or item.get("inspection_completed_at") or "")
    for run in completed_runs:
        persist_dashboard_snapshot(run, run["report_data"])
        synced += 1
    return synced


def get_dashboard_contract(brand_config_id: str | None = None, brand_id: str | None = None) -> dict[str, Any] | None:
    snapshot, previous = _select_snapshot_pair(brand_config_id=brand_config_id, brand_id=brand_id)
    if not snapshot:
        return None
    return _build_contract(snapshot, previous)


def get_brand_history(brand_id: str, days: int = 30) -> dict[str, Any] | None:
    account = brand_dashboard_snapshots_store.get(str(brand_id))
    if not account:
        account = _find_account(brand_id=str(brand_id))
    if not account:
        return None

    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, int(days or 30)))
    snapshots = []
    for snapshot in account.get("snapshots", []):
        generated_at = _parse_datetime(snapshot.get("generated_at"))
        if generated_at and generated_at < cutoff:
            continue
        snapshots.append(snapshot)

    snapshots.sort(key=lambda item: item.get("generated_at") or item.get("snapshot_date") or "")
    by_metric: dict[str, list[dict[str, Any]]] = {metric_id: [] for metric_id in METRIC_DEFINITIONS}
    history = []

    for snapshot in snapshots:
        metrics = snapshot.get("metrics") or {}
        date = snapshot.get("snapshot_date") or _date_text(snapshot.get("generated_at"))
        history.append(
            {
                "date": date,
                "run_id": snapshot.get("run_id"),
                "report_id": snapshot.get("report_id"),
                "metrics": metrics,
            }
        )
        for metric_id in METRIC_DEFINITIONS:
            value = metrics.get(metric_id)
            if value is not None:
                by_metric[metric_id].append({"date": date, "value": value, "run_id": snapshot.get("run_id")})

    return {
        "brand_id": account.get("brand_id"),
        "brand_name": account.get("brand_name"),
        "days": days,
        "history": history,
        "by_metric": by_metric,
        "by_intent": [],
    }


def get_overview_payload(brand_config_id: str | None = None) -> dict[str, Any] | None:
    snapshot, _previous = _select_snapshot_pair(brand_config_id=brand_config_id)
    if not snapshot:
        return None
    report = snapshot.get("report_data") or {}
    queryset = snapshot.get("queryset") or {}
    return {
        "queryset": {
            "version": queryset.get("queryset_version"),
            "total_queries": len(queryset.get("queries", [])),
            "queries": queryset.get("queries", []),
        },
        "metrics": report.get("global"),
        "attribution": {
            "platforms": report.get("platforms", []),
            "competitor_ranking": report.get("competitor_ranking", []),
            "sources": report.get("sources", []),
        },
        "methodology_note": "Metrics are aggregated from live multi-platform answers generated during the latest completed diagnostic run.",
        "latest_run_id": snapshot.get("run_id"),
        "brand_id": snapshot.get("brand_id"),
        "brand_config_id": snapshot.get("brand_config_id"),
    }


def _build_snapshot(run: dict[str, Any], report_data: dict[str, Any]) -> dict[str, Any]:
    brand_config = report_data.get("brand_config") or {}
    meta = report_data.get("meta") or {}
    entity_name = brand_config.get("entity_name") or meta.get("brand_name") or "未命名品牌"
    brand_id = _brand_account_id(entity_name)
    metrics = _dashboard_metrics(report_data.get("global") or {})
    generated_at = meta.get("generated_at") or datetime.now(timezone.utc).isoformat()

    return {
        "brand_id": brand_id,
        "brand_config_id": brand_config.get("brand_config_id") or run.get("brand_config_id"),
        "entity_id": brand_config.get("entity_id"),
        "run_id": run.get("run_id"),
        "report_id": meta.get("report_id"),
        "snapshot_date": meta.get("report_date") or _date_text(generated_at),
        "generated_at": generated_at,
        "main_brand": _main_brand(brand_id, brand_config, meta),
        "brand_config": brand_config,
        "metrics": metrics,
        "queryset": run.get("queryset") or {"queries": brand_config.get("queries", [])},
        "report_data": report_data,
    }


def _build_contract(snapshot: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    report = snapshot.get("report_data") or {}
    queryset = snapshot.get("queryset") or {}
    lineage = report.get("lineage") or {}
    previous_metrics = (previous or {}).get("metrics") or {}
    metrics = snapshot.get("metrics") or {}

    return {
        "snapshot_date": snapshot.get("snapshot_date"),
        "main_brand": snapshot.get("main_brand"),
        "brand_config": snapshot.get("brand_config"),
        "contract_version": "dashboard_from_report_data_v1",
        "latest_run_id": snapshot.get("run_id"),
        "diagnostic_run": {"run_id": snapshot.get("run_id")},
        "report": {"run_id": snapshot.get("run_id"), "report_id": snapshot.get("report_id")},
        "queryset": {
            "queryset_id": queryset.get("queryset_id") or lineage.get("queryset_id"),
            "queryset_version": queryset.get("queryset_version") or lineage.get("queryset_version"),
            "parent_queryset_id": queryset.get("parent_queryset_id") or lineage.get("parent_queryset_id"),
            "queries": queryset.get("queries") or [],
        },
        "lineage": lineage,
        "key_metrics": [_metric_row(metric_id, metrics, previous_metrics) for metric_id in METRIC_DEFINITIONS],
        "key_issues": _issue_rows(report),
        "optimization_actions": _action_rows(report),
        "cross_topic_rules": _cross_topic_rules(),
        "rule_activation": _rule_activation_gate(),
    }


def _dashboard_metrics(global_metrics: dict[str, Any]) -> dict[str, float | int | None]:
    rows = {}
    for metric_id, definition in METRIC_DEFINITIONS.items():
        value = global_metrics.get(metric_id)
        if value is None:
            rows[metric_id] = None
            continue
        number = _number(value)
        rows[metric_id] = round(number * definition["scale"], 1) if number is not None else None
    return rows


def _metric_row(metric_id: str, metrics: dict[str, Any], previous_metrics: dict[str, Any]) -> dict[str, Any]:
    definition = METRIC_DEFINITIONS[metric_id]
    return {
        "metric_id": metric_id,
        "metric_name": definition["metric_name"],
        "current_value": metrics.get(metric_id),
        "previous_value": previous_metrics.get(metric_id),
        "competitor_avg": None,
        "benchmark_value": definition["benchmark_value"],
        "benchmark_label": definition["benchmark_label"],
        "unit": definition["unit"],
        "direction": definition["direction"],
        "use_for_before_after": True,
    }


def _issue_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for index, insight in enumerate(report.get("insights") or [], start=1):
        rows.append(
            {
                "issue_id": f"issue_{index}",
                "severity": insight.get("priority") or "P1",
                "dimension": "诊断报告",
                "title": insight.get("text") or "巡检发现待优化项",
                "abnormal_metric": {},
                "business_pain": insight.get("text") or "",
                "evidence": [],
            }
        )
    return rows


def _action_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    recommendations = report.get("optimization_recommendations") or []
    rows = []
    for index, item in enumerate(recommendations, start=1):
        rows.append(
            {
                "action_id": f"action_{index}",
                "action_name": item.get("title") or item.get("text") or "优化内容资产",
                "action_type": "content_optimization",
                "output_assets": ["选型问答", "官网 FAQ", "案例页"],
                "success_metrics": ["可见度", "品牌自有引用", "AI 推荐度"],
                "priority": item.get("priority") or "P1",
                "description": item.get("text") or "",
            }
        )
    if rows:
        return rows
    return [
        {
            "action_id": "action_content_refresh",
            "action_name": "持续补强核心场景内容",
            "action_type": "content_optimization",
            "output_assets": ["场景页", "FAQ", "对比页"],
            "success_metrics": ["可见度", "平均位次"],
            "priority": "P2",
            "description": "根据本次巡检结果维护可被 AI 引用的事实型内容。",
        }
    ]


def _cross_topic_rules() -> list[dict[str, Any]]:
    return [
        {
            "rule_id": "rule_content_optimization",
            "rule_name": "报告诊断内容优化",
            "applies_to": ["content_optimization"],
            "template": "围绕诊断问题输出清晰主张，补充能力事实和可追溯证据，并避免编造不可验证数据。",
            "required_elements": ["诊断问题", "品牌定位", "能力事实", "证据来源", "风险约束"],
        }
    ]


def _rule_activation_gate() -> dict[str, Any]:
    baseline_rule = {
        "rule_id": "baseline_geo_content_v1",
        "rule_version": "baseline_v1.0",
        "rule_name": "GEO 内容生成基准规则",
        "source_type": "baseline",
        "status": "active",
        "maintained_by": "user",
        "applies_to": ["content_optimization", "website_content", "ugc_content", "rewrite_rules", "comparison_page", "case_study"],
        "template": "统一品牌实体表达，按“主张 + 事实 + 证据”输出内容；不得编造数据、客户案例、排名或攻击竞品。",
        "required_elements": ["品牌实体", "业务场景", "事实表达", "证据来源", "风险约束"],
    }
    active_rule = {
        "active_rule_id": "active_baseline_geo_content_v1",
        "source_rule_id": baseline_rule["rule_id"],
        "source_type": "baseline",
        "rule_version": baseline_rule["rule_version"],
        "rule_name": baseline_rule["rule_name"],
        "platform": "all",
        "query_pattern": "all",
        "action_type": "all",
        "status": "active",
        "activated_by_evaluation_id": None,
        "applies_to": baseline_rule["applies_to"],
        "template": baseline_rule["template"],
        "required_elements": baseline_rule["required_elements"],
    }
    return {
        "default_decision_policy": {
            "mvp_default": "keep_baseline",
            "fallback_rule": "baseline_rule",
        },
        "stores": {
            "baseline_rules_store": [baseline_rule],
            "platform_rules_store": [],
            "rule_activation_evaluations": [],
            "active_rules_store": [active_rule],
        },
        "actiontask_rule_source": "优化任务只读取 active_rules_store；若没有匹配规则，则回退 baseline_rules_store 的 active version。",
    }


def _main_brand(brand_id: str, brand_config: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    entity_name = brand_config.get("entity_name") or meta.get("brand_name") or "未命名品牌"
    segments = [item for item in brand_config.get("industry_segments", []) if item]
    return {
        "brand_id": brand_id,
        "brand_config_id": brand_config.get("brand_config_id"),
        "entity_id": brand_config.get("entity_id"),
        "brand_name": entity_name,
        "short_name": entity_name,
        "aliases": brand_config.get("entity_aliases", []),
        "category": segments[0] if segments else "GEO 诊断品牌",
    }


def _select_snapshot_pair(
    brand_config_id: str | None = None,
    brand_id: str | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    account = brand_dashboard_snapshots_store.get(str(brand_id)) if brand_id else None
    if not account and (brand_id or brand_config_id):
        account = _find_account(brand_id=brand_id, brand_config_id=brand_config_id)
    if not account:
        account = _latest_account()
    if not account:
        return None, None

    snapshots = sorted(account.get("snapshots", []), key=lambda item: item.get("generated_at") or item.get("snapshot_date") or "")
    if brand_config_id:
        snapshots = [item for item in snapshots if item.get("brand_config_id") == brand_config_id]
    if not snapshots:
        return None, None
    return snapshots[-1], snapshots[-2] if len(snapshots) > 1 else None


def _find_account(brand_id: str | None = None, brand_config_id: str | None = None) -> dict[str, Any] | None:
    for account in brand_dashboard_snapshots_store.read().values():
        if not isinstance(account, dict):
            continue
        if brand_id and brand_id in {account.get("brand_id"), account.get("latest_brand_config_id"), account.get("latest_entity_id")}:
            return account
        if brand_config_id and any(item.get("brand_config_id") == brand_config_id for item in account.get("snapshots", [])):
            return account
    return None


def _latest_account() -> dict[str, Any] | None:
    accounts = [value for value in brand_dashboard_snapshots_store.read().values() if isinstance(value, dict)]
    if not accounts:
        return None
    return sorted(accounts, key=lambda item: item.get("updated_at") or "", reverse=True)[0]


def _brand_account_id(entity_name: str) -> str:
    digest = hashlib.sha1(str(entity_name).strip().lower().encode("utf-8")).hexdigest()[:12]
    return f"brand_{digest}"


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _date_text(value: Any) -> str:
    parsed = _parse_datetime(value)
    return parsed.date().isoformat() if parsed else datetime.now(timezone.utc).date().isoformat()


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
