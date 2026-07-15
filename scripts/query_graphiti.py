from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GRAPHITI_ROOT = ROOT / "graphiti-main" / "graphiti-main"
sys.path.insert(0, str(GRAPHITI_ROOT))

from graphiti_core import Graphiti  # type: ignore  # noqa: E402
from graphiti_core.cross_encoder.openai_reranker_client import (  # type: ignore  # noqa: E402
    OpenAIRerankerClient,
)
from graphiti_core.embedder.openai import (  # type: ignore  # noqa: E402
    OpenAIEmbedder,
    OpenAIEmbedderConfig,
)
from graphiti_core.llm_client.config import LLMConfig  # type: ignore  # noqa: E402
from graphiti_core.llm_client.openai_generic_client import (  # type: ignore  # noqa: E402
    OpenAIGenericClient,
)
from neo4j import GraphDatabase  # type: ignore  # noqa: E402

from load_ai_keys import DEFAULT_KEY_FILE, load_service_keys  # noqa: E402


def value(edge: Any, name: str, default: Any = "") -> Any:
    direct = getattr(edge, name, default)
    if direct not in (None, ""):
        return direct
    attributes = getattr(edge, "attributes", {}) or {}
    return attributes.get(name, default)


def short_date(value_: Any) -> str:
    if value_ is None:
        return ""
    text = str(value_)
    return text[:10] if len(text) >= 10 else text


def truthy(value_: Any) -> bool:
    return str(value_).strip().lower() in {"true", "1", "yes", "y"}


def edge_priority(edge: Any) -> tuple[int, int, int, int]:
    attrs = getattr(edge, "attributes", {}) or {}
    has_status = bool(attrs.get("relationship_status"))
    has_evidence = bool(attrs.get("evidence_ids") or attrs.get("primary_evidence_id"))
    has_validation = attrs.get("requires_internal_validation") is not None
    deterministic = truthy(attrs.get("deterministic_backfill"))
    # Lower tuple sorts first. Deterministic curated edges should outrank LLM-only
    # extracted duplicates because they carry the graph governance fields.
    return (
        0 if deterministic else 1,
        0 if has_status else 1,
        0 if has_evidence else 1,
        0 if has_validation else 1,
    )


def rank_edges(edges: list[Any], limit: int | None = None) -> list[Any]:
    ranked = [
        edge
        for _, edge in sorted(
            enumerate(edges),
            key=lambda item: (*edge_priority(item[1]), item[0]),
        )
    ]
    return ranked[:limit] if limit else ranked


def synthesize_answer(question: str, edges: list[Any]) -> str:
    if not edges:
        return "没有检索到足够相关的图谱事实。"

    question_lower = question.lower()
    if "神州数码" in question:
        relation_edges = [edge for edge in edges if value(edge, "relationship_status")]
        if relation_edges:
            lines = []
            for edge in relation_edges[:5]:
                status = value(edge, "relationship_status")
                relation_type = value(edge, "relationship_type")
                evidence = value(edge, "evidence_ids")
                validity = value(edge, "current_validity")
                lines.append(f"- {edge.fact} 当前有效性：{validity}。证据ID：{evidence}。")
            return "检索到的神州数码相关关系如下：\n" + "\n".join(lines)

    if "龙头" in question or "leader" in question_lower:
        leader_edges = [
            edge
            for edge in edges
            if "leader" in str(getattr(edge, "name", "")).lower()
            or "龙头" in str(getattr(edge, "fact", ""))
        ]
        selected = leader_edges or edges
        seen: set[str] = set()
        lines: list[str] = []
        for edge in selected:
            fact = str(edge.fact)
            if fact in seen or "证据" in fact:
                continue
            seen.add(fact)
            lines.append(f"- {fact}")
            if len(lines) >= 8:
                break
        return "检索到的龙头/代表性判断如下：\n" + "\n".join(lines)

    if "竞争" in question or "compet" in question_lower:
        return "检索到的竞争或推定竞争关系如下：\n" + "\n".join(
            f"- {edge.fact}" for edge in edges[:5]
        )

    return "检索到的相关事实如下：\n" + "\n".join(f"- {edge.fact}" for edge in edges[:5])


def edge_context(edges: list[Any], limit: int = 10) -> str:
    blocks: list[str] = []
    for index, edge in enumerate(rank_edges(edges, limit), start=1):
        attrs = getattr(edge, "attributes", {}) or {}
        lines = [f"[{index}] 事实：{edge.fact}"]
        if getattr(edge, "name", None):
            lines.append(f"关系：{edge.name}")
        if getattr(edge, "valid_at", None):
            lines.append(f"valid_at：{short_date(edge.valid_at)}")
        if getattr(edge, "reference_time", None):
            lines.append(f"reference_time：{short_date(edge.reference_time)}")
        evidence = attrs.get("evidence_ids") or attrs.get("primary_evidence_id")
        if evidence:
            lines.append(f"证据ID：{evidence}")
        status = attrs.get("relationship_status") or attrs.get("current_validity")
        if status:
            lines.append(f"状态：{status}")
        if attrs.get("requires_internal_validation") is not None:
            lines.append(f"是否需要内部验证：{attrs.get('requires_internal_validation')}")
        relation_type = attrs.get("relationship_type")
        if relation_type:
            lines.append(f"关系类型：{relation_type}")
        for field, label in [
            ("data_as_of", "数据截至时间"),
            ("first_seen_at", "首次入库时间"),
            ("last_verified_at", "最近核验时间"),
            ("source_publish_dates", "证据发布日期"),
            ("source_retrieved_dates", "证据检索日期"),
            ("current_validity", "当前有效性"),
            ("claim_nature", "判断性质"),
        ]:
            if attrs.get(field):
                lines.append(f"{label}：{attrs.get(field)}")
        if attrs.get("deterministic_backfill"):
            lines.append("来源：deterministic_backfill")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def generate_deepseek_answer(args: argparse.Namespace, edges: list[Any]) -> str | None:
    if args.answer_provider == "none":
        return None
    key = (
        os.getenv("DEEPSEEK_API_KEY")
        or load_service_keys(DEFAULT_KEY_FILE, ["deepseek"]).get("DEEPSEEK_API_KEY", "")
    )
    if not key:
        return None
    context = edge_context(edges, args.answer_context_edges)
    if not context:
        return None
    prompt = f"""请只基于下面的 Graphiti 图谱事实回答问题，不要引入外部知识。
回答必须优先保留这些字段：关系状态、关系类型、证据ID、数据截至时间/valid_at、证据发布日期、是否需要内部验证。
如果事实里标注“需要内部验证”“潜在匹配”“候选分析”，必须明确说明不能当作已确认客户/交易关系。
如果同一事实同时出现 LLM 自动抽取边和 deterministic_backfill 标准边，优先采用 deterministic_backfill 的关系状态、证据ID和验证口径。
回答要简洁，先给结论，再列关键事实依据。

问题：{args.question}

图谱事实：
{context}
"""
    payload = json.dumps(
        {
            "model": args.deepseek_model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是严谨的产业知识图谱问答助手，只能根据给定事实回答。",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        args.deepseek_base_url.rstrip("/") + "/chat/completions",
        data=payload,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=args.deepseek_timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as exc:
        print(f"提示：DeepSeek 答案生成失败，改用本地摘要。原因：{type(exc).__name__}: {exc}")
        print()
        return None
    return str(body["choices"][0]["message"]["content"]).strip()


def cjk_ngrams(text: str) -> set[str]:
    terms: set[str] = set()
    for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        for size in range(2, min(7, len(chunk) + 1)):
            for start in range(0, len(chunk) - size + 1):
                terms.add(chunk[start : start + size])
    return terms


def query_terms(question: str, entity_names: list[str]) -> list[str]:
    stop_terms = {
        "什么",
        "哪些",
        "怎么",
        "如何",
        "是否",
        "以及",
        "还有",
        "公司",
        "企业",
        "关系",
        "图谱",
    }
    terms = {name for name in entity_names if name and name in question}
    terms.update(cjk_ngrams(question))
    for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9/+.-]{1,}", question):
        terms.add(token.lower())
        terms.update(part.lower() for part in re.split(r"[/+.-]+", token) if len(part) >= 2)
    if "gpu" in {term.lower() for term in terms} or "GPU" in question:
        terms.update({"gpu", "ai", "ai/gpu", "gpu/ai", "加速芯片", "算力芯片"})
    filtered = {
        term.strip().lower()
        for term in terms
        if len(term.strip()) >= 2 and term.strip() not in stop_terms
    }
    return sorted(filtered, key=lambda term: (-len(term), term))[:80]


def query_entity_terms(question: str, entity_names: list[str]) -> list[str]:
    terms = {
        name.strip().lower()
        for name in entity_names
        if len(name.strip()) >= 2 and name.strip() in question
    }
    return sorted(terms, key=lambda term: (-len(term), term))[:20]


def lexical_fallback_search(
    args: argparse.Namespace, reason: Exception | None = None, announce: bool = True
) -> list[Any]:
    with GraphDatabase.driver(args.neo4j_uri, auth=(args.neo4j_user, args.neo4j_password)) as driver:
        entity_records, _, _ = driver.execute_query(
            """
            MATCH (n:Entity {group_id: $group_id})
            RETURN n.name AS name
            """,
            group_id=args.group_id,
            routing_="r",
        )
        entity_names = [str(record["name"]) for record in entity_records]
        terms = query_terms(args.question, entity_names)
        entity_terms = query_entity_terms(args.question, entity_names)
        prefer_leader = "龙头" in args.question or "leader" in args.question.lower()
        records, _, _ = driver.execute_query(
            """
            MATCH (a)-[r:RELATES_TO {group_id: $group_id}]->(b)
            WITH a, r, b,
                 toLower(
                    coalesce(a.name, '') + ' ' +
                    coalesce(b.name, '') + ' ' +
                    coalesce(r.name, '') + ' ' +
                    coalesce(r.fact, '') + ' ' +
                    coalesce(r.relationship_status, '') + ' ' +
                    coalesce(r.relationship_type, '') + ' ' +
                    coalesce(r.current_validity, '') + ' ' +
                    coalesce(r.evidence_ids, '')
                 ) AS text
            WITH a, r, b, text,
                 reduce(entity_score = 0, term IN $entity_terms |
                    entity_score + CASE WHEN text CONTAINS term THEN 8 ELSE 0 END
                 ) AS entity_score,
                 reduce(score = 0, term IN $terms |
                    score + CASE WHEN text CONTAINS term THEN 1 ELSE 0 END
                 ) +
                 CASE
                    WHEN $prefer_leader
                     AND toLower(coalesce(r.name, '')) CONTAINS 'leader'
                    THEN 10
                    WHEN $prefer_leader
                     AND (toLower(coalesce(r.fact, '')) CONTAINS 'leader'
                          OR coalesce(r.fact, '') CONTAINS '龙头')
                    THEN 2
                    ELSE 0
                 END +
                 CASE
                    WHEN $prefer_leader
                     AND toLower(coalesce(r.name, '')) CONTAINS 'evidence'
                    THEN -5
                    ELSE 0
                 END AS score
            WHERE score > 0
              AND (size($entity_terms) = 0 OR entity_score > 0)
            RETURN a.name AS source, b.name AS target, r AS edge, score + entity_score AS score
            ORDER BY score DESC, entity_score DESC, r.valid_at DESC
            LIMIT $limit
            """,
            group_id=args.group_id,
            terms=terms,
            entity_terms=entity_terms,
            prefer_leader=prefer_leader,
            limit=args.num_results,
            routing_="r",
        )
    if announce and reason is not None:
        print(
            "提示：Graphiti semantic search 不可用，已切换到 Neo4j 词面检索。"
            f"原因：{type(reason).__name__}: {reason}"
        )
        print(f"检索词：{', '.join(terms[:20])}")
        print()
    edges: list[Any] = []
    for record in records:
        props = dict(record["edge"])
        known = {
            "uuid",
            "name",
            "fact",
            "valid_at",
            "invalid_at",
            "reference_time",
            "episodes",
            "fact_embedding",
        }
        attrs = {key: value_ for key, value_ in props.items() if key not in known}
        edges.append(
            SimpleNamespace(
                uuid=props.get("uuid", ""),
                name=props.get("name", ""),
                fact=props.get("fact", ""),
                valid_at=props.get("valid_at"),
                invalid_at=props.get("invalid_at"),
                reference_time=props.get("reference_time"),
                episodes=props.get("episodes") or [],
                attributes=attrs,
                source=record["source"],
                target=record["target"],
                score=record["score"],
            )
        )
    return edges


def should_augment_with_lexical(question: str) -> bool:
    question_lower = question.lower()
    graph_terms = [
        "龙头",
        "竞争",
        "神州数码",
        "关系",
        "哪些",
        "有什么",
        "是否",
        "提供",
        "生产",
        "销售",
        "使用",
        "采购",
        "集成",
        "供应",
        "合作",
        "授权",
        "代工",
        "封装",
        "设备",
        "材料",
        "产品",
        "服务",
        "证据",
        "核验",
        "数据截至",
        "年报",
        "内部验证",
        "客户",
        "交易",
        "上游",
        "中游",
        "下游",
        "晶圆",
        "光刻",
        "存储",
        "主控",
        "服务器",
        "云基础设施",
        "汽车电子",
    ]
    english_terms = [
        "leader",
        "compet",
        "nvidia",
        "gpu",
        "hbm",
        "eda",
        "ip",
        "tsmc",
        "asml",
        "arm",
        "supermicro",
    ]
    return any(term in question for term in graph_terms) or any(
        term in question_lower for term in english_terms
    )


def should_prefer_lexical_first(question: str) -> bool:
    question_lower = question.lower()
    lexical_first_terms = [
        "龙头",
        "关系",
        "哪些",
        "有什么",
        "是否",
        "证据",
        "核验",
        "数据截至",
        "年报",
        "内部验证",
        "不能",
        "供应",
        "授权",
        "代工",
        "封装",
        "设备",
        "材料",
        "产品",
        "服务",
    ]
    english_terms = ["leader", "relationship", "supplier", "supply", "hbm", "ip"]
    return any(term in question for term in lexical_first_terms) or any(
        term in question_lower for term in english_terms
    )


def merge_edges(primary: list[Any], secondary: list[Any], limit: int) -> list[Any]:
    merged: list[Any] = []
    seen: set[str] = set()
    for index in range(max(len(primary), len(secondary))):
        for edges in (primary, secondary):
            if index >= len(edges):
                continue
            edge = edges[index]
            key = getattr(edge, "uuid", "") or getattr(edge, "fact", "")
            if key in seen:
                continue
            seen.add(key)
            merged.append(edge)
            if len(merged) >= limit:
                return merged
    return merged


async def run(args: argparse.Namespace) -> int:
    keys = load_service_keys(DEFAULT_KEY_FILE, ["siliconflow"])
    siliconflow_key = os.getenv("SILICONFLOW_API_KEY") or keys.get("SILICONFLOW_API_KEY", "")
    if not siliconflow_key:
        print("FAIL missing SILICONFLOW_API_KEY for query embedding")
        return 1

    llm_client = OpenAIGenericClient(
        config=LLMConfig(
            api_key=siliconflow_key,
            model=args.llm_model,
            small_model=args.llm_model,
            base_url=args.llm_base_url,
            temperature=0,
        ),
        structured_output_mode="json_object",
    )
    embedder = OpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            api_key=siliconflow_key,
            base_url=args.embedding_base_url,
            embedding_model=args.embedding_model,
        )
    )
    cross_encoder = OpenAIRerankerClient(
        config=LLMConfig(
            api_key=siliconflow_key,
            model=args.llm_model,
            base_url=args.llm_base_url,
            temperature=0,
        )
    )
    graphiti = Graphiti(
        args.neo4j_uri,
        args.neo4j_user,
        args.neo4j_password,
        llm_client=llm_client,
        embedder=embedder,
        cross_encoder=cross_encoder,
    )
    try:
        try:
            edges = await graphiti.search(
                args.question,
                group_ids=[args.group_id],
                num_results=args.num_results,
            )
        except Exception as exc:
            await graphiti.close()
            edges = lexical_fallback_search(args, exc)
        else:
            await graphiti.close()
            if should_augment_with_lexical(args.question):
                lexical_edges = lexical_fallback_search(args, announce=False)
                if should_prefer_lexical_first(args.question):
                    edges = merge_edges(lexical_edges, edges, args.num_results)
                else:
                    edges = merge_edges(edges, lexical_edges, args.num_results)
    except Exception:
        await graphiti.close()
        raise

    edges = rank_edges(edges, args.num_results)

    print(f"问题：{args.question}")
    print()
    print("回答：")
    generated_answer = generate_deepseek_answer(args, edges)
    print(generated_answer or synthesize_answer(args.question, edges))
    print()
    print("Graphiti 检索事实：")
    for index, edge in enumerate(edges, start=1):
        attrs = getattr(edge, "attributes", {}) or {}
        print(f"{index}. {edge.fact}")
        if getattr(edge, "name", None):
            print(f"   关系：{edge.name}")
        dates = []
        if getattr(edge, "valid_at", None):
            dates.append(f"valid_at={short_date(edge.valid_at)}")
        if getattr(edge, "reference_time", None):
            dates.append(f"reference_time={short_date(edge.reference_time)}")
        if dates:
            print(f"   时间：{'; '.join(dates)}")
        evidence = attrs.get("evidence_ids") or attrs.get("primary_evidence_id")
        if evidence:
            print(f"   证据：{evidence}")
        if attrs.get("relationship_status"):
            print(f"   关系状态：{attrs.get('relationship_status')}")
        if attrs.get("relationship_type"):
            print(f"   关系类型：{attrs.get('relationship_type')}")
        if attrs.get("requires_internal_validation") is not None:
            print(f"   是否需要内部验证：{attrs.get('requires_internal_validation')}")
        for field, label in [
            ("data_as_of", "数据截至"),
            ("first_seen_at", "首次入库"),
            ("last_verified_at", "最近核验"),
            ("source_publish_dates", "证据发布日期"),
            ("source_retrieved_dates", "证据检索日期"),
            ("current_validity", "当前有效性"),
            ("claim_nature", "判断性质"),
        ]:
            if attrs.get(field):
                print(f"   {label}：{attrs.get(field)}")
        if attrs.get("deterministic_backfill"):
            print("   来源：deterministic_backfill")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--neo4j-uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--neo4j-user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--neo4j-password", default=os.getenv("NEO4J_PASSWORD", "password"))
    parser.add_argument("--group-id", default="semiconductor_dc_kg")
    parser.add_argument("--num-results", type=int, default=8)
    parser.add_argument("--answer-provider", choices=["auto", "none"], default="auto")
    parser.add_argument("--answer-context-edges", type=int, default=10)
    parser.add_argument("--deepseek-base-url", default="https://api.deepseek.com")
    parser.add_argument("--deepseek-model", default="deepseek-chat")
    parser.add_argument("--deepseek-timeout", type=int, default=60)
    parser.add_argument("--llm-base-url", default="https://api.siliconflow.cn/v1")
    parser.add_argument("--llm-model", default="deepseek-ai/DeepSeek-V3.2")
    parser.add_argument("--embedding-base-url", default="https://api.siliconflow.cn/v1")
    parser.add_argument("--embedding-model", default="BAAI/bge-m3")
    return parser


def main() -> int:
    return asyncio.run(run(build_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
