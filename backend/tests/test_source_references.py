from service.aggregator import aggregate_report


def _brand_config() -> dict:
    return {
        "brand_config_id": "bc_test",
        "entity_id": "entity_test",
        "entity_name": "兑吧",
        "entity_aliases": ["Duiba"],
        "owned_domains": ["duiba.com.cn"],
        "topics": [{"topic_name": "积分商城", "business_line": "积分商城", "priority": 1}],
        "competitors": [{"name": "有赞", "aliases": [], "owned_domains": ["youzan.com"]}],
    }


def _run() -> dict:
    return {
        "inspection_batch_id": "batch_test",
        "queryset_strategy": "rule_matrix_v1",
        "queryset_source": "matrix_api_v1",
        "queryset_policy": "reuse_latest",
        "inspection_mode": "multi_platform_live_v1",
        "platforms_requested": ["DeepSeek"],
    }


def _queryset() -> dict:
    return {
        "queryset_id": "qs_test",
        "queryset_version": "rule_matrix_v1",
        "queries": [{"query_id": "q_001", "query_text": "积分商城工具有哪些？"}],
    }


def _result(index: int, url: str, quoted_text: str) -> dict:
    return {
        "inspection_id": f"insp_{index:03d}",
        "status": "completed",
        "platform": "DeepSeek",
        "model": "deepseek-chat",
        "query_id": f"q_{index:03d}",
        "query_text": "金融场景积分商城管理工具有哪些？",
        "query_pattern": "supplier_selection",
        "query_layer": "core_anchor",
        "topic": "积分商城",
        "intent_type": "comparison",
        "raw_answer": f"引用 {url} 说明 {quoted_text}",
        "parsed": {
            "answer": f"引用 {url} 说明 {quoted_text}",
            "mentioned_brands": [
                {
                    "name": "兑吧",
                    "position": 1,
                    "sentiment": "neutral",
                    "mention_context": "standard_listing",
                }
            ],
            "citations": [
                {
                    "url": url,
                    "domain": "example.com",
                    "title": "Example case",
                    "is_official": False,
                    "quoted_text": quoted_text,
                }
            ],
        },
    }


def test_aggregate_report_exposes_top_url_source_references():
    results = [
        _result(1, "https://www.example.com/a", "A 引用 1"),
        _result(2, "https://example.com/a/", "A 引用 2"),
        _result(3, "https://example.com/a#fragment", "A 引用 3"),
        _result(4, "https://example.com/b", "B 引用 1"),
        _result(5, "https://example.com/b", "B 引用 2"),
        _result(6, "https://example.com/c", "C 引用"),
        _result(7, "https://example.com/d", "D 引用"),
        _result(8, "https://example.com/e", "E 引用"),
        _result(9, "https://example.com/f", "F 引用"),
        _result(10, "https://example.com/g", "G 引用"),
    ]

    report = aggregate_report(_run(), _brand_config(), _queryset(), results)

    references = report["source_references"]
    assert len(references) == 6
    assert references[0]["url"] == "https://example.com/a"
    assert references[0]["citation_count"] == 3
    assert references[1]["url"] == "https://example.com/b"
    assert references[1]["citation_count"] == 2
    assert references[0]["references"][0]["inspection_id"] == "insp_001"
    assert references[0]["references"][0]["quoted_text"] == "A 引用 1"


def test_aggregate_report_resolves_source_ownership_from_owned_domains():
    results = [
        _result(1, "https://www.duiba.com.cn/case", "兑吧官网引用"),
        _result(2, "https://www.youzan.com/case", "有赞官网引用"),
        _result(3, "https://www.zhihu.com/question/1", "知乎引用"),
    ]
    results[0]["parsed"]["citations"][0]["domain"] = "www.duiba.com.cn"
    results[1]["parsed"]["citations"][0]["domain"] = "www.youzan.com"
    results[2]["parsed"]["citations"][0]["domain"] = "www.zhihu.com"
    for result in results:
        result["parsed"]["citations"][0]["is_official"] = True

    report = aggregate_report(_run(), _brand_config(), _queryset(), results)
    by_domain = {row["domain"]: row for row in report["sources"]}

    assert by_domain["duiba.com.cn"]["ownership"] == "brand_owned"
    assert by_domain["duiba.com.cn"]["type"] == "品牌自有"
    assert by_domain["youzan.com"]["ownership"] == "competitor_owned"
    assert by_domain["youzan.com"]["type"] == "竞品自有"
    assert by_domain["zhihu.com"]["ownership"] == "third_party"
    assert by_domain["zhihu.com"]["source_type"] == "ugc_community"
    assert report["global"]["own_citations"] == 1
