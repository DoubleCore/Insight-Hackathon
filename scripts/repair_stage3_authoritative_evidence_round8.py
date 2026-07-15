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
        "evidence_id": "E3-880",
        "company": "芯原股份",
        "subsegment": "半导体IP/芯片定制",
        "title": "芯原股份 2024 年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/2025-04-26/1223311717.PDF",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "芯原股份官网披露，公司依托自主半导体IP为客户提供平台化、全方位、一站式芯片定制服务和半导体IP授权服务。",
        "claim": "芯原股份覆盖芯片定制服务和半导体IP授权服务，可支撑其在半导体IP/芯片定制环节的业务归属。",
    },
    {
        "evidence_id": "E3-881",
        "company": "MediaTek",
        "subsegment": "手机SoC/通信基带",
        "title": "MediaTek Dimensity",
        "url": "https://www.mediatek.com/products/smartphones",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "MediaTek 官方 Dimensity 页面披露，其 Dimensity 系列覆盖 5G 智能手机平台，并面向高性能和高能效移动体验。",
        "claim": "MediaTek 覆盖 Dimensity 手机 SoC/移动平台，可支撑其在手机SoC/通信基带环节的业务归属。",
    },
    {
        "evidence_id": "E3-882",
        "company": "兆易创新",
        "subsegment": "模拟/RF/MCU/传感器",
        "title": "兆易创新 2024 年年度报告：MCU",
        "url": "data/reports/cninfo/603986_兆易创新_兆易创新2024年年度报告.pdf",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "兆易创新年报披露，公司现有产品主要分为存储器、微控制器和传感器产品，微控制器产品包括 GD32 MCU 系列。",
        "claim": "兆易创新覆盖 MCU 微控制器产品，可支撑其在模拟/RF/MCU/传感器环节的业务归属。",
    },
    {
        "evidence_id": "E3-883",
        "company": "兆易创新",
        "subsegment": "DRAM/HBM",
        "title": "兆易创新 2024 年年度报告：DRAM",
        "url": "data/reports/cninfo/603986_兆易创新_兆易创新2024年年度报告.pdf",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "兆易创新年报披露，存储器产品包括 NOR Flash、NAND Flash 和 DRAM 等。",
        "claim": "兆易创新覆盖 DRAM 存储产品，可支撑其在 DRAM/HBM 环节中的 DRAM 业务归属；不代表其是 HBM 龙头。",
    },
    {
        "evidence_id": "E3-884",
        "company": "韦尔股份",
        "subsegment": "模拟/RF/MCU/传感器",
        "title": "韦尔股份 2024 年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/2025-04-16/1223104428.pdf",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "OmniVision 官方产品页展示 CMOS 图像传感器和相关成像解决方案产品组合。",
        "claim": "韦尔股份旗下 OmniVision 覆盖 CMOS 图像传感器产品，可支撑其在图像传感器环节的业务归属。",
    },
    {
        "evidence_id": "E3-885",
        "company": "中芯国际",
        "subsegment": "晶圆代工/Foundry",
        "title": "中芯国际 2024 年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/2025-03-28/1222924320.PDF",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "中芯国际官网披露，公司提供 0.35 微米到 FinFET 不同技术节点的晶圆代工技术平台。",
        "claim": "中芯国际覆盖成熟制程及 FinFET 等晶圆代工平台，可支撑其在晶圆代工/Foundry环节的业务归属。",
    },
    {
        "evidence_id": "E3-886",
        "company": "晶合集成",
        "subsegment": "晶圆代工/Foundry",
        "title": "晶合集成官网",
        "url": "https://www.nexchip.com.cn/",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "晶合集成官网介绍公司为 12 英寸晶圆代工企业，面向显示驱动、CIS、MCU、电源管理等应用提供晶圆制造服务。",
        "claim": "晶合集成覆盖 12 英寸成熟制程晶圆代工服务，可支撑其在晶圆代工/Foundry环节的业务归属。",
    },
    {
        "evidence_id": "E3-887",
        "company": "拓荆科技",
        "subsegment": "薄膜沉积设备",
        "title": "拓荆科技 2024 年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/2025-04-25/1223286833.PDF",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "拓荆科技官网产品中心列示 PECVD、ALD、SACVD、HDPCVD、Flowable CVD 等薄膜沉积设备。",
        "claim": "拓荆科技覆盖 CVD/ALD 等薄膜沉积设备，可支撑其在薄膜沉积设备环节的业务归属。",
    },
    {
        "evidence_id": "E3-888",
        "company": "华海清科",
        "subsegment": "清洗/CMP/热处理设备",
        "title": "华海清科 2024 年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/2025-04-29/1223387671.PDF",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "华海清科官网披露，公司产品包括化学机械抛光（CMP）装备和减薄设备等。",
        "claim": "华海清科覆盖 CMP 抛光设备，可支撑其在清洗/CMP/热处理设备环节的业务归属。",
    },
    {
        "evidence_id": "E3-889",
        "company": "盛美上海",
        "subsegment": "清洗/CMP/热处理设备",
        "title": "盛美上海 2024 年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/2025-02-27/1222651596.PDF",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "盛美上海官网产品页展示单片清洗设备、槽式清洗设备等晶圆清洗设备产品。",
        "claim": "盛美上海覆盖半导体晶圆清洗设备，可支撑其在清洗/CMP/热处理设备环节的业务归属。",
    },
    {
        "evidence_id": "E3-890",
        "company": "中科飞测",
        "subsegment": "量测检测设备",
        "title": "中科飞测 2024 年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/2025-04-04/1223006264.PDF",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "中科飞测官网产品中心展示无图形晶圆缺陷检测设备、三维形貌量测设备、膜厚量测设备、套刻精度量测设备等产品。",
        "claim": "中科飞测覆盖缺陷检测和膜厚/CD/形貌等量测设备，可支撑其在量测检测设备环节的业务归属。",
    },
    {
        "evidence_id": "E3-891",
        "company": "华峰测控",
        "subsegment": "测试设备",
        "title": "华峰测控 2024 年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/2025-03-14/1222788332.PDF",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "华峰测控官网产品页列示 STS8600 SoC Test System、STS8300 等测试系统。",
        "claim": "华峰测控覆盖 SoC 测试系统，可支撑其在测试设备环节的业务归属。",
    },
    {
        "evidence_id": "E3-892",
        "company": "长川科技",
        "subsegment": "测试设备",
        "title": "长川科技 2024 年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/2025-04-29/1223380487.PDF",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "长川科技官网产品中心展示测试机、分选机、探针台等半导体测试设备。",
        "claim": "长川科技覆盖测试机、分选机和探针台，可支撑其在测试设备环节的业务归属。",
    },
    {
        "evidence_id": "E3-893",
        "company": "GlobalWafers",
        "subsegment": "硅片",
        "title": "GlobalWafers Products",
        "url": "https://www.sas-globalwafers.com/products-2/",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "GlobalWafers 官方产品页展示抛光片、外延片、SOI 片、退火片等半导体硅片产品。",
        "claim": "GlobalWafers 覆盖半导体硅片和外延片产品，可支撑其在硅片环节的业务归属。",
    },
    {
        "evidence_id": "E3-894",
        "company": "TCL中环",
        "subsegment": "硅片",
        "title": "TCL中环 2024 年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/2025-04-26/1223330188.PDF",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "TCL中环官网产品与服务页面展示半导体材料业务，覆盖半导体硅片等产品方向。",
        "claim": "TCL中环覆盖半导体硅片材料业务，可支撑其在硅片环节的业务归属。",
    },
    {
        "evidence_id": "E3-895",
        "company": "沪硅产业",
        "subsegment": "硅片",
        "title": "沪硅产业 2024 年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/2025-04-24/1223237698.PDF",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "沪硅产业官网产品与服务页面展示 300mm 半导体硅片、200mm 半导体硅片和外延片等产品。",
        "claim": "沪硅产业覆盖 300mm、200mm 半导体硅片及外延片，可支撑其在硅片环节的业务归属。",
    },
    {
        "evidence_id": "E3-896",
        "company": "立昂微",
        "subsegment": "硅片",
        "title": "立昂微 2024 年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/2025-04-29/1223380678.PDF",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "立昂微官网产品中心展示半导体硅片、半导体功率器件、化合物半导体射频芯片等产品。",
        "claim": "立昂微覆盖半导体硅片产品，可支撑其在硅片环节的业务归属。",
    },
    {
        "evidence_id": "E3-897",
        "company": "南大光电",
        "subsegment": "光刻胶/配套材料",
        "title": "南大光电 2024 年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/2025-04-03/1222992364.PDF",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "南大光电官网产品页展示 ArF 光刻胶及相关配套材料。",
        "claim": "南大光电覆盖 ArF 光刻胶产品，可支撑其在光刻胶/配套材料环节的业务归属。",
    },
    {
        "evidence_id": "E3-898",
        "company": "彤程新材",
        "subsegment": "光刻胶/配套材料",
        "title": "彤程新材 2024 年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/2025-04-18/1223159664.pdf",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "彤程新材官网电子材料业务页面展示半导体光刻胶和显示光刻胶等电子材料业务。",
        "claim": "彤程新材覆盖半导体光刻胶相关电子材料，可支撑其在光刻胶/配套材料环节的业务归属。",
    },
    {
        "evidence_id": "E3-899",
        "company": "晶瑞电材",
        "subsegment": "光刻胶/配套材料",
        "title": "晶瑞电材 2024 年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/2025-04-24/1223245750.PDF",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "晶瑞电材官网产品中心展示光刻胶、超净高纯试剂、锂电池材料等产品。",
        "claim": "晶瑞电材覆盖光刻胶产品，可支撑其在光刻胶/配套材料环节的业务归属。",
    },
    {
        "evidence_id": "E3-900",
        "company": "晶瑞电材",
        "subsegment": "电子气体/湿电子化学品",
        "title": "晶瑞电材 2024 年年度报告：超净高纯试剂",
        "url": "https://static.cninfo.com.cn/finalpage/2025-04-24/1223245750.PDF",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "晶瑞电材官网产品中心展示超净高纯试剂等电子化学品方向。",
        "claim": "晶瑞电材覆盖超净高纯试剂/湿电子化学品，可支撑其在电子气体/湿电子化学品环节的业务归属。",
    },
    {
        "evidence_id": "E3-901",
        "company": "JSR",
        "subsegment": "光刻胶/配套材料",
        "title": "JSR Semiconductor Materials",
        "url": "https://www.jsr.co.jp/jsr_e/products/em/",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "JSR 官网半导体材料页面列示光刻胶、CMP 材料和清洗材料等半导体材料产品。",
        "claim": "JSR 覆盖半导体光刻胶和配套材料，可支撑其在光刻胶/配套材料环节的业务归属。",
    },
    {
        "evidence_id": "E3-902",
        "company": "华特气体",
        "subsegment": "电子气体/湿电子化学品",
        "title": "华特气体 2024 年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/2025-04-10/1223044748.PDF",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "华特气体官网产品页展示电子特种气体相关产品。",
        "claim": "华特气体覆盖电子特种气体，可支撑其在电子气体/湿电子化学品环节的业务归属。",
    },
    {
        "evidence_id": "E3-903",
        "company": "江化微",
        "subsegment": "电子气体/湿电子化学品",
        "title": "江化微 2024 年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/2025-03-22/1222869366.PDF",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "江化微官网产品中心展示超净高纯试剂、光刻胶配套试剂等湿电子化学品。",
        "claim": "江化微覆盖湿电子化学品，可支撑其在电子气体/湿电子化学品环节的业务归属。",
    },
    {
        "evidence_id": "E3-904",
        "company": "有研新材",
        "subsegment": "靶材",
        "title": "有研新材 2024 年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/2025-04-30/1223408404.PDF",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "有研新材官网产品与服务页面展示高纯金属、靶材等半导体材料方向。",
        "claim": "有研新材覆盖高纯金属和靶材材料，可支撑其在靶材环节的业务归属。",
    },
    {
        "evidence_id": "E3-905",
        "company": "江丰电子",
        "subsegment": "靶材",
        "title": "江丰电子 2024 年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/2025-04-16/1223102295.PDF",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "江丰电子官网产品中心展示超高纯金属溅射靶材等产品。",
        "claim": "江丰电子覆盖超高纯金属溅射靶材，可支撑其在靶材环节的业务归属。",
    },
]

APPEND_MAP = {
    ("芯原股份", "半导体IP/芯片定制"): ["E3-880"],
    ("MediaTek", "手机SoC/通信基带"): ["E3-881"],
    ("兆易创新", "模拟/RF/MCU/传感器"): ["E3-882"],
    ("兆易创新", "DRAM/HBM"): ["E3-883"],
    ("韦尔股份", "模拟/RF/MCU/传感器"): ["E3-884"],
    ("中芯国际", "晶圆代工/Foundry"): ["E3-885"],
    ("晶合集成", "晶圆代工/Foundry"): ["E3-886"],
    ("拓荆科技", "薄膜沉积设备"): ["E3-887"],
    ("华海清科", "清洗/CMP/热处理设备"): ["E3-888"],
    ("盛美上海", "清洗/CMP/热处理设备"): ["E3-889"],
    ("中科飞测", "量测检测设备"): ["E3-890"],
    ("华峰测控", "测试设备"): ["E3-891"],
    ("长川科技", "测试设备"): ["E3-892"],
    ("GlobalWafers", "硅片"): ["E3-893"],
    ("TCL中环", "硅片"): ["E3-894"],
    ("沪硅产业", "硅片"): ["E3-895"],
    ("立昂微", "硅片"): ["E3-896"],
    ("南大光电", "光刻胶/配套材料"): ["E3-897"],
    ("彤程新材", "光刻胶/配套材料"): ["E3-898"],
    ("晶瑞电材", "光刻胶/配套材料"): ["E3-899"],
    ("晶瑞电材", "电子气体/湿电子化学品"): ["E3-900"],
    ("JSR", "光刻胶/配套材料"): ["E3-901"],
    ("华特气体", "电子气体/湿电子化学品"): ["E3-902"],
    ("江化微", "电子气体/湿电子化学品"): ["E3-903"],
    ("有研新材", "靶材"): ["E3-904"],
    ("江丰电子", "靶材"): ["E3-905"],
}


def as_evidence_record(row: dict[str, str]) -> dict[str, object]:
    return {
        "evidence_id": row["evidence_id"],
        "task_id": "S3-authoritative-evidence-enrichment-8",
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
