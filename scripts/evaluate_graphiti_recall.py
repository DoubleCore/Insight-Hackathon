from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GRAPHITI_ROOT = ROOT / "graphiti-main" / "graphiti-main"
sys.path.insert(0, str(GRAPHITI_ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "apps" / "api-server"))

from graphiti_core import Graphiti  # type: ignore  # noqa: E402
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig  # type: ignore  # noqa: E402
from graphiti_core.llm_client.config import LLMConfig  # type: ignore  # noqa: E402
from graphiti_core.llm_client.openai_generic_client import (  # type: ignore  # noqa: E402
    OpenAIGenericClient,
)

from load_ai_keys import DEFAULT_KEY_FILE, load_service_keys  # noqa: E402
from app.services.retrieval import SiliconFlowReranker  # noqa: E402
from query_graphiti import (  # noqa: E402
    lexical_fallback_search,
    merge_edges,
    rank_edges,
    should_augment_with_lexical,
    should_prefer_lexical_first,
)


DEFAULT_GOLD = ROOT / "data" / "graphiti" / "retrieval_eval_gold.jsonl"
DEFAULT_RESULTS = ROOT / "data" / "graphiti" / "retrieval_eval_results.csv"
DEFAULT_REPORT = ROOT / "data" / "graphiti" / "retrieval_eval_report.md"
MODES = ("semantic_only", "lexical_only", "hybrid")
TERM_ALIASES = {
    "龙头": ["leader"],
    "全球龙头": ["global leader", "global leaders"],
    "国内龙头": ["domestic leader", "domestic leaders"],
    "公开可验证": ["confirmed_public_relationship"],
    "内部验证": ["internal validation", "requires_internal_validation"],
    "需要内部验证": ["needs_internal_validation", "requires_internal_validation"],
    "潜在匹配": ["potential_fit"],
    "晶圆代工": ["foundry", "wafer fabrication", "wafer foundry"],
    "晶圆制造": ["wafer fabrication", "wafer manufacturing"],
    "先进封装": ["advanced packaging"],
    "刻蚀": ["etch", "etching"],
    "光刻": ["lithography"],
    "设备": ["equipment"],
    "材料": ["materials"],
    "存储": ["memory", "storage"],
    "供应": ["supply", "supplies", "supplier"],
    "合作": ["collaborates", "collaboration", "partner"],
    "授权": ["license", "licensing", "authorization"],
    "系统伙伴": ["system partner", "partner"],
    "数据截至时间": ["data_as_of"],
    "最近核验时间": ["last_verified_at"],
    "证据发布日期": ["source_publish_dates"],
    "年报": ["annual report"],
    "EDA软件": ["EDA software"],
    "AI服务器": ["AI server", "AI servers"],
    "数据中心基础设施": ["data center infrastructure"],
    "主控": ["controller", "main control"],
}


@dataclass
class ExpectedMatch:
    label: str
    record_ids: list[str]
    any_evidence_ids: list[str]
    entities: list[str]
    fact_keywords: list[str]
    any_fact_keywords: list[str]
    source: str
    target: str
    allow_reverse: bool


@dataclass
class GoldItem:
    item_id: str
    category: str
    question: str
    min_required_hits: int
    expected_matches: list[ExpectedMatch]


@dataclass
class MatchResult:
    expected: ExpectedMatch
    rank: int | None
    fact: str


def split_ids(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).replace(",", ";").split(";") if part.strip()]


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def normalize_expected(raw: dict[str, Any]) -> list[ExpectedMatch]:
    matches = raw.get("expected_matches") or []
    if not matches:
        matches = [
            {
                "label": raw.get("id", "expected"),
                "any_evidence_ids": raw.get("expected_evidence_ids", []),
                "fact_keywords": raw.get("expected_fact_keywords", []),
            }
        ]

    normalized: list[ExpectedMatch] = []
    for index, match in enumerate(matches, start=1):
        record_ids = split_ids(match.get("record_ids") or match.get("expected_record_ids"))
        evidence_ids = split_ids(
            match.get("any_evidence_ids")
            or match.get("evidence_ids")
            or match.get("expected_evidence_ids")
        )
        label = str(match.get("label") or f"expected_{index}")
        normalized.append(
            ExpectedMatch(
                label=label,
                record_ids=record_ids,
                any_evidence_ids=evidence_ids,
                entities=as_list(match.get("entities")),
                fact_keywords=as_list(match.get("fact_keywords")),
                any_fact_keywords=as_list(match.get("any_fact_keywords")),
                source=str(match.get("source") or ""),
                target=str(match.get("target") or ""),
                allow_reverse=bool(match.get("allow_reverse", True)),
            )
        )
    return normalized


def load_gold(path: Path, limit: int | None = None) -> list[GoldItem]:
    items: list[GoldItem] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            expected_matches = normalize_expected(raw)
            if not expected_matches:
                raise ValueError(f"{path}:{line_no} has no expected matches")
            items.append(
                GoldItem(
                    item_id=str(raw["id"]),
                    category=str(raw.get("category") or "未分类"),
                    question=str(raw["question"]),
                    min_required_hits=int(raw.get("min_required_hits") or 1),
                    expected_matches=expected_matches,
                )
            )
            if limit and len(items) >= limit:
                break
    return items


def edge_attr(edge: Any, name: str) -> str:
    direct = getattr(edge, name, None)
    if direct not in (None, ""):
        return str(direct)
    attrs = getattr(edge, "attributes", {}) or {}
    value = attrs.get(name)
    return "" if value is None else str(value)


def edge_search_text(edge: Any) -> str:
    attrs = getattr(edge, "attributes", {}) or {}
    parts = [
        getattr(edge, "source", ""),
        getattr(edge, "target", ""),
        getattr(edge, "name", ""),
        getattr(edge, "fact", ""),
    ]
    parts.extend(str(value) for value in attrs.values() if value not in (None, ""))
    return " ".join(str(part) for part in parts if part not in (None, ""))


def term_variants(term: str) -> list[str]:
    variants = [term]
    variants.extend(TERM_ALIASES.get(term, []))
    return [variant for variant in variants if variant]


def contains_term(text: str, term: str) -> bool:
    text_lower = text.lower()
    return any(variant.lower() in text_lower for variant in term_variants(term))


def contains_all(text: str, terms: list[str]) -> bool:
    return all(contains_term(text, term) for term in terms if term)


def contains_any(text: str, terms: list[str]) -> bool:
    return not terms or any(contains_term(text, term) for term in terms if term)


def endpoints_match(edge: Any, expected: ExpectedMatch) -> bool:
    if not expected.source and not expected.target:
        return True
    source = str(getattr(edge, "source", ""))
    target = str(getattr(edge, "target", ""))
    direct = (not expected.source or expected.source in source) and (
        not expected.target or expected.target in target
    )
    reverse = expected.allow_reverse and (not expected.source or expected.source in target) and (
        not expected.target or expected.target in source
    )
    return direct or reverse


def edge_matches(edge: Any, expected: ExpectedMatch) -> bool:
    text = edge_search_text(edge)
    if expected.record_ids:
        record_id = edge_attr(edge, "record_id")
        if record_id not in expected.record_ids:
            return False
    if expected.any_evidence_ids:
        evidence_text = " ".join(
            [
                edge_attr(edge, "evidence_ids"),
                edge_attr(edge, "primary_evidence_id"),
                str(getattr(edge, "fact", "")),
            ]
        )
        if not contains_any(evidence_text, expected.any_evidence_ids):
            return False
    if expected.entities and not contains_all(text, expected.entities):
        return False
    if expected.fact_keywords and not contains_all(text, expected.fact_keywords):
        return False
    if expected.any_fact_keywords and not contains_any(text, expected.any_fact_keywords):
        return False
    return endpoints_match(edge, expected)


def score_edges(edges: list[Any], item: GoldItem, k: int) -> tuple[list[MatchResult], float, int, int, float]:
    prefix = edges[:k]
    match_results: list[MatchResult] = []
    ranks: list[int] = []
    for expected in item.expected_matches:
        rank: int | None = None
        fact = ""
        for index, edge in enumerate(prefix, start=1):
            if edge_matches(edge, expected):
                rank = index
                fact = str(getattr(edge, "fact", ""))
                ranks.append(index)
                break
        match_results.append(MatchResult(expected=expected, rank=rank, fact=fact))
    hits = sum(1 for result in match_results if result.rank is not None)
    recall = hits / len(item.expected_matches)
    hit = 1 if hits > 0 else 0
    strict_hit = 1 if hits >= min(item.min_required_hits, len(item.expected_matches)) else 0
    mrr = 1 / min(ranks) if ranks else 0.0
    return match_results, recall, hit, strict_hit, mrr


def summarize_edge(edge: Any) -> str:
    source = str(getattr(edge, "source", ""))
    target = str(getattr(edge, "target", ""))
    name = str(getattr(edge, "name", ""))
    fact = str(getattr(edge, "fact", "")).replace("\n", " ")
    if len(fact) > 120:
        fact = fact[:117] + "..."
    return f"{source}->{target} [{name}] {fact}"


def make_query_args(args: argparse.Namespace, question: str, num_results: int) -> SimpleNamespace:
    return SimpleNamespace(
        question=question,
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password,
        group_id=args.group_id,
        num_results=num_results,
    )


def build_graphiti(args: argparse.Namespace) -> Graphiti:
    siliconflow_key = os.getenv("SILICONFLOW_API_KEY", "")
    if not siliconflow_key and DEFAULT_KEY_FILE.exists():
        keys = load_service_keys(DEFAULT_KEY_FILE, ["siliconflow"])
        siliconflow_key = keys.get("SILICONFLOW_API_KEY", "")
    if not siliconflow_key:
        raise RuntimeError("missing SILICONFLOW_API_KEY for Graphiti semantic search")

    llm_config = LLMConfig(
        api_key=siliconflow_key,
        model=args.llm_model,
        small_model=args.llm_model,
        base_url=args.llm_base_url,
        temperature=0,
    )
    llm_client = OpenAIGenericClient(config=llm_config, structured_output_mode="json_object")
    embedder = OpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            api_key=siliconflow_key,
            base_url=args.embedding_base_url,
            embedding_model=args.embedding_model,
        )
    )
    cross_encoder = SiliconFlowReranker(
        api_key=siliconflow_key,
        base_url=args.llm_base_url,
        model=args.reranker_model,
    )
    return Graphiti(
        args.neo4j_uri,
        args.neo4j_user,
        args.neo4j_password,
        llm_client=llm_client,
        embedder=embedder,
        cross_encoder=cross_encoder,
    )


async def semantic_search(graphiti: Graphiti, args: argparse.Namespace, item: GoldItem) -> tuple[list[Any], str]:
    try:
        edges = await graphiti.search(
            item.question,
            group_ids=[args.group_id],
            num_results=max(args.k_values),
        )
    except Exception as exc:  # noqa: BLE001 - report retrieval failures in eval output.
        return [], f"{type(exc).__name__}: {exc}"
    return list(edges), ""


def dedupe_edges(edges: list[Any]) -> list[Any]:
    deduped: list[Any] = []
    seen: set[str] = set()
    for edge in edges:
        key = str(getattr(edge, "uuid", "")) or summarize_edge(edge)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(edge)
    return deduped


async def retrieve_for_item(
    graphiti: Graphiti | None,
    args: argparse.Namespace,
    item: GoldItem,
) -> dict[str, tuple[list[Any], str]]:
    query_args = make_query_args(args, item.question, max(args.k_values))
    needs_semantic = "semantic_only" in args.modes or "hybrid" in args.modes
    semantic_edges: list[Any] = []
    semantic_error = ""
    if needs_semantic:
        if graphiti is None:
            semantic_error = "semantic search disabled"
        else:
            semantic_edges, semantic_error = await semantic_search(graphiti, args, item)

    lexical_edges: list[Any] | None = None

    def get_lexical() -> list[Any]:
        nonlocal lexical_edges
        if lexical_edges is None:
            lexical_edges = lexical_fallback_search(query_args, reason=None, announce=False)
        return lexical_edges

    results: dict[str, tuple[list[Any], str]] = {}
    if "semantic_only" in args.modes:
        results["semantic_only"] = (dedupe_edges(rank_edges(semantic_edges, max(args.k_values))), semantic_error)
    if "lexical_only" in args.modes:
        results["lexical_only"] = (
            dedupe_edges(rank_edges(get_lexical(), max(args.k_values))),
            "",
        )
    if "hybrid" in args.modes:
        if semantic_error:
            hybrid_edges = get_lexical()
            error = f"semantic failed; fallback lexical: {semantic_error}"
        elif should_augment_with_lexical(item.question):
            lex = get_lexical()
            if should_prefer_lexical_first(item.question):
                hybrid_edges = merge_edges(lex, semantic_edges, max(args.k_values))
            else:
                hybrid_edges = merge_edges(semantic_edges, lex, max(args.k_values))
            error = ""
        else:
            hybrid_edges = semantic_edges
            error = ""
        results["hybrid"] = (dedupe_edges(rank_edges(hybrid_edges, max(args.k_values))), error)
    return results


def aggregate(rows: list[dict[str, Any]], group_fields: list[str]) -> list[dict[str, Any]]:
    buckets: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = tuple(row[field] for field in group_fields)
        buckets[key].append(row)
    summary: list[dict[str, Any]] = []
    for key, values in sorted(buckets.items()):
        item = {field: key[index] for index, field in enumerate(group_fields)}
        item.update(
            {
                "questions": len(values),
                "avg_recall": sum(float(row["recall"]) for row in values) / len(values),
                "hit_rate": sum(int(row["hit"]) for row in values) / len(values),
                "strict_hit_rate": sum(int(row["strict_hit"]) for row in values) / len(values),
                "avg_mrr": sum(float(row["mrr"]) for row in values) / len(values),
            }
        )
        summary.append(item)
    return summary


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id",
        "category",
        "mode",
        "k",
        "question",
        "expected_count",
        "min_required_hits",
        "hits",
        "recall",
        "hit",
        "strict_hit",
        "mrr",
        "matched",
        "missed",
        "retrieval_error",
        "top_edges",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def fmt_rate(value: float) -> str:
    return f"{value:.3f}"


def write_report(path: Path, rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    by_mode = aggregate(rows, ["mode", "k"])
    by_category = aggregate([row for row in rows if int(row["k"]) == args.primary_k], ["mode", "category"])
    failures = [
        row
        for row in rows
        if row["mode"] == "hybrid" and int(row["k"]) == args.primary_k and int(row["hit"]) == 0
    ]

    lines = [
        "# Graphiti 问答召回评估报告",
        "",
        f"- Gold 问题数：{len({row['id'] for row in rows})}",
        f"- 检索模式：{', '.join(args.modes)}",
        f"- K 值：{', '.join(str(k) for k in args.k_values)}",
        f"- 主验收 K：{args.primary_k}",
        "",
        "## 整体指标",
        "",
        "| mode | K | questions | Recall@K | Hit@K | Strict Hit@K | MRR@K |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in by_mode:
        lines.append(
            "| {mode} | {k} | {questions} | {recall} | {hit} | {strict_hit} | {mrr} |".format(
                mode=row["mode"],
                k=row["k"],
                questions=row["questions"],
                recall=fmt_rate(row["avg_recall"]),
                hit=fmt_rate(row["hit_rate"]),
                strict_hit=fmt_rate(row["strict_hit_rate"]),
                mrr=fmt_rate(row["avg_mrr"]),
            )
        )

    lines.extend(
        [
            "",
            f"## 分类指标（K={args.primary_k}）",
            "",
            "| mode | category | questions | Recall | Hit Rate | Strict Hit Rate | MRR |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in by_category:
        lines.append(
            "| {mode} | {category} | {questions} | {recall} | {hit} | {strict_hit} | {mrr} |".format(
                mode=row["mode"],
                category=row["category"],
                questions=row["questions"],
                recall=fmt_rate(row["avg_recall"]),
                hit=fmt_rate(row["hit_rate"]),
                strict_hit=fmt_rate(row["strict_hit_rate"]),
                mrr=fmt_rate(row["avg_mrr"]),
            )
        )

    lines.extend(["", f"## Hybrid 未命中问题（K={args.primary_k}）", ""])
    if failures:
        for row in failures:
            lines.append(f"- `{row['id']}` {row['question']}：漏召回 {row['missed']}")
    else:
        lines.append("- 无。")

    lines.extend(
        [
            "",
            "## 口径说明",
            "",
            "- 本报告只评估检索召回，不评估 DeepSeek 最终答案生成质量。",
            "- 命中规则支持 evidence ID、实体名、事实关键词组合匹配；不依赖 Graphiti 自动生成的 uuid。",
            "- `stage8_business_opportunities.csv` 未进入 Graphiti，因此不作为 gold 标准事实。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run(args: argparse.Namespace) -> int:
    args.gold = Path(args.gold)
    args.results_csv = Path(args.results_csv)
    args.report_md = Path(args.report_md)
    args.modes = list(dict.fromkeys(args.modes))
    args.k_values = sorted(set(args.k_values))
    args.primary_k = args.primary_k or 8
    if args.primary_k not in args.k_values:
        args.k_values.append(args.primary_k)
        args.k_values = sorted(set(args.k_values))

    invalid_modes = [mode for mode in args.modes if mode not in MODES]
    if invalid_modes:
        raise ValueError(f"unsupported modes: {', '.join(invalid_modes)}")

    items = load_gold(args.gold, args.limit)
    graphiti: Graphiti | None = None
    if "semantic_only" in args.modes or "hybrid" in args.modes:
        graphiti = build_graphiti(args)

    rows: list[dict[str, Any]] = []
    try:
        for index, item in enumerate(items, start=1):
            print(f"[{index}/{len(items)}] {item.id if hasattr(item, 'id') else item.item_id}: {item.question}")
            retrieved = await retrieve_for_item(graphiti, args, item)
            for mode, (edges, retrieval_error) in retrieved.items():
                for k in args.k_values:
                    match_results, recall, hit, strict_hit, mrr = score_edges(edges, item, k)
                    matched = [
                        f"{result.expected.label}@{result.rank}"
                        for result in match_results
                        if result.rank is not None
                    ]
                    missed = [
                        result.expected.label
                        for result in match_results
                        if result.rank is None
                    ]
                    rows.append(
                        {
                            "id": item.item_id,
                            "category": item.category,
                            "mode": mode,
                            "k": k,
                            "question": item.question,
                            "expected_count": len(item.expected_matches),
                            "min_required_hits": item.min_required_hits,
                            "hits": len(matched),
                            "recall": f"{recall:.6f}",
                            "hit": hit,
                            "strict_hit": strict_hit,
                            "mrr": f"{mrr:.6f}",
                            "matched": "; ".join(matched),
                            "missed": "; ".join(missed),
                            "retrieval_error": retrieval_error,
                            "top_edges": " || ".join(summarize_edge(edge) for edge in edges[:k]),
                        }
                    )
    finally:
        if graphiti is not None:
            close_reranker = getattr(graphiti.cross_encoder, "close", None)
            if close_reranker is not None:
                await close_reranker()
            await graphiti.close()

    write_csv(args.results_csv, rows)
    write_report(args.report_md, rows, args)

    primary_rows = [
        row for row in rows if row["mode"] == "hybrid" and int(row["k"]) == args.primary_k
    ]
    if primary_rows:
        recall = sum(float(row["recall"]) for row in primary_rows) / len(primary_rows)
        hit_rate = sum(int(row["hit"]) for row in primary_rows) / len(primary_rows)
        print(
            f"Hybrid@{args.primary_k}: recall={recall:.3f}, hit_rate={hit_rate:.3f}, "
            f"questions={len(primary_rows)}"
        )
    print(f"Wrote CSV: {args.results_csv}")
    print(f"Wrote report: {args.report_md}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate Graphiti retrieval recall against a gold set.")
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--results-csv", default=str(DEFAULT_RESULTS))
    parser.add_argument("--report-md", default=str(DEFAULT_REPORT))
    parser.add_argument("--limit", type=int, default=None, help="Only evaluate first N gold questions.")
    parser.add_argument("--modes", nargs="+", default=list(MODES), choices=list(MODES))
    parser.add_argument("--k-values", nargs="+", type=int, default=[5, 8, 10, 20])
    parser.add_argument("--primary-k", type=int, default=8)
    parser.add_argument("--neo4j-uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--neo4j-user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--neo4j-password", default=os.getenv("NEO4J_PASSWORD", "password"))
    parser.add_argument("--group-id", default="semiconductor_dc_kg")
    parser.add_argument("--llm-base-url", default="https://api.siliconflow.cn/v1")
    parser.add_argument("--llm-model", default="deepseek-ai/DeepSeek-V3.2")
    parser.add_argument("--embedding-base-url", default="https://api.siliconflow.cn/v1")
    parser.add_argument("--embedding-model", default="BAAI/bge-m3")
    parser.add_argument("--reranker-model", default="BAAI/bge-reranker-v2-m3")
    return parser


def main() -> int:
    return asyncio.run(run(build_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
