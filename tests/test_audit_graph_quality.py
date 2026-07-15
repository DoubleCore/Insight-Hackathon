from __future__ import annotations

import unittest

from scripts.audit_graph_quality import (
    audit_company_product_relations,
    audit_digital_china_relations,
    audit_leader_evidence,
)


class GraphQualityAuditTest(unittest.TestCase):
    def test_abstract_entity_as_company_is_flagged(self) -> None:
        rows = [
            {
                "company_name": "国产算力",
                "relationship_status": "confirmed_public_relationship",
                "evidence_ids": "DC-S-001",
                "asset_tier": "生态伙伴",
            }
        ]
        evidence = {
            "DC-S-001": {
                "source_grade": "A",
                "source_type": "public_search",
            }
        }

        issues = audit_digital_china_relations(rows, evidence, {"华为"})

        self.assertIn("abstract_entity_as_company", {issue["issue_type"] for issue in issues})

    def test_high_confidence_leader_with_search_only_evidence_is_flagged(self) -> None:
        rows = [
            {
                "company_name": "寒武纪",
                "subsegment_name": "AI/GPU/CPU算力芯片",
                "evidence_ids": "E3-001",
                "confidence": "high",
            }
        ]
        evidence = {
            "E3-001": {
                "source_grade": "B-",
                "source_type": "industry_search",
            }
        }

        issues = audit_leader_evidence(rows, evidence)

        self.assertEqual(issues[0]["issue_type"], "high_confidence_weak_leader_evidence")
        self.assertEqual(issues[0]["priority"], "P0")
        self.assertEqual(issues[0]["severity"], "high")

    def test_potential_digital_china_relation_asset_tier_is_flagged(self) -> None:
        rows = [
            {
                "company_name": "NVIDIA",
                "relationship_status": "potential_fit",
                "evidence_ids": "DC-004",
                "asset_tier": "潜力客户",
            }
        ]
        evidence = {
            "DC-004": {
                "source_grade": "B",
                "source_type": "public_or_existing_evidence",
            }
        }

        issues = audit_digital_china_relations(rows, evidence, {"NVIDIA"})

        self.assertIn("potential_status_asset_tier_risk", {issue["issue_type"] for issue in issues})

    def test_company_product_relation_outside_controlled_product_list_is_flagged(self) -> None:
        rows = [
            {
                "company_name": "测试公司",
                "product_service_name": "随意抽取的产品词",
                "relation_type": "PRODUCES",
                "evidence_ids": "E3-001",
                "requires_internal_validation": "false",
            }
        ]
        evidence = {
            "E3-001": {
                "source_grade": "A",
                "source_type": "official_product_page",
            }
        }

        issues = audit_company_product_relations(rows, evidence, {"AI服务器"})

        self.assertEqual(issues[0]["issue_type"], "unknown_product_service")


if __name__ == "__main__":
    unittest.main()
