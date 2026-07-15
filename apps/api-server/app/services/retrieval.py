from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import re
from collections import defaultdict, deque
from collections.abc import Mapping, Sequence
from datetime import datetime
from time import perf_counter
from typing import Any, Protocol
from uuid import uuid4

import httpx
from graphiti_core.cross_encoder.client import CrossEncoderClient
from graphiti_core.search.search_config import (
    CommunityReranker,
    CommunitySearchConfig,
    CommunitySearchMethod,
    EdgeReranker,
    EdgeSearchConfig,
    EdgeSearchMethod,
    EpisodeReranker,
    EpisodeSearchConfig,
    EpisodeSearchMethod,
    NodeReranker,
    NodeSearchConfig,
    NodeSearchMethod,
    SearchConfig,
)
from pydantic import BaseModel, Field

from app.schemas import RetrievalCandidate, RetrievalSlice
from app.services.tracing import start_span


EVIDENCE_ID_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:E\d+-(?:[A-Z]+)?\d+|DC(?:-[A-Z]+)?-\d+|DS-[A-Z0-9][A-Z0-9-]*)(?![A-Za-z0-9])"
)
EPISODE_FIELD_LABELS = {
    "confidence": "置信度",
    "data_as_of": "数据截至时间",
    "last_verified_at": "最近核验时间",
    "needs_refresh_after": "建议复核时间",
    "current_validity": "当前有效性",
    "claim_nature": "判断性质",
    "requires_internal_validation": "是否需要内部验证",
}
CLAIM_NATURE_VALUES = {
    "事实判断": "fact",
    "事实关系": "fact",
    "推断关系": "inferred",
    "推定关系": "inferred",
}


class CrossEncoder(Protocol):
    def rank(self, query: str, passages: list[str]) -> Sequence[float]: ...


class GraphitiCrossEncoderAdapter:
    """把 Graphiti 的 `(passage, score)` 排序结果还原成输入顺序分数。"""

    def __init__(self, reranker: Any) -> None:
        self.reranker = reranker

    async def rank(self, query: str, passages: list[str]) -> list[float]:
        results = self.reranker.rank(query, passages)
        if inspect.isawaitable(results):
            results = await results
        values = list(results)
        if not values:
            return []
        if all(isinstance(value, (int, float)) for value in values):
            return [float(value) for value in values]

        scores_by_passage: dict[str, deque[float]] = defaultdict(deque)
        for value in values:
            if not isinstance(value, (tuple, list)) or len(value) != 2:
                raise ValueError("Graphiti reranker 返回格式不受支持")
            passage, score = value
            scores_by_passage[str(passage)].append(float(score))

        restored: list[float] = []
        for passage in passages:
            scores = scores_by_passage.get(passage)
            if not scores:
                raise ValueError("Graphiti reranker 未返回全部段落分数")
            restored.append(scores.popleft())
        return restored

    async def close(self) -> None:
        close = getattr(self.reranker, "close", None)
        if close is None:
            return
        result = close()
        if inspect.isawaitable(result):
            await result


class SiliconFlowReranker(CrossEncoderClient):
    """调用 SiliconFlow 原生 rerank 接口并按原文档顺序返回相关度。"""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 30.0,
        client: Any | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("SiliconFlow reranker 缺少 API key")
        if not model:
            raise ValueError("SiliconFlow reranker 缺少模型名称")
        self.model = model
        self.client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_seconds,
        )

    async def rank(self, query: str, passages: list[str]) -> list[tuple[str, float]]:
        if not passages:
            return []
        response = await self.client.post(
            "/rerank",
            json={
                "model": self.model,
                "query": query,
                "documents": passages,
                "top_n": len(passages),
                "return_documents": False,
            },
        )
        response.raise_for_status()
        results = response.json().get("results") or []
        scores: list[float | None] = [None] * len(passages)
        for item in results:
            index = int(item["index"])
            if not 0 <= index < len(scores):
                raise ValueError("SiliconFlow reranker 返回了越界文档索引")
            scores[index] = float(item["relevance_score"])
        if any(score is None for score in scores):
            raise ValueError("SiliconFlow reranker 未返回全部文档分数")
        ranked = [
            (passage, float(score))
            for passage, score in zip(passages, scores, strict=True)
            if score is not None
        ]
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked

    async def close(self) -> None:
        await self.client.aclose()


class DeepSearchResult(BaseModel):
    slices: list[RetrievalSlice] = Field(default_factory=list)
    candidates: list[RetrievalCandidate] = Field(default_factory=list)
    rerank_method: str
    fallback_reason: str | None = None

    @property
    def selected_candidates(self) -> list[RetrievalCandidate]:
        return [candidate for candidate in self.candidates if candidate.selected]


class GraphitiAdvancedSearchAdapter:
    """限制生产检索入口只能调用 Graphiti 的高级 search_。"""

    def __init__(self, graphiti: Any, *, group_id: str) -> None:
        self.graphiti = graphiti
        self.group_id = _require_group_id(group_id)

    async def search_(self, **kwargs: Any) -> Any:
        group_id = _require_group_id(self.group_id)
        requested_group_ids = kwargs.get("group_ids")
        if requested_group_ids is not None and requested_group_ids != [group_id]:
            raise ValueError("group_ids 必须与适配器的明确 group_id 一致")
        kwargs["group_ids"] = [group_id]
        return await self.graphiti.search_(**kwargs)


class Neo4jLexicalSearchAdapter:
    def __init__(self, driver: Any, group_id: str) -> None:
        self.driver = driver
        self.group_id = group_id

    async def search_(self, query: str, limit: int) -> list[dict[str, Any]]:
        terms = _query_terms(query)
        if not terms:
            return []
        cypher = """
        CALL () {
        MATCH (source)-[r:RELATES_TO {group_id: $group_id}]->(target)
        WITH source, r, target,
             toLower(
                coalesce(source.name, '') + ' ' +
                coalesce(target.name, '') + ' ' +
                coalesce(r.name, '') + ' ' +
                coalesce(r.fact, '') + ' ' +
                coalesce(r.relationship_status, '') + ' ' +
                coalesce(r.relationship_type, '')
             ) AS searchable
        WITH source, r, target,
             reduce(score = 0, term IN $terms |
                score + CASE WHEN searchable CONTAINS term THEN 1 ELSE 0 END
             ) AS score
        WHERE score > 0
        RETURN 'edge' AS object_type,
               coalesce(r.uuid, elementId(r)) AS uuid,
               r.name AS name,
               r.fact AS fact,
               null AS content,
               source.name AS source,
               target.name AS target,
               r.evidence_ids AS evidence_ids,
               r.primary_evidence_id AS primary_evidence_id,
               r.confidence AS confidence,
               r.current_validity AS current_validity,
               r.last_verified_at AS last_verified_at,
               r.needs_refresh_after AS needs_refresh_after,
               r.requires_internal_validation AS requires_internal_validation,
               r.claim_nature AS claim_nature,
               r.relationship_status AS verification_status,
               score
        UNION ALL
        MATCH (e:Episodic {group_id: $group_id})
        WITH e,
             toLower(
                coalesce(e.name, '') + ' ' +
                coalesce(e.content, '') + ' ' +
                coalesce(e.source_description, '')
             ) AS searchable
        WITH e,
             reduce(score = 0, term IN $terms |
                score + CASE WHEN searchable CONTAINS term THEN 1 ELSE 0 END
             ) AS score
        WHERE score > 0
        RETURN 'episode' AS object_type,
               coalesce(e.uuid, elementId(e)) AS uuid,
               e.name AS name,
               null AS fact,
               e.content AS content,
               null AS source,
               null AS target,
               e.evidence_ids AS evidence_ids,
               e.primary_evidence_id AS primary_evidence_id,
               null AS confidence,
               null AS current_validity,
               null AS last_verified_at,
               null AS needs_refresh_after,
               null AS requires_internal_validation,
               null AS claim_nature,
               null AS verification_status,
               score
        }
        WITH *
        ORDER BY score DESC, uuid
        LIMIT $limit
        RETURN object_type,
               uuid,
               name,
               fact,
               content,
               source,
               target,
               evidence_ids,
               primary_evidence_id,
               confidence,
               current_validity,
               last_verified_at,
               needs_refresh_after,
               requires_internal_validation,
               claim_nature,
               verification_status,
               score
        """

        def execute() -> Any:
            return self.driver.execute_query(
                cypher,
                group_id=self.group_id,
                terms=terms,
                limit=limit,
                routing_="r",
            )

        response = await asyncio.to_thread(execute)
        if inspect.isawaitable(response):
            response = await response
        records = response[0] if isinstance(response, tuple) else response
        return [dict(record) for record in records]


class DeepSearchService:
    def __init__(
        self,
        advanced_search: Any,
        lexical_search: Any,
        cross_encoder: CrossEncoder,
        *,
        group_id: str,
        slice_limit: int = 20,
        candidate_pool_limit: int = 60,
        final_limit: int = 12,
        search_timeout_seconds: float = 20.0,
    ) -> None:
        self.advanced_search = advanced_search
        self.lexical_search = lexical_search
        self.cross_encoder = cross_encoder
        self.group_id = _require_group_id(group_id)
        self.slice_limit = slice_limit
        self.candidate_pool_limit = candidate_pool_limit
        self.final_limit = final_limit
        if search_timeout_seconds <= 0:
            raise ValueError("search_timeout_seconds 必须大于 0")
        self.search_timeout_seconds = search_timeout_seconds

    async def search(self, query: str) -> DeepSearchResult:
        _require_group_id(self.group_id)
        with start_span(
            "retrieval.search",
            {
                "group_id": self.group_id,
                "query_length": len(query),
                "slice_limit": self.slice_limit,
                "candidate_pool_limit": self.candidate_pool_limit,
                "final_limit": self.final_limit,
            },
        ) as span:
            vector, bm25, lexical = await asyncio.gather(
                self._advanced_slice(query, "vector"),
                self._advanced_slice(query, "bm25"),
                self._lexical_slice(query),
            )
            origins = _entity_origins(vector, bm25)
            bfs = await self._advanced_slice(query, "bfs", origins=origins)
            slices = [vector, bm25, bfs, lexical]
            candidates = self._merge_candidates(slices)
            rerank_method, fallback_reason = await self._rerank(query, candidates)
            span.set_attributes(
                {
                    "slice_count": len(slices),
                    "candidate_count": len(candidates),
                    "selected_count": sum(candidate.selected for candidate in candidates),
                    "rerank_method": rerank_method,
                    "fallback_reason": fallback_reason,
                }
            )
            return DeepSearchResult(
                slices=slices,
                candidates=candidates,
                rerank_method=rerank_method,
                fallback_reason=fallback_reason,
            )

    async def close(self) -> None:
        close = getattr(self.cross_encoder, "close", None)
        if close is None:
            return
        result = close()
        if inspect.isawaitable(result):
            await result

    async def _advanced_slice(
        self, query: str, algorithm: str, origins: list[str] | None = None
    ) -> RetrievalSlice:
        started_at = datetime.now().astimezone()
        started = perf_counter()
        with start_span(
            f"retrieval.slice.{algorithm}",
            {
                "group_id": self.group_id,
                "algorithm": algorithm,
                "query_length": len(query),
            },
        ) as span:
            try:
                kwargs: dict[str, Any] = {
                    "query": query,
                    "config": _search_config(algorithm, self.slice_limit),
                    "group_ids": [_require_group_id(self.group_id)],
                }
                if algorithm == "bfs":
                    kwargs["bfs_origin_node_uuids"] = origins or []
                results = await asyncio.wait_for(
                    self.advanced_search.search_(**kwargs),
                    timeout=self.search_timeout_seconds,
                )
                candidates = _normalize_search_results(results, algorithm)
                entity_origin_uuids = _unique(
                    candidate.uuid
                    for candidate in candidates
                    if candidate.object_type == "entity" and candidate.uuid
                )
                span.set_attributes(
                    {
                        "status": "completed",
                        "candidate_count": len(candidates),
                        "entity_origin_count": len(entity_origin_uuids),
                    }
                )
                return RetrievalSlice(
                    id=f"{algorithm}-{uuid4()}",
                    name=algorithm,
                    algorithm=algorithm,
                    query=query,
                    status="completed",
                    candidates=candidates[: self.slice_limit],
                    metadata={"entity_origin_uuids": entity_origin_uuids},
                    duration_ms=(perf_counter() - started) * 1000,
                    started_at=started_at,
                    completed_at=datetime.now().astimezone(),
                )
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                span.set_attributes({"status": "failed", "error": error})
                return RetrievalSlice(
                    id=f"{algorithm}-{uuid4()}",
                    name=algorithm,
                    algorithm=algorithm,
                    query=query,
                    status="failed",
                    error=error,
                    duration_ms=(perf_counter() - started) * 1000,
                    started_at=started_at,
                    completed_at=datetime.now().astimezone(),
                )

    async def _lexical_slice(self, query: str) -> RetrievalSlice:
        started_at = datetime.now().astimezone()
        started = perf_counter()
        with start_span(
            "retrieval.slice.lexical",
            {
                "group_id": self.group_id,
                "query_length": len(query),
            },
        ) as span:
            try:
                records = await asyncio.wait_for(
                    self.lexical_search.search_(query, self.slice_limit),
                    timeout=self.search_timeout_seconds,
                )
                candidates = [
                    _candidate_from_object(
                        record,
                        str(record.get("object_type") or "edge"),
                        "lexical",
                        index,
                    )
                    for index, record in enumerate(records, start=1)
                ]
                span.set_attributes(
                    {
                        "status": "completed",
                        "candidate_count": len(candidates),
                    }
                )
                return RetrievalSlice(
                    id=f"lexical-{uuid4()}",
                    name="lexical",
                    algorithm="lexical",
                    query=query,
                    status="completed",
                    candidates=candidates[: self.slice_limit],
                    duration_ms=(perf_counter() - started) * 1000,
                    started_at=started_at,
                    completed_at=datetime.now().astimezone(),
                )
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                span.set_attributes({"status": "failed", "error": error})
                return RetrievalSlice(
                    id=f"lexical-{uuid4()}",
                    name="lexical",
                    algorithm="lexical",
                    query=query,
                    status="failed",
                    error=error,
                    duration_ms=(perf_counter() - started) * 1000,
                    started_at=started_at,
                    completed_at=datetime.now().astimezone(),
                )

    def _merge_candidates(
        self, slices: list[RetrievalSlice]
    ) -> list[RetrievalCandidate]:
        merged: dict[tuple[str, str], RetrievalCandidate] = {}
        order: list[tuple[str, str]] = []
        for slice_ in slices:
            for candidate in slice_.candidates:
                key = _stable_key(candidate)
                current = merged.get(key)
                if current is None:
                    current = candidate.model_copy(deep=True)
                    current.algorithms = []
                    current.metadata = dict(current.metadata)
                    current.metadata["algorithm_ranks"] = {}
                    current.metadata["algorithm_scores"] = {}
                    merged[key] = current
                    order.append(key)
                if slice_.algorithm not in current.algorithms:
                    current.algorithms.append(slice_.algorithm)
                current.metadata["algorithm_ranks"][slice_.algorithm] = (
                    candidate.metadata.get("type_rank") or candidate.rank
                )
                current.metadata["algorithm_scores"][slice_.algorithm] = candidate.score
                current.evidence_ids = _unique(
                    [*current.evidence_ids, *candidate.evidence_ids]
                )

        candidates = [merged[key] for key in order]
        indexed = list(enumerate(candidates))
        for _, candidate in indexed:
            candidate.metadata["rrf_score"] = _rrf_score(candidate)
        indexed.sort(
            key=lambda item: (-float(item[1].metadata["rrf_score"]), item[0])
        )
        return [candidate for _, candidate in indexed[: self.candidate_pool_limit]]

    async def _rerank(
        self, query: str, candidates: list[RetrievalCandidate]
    ) -> tuple[str, str | None]:
        if not candidates:
            return "cross_encoder", None
        passages = [f"{item.title}\n{item.content}" for item in candidates]
        with start_span(
            "retrieval.rerank",
            {
                "query_length": len(query),
                "candidate_count": len(candidates),
            },
        ) as span:
            try:
                scores = self.cross_encoder.rank(query, passages)
                if inspect.isawaitable(scores):
                    scores = await scores
                scores = list(scores)
                if len(scores) != len(candidates):
                    raise ValueError(
                        f"reranker returned {len(scores)} scores for {len(candidates)} passages"
                    )
                indexed = list(enumerate(candidates))
                for (_, candidate), score in zip(indexed, scores, strict=True):
                    candidate.rerank_score = float(score)
                indexed.sort(
                    key=lambda item: (-float(item[1].rerank_score or 0), item[0])
                )
                candidates[:] = [candidate for _, candidate in indexed]
                method = "cross_encoder"
                reason = None
                span.set_attributes({"status": "completed", "method": method})
            except Exception as exc:
                reason = f"{type(exc).__name__}: {exc}"
                indexed = list(enumerate(candidates))
                indexed.sort(
                    key=lambda item: (-float(item[1].metadata["rrf_score"]), item[0])
                )
                candidates[:] = [candidate for _, candidate in indexed]
                for candidate in candidates:
                    candidate.rerank_fallback_reason = reason
                method = "rrf"
                span.set_attributes(
                    {
                        "status": "failed",
                        "method": method,
                        "fallback_reason": reason,
                    }
                )

        for index, candidate in enumerate(candidates, start=1):
            candidate.rank = index
            candidate.selected = index <= self.final_limit
        return method, reason


def _search_config(algorithm: str, limit: int) -> SearchConfig:
    if algorithm == "vector":
        return SearchConfig(
            edge_config=EdgeSearchConfig(
                search_methods=[EdgeSearchMethod.cosine_similarity],
                reranker=EdgeReranker.rrf,
            ),
            node_config=NodeSearchConfig(
                search_methods=[NodeSearchMethod.cosine_similarity],
                reranker=NodeReranker.rrf,
            ),
            community_config=CommunitySearchConfig(
                search_methods=[CommunitySearchMethod.cosine_similarity],
                reranker=CommunityReranker.rrf,
            ),
            limit=limit,
        )
    if algorithm == "bm25":
        return SearchConfig(
            edge_config=EdgeSearchConfig(
                search_methods=[EdgeSearchMethod.bm25], reranker=EdgeReranker.rrf
            ),
            node_config=NodeSearchConfig(
                search_methods=[NodeSearchMethod.bm25], reranker=NodeReranker.rrf
            ),
            episode_config=EpisodeSearchConfig(
                search_methods=[EpisodeSearchMethod.bm25],
                reranker=EpisodeReranker.rrf,
            ),
            community_config=CommunitySearchConfig(
                search_methods=[CommunitySearchMethod.bm25],
                reranker=CommunityReranker.rrf,
            ),
            limit=limit,
        )
    if algorithm == "bfs":
        return SearchConfig(
            edge_config=EdgeSearchConfig(
                search_methods=[EdgeSearchMethod.bfs], reranker=EdgeReranker.rrf
            ),
            node_config=NodeSearchConfig(
                search_methods=[NodeSearchMethod.bfs], reranker=NodeReranker.rrf
            ),
            limit=limit,
        )
    raise ValueError(f"unsupported retrieval algorithm: {algorithm}")


def _normalize_search_results(results: Any, algorithm: str) -> list[RetrievalCandidate]:
    candidates_by_type: list[list[RetrievalCandidate]] = []
    sections = (
        ("edges", "edge", "edge_reranker_scores"),
        ("nodes", "entity", "node_reranker_scores"),
        ("episodes", "episode", "episode_reranker_scores"),
        ("communities", "community", "community_reranker_scores"),
    )
    for collection_name, object_type, score_name in sections:
        objects = list(_value(results, collection_name, []) or [])
        scores = list(_value(results, score_name, []) or [])
        type_candidates: list[RetrievalCandidate] = []
        for index, obj in enumerate(objects):
            score = scores[index] if index < len(scores) else None
            type_rank = index + 1
            candidate = _candidate_from_object(
                obj, object_type, algorithm, type_rank, score
            )
            candidate.metadata["type_rank"] = type_rank
            type_candidates.append(candidate)
        if type_candidates:
            candidates_by_type.append(type_candidates)

    candidates: list[RetrievalCandidate] = []
    max_type_size = max((len(items) for items in candidates_by_type), default=0)
    for type_index in range(max_type_size):
        for type_candidates in candidates_by_type:
            if type_index >= len(type_candidates):
                continue
            candidate = type_candidates[type_index]
            candidate.rank = len(candidates) + 1
            candidate.metadata["interleaved_rank"] = candidate.rank
            candidates.append(candidate)
    return candidates


def _candidate_from_object(
    obj: Any,
    object_type: str,
    algorithm: str,
    rank: int,
    score: Any = None,
) -> RetrievalCandidate:
    attributes = dict(_value(obj, "attributes", {}) or {})
    if object_type == "episode":
        attributes.update(dict(_value(obj, "episode_metadata", {}) or {}))
    if isinstance(obj, Mapping):
        attributes = {**dict(obj), **attributes}

    uuid = _string_or_none(_value(obj, "uuid", None))
    relation = _first(obj, attributes, "relation", "name", "relationship_type")
    if object_type == "edge":
        content = _first(obj, attributes, "fact", "content") or relation or ""
        title = relation or "关系事实"
    elif object_type == "episode":
        content = _first(obj, attributes, "content") or ""
        title = _first(obj, attributes, "name", "title") or "事件"
    else:
        content = _first(obj, attributes, "summary", "content", "name") or ""
        title = _first(obj, attributes, "name", "title") or object_type

    if object_type == "episode":
        for key, value in _episode_fields(str(content)).items():
            attributes.setdefault(key, value)

    raw_score = score if score is not None else _first(obj, attributes, "score")
    numeric_score = float(raw_score) if raw_score is not None else 1.0 / rank
    evidence_ids = _parse_evidence_ids(
        _first(obj, attributes, "evidence_ids", "primary_evidence_id")
    )
    if object_type == "episode":
        evidence_ids = _unique(
            [*evidence_ids, *EVIDENCE_ID_PATTERN.findall(str(content))]
        )
    candidate_id = uuid or _content_hash(object_type, str(content))
    return RetrievalCandidate(
        id=candidate_id,
        uuid=uuid,
        title=str(title),
        content=str(content),
        score=numeric_score,
        algorithm=algorithm,
        algorithms=[algorithm],
        object_type=object_type,
        rank=rank,
        evidence_ids=evidence_ids,
        source=_first(
            obj, attributes, "source", "source_node_uuid", "source_company"
        ),
        target=_first(
            obj, attributes, "target", "target_node_uuid", "target_company"
        ),
        relation=relation,
        evidence_level=_first(obj, attributes, "evidence_level", "source_grade"),
        confidence=_business_confidence(_first(obj, attributes, "confidence")),
        valid_from=_string_or_none(_first(obj, attributes, "valid_from", "valid_at")),
        valid_to=_string_or_none(_first(obj, attributes, "valid_to", "invalid_at")),
        data_as_of=_string_or_none(_first(obj, attributes, "data_as_of", "reference_time")),
        last_verified_at=_string_or_none(
            _first(obj, attributes, "last_verified_at")
        ),
        needs_refresh_after=_string_or_none(
            _first(obj, attributes, "needs_refresh_after")
        ),
        current_validity=_first(obj, attributes, "current_validity"),
        requires_internal_validation=_truthy(
            _first(obj, attributes, "requires_internal_validation")
        ),
        claim_nature=_first(obj, attributes, "claim_nature"),
        verification_status=_first(
            obj, attributes, "verification_status", "relationship_status"
        ),
        metadata={
            **attributes,
            "original_rank": rank,
            "original_score": numeric_score,
            "type_rank": rank,
        },
    )


def _entity_origins(*slices: RetrievalSlice) -> list[str]:
    return _unique(
        uuid
        for slice_ in slices
        for uuid in (
            slice_.metadata.get("entity_origin_uuids")
            or [
                candidate.uuid
                for candidate in slice_.candidates
                if candidate.object_type == "entity" and candidate.uuid
            ]
        )
        if uuid
    )


def _stable_key(candidate: RetrievalCandidate) -> tuple[str, str]:
    if candidate.uuid:
        return candidate.object_type, candidate.uuid
    return candidate.object_type, _content_hash(candidate.object_type, candidate.content)


def _content_hash(object_type: str, content: str) -> str:
    normalized = " ".join(content.casefold().split())
    return hashlib.sha256(f"{object_type}:{normalized}".encode("utf-8")).hexdigest()


def _rrf_score(candidate: RetrievalCandidate, constant: int = 60) -> float:
    ranks = candidate.metadata.get("algorithm_ranks", {})
    return sum(1.0 / (constant + int(rank)) for rank in ranks.values() if rank)


def _value(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _first(obj: Any, attributes: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        value = _value(obj, name, None)
        if value not in (None, "", []):
            return value
        value = attributes.get(name)
        if value not in (None, "", []):
            return value
    return None


def _parse_evidence_ids(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("["):
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError:
                value = re.split(r"[,;\s]+", stripped)
        else:
            value = re.split(r"[,;\s]+", stripped)
    if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray)):
        value = [value]
    return _unique(str(item).strip() for item in value if str(item).strip())


def _episode_fields(content: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for key, label in EPISODE_FIELD_LABELS.items():
        match = re.search(
            rf"(?:^|\n){re.escape(label)}[：:]\s*([^\n。；]+)", content
        )
        if match:
            fields[key] = match.group(1).strip()
    relationship_status = re.search(
        r"关系状态(?:为|[：:])\s*([A-Za-z_][A-Za-z0-9_-]*)", content
    )
    if relationship_status:
        fields["verification_status"] = relationship_status.group(1)
    if "claim_nature" in fields:
        fields["claim_nature"] = CLAIM_NATURE_VALUES.get(
            fields["claim_nature"], fields["claim_nature"]
        )
    return fields


def _query_terms(query: str) -> list[str]:
    terms: set[str] = set()
    terms.update(token.casefold() for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9/+.-]*", query))
    terms.update(chunk for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", query))
    chinese_text = "".join(re.findall(r"[\u4e00-\u9fff]+", query))
    for size in (2, 3, 4):
        terms.update(
            chinese_text[index : index + size]
            for index in range(0, max(len(chinese_text) - size + 1, 0))
        )
    return sorted((term for term in terms if len(term) >= 2), key=lambda item: (-len(item), item))[:80]


def _unique(values: Any) -> list[Any]:
    seen: set[Any] = set()
    result: list[Any] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"1", "true", "yes", "y"}


def _string_or_none(value: Any) -> str | None:
    return None if value in (None, "") else str(value)


def _business_confidence(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        if value >= 0.8:
            return "high"
        if value >= 0.6:
            return "medium"
        if value >= 0.4:
            return "medium-low"
        return "low"
    return str(value).strip().casefold()


def _require_group_id(group_id: Any) -> str:
    if not isinstance(group_id, str) or not group_id.strip():
        raise ValueError("group_id 必须是非空字符串")
    return group_id.strip()
