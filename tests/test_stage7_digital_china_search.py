from __future__ import annotations

import unittest

from scripts.stage7_digital_china_search import (
    SEARCH_SPECS,
    build_relation_rows,
    collect_search_evidence,
    confuses_digital_china_information,
    filter_relevant_hits,
    generate_stage7_and_stage8,
    infer_status,
    merge_seed_and_search_evidence,
    search_hit_to_evidence,
)


class Stage7DigitalChinaSearchTest(unittest.TestCase):
    def test_filter_relevant_hits_requires_digital_china_target_and_relation_terms(self) -> None:
        hits = [
            {
                "search_tool": "Bocha",
                "query": "神州数码 华为 合作",
                "title": "神州数码与华为发布联合解决方案",
                "url": "https://example.com/huawei",
                "snippet": "双方围绕鲲鹏、昇腾和国产算力生态合作。",
                "publish_date": "2025-01-01",
            },
            {
                "search_tool": "Bocha",
                "query": "神州数码 华为 合作",
                "title": "华为发布新品",
                "url": "https://example.com/no-dc",
                "snippet": "只提到华为，没有神州数码。",
                "publish_date": "2025-01-01",
            },
            {
                "search_tool": "Bocha",
                "query": "神州数码 华为 合作",
                "title": "神州数码渠道大会",
                "url": "https://example.com/no-target",
                "snippet": "只提到神州数码，没有目标公司。",
                "publish_date": "2025-01-01",
            },
        ]

        rows = filter_relevant_hits("华为", ["华为", "Huawei"], hits)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["url"], "https://example.com/huawei")

    def test_filter_relevant_hits_rejects_forums_and_digital_china_information_confusion(self) -> None:
        hits = [
            {
                "search_tool": "Bocha",
                "query": "神州数码 浪潮信息 合作",
                "title": "神州信息与浪潮信息签订战略合作框架协议",
                "url": "https://www.dcits.com/show-269-1605-1.html",
                "snippet": "神州数码信息服务股份有限公司(神州信息)与浪潮信息合作。",
                "publish_date": "2020-01-10",
            },
            {
                "search_tool": "Bocha",
                "query": "神州数码 NVIDIA 合作",
                "title": "英伟达Ai核心受益",
                "url": "https://xueqiu.com/1671490202/245324407",
                "snippet": "神州数码与NVIDIA签署合作。",
                "publish_date": "",
            },
            {
                "search_tool": "Bocha",
                "query": "神州问学 浪潮信息",
                "title": "神州数码联合浪潮信息共推神州问学AI一体机解决方案",
                "url": "https://example.com/inspur",
                "snippet": "神州数码与浪潮信息围绕AI一体机解决方案开展合作。",
                "publish_date": "2025-01-01",
            },
        ]

        rows = filter_relevant_hits("浪潮信息", ["浪潮信息", "Inspur"], hits)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["url"], "https://example.com/inspur")

    def test_search_hit_to_evidence_marks_confirmed_public_relationship(self) -> None:
        hit = {
            "search_tool": "Bocha",
            "query": "神州数码 华为 合作",
            "title": "神州数码与华为发布联合解决方案",
            "url": "https://example.com/huawei",
            "snippet": "神州数码与华为围绕鲲鹏、昇腾、国产算力开展生态合作。",
            "publish_date": "2025-01-01",
        }

        evidence = search_hit_to_evidence("DC-S-001", "华为", hit)

        self.assertEqual(evidence["relationship_status"], "confirmed_public_relationship")
        self.assertEqual(evidence["company_name"], "华为")
        self.assertEqual(evidence["source_type"], "public_search")
        self.assertIn("神州数码与华为", evidence["possible_claim"])
        self.assertEqual(evidence["source_url_or_file"], "https://example.com/huawei")

    def test_build_relation_rows_groups_multiple_evidence_ids_by_company(self) -> None:
        evidence_rows = [
            {
                "evidence_id": "DC-S-001",
                "company_name": "华为",
                "relationship_status": "confirmed_public_relationship",
                "relationship_type": "生态合作/解决方案匹配",
                "possible_claim": "神州数码与华为存在公开生态合作证据。",
                "confidence": "high",
                "source_grade": "A",
            },
            {
                "evidence_id": "DC-S-002",
                "company_name": "华为",
                "relationship_status": "confirmed_public_relationship",
                "relationship_type": "生态合作/解决方案匹配",
                "possible_claim": "神州数码与华为存在公开伙伴关系证据。",
                "confidence": "high",
                "source_grade": "A",
            },
            {
                "evidence_id": "DC-S-003",
                "company_name": "NVIDIA",
                "relationship_status": "potential_fit",
                "relationship_type": "AI算力生态潜在协同",
                "possible_claim": "NVIDIA 与神州数码业务方向存在公开场景匹配。",
                "confidence": "medium-low",
                "source_grade": "B",
            },
        ]

        rows = build_relation_rows(evidence_rows)
        by_company = {row["company_name"]: row for row in rows}

        self.assertEqual(by_company["华为"]["relationship_status"], "confirmed_public_relationship")
        self.assertEqual(by_company["华为"]["evidence_ids"], "DC-S-001;DC-S-002")
        self.assertEqual(by_company["NVIDIA"]["relationship_status"], "potential_fit")
        self.assertEqual(by_company["NVIDIA"]["requires_internal_validation"], "true")

    def test_merge_seed_and_search_evidence_prefers_stronger_search_status(self) -> None:
        seed_rows = [
            {
                "evidence_id": "DC-001",
                "company_name": "华为",
                "relationship_status": "potential_fit",
                "relationship_type": "生态合作/解决方案匹配",
                "possible_claim": "旧证据只说明潜在匹配。",
                "confidence": "medium-low",
                "source_grade": "B",
            }
        ]
        search_rows = [
            {
                "evidence_id": "DC-S-001",
                "company_name": "华为",
                "relationship_status": "confirmed_public_relationship",
                "relationship_type": "生态合作/解决方案匹配",
                "possible_claim": "搜索证据说明公开合作。",
                "confidence": "high",
                "source_grade": "A",
            }
        ]

        rows = build_relation_rows(merge_seed_and_search_evidence(seed_rows, search_rows))

        self.assertEqual(rows[0]["relationship_status"], "confirmed_public_relationship")
        self.assertEqual(rows[0]["evidence_ids"], "DC-001;DC-S-001")

    def test_collect_search_evidence_limit_restricts_specs(self) -> None:
        calls: list[str] = []

        def fake_search(query: str, count: int) -> list[dict[str, str]]:
            calls.append(query)
            return [
                {
                    "search_tool": "Bocha",
                    "query": query,
                    "title": "神州数码与华为签署战略合作协议",
                    "url": "https://example.com/huawei",
                    "snippet": "神州数码与华为签署战略合作协议，联合发布解决方案。",
                    "publish_date": "",
                }
            ]

        rows = collect_search_evidence(
            search_bocha_fn=fake_search,
            search_tavily_fn=fake_search,
            count=1,
            limit=1,
            sleep_seconds=0,
        )

        self.assertEqual(len(calls), 3)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["company_name"], "华为")

    def test_generate_dry_run_builds_without_writing(self) -> None:
        result = generate_stage7_and_stage8(use_search=False, write_outputs=False)

        self.assertGreaterEqual(result["seed_evidence"], 1)
        self.assertGreaterEqual(result["digital_china_relations"], 1)

    def test_search_specs_do_not_treat_scenario_as_company(self) -> None:
        company_names = {spec.company_name for spec in SEARCH_SPECS}

        self.assertNotIn("国产算力", company_names)


class Stage7TightenedInferenceTest(unittest.TestCase):
    """WS3 判定收紧：修复 combined_text query 污染 bug + 三级词表 + 句级共现 + 数字中国语料拒绝。"""

    def test_strong_term_with_same_sentence_cooccurrence_is_confirmed(self) -> None:
        text = "神州数码与华为签署战略合作协议，联合发布解决方案。"
        self.assertEqual(
            infer_status(text, "华为", ("华为", "Huawei")),
            "confirmed_public_relationship",
        )

    def test_weak_term_alone_is_not_confirmed(self) -> None:
        """仅命中弱词'合作'（无强词）不应直升 confirmed（修复 query 污染 bug）。"""
        text = "神州数码与华为合作开展业务。"
        self.assertEqual(
            infer_status(text, "华为", ("华为", "Huawei")),
            "needs_internal_validation",
        )

    def test_strong_term_without_same_sentence_cooccurrence_downgrades(self) -> None:
        """强词命中但神州数码与目标公司不在同一句 -> 降级为 needs_internal_validation。"""
        text = "某公司签署战略合作协议。另一段提到华为的产品。"
        self.assertEqual(
            infer_status(text, "华为", ("华为", "Huawei")),
            "needs_internal_validation",
        )

    def test_query_text_pollution_no_longer_auto_confirms(self) -> None:
        """模拟旧 bug：hit 文本只有 query 残留的'合作'，无实质内容，不应 confirmed。"""
        hit = {
            "title": "某行业报告",
            "snippet": "市场分析",
            "url": "https://example.com/report",
            "query": "神州数码 华为 合作 代理 分销 中标",
        }
        # search_hit_to_evidence 现在用 result_text（不含 query）
        ev = search_hit_to_evidence("DC-S-TEST", "华为", hit, ("华为", "Huawei"))
        self.assertNotEqual(ev["relationship_status"], "confirmed_public_relationship")

    def test_digital_china_policy_corpus_is_rejected(self) -> None:
        """'数字中国建设/峰会'政策语料应被拒绝（与神州数码无关）。"""
        self.assertTrue(
            confuses_digital_china_information("华为", "数字中国建设峰会发布行业发展报告")
        )

    def test_real_digital_china_not_confused_with_policy(self) -> None:
        """含神州数码实体的内容不应被误拒。"""
        self.assertFalse(
            confuses_digital_china_information(
                "华为", "神州数码与华为在数字中国建设方面开展生态合作"
            )
        )


if __name__ == "__main__":
    unittest.main()
