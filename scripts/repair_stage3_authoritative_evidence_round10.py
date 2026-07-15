from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "data" / "evidence" / "evidence_stage_3.jsonl"
LEADERS_PATH = ROOT / "data" / "company_pool" / "company_leaders_stage_3.csv"

NOW = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


EVIDENCE_ROWS = [
    {
        "evidence_id": "E3-919",
        "company": "上海微电子",
        "subsegment": "光刻设备",
        "title": "上海微电子官网：SSX600系列步进扫描投影光刻机",
        "url": "https://www.smee.com.cn/eis.pub?service=homepageService&method=indexview&homepage=10&type_name=%E6%AD%A5%E8%BF%9B%E6%89%AB%E6%8F%8F%E6%8A%95%E5%BD%B1%E5%85%89%E5%88%BB%E6%9C%BA&contentid=95&ptype=%E9%9B%86%E6%88%90%E7%94%B5%E8%B7%AF%E8%A3%85%E5%A4%87",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "上海微电子官网展示 SSX600 系列步进扫描投影光刻机，属于集成电路装备产品。",
        "claim": "上海微电子覆盖集成电路光刻相关装备，可支撑其在光刻设备环节的业务归属。",
    },
]

APPEND_MAP = {
    ("上海微电子", "光刻设备"): ["E3-919"],
}


def as_evidence_record(row: dict[str, str]) -> dict[str, object]:
    return {
        "evidence_id": row["evidence_id"],
        "task_id": "S3-authoritative-evidence-enrichment-10",
        "question": f"{row['company']} 在 {row['subsegment']} 环节是否有官方产品/业务证据？",
        "value_chain_layer": "",
        "major_segment": "",
        "subsegment_name": row["subsegment"],
        "subsegment_role": "",
        "query_side": "官方资料",
        "source_title": row["title"],
        "source_url_or_file": row["url"],
        "source_type": row["source_type"],
        "publish_date": "",
        "entities": [row["company"]],
        "evidence_excerpt": row["excerpt"],
        "possible_claim": row["claim"],
        "claim_type_guess": "segment_business_presence",
        "confidence": "high",
        "limitations": "官网可证明业务覆盖或产品服务归属；龙头地位仍需结合市场份额、收入规模、客户和行业报告判断。",
        "retrieved_at": NOW,
        "source_grade": row["grade"],
        "search_tool": "web_search",
        "query": f"{row['company']} {row['subsegment']} official product evidence",
    }


def add_ids(existing: str, ids: list[str]) -> str:
    parts = [item.strip() for item in (existing or "").split(";") if item.strip()]
    for evidence_id in ids:
        if evidence_id not in parts:
            parts.append(evidence_id)
    return ";".join(parts)


def repair_evidence() -> tuple[int, int]:
    replacements = {row["evidence_id"]: as_evidence_record(row) for row in EVIDENCE_ROWS}
    output: list[dict[str, object]] = []
    seen: set[str] = set()
    replaced = 0

    with EVIDENCE_PATH.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            item = json.loads(line)
            evidence_id = item.get("evidence_id", "")
            if evidence_id in replacements:
                output.append(replacements[evidence_id])
                seen.add(evidence_id)
                replaced += 1
            else:
                output.append(item)

    appended = 0
    for evidence_id, item in replacements.items():
        if evidence_id not in seen:
            output.append(item)
            appended += 1

    with EVIDENCE_PATH.open("w", encoding="utf-8", newline="") as file:
        for item in output:
            file.write(json.dumps(item, ensure_ascii=False) + "\n")
    return replaced, appended


def update_leaders() -> int:
    with LEADERS_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    url_by_evidence = {row["evidence_id"]: row["url"] for row in EVIDENCE_ROWS}
    updates = 0
    for row in rows:
        key = (row.get("company_name", "").strip(), row.get("subsegment_name", "").strip())
        ids = APPEND_MAP.get(key)
        if not ids:
            continue
        before = row.get("evidence_ids", "")
        row["evidence_ids"] = add_ids(before, ids)
        if "evidence_count" in row:
            row["evidence_count"] = str(len([item for item in row["evidence_ids"].split(";") if item.strip()]))
        if "source_urls" in row:
            urls = [item.strip() for item in (row.get("source_urls") or "").split("|") if item.strip()]
            for evidence_id in ids:
                url = url_by_evidence.get(evidence_id, "")
                if url and url not in urls:
                    urls.append(url)
            row["source_urls"] = " | ".join(urls)
        if row["evidence_ids"] != before:
            updates += 1

    with LEADERS_PATH.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return updates


def main() -> None:
    replaced, appended = repair_evidence()
    updates = update_leaders()
    print(json.dumps({"evidence_replaced": replaced, "evidence_appended": appended, "leader_updates": updates}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
