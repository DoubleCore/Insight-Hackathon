from __future__ import annotations

import asyncio
import inspect
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any, Literal

from app.config import Settings
from app.schemas import GraphEdge, GraphNode, GraphPayload


GraphView = Literal["business", "temporal", "governance"]

NODE_LABELS = {
    "ValueChainLayer": "产业链层级",
    "MajorSegment": "业务域",
    "Subsegment": "细分环节",
    "Company": "企业",
    "ProductService": "产品服务",
    "DigitalChina": "神州数码",
    "Entity": "事实实体",
    "Episodic": "事件",
    "Saga": "事件序列",
    "Community": "知识社区",
}

RELATION_LABELS = {
    "HAS_MAJOR_SEGMENT": "包含业务域",
    "HAS_SUBSEGMENT": "包含细分环节",
    "LEADER_IN": "龙头企业",
    "HAS_LEADERSHIP_CLAIM": "具有龙头判断",
    "ASSERTS_LEADER_IN": "判断为龙头",
    "SUPPORTED_BY": "证据支持",
    "SUPPLIES_TO": "供应给",
    "HAS_EPISODE": "包含事件",
    "NEXT_EPISODE": "下一事件",
    "MENTIONS": "提及",
}
RELATION_NAME_LABELS = {
    "PRODUCES": "生产",
    "SELLS": "销售",
    "USES": "使用",
    "PROCURES": "采购",
    "INTEGRATES": "集成",
    "SUPPLIES_TO": "供应给",
    "PRESUMED_COMPETITOR": "推定竞争",
    "IS_GLOBAL_LEADER_IN": "全球龙头",
    "IS_DOMESTIC_LEADER_IN": "国内龙头",
    "IS_SUBSECTOR_LEADER_IN": "细分龙头",
    "IS_SUBSECTOR_LEADER": "细分龙头",
    "IS_LEADER_IN": "龙头",
    "HAS_DIGITAL_CHINA_RELATION": "神州数码关系",
    "PARTNERS_WITH": "合作伙伴",
}

BUSINESS_RELATION_TYPES = [
    "HAS_MAJOR_SEGMENT",
    "HAS_SUBSEGMENT",
    "包含产品服务",
    "LEADER_IN",
    "生产",
    "销售",
    "使用",
    "集成",
    "供应给",
    "SUPPLIES_TO",
    "公开关系",
    "生态适配",
    "合资建设",
    "联合研发",
    "方案协同",
]

BUSINESS_QUERY = """
MATCH (source:SemiconductorKG)-[relation]->(target:SemiconductorKG)
WHERE type(relation) IN $relation_types
  AND any(label IN labels(source) WHERE label IN $node_labels)
  AND any(label IN labels(target) WHERE label IN $node_labels)
WITH source, relation, target
ORDER BY CASE type(relation)
  WHEN 'HAS_MAJOR_SEGMENT' THEN 1
  WHEN 'HAS_SUBSEGMENT' THEN 2
  WHEN '包含产品服务' THEN 3
  WHEN 'LEADER_IN' THEN 4
  ELSE 5 END,
  coalesce(source.name, ''), coalesce(target.name, '')
LIMIT $limit
RETURN elementId(source) AS source_id, labels(source) AS source_labels,
       properties(source) AS source_properties,
       elementId(relation) AS edge_id, type(relation) AS edge_type,
       properties(relation) AS edge_properties,
       elementId(target) AS target_id, labels(target) AS target_labels,
       properties(target) AS target_properties
"""

TEMPORAL_QUERY = """
MATCH (source:Entity)-[relation:RELATES_TO {group_id: $group_id}]->(target:Entity)
WHERE source.group_id = $group_id AND target.group_id = $group_id
WITH source, relation, target
ORDER BY coalesce(
  toString(relation.last_verified_at),
  toString(relation.reference_time),
  toString(relation.created_at),
  ''
) DESC
LIMIT $limit
RETURN elementId(source) AS source_id, labels(source) AS source_labels,
       properties(source) AS source_properties,
       elementId(relation) AS edge_id, type(relation) AS edge_type,
       properties(relation) AS edge_properties,
       elementId(target) AS target_id, labels(target) AS target_labels,
       properties(target) AS target_properties
"""

GOVERNANCE_QUERY = """
CALL () {
  MATCH (source:Saga {group_id: $group_id})
  OPTIONAL MATCH (source)-[relation:HAS_EPISODE]->(target:Episodic {group_id: $group_id})
  RETURN source, relation, target LIMIT $episode_limit
  UNION ALL
  MATCH (source:Episodic {group_id: $group_id})-[relation:MENTIONS]->(target:Entity {group_id: $group_id})
  RETURN source, relation, target LIMIT $mention_limit
  UNION ALL
  MATCH (source:Community {group_id: $group_id})
  OPTIONAL MATCH (source)-[relation]-(target:Entity {group_id: $group_id})
  RETURN source, relation, target LIMIT $community_limit
}
WITH source, relation, target
LIMIT $limit
RETURN elementId(source) AS source_id, labels(source) AS source_labels,
       properties(source) AS source_properties,
       CASE WHEN relation IS NULL THEN NULL ELSE elementId(relation) END AS edge_id,
       CASE WHEN relation IS NULL THEN NULL ELSE type(relation) END AS edge_type,
       CASE WHEN relation IS NULL THEN {} ELSE properties(relation) END AS edge_properties,
       CASE WHEN target IS NULL THEN NULL ELSE elementId(target) END AS target_id,
       CASE WHEN target IS NULL THEN [] ELSE labels(target) END AS target_labels,
       CASE WHEN target IS NULL THEN {} ELSE properties(target) END AS target_properties
"""

STATS_QUERY = """
CALL () { MATCH (n:SemiconductorKG) RETURN count(n) AS industry_nodes }
CALL () { MATCH (:SemiconductorKG)-[r]->(:SemiconductorKG) RETURN count(r) AS industry_edges }
CALL () { MATCH (n:Entity {group_id: $group_id}) RETURN count(n) AS entities }
CALL () { MATCH (n:Episodic {group_id: $group_id}) RETURN count(n) AS episodes }
CALL () { MATCH ()-[r:RELATES_TO {group_id: $group_id}]->() RETURN count(r) AS facts }
CALL () { MATCH (n:Saga {group_id: $group_id}) RETURN count(n) AS sagas }
CALL () { MATCH (n:Community {group_id: $group_id}) RETURN count(n) AS communities }
RETURN industry_nodes, industry_edges, entities, episodes, facts, sagas, communities
"""


class Neo4jGraphService:
    def __init__(self, driver: Any, *, group_id: str) -> None:
        if not group_id.strip():
            raise ValueError("group_id 不能为空")
        self.driver = driver
        self.group_id = group_id

    @classmethod
    def from_settings(cls, settings: Settings) -> "Neo4jGraphService":
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        return cls(driver, group_id=settings.group_id)

    async def get_view(self, view: str, *, limit: int = 300) -> GraphPayload:
        if view not in {"business", "temporal", "governance"}:
            raise ValueError("不支持的图谱视图")
        if not 1 <= limit <= 500:
            raise ValueError("limit 必须在 1 到 500 之间")
        query = {
            "business": BUSINESS_QUERY,
            "temporal": TEMPORAL_QUERY,
            "governance": GOVERNANCE_QUERY,
        }[view]
        parameters: dict[str, Any] = {"limit": limit}
        if view == "business":
            parameters.update(
                {
                    "relation_types": BUSINESS_RELATION_TYPES,
                    "node_labels": [
                        "ValueChainLayer",
                        "MajorSegment",
                        "Subsegment",
                        "Company",
                        "ProductService",
                        "DigitalChina",
                    ],
                }
            )
        else:
            parameters["group_id"] = self.group_id
        if view == "governance":
            parameters.update(
                {
                    "episode_limit": max(1, int(limit * 0.4)),
                    "mention_limit": max(1, int(limit * 0.5)),
                    "community_limit": max(1, limit - int(limit * 0.9)),
                }
            )
        records = await self._execute(query, **parameters)
        return _graph_payload(records)

    async def get_stats(self) -> dict[str, int]:
        records = await self._execute(STATS_QUERY, group_id=self.group_id)
        if not records:
            return {
                "industry_nodes": 0,
                "industry_edges": 0,
                "entities": 0,
                "episodes": 0,
                "facts": 0,
                "sagas": 0,
                "communities": 0,
            }
        return {key: int(value or 0) for key, value in records[0].items()}

    async def _execute(self, query: str, **parameters: Any) -> list[dict[str, Any]]:
        def run() -> Any:
            return self.driver.execute_query(query, **parameters, routing_="r")

        response = await asyncio.to_thread(run)
        if inspect.isawaitable(response):
            response = await response
        records = response[0] if isinstance(response, tuple) else response.records
        return [dict(record) for record in records]

    async def close(self) -> None:
        result = self.driver.close()
        if inspect.isawaitable(result):
            await result


def _graph_payload(records: list[dict[str, Any]]) -> GraphPayload:
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    for record in records:
        _add_node(
            nodes,
            record.get("source_id"),
            record.get("source_labels") or [],
            record.get("source_properties") or {},
        )
        _add_node(
            nodes,
            record.get("target_id"),
            record.get("target_labels") or [],
            record.get("target_properties") or {},
        )
        if record.get("edge_id") and record.get("target_id"):
            original_type = str(record.get("edge_type") or "关系")
            properties = _safe_properties(record.get("edge_properties") or {})
            display_label = _edge_display_label(original_type, properties)
            properties.setdefault("原始关系类型", original_type)
            properties.setdefault("关系名称", display_label)
            properties.setdefault("display_label", display_label)
            if properties.get("name") is not None:
                properties.setdefault("原始关系名", properties["name"])
            edges.append(
                GraphEdge(
                    id=str(record["edge_id"]),
                    source=str(record["source_id"]),
                    target=str(record["target_id"]),
                    type=display_label,
                    properties=properties,
                )
            )
    return GraphPayload(nodes=list(nodes.values()), edges=edges)


def _add_node(
    nodes: dict[str, GraphNode],
    node_id: Any,
    labels: list[str],
    properties: Mapping[str, Any],
) -> None:
    if node_id is None or str(node_id) in nodes:
        return
    safe = _safe_properties(properties)
    name = safe.get("名称") or safe.get("name") or safe.get("title") or str(node_id)
    safe.setdefault("名称", name)
    translated = [NODE_LABELS.get(label, label) for label in labels if label != "SemiconductorKG"]
    safe.setdefault("节点类型", translated[0] if translated else "实体")
    nodes[str(node_id)] = GraphNode(
        id=str(node_id), labels=translated or ["实体"], properties=safe
    )


def _safe_properties(properties: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in properties.items():
        if "embedding" in str(key).casefold():
            continue
        result[str(key)] = _safe_value(value)
    return result


def _edge_display_label(edge_type: str, properties: Mapping[str, Any]) -> str:
    raw_name = str(properties.get("name") or "").strip()
    if raw_name:
        return RELATION_NAME_LABELS.get(raw_name, raw_name)
    if edge_type == "RELATES_TO":
        fact = str(properties.get("fact") or "").strip()
        if "晶圆代工" in fact or "代工" in fact:
            return "晶圆代工"
        if "供应" in fact or "供货" in fact:
            return "供应"
        if "授权" in fact:
            return "授权"
        if "合作" in fact:
            return "合作"
        if "公开关系" in fact:
            return "公开关系"
        if "推定竞争" in fact:
            return "推定竞争"
        if "生产" in fact:
            return "生产"
        if "销售" in fact:
            return "销售"
        if "使用" in fact:
            return "使用"
        if "采购" in fact:
            return "采购"
        if "集成" in fact:
            return "集成"
        if "龙头" in fact:
            return "龙头"
        return "事实连接"
    return RELATION_LABELS.get(edge_type, edge_type)


def _safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= 3000 else value[:3000] + "..."
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe_value(item) for item in list(value)[:100]]
    if hasattr(value, "iso_format"):
        return value.iso_format()
    return str(value)
