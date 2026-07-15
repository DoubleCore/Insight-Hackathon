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
        "evidence_id": "E3-826",
        "company": "卓胜微",
        "subsegment": "模拟/RF/MCU/传感器",
        "title": "江苏卓胜微电子股份有限公司官网",
        "url": "https://www.maxscend.com",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "卓胜微官网称公司专注于射频前端芯片领域，主要提供射频开关、射频低噪声放大器、射频滤波器等射频前端芯片。",
        "claim": "卓胜微覆盖射频前端芯片产品，可支撑其在模拟/RF/MCU/传感器环节的业务归属；手机SoC/通信基带行仅表示通信射频相关细分，不代表其生产手机SoC。",
    },
    {
        "evidence_id": "E3-827",
        "company": "Western Digital",
        "subsegment": "NAND Flash",
        "title": "Sandisk Product Portfolio",
        "url": "https://www.sandisk.com/product-portfolio",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Sandisk 官方产品组合页面覆盖 SSD、存储卡、U盘、嵌入式闪存等 Flash 存储产品。",
        "claim": "Western Digital/Sandisk 覆盖 Flash 存储产品，可支撑其在 NAND Flash 相关存储环节的业务归属。",
    },
    {
        "evidence_id": "E3-828",
        "company": "三安光电",
        "subsegment": "SiC功率器件/模块",
        "title": "Sanan Semiconductor SiC Diode Products",
        "url": "https://www.sanan-semiconductor.com/en/products",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "三安半导体官方产品页展示 SiC SBD 裸片、分立器件、模块等 SiC 二极管产品。",
        "claim": "三安光电/三安半导体覆盖 SiC 功率器件产品，可支撑其在 SiC功率器件/模块环节的业务归属。",
    },
    {
        "evidence_id": "E3-829",
        "company": "华为",
        "subsegment": "消费电子/通信设备",
        "title": "Huawei Carrier",
        "url": "https://carrier.huawei.com/en?ic_medium=hwdc&ic_source=cbg_header_car",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "华为运营商业务官网展示面向运营商的产品、解决方案和服务。",
        "claim": "华为覆盖通信设备、运营商网络产品和 ICT 解决方案，可支撑其在消费电子/通信设备环节的业务归属。",
    },
]

APPEND_MAP = {
    ("卓胜微", "手机SoC/通信基带"): ["E3-826"],
    ("卓胜微", "模拟/RF/MCU/传感器"): ["E3-826"],
    ("Western Digital", "NAND Flash"): ["E3-827"],
    ("三安光电", "SiC功率器件/模块"): ["E3-828"],
    ("华为", "消费电子/通信设备"): ["E3-829"],
}


def as_evidence_record(row: dict[str, str]) -> dict[str, object]:
    return {
        "evidence_id": row["evidence_id"],
        "task_id": "S3-authoritative-evidence-enrichment-4",
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
        "limitations": "官网/公告可证明业务覆盖或产品服务归属；龙头地位仍需结合市场份额、收入规模、客户和行业报告判断。",
        "retrieved_at": NOW,
        "source_grade": row["grade"],
        "search_tool": "official_site",
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
        row["evidence_count"] = str(len([item for item in row["evidence_ids"].split(";") if item.strip()]))
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
