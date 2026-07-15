from __future__ import annotations

import asyncio
import inspect
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any, Literal
from urllib.parse import unquote

from app.config import Settings
from app.schemas import GraphEdge, GraphNode, GraphPayload


UnifiedBranch = Literal[
    "hierarchy",
    "business",
    "facts",
    "timeline",
    "saga",
    "community",
    "evidence",
    "digital_china",
]

GROUP_ID = "semiconductor_dc_kg"
L1_NAMES = ["上游", "中游", "下游"]
RELATION_LABELS = {
    "HAS_EPISODE": "包含事件",
    "MENTIONS": "提及",
    "HAS_MEMBER": "包含成员",
    "SUPPORTED_BY": "证据支持",
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
BUSINESS_RELATIONS = ["生产", "销售", "使用", "采购", "集成", "供应给", "SUPPLIES_TO", "公开关系", "生态适配"]
LEVEL_BY_LABEL = {
    "L1 产业层级": 0,
    "L2 业务域": 1,
    "L3 产业环节": 2,
    "L4 细分环节": 3,
    "产品服务": 4,
    "企业": 5,
    "神州数码": 5,
    "事实实体": 6,
    "事件": 7,
    "事件序列": 8,
    "知识社区": 8,
    "证据": 8,
}
LABEL_TRANSLATIONS = {
    "Subsegment": "L4 细分环节",
    "ProductService": "产品服务",
    "Company": "企业",
    "DigitalChina": "神州数码",
    "Entity": "事实实体",
    "Episodic": "事件",
    "Saga": "事件序列",
    "Community": "知识社区",
    "Evidence": "证据",
}

L1_CHILDREN_QUERY = """
MATCH (s:Subsegment:SemiconductorKG)
WHERE s.l1 = $l1
RETURN DISTINCT s.l2 AS child_name, count(s) AS child_count
ORDER BY child_name
SKIP $skip LIMIT $limit
"""

L2_CHILDREN_QUERY = """
MATCH (s:Subsegment:SemiconductorKG)
WHERE s.l1 = $l1 AND s.l2 = $l2
RETURN DISTINCT s.l3 AS child_name, count(s) AS child_count
ORDER BY child_name
SKIP $skip LIMIT $limit
"""

L3_CHILDREN_QUERY = """
MATCH (s:Subsegment:SemiconductorKG)
WHERE s.l1 = $l1 AND s.l2 = $l2 AND s.l3 = $l3
RETURN s.l4_name AS child_name, s.l4_code AS l4_code, properties(s) AS properties
ORDER BY child_name
SKIP $skip LIMIT $limit
"""

L4_BUSINESS_QUERY = """
MATCH (s:Subsegment:SemiconductorKG)-[relation:包含产品服务]->(target:ProductService:SemiconductorKG)
WHERE s.l1 = $l1 AND s.l2 = $l2 AND s.l3 = $l3 AND s.l4_name = $l4
RETURN $node_id AS source_id, ['Subsegment'] AS source_labels, properties(s) AS source_properties,
       elementId(relation) AS edge_id, type(relation) AS edge_type, properties(relation) AS edge_properties,
       coalesce(target.key, 'product:' + target.name) AS target_id, labels(target) AS target_labels,
       properties(target) AS target_properties
UNION ALL
MATCH (s:Subsegment:SemiconductorKG)-[:包含产品服务]->(product:ProductService:SemiconductorKG)<-[relation]-(source:Company:SemiconductorKG)
WHERE s.l1 = $l1 AND s.l2 = $l2 AND s.l3 = $l3 AND s.l4_name = $l4
  AND type(relation) IN $business_relations
RETURN coalesce(source.key, 'company:' + source.name) AS source_id, labels(source) AS source_labels,
       properties(source) AS source_properties,
       elementId(relation) AS edge_id, type(relation) AS edge_type, properties(relation) AS edge_properties,
       coalesce(product.key, 'product:' + product.name) AS target_id, labels(product) AS target_labels,
       properties(product) AS target_properties
ORDER BY edge_type
SKIP $skip LIMIT $limit
"""

PRODUCT_BUSINESS_QUERY = """
MATCH (source:Company:SemiconductorKG)-[relation]->(target:ProductService:SemiconductorKG)
WHERE target.name = $name AND type(relation) IN $business_relations
RETURN coalesce(source.key, 'company:' + source.name) AS source_id, labels(source) AS source_labels,
       properties(source) AS source_properties,
       elementId(relation) AS edge_id, type(relation) AS edge_type, properties(relation) AS edge_properties,
       coalesce(target.key, 'product:' + target.name) AS target_id, labels(target) AS target_labels,
       properties(target) AS target_properties
ORDER BY source.name
SKIP $skip LIMIT $limit
"""

FACTS_QUERY = """
MATCH (source:Entity {group_id: $group_id})-[relation:RELATES_TO {group_id: $group_id}]-(target:Entity {group_id: $group_id})
WHERE source.name = $name OR target.name = $name
RETURN 'entity:' + source.name AS source_id, labels(source) AS source_labels, properties(source) AS source_properties,
       elementId(relation) AS edge_id, type(relation) AS edge_type, properties(relation) AS edge_properties,
       'entity:' + target.name AS target_id, labels(target) AS target_labels, properties(target) AS target_properties
ORDER BY coalesce(relation.last_verified_at, relation.valid_at, relation.created_at) DESC
SKIP $skip LIMIT $limit
"""

TIMELINE_QUERY = """
MATCH (entity:Entity {group_id: $group_id, name: $name})<-[:MENTIONS]-(episode:Episodic {group_id: $group_id})
RETURN 'entity:' + entity.name AS source_id, labels(entity) AS source_labels, properties(entity) AS source_properties,
       elementId(episode) + ':mentions' AS edge_id, 'MENTIONS' AS edge_type, {} AS edge_properties,
       'episode:' + episode.uuid AS target_id, labels(episode) AS target_labels, properties(episode) AS target_properties
ORDER BY episode.valid_at DESC, episode.created_at DESC
SKIP $skip LIMIT $limit
"""

SAGA_QUERY = """
MATCH (saga:Saga {group_id: $group_id})-[:HAS_EPISODE]->(episode:Episodic {group_id: $group_id})-[:MENTIONS]->(entity:Entity {group_id: $group_id, name: $name})
RETURN 'saga:' + saga.uuid AS source_id, labels(saga) AS source_labels, properties(saga) AS source_properties,
       elementId(saga) + ':' + elementId(episode) AS edge_id, 'HAS_EPISODE' AS edge_type, {} AS edge_properties,
       'episode:' + episode.uuid AS target_id, labels(episode) AS target_labels, properties(episode) AS target_properties
ORDER BY saga.name, episode.valid_at DESC
SKIP $skip LIMIT $limit
"""

COMMUNITY_QUERY = """
MATCH (community:Community {group_id: $group_id})-[:HAS_MEMBER]->(entity:Entity {group_id: $group_id, name: $name})
RETURN 'community:' + community.uuid AS source_id, labels(community) AS source_labels, properties(community) AS source_properties,
       community.uuid + ':' + entity.uuid AS edge_id, 'HAS_MEMBER' AS edge_type, {} AS edge_properties,
       'entity:' + entity.name AS target_id, labels(entity) AS target_labels, properties(entity) AS target_properties
ORDER BY community.name
SKIP $skip LIMIT $limit
"""

EVIDENCE_QUERY = """
MATCH (anchor:SemiconductorKG)
WHERE coalesce(anchor.name, anchor.`名称`, anchor.title) = $name
OPTIONAL MATCH (anchor)-[r]-()
WITH anchor, collect(r) AS relationships
WITH anchor,
     coalesce(anchor.evidence_ids, []) + coalesce(anchor.`证据ID`, []) AS node_evidence_ids,
     relationships
UNWIND CASE WHEN relationships = [] THEN [null] ELSE relationships END AS relation
WITH anchor,
     node_evidence_ids
     + CASE WHEN relation IS NULL THEN [] ELSE coalesce(relation.evidence_ids, []) END
     + CASE WHEN relation IS NULL THEN [] ELSE coalesce(relation.`证据ID`, []) END AS evidence_ids
UNWIND evidence_ids AS evidence_id
WITH anchor, collect(DISTINCT toString(evidence_id)) AS property_evidence_ids
MATCH (e:Evidence:SemiconductorKG)
WHERE e.evidence_id IN property_evidence_ids
   OR e.key IN property_evidence_ids
WITH anchor, e
ORDER BY coalesce(e.source_grade, e.`来源等级`, ''), coalesce(e.publish_date, e.`发布日期`, '') DESC
RETURN $parent_id AS source_id, labels(anchor) AS source_labels, properties(anchor) AS source_properties,
       $parent_id + '->' + coalesce(e.key, e.evidence_id, elementId(e)) AS edge_id,
       'SUPPORTED_BY' AS edge_type,
       {evidence_id: coalesce(e.evidence_id, e.key), source_grade: coalesce(e.source_grade, e.`来源等级`)} AS edge_properties,
       coalesce(e.key, 'evidence:' + coalesce(e.evidence_id, e.name, elementId(e))) AS target_id,
       labels(e) AS target_labels, properties(e) AS target_properties
SKIP $skip LIMIT $limit
"""

DIGITAL_CHINA_QUERY = """
MATCH (company:Company:SemiconductorKG)
WHERE company.digital_china_relationship_status IS NOT NULL
  AND (
    $name = '神州数码'
    OR coalesce(company.name, company.`名称`) = $name
  )
OPTIONAL MATCH (dc:Company:SemiconductorKG)
WHERE coalesce(dc.name, dc.`名称`) = '神州数码'
WITH company, dc,
     CASE company.digital_china_relationship_status
       WHEN 'confirmed_public_relationship' THEN '公开确认'
       WHEN 'potential_fit' THEN '潜在匹配'
       WHEN 'needs_internal_validation' THEN '需内部验证'
       WHEN 'no_public_evidence' THEN '暂无公开证据'
       ELSE coalesce(company.digital_china_relationship_status, '未标注')
     END AS status_label
RETURN coalesce(company.key, 'company:' + company.name) AS source_id,
       labels(company) AS source_labels,
       properties(company) AS source_properties,
       'digital-china-status:' + coalesce(company.key, 'company:' + company.name) AS edge_id,
       '神州数码关系状态' AS edge_type,
       {
         display_label: '神州数码关系：' + status_label,
         `关系状态`: company.digital_china_relationship_status,
         `关系状态说明`: status_label,
         `关系类型`: company.digital_china_relationship_type,
         `判断依据`: company.digital_china_relationship_basis,
         `证据ID`: company.digital_china_evidence_ids,
         `置信度`: company.digital_china_confidence,
         `是否需要内部验证`: company.requires_internal_validation,
         `局限说明`: company.digital_china_limitations,
         relationship_status: company.digital_china_relationship_status,
         relationship_type: company.digital_china_relationship_type,
         relationship_basis: company.digital_china_relationship_basis,
         evidence_ids: company.digital_china_evidence_ids,
         confidence: company.digital_china_confidence,
         requires_internal_validation: company.requires_internal_validation,
         limitations: company.digital_china_limitations
       } AS edge_properties,
       coalesce(dc.key, 'company::神州数码') AS target_id,
       CASE WHEN dc IS NULL THEN ['DigitalChina', 'Company'] ELSE labels(dc) END AS target_labels,
       CASE WHEN dc IS NULL THEN {name: '神州数码', `名称`: '神州数码'} ELSE properties(dc) END AS target_properties
ORDER BY status_label, company.name
SKIP $skip LIMIT $limit
"""


class UnifiedGraphService:
    def __init__(self, driver: Any, *, group_id: str) -> None:
        if group_id != GROUP_ID:
            raise ValueError(f"统一图谱只允许分组 {GROUP_ID}")
        self.driver = driver
        self.group_id = group_id

    @classmethod
    def from_settings(cls, settings: Settings) -> "UnifiedGraphService":
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        return cls(driver, group_id=settings.group_id)

    async def root(self) -> GraphPayload:
        nodes = [
            _node(
                f"taxonomy:l1:{name}",
                "L1 产业层级",
                {"名称": name, "name": name, "branch_options": ["hierarchy"]},
                index=index,
                total=len(L1_NAMES),
                level=0,
            )
            for index, name in enumerate(L1_NAMES)
        ]
        return GraphPayload(nodes=nodes, edges=[])

    async def expand(
        self,
        node_id: str,
        *,
        branch: UnifiedBranch,
        cursor: str | None = None,
        limit: int = 20,
    ) -> GraphPayload:
        if branch not in {"hierarchy", "business", "facts", "timeline", "saga", "community", "evidence", "digital_china"}:
            raise ValueError("不支持的展开分支")
        if not 1 <= limit <= 50:
            raise ValueError("limit 必须在 1 到 50 之间")
        skip = int(cursor or 0)
        if branch == "hierarchy":
            return await self._expand_hierarchy(node_id, skip=skip, limit=limit)
        if branch == "business":
            return await self._expand_business(node_id, skip=skip, limit=limit)
        name = _name_from_node_id(node_id)
        query = {
            "facts": FACTS_QUERY,
            "timeline": TIMELINE_QUERY,
            "saga": SAGA_QUERY,
            "community": COMMUNITY_QUERY,
            "evidence": EVIDENCE_QUERY,
            "digital_china": DIGITAL_CHINA_QUERY,
        }[branch]
        records = await self._execute(
            query,
            group_id=self.group_id,
            name=name,
            parent_id=node_id,
            skip=skip,
            limit=limit,
        )
        return _payload_from_records(records, parent_id=node_id, include_evidence=branch == "evidence")

    async def _expand_hierarchy(self, node_id: str, *, skip: int, limit: int) -> GraphPayload:
        parts = _taxonomy_parts(node_id)
        kind = parts[0]
        if kind == "l1":
            records = await self._execute(L1_CHILDREN_QUERY, l1=parts[1], skip=skip, limit=limit)
            return _children_payload(
                node_id,
                records,
                child_label="L2 业务域",
                child_id=lambda name: f"taxonomy:l2:{parts[1]}|{name}",
                level=1,
            )
        if kind == "l2":
            l1, l2 = parts[1], parts[2]
            records = await self._execute(
                L2_CHILDREN_QUERY, l1=l1, l2=l2, skip=skip, limit=limit
            )
            return _children_payload(
                node_id,
                records,
                child_label="L3 产业环节",
                child_id=lambda name: f"taxonomy:l3:{l1}|{l2}|{name}",
                level=2,
            )
        if kind == "l3":
            l1, l2, l3 = parts[1], parts[2], parts[3]
            records = await self._execute(
                L3_CHILDREN_QUERY, l1=l1, l2=l2, l3=l3, skip=skip, limit=limit
            )
            nodes: list[GraphNode] = []
            edges: list[GraphEdge] = []
            for index, record in enumerate(records):
                name = str(record["child_name"])
                child_id = f"taxonomy:l4:{l1}|{l2}|{l3}|{name}"
                properties = _safe_properties(record.get("properties") or {})
                properties.update(
                    {"名称": name, "name": name, "branch_options": ["business", "facts"]}
                )
                nodes.append(_node(child_id, "L4 细分环节", properties, index=index, total=len(records), level=3))
                edges.append(_edge(f"{node_id}->{child_id}", node_id, child_id, "包含"))
            return GraphPayload(nodes=nodes, edges=edges)
        raise ValueError("该节点不支持层级展开")

    async def _expand_business(self, node_id: str, *, skip: int, limit: int) -> GraphPayload:
        if node_id.startswith("taxonomy:l4:"):
            _, l1, l2, l3, l4 = _taxonomy_parts(node_id)
            records = await self._execute(
                L4_BUSINESS_QUERY,
                node_id=node_id,
                l1=l1,
                l2=l2,
                l3=l3,
                l4=l4,
                business_relations=BUSINESS_RELATIONS,
                skip=skip,
                limit=limit,
            )
            return _payload_from_records(records, parent_id=node_id)
        records = await self._execute(
            PRODUCT_BUSINESS_QUERY,
            name=_name_from_node_id(node_id),
            business_relations=BUSINESS_RELATIONS,
            skip=skip,
            limit=limit,
        )
        return _payload_from_records(records, parent_id=node_id)

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


def _children_payload(
    parent_id: str,
    records: list[dict[str, Any]],
    *,
    child_label: str,
    child_id: Any,
    level: int,
) -> GraphPayload:
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    for index, record in enumerate(records):
        name = str(record["child_name"])
        node_id = child_id(name)
        nodes.append(
            _node(
                node_id,
                child_label,
                {
                    "名称": name,
                    "name": name,
                    "下级数量": int(record.get("child_count") or 0),
                    "branch_options": ["hierarchy"],
                },
                index=index,
                total=len(records),
                level=level,
            )
        )
        edges.append(_edge(f"{parent_id}->{node_id}", parent_id, node_id, "包含"))
    return GraphPayload(nodes=nodes, edges=edges)


def _payload_from_records(
    records: list[dict[str, Any]],
    *,
    parent_id: str,
    include_evidence: bool = False,
) -> GraphPayload:
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    parent_name = _name_from_node_id(parent_id)
    for record in records:
        if not include_evidence and (
            "Evidence" in (record.get("source_labels") or [])
            or "Evidence" in (record.get("target_labels") or [])
        ):
            continue
        source_id = str(record.get("source_id") or "")
        target_id = str(record.get("target_id") or "")
        source_properties = record.get("source_properties") or {}
        target_properties = record.get("target_properties") or {}
        if _record_name(source_properties, source_id) == parent_name:
            source_id = parent_id
        if _record_name(target_properties, target_id) == parent_name:
            target_id = parent_id
        if source_id and source_id != parent_id:
            _add_record_node(nodes, source_id, record.get("source_labels") or [], source_properties)
        if target_id and target_id != parent_id:
            _add_record_node(nodes, target_id, record.get("target_labels") or [], target_properties)
        if record.get("edge_id") and source_id and target_id:
            raw_type = str(record.get("edge_type") or "关系")
            edge_properties = record.get("edge_properties") or {}
            edges.append(
                _edge(
                    str(record["edge_id"]),
                    source_id,
                    target_id,
                    raw_type,
                    edge_properties,
                )
            )
    _assign_positions(nodes)
    return GraphPayload(nodes=list(nodes.values()), edges=edges)


def _record_name(properties: Mapping[str, Any], fallback_id: str) -> str:
    return str(properties.get("名称") or properties.get("name") or properties.get("title") or _name_from_node_id(fallback_id))


def _add_record_node(
    nodes: dict[str, GraphNode],
    node_id: str,
    labels: list[str],
    properties: Mapping[str, Any],
) -> None:
    if node_id in nodes:
        return
    label = next((LABEL_TRANSLATIONS.get(label, label) for label in labels if label != "SemiconductorKG"), "实体")
    safe = _safe_properties(properties)
    name = safe.get("名称") or safe.get("name") or safe.get("title") or _name_from_node_id(node_id)
    safe.setdefault("名称", name)
    safe.setdefault("name", name)
    branch_options = {
        "L4 细分环节": ["business", "facts"],
        "产品服务": ["business", "facts", "evidence"],
        "企业": ["business", "digital_china", "facts", "timeline", "saga", "community", "evidence"],
        "神州数码": ["business", "digital_china", "facts", "timeline", "saga", "community", "evidence"],
        "事实实体": ["facts", "timeline", "saga", "community", "evidence"],
        "事件": ["facts", "evidence"],
        "事件序列": ["saga"],
        "知识社区": ["community"],
    }.get(label, [])
    if label == "证据":
        safe.setdefault("来源标题", safe.get("title") or safe.get("来源标题") or name)
        safe.setdefault("来源链接", safe.get("url") or safe.get("来源链接"))
        safe.setdefault("来源等级", safe.get("source_grade") or safe.get("来源等级"))
        safe.setdefault("发布日期", safe.get("publish_date") or safe.get("发布日期"))
        safe.setdefault("检索时间", safe.get("retrieved_at") or safe.get("检索时间"))
        safe.setdefault("证据摘录", safe.get("excerpt") or safe.get("证据摘录"))
    safe.setdefault("branch_options", branch_options)
    nodes[node_id] = _node(
        node_id,
        label,
        safe,
        index=0,
        total=1,
        level=LEVEL_BY_LABEL.get(label, 6),
    )


def _assign_positions(nodes: dict[str, GraphNode]) -> None:
    by_level: dict[int, list[GraphNode]] = {}
    for node in nodes.values():
        by_level.setdefault(int(node.properties.get("level", 6)), []).append(node)
    for level, level_nodes in by_level.items():
        level_nodes.sort(key=lambda node: str(node.properties.get("名称", node.id)))
        total = len(level_nodes)
        for index, node in enumerate(level_nodes):
            node.properties["x"] = int((index - (total - 1) / 2) * 210)
            node.properties["y"] = int(level * 138)


def _node(
    node_id: str,
    label: str,
    properties: Mapping[str, Any],
    *,
    index: int,
    total: int,
    level: int,
) -> GraphNode:
    safe = _safe_properties(properties)
    safe.setdefault("节点类型", label)
    safe["level"] = level
    safe.setdefault("x", int((index - (total - 1) / 2) * 230))
    safe.setdefault("y", int(level * 138))
    return GraphNode(id=node_id, labels=[label], properties=safe)


def _edge(
    edge_id: str,
    source: str,
    target: str,
    edge_type: str,
    properties: Mapping[str, Any] | None = None,
) -> GraphEdge:
    safe = _safe_properties(properties or {})
    display_label = _edge_display_label(edge_type, safe)
    safe.setdefault("原始关系类型", edge_type)
    safe.setdefault("关系名称", display_label)
    safe.setdefault("display_label", display_label)
    raw_name = safe.get("name")
    if raw_name is not None:
        safe.setdefault("原始关系名", raw_name)
    return GraphEdge(id=edge_id, source=source, target=target, type=display_label, properties=safe)


def _edge_display_label(edge_type: str, properties: Mapping[str, Any]) -> str:
    explicit_label = str(properties.get("display_label") or properties.get("关系名称") or "").strip()
    if explicit_label:
        return explicit_label
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


def _taxonomy_parts(node_id: str) -> list[str]:
    if not node_id.startswith("taxonomy:"):
        raise ValueError("该节点不是产业层级节点")
    prefix, kind, raw_path = node_id.split(":", 2)
    _ = prefix
    return [kind, *[unquote(part) for part in raw_path.split("|")]]


def _name_from_node_id(node_id: str) -> str:
    if node_id.startswith("taxonomy:"):
        return _taxonomy_parts(node_id)[-1]
    if "::" in node_id:
        return unquote(node_id.rsplit("::", 1)[-1])
    if ":" in node_id:
        return unquote(node_id.rsplit(":", 1)[-1])
    return unquote(node_id)


def _safe_properties(properties: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in properties.items():
        if "embedding" in str(key).casefold():
            continue
        result[str(key)] = _safe_value(value)
    return result


def _safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= 2000 else value[:2000] + "..."
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe_value(item) for item in list(value)[:80]]
    if hasattr(value, "iso_format"):
        return value.iso_format()
    return str(value)
