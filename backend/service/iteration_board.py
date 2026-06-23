from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any

from service.storage import iteration_priority_board_store


BOARD_KEY = "geo_iteration_priority_board"
VALID_PHASES = {"now", "next", "later"}
VALID_STATUSES = {"planned", "in_progress", "blocked", "done"}


DEFAULT_BOARD: dict[str, Any] = {
    "board_id": BOARD_KEY,
    "title": "GEO Iteration Priority Board",
    "owner": "product / architecture / shared",
    "last_updated": "2026-05-21",
    "role_map": [
        {"document": "CLAUDE.md", "role": "Project entry, boundaries, constraints, navigation"},
        {"document": "docs/ITERATION_PRIORITY_BOARD.md", "role": "Only cross-topic priority entrance"},
        {"document": "docs/DIAGNOSTIC_FLOW_CONTEXT.md", "role": "Diagnostic flow source of truth and invariants"},
        {"document": "docs/queryset-governance-future-plan.md", "role": "QuerySet governance roadmap"},
        {"document": "docs/GEO_PROJECT_PROGRESS.md", "role": "Recent progress and handoff log"},
    ],
    "items": [
        {
            "id": "report-contract-stabilization",
            "phase": "now",
            "priority": "P0-1",
            "title": "Report contract stabilization",
            "status": "in_progress",
            "owner": "architecture",
            "why_now": "报告是 dashboard、内容生成、导出链路的上游契约，未稳定会放大后续返工。",
            "current_blocker": "前后端字段与展示逻辑仍有同步风险。",
            "source_of_truth": [
                "docs/DIAGNOSTIC_API_CONTRACT.md",
                "docs/DIAGNOSTIC_FLOW_CONTEXT.md",
                "src/schemas/report_data.schema.json",
            ],
            "next_action": "对齐 report_data_v1 字段、页面适配器和 schema 校验口径。",
            "exit_condition": "report page / export / downstream consumers 共享同一 contract，不再依赖临时 fallback。",
            "handoff_note": "任何字段调整必须先过 schema 与 adapter。",
        },
        {
            "id": "async-content-generation-persistence-fix",
            "phase": "now",
            "priority": "P0-2",
            "title": "Async content generation persistence fix",
            "status": "in_progress",
            "owner": "product",
            "why_now": "内容生成链路如果状态与持久化不稳，会导致后续评估与复用失真。",
            "current_blocker": "run/result persistence 逻辑可能存在断点。",
            "source_of_truth": [
                "backend/service/content_generation.py",
                "backend/storage/content_versions.json",
                "backend/tests/test_content_generation_persistence.py",
            ],
            "next_action": "明确 run state、result store、前端轮询/读取口径。",
            "exit_condition": "生成任务从触发到结果读取完整闭环稳定。",
            "handoff_note": "必须和 Rule Activation / report 引用路径对齐。",
        },
        {
            "id": "dashboard-contract-adoption",
            "phase": "now",
            "priority": "P0-3",
            "title": "Dashboard contract adoption",
            "status": "planned",
            "owner": "product",
            "why_now": "Dashboard 是外显层，但必须建立在稳定 report contract 之上。",
            "current_blocker": "仍存在旧版 UI 与新契约并存状态。",
            "source_of_truth": [
                "docs/GEO_PROJECT_PROGRESS.md",
                "backend/service/dashboard_snapshots.py",
                "src/api/geo.js",
            ],
            "next_action": "明确页面改造范围与新 contract 对应字段。",
            "exit_condition": "/dashboard 不再依赖旧问题链路/硬编码结构。",
            "handoff_note": "先做 contract 接入，再做视觉重构。",
        },
        {
            "id": "ui-sampling-calibration",
            "phase": "next",
            "priority": "P1-1",
            "title": "UI sampling / calibration",
            "status": "planned",
            "owner": "product",
            "why_now": "诊断报告和 dashboard 进入真实 API 后，需要校准样本口径与展示语言。",
            "current_blocker": "尚未沉淀统一的抽样检查与 UI 校准 checklist。",
            "source_of_truth": ["docs/GEO_PROJECT_PROGRESS.md", "docs/DIAGNOSTIC_FLOW_CONTEXT.md"],
            "next_action": "补齐抽样对象、页面清单、字段核对方式和验收标准。",
            "exit_condition": "核心页面的样本展示与后端 contract 逐项可追溯。",
            "handoff_note": "进入执行前补齐具体页面与样本 run_id。",
        },
        {
            "id": "executive-summary-agent",
            "phase": "next",
            "priority": "P1-2",
            "title": "Executive Summary Agent",
            "status": "planned",
            "owner": "product",
            "why_now": "经营层需要从诊断结果中直接读取结论、风险和下一步动作。",
            "current_blocker": "摘要输入、输出 contract、事实边界尚未固定。",
            "source_of_truth": ["docs/DIAGNOSTIC_API_CONTRACT.md", "docs/REPORT_GENERATOR_SOP.md"],
            "next_action": "定义摘要输入字段、不可编造规则和报告落点。",
            "exit_condition": "Executive Summary 只基于 report contract 生成，并能追溯到证据。",
            "handoff_note": "不能绕开 diagnostic report_data_v1 直接拼 prompt。",
        },
        {
            "id": "source-graph",
            "phase": "next",
            "priority": "P1-3",
            "title": "Source Graph",
            "status": "planned",
            "owner": "architecture",
            "why_now": "Source Graph 能解释品牌被提及/缺席的证据来源与关系。",
            "current_blocker": "信息来源类型、边关系和报告入口尚未定稿。",
            "source_of_truth": ["docs/DIAGNOSTIC_FLOW_CONTEXT.md", "backend/tools/source_reference_probe.py"],
            "next_action": "定义最小 graph contract：node、edge、evidence、run lineage。",
            "exit_condition": "图谱能从诊断 run 追溯到回答、source reference 和建议动作。",
            "handoff_note": "先做 contract 与证据追踪，不先做复杂可视化。",
        },
        {
            "id": "rule-lifecycle-full-governance",
            "phase": "later",
            "priority": "P2-1",
            "title": "Rule lifecycle full governance",
            "status": "planned",
            "owner": "architecture",
            "why_now": "Rule Activation 已进入执行链路，后续需要补齐全生命周期治理。",
            "current_blocker": "当前优先级仍在 report/dashboard/content 的契约稳定。",
            "source_of_truth": ["docs/rule_activation_integration_guide.md", "docs/rule_activation_flow_patch.md"],
            "next_action": "进入执行窗口后拆分 review、publish、archive、audit trail。",
            "exit_condition": "规则从提取到激活、消费、归档都有可追溯状态。",
            "handoff_note": "ActionTask 只能消费 active_rules_store。",
        },
        {
            "id": "business-attribution",
            "phase": "later",
            "priority": "P2-2",
            "title": "Business attribution",
            "status": "planned",
            "owner": "product",
            "why_now": "需要把 GEO 优化动作与业务效果建立可解释关联。",
            "current_blocker": "效果指标、复测周期和可比性规则尚未进入当前窗口。",
            "source_of_truth": ["backend/storage/effect_attribution.json", "backend/service/content_generation.py"],
            "next_action": "定义 attribution methodology、输入指标和不可比状态。",
            "exit_condition": "内容版本、规则动作、复测指标之间形成稳定归因链路。",
            "handoff_note": "不能破坏 QuerySet lineage comparability。",
        },
        {
            "id": "research-derived-modules",
            "phase": "later",
            "priority": "P2-3",
            "title": "Research-derived modules",
            "status": "planned",
            "owner": "shared",
            "why_now": "研究输入需要有进入执行窗口的承接位置。",
            "current_blocker": "尚未筛选哪些研究会转化为产品模块。",
            "source_of_truth": ["docs/ITERATION_PRIORITY_BOARD.md"],
            "next_action": "仅将可执行研究挂入专题文档的 Open Questions / Research Notes。",
            "exit_condition": "研究项进入执行前具备 source-of-truth、next action 和 exit condition。",
            "handoff_note": "不新增一级 research 目录作为主规划层。",
        },
    ],
    "cross_cutting_risks": [
        "schema drift",
        "mock fallback regression",
        "lineage break risk",
        "active_rules_store bypass risk",
    ],
    "recently_closed": [],
}


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split("\n") if item.strip()]
    return []


def _normalize_item(item: Any, index: int) -> dict[str, Any]:
    raw = item if isinstance(item, dict) else {}
    title = str(raw.get("title") or "Untitled item").strip()
    fallback_id = title.lower().replace(" ", "-") or f"item-{index + 1}"
    phase = str(raw.get("phase") or "later").strip().lower()
    status = str(raw.get("status") or "planned").strip().lower()
    return {
        "id": str(raw.get("id") or fallback_id).strip(),
        "phase": phase if phase in VALID_PHASES else "later",
        "priority": str(raw.get("priority") or "").strip(),
        "title": title,
        "status": status if status in VALID_STATUSES else "planned",
        "owner": str(raw.get("owner") or "shared").strip(),
        "why_now": str(raw.get("why_now") or "").strip(),
        "current_blocker": str(raw.get("current_blocker") or "").strip(),
        "source_of_truth": _string_list(raw.get("source_of_truth")),
        "next_action": str(raw.get("next_action") or "").strip(),
        "exit_condition": str(raw.get("exit_condition") or "").strip(),
        "handoff_note": str(raw.get("handoff_note") or "").strip(),
    }


def _normalize_board(payload: dict[str, Any], *, touch: bool = False) -> dict[str, Any]:
    raw = payload if isinstance(payload, dict) else {}
    board = deepcopy(DEFAULT_BOARD)
    board.update(
        {
            "board_id": BOARD_KEY,
            "title": str(raw.get("title") or board["title"]).strip(),
            "owner": str(raw.get("owner") or board["owner"]).strip(),
            "last_updated": date.today().isoformat() if touch else str(raw.get("last_updated") or board["last_updated"]),
            "role_map": raw.get("role_map") if isinstance(raw.get("role_map"), list) else board["role_map"],
            "items": [_normalize_item(item, index) for index, item in enumerate(raw.get("items") or [])],
            "cross_cutting_risks": _string_list(raw.get("cross_cutting_risks")),
            "recently_closed": raw.get("recently_closed") if isinstance(raw.get("recently_closed"), list) else [],
        }
    )
    if not board["items"]:
        board["items"] = deepcopy(DEFAULT_BOARD["items"])
    if not board["cross_cutting_risks"]:
        board["cross_cutting_risks"] = deepcopy(DEFAULT_BOARD["cross_cutting_risks"])
    return board


def get_iteration_priority_board() -> dict[str, Any]:
    stored = iteration_priority_board_store.get(BOARD_KEY)
    if not stored:
        return deepcopy(DEFAULT_BOARD)
    return _normalize_board(stored)


def save_iteration_priority_board(payload: dict[str, Any]) -> dict[str, Any]:
    board = _normalize_board(payload, touch=True)
    return iteration_priority_board_store.upsert(BOARD_KEY, board)
