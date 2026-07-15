from __future__ import annotations

import pytest


class FakeDriver:
    def __init__(self, records):
        self.records = records
        self.calls: list[tuple[str, dict[str, object]]] = []

    def execute_query(self, query: str, **kwargs):
        self.calls.append((query, kwargs))
        return self.records, None, None

    def close(self) -> None:
        return None


@pytest.mark.asyncio
@pytest.mark.parametrize("view", ["business", "temporal", "governance"])
async def test_graph_views_are_bounded_and_group_scoped(view: str) -> None:
    from app.services.graph import Neo4jGraphService

    driver = FakeDriver(
        [
            {
                "source_id": "n1",
                "source_labels": ["Company"],
                "source_properties": {
                    "name": "NVIDIA",
                    "name_embedding": [0.1, 0.2],
                },
                "edge_id": "r1",
                "edge_type": "LEADER_IN" if view == "business" else "RELATES_TO",
                "edge_properties": {"fact": "NVIDIA 是算力芯片龙头"},
                "target_id": "n2",
                "target_labels": ["Subsegment" if view == "business" else "Entity"],
                "target_properties": {"name": "AI/GPU 算力芯片"},
            }
        ]
    )
    service = Neo4jGraphService(driver, group_id="semiconductor_dc_kg")

    payload = await service.get_view(view, limit=120)

    assert len(payload.nodes) == 2
    assert payload.edges[0].type in {"龙头企业", "事实关系", "龙头"}
    assert "name_embedding" not in payload.nodes[0].properties
    query, parameters = driver.calls[0]
    assert "$limit" in query
    assert parameters["limit"] == 120
    if view != "business":
        assert "$group_id" in query
        assert parameters["group_id"] == "semiconductor_dc_kg"


@pytest.mark.asyncio
async def test_graph_service_rejects_unknown_view_and_invalid_limit() -> None:
    from app.services.graph import Neo4jGraphService

    service = Neo4jGraphService(FakeDriver([]), group_id="semiconductor_dc_kg")
    with pytest.raises(ValueError, match="视图"):
        await service.get_view("unknown", limit=10)
    with pytest.raises(ValueError, match="limit"):
        await service.get_view("business", limit=0)


@pytest.mark.asyncio
async def test_graph_stats_report_original_and_temporal_layers() -> None:
    from app.services.graph import Neo4jGraphService

    driver = FakeDriver(
        [
            {
                "industry_nodes": 1487,
                "industry_edges": 3420,
                "entities": 1417,
                "episodes": 818,
                "facts": 1376,
                "sagas": 5,
                "communities": 0,
            }
        ]
    )

    stats = await Neo4jGraphService(
        driver, group_id="semiconductor_dc_kg"
    ).get_stats()

    assert stats["industry_nodes"] == 1487
    assert stats["facts"] == 1376
    assert driver.calls[0][1]["group_id"] == "semiconductor_dc_kg"
