# -*- coding: utf-8 -*-
"""图谱质量审计：定位实体、关系、证据准确度风险。

该脚本只读数据，不修改任何 CSV/JSONL。目标是输出后续补证据和人工复核清单，
用于回应“实体和实体关系定义需要看准确度”的要求。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from kg_common import read_csv, read_jsonl, write_jsonl  # noqa: E402


DATA = ROOT / "data"
OUTPUT_PATH = DATA / "quality" / "graph_quality_audit.jsonl"

LEADERS = DATA / "company_pool" / "company_leaders_stage_3.csv"
RELATIONSHIPS = DATA / "company_pool" / "company_relationships_stage_4.csv"
LEADER_EVIDENCE = DATA / "evidence" / "evidence_stage_3.jsonl"
RELATIONSHIP_EVIDENCE = DATA / "evidence" / "evidence_stage_4_relationships.jsonl"
L1_L4 = DATA / "business_graph" / "stage5_l1_l4_segments.csv"
PRODUCTS = DATA / "business_graph" / "stage5_product_services.csv"
COMPANY_PRODUCT = DATA / "business_graph" / "stage6_company_product_relations.csv"
COMPETITION = DATA / "business_graph" / "stage6_company_competition.csv"
DC_RELATIONS = DATA / "business_graph" / "stage7_digital_china_relations.csv"
DC_EVIDENCE = DATA / "evidence" / "evidence_stage_7_digital_china.jsonl"

GRADE_RANK = {"A": 5, "A-": 4, "B": 3, "B-": 2, "C": 1, "": 0}
WEAK_SOURCE_TYPES = {"industry_search", "public_search"}
ABSTRACT_COMPANY_NAMES = {
    "国产算力",
    "AI服务器",
    "云基础设施",
    "数据中心",
    "汽车电子",
    "消费电子",
    "通信设备",
    "服务器",
    "网络",
    "存储",
}
FACT_RELATION_TYPES = {
    "PRODUCES",
    "SELLS",
    "USES",
    "PROCURES",
    "INTEGRATES",
}
PRESUMED_RELATION_TYPES = {"PROCURES", "竞争"}
CONFIRMED_RELATION_FORBIDDEN_TERMS = {
    "潜在",
    "待验证",
    "不能直接证明",
    "不能证明",
}
FOCUS_KEYWORDS = {
    "AI",
    "GPU",
    "服务器",
    "国产算力",
    "数据中心",
    "云基础设施",
    "通信设备",
    "智能终端",
    "网络",
    "存储",
    "汽车电子",
    "神州数码",
}


def evidence_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("evidence_id", "")).strip(): row for row in rows if row.get("evidence_id")}


def split_ids(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(";") if item.strip()]


def evidence_profile(evidence_ids: list[str], evidence_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    records = [evidence_by_id[eid] for eid in evidence_ids if eid in evidence_by_id]
    missing = [eid for eid in evidence_ids if eid not in evidence_by_id]
    grades = [str(row.get("source_grade", "")) for row in records]
    types = [str(row.get("source_type", "")) for row in records]
    best_grade = max(grades, key=lambda grade: GRADE_RANK.get(grade, 0), default="")
    official_count = sum(1 for grade in grades if GRADE_RANK.get(grade, 0) >= GRADE_RANK["A-"])
    search_only = bool(records) and all(source_type in WEAK_SOURCE_TYPES for source_type in types)
    weak = not records or search_only or GRADE_RANK.get(best_grade, 0) <= GRADE_RANK["B-"]
    return {
        "evidence_count": len(records),
        "missing_evidence_ids": missing,
        "best_grade": best_grade,
        "official_or_authoritative_count": official_count,
        "source_types": sorted(set(types)),
        "source_grades": grades,
        "search_only": search_only,
        "weak": weak,
    }


def issue(
    issue_type: str,
    severity: str,
    entity: str,
    relation: str,
    reason: str,
    row_ref: str,
    evidence_ids: list[str] | None = None,
    recommendation: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    combined = " ".join([issue_type, entity, relation, reason])
    priority = "P0" if any(keyword in combined for keyword in FOCUS_KEYWORDS) else "P1" if severity == "high" else "P2"
    return {
        "issue_type": issue_type,
        "priority": priority,
        "severity": severity,
        "entity": entity,
        "relation": relation,
        "reason": reason,
        "row_ref": row_ref,
        "evidence_ids": evidence_ids or [],
        "recommendation": recommendation,
        **(extra or {}),
    }


def audit_abstract_entities(
    rows: list[dict[str, str]],
    known_companies: set[str],
    evidence_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, start=2):
        name = row.get("company_name", "").strip()
        if name in ABSTRACT_COMPANY_NAMES:
            issues.append(issue(
                "abstract_entity_as_company",
                "high",
                name,
                "Company",
                "该名称更像产业方向、产品服务或场景，不应作为企业主体入图。",
                f"{DC_RELATIONS.name}:{idx}",
                split_ids(row.get("evidence_ids")),
                "改为 ProductService/业务场景/标签；不要画成 Company 节点。",
            ))
        elif name and name not in known_companies:
            evidence_ids = split_ids(row.get("evidence_ids"))
            profile = evidence_profile(evidence_ids, evidence_by_id)
            official_confirmed = (
                row.get("relationship_status") == "confirmed_public_relationship"
                and not profile["missing_evidence_ids"]
                and GRADE_RANK.get(profile["best_grade"], 0) >= GRADE_RANK["A-"]
            )
            if official_confirmed:
                continue
            issues.append(issue(
                "unknown_company_reference",
                "medium",
                name,
                "DigitalChinaRelation",
                "神州数码关系表引用了未出现在企业池中的名称。",
                f"{DC_RELATIONS.name}:{idx}",
                split_ids(row.get("evidence_ids")),
                "确认是否为企业；若不是企业，移出 Company 关系层。",
            ))
    return issues


def audit_leader_evidence(
    leaders: list[dict[str, str]],
    evidence_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for idx, row in enumerate(leaders, start=2):
        evidence_ids = split_ids(row.get("evidence_ids"))
        profile = evidence_profile(evidence_ids, evidence_by_id)
        if profile["missing_evidence_ids"]:
            issues.append(issue(
                "missing_leader_evidence",
                "high",
                row.get("company_name", ""),
                row.get("subsegment_name", ""),
                "龙头判断引用了不存在的证据 ID。",
                f"{LEADERS.name}:{idx}",
                evidence_ids,
                "修复证据 ID 或补录对应证据。",
                {"evidence_profile": profile},
            ))
        if profile["weak"] and row.get("confidence") == "high":
            issues.append(issue(
                "high_confidence_weak_leader_evidence",
                "high",
                row.get("company_name", ""),
                row.get("subsegment_name", ""),
                "龙头判断为 high，但证据主要来自搜索结果或 B- 来源。",
                f"{LEADERS.name}:{idx}",
                evidence_ids,
                "补官网、年报、招股书、交易所公告或权威市场份额报告；补强前建议降级或标注待复核。",
                {"evidence_profile": profile},
            ))
        elif profile["weak"]:
            issues.append(issue(
                "weak_leader_evidence",
                "medium",
                row.get("company_name", ""),
                row.get("subsegment_name", ""),
                "龙头判断证据偏弱，容易被追问依据。",
                f"{LEADERS.name}:{idx}",
                evidence_ids,
                "优先补权威来源，特别是重点 ICT/AI 基础设施相关环节。",
                {"evidence_profile": profile},
            ))
    return issues


def audit_company_product_relations(
    rows: list[dict[str, str]],
    evidence_by_id: dict[str, dict[str, Any]],
    product_names: set[str],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, start=2):
        evidence_ids = split_ids(row.get("evidence_ids"))
        profile = evidence_profile(evidence_ids, evidence_by_id)
        relation_type = row.get("relation_type", "")
        relation_label = f"{row.get('company_name', '')} -[{relation_type}]-> {row.get('product_service_name', '')}"
        if row.get("product_service_name", "") not in product_names:
            issues.append(issue(
                "unknown_product_service",
                "high",
                row.get("company_name", ""),
                relation_label,
                "公司-产品关系引用了受控产品服务表之外的名称。",
                f"{COMPANY_PRODUCT.name}:{idx}",
                evidence_ids,
                "补入受控词表或修正产品服务名称。",
            ))
        if relation_type not in FACT_RELATION_TYPES:
            issues.append(issue(
                "unknown_company_product_relation_type",
                "high",
                row.get("company_name", ""),
                relation_label,
                "公司-产品关系类型不在受控枚举内。",
                f"{COMPANY_PRODUCT.name}:{idx}",
                evidence_ids,
                "关系类型必须限定为 PRODUCES/SELLS/USES/PROCURES/INTEGRATES。",
            ))
        if row.get("requires_internal_validation") == "true":
            issues.append(issue(
                "requires_internal_validation",
                "medium",
                row.get("company_name", ""),
                relation_label,
                "该公司-产品关系仍需内部或人工验证。",
                f"{COMPANY_PRODUCT.name}:{idx}",
                evidence_ids,
                "补公开直接证据；若只是需求端推断，应保留待验证标记。",
                {"evidence_profile": profile},
            ))
        if relation_type == "PROCURES" and row.get("derivation") == "demand_side_presumed":
            issues.append(issue(
                "presumed_procurement_relation",
                "high",
                row.get("company_name", ""),
                relation_label,
                "需求端推断不应写成采购事实；没有直接证据时应表达为 USES/需求关联。",
                f"{COMPANY_PRODUCT.name}:{idx}",
                evidence_ids,
                "改为 USES，并保留 requires_internal_validation=true。",
            ))
        if profile["weak"] and relation_type not in PRESUMED_RELATION_TYPES:
            issues.append(issue(
                "weak_company_product_evidence",
                "medium",
                row.get("company_name", ""),
                relation_label,
                "事实型公司-产品关系证据偏弱。",
                f"{COMPANY_PRODUCT.name}:{idx}",
                evidence_ids,
                "优先补公司官网产品页、年报业务描述、公告或权威产品资料。",
                {"evidence_profile": profile},
            ))
    return issues


def audit_company_relationships(
    rows: list[dict[str, str]],
    evidence_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, start=2):
        evidence_ids = split_ids(row.get("evidence_ids"))
        profile = evidence_profile(evidence_ids, evidence_by_id)
        relation_label = (
            f"{row.get('source_company', '')} -[{row.get('relationship_type', '')}]-> "
            f"{row.get('target_company', '')}"
        )
        if profile["missing_evidence_ids"]:
            issues.append(issue(
                "missing_company_relationship_evidence",
                "high",
                row.get("source_company", ""),
                relation_label,
                "企业关系引用了不存在的证据 ID。",
                f"{RELATIONSHIPS.name}:{idx}",
                evidence_ids,
                "修复证据 ID 或补录证据。",
                {"evidence_profile": profile},
            ))
        if profile["weak"] and row.get("confidence") == "high":
            issues.append(issue(
                "high_confidence_weak_company_relationship_evidence",
                "high",
                row.get("source_company", ""),
                relation_label,
                "企业关系为 high，但证据来源强度不足。",
                f"{RELATIONSHIPS.name}:{idx}",
                evidence_ids,
                "补双方官网、公告、合同/诉讼/监管文件或权威媒体直接证据。",
                {"evidence_profile": profile},
            ))
    return issues


def audit_digital_china_relations(
    rows: list[dict[str, str]],
    evidence_by_id: dict[str, dict[str, Any]],
    known_companies: set[str],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    issues.extend(audit_abstract_entities(rows, known_companies, evidence_by_id))
    for idx, row in enumerate(rows, start=2):
        company = row.get("company_name", "").strip()
        evidence_ids = split_ids(row.get("evidence_ids"))
        profile = evidence_profile(evidence_ids, evidence_by_id)
        status = row.get("relationship_status", "")
        text = f"{row.get('relationship_type', '')} {row.get('relationship_basis', '')}"
        if status == "confirmed_public_relationship" and any(term in text for term in CONFIRMED_RELATION_FORBIDDEN_TERMS):
            issues.append(issue(
                "confirmed_relation_contains_potential_language",
                "high",
                company,
                "神州数码关系状态",
                "confirmed_public_relationship 中仍包含潜在/待验证/不能证明等表述，事实关系与分析判断混用。",
                f"{DC_RELATIONS.name}:{idx}",
                evidence_ids,
                "降级为 needs_internal_validation 或改写为明确公开合作事实。",
            ))
        if status == "confirmed_public_relationship" and profile["weak"]:
            issues.append(issue(
                "confirmed_digital_china_relation_weak_evidence",
                "high",
                company,
                "Company -[合作]-> 神州数码",
                "神州数码确认关系证据偏弱，容易被误解为无证据事实边。",
                f"{DC_RELATIONS.name}:{idx}",
                evidence_ids,
                "补神州数码官网、上市公司公告、互动易原文、合作伙伴页面或中标公告。",
                {"evidence_profile": profile},
            ))
        if status != "confirmed_public_relationship" and row.get("asset_tier") in {"潜力客户", "生态伙伴", "存量客户"}:
            issues.append(issue(
                "potential_status_asset_tier_risk",
                "medium",
                company,
                "神州数码关系状态",
                "非确认关系被分到业务资产层级，后续展示时可能被误读为事实客户关系。",
                f"{DC_RELATIONS.name}:{idx}",
                evidence_ids,
                "当前主图只保留关系状态属性；战略分析阶段再结合内部数据确认资产层级。",
            ))
    return issues


def build_summary(issues: list[dict[str, Any]]) -> dict[str, Any]:
    by_type = Counter(issue["issue_type"] for issue in issues)
    by_severity = Counter(issue["severity"] for issue in issues)
    by_priority = Counter(issue["priority"] for issue in issues)
    return {
        "total_issues": len(issues),
        "by_priority": dict(sorted(by_priority.items())),
        "by_severity": dict(sorted(by_severity.items())),
        "by_type": dict(sorted(by_type.items())),
    }


def run_audit() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    leaders = read_csv(LEADERS)
    relationships = read_csv(RELATIONSHIPS)
    products = read_csv(PRODUCTS)
    company_product = read_csv(COMPANY_PRODUCT)
    dc_relations = read_csv(DC_RELATIONS)
    leader_evidence = evidence_index(read_jsonl(LEADER_EVIDENCE))
    relationship_evidence = evidence_index(read_jsonl(RELATIONSHIP_EVIDENCE))
    dc_evidence = evidence_index(read_jsonl(DC_EVIDENCE))
    company_product_evidence = {**leader_evidence, **dc_evidence}

    known_companies = {row.get("company_name", "").strip() for row in leaders if row.get("company_name")}
    product_names = {row.get("product_service_name", "").strip() for row in products if row.get("product_service_name")}

    issues: list[dict[str, Any]] = []
    issues.extend(audit_leader_evidence(leaders, leader_evidence))
    issues.extend(audit_company_product_relations(company_product, company_product_evidence, product_names))
    issues.extend(audit_company_relationships(relationships, relationship_evidence))
    issues.extend(audit_digital_china_relations(dc_relations, dc_evidence, known_companies))
    return issues, build_summary(issues)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit semiconductor KG entity/relation/evidence quality.")
    parser.add_argument("--write", action="store_true", help=f"Write JSONL report to {OUTPUT_PATH}.")
    parser.add_argument("--limit", type=int, default=20, help="Number of sample issues to print.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    issues, summary = run_audit()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    for item in issues[: args.limit]:
        print(json.dumps(item, ensure_ascii=False))
    if args.write:
        write_jsonl(OUTPUT_PATH, issues)
        print(f"Wrote audit report: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
