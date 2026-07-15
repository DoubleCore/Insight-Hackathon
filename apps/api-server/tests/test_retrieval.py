from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest


@pytest.mark.asyncio
async def test_graphiti_cross_encoder_adapter_restores_input_score_order() -> None:
    from app.services.retrieval import GraphitiCrossEncoderAdapter

    class TupleReranker:
        async def rank(self, query: str, passages: list[str]):
            assert query == "查询"
            assert passages == ["段落 A", "段落 B", "重复", "重复"]
            return [
                ("段落 B", 0.8),
                ("重复", 0.6),
                ("段落 A", 0.2),
                ("重复", 0.1),
            ]

    scores = await GraphitiCrossEncoderAdapter(TupleReranker()).rank(
        "查询", ["段落 A", "段落 B", "重复", "重复"]
    )

    assert scores == [0.2, 0.8, 0.6, 0.1]


@pytest.mark.asyncio
async def test_siliconflow_reranker_restores_scores_by_document_index() -> None:
    from app.services.retrieval import SiliconFlowReranker
    from graphiti_core.cross_encoder.client import CrossEncoderClient

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {
                "results": [
                    {"index": 1, "relevance_score": 0.92},
                    {"index": 0, "relevance_score": 0.31},
                ]
            }

    class FakeClient:
        def __init__(self) -> None:
            self.payload: dict[str, Any] = {}
            self.closed = False

        async def post(self, path: str, *, json: dict[str, Any]):
            assert path == "/rerank"
            self.payload = json
            return FakeResponse()

        async def aclose(self) -> None:
            self.closed = True

    client = FakeClient()
    reranker = SiliconFlowReranker(
        api_key="test-key",
        base_url="https://api.siliconflow.cn/v1",
        model="BAAI/bge-reranker-v2-m3",
        client=client,
    )

    ranked = await reranker.rank("NVIDIA TSMC", ["晶圆代工", "无关资料"])
    await reranker.close()

    assert isinstance(reranker, CrossEncoderClient)
    assert ranked == [("无关资料", 0.92), ("晶圆代工", 0.31)]
    assert client.payload == {
        "model": "BAAI/bge-reranker-v2-m3",
        "query": "NVIDIA TSMC",
        "documents": ["晶圆代工", "无关资料"],
        "top_n": 2,
        "return_documents": False,
    }
    assert client.closed


def _method_values(config: Any) -> set[str]:
    values: set[str] = set()
    for name in ("edge_config", "node_config", "episode_config", "community_config"):
        section = getattr(config, name, None)
        if section is not None:
            values.update(method.value for method in section.search_methods)
    return values


def _edge(uuid: str, fact: str, score: float = 1.0, **attributes: Any) -> Any:
    return SimpleNamespace(
        uuid=uuid,
        name="SUPPLIES",
        fact=fact,
        source_node_uuid="source-1",
        target_node_uuid="target-1",
        valid_at=None,
        invalid_at=None,
        reference_time=None,
        attributes=attributes,
        score=score,
    )


def _node(uuid: str, name: str) -> Any:
    return SimpleNamespace(uuid=uuid, name=name, summary=f"{name} background", attributes={})


def _results(
    *,
    edges: list[Any] | None = None,
    nodes: list[Any] | None = None,
    episodes: list[Any] | None = None,
    communities: list[Any] | None = None,
) -> Any:
    edges = edges or []
    nodes = nodes or []
    episodes = episodes or []
    communities = communities or []
    return SimpleNamespace(
        edges=edges,
        edge_reranker_scores=[getattr(item, "score", 1.0) for item in edges],
        nodes=nodes,
        node_reranker_scores=[1.0 - index * 0.01 for index, _ in enumerate(nodes)],
        episodes=episodes,
        episode_reranker_scores=[1.0 for _ in episodes],
        communities=communities,
        community_reranker_scores=[1.0 for _ in communities],
    )


class FakeAdvancedSearch:
    def __init__(self, responses: dict[str, Any], fail: set[str] | None = None) -> None:
        self.responses = responses
        self.fail = fail or set()
        self.calls: list[dict[str, Any]] = []
        self.search_calls = 0

    async def search(self, *_args: Any, **_kwargs: Any) -> Any:
        self.search_calls += 1
        raise AssertionError("DeepSearchService must not call graphiti.search()")

    async def search_(self, **kwargs: Any) -> Any:
        methods = _method_values(kwargs["config"])
        if "breadth_first_search" in methods:
            algorithm = "bfs"
        elif methods == {"cosine_similarity"}:
            algorithm = "vector"
        else:
            algorithm = "bm25"
        self.calls.append({"algorithm": algorithm, **kwargs})
        if algorithm in self.fail:
            raise RuntimeError(f"{algorithm} unavailable")
        response = self.responses.get(algorithm, _results())
        return response() if callable(response) else response


class FakeLexicalSearch:
    def __init__(self, response: list[Any] | None = None, fail: bool = False) -> None:
        self.response = response or []
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    async def search_(self, query: str, limit: int) -> list[Any]:
        self.calls.append({"query": query, "limit": limit})
        if self.fail:
            raise RuntimeError("neo4j unavailable")
        return self.response


class FakeCrossEncoder:
    def __init__(self, scores: list[float] | None = None, fail: bool = False) -> None:
        self.scores = scores
        self.fail = fail
        self.calls: list[tuple[str, list[str]]] = []

    def rank(self, query: str, passages: list[str]) -> list[float]:
        self.calls.append((query, passages))
        if self.fail:
            raise RuntimeError("reranker timeout")
        if self.scores is not None:
            return self.scores
        return [float(index) for index in range(len(passages))]


def test_deep_search_uses_four_advanced_slices_and_bfs_entity_origins() -> None:
    from app.services.retrieval import DeepSearchService

    episode = SimpleNamespace(
        uuid="episode-1",
        name="filing",
        content="official filing content",
        valid_at=None,
        episode_metadata={"evidence_ids": ["E-2"]},
    )
    community = SimpleNamespace(
        uuid="community-1", name="AI chips", summary="AI chip community"
    )
    advanced = FakeAdvancedSearch(
        {
            "vector": _results(
                edges=[_edge("edge-1", "A supplies B", evidence_ids="E-1")],
                nodes=[_node("entity-vector", "Vector Entity")],
                communities=[community],
            ),
            "bm25": _results(
                edges=[_edge("edge-1", "A supplies B", evidence_ids=["E-1"])],
                nodes=[_node("entity-bm25", "BM25 Entity")],
                episodes=[episode],
            ),
            "bfs": _results(edges=[_edge("edge-bfs", "B supplies C")]),
        }
    )
    lexical = FakeLexicalSearch(
        [
            {
                "uuid": "edge-lexical",
                "name": "PARTNER_OF",
                "fact": "C partners D",
                "source": "C",
                "target": "D",
                "score": 7.0,
                "evidence_ids": ["E-3"],
            }
        ]
    )
    reranker = FakeCrossEncoder()
    service = DeepSearchService(advanced, lexical, reranker, group_id="test-group")

    result = asyncio.run(service.search("chip suppliers"))

    assert advanced.search_calls == 0
    assert [call["algorithm"] for call in advanced.calls] == ["vector", "bm25", "bfs"]
    assert all(call["config"].limit == 20 for call in advanced.calls)
    assert advanced.calls[0]["config"].episode_config is None
    assert advanced.calls[1]["config"].episode_config is not None
    assert advanced.calls[2]["config"].community_config is None
    assert advanced.calls[2]["bfs_origin_node_uuids"] == [
        "entity-vector",
        "entity-bm25",
    ]
    assert lexical.calls == [{"query": "chip suppliers", "limit": 20}]
    assert [slice_.algorithm for slice_ in result.slices] == [
        "vector",
        "bm25",
        "bfs",
        "lexical",
    ]
    assert all(slice_.status == "completed" for slice_ in result.slices)
    duplicate = next(item for item in result.candidates if item.uuid == "edge-1")
    assert duplicate.algorithms == ["vector", "bm25"]
    assert duplicate.evidence_ids == ["E-1"]
    assert {item.object_type for item in result.candidates} >= {
        "edge",
        "entity",
        "episode",
        "community",
    }


def test_episode_content_recovers_controlled_evidence_ids() -> None:
    from app.services.retrieval import DeepSearchService

    episode = SimpleNamespace(
        uuid="episode-tsmc-nvidia",
        name="TSMC-NVIDIA-晶圆代工",
        content=(
            "TSMC 为 NVIDIA 提供晶圆代工。\n"
            "置信度：medium。\n"
            "数据截至时间：2026-07-08。\n"
            "最近核验时间：2026-07-05。\n"
            "当前有效性：当前支持。\n"
            "判断性质：事实判断。\n"
            "证据ID：E4-026;E4-027;E4-M007。"
        ),
        valid_at=None,
        episode_metadata=None,
    )
    service = DeepSearchService(
        FakeAdvancedSearch({"bm25": _results(episodes=[episode])}),
        FakeLexicalSearch(),
        FakeCrossEncoder(fail=True),
        group_id="test-group",
    )

    result = asyncio.run(service.search("NVIDIA TSMC"))

    candidate = next(
        item for item in result.candidates if item.uuid == "episode-tsmc-nvidia"
    )
    assert candidate.evidence_ids == ["E4-026", "E4-027", "E4-M007"]
    assert candidate.confidence == "medium"
    assert candidate.data_as_of == "2026-07-08"
    assert candidate.last_verified_at == "2026-07-05"
    assert candidate.current_validity == "当前支持"
    assert candidate.claim_nature == "fact"


def test_episode_content_recovers_decision_signal_evidence_ids() -> None:
    from app.services.retrieval import DeepSearchService

    episode = SimpleNamespace(
        uuid="episode-decision-signal",
        name="华为与稻盛经营哲学",
        content="资料类型：企业战略含义\n证据ID：DS-20260715-ABC123\n核心内容：华为与稻盛经营哲学相关资料。",
        valid_at=None,
        episode_metadata=None,
    )
    service = DeepSearchService(
        FakeAdvancedSearch({"bm25": _results(episodes=[episode])}),
        FakeLexicalSearch(),
        FakeCrossEncoder(fail=True),
        group_id="test-group",
    )

    result = asyncio.run(service.search("华为 稻盛"))

    candidate = next(
        item for item in result.candidates if item.uuid == "episode-decision-signal"
    )
    assert candidate.evidence_ids == ["DS-20260715-ABC123"]


def test_one_retrieval_failure_does_not_block_other_slices() -> None:
    from app.services.retrieval import DeepSearchService

    advanced = FakeAdvancedSearch(
        {
            "vector": _results(nodes=[_node("origin", "Origin")]),
            "bfs": _results(edges=[_edge("edge-bfs", "reachable fact")]),
        },
        fail={"bm25"},
    )
    service = DeepSearchService(
        advanced,
        FakeLexicalSearch([{"uuid": "lex", "fact": "lexical fact", "score": 1}]),
        FakeCrossEncoder(),
        group_id="test-group",
    )

    result = asyncio.run(service.search("query"))

    slices = {slice_.algorithm: slice_ for slice_ in result.slices}
    assert slices["bm25"].status == "failed"
    assert "bm25 unavailable" in slices["bm25"].error
    assert slices["vector"].status == "completed"
    assert slices["bfs"].status == "completed"
    assert slices["lexical"].status == "completed"
    assert {item.uuid for item in result.candidates} >= {"edge-bfs", "lex"}


def test_cross_encoder_caps_pool_and_marks_only_twelve_selected() -> None:
    from app.services.retrieval import DeepSearchService

    def many_results(prefix: str) -> Any:
        return _results(
            nodes=[
                _node(f"{prefix}-{index:03d}", f"{prefix} {index:03d}")
                for index in range(25)
            ]
        )

    reranker = FakeCrossEncoder()
    service = DeepSearchService(
        FakeAdvancedSearch(
            {
                "vector": lambda: many_results("vector"),
                "bm25": lambda: many_results("bm25"),
                "bfs": lambda: many_results("bfs"),
            }
        ),
        FakeLexicalSearch(
            [
                {
                    "uuid": f"lexical-{index:03d}",
                    "fact": f"lexical fact {index:03d}",
                    "score": 25 - index,
                }
                for index in range(25)
            ]
        ),
        reranker,
        group_id="test-group",
    )

    result = asyncio.run(service.search("rank all"))

    assert all(len(slice_.candidates) <= 20 for slice_ in result.slices)
    assert len(result.candidates) == 60
    assert len(reranker.calls) == 1
    assert len(reranker.calls[0][1]) == 60
    assert result.rerank_method == "cross_encoder"
    assert result.fallback_reason is None
    assert sum(item.selected for item in result.candidates) == 12
    assert [item.rank for item in result.candidates] == list(range(1, 61))
    assert result.candidates[0].rerank_score == 59.0


def test_reranker_failure_uses_rrf_and_records_reason() -> None:
    from app.services.retrieval import DeepSearchService

    advanced = FakeAdvancedSearch(
        {
            "vector": _results(
                edges=[
                    _edge("vector-first", "vector first", score=0.9),
                    _edge("shared", "shared fact", score=0.8),
                ]
            ),
            "bm25": _results(
                edges=[
                    _edge("shared", "shared fact", score=8.0),
                    _edge("bm25-second", "bm25 second", score=7.0),
                ]
            ),
        }
    )
    service = DeepSearchService(
        advanced,
        FakeLexicalSearch(),
        FakeCrossEncoder(fail=True),
        group_id="test-group",
    )

    result = asyncio.run(service.search("fallback"))

    assert result.rerank_method == "rrf"
    assert "reranker timeout" in result.fallback_reason
    assert result.candidates[0].uuid == "shared"
    assert result.candidates[0].rerank_fallback_reason == result.fallback_reason
    assert result.candidates[0].metadata["rrf_score"] > 0


def test_neo4j_lexical_adapter_uses_parameterized_query() -> None:
    from app.services.retrieval import Neo4jLexicalSearchAdapter

    class FakeDriver:
        def __init__(self) -> None:
            self.cypher = ""
            self.parameters: dict[str, Any] = {}

        def execute_query(self, cypher: str, **parameters: Any) -> tuple[list[Any], None, None]:
            self.cypher = cypher
            self.parameters = parameters
            return ([{"uuid": "edge-1", "fact": "result", "score": 2}], None, None)

    driver = FakeDriver()
    adapter = Neo4jLexicalSearchAdapter(driver, group_id="group-1")

    rows = asyncio.run(adapter.search_("NVIDIA 'quoted'", limit=20))

    assert rows[0]["uuid"] == "edge-1"
    assert "NVIDIA" not in driver.cypher
    assert "$terms" in driver.cypher
    assert "MATCH (e:Episodic" in driver.cypher
    assert driver.parameters["group_id"] == "group-1"
    assert driver.parameters["limit"] == 20
    assert "nvidia" in driver.parameters["terms"]


def test_lexical_episode_candidates_recover_decision_signal_evidence_ids() -> None:
    from app.services.retrieval import DeepSearchService

    service = DeepSearchService(
        FakeAdvancedSearch({}),
        FakeLexicalSearch(
            [
                {
                    "object_type": "episode",
                    "uuid": "episode-decision-signal",
                    "name": "华为公司治理：以客户为中心",
                    "content": "资料类型：企业战略含义\n证据ID：DS-20260715-ABC123\n核心内容：华为长期主义。",
                    "score": 4,
                }
            ]
        ),
        FakeCrossEncoder(fail=True),
        group_id="test-group",
    )

    result = asyncio.run(service.search("华为 长期主义"))

    candidate = next(
        item for item in result.candidates if item.uuid == "episode-decision-signal"
    )
    assert candidate.object_type == "episode"
    assert candidate.evidence_ids == ["DS-20260715-ABC123"]
    assert candidate.algorithms == ["lexical"]


def test_deep_search_and_graphiti_adapter_require_explicit_group_scope() -> None:
    from app.services.retrieval import (
        DeepSearchService,
        GraphitiAdvancedSearchAdapter,
    )

    with pytest.raises(ValueError, match="group_id"):
        DeepSearchService(
            FakeAdvancedSearch({}),
            FakeLexicalSearch(),
            FakeCrossEncoder(),
            group_id="  ",
        )

    class FakeGraphiti:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        async def search_(self, **kwargs: Any) -> Any:
            self.calls.append(kwargs)
            return _results()

    graphiti = FakeGraphiti()
    with pytest.raises(ValueError, match="group_id"):
        GraphitiAdvancedSearchAdapter(graphiti, group_id="")

    adapter = GraphitiAdvancedSearchAdapter(graphiti, group_id=" scoped-group ")
    asyncio.run(adapter.search_(query="q", config=object()))
    assert graphiti.calls[0]["group_ids"] == ["scoped-group"]

    with pytest.raises(ValueError, match="group_ids"):
        asyncio.run(
            adapter.search_(
                query="q",
                config=object(),
                group_ids=["different-group"],
            )
        )

    service = DeepSearchService(
        FakeAdvancedSearch({}),
        FakeLexicalSearch(),
        FakeCrossEncoder(),
        group_id="scoped-group",
    )
    service.group_id = " "
    with pytest.raises(ValueError, match="group_id"):
        asyncio.run(service.search("q"))


def test_type_fair_slice_preserves_entities_and_all_bfs_origins() -> None:
    from app.services.retrieval import DeepSearchService

    advanced = FakeAdvancedSearch(
        {
            "vector": _results(
                edges=[
                    _edge(f"edge-{index:02d}", f"edge fact {index}")
                    for index in range(30)
                ],
                nodes=[
                    _node(f"entity-{index:02d}", f"Entity {index}")
                    for index in range(25)
                ],
            ),
            "bm25": _results(),
            "bfs": _results(),
        }
    )
    service = DeepSearchService(
        advanced,
        FakeLexicalSearch(),
        FakeCrossEncoder(fail=True),
        group_id="test-group",
        slice_limit=20,
    )

    result = asyncio.run(service.search("fair retrieval"))

    vector_slice = next(item for item in result.slices if item.algorithm == "vector")
    assert len(vector_slice.candidates) == 20
    assert {item.object_type for item in vector_slice.candidates} == {"edge", "entity"}
    entity_candidates = [
        item for item in vector_slice.candidates if item.object_type == "entity"
    ]
    assert [item.metadata["type_rank"] for item in entity_candidates] == list(
        range(1, 11)
    )
    bfs_call = next(call for call in advanced.calls if call["algorithm"] == "bfs")
    assert bfs_call["bfs_origin_node_uuids"] == [
        f"entity-{index:02d}" for index in range(25)
    ]
    edge_first = next(item for item in result.candidates if item.uuid == "edge-00")
    entity_first = next(item for item in result.candidates if item.uuid == "entity-00")
    assert edge_first.metadata["algorithm_ranks"]["vector"] == 1
    assert entity_first.metadata["algorithm_ranks"]["vector"] == 1
    assert edge_first.metadata["rrf_score"] == entity_first.metadata["rrf_score"]


def test_vector_bm25_and_lexical_start_concurrently_before_bfs() -> None:
    from app.services.retrieval import DeepSearchService

    class Probe:
        def __init__(self) -> None:
            self.started: set[str] = set()
            self.first_wave_ready = asyncio.Event()

        async def wait_for_first_wave(self, algorithm: str) -> None:
            self.started.add(algorithm)
            if self.started >= {"vector", "bm25", "lexical"}:
                self.first_wave_ready.set()
            await self.first_wave_ready.wait()

    probe = Probe()

    class CoordinatedAdvanced(FakeAdvancedSearch):
        async def search_(self, **kwargs: Any) -> Any:
            methods = _method_values(kwargs["config"])
            if "breadth_first_search" in methods:
                self.calls.append({"algorithm": "bfs", **kwargs})
                return _results()
            algorithm = "vector" if methods == {"cosine_similarity"} else "bm25"
            self.calls.append({"algorithm": algorithm, **kwargs})
            await probe.wait_for_first_wave(algorithm)
            return _results(nodes=[_node(f"{algorithm}-origin", algorithm)])

    class CoordinatedLexical(FakeLexicalSearch):
        async def search_(self, query: str, limit: int) -> list[Any]:
            self.calls.append({"query": query, "limit": limit})
            await probe.wait_for_first_wave("lexical")
            return []

    service = DeepSearchService(
        CoordinatedAdvanced({}),
        CoordinatedLexical(),
        FakeCrossEncoder(),
        group_id="test-group",
        search_timeout_seconds=0.2,
    )

    result = asyncio.run(asyncio.wait_for(service.search("concurrent"), timeout=1))

    assert probe.started == {"vector", "bm25", "lexical"}
    assert all(slice_.status == "completed" for slice_ in result.slices)


def test_hanging_first_wave_route_times_out_without_blocking_other_slices() -> None:
    from app.services.retrieval import DeepSearchService

    never = asyncio.Event()

    class HangingAdvanced(FakeAdvancedSearch):
        async def search_(self, **kwargs: Any) -> Any:
            methods = _method_values(kwargs["config"])
            if "breadth_first_search" in methods:
                algorithm = "bfs"
            elif methods == {"cosine_similarity"}:
                algorithm = "vector"
            else:
                algorithm = "bm25"
            self.calls.append({"algorithm": algorithm, **kwargs})
            if algorithm == "bm25":
                await never.wait()
            if algorithm == "vector":
                return _results(nodes=[_node("origin", "Origin")])
            return _results()

    service = DeepSearchService(
        HangingAdvanced({}),
        FakeLexicalSearch([{"uuid": "lex", "fact": "lexical fact", "score": 1}]),
        FakeCrossEncoder(),
        group_id="test-group",
        search_timeout_seconds=0.02,
    )

    result = asyncio.run(asyncio.wait_for(service.search("timeout"), timeout=1))

    slices = {slice_.algorithm: slice_ for slice_ in result.slices}
    assert slices["bm25"].status == "failed"
    assert "TimeoutError" in slices["bm25"].error
    assert slices["vector"].status == "completed"
    assert slices["lexical"].status == "completed"
    assert slices["bfs"].status == "completed"
