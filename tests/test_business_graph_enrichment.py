from __future__ import annotations

import unittest

from scripts.business_graph_enrichment import (
    build_business_opportunities,
    build_competition_relations,
    build_company_product_relations,
    build_digital_china_relations,
    build_l1_l4_rows,
    build_product_services,
)


class BusinessGraphEnrichmentTest(unittest.TestCase):
    def test_build_l1_l4_rows_normalizes_mixed_value_chain_layer(self) -> None:
        leader_rows = [
            {
                "value_chain_layer": "下游/系统需求",
                "major_segment": "终端应用/系统需求",
                "subsegment_name": "AI服务器/云基础设施",
                "subsegment_role": "AI服务器、云计算、数据中心和AI基础设施需求端。",
            }
        ]

        rows = build_l1_l4_rows(leader_rows)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["l1"], "下游")
        self.assertEqual(rows[0]["l2"], "系统需求")
        self.assertEqual(rows[0]["l3"], "终端应用/系统需求")
        self.assertEqual(rows[0]["l4_name"], "AI服务器/云基础设施")
        self.assertEqual(rows[0]["l4_code"], "L4-DOWNSTREAM-AI-INFRA")

    def test_build_l1_l4_rows_adds_downstream_business_segments(self) -> None:
        rows = build_l1_l4_rows([])
        by_name = {row["l4_name"]: row for row in rows}

        self.assertIn("云服务/互联网平台", by_name)
        self.assertIn("通信网络基础设施", by_name)
        self.assertIn("智能终端/PC", by_name)
        self.assertEqual(by_name["云服务/互联网平台"]["l1"], "下游")

    def test_build_product_services_uses_controlled_product_list(self) -> None:
        l1_l4_rows = [
            {
                "l4_code": "L4-DOWNSTREAM-AI-INFRA",
                "l4_name": "AI服务器/云基础设施",
            }
        ]

        rows = build_product_services(l1_l4_rows)
        names = {row["product_service_name"] for row in rows}

        self.assertIn("AI服务器", names)
        self.assertIn("GPU服务器", names)
        self.assertIn("液冷服务器", names)
        self.assertIn("数据中心基础设施服务", names)
        self.assertNotIn("随意抽取的产品词", names)

    def test_build_product_services_covers_added_downstream_segments(self) -> None:
        l1_l4_rows = build_l1_l4_rows([])

        rows = build_product_services(l1_l4_rows)
        names = {row["product_service_name"] for row in rows}

        self.assertIn("公有云服务", names)
        self.assertIn("运营商网络设备", names)
        self.assertIn("PC整机", names)

    def test_build_company_product_relations_requires_evidence_id(self) -> None:
        leader_rows = [
            {
                "subsegment_name": "AI服务器/云基础设施",
                "company_name": "浪潮信息",
                "evidence_ids": "E3-668;E3-669",
                "selection_basis": "AI服务器和数据中心服务器国内代表企业。",
                "confidence": "high",
            }
        ]

        rows = build_company_product_relations(leader_rows)

        self.assertTrue(rows)
        self.assertTrue(all(row["evidence_ids"] for row in rows))
        self.assertIn("PRODUCES", {row["relation_type"] for row in rows})
        self.assertIn("AI服务器", {row["product_service_name"] for row in rows})

    def test_mixed_compute_chip_l4_does_not_default_to_ai_gpu(self) -> None:
        leader_rows = [
            {
                "value_chain_layer": "中游/设计与产品",
                "major_segment": "芯片设计/Fabless",
                "subsegment_name": "AI/GPU/CPU算力芯片",
                "company_name": "澜起科技",
                "evidence_ids": "E3-CXL",
                "selection_basis": "内存接口芯片和CXL相关产品服务AI服务器。",
                "confidence": "medium",
            }
        ]

        rows = build_company_product_relations(leader_rows)

        self.assertNotIn(
            ("澜起科技", "AI GPU", "PRODUCES"),
            {(row["company_name"], row["product_service_name"], row["relation_type"]) for row in rows},
        )

    def test_demand_side_presumed_relations_are_uses_not_procures(self) -> None:
        leader_rows = [
            {
                "value_chain_layer": "下游/系统需求",
                "major_segment": "终端应用/系统需求",
                "subsegment_name": "新能源汽车/汽车电子",
                "company_name": "比亚迪",
                "evidence_ids": "E3-BYD",
                "selection_basis": "新能源汽车和功率半导体/汽车电子需求端代表。",
                "confidence": "high",
            }
        ]

        rows = build_company_product_relations(leader_rows)
        presumed = [row for row in rows if row["derivation"] == "demand_side_presumed"]

        self.assertTrue(presumed)
        self.assertEqual({row["relation_type"] for row in presumed}, {"USES"})
        self.assertEqual({row["requires_internal_validation"] for row in presumed}, {"true"})
        self.assertNotIn("high", {row["confidence"] for row in presumed})

    def test_competition_relations_are_labeled_presumed(self) -> None:
        company_product_rows = [
            {
                "company_name": "甲",
                "product_service_name": "AI服务器",
                "relation_type": "PRODUCES",
                "evidence_ids": "E1",
            },
            {
                "company_name": "乙",
                "product_service_name": "AI服务器",
                "relation_type": "PRODUCES",
                "evidence_ids": "E2",
            },
        ]
        leader_rows = [
            {"company_name": "甲", "leader_level": "国内龙头"},
            {"company_name": "乙", "leader_level": "全球龙头"},
        ]

        rows = build_competition_relations(company_product_rows, leader_rows)

        self.assertEqual(rows[0]["relationship_type"], "推定竞争")
        self.assertEqual(rows[0]["requires_internal_validation"], "true")

    def test_build_company_product_relations_uses_product_service_l4_not_first_company_segment(self) -> None:
        leader_rows = [
            {
                "value_chain_layer": "下游/系统需求",
                "major_segment": "终端应用/系统需求",
                "subsegment_name": "新能源汽车/汽车电子",
                "company_name": "华为",
                "evidence_ids": "E3-AUTO",
                "selection_basis": "智能汽车解决方案、通信和终端生态需求代表。",
                "confidence": "high",
            },
            {
                "value_chain_layer": "下游/系统需求",
                "major_segment": "终端应用/系统需求",
                "subsegment_name": "消费电子/通信设备",
                "company_name": "华为",
                "evidence_ids": "E3-ICT",
                "selection_basis": "通信设备、手机、AI和智能终端生态代表。",
                "confidence": "high",
            },
        ]

        rows = build_company_product_relations(leader_rows)
        by_product = {
            (row["company_name"], row["product_service_name"], row["relation_type"]): row
            for row in rows
        }

        self.assertEqual(
            by_product[("华为", "通信设备", "PRODUCES")]["l4_code"],
            "L4-DOWNSTREAM-ICT-DEVICE",
        )
        self.assertEqual(
            by_product[("华为", "国产算力服务器", "PRODUCES")]["l4_code"],
            "L4-DOWNSTREAM-AI-INFRA",
        )

    def test_build_digital_china_relations_marks_public_and_potential_relationships(self) -> None:
        rows = build_digital_china_relations()
        by_company = {row["company_name"]: row for row in rows}

        self.assertEqual(
            by_company["华为"]["relationship_status"],
            "confirmed_public_relationship",
        )
        self.assertEqual(by_company["NVIDIA"]["relationship_status"], "potential_fit")
        self.assertEqual(by_company["浪潮信息"]["relationship_status"], "needs_internal_validation")
        self.assertEqual(by_company["中兴通讯"]["relationship_status"], "needs_internal_validation")
        self.assertEqual(by_company["联想"]["relationship_status"], "needs_internal_validation")
        self.assertTrue(by_company["华为"]["evidence_ids"])
        self.assertTrue(by_company["NVIDIA"]["requires_internal_validation"])

    def test_build_business_opportunities_connects_company_solution_and_campaign(self) -> None:
        digital_china_relations = [
            {
                "company_name": "华为",
                "relationship_status": "confirmed_public_relationship",
                "relationship_basis": "公开资料显示神州数码围绕华为生态开展解决方案合作。",
                "evidence_ids": "DC-001",
            }
        ]
        company_product_relations = [
            {
                "company_name": "华为",
                "product_service_name": "国产算力服务器",
                "l4_code": "L4-DOWNSTREAM-AI-INFRA",
                "l4_name": "AI服务器/云基础设施",
                "relation_type": "PRODUCES",
                "evidence_ids": "E3-668",
            }
        ]

        opportunities = build_business_opportunities(
            digital_china_relations,
            company_product_relations,
        )

        self.assertEqual(len(opportunities), 1)
        self.assertEqual(opportunities[0]["company_name"], "华为")
        self.assertEqual(opportunities[0]["solution_name"], "国产算力与AI基础设施解决方案")
        self.assertEqual(opportunities[0]["campaign_name"], "AI基础设施重点客户战役")
        self.assertEqual(opportunities[0]["requires_internal_validation"], "true")


if __name__ == "__main__":
    unittest.main()
