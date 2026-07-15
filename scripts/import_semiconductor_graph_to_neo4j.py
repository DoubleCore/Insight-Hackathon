from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
GRAPHITI_ROOT = ROOT / 'graphiti-main' / 'graphiti-main'

sys.path.insert(0, str(ROOT / 'scripts'))
LEADERS_CSV = ROOT / 'data' / 'company_pool' / 'company_leaders_stage_3.csv'
LEADER_EVIDENCE_JSONL = ROOT / 'data' / 'evidence' / 'evidence_stage_3.jsonl'
RELATIONSHIPS_CSV = ROOT / 'data' / 'company_pool' / 'company_relationships_stage_4.csv'
RELATIONSHIP_EVIDENCE_JSONL = ROOT / 'data' / 'evidence' / 'evidence_stage_4_relationships.jsonl'
DIGITAL_CHINA_EVIDENCE_JSONL = ROOT / 'data' / 'evidence' / 'evidence_stage_7_digital_china.jsonl'
L1_L4_SEGMENTS_CSV = ROOT / 'data' / 'business_graph' / 'stage5_l1_l4_segments.csv'
PRODUCT_SERVICES_CSV = ROOT / 'data' / 'business_graph' / 'stage5_product_services.csv'
COMPANY_PRODUCT_RELATIONS_CSV = (
    ROOT / 'data' / 'business_graph' / 'stage6_company_product_relations.csv'
)
DIGITAL_CHINA_RELATIONS_CSV = (
    ROOT / 'data' / 'business_graph' / 'stage7_digital_china_relations.csv'
)
OPPORTUNITIES_CSV = ROOT / 'data' / 'business_graph' / 'stage8_business_opportunities.csv'
COMPETITION_CSV = ROOT / 'data' / 'business_graph' / 'stage6_company_competition.csv'

GRAPH_ID = 'semiconductor_industry_stage3_stage4'
ALLOWED_LABELS = {
    'SemiconductorKG',
    'ValueChainLayer',
    'MajorSegment',
    'Subsegment',
    'Company',
    'Evidence',
    'LeadershipClaim',
    'CompanyRelationship',
    'ProductService',
    'DigitalChina',
}

BUSINESS_RELATIONSHIP_TYPES = {
    '包含产品服务',
    '生产',
    '销售',
    '使用',
    '采购',
    '集成',
    '供应给',
    '合作',
    '合资建设',
    '联合研发',
    '生态适配',
    '方案协同',
    '公开关系',
    '推定竞争',
    '渠道代理',
    '投资控股',
}

COMPANY_PRODUCT_RELATION_TYPE_MAP = {
    'PRODUCES': '生产',
    'SELLS': '销售',
    'USES': '使用',
    'PROCURES': '采购',
    'INTEGRATES': '集成',
}

COMPANY_RELATIONSHIP_TYPE_MAP = {
    # stage4 实际出现的 relationship_type 全覆盖，未知类型 fail-fast（见 company_relationship_type）
    # 供应链类 -> 供应给
    'IP授权': '供应给',
    'EDA/IP供应': '供应给',
    '晶圆代工': '供应给',
    '设备供应': '供应给',
    '材料供应': '供应给',
    '先进封装': '供应给',
    '先进封装供应': '供应给',
    '封装测试': '供应给',
    '封装测试产能承接': '供应给',
    '封装测试供应链线索': '供应给',
    'HBM供应': '供应给',
    'HBM/存储供应': '供应给',
    'SiC材料供应': '供应给',
    '封装载板供应': '供应给',
    'IC载板供应': '供应给',
    '功率器件供应与战略伙伴': '供应给',
    # 合资、联合研发和生态适配类
    '战略合作': '联合研发',
    '生态合作': '生态适配',
    '封测合资与产能承接': '合资建设',
    '先进封装合资建设': '合资建设',
    '先进工艺联合研发合资': '联合研发',
    '先进工艺联合研发投资': '联合研发',
    'HGX系统伙伴发布': '生态适配',
    # 渠道
    '渠道代理': '渠道代理',
    '分销代理': '渠道代理',
    # 推定竞争 / 股权
    '竞争': '推定竞争',
    '推定竞争': '推定竞争',
    '股权投资': '投资控股',
    '投资控股': '投资控股',
}

def digital_china_confirmed_relationship_type(relationship_type: str) -> str:
    if any(term in relationship_type for term in ('联合发布', '方案协同', 'AI一体机')):
        return '方案协同'
    if any(term in relationship_type for term in ('生态适配', '鲲鹏', '昇腾', '国产算力')):
        return '生态适配'
    return '公开关系'


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        return [dict(row) for row in csv.DictReader(f)]


def read_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return records

    with path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            evidence_id = item.get('evidence_id')
            if evidence_id:
                records[evidence_id] = item
    return records


def split_ids(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(';') if part.strip()]


def split_urls(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split('|') if part.strip()]


def get_graph_database():
    from neo4j import GraphDatabase

    return GraphDatabase


def compact_text(value: Any, limit: int = 1800) -> str:
    if value is None:
        return ''
    text = str(value).replace('\r\n', '\n').strip()
    return text if len(text) <= limit else text[: limit - 3] + '...'


def safe_labels(labels: list[str]) -> str:
    unknown = set(labels) - ALLOWED_LABELS
    if unknown:
        raise ValueError(f'Unsupported labels: {sorted(unknown)}')
    return ':' + ':'.join(labels)


def merge_node(tx, labels: list[str], key: str, properties: dict[str, Any]) -> None:
    label_clause = safe_labels(['SemiconductorKG', *labels])
    tx.run(
        f"""
        MERGE (n{label_clause} {{key: $key}})
        SET n += $properties
        """,
        key=key,
        properties={k: v for k, v in properties.items() if v is not None},
    )


def merge_relationship(
    tx,
    from_key: str,
    relationship_type: str,
    to_key: str,
    properties: dict[str, Any] | None = None,
) -> None:
    tx.run(
        f"""
        MATCH (a:SemiconductorKG {{key: $from_key}})
        MATCH (b:SemiconductorKG {{key: $to_key}})
        MERGE (a)-[r:{relationship_type}]->(b)
        SET r += $properties
        """,
        from_key=from_key,
        to_key=to_key,
        properties=properties or {},
    )


def merge_business_relationship(
    tx,
    from_key: str,
    relationship_type: str,
    to_key: str,
    properties: dict[str, Any] | None = None,
) -> None:
    if relationship_type not in BUSINESS_RELATIONSHIP_TYPES:
        raise ValueError(f'Unsupported business relationship type: {relationship_type}')
    merge_relationship(tx, from_key, relationship_type, to_key, properties)


def company_product_relationship_type(value: str) -> str:
    return COMPANY_PRODUCT_RELATION_TYPE_MAP.get(value, value)


def company_relationship_type(value: str) -> str:
    """stage4 relationship_type -> 中文业务边类型。未知类型 fail-fast，避免静默错标。"""
    mapped = COMPANY_RELATIONSHIP_TYPE_MAP.get(value)
    if not mapped:
        raise ValueError(f'未知 company relationship_type: {value!r}，请在 COMPANY_RELATIONSHIP_TYPE_MAP 中显式映射')
    return mapped


def digital_china_relationship_type(status: str, relationship_type: str = '') -> str | None:
    if status != 'confirmed_public_relationship':
        return None
    return digital_china_confirmed_relationship_type(relationship_type)


def digital_china_status_properties(row: dict[str, str]) -> dict[str, Any]:
    evidence_ids = split_ids(row.get('evidence_ids'))
    requires_internal_validation = row.get('requires_internal_validation', '') == 'true'
    return {
        '神州数码关系状态': row.get('relationship_status', ''),
        '神州数码关系类型': row.get('relationship_type', ''),
        '神州数码关系依据': row.get('relationship_basis', ''),
        '神州数码关系证据ID': evidence_ids,
        '神州数码关系置信度': row.get('confidence', ''),
        '是否需要内部验证': requires_internal_validation,
        '神州数码关系局限说明': row.get('limitations', ''),
        'digital_china_relationship_status': row.get('relationship_status', ''),
        'digital_china_relationship_type': row.get('relationship_type', ''),
        'digital_china_relationship_basis': row.get('relationship_basis', ''),
        'digital_china_evidence_ids': evidence_ids,
        'digital_china_confidence': row.get('confidence', ''),
        'requires_internal_validation': requires_internal_validation,
        'digital_china_limitations': row.get('limitations', ''),
    }


def known_company_names(
    leaders: list[dict[str, str]],
    relationships: list[dict[str, str]],
    company_product_relations: list[dict[str, str]],
) -> set[str]:
    names: set[str] = set()
    for row in leaders:
        company_name = row.get('company_name', '').strip()
        if company_name:
            names.add(company_name)
    for row in relationships:
        for field in ('source_company', 'target_company', 'company_name', 'related_company'):
            company_name = row.get(field, '').strip()
            if company_name:
                names.add(company_name)
    for row in company_product_relations:
        company_name = row.get('company_name', '').strip()
        if company_name:
            names.add(company_name)
    return names


def filter_digital_china_company_relations(
    rows: list[dict[str, str]],
    companies: set[str],
) -> list[dict[str, str]]:
    return [row for row in rows if row.get('company_name', '').strip() in companies]


GRADE_RANK = {
    'A': 5,
    'A-': 4,
    'B': 3,
    'B-': 2,
    'C': 1,
}

SEARCH_SOURCE_TYPES = {'industry_search', 'public_search'}


def evidence_quality_props(
    evidence_ids: list[str],
    evidence: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    records = [evidence[evidence_id] for evidence_id in evidence_ids if evidence_id in evidence]
    grades = [record.get('source_grade') or '' for record in records]
    source_types = [record.get('source_type') or '' for record in records]
    best_grade = max(grades, key=lambda grade: GRADE_RANK.get(grade, 0), default='')
    best_rank = GRADE_RANK.get(best_grade, 0)
    search_only = bool(records) and all(source_type in SEARCH_SOURCE_TYPES for source_type in source_types)
    weak = bool(records) and best_rank <= GRADE_RANK['B-']
    strength = '强' if best_rank >= GRADE_RANK['A-'] else '中' if best_rank >= GRADE_RANK['B'] else '弱'

    return {
        '最高证据等级': best_grade,
        '证据强度': strength,
        '是否仅搜索结果支撑': search_only,
        '是否弱证据支撑': weak,
        '证据来源类型': sorted(set(source_types)),
        '证据等级列表': grades,
        'best_evidence_grade': best_grade,
        'evidence_strength': strength,
        'search_only_evidence': search_only,
        'weak_evidence_support': weak,
        'evidence_source_types': sorted(set(source_types)),
        'evidence_grades': grades,
    }


def evidence_props(evidence_id: str, item: dict[str, Any] | None, stage: str) -> dict[str, Any]:
    item = item or {}
    return {
        'key': f'evidence::{evidence_id}',
        'graph_id': GRAPH_ID,
        'kind': 'Evidence',
        'stage': stage,
        'evidence_id': evidence_id,
        'name': evidence_id,
        '名称': evidence_id,
        'title': compact_text(item.get('source_title'), 500),
        '来源标题': compact_text(item.get('source_title'), 500),
        'url': item.get('source_url_or_file') or '',
        '来源链接': item.get('source_url_or_file') or '',
        'source_type': item.get('source_type') or '',
        '来源类型': item.get('source_type') or '',
        'source_grade': item.get('source_grade') or '',
        '来源等级': item.get('source_grade') or '',
        'publish_date': item.get('publish_date') or '',
        '发布日期': item.get('publish_date') or '',
        'retrieved_at': item.get('retrieved_at') or '',
        '检索时间': item.get('retrieved_at') or '',
        'query': compact_text(item.get('query'), 500),
        '检索词': compact_text(item.get('query'), 500),
        'excerpt': compact_text(item.get('evidence_excerpt')),
        '证据摘录': compact_text(item.get('evidence_excerpt')),
        'possible_claim': compact_text(item.get('possible_claim'), 800),
        '可能支持的判断': compact_text(item.get('possible_claim'), 800),
        'confidence': item.get('confidence') or '',
        '置信度': item.get('confidence') or '',
    }


async def initialize_graphiti_indices(uri: str, user: str, password: str) -> None:
    if GRAPHITI_ROOT.exists():
        sys.path.insert(0, str(GRAPHITI_ROOT))

    os.environ.setdefault('OPENAI_API_KEY', 'graphiti-local-index-init')

    from graphiti_core import Graphiti

    graphiti = Graphiti(uri, user, password)
    try:
        await graphiti.build_indices_and_constraints()
    finally:
        await graphiti.close()


def create_constraints(driver) -> None:
    statements = [
        'CREATE CONSTRAINT semiconductor_kg_key IF NOT EXISTS '
        'FOR (n:SemiconductorKG) REQUIRE n.key IS UNIQUE',
        'CREATE INDEX semiconductor_kg_graph_id IF NOT EXISTS '
        'FOR (n:SemiconductorKG) ON (n.graph_id)',
        'CREATE INDEX semiconductor_company_name IF NOT EXISTS '
        'FOR (n:Company) ON (n.name)',
        'CREATE INDEX semiconductor_subsegment_name IF NOT EXISTS '
        'FOR (n:Subsegment) ON (n.name)',
        'CREATE INDEX semiconductor_evidence_id IF NOT EXISTS '
        'FOR (n:Evidence) ON (n.evidence_id)',
        'CREATE INDEX semiconductor_product_service_name IF NOT EXISTS '
        'FOR (n:ProductService) ON (n.name)',
    ]
    with driver.session() as session:
        for statement in statements:
            session.run(statement)


def clear_existing_graph(driver) -> None:
    with driver.session() as session:
        session.run(
            """
            MATCH (n:SemiconductorKG {graph_id: $graph_id})
            DETACH DELETE n
            """,
            graph_id=GRAPH_ID,
        )


def import_leadership_graph(driver, rows: list[dict[str, str]], evidence: dict[str, dict[str, Any]]):
    company_regions: dict[str, set[str]] = defaultdict(set)
    company_segment_counts: Counter[str] = Counter()
    subsegment_by_company_path: dict[tuple[str, str], str] = {}

    for row in rows:
        company = row['company_name'].strip()
        region = row.get('company_region', '').strip()
        if region:
            company_regions[company].add(region)
        company_segment_counts[company] += 1

    with driver.session() as session:
        for idx, row in enumerate(rows, start=1):
            layer_name = row['value_chain_layer'].strip()
            major_name = row['major_segment'].strip()
            subsegment_name = row['subsegment_name'].strip()
            company_name = row['company_name'].strip()
            segment_path = f'{layer_name}/{major_name}/{subsegment_name}'

            layer_key = f'layer::{layer_name}'
            major_key = f'major::{layer_name}::{major_name}'
            subsegment_key = f'subsegment::{segment_path}'
            company_key = f'company::{company_name}'
            claim_key = f'leadership_claim::{segment_path}::{company_name}'
            subsegment_by_company_path[(company_name, segment_path)] = subsegment_key

            evidence_ids = split_ids(row.get('evidence_ids'))
            source_urls = split_urls(row.get('source_urls'))
            quality_props = evidence_quality_props(evidence_ids, evidence)

            session.execute_write(
                merge_node,
                ['ValueChainLayer'],
                layer_key,
                {
                    'key': layer_key,
                    'graph_id': GRAPH_ID,
                    'kind': 'ValueChainLayer',
                    'name': layer_name,
                },
            )
            session.execute_write(
                merge_node,
                ['MajorSegment'],
                major_key,
                {
                    'key': major_key,
                    'graph_id': GRAPH_ID,
                    'kind': 'MajorSegment',
                    'name': major_name,
                    'value_chain_layer': layer_name,
                },
            )
            session.execute_write(
                merge_node,
                ['Subsegment'],
                subsegment_key,
                {
                    'key': subsegment_key,
                    'graph_id': GRAPH_ID,
                    'kind': 'Subsegment',
                    'name': subsegment_name,
                    'full_path': segment_path,
                    'role': row.get('subsegment_role', ''),
                    'value_chain_layer': layer_name,
                    'major_segment': major_name,
                },
            )
            session.execute_write(
                merge_node,
                ['Company'],
                company_key,
                {
                    'key': company_key,
                    'graph_id': GRAPH_ID,
                    'kind': 'Company',
                    'name': company_name,
                    'regions': sorted(company_regions[company_name]),
                    'segment_count': company_segment_counts[company_name],
                },
            )
            session.execute_write(
                merge_node,
                ['LeadershipClaim'],
                claim_key,
                {
                    'key': claim_key,
                    'graph_id': GRAPH_ID,
                    'kind': 'LeadershipClaim',
                    'name': f'{company_name} - {subsegment_name}',
                    'company_name': company_name,
                    'subsegment_name': subsegment_name,
                    'segment_path': segment_path,
                    'leader_level': row.get('leader_level', ''),
                    'selection_basis': row.get('selection_basis', ''),
                    'confidence': row.get('confidence', ''),
                    'evidence_count': int(row.get('evidence_count') or 0),
                    'limitations': row.get('limitations', ''),
                    'source_urls': source_urls,
                    'evidence_ids': evidence_ids,
                    **quality_props,
                },
            )

            session.execute_write(merge_relationship, layer_key, 'HAS_MAJOR_SEGMENT', major_key)
            session.execute_write(merge_relationship, major_key, 'HAS_SUBSEGMENT', subsegment_key)
            session.execute_write(
                merge_relationship,
                company_key,
                'LEADER_IN',
                subsegment_key,
                {
                    'leader_level': row.get('leader_level', ''),
                    'selection_basis': row.get('selection_basis', ''),
                    'confidence': row.get('confidence', ''),
                    'evidence_count': int(row.get('evidence_count') or 0),
                    'evidence_ids': evidence_ids,
                    '证据ID': evidence_ids,
                    **quality_props,
                },
            )
            session.execute_write(merge_relationship, company_key, 'HAS_LEADERSHIP_CLAIM', claim_key)
            session.execute_write(merge_relationship, claim_key, 'ABOUT_COMPANY', company_key)
            session.execute_write(merge_relationship, claim_key, 'ASSERTS_LEADER_IN', subsegment_key)

            for evidence_id in evidence_ids:
                evidence_key = f'evidence::{evidence_id}'
                session.execute_write(
                    merge_node,
                    ['Evidence'],
                    evidence_key,
                    evidence_props(evidence_id, evidence.get(evidence_id), 'stage3'),
                )
                session.execute_write(merge_relationship, claim_key, 'SUPPORTED_BY', evidence_key)

    return subsegment_by_company_path


def import_company_relationships(
    driver,
    rows: list[dict[str, str]],
    evidence: dict[str, dict[str, Any]],
    subsegment_by_company_path: dict[tuple[str, str], str],
) -> None:
    if not rows:
        return

    with driver.session() as session:
        for idx, row in enumerate(rows, start=1):
            source_company = row['source_company'].strip()
            target_company = row['target_company'].strip()
            source_segment = row.get('source_segment', '').strip()
            target_segment = row.get('target_segment', '').strip()

            source_company_key = f'company::{source_company}'
            target_company_key = f'company::{target_company}'
            relationship_id = row.get('relationship_id', '').strip() or f'R4-FALLBACK-{idx:04d}'
            relationship_key = f'company_relationship::{relationship_id}'
            evidence_ids = split_ids(row.get('evidence_ids'))
            source_urls = split_urls(row.get('source_urls'))
            quality_props = evidence_quality_props(evidence_ids, evidence)

            session.execute_write(
                merge_node,
                ['Company'],
                source_company_key,
                {
                    'key': source_company_key,
                    'graph_id': GRAPH_ID,
                    'kind': 'Company',
                    'name': source_company,
                },
            )
            session.execute_write(
                merge_node,
                ['Company'],
                target_company_key,
                {
                    'key': target_company_key,
                    'graph_id': GRAPH_ID,
                    'kind': 'Company',
                    'name': target_company,
                },
            )
            session.execute_write(
                merge_node,
                ['CompanyRelationship'],
                relationship_key,
                {
                    'key': relationship_key,
                    'graph_id': GRAPH_ID,
                    'kind': 'CompanyRelationship',
                    'name': f'{source_company} -> {target_company}',
                    'source_company': source_company,
                    'target_company': target_company,
                    'source_segment': source_segment,
                    'target_segment': target_segment,
                    'relationship_type': row.get('relationship_type', ''),
                    'relationship_direction': row.get('relationship_direction', ''),
                    'relationship_claim': row.get('relationship_claim', ''),
                    'confidence': row.get('confidence', ''),
                    'limitations': row.get('limitations', ''),
                    'source_urls': source_urls,
                    'evidence_ids': evidence_ids,
                    **quality_props,
                },
            )
            # 仅当中文映射为"供应给"时写英文 SUPPLIES_TO 边；合作/竞争/渠道/股权不写（语义不符）
            chinese_rel_type = company_relationship_type(row.get('relationship_type', ''))
            if chinese_rel_type == '供应给':
                session.execute_write(
                    merge_relationship,
                    source_company_key,
                    'SUPPLIES_TO',
                    target_company_key,
                    {
                        'relationship_type': row.get('relationship_type', ''),
                        'relationship_claim': row.get('relationship_claim', ''),
                        'confidence': row.get('confidence', ''),
                        'evidence_ids': evidence_ids,
                        '证据ID': evidence_ids,
                        **quality_props,
                    },
                )
            session.execute_write(
                merge_business_relationship,
                source_company_key,
                chinese_rel_type,
                target_company_key,
                {
                    '关系类型': row.get('relationship_type', ''),
                    '关系方向': row.get('relationship_direction', ''),
                    '判断依据': row.get('relationship_claim', ''),
                    '证据ID': evidence_ids,
                    '置信度': row.get('confidence', ''),
                    '局限说明': row.get('limitations', ''),
                    'relationship_type': row.get('relationship_type', ''),
                    'relationship_claim': row.get('relationship_claim', ''),
                    'evidence_ids': evidence_ids,
                    'confidence': row.get('confidence', ''),
                    **quality_props,
                },
            )
            session.execute_write(merge_relationship, relationship_key, 'SOURCE_COMPANY', source_company_key)
            session.execute_write(merge_relationship, relationship_key, 'TARGET_COMPANY', target_company_key)

            source_segment_key = subsegment_by_company_path.get((source_company, source_segment))
            target_segment_key = subsegment_by_company_path.get((target_company, target_segment))
            if source_segment_key:
                session.execute_write(merge_relationship, relationship_key, 'SOURCE_SEGMENT', source_segment_key)
            if target_segment_key:
                session.execute_write(merge_relationship, relationship_key, 'TARGET_SEGMENT', target_segment_key)

            for evidence_id in evidence_ids:
                evidence_key = f'evidence::{evidence_id}'
                session.execute_write(
                    merge_node,
                    ['Evidence'],
                    evidence_key,
                    evidence_props(evidence_id, evidence.get(evidence_id), 'stage4'),
                )
                session.execute_write(merge_relationship, relationship_key, 'SUPPORTED_BY', evidence_key)


def import_business_graph(
    driver,
    l1_l4_rows: list[dict[str, str]],
    product_services: list[dict[str, str]],
    company_product_relations: list[dict[str, str]],
    digital_china_relations: list[dict[str, str]],
    leader_evidence: dict[str, dict[str, Any]],
    digital_china_evidence: dict[str, dict[str, Any]],
) -> None:
    if not any(
        [
            l1_l4_rows,
            product_services,
            company_product_relations,
            digital_china_relations,
        ]
    ):
        return

    with driver.session() as session:
        company_product_evidence = {**leader_evidence, **digital_china_evidence}
        digital_china_key = 'company::神州数码'
        session.execute_write(
            merge_node,
                ['DigitalChina', 'Company'],
                digital_china_key,
                {
                    'key': digital_china_key,
                    'graph_id': GRAPH_ID,
                    'kind': 'DigitalChina',
                    'name': '神州数码',
                    '名称': '神州数码',
                    'relationship_note': '原产业链主图中的业务关系状态参照企业。',
                    '说明': '原产业链主图中的业务关系状态参照企业。',
                },
        )

        for row in l1_l4_rows:
            subsegment_key = (
                f"subsegment::{row['source_value_chain_layer']}/"
                f"{row['source_major_segment']}/{row['source_subsegment_name']}"
            )
            session.execute_write(
                merge_node,
                ['Subsegment'],
                subsegment_key,
                {
                    'key': subsegment_key,
                    'graph_id': GRAPH_ID,
                    'kind': 'Subsegment',
                    'name': row['l4_name'],
                    '名称': row['l4_name'],
                    'l1': row['l1'],
                    'l2': row['l2'],
                    'l3': row['l3'],
                    'l4_name': row['l4_name'],
                    'l4_code': row['l4_code'],
                    'L1': row['l1'],
                    'L2': row['l2'],
                    'L3': row['l3'],
                    'L4名称': row['l4_name'],
                    'L4编码': row['l4_code'],
                    '环节说明': row.get('subsegment_role', ''),
                    'is_focus_scope': row.get('is_focus_scope', 'false') == 'true',
                },
            )

        for row in product_services:
            product_key = f"product_service::{row['product_service_id']}"
            subsegment_candidates = [
                segment
                for segment in l1_l4_rows
                if segment['l4_code'] == row['l4_code']
            ]
            session.execute_write(
                merge_node,
                ['ProductService'],
                product_key,
                {
                    'key': product_key,
                    'graph_id': GRAPH_ID,
                    'kind': 'ProductService',
                    'name': row['product_service_name'],
                    '名称': row['product_service_name'],
                    'product_service_id': row['product_service_id'],
                    'category': row.get('category', ''),
                    'l4_code': row.get('l4_code', ''),
                    'l4_name': row.get('l4_name', ''),
                    'definition': row.get('definition', ''),
                    '产品服务ID': row['product_service_id'],
                    '类别': row.get('category', ''),
                    'L4编码': row.get('l4_code', ''),
                    'L4名称': row.get('l4_name', ''),
                    '定义': row.get('definition', ''),
                    'is_controlled': row.get('is_controlled', '') == 'true',
                },
            )
            for segment in subsegment_candidates:
                subsegment_key = (
                    f"subsegment::{segment['source_value_chain_layer']}/"
                    f"{segment['source_major_segment']}/{segment['source_subsegment_name']}"
                )
                session.execute_write(
                    merge_business_relationship,
                    subsegment_key,
                    '包含产品服务',
                    product_key,
                    {
                        'L4编码': row.get('l4_code', ''),
                        '关系说明': 'L4产业链细分环节包含该产品/服务。',
                        'l4_code': row.get('l4_code', ''),
                    },
                )

        product_key_by_name = {
            row['product_service_name']: f"product_service::{row['product_service_id']}"
            for row in product_services
        }
        for row in company_product_relations:
            company_key = f"company::{row['company_name']}"
            product_key = product_key_by_name.get(row['product_service_name'])
            if not product_key:
                continue
            evidence_ids = split_ids(row.get('evidence_ids'))
            quality_props = evidence_quality_props(evidence_ids, company_product_evidence)
            session.execute_write(
                merge_node,
                ['Company'],
                company_key,
                {
                    'key': company_key,
                    'graph_id': GRAPH_ID,
                    'kind': 'Company',
                    'name': row['company_name'],
                    '名称': row['company_name'],
                },
            )
            session.execute_write(
                merge_business_relationship,
                company_key,
                company_product_relationship_type(row['relation_type']),
                product_key,
                {
                    '判断依据': row.get('basis', ''),
                    '证据ID': evidence_ids,
                    '置信度': row.get('confidence', ''),
                    '是否需要内部验证': row.get('requires_internal_validation', '') == 'true',
                    'L4编码': row.get('l4_code', ''),
                    'L4名称': row.get('l4_name', ''),
                    '原始关系类型': row.get('relation_type', ''),
                    '推导来源': row.get('derivation', ''),
                    'basis': row.get('basis', ''),
                    'evidence_ids': evidence_ids,
                    'confidence': row.get('confidence', ''),
                    'requires_internal_validation': row.get('requires_internal_validation', '') == 'true',
                    'derivation': row.get('derivation', ''),
                    **quality_props,
                },
            )

        for row in digital_china_relations:
            company_key = f"company::{row['company_name']}"
            evidence_ids = split_ids(row.get('evidence_ids'))
            quality_props = evidence_quality_props(evidence_ids, digital_china_evidence)
            status_properties = {
                **digital_china_status_properties(row),
                **quality_props,
            }
            session.execute_write(
                merge_node,
                ['Company'],
                company_key,
                {
                    'key': company_key,
                    'graph_id': GRAPH_ID,
                    'kind': 'Company',
                    'name': row['company_name'],
                    '名称': row['company_name'],
                    **status_properties,
                },
            )
            relationship_type = digital_china_relationship_type(
                row.get('relationship_status', ''),
                row.get('relationship_type', ''),
            )
            if relationship_type:
                session.execute_write(
                    merge_business_relationship,
                    company_key,
                    relationship_type,
                    digital_china_key,
                    {
                        '关系对象': '神州数码',
                        '关系状态': row.get('relationship_status', ''),
                        '关系类型': row.get('relationship_type', ''),
                        '判断依据': row.get('relationship_basis', ''),
                        '证据ID': evidence_ids,
                        '置信度': row.get('confidence', ''),
                        '是否需要内部验证': row.get('requires_internal_validation', '') == 'true',
                        '局限说明': row.get('limitations', ''),
                        'relationship_status': row.get('relationship_status', ''),
                        'relationship_type': row.get('relationship_type', ''),
                        'relationship_basis': row.get('relationship_basis', ''),
                        'evidence_ids': evidence_ids,
                        'confidence': row.get('confidence', ''),
                        'requires_internal_validation': row.get('requires_internal_validation', '') == 'true',
                        'limitations': row.get('limitations', ''),
                        **quality_props,
                    },
                )

            for evidence_id in evidence_ids:
                evidence_key = f'evidence::{evidence_id}'
                session.execute_write(
                    merge_node,
                    ['Evidence'],
                    evidence_key,
                    evidence_props(evidence_id, digital_china_evidence.get(evidence_id), 'stage7'),
                )
                session.execute_write(merge_relationship, company_key, 'SUPPORTED_BY', evidence_key)


def import_competition_relations(
    driver,
    competition_rows: list[dict[str, str]],
    evidence: dict[str, dict[str, Any]],
) -> None:
    """导入同环节同产品龙头推定竞争边（推定关系，只写中文'推定竞争'边，不建具象节点）。"""
    if not competition_rows:
        return

    with driver.session() as session:
        for row in competition_rows:
            source_company = row.get('source_company', '').strip()
            target_company = row.get('target_company', '').strip()
            if not source_company or not target_company:
                continue
            source_key = f'company::{source_company}'
            target_key = f'company::{target_company}'
            evidence_ids = split_ids(row.get('evidence_ids'))
            quality_props = evidence_quality_props(evidence_ids, evidence)
            symmetric = row.get('对称关系', '') == 'true'
            session.execute_write(
                merge_business_relationship,
                source_key,
                '推定竞争',
                target_key,
                {
                    '推定关系': True,
                    '对称关系': symmetric,
                    '判断依据': row.get('basis', ''),
                    '证据ID': evidence_ids,
                    '置信度': row.get('confidence', ''),
                    '是否需要内部验证': row.get('requires_internal_validation', '') == 'true',
                    'relationship_type': row.get('relationship_type', '推定竞争'),
                    'basis': row.get('basis', ''),
                    'evidence_ids': evidence_ids,
                    'confidence': row.get('confidence', ''),
                    'requires_internal_validation': row.get('requires_internal_validation', '') == 'true',
                    'derivation': row.get('derivation', ''),
                    **quality_props,
                },
            )
            for evidence_id in evidence_ids:
                evidence_key = f'evidence::{evidence_id}'
                session.execute_write(
                    merge_node,
                    ['Evidence'],
                    evidence_key,
                    evidence_props(evidence_id, evidence.get(evidence_id), 'stage3'),
                )


def fetch_summary(driver) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    with driver.session() as session:
        node_rows = session.run(
            """
            MATCH (n:SemiconductorKG {graph_id: $graph_id})
            UNWIND labels(n) AS label
            WITH label, count(*) AS count
            WHERE label <> 'SemiconductorKG'
            RETURN label, count
            ORDER BY label
            """,
            graph_id=GRAPH_ID,
        )
        rel_rows = session.run(
            """
            MATCH (a:SemiconductorKG {graph_id: $graph_id})-[r]->(b:SemiconductorKG {graph_id: $graph_id})
            RETURN type(r) AS type, count(*) AS count
            ORDER BY type
            """,
            graph_id=GRAPH_ID,
        )
        return (
            [(record['label'], record['count']) for record in node_rows],
            [(record['type'], record['count']) for record in rel_rows],
        )


def print_browser_queries() -> None:
    print('\nNeo4j Browser: http://localhost:7474')
    print('Login: neo4j / password')
    print('\nRecommended Cypher queries:')
    print(
        """
MATCH p=(l:ValueChainLayer {graph_id:'semiconductor_industry_stage3_stage4'})
  -[:HAS_MAJOR_SEGMENT]->(:MajorSegment)
  -[:HAS_SUBSEGMENT]->(:Subsegment)
  <-[:LEADER_IN]-(:Company)
RETURN p
LIMIT 200;
""".strip()
    )
    print(
        """
MATCH p=(c:Company {graph_id:'semiconductor_industry_stage3_stage4', name:'中芯国际'})-[r]-(n)
RETURN p
LIMIT 80;
""".strip()
    )
    print(
        """
MATCH p=(claim:LeadershipClaim {graph_id:'semiconductor_industry_stage3_stage4'})
  -[:ABOUT_COMPANY]->(:Company {name:'华大九天'})
MATCH p2=(claim)-[:SUPPORTED_BY]->(:Evidence)
RETURN p, p2
LIMIT 50;
""".strip()
    )
    print(
        """
MATCH p=(:Company {graph_id:'semiconductor_industry_stage3_stage4'})
  -[:SUPPLIES_TO]->(:Company {graph_id:'semiconductor_industry_stage3_stage4'})
RETURN p
LIMIT 120;
""".strip()
    )
    print(
        """
MATCH p=(:Subsegment)-[:包含产品服务]->(:ProductService)<-[:生产|销售|使用|采购|集成]-(:Company)
RETURN p
LIMIT 100;
""".strip()
    )
    print(
        """
MATCH p=(:Company)-[:生态适配|方案协同|公开关系]->(:Company {名称:'神州数码'})
RETURN p
LIMIT 100;
""".strip()
    )
    print(
        """
MATCH (c:Company)
WHERE c.`神州数码关系状态` IN ['potential_fit', 'needs_internal_validation', 'no_public_evidence']
RETURN c.name, c.`神州数码关系状态`, c.`神州数码关系类型`, c.`神州数码关系依据`
LIMIT 50;
""".strip()
    )
    print(
        """
MATCH p=(:Subsegment)-[:包含产品服务]->(:ProductService)<-[:生产|销售|使用|采购|集成]-(c:Company)
OPTIONAL MATCH p2=(c)-[:生态适配|方案协同|公开关系]->(:Company {名称:'神州数码'})
RETURN p, p2
LIMIT 200;
""".strip()
    )
    print(
        """
MATCH p=(:Company)-[:供应给|合作|合资建设|联合研发|生态适配|方案协同|公开关系|推定竞争|渠道代理|投资控股]->(:Company)
RETURN p
LIMIT 100;
""".strip()
    )
    print(
        """
MATCH p=(a:Company)-[r]->(b)
WHERE type(r) IN ['生产','销售','使用','采购','集成','供应给','合作','合资建设','联合研发','生态适配','方案协同','公开关系','推定竞争','渠道代理','投资控股','LEADER_IN','SUPPLIES_TO']
  AND r.`是否弱证据支撑` = true
RETURN p, r.`证据强度` AS 证据强度, r.`最高证据等级` AS 最高证据等级, r.`证据来源类型` AS 证据来源类型
LIMIT 100;
""".strip()
    )
    print(
        """
MATCH p=(a:Company)-[r]->(b)
WHERE type(r) IN ['生产','销售','使用','采购','集成','供应给','合作','合资建设','联合研发','生态适配','方案协同','公开关系','推定竞争','渠道代理','投资控股','LEADER_IN','SUPPLIES_TO']
  AND r.`证据强度` IN ['强','中']
RETURN p, r.`证据强度` AS 证据强度, r.`最高证据等级` AS 最高证据等级
LIMIT 100;
""".strip()
    )

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Import semiconductor industry graph into Neo4j.')
    parser.add_argument('--neo4j-uri', default=os.getenv('NEO4J_URI', 'bolt://localhost:7687'))
    parser.add_argument('--neo4j-user', default=os.getenv('NEO4J_USER', 'neo4j'))
    parser.add_argument('--neo4j-password', default=os.getenv('NEO4J_PASSWORD', 'password'))
    parser.add_argument('--skip-graphiti-init', action='store_true')
    parser.add_argument('--keep-existing', action='store_true')
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not LEADERS_CSV.exists():
        raise FileNotFoundError(f'Missing leaders CSV: {LEADERS_CSV}')
    if not LEADER_EVIDENCE_JSONL.exists():
        raise FileNotFoundError(f'Missing evidence JSONL: {LEADER_EVIDENCE_JSONL}')

    leaders = read_csv(LEADERS_CSV)
    leader_evidence = read_jsonl(LEADER_EVIDENCE_JSONL)
    relationships = read_csv(RELATIONSHIPS_CSV) if RELATIONSHIPS_CSV.exists() else []
    relationship_evidence = read_jsonl(RELATIONSHIP_EVIDENCE_JSONL)
    digital_china_evidence = read_jsonl(DIGITAL_CHINA_EVIDENCE_JSONL)
    l1_l4_rows = read_csv(L1_L4_SEGMENTS_CSV) if L1_L4_SEGMENTS_CSV.exists() else []
    product_services = read_csv(PRODUCT_SERVICES_CSV) if PRODUCT_SERVICES_CSV.exists() else []
    company_product_relations = (
        read_csv(COMPANY_PRODUCT_RELATIONS_CSV)
        if COMPANY_PRODUCT_RELATIONS_CSV.exists()
        else []
    )
    digital_china_relations = (
        read_csv(DIGITAL_CHINA_RELATIONS_CSV) if DIGITAL_CHINA_RELATIONS_CSV.exists() else []
    )
    # Stage7 is a business-relation layer. A company may be relevant to Digital China
    # because of public annual-report/partner evidence even if it is not a Stage3 leader.
    # Keep those rows in the native graph, but do not mark them as leaders unless Stage3 does.
    skipped_digital_china_relations: list[str] = []
    competition_rows = read_csv(COMPETITION_CSV) if COMPETITION_CSV.exists() else []
    print(f'Loaded leader rows: {len(leaders)}')
    print(f'Loaded leader evidence: {len(leader_evidence)}')
    print(f'Loaded company relationship rows: {len(relationships)}')
    print(f'Loaded company relationship evidence: {len(relationship_evidence)}')
    print(f'Loaded L1-L4 business rows: {len(l1_l4_rows)}')
    print(f'Loaded product services: {len(product_services)}')
    print(f'Loaded company-product relations: {len(company_product_relations)}')
    print(f'Loaded Digital China relations: {len(digital_china_relations)}')
    if OPPORTUNITIES_CSV.exists():
        print(f'Skipped Stage8 business conversion CSV for current main graph: {OPPORTUNITIES_CSV.name}')
    print(f'Loaded competition relations: {len(competition_rows)}')
    if skipped_digital_china_relations:
        print(
            'Skipped non-company Digital China relation rows: '
            + ', '.join(skipped_digital_china_relations)
        )

    if not args.skip_graphiti_init:
        print('Initializing Graphiti indices and constraints...')
        asyncio.run(initialize_graphiti_indices(args.neo4j_uri, args.neo4j_user, args.neo4j_password))
        print('Graphiti initialization finished.')

    graph_database = get_graph_database()
    driver = graph_database.driver(args.neo4j_uri, auth=(args.neo4j_user, args.neo4j_password))
    try:
        driver.verify_connectivity()
        create_constraints(driver)
        if not args.keep_existing:
            clear_existing_graph(driver)

        subsegment_by_company_path = import_leadership_graph(driver, leaders, leader_evidence)
        import_company_relationships(
            driver,
            relationships,
            relationship_evidence,
            subsegment_by_company_path,
        )
        import_competition_relations(driver, competition_rows, leader_evidence)
        import_business_graph(
            driver,
            l1_l4_rows,
            product_services,
            company_product_relations,
            digital_china_relations,
            leader_evidence,
            digital_china_evidence,
        )
        node_summary, rel_summary = fetch_summary(driver)
    finally:
        driver.close()

    print('\nImport completed.')
    print('\nNode counts:')
    for label, count in node_summary:
        print(f'  {label}: {count}')
    print('\nRelationship counts:')
    for rel_type, count in rel_summary:
        print(f'  {rel_type}: {count}')

    print_browser_queries()


if __name__ == '__main__':
    main()
