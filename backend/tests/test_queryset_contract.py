from __future__ import annotations

import asyncio
from collections import Counter
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.aggregator import aggregate_report
from service.dashboard_snapshots import get_overview_payload, persist_dashboard_snapshot
from service.inspector import _inspect_queries
from models.schemas import QuerySet
from service.queryset import (
    build_query_matrix_input,
    build_query_quality_report,
    normalize_query_matrix_output,
    persist_queryset_snapshot,
)
from service.queryset_matrix_client import normalize_matrix_queryset
from service.rule_matrix import generate_rule_matrix_queryset
from service.storage import (
    brand_dashboard_snapshots_store,
    inspection_results_store,
    queryset_items_store,
    querysets_store,
    runs_store,
)


def brand_config() -> dict:
    return {
        "brand_config_id": "bc_contract",
        "entity_id": "entity_contract",
        "entity_name": "杭州XX科技有限公司",
        "entity_aliases": ["XX"],
        "industry_segments": ["金融场景"],
        "topics": [
            {"topic_name": "积分商城管理工具", "business_line": "积分商城", "priority": 1},
            {"topic_name": "会员运营", "business_line": "会员运营", "priority": 2},
        ],
        "competitors": [{"name": "有赞", "aliases": ["Youzan"], "business_line": "会员权益", "category": "SaaS"}],
        "created_at": "2026-05-13T00:00:00+00:00",
        "updated_at": "2026-05-13T00:00:00+00:00",
    }


def duiba_brand_config() -> dict:
    return {
        "brand_config_id": "bc_duiba_contract",
        "entity_id": "entity_duiba_contract",
        "entity_name": "杭州兑吧网络科技有限公司",
        "entity_aliases": ["兑吧", "Duiba"],
        "industry_segments": ["金融场景", "互联网App运营"],
        "topics": [
            {"topic_name": "积分商城管理工具", "business_line": "积分商城", "priority": 1},
            {"topic_name": "会员权益", "business_line": "会员权益", "priority": 2},
            {"topic_name": "互动广告", "business_line": "互动广告", "priority": 3},
        ],
        "competitors": [
            {"name": "有赞", "aliases": ["Youzan"], "business_line": "会员权益", "category": "SaaS"},
            {"name": "微盟", "aliases": ["Weimob"], "business_line": "会员权益", "category": "SaaS"},
            {"name": "星耀", "aliases": [], "business_line": "积分商城", "category": "垂直工具"},
            {"name": "灵智", "aliases": [], "business_line": "积分商城", "category": "垂直工具"},
        ],
    }


def single_topic_brand_config() -> dict:
    config = brand_config()
    config["topics"] = [{"topic_name": "积分商城管理工具", "business_line": "积分商城", "priority": 1}]
    return config


def run_payload() -> dict:
    return {
        "run_id": "run_contract",
        "brand_config_id": "bc_contract",
        "queryset_strategy": "rule_matrix_v1",
        "queryset_source": "matrix_api_v1",
        "inspection_mode": "multi_platform_live_v1",
        "platforms": ["DeepSeek", "Kimi"],
        "inspection_batch_id": "batch_contract",
        "inspection_started_at": "2026-05-13T00:00:00+00:00",
        "inspection_completed_at": "2026-05-13T00:02:00+00:00",
    }


def assert_required_contract(testcase: unittest.TestCase, schema: dict, payload: dict) -> None:
    for field in schema.get("required", []):
        testcase.assertIn(field, payload)
    for field, subschema in schema.get("properties", {}).items():
        if field in payload and isinstance(subschema, dict) and isinstance(payload[field], dict):
            assert_required_contract(testcase, subschema, payload[field])


class QuerySetContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        for store, filename in (
            (querysets_store, "querysets.json"),
            (queryset_items_store, "queryset_items.json"),
            (inspection_results_store, "inspection_results.json"),
            (runs_store, "diagnostic_runs.json"),
            (brand_dashboard_snapshots_store, "brand_dashboard_snapshots.json"),
        ):
            store.path = root / filename
            store.write({})

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_brand_config_maps_to_query_matrix_input(self) -> None:
        matrix_input = build_query_matrix_input(brand_config(), run_payload())

        self.assertEqual(matrix_input.run_id, "run_contract")
        self.assertEqual(matrix_input.brand_config_snapshot["brand_config_id"], "bc_contract")
        self.assertEqual(matrix_input.queryset_source, "matrix_api_v1")
        self.assertEqual(matrix_input.platforms_requested, ["DeepSeek", "Kimi"])

    def test_query_matrix_output_shape_and_quality_gate(self) -> None:
        matrix_input = build_query_matrix_input(brand_config(), run_payload())
        raw = generate_rule_matrix_queryset(brand_config(), "rule_matrix_v1")
        output = normalize_query_matrix_output(raw, matrix_input)
        queryset = QuerySet(**output.model_dump())

        self.assertEqual(queryset.brand_config_id, "bc_contract")
        self.assertEqual(queryset.run_id, "run_contract")
        self.assertEqual(queryset.quality_report.status, "pass")
        self.assertTrue(queryset.queries)
        self.assertTrue(all(query.query_pattern for query in queryset.queries))

    def test_duiba_scenario_library_generates_full_queryset(self) -> None:
        matrix_input = build_query_matrix_input(duiba_brand_config(), run_payload())
        raw = generate_rule_matrix_queryset(duiba_brand_config(), "rule_matrix_v1")
        output = normalize_query_matrix_output(raw, matrix_input)

        self.assertEqual(len(output.queries), 26)
        self.assertEqual(output.quality_report.status, "pass")
        self.assertEqual(output.queries[0].source_dimension_json["source_type"], "duiba_scenario_library_v4")
        self.assertEqual(output.queries[0].source_dimension_json["journey_stage"], "problem_discovery")
        self.assertEqual(output.queries[17].source_dimension_json["journey_stage"], "purchase_decision")
        self.assertIn("duiba_app_ops_v4", output.queryset_version)
        matrix_counts = Counter(query.matrix_cell_id for query in output.queries)
        self.assertEqual(matrix_counts["problem_discovery:scenario_explore"], 2)
        self.assertEqual(matrix_counts["problem_discovery:category_rec"], 4)
        self.assertEqual(matrix_counts["solution_evaluation:scenario_explore"], 3)
        self.assertEqual(matrix_counts["solution_evaluation:category_rec"], 4)
        self.assertEqual(matrix_counts["solution_evaluation:competitive_comp"], 4)
        self.assertEqual(matrix_counts["purchase_decision:vendor_choice"], 3)
        self.assertEqual(matrix_counts["purchase_decision:internal_justification"], 1)
        self.assertEqual(matrix_counts["purchase_decision:purchase_risk"], 1)
        self.assertEqual(matrix_counts["purchase_decision:commercial_terms"], 1)
        self.assertEqual(matrix_counts["purchase_decision:competitive_comp"], 3)
        self.assertEqual(output.quality_report.coverage["metric_scope_counts"]["core_trend"], 19)
        self.assertAlmostEqual(output.quality_report.coverage["core_weight_sum"], 1.0)
        commercial = next(query for query in output.queries if query.query_pattern == "commercial_terms")
        self.assertEqual(commercial.run_scope, "shadow")
        self.assertEqual(commercial.metric_weight, 0)

    def test_legacy_decision_confirm_is_mapped_to_new_pattern(self) -> None:
        raw = normalize_matrix_queryset(
            {
                "queryset_id": "qs_legacy",
                "queries": [
                    {
                        "query_id": "q_legacy",
                        "query_text": "签了年度合同之后平台服务质量下降怎么办，SLA 和违约条款怎么谈",
                        "query_pattern": "decision_confirm",
                        "topic": "积分商城",
                    }
                ],
            }
        )
        output = normalize_query_matrix_output(raw, build_query_matrix_input(single_topic_brand_config(), run_payload()))

        query = output.queries[0]
        self.assertEqual(query.query_pattern, "commercial_terms")
        self.assertEqual(query.journey_stage, "purchase_decision")
        self.assertEqual(query.metric_scope, "exploratory_coverage")
        self.assertEqual(query.run_scope, "shadow")

    def test_queryset_freeze_is_immutable(self) -> None:
        config = single_topic_brand_config()
        matrix_input = build_query_matrix_input(config, run_payload())
        output = normalize_query_matrix_output(generate_rule_matrix_queryset(brand_config()), matrix_input)

        persist_queryset_snapshot(output, brand_config())

        with self.assertRaisesRegex(RuntimeError, "immutable"):
            persist_queryset_snapshot(output, brand_config())

    def test_query_quality_report_rejects_duplicate_text(self) -> None:
        matrix_input = build_query_matrix_input(brand_config(), run_payload())
        output = normalize_query_matrix_output(generate_rule_matrix_queryset(brand_config()), matrix_input)
        duplicated = [output.queries[0], output.queries[0]]

        report = build_query_quality_report(duplicated, brand_config())

        self.assertEqual(report.status, "fail")
        self.assertIn("Duplicate query_id or query_text detected.", report.errors)

    def test_inspection_result_lineage_is_complete_for_success_and_failure(self) -> None:
        class SuccessClient:
            platform = "DeepSeek"
            model = "deepseek-test"

            async def inspect(self, query: dict, config: dict) -> dict:
                return {
                    "model": self.model,
                    "raw_answer": "XX is recommended.",
                    "parsed": {"mentioned_brands": [], "citations": []},
                    "usage": {},
                }

        class FailureClient:
            platform = "Kimi"
            model = "kimi-test"

            async def inspect(self, query: dict, config: dict) -> dict:
                raise RuntimeError("platform unavailable")

        run = {**run_payload(), "status": "running", "progress": 0}
        runs_store.upsert(run["run_id"], run)
        query = normalize_query_matrix_output(
            generate_rule_matrix_queryset(brand_config()),
            build_query_matrix_input(brand_config(), run),
        ).model_dump()["queries"][0]

        results = asyncio.run(
            _inspect_queries("run_contract", [SuccessClient(), FailureClient()], [query], brand_config(), "qs_contract")
        )

        self.assertEqual({result["status"] for result in results}, {"completed", "failed"})
        for result in results:
            for field in (
                "inspection_result_id",
                "inspection_batch_id",
                "run_id",
                "queryset_id",
                "query_id",
                "platform",
                "model",
                "status",
                "raw_answer",
                "parsed_answer",
                "error_message",
                "started_at",
                "completed_at",
            ):
                self.assertIn(field, result)

    def test_report_lineage_schema_and_overview_contract(self) -> None:
        matrix_input = build_query_matrix_input(brand_config(), run_payload())
        queryset = normalize_query_matrix_output(generate_rule_matrix_queryset(brand_config()), matrix_input).model_dump()
        query = queryset["queries"][0]
        result = {
            "status": "completed",
            "platform": "DeepSeek",
            "model": "deepseek-test",
            "queryset_id": queryset["queryset_id"],
            "query_id": query["query_id"],
            "query_text": query["query_text"],
            "topic": query["topic"],
            "intent_type": query["intent_type"],
            "raw_answer": "XX is recommended.",
            "parsed": {
                "mentioned_brands": [
                    {"name": "杭州XX科技有限公司", "position": 1, "sentiment": "positive"},
                ],
                "citations": [{"domain": "example.com", "is_official": True}],
            },
        }
        run = {**run_payload(), "queryset": queryset, "status": "completed"}
        report = aggregate_report(run, brand_config(), queryset, [result])

        self.assertEqual(report["lineage"]["queryset_version"], "rule_matrix_v1")
        self.assertEqual(report["lineage"]["queryset_source"], "matrix_api_v1")
        self.assertEqual(report["lineage"]["brand_config_snapshot"]["brand_config_id"], "bc_contract")

        schema_path = Path(__file__).resolve().parents[2] / "src" / "schemas" / "report_data.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        assert_required_contract(self, schema, report)

        persist_dashboard_snapshot(run, report)
        overview = get_overview_payload("bc_contract")
        self.assertIsNotNone(overview)
        self.assertIn("queryset", overview)
        self.assertIn("metrics", overview)
        self.assertIn("attribution", overview)
        self.assertEqual(overview["latest_run_id"], "run_contract")

    def test_report_main_metrics_use_core_weighted_samples_only(self) -> None:
        config = single_topic_brand_config()
        matrix_input = build_query_matrix_input(config, run_payload())
        raw = {
            "queryset_id": "qs_weighted",
            "queryset_version": "rule_matrix_v1",
            "queries": [
                {
                    "query_id": "q_core",
                    "query_text": "积分商城有哪些成熟供应商？",
                    "journey_stage": "problem_discovery",
                    "query_pattern": "category_rec",
                    "matrix_cell_id": "problem_discovery:category_rec",
                    "topic": "积分商城",
                    "intent_type": "vendor_recommendation",
                    "related_competitors": ["有赞"],
                },
                {
                    "query_id": "q_explore",
                    "query_text": "积分体系能提升留存吗？",
                    "journey_stage": "problem_discovery",
                    "query_pattern": "scenario_explore",
                    "matrix_cell_id": "problem_discovery:scenario_explore",
                    "topic": "积分商城",
                    "intent_type": "awareness_scenario_explore",
                    "related_competitors": ["有赞"],
                },
            ],
        }
        queryset = normalize_query_matrix_output(raw, matrix_input).model_dump()
        results = [
            {
                "status": "completed",
                "platform": "DeepSeek",
                "model": "deepseek-test",
                "query_id": "q_core",
                "topic": "积分商城",
                "parsed": {
                    "mentioned_brands": [
                        {"name": "杭州XX科技有限公司", "position": 1, "sentiment": "positive"},
                    ],
                    "citations": [],
                },
            },
            {
                "status": "completed",
                "platform": "DeepSeek",
                "model": "deepseek-test",
                "query_id": "q_explore",
                "topic": "积分商城",
                "parsed": {"mentioned_brands": [], "citations": []},
            },
        ]

        report = aggregate_report({**run_payload(), "queryset": queryset}, config, queryset, results)

        self.assertEqual(report["global"]["natural_visibility"], 1.0)
        self.assertEqual(report["audit"]["core_completed_samples"], 1)
        self.assertEqual(report["audit"]["completed_samples"], 2)


if __name__ == "__main__":
    unittest.main()
