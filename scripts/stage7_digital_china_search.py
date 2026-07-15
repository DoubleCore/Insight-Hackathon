from __future__ import annotations

import argparse
import csv
import json
import time
import sys
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import business_graph_enrichment as enrichment
from scripts.stage2_company_leaders import alias_matches, search_bocha, search_tavily


RELATIONS_PATH = ROOT / "data" / "business_graph" / "stage7_digital_china_relations.csv"
EVIDENCE_PATH = ROOT / "data" / "evidence" / "evidence_stage_7_digital_china.jsonl"
OPPORTUNITIES_PATH = ROOT / "data" / "business_graph" / "stage8_business_opportunities.csv"
COMPANY_PRODUCT_RELATIONS_PATH = ROOT / "data" / "business_graph" / "stage6_company_product_relations.csv"
SUMMARY_PATH = ROOT / "data" / "business_graph" / "stage7_digital_china_search_summary.md"

RELATION_TERMS = [
    "合作",
    "伙伴",
    "生态",
    "解决方案",
    "中标",
    "招投标",
    "代理",
    "分销",
    "签约",
    "联合",
    "适配",
    "认证",
    "鲲鹏",
    "昇腾",
    "国产算力",
    "AI服务器",
    "数据中心",
    "云基础设施",
    "partner",
    "partnership",
    "solution",
    "distributor",
    "reseller",
    "alliance",
]

BLOCKED_SOURCE_MARKERS = [
    "guba",
    "mguba",
    "xueqiu.com",
    "doc88.com",
    "taodocs.com",
    "51sole.com",
    "book118.com",
    "528045.com",
    "股吧",
    "聊吧",
    "雪球",
    "道客巴巴",
    "淘豆",
    "原创力文档",
]

CONFIRMED_TERMS = [
    "合作",
    "伙伴",
    "生态",
    "中标",
    "招投标",
    "代理",
    "分销",
    "签约",
    "联合",
    "适配",
    "认证",
    "partner",
    "partnership",
    "distributor",
    "reseller",
    "alliance",
]

STATUS_RANK = {
    "no_public_evidence": 0,
    "potential_fit": 1,
    "needs_internal_validation": 2,
    "confirmed_public_relationship": 3,
}

CONFIDENCE_RANK = {
    "low": 0,
    "medium-low": 1,
    "medium": 2,
    "high": 3,
}

# 强确认词：命中且证据等级 A/A- 才可能升"生态伙伴"，否则 confirmed -> 潜力客户
STRONG_CONFIRM_TERMS = [
    "战略合作", "合作协议", "签署", "签约", "总经销", "总代理",
    "分销协议", "授权代理", "授权经销商", "中标", "联合发布", "联合推出",
    "伙伴认证", "生态合作", "战略协议",
    "partnership agreement", "signed", "distributor", "reseller",
]

# 弱关系词：仅命中这些单词（无强词）-> needs_internal_validation（不再直升 confirmed）
WEAK_RELATION_TERMS = ["合作", "伙伴", "联合", "适配", "认证", "partner", "alliance"]

# "数字中国"政策语料拒绝标记（与神州数码无关）
DIGITAL_CHINA_POLICY_MARKERS = [
    "数字中国建设", "数字中国峰会", "digital china summit",
    "数字中国创新大赛", "数字中国成果展",
]


@dataclass(frozen=True)
class SearchSpec:
    company_name: str
    aliases: tuple[str, ...]
    queries: tuple[str, ...]
    relationship_type: str
    fallback_status: str = "potential_fit"
    fallback_claim: str = ""


SEARCH_SPECS = [
    SearchSpec(
        company_name="华为",
        aliases=("华为", "Huawei"),
        relationship_type="生态合作/解决方案匹配",
        queries=(
            "神州数码 华为 合作 伙伴 解决方案",
            "神州数码 华为 鲲鹏 昇腾 国产算力",
            "神州数码 华为 云 数据中心 生态",
        ),
        fallback_status="confirmed_public_relationship",
        fallback_claim="神州数码与华为生态、鲲鹏/昇腾/国产算力相关业务存在公开业务关联线索。",
    ),
    SearchSpec(
        company_name="浪潮信息",
        aliases=("浪潮信息", "Inspur"),
        relationship_type="AI服务器/数据中心潜在商机",
        queries=(
            "神州数码 浪潮信息 合作 AI服务器 数据中心",
            "神州数码 浪潮 服务器 解决方案 合作",
            "Digital China Inspur AI server partnership",
        ),
        fallback_claim="浪潮信息处于AI服务器和数据中心基础设施重点环节，与神州数码系统集成、算力基础设施方案存在潜在业务匹配。",
    ),
    SearchSpec(
        company_name="NVIDIA",
        aliases=("NVIDIA", "英伟达", "Nvidia"),
        relationship_type="AI算力生态潜在协同",
        queries=(
            "神州数码 NVIDIA 英伟达 合作 AI服务器",
            "神州数码 英伟达 GPU 解决方案",
            "Digital China NVIDIA AI GPU partnership",
        ),
        fallback_claim="NVIDIA 是AI GPU和加速计算生态核心企业，与AI服务器、数据中心和算力解决方案高度相关。",
    ),
    SearchSpec(
        company_name="联想",
        aliases=("联想", "Lenovo"),
        relationship_type="服务器/终端/ICT潜在协同",
        queries=(
            "神州数码 联想 合作 服务器 数据中心",
            "神州数码 Lenovo 合作 解决方案",
            "神州数码 联想 分销 代理",
        ),
        fallback_claim="联想覆盖服务器、PC和AI终端系统，与神州数码ICT渠道和系统集成业务存在潜在业务相关性。",
    ),
    SearchSpec(
        company_name="中兴通讯",
        aliases=("中兴通讯", "中兴", "ZTE"),
        relationship_type="ICT方案潜在协同",
        queries=(
            "神州数码 中兴通讯 合作 ICT 解决方案",
            "神州数码 中兴 数据中心 网络设备",
            "Digital China ZTE partnership solution",
        ),
        fallback_claim="中兴通讯属于通信设备和数据中心基础设施相关公司，与神州数码ICT集成和渠道能力存在潜在方案协同空间。",
    ),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def combined_text(row: dict[str, Any]) -> str:
    return " ".join(str(row.get(field, "")) for field in ("title", "snippet", "url", "query"))


def result_text(row: dict[str, Any]) -> str:
    return " ".join(str(row.get(field, "")) for field in ("title", "snippet", "url"))


def has_any_term(text: str, terms: list[str] | tuple[str, ...]) -> bool:
    return any(alias_matches(text, term) for term in terms)


def is_blocked_source(hit: dict[str, Any]) -> bool:
    text = result_text(hit).lower()
    return any(marker.lower() in text for marker in BLOCKED_SOURCE_MARKERS)


def confuses_digital_china_information(company_name: str, text: str) -> bool:
    """拒绝与神州数码无关的混淆来源：
    1) 神州信息（dcits）冒充神州数码；
    2) "数字中国"政策语料（峰会/建设/成果展等）误命中 "Digital China"。
    去掉原有对华为/NVIDIA 等 5 家的白名单豁免（一律按规则判定，避免漏判）。
    """
    low = text.lower()
    # 数字中国政策语料：含政策标记且不含任何神州数码实体指代 -> 拒绝
    has_policy = any(marker.lower() in low for marker in DIGITAL_CHINA_POLICY_MARKERS)
    has_dc_entity = (
        "神州数码" in text or "000034" in text or "神州鲲泰" in text
        or "digitalchina.com" in low or "digital china holdings" in low
    )
    if has_policy and not has_dc_entity:
        return True
    # 神州信息冒充：含 dcits/神州信息 但不含神州数码集团实体
    mentions_dcits = "神州信息" in text or "神州数码信息服务股份有限公司" in text or "dcits" in low
    mentions_group = "神州数码集团" in text or "000034" in text or "神州数码股份有限公司" in text
    return mentions_dcits and not mentions_group


def source_grade(url: str, title: str) -> str:
    combined = f"{url} {title}".lower()
    if any(domain in combined for domain in ["digitalchina.com", "huawei.com", "lenovo.com", "zte.com.cn", "nvidia.com", "inspur.com"]):
        return "A"
    if any(domain in combined for domain in ["cninfo.com.cn", "sse.com.cn", "szse.cn", "gov.cn"]):
        return "A"
    if any(domain in combined for domain in ["36kr", "eet", "ofweek", "csdn", "donews", "ithome"]):
        return "B"
    return "B-"


def _split_sentences(text: str) -> list[str]:
    """按句分隔符切分（用于句级共现判定）。"""
    buf = ""
    sentences = []
    for ch in text:
        buf += ch
        if ch in "。；;！!？?\n":
            if buf.strip():
                sentences.append(buf.strip())
            buf = ""
    if buf.strip():
        sentences.append(buf.strip())
    return sentences


def infer_status(text: str, company_name: str = "", aliases: list[str] | tuple[str, ...] = ()) -> str:
    """三级判定（修复 combined_text query 污染 bug）：
    - 强确认词命中 -> confirmed_public_relationship；
    - 仅弱关系词（合作/伙伴等单词）命中 -> needs_internal_validation（不再直升 confirmed）；
    - 场景词命中 -> potential_fit；
    - 都不命中 -> no_public_evidence。
    若提供 company_name+aliases，进一步要求"神州数码"与目标公司在同一句共现才可 confirmed。
    """
    if has_any_term(text, STRONG_CONFIRM_TERMS):
        # 句级共现校验（若提供了公司别名）
        if company_name and aliases:
            dc_aliases = ("神州数码", "神州鲲泰", "Digital China")
            for sent in _split_sentences(text):
                has_dc = any(a in sent for a in dc_aliases)
                has_target = any(alias_matches(sent, a) for a in aliases)
                if has_dc and has_target:
                    return "confirmed_public_relationship"
            # 强词命中但无同句共现 -> 降级为需内部验证
            return "needs_internal_validation"
        return "confirmed_public_relationship"
    if has_any_term(text, WEAK_RELATION_TERMS):
        return "needs_internal_validation"
    if has_any_term(text, RELATION_TERMS):
        return "potential_fit"
    return "no_public_evidence"


def infer_confidence(status: str, url: str, title: str) -> str:
    grade = source_grade(url, title)
    if status == "confirmed_public_relationship" and grade == "A":
        return "high"
    if status == "confirmed_public_relationship":
        return "medium"
    if status == "potential_fit":
        return "medium-low"
    return "low"


def filter_relevant_hits(
    company_name: str,
    aliases: list[str] | tuple[str, ...],
    hits: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    relevant: list[dict[str, Any]] = []
    for hit in hits:
        if is_blocked_source(hit):
            continue
        text = result_text(hit)
        if confuses_digital_china_information(company_name, text):
            continue
        mentions_digital_china = has_any_term(text, ("神州数码", "Digital China", "神州鲲泰"))
        mentions_target = has_any_term(text, aliases)
        mentions_relation = has_any_term(text, RELATION_TERMS)
        if mentions_digital_china and mentions_target and mentions_relation:
            relevant.append(hit)
    return relevant


def relationship_claim(company_name: str, status: str, hit: dict[str, Any]) -> str:
    snippet = str(hit.get("snippet", "")).strip()
    title = str(hit.get("title", "")).strip()
    base = snippet or title
    if len(base) > 220:
        base = base[:217] + "..."
    if status == "confirmed_public_relationship":
        return f"公开搜索结果显示神州数码与{company_name}存在合作、伙伴、生态、分销、招投标或解决方案相关线索：{base}"
    if status == "potential_fit":
        return f"公开搜索结果显示{company_name}与神州数码目标业务场景存在匹配线索：{base}"
    return f"公开搜索暂未发现神州数码与{company_name}的直接关系证据。"


def search_hit_to_evidence(evidence_id: str, company_name: str, hit: dict[str, Any], aliases: list[str] | tuple[str, ...] = ()) -> dict[str, Any]:
    # 修复：用 result_text（title+snippet+url，不含 query），杜绝 query 自带"合作"导致的自动 confirmed
    text = result_text(hit)
    status = infer_status(text, company_name, aliases)
    title = str(hit.get("title", ""))
    url = str(hit.get("url", ""))
    confidence = infer_confidence(status, url, title)
    return {
        "evidence_id": evidence_id,
        "task_id": "S7-digital-china-public-search",
        "company_name": company_name,
        "relationship_status": status,
        "relationship_type": "",
        "source_title": title,
        "source_url_or_file": url,
        "source_type": "public_search",
        "publish_date": hit.get("publish_date", ""),
        "evidence_excerpt": str(hit.get("snippet", ""))[:900],
        "possible_claim": relationship_claim(company_name, status, hit),
        "confidence": confidence,
        "limitations": "公开资料不能证明内部CRM客户关系；只能证明公开合作、生态关系、产品/场景匹配或潜在业务相关性。",
        "retrieved_at": now_iso(),
        "source_grade": source_grade(url, title),
        "search_tool": hit.get("search_tool", ""),
        "query": hit.get("query", ""),
    }


def seed_evidence_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in enrichment.DIGITAL_CHINA_PUBLIC_RELATIONS:
        rows.append(
            {
                "evidence_id": item["evidence_id"],
                "task_id": "S7-digital-china-public-relations",
                "company_name": item["company_name"],
                "relationship_status": item["relationship_status"],
                "relationship_type": item["relationship_type"],
                "source_title": item["source_title"],
                "source_url_or_file": item["source_url_or_file"],
                "source_type": "public_or_existing_evidence",
                "publish_date": "",
                "evidence_excerpt": item["evidence_excerpt"],
                "possible_claim": item["relationship_basis"],
                "confidence": item["confidence"],
                "limitations": "公开资料不能证明内部客户关系，需要内部客户/销售数据确认。",
                "retrieved_at": now_iso(),
                "source_grade": "B",
                "search_tool": "",
                "query": "",
            }
        )
    return rows


def merge_seed_and_search_evidence(
    seed_rows: list[dict[str, Any]],
    search_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    seen: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for row in [*seed_rows, *search_rows]:
        evidence_id = str(row.get("evidence_id", "")).strip()
        if not evidence_id:
            continue
        seen[evidence_id] = row
    return list(seen.values())


def strongest_status(rows: list[dict[str, Any]]) -> str:
    statuses = [str(row.get("relationship_status", "no_public_evidence")) for row in rows]
    confirmed_rows = [
        row for row in rows
        if str(row.get("relationship_status", "")) == "confirmed_public_relationship"
        and str(row.get("source_grade", "")) in {"A", "A-"}
    ]
    if confirmed_rows:
        return "confirmed_public_relationship"
    if "needs_internal_validation" in statuses:
        return "needs_internal_validation"
    if "potential_fit" in statuses:
        return "potential_fit"
    return "no_public_evidence"


def strongest_confidence(rows: list[dict[str, Any]]) -> str:
    return max(
        (str(row.get("confidence", "low")) for row in rows),
        key=lambda confidence: CONFIDENCE_RANK.get(confidence, 0),
    )


def build_relation_rows(evidence_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    grouped: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for row in evidence_rows:
        company = str(row.get("company_name", "")).strip()
        if company:
            grouped.setdefault(company, []).append(row)

    rows: list[dict[str, str]] = []
    for company, group in grouped.items():
        status = strongest_status(group)
        confidence = strongest_confidence(group)
        evidence_ids = sorted({str(row.get("evidence_id", "")).strip() for row in group if row.get("evidence_id")})
        relation_types = [
            str(row.get("relationship_type", "")).strip()
            for row in group
            if str(row.get("relationship_type", "")).strip()
        ]
        claims = [
            str(row.get("possible_claim", "")).strip()
            for row in group
            if str(row.get("possible_claim", "")).strip()
        ]
        rows.append(
            {
                "company_name": company,
                "relationship_status": status,
                "relationship_type": relation_types[0] if relation_types else "公开搜索关系线索",
                "relationship_basis": "；".join(claims[:4]),
                "evidence_ids": ";".join(evidence_ids),
                "confidence": confidence,
                "requires_internal_validation": "true",
                "limitations": "公开资料只证明公开合作/生态匹配/潜在业务相关性，不证明内部CRM客户关系。",
            }
        )
    return sorted(rows, key=lambda row: row["company_name"])


def collect_search_evidence(
    specs: list[SearchSpec] | None = None,
    search_bocha_fn: Callable[[str, int], list[dict[str, Any]]] = search_bocha,
    search_tavily_fn: Callable[[str, int], list[dict[str, Any]]] = search_tavily,
    count: int = 6,
    limit: int | None = None,
    sleep_seconds: float = 0.2,
) -> list[dict[str, Any]]:
    specs = specs or SEARCH_SPECS
    if limit is not None:
        if limit < 0:
            raise ValueError("limit must be non-negative")
        specs = specs[:limit]
    rows: list[dict[str, Any]] = []
    evidence_index = 1
    seen_urls: set[tuple[str, str]] = set()
    for spec in specs:
        for query in spec.queries:
            tool = "Tavily" if query.lower().startswith("digital china") else "Bocha"
            try:
                hits = search_tavily_fn(query, count) if tool == "Tavily" else search_bocha_fn(query, count)
            except Exception as exc:
                hits = [
                    {
                        "search_tool": tool,
                        "query": query,
                        "title": f"ERROR: {type(exc).__name__}",
                        "url": "",
                        "snippet": str(exc),
                        "publish_date": "",
                    }
                ]
            for hit in filter_relevant_hits(spec.company_name, spec.aliases, hits):
                key = (spec.company_name, str(hit.get("url", "")))
                if key in seen_urls:
                    continue
                seen_urls.add(key)
                evidence = search_hit_to_evidence(f"DC-S-{evidence_index:03d}", spec.company_name, hit, spec.aliases)
                evidence["relationship_type"] = spec.relationship_type
                rows.append(evidence)
                evidence_index += 1
            if sleep_seconds:
                time.sleep(sleep_seconds)
    return rows


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_summary(search_rows: list[dict[str, Any]], relation_rows: list[dict[str, str]], opportunities: list[dict[str, str]]) -> None:
    confirmed = [row for row in relation_rows if row["relationship_status"] == "confirmed_public_relationship"]
    lines = [
        "# Stage7 神州数码公开关系搜索增强汇总",
        "",
        f"- 生成时间：{now_iso()}",
        f"- 新增公开搜索证据：{len(search_rows)} 条",
        f"- 神州数码关系节点：{len(relation_rows)} 个",
        f"- confirmed_public_relationship：{len(confirmed)} 个",
        f"- Stage8 商机：{len(opportunities)} 条",
        "",
        "| 公司/主题 | 关系状态 | 置信度 | 证据ID |",
        "|---|---|---|---|",
    ]
    for row in relation_rows:
        lines.append(
            f"| {row['company_name']} | {row['relationship_status']} | {row['confidence']} | {row['evidence_ids']} |"
        )
    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_stage7_and_stage8(
    use_search: bool = True,
    limit: int | None = None,
    write_outputs: bool = True,
) -> dict[str, int]:
    seed_rows = seed_evidence_rows()
    search_rows = collect_search_evidence(limit=limit) if use_search else []
    evidence_rows = merge_seed_and_search_evidence(seed_rows, search_rows)
    relation_rows = build_relation_rows(evidence_rows)

    company_product_relations = read_csv(COMPANY_PRODUCT_RELATIONS_PATH)
    opportunities = enrichment.build_business_opportunities(relation_rows, company_product_relations)

    if write_outputs:
        write_jsonl(EVIDENCE_PATH, evidence_rows)
        write_csv(
            RELATIONS_PATH,
            relation_rows,
            [
                "company_name",
                "relationship_status",
                "relationship_type",
                "relationship_basis",
                "evidence_ids",
                "confidence",
                "requires_internal_validation",
                "limitations",
            ],
        )
        write_csv(
            OPPORTUNITIES_PATH,
            opportunities,
            [
                "opportunity_id",
                "company_name",
                "product_service_name",
                "l4_code",
                "l4_name",
                "opportunity_name",
                "opportunity_type",
                "opportunity_basis",
                "solution_name",
                "campaign_name",
                "margin_improvement_logic",
                "evidence_ids",
                "confidence",
                "requires_internal_validation",
                "limitations",
            ],
        )
        write_summary(search_rows, relation_rows, opportunities)
    return {
        "seed_evidence": len(seed_rows),
        "search_evidence": len(search_rows),
        "total_evidence": len(evidence_rows),
        "digital_china_relations": len(relation_rows),
        "opportunities": len(opportunities),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enhance Stage7 Digital China relations with public search evidence.")
    parser.add_argument("--no-search", action="store_true", help="Only rebuild from seed evidence.")
    parser.add_argument("--limit", type=int, default=None, help="Only search the first N configured company specs.")
    parser.add_argument("--dry-run", action="store_true", help="Run search and build rows without writing output files.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(
        json.dumps(
            generate_stage7_and_stage8(
                use_search=not args.no_search,
                limit=args.limit,
                write_outputs=not args.dry_run,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
