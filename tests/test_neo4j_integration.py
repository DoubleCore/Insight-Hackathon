# -*- coding: utf-8 -*-
"""Neo4j 导入集成冒烟测试。

需要本地 Neo4j 运行。通过环境变量 NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD 配置，
未设置时自动跳过（不影响普通 pytest 运行）。

用法：
  NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=password \
      python -m pytest tests/test_neo4j_integration.py -q
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

SKIP = not NEO4J_URI


@unittest.skipIf(SKIP, "未设置 NEO4J_URI，跳过 Neo4j 集成测试")
class Neo4jIntegrationSmokeTest(unittest.TestCase):
    """导入完整图后核对关键计数与链路连通性。

    依赖 scripts/import_semiconductor_graph_to_neo4j.py 的 main() 全量导入。
    """

    @classmethod
    def setUpClass(cls) -> None:
        from neo4j import GraphDatabase
        import import_semiconductor_graph_to_neo4j as importer

        # 全量重导（清空重建，幂等）
        sys.argv = [
            "import_semiconductor_graph_to_neo4j.py",
            "--skip-graphiti-init",
        ]
        importer.main()
        cls.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls.driver.close()
        except Exception:  # noqa: BLE001
            pass

    def _count(self, cypher: str) -> int:
        with self.driver.session() as s:
            return s.run(cypher).single()[0]

    def test_inferred_business_conversion_nodes_are_not_in_main_graph(self) -> None:
        for label in ("CustomerAsset", "Opportunity", "Solution", "CampaignPlan"):
            n = self._count(f"MATCH (n:{label}) RETURN count(n)")
            self.assertEqual(n, 0, f"{label} 不应导入当前 Neo4j 主图")

    def test_competition_edges_exist(self) -> None:
        n = self._count("MATCH ()-[r:推定竞争]->() RETURN count(r)")
        self.assertGreater(n, 0, "推定竞争边应为正")

    def test_presumed_demand_side_use_edges_exist(self) -> None:
        n = self._count(
            "MATCH ()-[r:使用]->() WHERE r.derivation = 'demand_side_presumed' RETURN count(r)"
        )
        self.assertGreater(n, 0, "需求端使用/需求关联边应为正")

    def test_all_l4_have_products(self) -> None:
        n = self._count(
            "MATCH (s:Subsegment) WHERE NOT (s)-[:包含产品服务]->() RETURN count(s)"
        )
        self.assertEqual(n, 0, "所有 L4 环节应都挂载了产品/服务")

    def test_no_orphan_stage7_evidence(self) -> None:
        n = self._count(
            "MATCH (e:Evidence) WHERE e.stage = 'stage7' "
            "AND NOT ( ()-[:SUPPORTED_BY]->(e) ) RETURN count(e)"
        )
        self.assertEqual(n, 0, "stage7 证据不应为孤儿（应有 SUPPORTED_BY 边）")

    def test_main_graph_path_exists(self) -> None:
        """当前主图链路：L4 -> 产品/服务 -> 企业 -> 神州数码关系状态。"""
        n = self._count(
            "MATCH p=(l4:Subsegment)-[:包含产品服务]->(:ProductService)"
            "<-[:生产|销售|使用|采购|集成]-(c:Company)"
            " WHERE c.`神州数码关系状态` IS NOT NULL "
            "RETURN count(p)"
        )
        self.assertGreater(n, 0, "应存在至少一条主图贯通路径")

    def test_only_confirmed_digital_china_relations_have_cooperation_edges(self) -> None:
        n = self._count(
            "MATCH (c:Company)-[:生态适配|方案协同|公开关系]->(:Company {名称:'神州数码'}) "
            "WHERE c.`神州数码关系状态` <> 'confirmed_public_relationship' "
            "RETURN count(c)"
        )
        self.assertEqual(n, 0, "非 confirmed_public_relationship 不应画成公开关系事实边")


if __name__ == "__main__":
    unittest.main()
