from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "data" / "evidence" / "evidence_stage_3.jsonl"
LEADERS_PATH = ROOT / "data" / "company_pool" / "company_leaders_stage_3.csv"
STAGE6_PATH = ROOT / "data" / "business_graph" / "stage6_company_product_relations.csv"

NOW = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


EVIDENCE_ROWS = [
    {
        "evidence_id": "E3-848",
        "company": "兆易创新",
        "subsegment": "存储控制/模组/NOR",
        "title": "兆易创新 2024 年年度报告",
        "url": "data/reports/cninfo/603986_兆易创新_兆易创新2024年年度报告.pdf",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "年报披露公司现有产品主要分为存储器、微控制器和传感器产品；存储器产品包括闪存芯片（NOR Flash、NAND Flash）和动态随机存取存储器（DRAM），NOR Flash 广泛应用于工业、汽车、消费电子、PC及周边、网络通信、物联网及移动设备等领域。",
        "claim": "兆易创新覆盖 NOR Flash、NAND Flash、DRAM 和 MCU，可支撑其在存储控制/模组/NOR环节的业务归属。",
    },
    {
        "evidence_id": "E3-849",
        "company": "北京君正",
        "subsegment": "存储控制/模组/NOR",
        "title": "北京君正 2024 年年度报告",
        "url": "data/reports/cninfo/300223_北京君正_2024年年度报告.pdf",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "年报释义列示 SRAM、DRAM、Flash、NOR Flash、NAND Flash、Connectivity、LIN、CAN、MCU 等芯片类别。",
        "claim": "北京君正覆盖 DRAM/SRAM/Flash/NOR Flash 和车规互联/控制相关芯片，可支撑其在存储控制/模组/NOR环节的业务归属。",
    },
]

APPEND_MAP = {
    ("兆易创新", "存储控制/模组/NOR"): ["E3-848"],
    ("北京君正", "存储控制/模组/NOR"): ["E3-849"],
}

STAGE6_MAP = {
    ("兆易创新", "NOR Flash"): ["E3-848"],
    ("兆易创新", "存储主控芯片"): ["E3-848"],
    ("北京君正", "NOR Flash"): ["E3-849"],
}


def as_evidence_record(row: dict[str, str]) -> dict[str, object]:
    return {
        "evidence_id": row["evidence_id"],
        "task_id": "S3-authoritative-evidence-enrichment-6",
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
        "search_tool": "cninfo",
        "query": f"{row['company']} {row['subsegment']} official disclosure evidence",
    }


def add_ids(existing: str, ids: list[str]) -> str:
    parts = [item.strip() for item in (existing or "").split(";") if item.strip()]
    for evidence_id in ids:
        if evidence_id not in parts:
            parts.append(evidence_id)
    return ";".join(parts)


def append_or_replace_evidence() -> tuple[int, int]:
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


def update_csv(path: Path, key_fields: tuple[str, str], append_map: dict[tuple[str, str], list[str]]) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    url_by_id = {row["evidence_id"]: row["url"] for row in EVIDENCE_ROWS}
    updates = 0
    for row in rows:
        key = (row.get(key_fields[0], "").strip(), row.get(key_fields[1], "").strip())
        ids = append_map.get(key)
        if not ids:
            continue
        before = row.get("evidence_ids", "")
        row["evidence_ids"] = add_ids(before, ids)
        if "evidence_count" in row:
            row["evidence_count"] = str(len([item for item in row["evidence_ids"].split(";") if item.strip()]))
        if "source_urls" in row:
            urls = [item.strip() for item in (row.get("source_urls") or "").split("|") if item.strip()]
            for evidence_id in ids:
                url = url_by_id.get(evidence_id, "")
                if url and url not in urls:
                    urls.append(url)
            row["source_urls"] = " | ".join(urls)
        if row["evidence_ids"] != before:
            updates += 1

    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return updates


def main() -> None:
    replaced, appended = append_or_replace_evidence()
    leader_updates = update_csv(LEADERS_PATH, ("company_name", "subsegment_name"), APPEND_MAP)
    stage6_updates = update_csv(STAGE6_PATH, ("company_name", "product_service_name"), STAGE6_MAP)
    print(json.dumps(
        {
            "evidence_replaced": replaced,
            "evidence_appended": appended,
            "leader_updates": leader_updates,
            "stage6_updates": stage6_updates,
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
