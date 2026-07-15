from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import networkx as nx

from app.config import Settings
from app.services.retrieval import SiliconFlowReranker


ProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]
CommunityBuilder = Callable[[Any, Any, list[str]], Awaitable[tuple[list[Any], list[Any]]]]
GOVERNANCE_GROUP_ID = "semiconductor_dc_kg"
COMMUNITY_LLM_CONCURRENCY = 4


COMMUNITY_PROJECTION_QUERY = """
MATCH (source:Entity {group_id: $group_id})
      -[:RELATES_TO {group_id: $group_id}]-
      (target:Entity {group_id: $group_id})
WITH source, collect(DISTINCT target.uuid) AS neighbors
RETURN source.uuid AS uuid, source.name AS name,
       coalesce(source.summary, '') AS summary, neighbors
"""


SAGA_LIST_QUERY = """
MATCH (s:Saga {group_id: $group_id})
OPTIONAL MATCH (s)-[:HAS_EPISODE]->(e:Episodic {group_id: $group_id})
RETURN s.uuid AS uuid, s.name AS name, coalesce(s.summary, '') AS summary,
       s.legacy_saga_key AS legacy_saga_key,
       s.saga_key AS saga_key,
       s.layer_id AS layer_id,
       s.layer_name AS layer_name,
       s.fact_set_name AS fact_set_name,
       s.fact_set_type AS fact_set_type,
       s.fact_set_description AS fact_set_description,
       s.display_name AS display_name,
       count(e) AS episode_count,
       s.last_summarized_at AS last_summarized_at,
       s.last_summarized_episode_valid_at AS last_summarized_episode_valid_at
ORDER BY s.layer_id, s.fact_set_name, s.name, s.uuid
"""

COMMUNITY_LIST_QUERY = """
MATCH (c:Community {group_id: $group_id})
OPTIONAL MATCH (c)-[:HAS_MEMBER]->(e:Entity {group_id: $group_id})
WITH c, count(e) AS member_count,
     [
       name IN collect(DISTINCT e.name)
       WHERE name IS NOT NULL AND NOT name =~ 'E[0-9]+-.*'
     ][0..8] AS representative_entities
RETURN c.uuid AS uuid, c.name AS name, coalesce(c.summary, '') AS summary,
       member_count, representative_entities, c.created_at AS created_at
ORDER BY member_count DESC, c.name, c.uuid
"""

SAGA_DETAIL_QUERY = """
MATCH (s:Saga {uuid: $saga_id, group_id: $group_id})
OPTIONAL MATCH (s)-[:HAS_EPISODE]->(e:Episodic {group_id: $group_id})
RETURN s.uuid AS uuid, s.name AS name, coalesce(s.summary, '') AS summary,
       coalesce(s.display_name, s.name) AS display_name,
       count(e) AS episode_count, max(e.valid_at) AS max_valid_at
"""

SAGA_EPISODE_PAGE_QUERY = """
MATCH (s:Saga {uuid: $saga_id, group_id: $group_id})-[:HAS_EPISODE]->
      (e:Episodic {group_id: $group_id})
RETURN e.content AS content, e.valid_at AS valid_at
ORDER BY e.valid_at ASC, e.created_at ASC, e.uuid ASC
SKIP $skip LIMIT $limit
"""

SAGA_UPDATE_QUERY = """
MATCH (s:Saga {uuid: $saga_id, group_id: $group_id})
SET s.summary = $summary,
    s.last_summarized_at = $last_summarized_at,
    s.last_summarized_episode_valid_at = $last_summarized_episode_valid_at
RETURN count(s) AS updated
"""

REPLACE_GROUP_COMMUNITIES_QUERY = """
CALL () {
  MATCH (c:Community {group_id: $group_id})
  DETACH DELETE c
  RETURN count(c) AS deleted_count
}
CALL () {
  UNWIND $communities AS item
  CREATE (c:Community {
    uuid: item.uuid,
    name: item.name,
    group_id: item.group_id,
    summary: item.summary,
    name_embedding: item.name_embedding,
    created_at: item.created_at
  })
  RETURN count(c) AS community_count
}
CALL () {
  UNWIND $memberships AS item
  MATCH (c:Community {uuid: item.source_node_uuid, group_id: $group_id})
  MATCH (e:Entity {uuid: item.target_node_uuid, group_id: $group_id})
  CREATE (c)-[membership:HAS_MEMBER {
    uuid: item.uuid,
    group_id: item.group_id,
    created_at: item.created_at
  }]->(e)
  RETURN count(membership) AS membership_count
}
RETURN community_count, membership_count
"""


async def build_bounded_communities(
    driver: Any,
    llm_client: Any,
    group_ids: list[str],
) -> tuple[list[Any], list[Any]]:
    """构建有界社区，避免 Graphiti 标签传播在部分图结构上振荡。"""
    if group_ids != [GOVERNANCE_GROUP_ID]:
        raise ValueError(f"社区构建仅允许分组 {GOVERNANCE_GROUP_ID}")

    response = driver.execute_query(
        COMMUNITY_PROJECTION_QUERY,
        group_id=GOVERNANCE_GROUP_ID,
    )
    if inspect.isawaitable(response):
        response = await response
    records = response[0] if isinstance(response, tuple) else response.records

    graph = nx.Graph()
    entities: dict[str, dict[str, str]] = {}
    for raw_record in records:
        record = dict(raw_record)
        entity_uuid = str(record["uuid"])
        entities[entity_uuid] = {
            "name": str(record.get("name") or entity_uuid),
            "summary": str(record.get("summary") or ""),
        }
        for neighbor in record.get("neighbors") or []:
            graph.add_edge(entity_uuid, str(neighbor))

    if graph.number_of_nodes() == 0:
        return [], []

    detected = await asyncio.to_thread(
        nx.community.louvain_communities,
        graph,
        seed=42,
    )
    clusters = sorted(
        (sorted(str(uuid) for uuid in cluster) for cluster in detected if len(cluster) > 1),
        key=lambda cluster: (-len(cluster), cluster[0]),
    )

    from graphiti_core.edges import CommunityEdge
    from graphiti_core.nodes import CommunityNode

    semaphore = asyncio.Semaphore(COMMUNITY_LLM_CONCURRENCY)

    async def build_cluster(cluster_index: int, members: list[str]):
        ranked_members = sorted(
            members,
            key=lambda uuid: (-graph.degree(uuid), entities.get(uuid, {}).get("name", uuid)),
        )
        context_lines = []
        for uuid in ranked_members[:30]:
            entity = entities.get(uuid, {"name": uuid, "summary": ""})
            summary = entity["summary"].replace("\n", " ")[:240]
            context_lines.append(f"- {entity['name']}：{summary}")
        messages = _community_summary_messages(context_lines, len(members))
        async with semaphore:
            response = await llm_client.generate_response(
                messages,
                response_model=None,
                prompt_name="governance.summarize_community",
            )

        fallback_names = [entities.get(uuid, {}).get("name", uuid) for uuid in ranked_members[:3]]
        name = str(response.get("name") or "、".join(fallback_names) or f"知识社区{cluster_index}")
        summary = str(response.get("summary") or "该社区由图谱中的高关联实体组成。")
        now = datetime.now(UTC)
        node = CommunityNode(
            name=name[:120],
            group_id=GOVERNANCE_GROUP_ID,
            labels=["Community"],
            created_at=now,
            summary=summary,
        )
        edges = [
            CommunityEdge(
                group_id=GOVERNANCE_GROUP_ID,
                source_node_uuid=node.uuid,
                target_node_uuid=uuid,
                created_at=now,
            )
            for uuid in members
        ]
        return node, edges

    built = await asyncio.gather(
        *(build_cluster(index, cluster) for index, cluster in enumerate(clusters, start=1))
    )
    nodes = [node for node, _ in built]
    edges = [edge for _, memberships in built for edge in memberships]
    return nodes, edges


def _community_summary_messages(context_lines: list[str], member_count: int) -> list[Any]:
    from graphiti_core.prompts.models import Message

    return [
        Message(
            role="system",
            content=(
                "你是半导体产业知识图谱治理助手。根据社区内实体生成简洁中文名称和摘要，"
                "只能概括输入内容，不得补充未提供的交易、客户或合作结论。"
            ),
        ),
        Message(
            role="user",
            content=(
                f"该社区共有 {member_count} 个相互关联实体，以下是按连接度选取的代表实体：\n"
                + "\n".join(context_lines)
                + '\n\n只返回 JSON 对象：{"name":"社区名称","summary":"社区摘要"}。'
            ),
        ),
    ]


class GovernanceService:
    def __init__(
        self,
        driver: Any,
        *,
        llm_client: Any,
        embedder: Any,
        group_id: str,
        saga_page_size: int = 75,
        community_builder: CommunityBuilder | None = None,
        owned_graphiti: Any | None = None,
        owned_cross_encoder: Any | None = None,
    ) -> None:
        if group_id != GOVERNANCE_GROUP_ID:
            raise ValueError(f"治理写操作仅允许分组 {GOVERNANCE_GROUP_ID}")
        if saga_page_size <= 0:
            raise ValueError("Saga 分页大小必须大于 0")
        self.driver = driver
        self.llm_client = llm_client
        self.embedder = embedder
        self.group_id = group_id
        self.saga_page_size = saga_page_size
        self._community_builder = community_builder
        self._owned_graphiti = owned_graphiti
        self._owned_cross_encoder = owned_cross_encoder

    @classmethod
    def from_settings(cls, settings: Settings) -> "GovernanceService":
        if not settings.siliconflow_api_key:
            raise RuntimeError("SILICONFLOW_API_KEY 未配置")

        from graphiti_core import Graphiti
        from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
        from graphiti_core.llm_client import LLMConfig
        from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient

        llm_config = LLMConfig(
            api_key=settings.siliconflow_api_key,
            model=settings.llm_model,
            small_model=settings.llm_model,
            base_url=settings.llm_base_url,
            temperature=0,
        )
        llm_client = OpenAIGenericClient(
            config=llm_config, structured_output_mode="json_object"
        )
        embedder = OpenAIEmbedder(
            config=OpenAIEmbedderConfig(
                api_key=settings.siliconflow_api_key,
                base_url=settings.embedding_base_url,
                embedding_model=settings.embedding_model,
            )
        )
        cross_encoder = SiliconFlowReranker(
            api_key=settings.siliconflow_api_key,
            base_url=settings.llm_base_url,
            model=settings.reranker_model,
        )
        graphiti = Graphiti(
            settings.neo4j_uri,
            settings.neo4j_user,
            settings.neo4j_password,
            llm_client=llm_client,
            embedder=embedder,
            cross_encoder=cross_encoder,
        )
        return cls(
            graphiti.driver,
            llm_client=llm_client,
            embedder=embedder,
            group_id=settings.group_id,
            owned_graphiti=graphiti,
            owned_cross_encoder=cross_encoder,
        )

    async def list_sagas(self) -> list[dict[str, Any]]:
        return await self._execute(SAGA_LIST_QUERY, group_id=self.group_id)

    async def list_communities(self) -> list[dict[str, Any]]:
        return await self._execute(COMMUNITY_LIST_QUERY, group_id=self.group_id)

    async def summarize_saga(
        self, saga_id: str, progress: ProgressCallback | None = None
    ) -> dict[str, Any]:
        records = await self._execute(
            SAGA_DETAIL_QUERY, saga_id=saga_id, group_id=self.group_id
        )
        if not records or not records[0].get("uuid"):
            raise ValueError("Saga 不存在或不属于当前图谱")

        saga = records[0]
        episode_count = int(saga.get("episode_count") or 0)
        if episode_count == 0:
            return {
                "saga_id": saga_id,
                "summary": str(saga.get("summary") or ""),
                "episode_count": 0,
                "pages": 0,
            }

        page_summaries: list[str] = []
        page_count = (episode_count + self.saga_page_size - 1) // self.saga_page_size
        for page_index, skip in enumerate(
            range(0, episode_count, self.saga_page_size), start=1
        ):
            page = await self._execute(
                SAGA_EPISODE_PAGE_QUERY,
                saga_id=saga_id,
                group_id=self.group_id,
                skip=skip,
                limit=self.saga_page_size,
            )
            contents = [str(item["content"]) for item in page if item.get("content")]
            if contents:
                page_summaries.append(
                    await self._summarize(str(saga.get("display_name") or saga["name"]), contents)
                )
            await _notify(
                progress,
                {
                    "progress": 10 + int(page_index / page_count * 65),
                    "message": f"已汇总 {page_index}/{page_count} 页事件",
                },
            )

        if not page_summaries:
            summary = str(saga.get("summary") or "")
        elif len(page_summaries) == 1:
            summary = page_summaries[0]
        else:
            await _notify(progress, {"progress": 82, "message": "正在归并分页摘要"})
            summary = await self._summarize(str(saga.get("display_name") or saga["name"]), page_summaries)

        summarized_at = datetime.now(UTC)
        await self._execute(
            SAGA_UPDATE_QUERY,
            saga_id=saga_id,
            group_id=self.group_id,
            summary=summary,
            last_summarized_at=summarized_at,
            last_summarized_episode_valid_at=saga.get("max_valid_at"),
        )
        await _notify(progress, {"progress": 100, "message": "Saga 摘要已更新"})
        return {
            "saga_id": saga_id,
            "summary": summary,
            "episode_count": episode_count,
            "pages": page_count,
        }

    async def rebuild_communities(
        self, progress: ProgressCallback | None = None
    ) -> dict[str, int]:
        await _notify(progress, {"progress": 10, "message": "正在计算实体社区"})
        builder = self._community_builder or build_bounded_communities
        community_nodes, community_edges = await builder(
            self.driver, self.llm_client, [self.group_id]
        )
        objects = [*community_nodes, *community_edges]
        if any(getattr(item, "group_id", None) != self.group_id for item in objects):
            raise ValueError("Community 构建结果包含其他分组")

        await _notify(progress, {"progress": 60, "message": "正在生成社区向量"})
        await asyncio.gather(
            *(node.generate_name_embedding(self.embedder) for node in community_nodes)
        )
        await _notify(progress, {"progress": 80, "message": "正在保存社区结构"})
        communities = [
            {
                "uuid": node.uuid,
                "name": getattr(node, "name", node.uuid),
                "group_id": node.group_id,
                "summary": getattr(node, "summary", ""),
                "name_embedding": getattr(node, "name_embedding", None),
                "created_at": getattr(node, "created_at", datetime.now(UTC)),
            }
            for node in community_nodes
        ]
        memberships = [
            {
                "uuid": edge.uuid,
                "source_node_uuid": edge.source_node_uuid,
                "target_node_uuid": edge.target_node_uuid,
                "group_id": edge.group_id,
                "created_at": edge.created_at,
            }
            for edge in community_edges
        ]
        await self._execute(
            REPLACE_GROUP_COMMUNITIES_QUERY,
            group_id=self.group_id,
            communities=communities,
            memberships=memberships,
        )
        await _notify(progress, {"progress": 100, "message": "Community 重建完成"})
        return {
            "community_count": len(community_nodes),
            "membership_count": len(community_edges),
        }

    async def _summarize(self, saga_name: str, contents: list[str]) -> str:
        from graphiti_core.prompts import prompt_library
        from graphiti_core.utils.text_utils import MAX_SUMMARY_CHARS

        messages = prompt_library.summarize_sagas.summarize_saga(
            {
                "saga_name": saga_name,
                "existing_summary": "",
                "episodes": contents,
            }
        )
        messages[-1].content += (
            '\n\n只返回 JSON 对象：{"summary":"实际摘要内容"}。'
            "summary 的值必须是基于上述事实生成的中文摘要，不要返回 JSON Schema、字段定义或示例。"
        )
        response = await self.llm_client.generate_response(
            messages,
            response_model=None,
            prompt_name="summarize_sagas.summarize_saga",
        )
        summary = str(response.get("summary") or "").strip()
        if not summary:
            raise ValueError("大模型未生成 Saga 摘要")
        return summary[:MAX_SUMMARY_CHARS]

    async def _execute(self, query: str, **parameters: Any) -> list[dict[str, Any]]:
        response = self.driver.execute_query(query, **parameters)
        if inspect.isawaitable(response):
            response = await response
        records = response[0] if isinstance(response, tuple) else response.records
        return [
            {key: _native_value(value) for key, value in dict(record).items()}
            for record in records
        ]

    async def close(self) -> None:
        if self._owned_cross_encoder is not None:
            await self._owned_cross_encoder.close()
        if self._owned_graphiti is not None:
            result = self._owned_graphiti.close()
            if inspect.isawaitable(result):
                await result


async def _notify(
    callback: ProgressCallback | None, payload: dict[str, Any]
) -> None:
    if callback is not None:
        await callback(payload)


def _native_value(value: Any) -> Any:
    to_native = getattr(value, "to_native", None)
    return to_native() if callable(to_native) else value
