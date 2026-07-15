from __future__ import annotations

import csv
import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

DATE_SNAPSHOT = "2026-07-08"

TEMPORAL_FIELDS = [
    "record_id",
    "data_as_of",
    "first_seen_at",
    "last_verified_at",
    "event_date",
    "event_start_at",
    "event_end_at",
    "time_precision",
    "temporal_basis",
    "source_publish_dates",
    "source_retrieved_dates",
    "current_validity",
    "claim_nature",
    "primary_evidence_id",
    "evidence_grade_summary",
    "verification_method",
    "needs_refresh_after",
    "risk_note",
]


def split_ids(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.replace(",", ";").split(";") if part.strip()]


def normalize_date(raw: str | None) -> str:
    if not raw:
        return ""
    value = raw.strip()
    if len(value) >= 10 and value[4] == "-" and value[7] == "-":
        return value[:10]
    return value


def load_evidence_index(paths: list[Path]) -> dict[str, dict[str, Any]]:
    evidence: dict[str, dict[str, Any]] = {}
    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                evidence_id = str(item.get("evidence_id", "")).strip()
                if evidence_id:
                    evidence[evidence_id] = item
    return evidence


def aggregate_evidence_dates(
    evidence_ids: list[str],
    evidence: dict[str, dict[str, Any]],
) -> dict[str, str]:
    publish_dates: list[str] = []
    retrieved_dates: list[str] = []
    grades: Counter[str] = Counter()
    primary = ""
    for evidence_id in evidence_ids:
        item = evidence.get(evidence_id, {})
        if not item:
            continue
        if not primary:
            primary = evidence_id
        publish_date = normalize_date(str(item.get("publish_date", "")))
        retrieved_date = normalize_date(str(item.get("retrieved_at", "")))
        if publish_date:
            publish_dates.append(publish_date)
        if retrieved_date:
            retrieved_dates.append(retrieved_date)
        grade = str(item.get("source_grade", "")).strip()
        if grade:
            grades[grade] += 1

    grade_order = ["A", "A-", "B", "B-", "unknown"]
    grade_summary = ";".join(
        f"{grade}:{grades[grade]}" for grade in grade_order if grades.get(grade, 0) > 0
    )
    other_grades = sorted(g for g in grades if g not in grade_order)
    if other_grades:
        suffix = ";".join(f"{grade}:{grades[grade]}" for grade in other_grades)
        grade_summary = f"{grade_summary};{suffix}" if grade_summary else suffix

    return {
        "source_publish_dates": ";".join(sorted(set(publish_dates))),
        "source_retrieved_dates": ";".join(sorted(set(retrieved_dates))),
        "primary_evidence_id": primary,
        "evidence_grade_summary": grade_summary,
    }


def infer_last_verified_at(source_retrieved_dates: str) -> str:
    dates = [part for part in source_retrieved_dates.split(";") if part]
    return max(dates) if dates else DATE_SNAPSHOT


def prefer_explicit_temporal_value(existing: str, candidate: str, generic_values: set[str]) -> str:
    if candidate and existing in generic_values:
        return candidate
    return existing or candidate


def add_temporal_fields(
    row: dict[str, str],
    evidence: dict[str, dict[str, Any]],
    *,
    claim_nature: str,
    record_id: str = "",
    current_validity: str = "当前支持",
    event_date: str = "",
    event_start_at: str = "",
    event_end_at: str = "",
    time_precision: str = "unknown",
    temporal_basis: str = "检索快照",
    verification_method: str = "公开资料检索",
    needs_refresh_after: str = "2026-10-08",
    risk_note: str = "",
) -> dict[str, str]:
    evidence_ids = split_ids(row.get("evidence_ids"))
    aggregate = aggregate_evidence_dates(evidence_ids, evidence)
    enriched = dict(row)
    enriched.update(
        {
            "record_id": record_id or row.get("record_id", ""),
            "data_as_of": row.get("data_as_of") or DATE_SNAPSHOT,
            "first_seen_at": row.get("first_seen_at") or DATE_SNAPSHOT,
            "last_verified_at": row.get("last_verified_at")
            or infer_last_verified_at(aggregate["source_retrieved_dates"]),
            "event_date": row.get("event_date") or event_date,
            "event_start_at": row.get("event_start_at") or event_start_at,
            "event_end_at": row.get("event_end_at") or event_end_at,
            "time_precision": prefer_explicit_temporal_value(
                row.get("time_precision", ""),
                time_precision,
                {"", "unknown", "未明确"},
            ),
            "temporal_basis": prefer_explicit_temporal_value(
                row.get("temporal_basis", ""),
                temporal_basis,
                {"", "检索快照", "未明确"},
            ),
            "source_publish_dates": aggregate["source_publish_dates"]
            or row.get("source_publish_dates", ""),
            "source_retrieved_dates": aggregate["source_retrieved_dates"]
            or row.get("source_retrieved_dates", ""),
            "current_validity": row.get("current_validity") or current_validity,
            "claim_nature": row.get("claim_nature") or claim_nature,
            "primary_evidence_id": row.get("primary_evidence_id")
            or aggregate["primary_evidence_id"],
            "evidence_grade_summary": row.get("evidence_grade_summary")
            or aggregate["evidence_grade_summary"],
            "verification_method": row.get("verification_method") or verification_method,
            "needs_refresh_after": row.get("needs_refresh_after") or needs_refresh_after,
            "risk_note": row.get("risk_note") or risk_note,
        }
    )
    return enriched


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

EVIDENCE_PATHS = [
    DATA / "evidence" / "evidence_stage_1.jsonl",
    DATA / "evidence" / "evidence_stage_2.jsonl",
    DATA / "evidence" / "evidence_stage_3.jsonl",
    DATA / "evidence" / "evidence_stage_4_relationships.jsonl",
    DATA / "evidence" / "evidence_stage_7_digital_china.jsonl",
]

TABLES = {
    "stage3": DATA / "company_pool" / "company_leaders_stage_3.csv",
    "stage4": DATA / "company_pool" / "company_relationships_stage_4.csv",
    "stage6": DATA / "business_graph" / "stage6_company_product_relations.csv",
    "stage6_competition": DATA / "business_graph" / "stage6_company_competition.csv",
    "stage7": DATA / "business_graph" / "stage7_digital_china_relations.csv",
    "stage8": DATA / "business_graph" / "stage8_business_opportunities.csv",
}


def build_record_id(stage: str, row: dict[str, str], index: int) -> str:
    if stage == "stage3":
        return f"stage3::{row.get('company_name', '')}::{row.get('subsegment_name', '')}"
    if stage == "stage4":
        relationship_id = row.get("relationship_id") or f"row-{index:04d}"
        return f"stage4::{relationship_id}"
    if stage == "stage6":
        return (
            f"stage6::{row.get('company_name', '')}::"
            f"{row.get('relation_type', '')}::{row.get('product_service_name', '')}"
        )
    if stage == "stage6_competition":
        return (
            f"stage6_competition::{row.get('source_company', '')}::"
            f"{row.get('target_company', '')}::{row.get('relationship_type', '')}"
        )
    if stage == "stage7":
        return f"stage7::{row.get('company_name', '')}::{row.get('relationship_status', '')}"
    if stage == "stage8":
        opportunity_id = row.get("opportunity_id") or f"row-{index:04d}"
        return f"stage8::{opportunity_id}"
    return f"{stage}::row-{index:04d}"


def claim_nature_for_stage(stage: str, row: dict[str, str]) -> str:
    if stage in {"stage3", "stage4"}:
        return "事实判断"
    if stage == "stage6":
        if row.get("requires_internal_validation") == "true":
            return "推断关系"
        return "事实判断"
    if stage == "stage6_competition":
        return "推断关系"
    if stage == "stage7":
        status = row.get("relationship_status", "")
        if status == "confirmed_public_relationship":
            return "事实关系"
        return "候选分析"
    if stage == "stage8":
        return "候选分析"
    return "事实判断"


def validity_for_stage(stage: str, row: dict[str, str]) -> str:
    if row.get("requires_internal_validation") == "true":
        return "需要内部验证"
    if stage == "stage8":
        return "候选分析"
    if stage == "stage7" and row.get("relationship_status") != "confirmed_public_relationship":
        return "需要内部验证"
    return "当前支持"


def risk_note_for_stage(stage: str, row: dict[str, str]) -> str:
    if row.get("requires_internal_validation") == "true":
        return "公开资料不足以证明内部客户或当前交易关系，需要内部销售/客户数据确认。"
    if stage == "stage8":
        return "商机、解决方案和战役计划为候选分析，不代表已发生订单或客户事实。"
    return ""


EXPLICIT_EVENT_DATES = {
    "R4-030": ("2026-06-07", "2026-06-07", "", "day", "官方公告日期"),
    "R4-031": ("2024-02-26", "2024-02-26", "", "day", "官方公告日期"),
    "R4-M001": ("2016-04-29", "2016-04-29", "", "day", "官方公告日期"),
    "R4-M002": ("2014-02-20", "2014-02-20", "", "day", "公开新闻稿日期"),
    "R4-M003": ("2015-06-23", "2015-06-23", "", "day", "官方公告日期"),
    "R4-M004": ("2015-06-23", "2015-06-23", "", "day", "公开新闻稿日期"),
    "R4-M005": ("2021-06-28", "2021-06-28", "", "day", "官方公告日期"),
    "R4-M006": ("2021-06-28", "2021-06-28", "", "day", "官方公告日期"),
    "R4-M007": ("2021-06-28", "2021-06-28", "", "day", "官方公告日期"),
    "R4-MANUAL-001": ("2016-04-29", "2016-04-29", "", "day", "公告日期"),
    "R4-MANUAL-002": ("2014-02-20", "2014-02-20", "", "day", "公告日期"),
    "R4-MANUAL-003": ("2015-06-23", "2015-06-23", "", "day", "公告日期"),
    "R4-MANUAL-004": ("2015-06-23", "2015-06-23", "", "day", "公告日期"),
    "R4-MANUAL-005": ("2020-06-22", "2020-06-22", "", "day", "公告日期"),
    "R4-MANUAL-006": ("2020-06-22", "2020-06-22", "", "day", "公告日期"),
    "R4-MANUAL-007": ("2020-06-22", "2020-06-22", "", "day", "公告日期"),
}


def event_time_for_row(stage: str, row: dict[str, str]) -> dict[str, str]:
    if stage != "stage4":
        return {
            "event_date": "",
            "event_start_at": "",
            "event_end_at": "",
            "time_precision": "unknown",
            "temporal_basis": "检索快照",
        }
    relationship_id = row.get("relationship_id", "")
    if relationship_id in EXPLICIT_EVENT_DATES:
        event_date, event_start_at, event_end_at, time_precision, temporal_basis = (
            EXPLICIT_EVENT_DATES[relationship_id]
        )
        return {
            "event_date": event_date,
            "event_start_at": event_start_at,
            "event_end_at": event_end_at,
            "time_precision": time_precision,
            "temporal_basis": temporal_basis,
        }
    return {
        "event_date": "",
        "event_start_at": "",
        "event_end_at": "",
        "time_precision": "unknown",
        "temporal_basis": "检索快照",
    }


def enrich_table(stage: str, evidence: dict[str, dict[str, Any]]) -> int:
    path = TABLES[stage]
    rows = read_csv_rows(path)
    enriched_rows: list[dict[str, str]] = []
    for index, row in enumerate(rows, start=1):
        event_time = event_time_for_row(stage, row)
        enriched_rows.append(
            add_temporal_fields(
                row,
                evidence,
                claim_nature=claim_nature_for_stage(stage, row),
                record_id=build_record_id(stage, row, index),
                current_validity=validity_for_stage(stage, row),
                event_date=event_time["event_date"],
                event_start_at=event_time["event_start_at"],
                event_end_at=event_time["event_end_at"],
                time_precision=event_time["time_precision"],
                temporal_basis=event_time["temporal_basis"],
                risk_note=risk_note_for_stage(stage, row),
            )
        )
    write_csv_rows(path, enriched_rows)
    return len(enriched_rows)


def enrich_all_tables(stages: list[str] | None = None) -> dict[str, int]:
    evidence = load_evidence_index(EVIDENCE_PATHS)
    selected_stages = stages or list(TABLES)
    unknown = [stage for stage in selected_stages if stage not in TABLES]
    if unknown:
        raise ValueError(f"unknown stages: {', '.join(unknown)}")
    return {stage: enrich_table(stage, evidence) for stage in selected_stages}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stages",
        nargs="+",
        choices=sorted(TABLES),
        help="Only enrich selected stages. Defaults to all known tables.",
    )
    args = parser.parse_args()

    summary = enrich_all_tables(args.stages)
    for stage, count in summary.items():
        print(f"{stage}: enriched {count} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
