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
        "evidence_id": "E3-906",
        "company": "芯源微",
        "subsegment": "光刻设备",
        "title": "芯源微 2024 年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/2025-04-26/1223330378.PDF",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "芯源微年报披露，公司主要产品包括涂胶显影设备、单片式湿法设备等半导体专用设备。",
        "claim": "芯源微覆盖涂胶显影设备，可支撑其在光刻配套设备环节的业务归属。",
    },
    {
        "evidence_id": "E3-907",
        "company": "鼎龙股份",
        "subsegment": "CMP材料",
        "title": "鼎龙股份 2024 年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/2025-04-29/1223367500.PDF",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "鼎龙股份年报披露，公司重点布局半导体 CMP 抛光垫、CMP 抛光液、清洗液等半导体材料产品。",
        "claim": "鼎龙股份覆盖 CMP 抛光垫等 CMP 材料，可支撑其在 CMP材料环节的业务归属。",
    },
    {
        "evidence_id": "E3-908",
        "company": "生益科技",
        "subsegment": "封装材料/IC载板",
        "title": "生益科技 2024 年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/2025-04-26/1223317223.PDF",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "生益科技年报披露，公司产品包括覆铜板、粘结片、印制电路板、IC封装基板及电子用树脂等电子材料。",
        "claim": "生益科技覆盖 IC 封装基板，可支撑其在封装材料/IC载板环节的业务归属。",
    },
    {
        "evidence_id": "E3-909",
        "company": "甬矽电子",
        "subsegment": "2.5D/3D/Chiplet先进封装",
        "title": "甬矽电子 2024 年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/2025-04-23/1223218861.PDF",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "甬矽电子年报披露，公司主要从事集成电路封装测试业务，并持续推进高密度细间距凸点倒装、SiP、Fan-out 等先进封装技术。",
        "claim": "甬矽电子覆盖先进封装相关技术和封装测试服务，可支撑其在 2.5D/3D/Chiplet先进封装环节的业务归属。",
    },
    {
        "evidence_id": "E3-910",
        "company": "通富微电",
        "subsegment": "2.5D/3D/Chiplet先进封装",
        "title": "通富微电 2024 年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/2025-04-12/1223070267.PDF",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "通富微电年报披露，公司从事集成电路封装测试，具备倒装、Bumping、WLCSP、Fan-out、SiP 等先进封装技术能力。",
        "claim": "通富微电覆盖先进封装和封装测试服务，可支撑其在 2.5D/3D/Chiplet先进封装环节的业务归属。",
    },
    {
        "evidence_id": "E3-911",
        "company": "新洁能",
        "subsegment": "功率器件/模块",
        "title": "新洁能 2024 年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/2025-04-25/1223286536.PDF",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "新洁能年报披露，公司主要从事 MOSFET、IGBT 等半导体芯片和功率器件的研发设计及销售。",
        "claim": "新洁能覆盖 MOSFET 等功率器件，可支撑其在功率器件/模块环节的业务归属。",
    },
    {
        "evidence_id": "E3-912",
        "company": "天岳先进",
        "subsegment": "SiC衬底/外延",
        "title": "天岳先进 2024 年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/2025-03-28/1222928209.PDF",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "天岳先进年报披露，公司主要从事碳化硅衬底材料的研发、生产和销售，产品覆盖半绝缘型和导电型碳化硅衬底。",
        "claim": "天岳先进覆盖 SiC 衬底材料，可支撑其在 SiC衬底/外延环节的业务归属。",
    },
    {
        "evidence_id": "E3-913",
        "company": "天科合达",
        "subsegment": "SiC衬底/外延",
        "title": "天科合达官网：产品中心",
        "url": "https://www.tankeblue.com/product",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "天科合达官网产品中心展示导电型碳化硅衬底、半绝缘型碳化硅衬底等产品。",
        "claim": "天科合达覆盖 SiC 衬底产品，可支撑其在 SiC衬底/外延环节的业务归属。",
    },
    {
        "evidence_id": "E3-914",
        "company": "英诺赛科",
        "subsegment": "GaN功率/RF器件",
        "title": "英诺赛科官网：GaN 功率器件",
        "url": "https://www.innoscience.com/products",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "英诺赛科官网产品中心展示 InnoGaN 系列 GaN 功率器件产品。",
        "claim": "英诺赛科覆盖 GaN 功率器件，可支撑其在 GaN功率/RF器件环节的业务归属。",
    },
    {
        "evidence_id": "E3-915",
        "company": "EPC",
        "subsegment": "GaN功率/RF器件",
        "title": "EPC 官网：eGaN FETs and ICs",
        "url": "https://epc-co.com/epc/products/gan-fets-and-ics",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "EPC 官网产品页展示 eGaN FETs and ICs，面向高效电源转换等应用。",
        "claim": "EPC 覆盖 GaN FET/IC 功率器件，可支撑其在 GaN功率/RF器件环节的业务归属。",
    },
    {
        "evidence_id": "E3-916",
        "company": "SK hynix",
        "subsegment": "2.5D/3D/Chiplet先进封装",
        "title": "SK hynix HBM3E",
        "url": "https://news.skhynix.com/sk-hynix-begins-mass-production-of-hbm3e/",
        "source_type": "company_or_wire_release",
        "grade": "A-",
        "excerpt": "SK hynix 官方新闻披露 HBM3E 量产，并说明 HBM 通过 TSV 技术垂直连接 DRAM 芯片。",
        "claim": "SK hynix 的 HBM 产品依赖 TSV/堆叠等先进封装相关能力，可作为其先进封装能力的公开证据。",
    },
    {
        "evidence_id": "E3-917",
        "company": "Nan Ya PCB",
        "subsegment": "封装材料/IC载板",
        "title": "Nan Ya PCB 官方网站：IC Substrates",
        "url": "https://www.nanyapcb.com.tw/nypcb/english/index",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Nan Ya PCB 英文官网在 Products Applications 中列示 IC Substrate、Flip Chip Substrate、Wire Bond Substrate 等产品方向。",
        "claim": "Nan Ya PCB 覆盖 IC 载板/封装基板产品，可支撑其在封装材料/IC载板环节的业务归属。",
    },
    {
        "evidence_id": "E3-918",
        "company": "Unimicron",
        "subsegment": "封装材料/IC载板",
        "title": "Unimicron 官方网站：IC Substrate",
        "url": "https://www.unimicron.com/en/product/technology.aspx?kind=1",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Unimicron 官网产品技术页面展示 IC Substrate 产品和技术。",
        "claim": "Unimicron 覆盖 IC Substrate/载板产品，可支撑其在封装材料/IC载板环节的业务归属。",
    },
]

APPEND_MAP = {
    ("芯源微", "光刻设备"): ["E3-906"],
    ("鼎龙股份", "CMP材料"): ["E3-907"],
    ("生益科技", "封装材料/IC载板"): ["E3-908"],
    ("甬矽电子", "2.5D/3D/Chiplet先进封装"): ["E3-909"],
    ("通富微电", "2.5D/3D/Chiplet先进封装"): ["E3-910"],
    ("新洁能", "功率器件/模块"): ["E3-911"],
    ("天岳先进", "SiC衬底/外延"): ["E3-912"],
    ("天科合达", "SiC衬底/外延"): ["E3-913"],
    ("英诺赛科", "GaN功率/RF器件"): ["E3-914"],
    ("EPC", "GaN功率/RF器件"): ["E3-915"],
    ("SK hynix", "2.5D/3D/Chiplet先进封装"): ["E3-916"],
    ("Nan Ya PCB", "封装材料/IC载板"): ["E3-917"],
    ("Unimicron", "封装材料/IC载板"): ["E3-918"],
}


def as_evidence_record(row: dict[str, str]) -> dict[str, object]:
    return {
        "evidence_id": row["evidence_id"],
        "task_id": "S3-authoritative-evidence-enrichment-9",
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
