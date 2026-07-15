from __future__ import annotations

import asyncio


class FakeDriver:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def execute_query(self, query: str, **kwargs):
        self.calls.append((query, kwargs))
        if "DISTINCT s.l2 AS child_name" in query:
            return (
                [
                    {"child_name": "设计与产品", "child_count": 7},
                    {"child_name": "制造支撑", "child_count": 4},
                ],
                None,
                None,
            )
        if "MATCH (s:Subsegment" in query and "包含产品服务" in query:
            return (
                [
                    {
                        "source_id": "taxonomy:l4:上游|设计与产品|芯片设计|AI/GPU 算力芯片",
                        "source_labels": ["Subsegment"],
                        "source_properties": {
                            "name": "AI/GPU 算力芯片",
                            "l1": "上游",
                            "l2": "设计与产品",
                            "l3": "芯片设计",
                            "l4_name": "AI/GPU 算力芯片",
                        },
                        "edge_id": "r-product",
                        "edge_type": "包含产品服务",
                        "edge_properties": {"证据ID": ["E6-001"]},
                        "target_id": "product:AI服务器",
                        "target_labels": ["ProductService"],
                        "target_properties": {"name": "AI服务器"},
                    },
                    {
                        "source_id": "company:NVIDIA",
                        "source_labels": ["Company"],
                        "source_properties": {"name": "NVIDIA"},
                        "edge_id": "r-company",
                        "edge_type": "生产",
                        "edge_properties": {"证据ID": ["E6-002"]},
                        "target_id": "product:AI服务器",
                        "target_labels": ["ProductService"],
                        "target_properties": {"name": "AI服务器"},
                    },
                ],
                None,
                None,
            )
        if "RELATES_TO" in query:
            return (
                [
                    {
                        "source_id": "entity:NVIDIA",
                        "source_labels": ["Entity"],
                        "source_properties": {"name": "NVIDIA"},
                        "edge_id": "fact-1",
                        "edge_type": "RELATES_TO",
                        "edge_properties": {"fact": "NVIDIA 与 TSMC 存在晶圆代工关系。"},
                        "target_id": "entity:TSMC",
                        "target_labels": ["Entity"],
                        "target_properties": {"name": "TSMC"},
                    },
                    {
                        "source_id": "entity:NVIDIA",
                        "source_labels": ["Entity"],
                        "source_properties": {"name": "NVIDIA"},
                        "edge_id": "evidence-edge",
                        "edge_type": "SUPPORTED_BY",
                        "edge_properties": {},
                        "target_id": "evidence:E4-001",
                        "target_labels": ["Evidence"],
                        "target_properties": {"name": "E4-001"},
                    },
                ],
                None,
                None,
            )
        if "digital_china_relationship_status" in query:
            return (
                [
                    {
                        "source_id": "company:浪潮信息",
                        "source_labels": ["Company"],
                        "source_properties": {
                            "name": "浪潮信息",
                            "digital_china_relationship_status": "confirmed_public_relationship",
                            "digital_china_relationship_type": "联合发布AI一体机解决方案",
                            "digital_china_relationship_basis": "神州数码官网新闻显示双方联合发布AI一体机解决方案。",
                            "digital_china_evidence_ids": ["DC-008"],
                            "requires_internal_validation": True,
                        },
                        "edge_id": "digital-china-status:company:浪潮信息",
                        "edge_type": "神州数码关系状态",
                        "edge_properties": {
                            "display_label": "神州数码关系：公开确认",
                            "关系状态": "confirmed_public_relationship",
                            "关系类型": "联合发布AI一体机解决方案",
                            "判断依据": "神州数码官网新闻显示双方联合发布AI一体机解决方案。",
                            "证据ID": ["DC-008"],
                            "是否需要内部验证": True,
                            "requires_internal_validation": True,
                        },
                        "target_id": "company::神州数码",
                        "target_labels": ["DigitalChina", "Company"],
                        "target_properties": {"name": "神州数码"},
                    }
                ],
                None,
                None,
            )
        if "MATCH (anchor)" in query and "Evidence" in query:
            return (
                [
                    {
                        "source_id": "company:NVIDIA",
                        "source_labels": ["Company"],
                        "source_properties": {"name": "NVIDIA"},
                        "edge_id": "company:NVIDIA->evidence:E4-001",
                        "edge_type": "SUPPORTED_BY",
                        "edge_properties": {"evidence_id": "E4-001"},
                        "target_id": "evidence:E4-001",
                        "target_labels": ["Evidence"],
                        "target_properties": {
                            "name": "E4-001",
                            "title": "NVIDIA 与 TSMC 代工资料",
                            "url": "https://example.com/e4-001",
                            "source_grade": "A",
                        },
                    }
                ],
                None,
                None,
            )
        return [], None, None

    def close(self) -> None:
        return None


def test_unified_root_starts_with_three_l1_nodes() -> None:
    from app.services.unified_graph import UnifiedGraphService

    payload = asyncio.run(
        UnifiedGraphService(FakeDriver(), group_id="semiconductor_dc_kg").root()
    )

    assert [node.properties["名称"] for node in payload.nodes] == ["上游", "中游", "下游"]
    assert {node.labels[0] for node in payload.nodes} == {"L1 产业层级"}
    assert {node.properties["level"] for node in payload.nodes} == {0}
    assert payload.edges == []


def test_unified_expand_l1_returns_ordered_l2_children_with_layout() -> None:
    from app.services.unified_graph import UnifiedGraphService

    payload = asyncio.run(
        UnifiedGraphService(FakeDriver(), group_id="semiconductor_dc_kg").expand(
            "taxonomy:l1:上游", branch="hierarchy", limit=20
        )
    )

    assert [node.properties["名称"] for node in payload.nodes] == ["设计与产品", "制造支撑"]
    assert {node.labels[0] for node in payload.nodes} == {"L2 业务域"}
    assert all(node.properties["level"] == 1 for node in payload.nodes)
    assert len(payload.edges) == 2
    assert {edge.type for edge in payload.edges} == {"包含"}


def test_unified_expand_l4_business_links_products_and_companies() -> None:
    from app.services.unified_graph import UnifiedGraphService

    payload = asyncio.run(
        UnifiedGraphService(FakeDriver(), group_id="semiconductor_dc_kg").expand(
            "taxonomy:l4:上游|设计与产品|芯片设计|AI/GPU 算力芯片",
            branch="business",
            limit=20,
        )
    )

    names = {node.properties["名称"] for node in payload.nodes}
    assert {"AI服务器", "NVIDIA"} <= names
    assert {edge.type for edge in payload.edges} == {"包含产品服务", "生产"}
    assert all(node.properties["level"] in {4, 5} for node in payload.nodes)


def test_unified_facts_exclude_evidence_nodes_by_default() -> None:
    from app.services.unified_graph import UnifiedGraphService

    payload = asyncio.run(
        UnifiedGraphService(FakeDriver(), group_id="semiconductor_dc_kg").expand(
            "company:NVIDIA", branch="facts", limit=20
        )
    )

    assert {node.properties["名称"] for node in payload.nodes} == {"TSMC"}
    assert {node.labels[0] for node in payload.nodes} == {"事实实体"}
    assert len(payload.edges) == 1
    assert payload.edges[0].type == "晶圆代工"
    assert payload.edges[0].source == "company:NVIDIA"


def test_unified_evidence_branch_returns_evidence_nodes_with_source_fields() -> None:
    from app.services.unified_graph import UnifiedGraphService

    payload = asyncio.run(
        UnifiedGraphService(FakeDriver(), group_id="semiconductor_dc_kg").expand(
            "company:NVIDIA", branch="evidence", limit=20
        )
    )

    assert {node.labels[0] for node in payload.nodes} == {"证据"}
    assert payload.nodes[0].properties["来源标题"] == "NVIDIA 与 TSMC 代工资料"
    assert payload.nodes[0].properties["来源链接"] == "https://example.com/e4-001"
    assert payload.nodes[0].properties["来源等级"] == "A"
    assert payload.edges[0].type == "证据支持"


def test_unified_digital_china_branch_returns_status_relationship() -> None:
    from app.services.unified_graph import UnifiedGraphService

    payload = asyncio.run(
        UnifiedGraphService(FakeDriver(), group_id="semiconductor_dc_kg").expand(
            "company:浪潮信息", branch="digital_china", limit=20
        )
    )

    assert {node.properties["名称"] for node in payload.nodes} == {"神州数码"}
    assert len(payload.edges) == 1
    assert payload.edges[0].type == "神州数码关系：公开确认"
    assert payload.edges[0].properties["关系状态"] == "confirmed_public_relationship"
    assert payload.edges[0].properties["是否需要内部验证"] is True
