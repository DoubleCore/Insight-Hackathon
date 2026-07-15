from __future__ import annotations

import csv
import json
from collections import OrderedDict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

STAGE6_CSV = DATA / "business_graph" / "stage6_company_product_relations.csv"
STAGE7_CSV = DATA / "business_graph" / "stage7_digital_china_relations.csv"
STAGE7_EVIDENCE = DATA / "evidence" / "evidence_stage_7_digital_china.jsonl"
SUMMARY = DATA / "business_graph" / "stage7_2025_brand_enrichment_summary.md"

DATA_AS_OF = "2026-07-12"
SOURCE_PUBLISH_DATE = "2026-03-31"
RETRIEVED_AT = "2026-07-12T00:00:00+08:00"
NEEDS_REFRESH_AFTER = "2026-10-12"

ANNUAL_REPORT_SUMMARY_URL = "https://static.cninfo.com.cn/finalpage/2026-03-31/1225058635.PDF"
DIGITAL_CHINA_INSPUR_AI_URL = "https://www.digitalchina.com/aboutus/news/details711.html"

ANNUAL_REPORT_EXCERPT = (
    "神州数码2025年年度报告摘要披露：2025年公司电子元器件业务收入282.4亿元，同比增长39.6%；"
    "在国产芯片领域相继引入沐曦、摩尔、壁仞、海思等TOP品牌；在主控领域英特尔、AMD、"
    "飞腾、龙芯、海思、展锐、瑞芯微等业务继续稳健增长；在存储领域长鑫、佰维、大普微、"
    "海康、紫光国芯等品牌业务规模保持高速成长。"
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def upsert(rows: list[dict[str, Any]], new_rows: list[dict[str, Any]], key: str) -> tuple[list[dict[str, Any]], int, int]:
    by_key: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for row in rows:
        value = str(row.get(key, "")).strip()
        if value:
            by_key[value] = row

    added = 0
    updated = 0
    for row in new_rows:
        value = str(row.get(key, "")).strip()
        if not value:
            continue
        if value in by_key:
            by_key[value].update(row)
            updated += 1
        else:
            by_key[value] = row
            added += 1
    return list(by_key.values()), added, updated


def upsert_evidence(rows: list[dict[str, Any]], new_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int, int]:
    return upsert(rows, new_rows, "evidence_id")


def stage7_row(company: str, category: str, source_name: str | None = None) -> dict[str, str]:
    display = source_name or company
    relation_type = f"{category}品牌引入/电子元器件业务关系"
    return {
        "company_name": company,
        "relationship_status": "confirmed_public_relationship",
        "relationship_type": relation_type,
        "relationship_basis": (
            f"神州数码2025年年度报告摘要披露，公司在{category}领域引入或经营{display}等品牌/业务，"
            "可作为公开年报层面的品牌业务关系入图；该关系不等同于内部客户关系、具体订单或当前交易金额。"
        ),
        "evidence_ids": "DC-006",
        "confidence": "high",
        "requires_internal_validation": "true",
        "limitations": "年报摘要可证明公开披露的品牌/业务线索，但不能证明内部CRM客户、具体项目金额、排他代理或当前订单状态。",
        "asset_tier": "生态伙伴",
        "record_id": f"stage7::{company}::confirmed_public_relationship",
        "data_as_of": DATA_AS_OF,
        "first_seen_at": DATA_AS_OF,
        "last_verified_at": DATA_AS_OF,
        "event_date": "2025",
        "event_start_at": "",
        "event_end_at": "",
        "time_precision": "year",
        "temporal_basis": "神州数码2025年年度报告摘要披露的报告期业务信息",
        "source_publish_dates": SOURCE_PUBLISH_DATE,
        "source_retrieved_dates": DATA_AS_OF,
        "current_validity": "公开年报支持；内部客户/交易关系需验证",
        "claim_nature": "事实关系",
        "primary_evidence_id": "DC-006",
        "evidence_grade_summary": "A:1",
        "verification_method": "公开公告/年报摘要核验",
        "needs_refresh_after": NEEDS_REFRESH_AFTER,
        "risk_note": "不能把品牌引入或业务增长直接解读为客户资产、订单金额、独家代理或持续交易，需要内部数据确认。",
    }


def stage6_product_row(
    product: str,
    relation_type: str,
    basis: str,
    evidence_ids: str,
    confidence: str,
    event_date: str,
    event_start_at: str,
    source_publish_dates: str,
) -> dict[str, str]:
    return {
        "company_name": "神州数码",
        "product_service_name": product,
        "relation_type": relation_type,
        "l4_code": "L4-DOWNSTREAM-AI-INFRA",
        "l4_name": "AI服务器/云基础设施",
        "basis": basis,
        "evidence_ids": evidence_ids,
        "confidence": confidence,
        "requires_internal_validation": "true",
        "derivation": "manual_official_evidence",
        "record_id": f"stage6::神州数码::{relation_type}::{product}",
        "data_as_of": DATA_AS_OF,
        "first_seen_at": DATA_AS_OF,
        "last_verified_at": DATA_AS_OF,
        "event_date": event_date,
        "event_start_at": event_start_at,
        "event_end_at": "",
        "time_precision": "day" if event_start_at else "year",
        "temporal_basis": "公开官网新闻/年报摘要披露",
        "source_publish_dates": source_publish_dates,
        "source_retrieved_dates": DATA_AS_OF,
        "current_validity": "公开资料支持；内部项目/客户关系需验证",
        "claim_nature": "事实关系",
        "primary_evidence_id": evidence_ids.split(";")[0],
        "evidence_grade_summary": "A:1",
        "verification_method": "公开官网/公告核验",
        "needs_refresh_after": NEEDS_REFRESH_AFTER,
        "risk_note": "只表示公开资料支持神州数码具备相关方案集成或业务布局，不外推为具体客户订单。",
    }


def build_stage7_rows() -> list[dict[str, str]]:
    specs = [
        ("沐曦", "国产芯片", None),
        ("摩尔线程", "国产芯片", "摩尔"),
        ("壁仞科技", "国产芯片", "壁仞"),
        ("海思", "国产芯片/主控", None),
        ("Intel", "主控", "英特尔"),
        ("AMD", "主控", None),
        ("飞腾", "主控", None),
        ("龙芯中科", "主控", "龙芯"),
        ("紫光展锐", "主控", "展锐"),
        ("瑞芯微", "主控", None),
        ("长鑫存储", "存储", "长鑫"),
        ("佰维存储", "存储", "佰维"),
        ("大普微", "存储", None),
        ("紫光国芯", "存储", None),
    ]
    return [stage7_row(company, category, source_name) for company, category, source_name in specs]


def build_stage6_rows() -> list[dict[str, str]]:
    return [
        stage6_product_row(
            "AI服务器",
            "INTEGRATES",
            "神州数码官网新闻披露其与浪潮信息联合发布AI一体机解决方案，支持其在AI服务器/一体机方案集成侧入图。",
            "DC-007",
            "high",
            "2024-12-18",
            "2024-12-18",
            "2024-12-18",
        ),
        stage6_product_row(
            "数据中心基础设施服务",
            "INTEGRATES",
            "神州数码2025年报摘要披露其围绕芯片、主控、存储、模组等品类完善电子元器件业务布局，并为客户提供Design House等增值服务；结合AI一体机公开方案，可支撑其数据中心/AI基础设施方案集成能力入图。",
            "DC-006;DC-007",
            "medium",
            "2025",
            "",
            "2026-03-31;2024-12-18",
        ),
    ]


def build_evidence_rows() -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": "DC-006",
            "task_id": "S7-2025-annual-report-semiconductor-brands",
            "company_name": "神州数码电子元器件品牌组合",
            "relationship_status": "confirmed_public_relationship",
            "source_title": "神州数码2025年年度报告摘要",
            "source_url_or_file": ANNUAL_REPORT_SUMMARY_URL,
            "source_type": "official_annual_report_summary",
            "publish_date": SOURCE_PUBLISH_DATE,
            "evidence_excerpt": ANNUAL_REPORT_EXCERPT,
            "possible_claim": "神州数码2025年报摘要公开披露其在国产芯片、主控、存储领域引入或经营多个半导体品牌。",
            "confidence": "high",
            "limitations": "该证据证明公开披露的品牌/业务线索，不证明内部客户关系、订单金额、排他代理或持续交易状态。",
            "retrieved_at": RETRIEVED_AT,
            "source_grade": "A",
            "search_tool": "public_report_pdf_review",
            "query": "神州数码 2025 年年度报告摘要 沐曦 摩尔 壁仞 海思 Intel AMD 长鑫 佰维",
        },
        {
            "evidence_id": "DC-007",
            "task_id": "S7-digital-china-inspur-ai-appliance",
            "company_name": "浪潮信息",
            "relationship_status": "confirmed_public_relationship",
            "source_title": "神州数码官网：与浪潮信息联合发布AI一体机解决方案",
            "source_url_or_file": DIGITAL_CHINA_INSPUR_AI_URL,
            "source_type": "official_company_news",
            "publish_date": "2024-12-18",
            "evidence_excerpt": "神州数码官网新闻显示，神州数码与浪潮信息联合发布AI一体机解决方案。",
            "possible_claim": "神州数码与浪潮信息存在公开可验证的AI一体机/解决方案协同关系。",
            "confidence": "high",
            "limitations": "该证据证明公开联合发布/方案协同，不证明内部客户资产或具体订单金额。",
            "retrieved_at": RETRIEVED_AT,
            "source_grade": "A",
            "search_tool": "official_site_review",
            "query": "site:digitalchina.com 神州数码 浪潮信息 AI一体机 解决方案",
        },
    ]


def run() -> dict[str, int]:
    stage7_rows = read_csv(STAGE7_CSV)
    stage7_fieldnames = list(stage7_rows[0].keys())
    stage7_rows, stage7_added, stage7_updated = upsert(stage7_rows, build_stage7_rows(), "record_id")
    write_csv(STAGE7_CSV, stage7_rows, stage7_fieldnames)

    stage6_rows = read_csv(STAGE6_CSV)
    stage6_fieldnames = list(stage6_rows[0].keys())
    stage6_rows, stage6_added, stage6_updated = upsert(stage6_rows, build_stage6_rows(), "record_id")
    write_csv(STAGE6_CSV, stage6_rows, stage6_fieldnames)

    evidence_rows = read_jsonl(STAGE7_EVIDENCE)
    evidence_rows, evidence_added, evidence_updated = upsert_evidence(evidence_rows, build_evidence_rows())
    write_jsonl(STAGE7_EVIDENCE, evidence_rows)

    summary = {
        "stage7_rows_total": len(stage7_rows),
        "stage7_added": stage7_added,
        "stage7_updated": stage7_updated,
        "stage6_rows_total": len(stage6_rows),
        "stage6_added": stage6_added,
        "stage6_updated": stage6_updated,
        "stage7_evidence_total": len(evidence_rows),
        "stage7_evidence_added": evidence_added,
        "stage7_evidence_updated": evidence_updated,
    }
    SUMMARY.write_text(
        "\n".join(
            [
                "# 2025年报半导体品牌关系补充摘要",
                "",
                f"- 数据截至时间：{DATA_AS_OF}",
                f"- Stage7 神州数码关系总数：{summary['stage7_rows_total']}",
                f"- 本轮新增 Stage7 关系：{summary['stage7_added']}",
                f"- 本轮更新 Stage7 关系：{summary['stage7_updated']}",
                f"- Stage6 公司-产品关系总数：{summary['stage6_rows_total']}",
                f"- 本轮新增 Stage6 关系：{summary['stage6_added']}",
                f"- Stage7 证据总数：{summary['stage7_evidence_total']}",
                f"- 本轮新增证据：{summary['stage7_evidence_added']}",
                "",
                "## 口径",
                "",
                "- 新增关系来自神州数码2025年年度报告摘要和神州数码官网新闻。",
                "- 年报摘要证明品牌/业务线索，不证明内部客户、订单金额、排他代理或当前交易状态。",
                "- 新增记录均保留 `requires_internal_validation=true` 和刷新时间字段。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    print(json.dumps(run(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
