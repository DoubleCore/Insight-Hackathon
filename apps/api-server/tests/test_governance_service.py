from __future__ import annotations

from datetime import UTC, datetime

import pytest
from neo4j.time import DateTime as Neo4jDateTime


class FakeDriver:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def execute_query(self, query: str, **parameters):
        self.calls.append((query, parameters))
        if "RETURN s.uuid AS uuid" in query and "episode_count" in query:
            return (
                [
                    {
                        "uuid": "saga-1",
                        "name": "AI 算力产业链",
                        "summary": "",
                        "episode_count": 3,
                        "last_summarized_at": Neo4jDateTime(2026, 7, 14, 20, 0, 0),
                        "last_summarized_episode_valid_at": Neo4jDateTime(2026, 7, 10, 0, 0, 0),
                    }
                ],
                None,
                None,
            )
        if "RETURN s.uuid AS uuid" in query and "max_valid_at" in query:
            return (
                [
                    {
                        "uuid": "saga-1",
                        "name": "AI 算力产业链",
                        "summary": "",
                        "episode_count": 3,
                        "max_valid_at": datetime(2026, 7, 10, tzinfo=UTC),
                    }
                ],
                None,
                None,
            )
        if "RETURN e.content AS content" in query:
            skip = int(parameters["skip"])
            pages = {
                0: [
                    {"content": "NVIDIA 生产 GPU。", "valid_at": datetime(2026, 7, 8, tzinfo=UTC)},
                    {"content": "TSMC 为 NVIDIA 提供晶圆代工。", "valid_at": datetime(2026, 7, 9, tzinfo=UTC)},
                ],
                2: [
                    {"content": "浪潮信息集成 AI 服务器。", "valid_at": datetime(2026, 7, 10, tzinfo=UTC)},
                ],
            }
            return pages.get(skip, []), None, None
        if "SET s.summary = $summary" in query:
            return [{"updated": 1}], None, None
        if "DETACH DELETE c" in query:
            return [], None, None
        raise AssertionError(f"未处理的查询：{query}")

    async def close(self) -> None:
        return None


class FakeLlm:
    def __init__(self) -> None:
        self.calls = 0

    async def generate_response(self, *_args, **_kwargs):
        self.calls += 1
        return {"summary": f"摘要-{self.calls}"}


class InspectingLlm:
    async def generate_response(self, messages, *, response_model, **_kwargs):
        assert response_model is None
        assert '{"summary":"实际摘要内容"}' in messages[-1].content
        assert "不要返回 JSON Schema" in messages[-1].content
        return {"summary": "有效摘要"}


class FakeCommunityNode:
    def __init__(self, uuid: str, group_id: str) -> None:
        self.uuid = uuid
        self.group_id = group_id
        self.embedded = False
        self.saved = False

    async def generate_name_embedding(self, _embedder) -> None:
        self.embedded = True

    async def save(self, _driver) -> None:
        self.saved = True


class FakeCommunityEdge:
    def __init__(self, group_id: str) -> None:
        self.uuid = "membership-1"
        self.source_node_uuid = "community-1"
        self.target_node_uuid = "entity-1"
        self.group_id = group_id
        self.created_at = datetime(2026, 7, 15, tzinfo=UTC)
        self.saved = False

    async def save(self, _driver) -> None:
        self.saved = True


@pytest.mark.asyncio
async def test_saga_listing_and_map_reduce_summary_are_group_scoped() -> None:
    from app.services.governance import GovernanceService

    driver = FakeDriver()
    llm = FakeLlm()
    service = GovernanceService(
        driver,
        llm_client=llm,
        embedder=object(),
        group_id="semiconductor_dc_kg",
        saga_page_size=2,
    )

    sagas = await service.list_sagas()
    result = await service.summarize_saga("saga-1")

    assert sagas[0]["episode_count"] == 3
    assert type(sagas[0]["last_summarized_at"]) is datetime
    assert type(sagas[0]["last_summarized_episode_valid_at"]) is datetime
    assert result["summary"] == "摘要-3"
    assert result["episode_count"] == 3
    assert result["pages"] == 2
    assert llm.calls == 3
    assert all(
        parameters.get("group_id") == "semiconductor_dc_kg"
        for query, parameters in driver.calls
        if "Saga" in query
    )
    update_query, update_parameters = next(
        call for call in driver.calls if "SET s.summary = $summary" in call[0]
    )
    assert "group_id: $group_id" in update_query
    assert update_parameters["saga_id"] == "saga-1"


@pytest.mark.asyncio
async def test_saga_summary_uses_json_object_instruction_without_schema() -> None:
    from app.services.governance import GovernanceService

    service = GovernanceService(
        FakeDriver(),
        llm_client=InspectingLlm(),
        embedder=object(),
        group_id="semiconductor_dc_kg",
    )

    summary = await service._summarize("神州数码公开关系", ["公开关系事实"])

    assert summary == "有效摘要"


@pytest.mark.asyncio
async def test_community_rebuild_deletes_only_current_group() -> None:
    from app.services.governance import GovernanceService

    driver = FakeDriver()
    node = FakeCommunityNode("community-1", "semiconductor_dc_kg")
    edge = FakeCommunityEdge("semiconductor_dc_kg")

    async def build_communities(_driver, _llm, group_ids):
        assert group_ids == ["semiconductor_dc_kg"]
        return [node], [edge]

    service = GovernanceService(
        driver,
        llm_client=FakeLlm(),
        embedder=object(),
        group_id="semiconductor_dc_kg",
        community_builder=build_communities,
    )

    result = await service.rebuild_communities()

    replace_query, parameters = next(
        call for call in driver.calls if "DETACH DELETE c" in call[0]
    )
    assert "Community {group_id: $group_id}" in replace_query
    assert "UNWIND $communities" in replace_query
    assert "UNWIND $memberships" in replace_query
    assert parameters["group_id"] == "semiconductor_dc_kg"
    assert parameters["communities"][0]["uuid"] == "community-1"
    assert parameters["memberships"][0]["group_id"] == "semiconductor_dc_kg"
    assert "MATCH (c:Community)" not in replace_query
    assert node.embedded
    assert not node.saved and not edge.saved
    assert result == {"community_count": 1, "membership_count": 1}


@pytest.mark.asyncio
async def test_community_rebuild_rejects_cross_group_output_before_delete() -> None:
    from app.services.governance import GovernanceService

    driver = FakeDriver()

    async def build_communities(_driver, _llm, _group_ids):
        return [FakeCommunityNode("foreign", "another_group")], []

    service = GovernanceService(
        driver,
        llm_client=FakeLlm(),
        embedder=object(),
        group_id="semiconductor_dc_kg",
        community_builder=build_communities,
    )

    with pytest.raises(ValueError, match="分组"):
        await service.rebuild_communities()

    assert not any("DETACH DELETE c" in query for query, _ in driver.calls)


def test_governance_service_hard_locks_business_group() -> None:
    from app.services.governance import GovernanceService

    with pytest.raises(ValueError, match="semiconductor_dc_kg"):
        GovernanceService(
            FakeDriver(),
            llm_client=FakeLlm(),
            embedder=object(),
            group_id="another_group",
        )


def test_governance_factory_injects_configured_cross_encoder(monkeypatch) -> None:
    import graphiti_core

    from app.config import Settings
    from app.services.governance import GovernanceService
    from app.services.retrieval import SiliconFlowReranker

    captured: dict[str, object] = {}

    class FakeGraphiti:
        driver = object()

        def __init__(self, *_args, **kwargs) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(graphiti_core, "Graphiti", FakeGraphiti)

    service = GovernanceService.from_settings(
        Settings(siliconflow_api_key="test-key", session_secret="test-secret")
    )

    assert isinstance(captured["cross_encoder"], SiliconFlowReranker)
    assert captured["cross_encoder"].model == "BAAI/bge-reranker-v2-m3"
    assert service._owned_graphiti is not None


@pytest.mark.asyncio
async def test_bounded_community_builder_excludes_isolates_and_summarizes_once_per_group() -> None:
    from app.services.governance import build_bounded_communities

    class ProjectionDriver:
        async def execute_query(self, query: str, **parameters):
            assert "RELATES_TO" in query
            assert parameters["group_id"] == "semiconductor_dc_kg"
            return (
                [
                    {"uuid": "a", "name": "NVIDIA", "summary": "GPU", "neighbors": ["b", "c"]},
                    {"uuid": "b", "name": "TSMC", "summary": "晶圆代工", "neighbors": ["a", "c"]},
                    {"uuid": "c", "name": "CoWoS", "summary": "先进封装", "neighbors": ["a", "b"]},
                    {"uuid": "d", "name": "ASML", "summary": "光刻机", "neighbors": ["e"]},
                    {"uuid": "e", "name": "光刻", "summary": "制造设备", "neighbors": ["d"]},
                ],
                None,
                None,
            )

    class CommunityLlm:
        def __init__(self) -> None:
            self.calls = 0

        async def generate_response(self, *_args, **_kwargs):
            self.calls += 1
            return {"name": f"社区-{self.calls}", "summary": f"摘要-{self.calls}"}

    llm = CommunityLlm()
    nodes, edges = await build_bounded_communities(
        ProjectionDriver(), llm, ["semiconductor_dc_kg"]
    )

    assert len(nodes) == 2
    assert len(edges) == 5
    assert llm.calls == 2
    assert {node.name for node in nodes} == {"社区-1", "社区-2"}
    assert {edge.target_node_uuid for edge in edges} == {"a", "b", "c", "d", "e"}
