from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "data" / "evidence" / "evidence_stage_3.jsonl"
LEADERS_PATH = ROOT / "data" / "company_pool" / "company_leaders_stage_3.csv"
STAGE6_PATH = ROOT / "data" / "business_graph" / "stage6_company_product_relations.csv"
DC_EVIDENCE_PATH = ROOT / "data" / "evidence" / "evidence_stage_7_digital_china.jsonl"
DC_RELATIONS_PATH = ROOT / "data" / "business_graph" / "stage7_digital_china_relations.csv"

NOW = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


EVIDENCE_ROWS = [
    {
        "evidence_id": "E3-830",
        "company": "寒武纪",
        "subsegment": "AI/GPU/CPU算力芯片",
        "title": "寒武纪 2024 年年度报告",
        "url": "data/reports/cninfo/688256_寒武纪_2024年年度报告.pdf",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "年报披露公司先后推出寒武纪 1A/1H/1M 系列智能处理器、基于思元 100/270/290/370 的云端智能加速卡，以及基于思元 220 的边缘智能加速卡。",
        "claim": "寒武纪覆盖云端和边缘 AI 智能芯片/加速卡产品，可支撑其在 AI/GPU/CPU 算力芯片环节的业务归属。",
    },
    {
        "evidence_id": "E3-831",
        "company": "海光信息",
        "subsegment": "AI/GPU/CPU算力芯片",
        "title": "海光信息 2024 年年度报告",
        "url": "data/reports/cninfo/688041_海光信息_海光信息技术股份有限公司2024年年度报告.pdf",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "年报释义说明 CPU 为中央处理器/通用处理器，DCU 为公司基于通用 GPGPU 架构设计、发布的深度计算处理器。",
        "claim": "海光信息覆盖 CPU 与 DCU 算力处理器产品，可支撑其在 AI/GPU/CPU 算力芯片环节的业务归属。",
    },
    {
        "evidence_id": "E3-832",
        "company": "澜起科技",
        "subsegment": "AI/GPU/CPU算力芯片",
        "title": "澜起科技 2024 年年度报告",
        "url": "data/reports/cninfo/688008_澜起科技_澜起科技2024年年度报告.pdf",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "年报披露公司致力于为云计算和人工智能领域提供高性能、低功耗芯片解决方案，内存接口及模组配套芯片收入增长，并定义 CXL 为 CPU 与专用加速器、高性能存储系统之间的高速互连协议。",
        "claim": "澜起科技更适合作为 AI 服务器相关内存接口/CXL 互连芯片代表，而不是 AI GPU 生产商。",
    },
    {
        "evidence_id": "E3-833",
        "company": "中科曙光",
        "subsegment": "AI服务器/云基础设施",
        "title": "中科曙光 2024 年年度报告",
        "url": "data/reports/cninfo/603019_中科曙光_中科曙光2024年年度报告.pdf",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "年报披露公司推出存储、网络安全、大数据、云计算等产品和解决方案，完成“芯-端-云-算”全产业链布局，并覆盖服务器硬件、IO 存储、云计算平台、大数据平台、算力服务平台等。",
        "claim": "中科曙光覆盖服务器硬件、存储、云计算和算力服务平台，可支撑其在 AI服务器/云基础设施环节的业务归属。",
    },
    {
        "evidence_id": "E3-834",
        "company": "中科曙光",
        "subsegment": "AI服务器/云基础设施",
        "title": "中科曙光 2024 年年度报告：液冷技术",
        "url": "data/reports/cninfo/603019_中科曙光_中科曙光2024年年度报告.pdf",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "年报披露公司自 2011 年起开展液冷技术研究，形成冷板式液冷、浸没液冷、浸没相变液冷三大发展阶段，第三代 C8000 浸没液冷解决方案完成研发升级。",
        "claim": "中科曙光具备液冷基础设施/液冷服务器相关产品与方案能力。",
    },
    {
        "evidence_id": "E3-835",
        "company": "工业富联",
        "subsegment": "AI服务器/云基础设施",
        "title": "工业富联 2024 年年度报告",
        "url": "data/reports/cninfo/601138_工业富联_富士康工业互联网股份有限公司2024年年度报告.pdf",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "年报披露公司依托 AI 全产业链垂直整合及智能制造优势，AI 服务器营收同比增长超过 150%，并在先进液冷设备、自动化、数据中心等级测试集群等方面强化优势。",
        "claim": "工业富联覆盖 AI 服务器制造和数据中心/液冷相关基础设施能力，可支撑其在 AI服务器/云基础设施环节的业务归属。",
    },
    {
        "evidence_id": "E3-836",
        "company": "浪潮信息",
        "subsegment": "AI服务器/云基础设施",
        "title": "浪潮信息 2024 年年度报告",
        "url": "data/reports/cninfo/000977_浪潮信息_2024年年度报告.pdf",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "年报披露浪潮信息 2024 年服务器全球第二、中国第一，存储装机容量全球前三、中国第一，液冷服务器中国第一，并持续引领 AI 计算、开放计算、绿色计算。",
        "claim": "浪潮信息覆盖 AI 服务器、存储设备和液冷服务器，可支撑其在 AI服务器/云基础设施环节的龙头/业务归属判断。",
    },
    {
        "evidence_id": "E3-837",
        "company": "佰维存储",
        "subsegment": "存储控制/模组/NOR",
        "title": "佰维存储 2024 年年度报告",
        "url": "data/reports/cninfo/688525_佰维存储_2024年年度报告.pdf",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "年报定义 eMMC、UFS、SSD 等存储产品，并披露消费类存储模组产品开发、量产和客户导入进展。",
        "claim": "佰维存储覆盖 eMMC、UFS、SSD 和消费类存储模组，可支撑其在存储控制/模组/NOR环节的业务归属。",
    },
    {
        "evidence_id": "E3-838",
        "company": "江波龙",
        "subsegment": "存储控制/模组/NOR",
        "title": "江波龙 2024 年年度报告",
        "url": "data/reports/cninfo/301308_江波龙_2024年年度报告.pdf",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "年报披露公司正从传统存储模组厂向综合型半导体存储品牌企业转型，形成存储芯片设计、主控芯片设计及固件算法开发、封装测试等核心能力，并定义 eMMC、UFS、SSD 等产品。",
        "claim": "江波龙覆盖存储模组、存储芯片设计、主控芯片设计和固件算法，可支撑其在存储控制/模组/NOR环节的业务归属。",
    },
    {
        "evidence_id": "E3-839",
        "company": "比亚迪",
        "subsegment": "新能源汽车/汽车电子",
        "title": "比亚迪 2024 年年度报告",
        "url": "data/reports/cninfo/002594_比亚迪_2024年年度报告.pdf",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "年报披露公司经营范围包括汽车电子装置研发、销售和新能源汽车关键零部件研发；同时披露“整车智能”和高阶智能驾驶辅助系统“天神之眼”等智能化战略。",
        "claim": "比亚迪覆盖新能源汽车、汽车电子装置和智能驾驶系统，可支撑其在新能源汽车/汽车电子环节的需求端龙头判断。",
    },
    {
        "evidence_id": "E3-840",
        "company": "神州数码",
        "subsegment": "AI服务器/云基础设施",
        "title": "神州数码 2024 年年度报告",
        "url": "data/reports/cninfo/000034_神州数码_2024年年度报告.pdf",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "年报披露神州鲲泰基于昇腾基础硬件打造 AI 智算系列服务器、自研异构智算调度运营平台 HISO、异构智算加速平台 HICA，并推出“硅光+液冷”整机柜产品。",
        "claim": "神州数码/神州鲲泰具备国产算力服务器、AI 智算服务器和液冷整机柜相关产品能力，可作为神州数码业务切入层的事实支撑。",
    },
    {
        "evidence_id": "E3-841",
        "company": "联想",
        "subsegment": "AI服务器/云基础设施",
        "title": "ThinkSystem Servers: AI-Ready Rack, Tower & Edge Solutions | Lenovo",
        "url": "https://www.lenovo.com/us/en/servers-storage/servers",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Lenovo 官方 ThinkSystem 页面介绍 AI-ready rack、tower 与 edge server systems，并归入 servers and storage 产品线。",
        "claim": "联想覆盖 AI-ready ThinkSystem 服务器和数据中心产品，可支撑其在 AI服务器/云基础设施环节的业务归属。",
    },
    {
        "evidence_id": "E3-842",
        "company": "Dell",
        "subsegment": "AI服务器/云基础设施",
        "title": "PowerEdge AI Servers with GPU Acceleration | Dell",
        "url": "https://www.dell.com/en-us/shop/storage-servers-and-networking-for-business/sf/poweredge-ai-servers",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Dell 官方页面列出 PowerEdge AI Servers with GPU Acceleration，用于 AI 工作负载和加速计算。",
        "claim": "Dell 覆盖 PowerEdge AI 服务器和企业基础设施产品，可支撑其在 AI服务器/云基础设施环节的业务归属。",
    },
    {
        "evidence_id": "E3-843",
        "company": "Supermicro",
        "subsegment": "AI服务器/云基础设施",
        "title": "GPU Servers For AI, Deep / Machine Learning & HPC | Supermicro",
        "url": "https://www.supermicro.com/en/products/gpu",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Supermicro 官方 GPU systems 页面说明其提供面向 AI、深度学习/机器学习和 HPC 的 GPU 服务器及 AI systems and solutions。",
        "claim": "Supermicro 覆盖 GPU 服务器和 AI 基础设施系统，可支撑其在 AI服务器/云基础设施环节的业务归属。",
    },
    {
        "evidence_id": "E3-844",
        "company": "Micron",
        "subsegment": "DRAM/HBM",
        "title": "HBM3E | Micron Technology",
        "url": "https://www.micron.com/products/memory/hbm/hbm3e",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Micron 官方 HBM3E 页面称其为面向生成式 AI 创新的高速、高容量 high-bandwidth memory。",
        "claim": "Micron 覆盖 HBM 高带宽存储产品，可支撑其在 DRAM/HBM 环节的业务归属。",
    },
    {
        "evidence_id": "E3-845",
        "company": "SK hynix",
        "subsegment": "DRAM/HBM",
        "title": "SK hynix Announces 16-Layer HBM3E at SK AI Summit 2024",
        "url": "https://news.skhynix.com/sk-hynix-announces-16-layer-hbm3e-at-sk-ai-summit-2024",
        "source_type": "company_or_wire_release",
        "grade": "A-",
        "excerpt": "SK hynix 官方新闻披露其开发 16 层 HBM3E，并用于 AI/HPC 高性能存储需求。",
        "claim": "SK hynix 覆盖 HBM 高带宽存储产品，可支撑其在 DRAM/HBM 环节的业务归属。",
    },
    {
        "evidence_id": "E3-846",
        "company": "Tesla",
        "subsegment": "新能源汽车/汽车电子",
        "title": "Full Self-Driving (Supervised) | Tesla",
        "url": "https://www.tesla.com/fsd",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Tesla 官方 FSD 页面介绍 Full Self-Driving (Supervised) 能力，体现其车辆智能驾驶软硬件系统应用。",
        "claim": "Tesla 覆盖智能驾驶和车载计算相关系统，可支撑其在新能源汽车/汽车电子环节的需求端龙头判断。",
    },
    {
        "evidence_id": "E3-847",
        "company": "华为",
        "subsegment": "新能源汽车/汽车电子",
        "title": "Intelligent Automotive Solution 2030 | Huawei",
        "url": "https://www.huawei.com/en/giv/intelligent-automotive-solution-2030",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Huawei 官方 Intelligent Automotive Solution 2030 页面介绍智能驾驶、智能座舱、智能服务等汽车智能化方向。",
        "claim": "华为覆盖智能汽车解决方案，可支撑其在新能源汽车/汽车电子环节的业务归属。",
    },
]

APPEND_MAP = {
    ("寒武纪", "AI/GPU/CPU算力芯片"): ["E3-830"],
    ("海光信息", "AI/GPU/CPU算力芯片"): ["E3-831"],
    ("澜起科技", "AI/GPU/CPU算力芯片"): ["E3-832"],
    ("中科曙光", "AI服务器/云基础设施"): ["E3-833", "E3-834"],
    ("工业富联", "AI服务器/云基础设施"): ["E3-835"],
    ("浪潮信息", "AI服务器/云基础设施"): ["E3-836"],
    ("联想", "AI服务器/云基础设施"): ["E3-841"],
    ("Dell", "AI服务器/云基础设施"): ["E3-842"],
    ("Supermicro", "AI服务器/云基础设施"): ["E3-843"],
    ("佰维存储", "存储控制/模组/NOR"): ["E3-837"],
    ("江波龙", "存储控制/模组/NOR"): ["E3-838"],
    ("比亚迪", "新能源汽车/汽车电子"): ["E3-839"],
    ("Tesla", "新能源汽车/汽车电子"): ["E3-846"],
    ("华为", "新能源汽车/汽车电子"): ["E3-847"],
    ("Micron", "DRAM/HBM"): ["E3-844"],
    ("SK hynix", "DRAM/HBM"): ["E3-845"],
}

STAGE6_MAP = {
    ("寒武纪", "AI加速卡"): ["E3-830"],
    ("海光信息", "CPU/DCU算力芯片"): ["E3-831"],
    ("中科曙光", "AI服务器"): ["E3-833"],
    ("中科曙光", "液冷服务器"): ["E3-834"],
    ("中科曙光", "国产算力服务器"): ["E3-833"],
    ("工业富联", "AI服务器"): ["E3-835"],
    ("工业富联", "GPU服务器"): ["E3-835"],
    ("工业富联", "数据中心基础设施服务"): ["E3-835"],
    ("浪潮信息", "AI服务器"): ["E3-836"],
    ("浪潮信息", "GPU服务器"): ["E3-836"],
    ("浪潮信息", "液冷服务器"): ["E3-836"],
    ("浪潮信息", "存储设备"): ["E3-836"],
    ("联想", "AI服务器"): ["E3-841"],
    ("联想", "存储设备"): ["E3-841"],
    ("联想", "数据中心基础设施服务"): ["E3-841"],
    ("联想", "AI GPU"): ["E3-841"],
    ("Dell", "AI服务器"): ["E3-842"],
    ("Dell", "存储设备"): ["E3-842"],
    ("Dell", "数据中心基础设施服务"): ["E3-842"],
    ("Dell", "AI GPU"): ["E3-842"],
    ("Supermicro", "AI服务器"): ["E3-843"],
    ("Supermicro", "GPU服务器"): ["E3-843"],
    ("Supermicro", "AI GPU"): ["E3-843"],
    ("Micron", "HBM高带宽存储"): ["E3-844"],
    ("SK hynix", "HBM高带宽存储"): ["E3-845"],
    ("佰维存储", "存储模组"): ["E3-837"],
    ("江波龙", "存储模组"): ["E3-838"],
    ("比亚迪", "智能汽车解决方案"): ["E3-839"],
    ("比亚迪", "汽车电子系统"): ["E3-839"],
    ("Tesla", "智能汽车解决方案"): ["E3-846"],
    ("Tesla", "车载计算平台"): ["E3-846"],
    ("华为", "智能汽车解决方案"): ["E3-847"],
}

DC_EVIDENCE_ROWS = [
    {
        "evidence_id": "DC-S-101",
        "company_name": "华为",
        "relationship_status": "confirmed_public_relationship",
        "relationship_type": "生态合作/解决方案匹配",
        "source_title": "神州数码 2024 年年度报告：神州鲲泰/昇腾 AI 智算系列服务器",
        "source_url_or_file": "data/reports/cninfo/000034_神州数码_2024年年度报告.pdf",
        "source_type": "official_disclosure",
        "evidence_excerpt": "神州数码年报披露神州鲲泰基于昇腾基础硬件打造 AI 智算系列服务器，并与华为侧开展联合开发和产品适配。",
        "possible_claim": "公开披露可证明神州数码围绕华为昇腾生态、神州鲲泰 AI 智算服务器存在公开业务关系线索。",
        "confidence": "high",
        "source_grade": "A",
    },
]


def as_evidence_record(row: dict[str, str]) -> dict[str, object]:
    return {
        "evidence_id": row["evidence_id"],
        "task_id": "S3-authoritative-evidence-enrichment-5",
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
        "search_tool": "official_site_or_cninfo",
        "query": f"{row['company']} {row['subsegment']} official product evidence",
    }


def add_ids(existing: str, ids: list[str]) -> str:
    parts = [item.strip() for item in (existing or "").split(";") if item.strip()]
    for evidence_id in ids:
        if evidence_id not in parts:
            parts.append(evidence_id)
    return ";".join(parts)


def append_or_replace_jsonl(path: Path, replacements: dict[str, dict[str, object]]) -> tuple[int, int]:
    output: list[dict[str, object]] = []
    seen: set[str] = set()
    replaced = 0
    if path.exists():
        with path.open("r", encoding="utf-8") as file:
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
    with path.open("w", encoding="utf-8", newline="") as file:
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


def update_digital_china() -> dict[str, int]:
    replacements: dict[str, dict[str, object]] = {}
    for row in DC_EVIDENCE_ROWS:
        item = dict(row)
        item.update(
            {
                "task_id": "S7-digital-china-public-relations",
                "publish_date": "",
                "limitations": "公开资料不能证明内部客户关系；只能证明公开合作、生态关系、产品/场景匹配或潜在业务相关性。",
                "retrieved_at": NOW,
                "search_tool": "cninfo",
                "query": "神州数码 2024 年报 神州鲲泰 昇腾 AI 智算服务器",
            }
        )
        replacements[row["evidence_id"]] = item
    replaced, appended = append_or_replace_jsonl(DC_EVIDENCE_PATH, replacements)

    with DC_RELATIONS_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    output: list[dict[str, str]] = []
    updates = 0
    for row in rows:
        company = row.get("company_name", "").strip()
        if company == "国产算力":
            updates += 1
            continue
        if company == "华为":
            before = row.get("evidence_ids", "")
            row["evidence_ids"] = add_ids(before, ["DC-S-101"])
            row["relationship_status"] = "confirmed_public_relationship"
            row["confidence"] = "high"
            row["requires_internal_validation"] = "true"
            if "神州鲲泰" not in row.get("relationship_basis", ""):
                row["relationship_basis"] = (
                    row.get("relationship_basis", "").strip()
                    + "；神州数码 2024 年报披露神州鲲泰基于昇腾基础硬件打造 AI 智算系列服务器，并与华为侧开展联合开发和产品适配。"
                ).strip("；")
            if row["evidence_ids"] != before:
                updates += 1
        if row.get("relationship_status") != "confirmed_public_relationship":
            row["asset_tier"] = "待验证"
        output.append(row)

    with DC_RELATIONS_PATH.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output)
    return {
        "dc_evidence_replaced": replaced,
        "dc_evidence_appended": appended,
        "dc_relation_updates": updates,
    }


def main() -> None:
    replacements = {row["evidence_id"]: as_evidence_record(row) for row in EVIDENCE_ROWS}
    replaced, appended = append_or_replace_jsonl(EVIDENCE_PATH, replacements)
    leader_updates = update_csv(LEADERS_PATH, ("company_name", "subsegment_name"), APPEND_MAP)
    stage6_updates = update_csv(STAGE6_PATH, ("company_name", "product_service_name"), STAGE6_MAP)
    dc_result = update_digital_china()
    print(json.dumps(
        {
            "evidence_replaced": replaced,
            "evidence_appended": appended,
            "leader_updates": leader_updates,
            "stage6_updates": stage6_updates,
            **dc_result,
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
