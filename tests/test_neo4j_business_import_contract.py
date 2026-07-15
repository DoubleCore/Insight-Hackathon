from __future__ import annotations

import csv
import unittest

from scripts import import_semiconductor_graph_to_neo4j as importer


class Neo4jBusinessImportContractTest(unittest.TestCase):
    def test_business_graph_is_merged_into_original_industry_graph(self) -> None:
        self.assertIn("ProductService", importer.ALLOWED_LABELS)
        self.assertIn("DigitalChina", importer.ALLOWED_LABELS)
        self.assertNotIn("CustomerAsset", importer.ALLOWED_LABELS)
        self.assertNotIn("Opportunity", importer.ALLOWED_LABELS)
        self.assertNotIn("Solution", importer.ALLOWED_LABELS)
        self.assertNotIn("CampaignPlan", importer.ALLOWED_LABELS)
        self.assertNotIn("MarginImprovement", importer.ALLOWED_LABELS)
        self.assertNotIn("DigitalChinaRelation", importer.ALLOWED_LABELS)

    def test_main_graph_uses_chinese_relationship_types_for_business_enrichment(self) -> None:
        expected_relationships = {
            "包含产品服务",
            "生产",
            "销售",
            "使用",
            "采购",
            "集成",
            "供应给",
            "合作",
            "合资建设",
            "联合研发",
            "生态适配",
            "方案协同",
            "公开关系",
            "推定竞争",
            "渠道代理",
            "投资控股",
        }

        self.assertTrue(expected_relationships.issubset(importer.BUSINESS_RELATIONSHIP_TYPES))
        self.assertNotIn("具有客户资产状态", importer.BUSINESS_RELATIONSHIP_TYPES)
        self.assertNotIn("归属于", importer.BUSINESS_RELATIONSHIP_TYPES)
        self.assertNotIn("转化为", importer.BUSINESS_RELATIONSHIP_TYPES)
        self.assertNotIn("采用方案", importer.BUSINESS_RELATIONSHIP_TYPES)
        self.assertNotIn("纳入战役", importer.BUSINESS_RELATIONSHIP_TYPES)
        self.assertNotIn("涉及产品服务", importer.BUSINESS_RELATIONSHIP_TYPES)
        self.assertNotIn("与神州数码关系", importer.BUSINESS_RELATIONSHIP_TYPES)
        self.assertNotIn("潜在匹配", importer.BUSINESS_RELATIONSHIP_TYPES)
        self.assertNotIn("竞争", importer.BUSINESS_RELATIONSHIP_TYPES)
        self.assertNotIn("需内部验证", importer.BUSINESS_RELATIONSHIP_TYPES)
        self.assertNotIn("暂无公开证据", importer.BUSINESS_RELATIONSHIP_TYPES)

    def test_digital_china_status_maps_to_real_relationship_type(self) -> None:
        self.assertEqual(
            importer.digital_china_relationship_type(
                "confirmed_public_relationship",
                "鲲鹏/昇腾生态适配与国产算力方案",
            ),
            "生态适配",
        )
        self.assertEqual(
            importer.digital_china_relationship_type(
                "confirmed_public_relationship",
                "AI一体机联合发布与方案协同",
            ),
            "方案协同",
        )
        self.assertEqual(
            importer.digital_china_relationship_type("confirmed_public_relationship", ""),
            "公开关系",
        )
        self.assertIsNone(importer.digital_china_relationship_type("potential_fit"))
        self.assertIsNone(importer.digital_china_relationship_type("needs_internal_validation"))
        self.assertIsNone(importer.digital_china_relationship_type("no_public_evidence"))

    def test_all_stage4_relationship_types_are_mapped(self) -> None:
        with importer.RELATIONSHIPS_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))

        unmapped = sorted(
            {
                row["relationship_type"]
                for row in rows
                if not importer.COMPANY_RELATIONSHIP_TYPE_MAP.get(row["relationship_type"])
            }
        )

        self.assertEqual(unmapped, [])

    def test_digital_china_status_is_stored_as_company_properties_not_edges(self) -> None:
        row = {
            "relationship_status": "potential_fit",
            "relationship_type": "AI算力生态潜在协同",
            "relationship_basis": "公开资料只能说明场景匹配，不能证明公司关系。",
            "evidence_ids": "DC-004",
            "confidence": "medium",
            "requires_internal_validation": "true",
            "limitations": "不证明内部CRM客户关系。",
        }

        props = importer.digital_china_status_properties(row)

        self.assertEqual(props["神州数码关系状态"], "potential_fit")
        self.assertEqual(props["神州数码关系类型"], "AI算力生态潜在协同")
        self.assertEqual(props["神州数码关系证据ID"], ["DC-004"])
        self.assertTrue(props["是否需要内部验证"])

    def test_digital_china_relations_only_keep_known_companies(self) -> None:
        rows = [
            {"company_name": "NVIDIA"},
            {"company_name": "国产算力"},
            {"company_name": "华为"},
        ]

        filtered = importer.filter_digital_china_company_relations(rows, {"NVIDIA", "华为"})

        self.assertEqual([row["company_name"] for row in filtered], ["NVIDIA", "华为"])

    def test_evidence_quality_marks_search_only_weak_claims(self) -> None:
        evidence = {
            "E1": {"source_grade": "B-", "source_type": "industry_search"},
            "E2": {"source_grade": "B-", "source_type": "industry_search"},
        }

        props = importer.evidence_quality_props(["E1", "E2"], evidence)

        self.assertEqual(props["最高证据等级"], "B-")
        self.assertEqual(props["证据强度"], "弱")
        self.assertTrue(props["是否仅搜索结果支撑"])
        self.assertTrue(props["是否弱证据支撑"])

    def test_evidence_quality_marks_official_evidence_as_strong(self) -> None:
        evidence = {
            "E1": {"source_grade": "B-", "source_type": "industry_search"},
            "E2": {"source_grade": "A", "source_type": "official_disclosure"},
        }

        props = importer.evidence_quality_props(["E1", "E2"], evidence)

        self.assertEqual(props["最高证据等级"], "A")
        self.assertEqual(props["证据强度"], "强")
        self.assertFalse(props["是否仅搜索结果支撑"])
        self.assertFalse(props["是否弱证据支撑"])

    def test_business_graph_input_paths_are_defined(self) -> None:
        self.assertEqual(importer.PRODUCT_SERVICES_CSV.name, "stage5_product_services.csv")
        self.assertEqual(
            importer.COMPANY_PRODUCT_RELATIONS_CSV.name,
            "stage6_company_product_relations.csv",
        )
        self.assertEqual(
            importer.DIGITAL_CHINA_RELATIONS_CSV.name,
            "stage7_digital_china_relations.csv",
        )


    def test_customer_asset_tier_enum_is_well_defined(self) -> None:
        from scripts import business_graph_enrichment as enrichment
        self.assertEqual(set(enrichment.ASSET_TIERS), {"存量客户", "生态伙伴", "潜力客户", "待验证"})

    def test_assign_asset_tier_classifies_relations(self) -> None:
        from scripts import business_graph_enrichment as enrichment
        self.assertEqual(
            enrichment.assign_asset_tier("confirmed_public_relationship", "medium"),
            "潜力客户",
        )
        self.assertEqual(
            enrichment.assign_asset_tier(
                "confirmed_public_relationship", "high",
                relationship_type="生态合作", relationship_basis="签署分销协议",
                evidence_grade="A",
            ),
            "生态伙伴",
        )
        self.assertEqual(
            enrichment.assign_asset_tier("potential_fit", "medium-low"),
            "待验证",
        )
        self.assertEqual(
            enrichment.assign_asset_tier("potential_fit", "medium"),
            "待验证",
        )

    def test_opportunities_only_for_qualified_tiers(self) -> None:
        """商机只为 潜力客户/生态伙伴/存量客户 生成，待验证不生成。"""
        from scripts import business_graph_enrichment as enrichment
        relations = [
            {"company_name": "甲", "relationship_status": "confirmed_public_relationship",
             "relationship_type": "", "relationship_basis": "", "evidence_ids": "",
             "confidence": "medium", "requires_internal_validation": "true", "limitations": ""},
            {"company_name": "乙", "relationship_status": "potential_fit",
             "relationship_type": "", "relationship_basis": "", "evidence_ids": "",
             "confidence": "medium-low", "requires_internal_validation": "true", "limitations": ""},
            {"company_name": "丙", "relationship_status": "potential_fit",
             "relationship_type": "", "relationship_basis": "", "evidence_ids": "",
             "confidence": "medium", "requires_internal_validation": "true", "limitations": ""},
        ]
        relations = enrichment.enrich_relations_with_tier(relations, [])
        self.assertEqual(relations[0]["asset_tier"], "潜力客户")
        self.assertEqual(relations[1]["asset_tier"], "待验证")
        self.assertEqual(relations[2]["asset_tier"], "待验证")
        products = [
            {"company_name": "甲", "product_service_name": "AI服务器", "l4_code": "x", "l4_name": "x",
             "relation_type": "PRODUCES", "basis": "", "evidence_ids": "", "confidence": "medium",
             "requires_internal_validation": "false"},
            {"company_name": "乙", "product_service_name": "AI服务器", "l4_code": "x", "l4_name": "x",
             "relation_type": "PRODUCES", "basis": "", "evidence_ids": "", "confidence": "medium",
             "requires_internal_validation": "false"},
            {"company_name": "丙", "product_service_name": "AI服务器", "l4_code": "x", "l4_name": "x",
             "relation_type": "PRODUCES", "basis": "", "evidence_ids": "", "confidence": "medium",
             "requires_internal_validation": "false"},
        ]
        opps = enrichment.build_business_opportunities(relations, products)
        companies = {o["company_name"] for o in opps}
        self.assertIn("甲", companies)
        self.assertNotIn("乙", companies)
        self.assertNotIn("丙", companies)


if __name__ == "__main__":
    unittest.main()
