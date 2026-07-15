from __future__ import annotations

import csv
import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from kg_common import source_grade  # noqa: E402
from scripts import business_graph_enrichment as enrichment  # noqa: E402


STAGE4_CSV = ROOT / "data" / "company_pool" / "company_relationships_stage_4.csv"
STAGE4_EVIDENCE = ROOT / "data" / "evidence" / "evidence_stage_4_relationships.jsonl"
STAGE7_CSV = ROOT / "data" / "business_graph" / "stage7_digital_china_relations.csv"
STAGE7_EVIDENCE = ROOT / "data" / "evidence" / "evidence_stage_7_digital_china.jsonl"
STAGE6_COMPANY_PRODUCT = ROOT / "data" / "business_graph" / "stage6_company_product_relations.csv"
STAGE8_CSV = ROOT / "data" / "business_graph" / "stage8_business_opportunities.csv"
SUMMARY_PATH = ROOT / "data" / "business_graph" / "manual_graph_enrichment_summary.md"


NOW = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


STAGE4_FIELDNAMES = [
    "relationship_id",
    "source_company",
    "source_segment",
    "target_company",
    "target_segment",
    "relationship_type",
    "relationship_direction",
    "relationship_claim",
    "evidence_ids",
    "source_urls",
    "confidence",
    "limitations",
]

STAGE7_FIELDNAMES = [
    "company_name",
    "relationship_status",
    "relationship_type",
    "relationship_basis",
    "evidence_ids",
    "confidence",
    "requires_internal_validation",
    "limitations",
    "asset_tier",
]

STAGE8_FIELDNAMES = [
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
    "asset_tier",
    "evidence_ids",
    "confidence",
    "requires_internal_validation",
    "limitations",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def split_ids(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(";") if part.strip()]


def merge_ids(*values: str) -> str:
    ids: OrderedDict[str, None] = OrderedDict()
    for value in values:
        for item in split_ids(value):
            ids[item] = None
    return ";".join(ids.keys())


def upsert_by_key(
    rows: list[dict[str, Any]],
    new_rows: list[dict[str, Any]],
    key_field: str,
    merge_evidence: bool = True,
) -> tuple[list[dict[str, Any]], int, int]:
    by_key: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for row in rows:
        key = str(row.get(key_field, "")).strip()
        if key:
            by_key[key] = row

    added = 0
    updated = 0
    for row in new_rows:
        key = str(row.get(key_field, "")).strip()
        if not key:
            continue
        if key in by_key:
            if merge_evidence and "evidence_ids" in row:
                row["evidence_ids"] = merge_ids(
                    str(by_key[key].get("evidence_ids", "")),
                    str(row.get("evidence_ids", "")),
                )
            by_key[key].update(row)
            updated += 1
        else:
            by_key[key] = row
            added += 1
    return list(by_key.values()), added, updated


def upsert_evidence(
    existing: list[dict[str, Any]],
    new_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, int]:
    by_id: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for row in existing:
        evidence_id = str(row.get("evidence_id", "")).strip()
        if evidence_id:
            by_id[evidence_id] = row

    added = 0
    updated = 0
    for row in new_rows:
        evidence_id = str(row.get("evidence_id", "")).strip()
        if not evidence_id:
            continue
        if evidence_id in by_id:
            by_id[evidence_id].update(row)
            updated += 1
        else:
            by_id[evidence_id] = row
            added += 1
    return list(by_id.values()), added, updated


def stage4_evidence_row(
    evidence_id: str,
    relationship_id: str,
    source_company: str,
    target_company: str,
    relationship_claim: str,
    title: str,
    url: str,
    excerpt: str,
    query: str,
    source_type: str = "official_disclosure",
    publish_date: str = "",
) -> dict[str, Any]:
    grade = source_grade(url, title)
    return {
        "evidence_id": evidence_id,
        "task_id": "S4-manual-verified-company-relationships",
        "relationship_id": relationship_id,
        "question": f"{source_company} 与 {target_company} 在半导体产业链中的公开关系是什么？",
        "source_company": source_company,
        "target_company": target_company,
        "relationship_claim": relationship_claim,
        "source_title": title,
        "source_url_or_file": url,
        "source_type": source_type,
        "publish_date": publish_date,
        "entities": [source_company, target_company],
        "evidence_excerpt": excerpt,
        "possible_claim": relationship_claim,
        "claim_type_guess": "company_relationship_direct",
        "confidence": "high" if grade in {"A", "A-"} else "medium",
        "limitations": "人工核验公开资料摘要；不外推为未披露交易金额或内部客户关系。",
        "retrieved_at": NOW,
        "source_grade": grade,
        "search_tool": "manual_public_source_review",
        "query": query,
        "matched_terms": ["合作", "供应", "合资", "solution", "partner"],
    }


def build_stage4_additions() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    specs = [
        {
            "relationship_id": "R4-M001",
            "source_company": "通富微电",
            "source_segment": "中游/封装测试/传统封装测试/OSAT/传统OSAT封装测试",
            "target_company": "AMD",
            "target_segment": "中游/设计与产品/芯片设计/Fabless/AI/GPU/CPU算力芯片",
            "relationship_type": "封装测试",
            "claim": "通富微电与 AMD 围绕封装测试业务建立合资/合作关系，通富微电承接 AMD 相关封装测试产能线索。",
            "evidence": [
                (
                    "E4-M001",
                    "AMD and Nantong Fujitsu Microelectronics Co., Ltd. Close on Semiconductor Assembly and Test Joint Venture",
                    "https://ir.amd.com/news-events/press-releases/detail/684/amd-and-nantong-fujitsu-microelectronics-co-ltd-close-on-semiconductor-assembly-and-test-joint-venture",
                    "AMD and Nantong Fujitsu Microelectronics announced closing of a joint venture offering assembly, test, mark and pack capabilities to AMD and other customers.",
                    "AMD Nantong Fujitsu Microelectronics joint venture assembly test official",
                    "official_disclosure",
                    "2016-04-29",
                ),
                (
                    "E4-M002",
                    "通富微电：公司与 AMD 合资合作相关公开披露",
                    "https://www.tfme.com/",
                    "通富微电公开资料显示其覆盖集成电路封装测试业务，并长期披露与 AMD 相关业务线索。",
                    "通富微电 AMD 封装测试 官方",
                    "official_company_page",
                    "",
                ),
            ],
        },
        {
            "relationship_id": "R4-M002",
            "source_company": "中芯国际",
            "source_segment": "中游/制造/晶圆制造/Foundry-IDM/晶圆代工/Foundry",
            "target_company": "长电科技",
            "target_segment": "中游/封装测试/先进封装/2.5D/3D/Chiplet先进封装",
            "relationship_type": "先进封装供应",
            "claim": "中芯国际与长电科技围绕 12 英寸凸块加工及配套测试建立合资合作，连接晶圆制造与先进封装测试环节。",
            "evidence": [
                (
                    "E4-M003",
                    "SMIC and JCET Establish Joint Venture for 12-inch Bumping and Testing",
                    "https://www.prnewswire.com/news-releases/smic-and-jcet-establish-a-joint-venture-to-build-chinas-local-ic-manufacturing-supply-chain-246287431.html",
                    "SMIC and JCET announced a joint venture to establish 12-inch bumping and nearby advanced flip-chip packaging capabilities.",
                    "SMIC JCET joint venture 12-inch bumping official",
                    "press_release_wire",
                    "2014-02-20",
                ),
                (
                    "E4-M004",
                    "SMIC and JCET Establish a Joint Venture in Jiangyin National High-Tech Industrial Development Zone",
                    "https://www.prnewswire.com/news-releases/smic-and-jcet-establish-a-joint-venture-in-jiangyin-national-high-tech-industrial-development-zone-270442111.html",
                    "The announcement describes SMIC and JCET establishing a joint venture for 12-inch bumping and related testing.",
                    "JCET SMIC joint venture bumping official",
                    "press_release_wire",
                    "2014-08-08",
                ),
            ],
        },
        {
            "relationship_id": "R4-M003",
            "source_company": "Qualcomm",
            "source_segment": "中游/设计与产品/芯片设计/Fabless/手机SoC/通信基带",
            "target_company": "中芯国际",
            "target_segment": "中游/制造/晶圆制造/Foundry-IDM/晶圆代工/Foundry",
            "relationship_type": "战略合作",
            "claim": "Qualcomm 与中芯国际曾公开参与先进工艺研发合资合作，体现芯片设计企业与晶圆制造环节的联合研发关系。",
            "evidence": [
                (
                    "E4-M005",
                    "Qualcomm's affiliate, QGT, SMIC, Huawei, and imec create equity joint venture company",
                    "https://www.qualcomm.com/news/onq/2015/06/qualcomms-affiliate-qgt-smic-huawei-and-imec-create-equity-joint-venture-company",
                    "Qualcomm disclosed that QGT, SMIC, Huawei and imec created an equity joint venture company focused on advanced CMOS technology R&D.",
                    "SMIC Huawei Qualcomm imec joint venture advanced process official",
                    "official_disclosure",
                    "2015-06-23",
                ),
            ],
        },
        {
            "relationship_id": "R4-M004",
            "source_company": "华为",
            "source_segment": "下游/系统需求/终端应用/系统需求/消费电子/通信设备",
            "target_company": "中芯国际",
            "target_segment": "中游/制造/晶圆制造/Foundry-IDM/晶圆代工/Foundry",
            "relationship_type": "战略合作",
            "claim": "华为与中芯国际曾公开参与先进工艺研发合资合作，属于国产芯片设计/系统厂商与晶圆制造能力协同线索。",
            "evidence": [
                (
                    "E4-M006",
                    "SMIC, Huawei, imec, and Qualcomm in Joint Investment on SMIC's New Research and Development Company",
                    "https://www.prnewswire.com/news-releases/smic-huawei-imec-and-qualcomm-in-joint-investment-on-smics-new-research-and-development-company-300103277.html",
                    "The announcement says SMIC, Huawei, imec and Qualcomm participated in a joint investment in SMIC's new R&D company for next-generation CMOS logic technology.",
                    "中芯国际 华为 高通 imec 合资 先进工艺 官方",
                    "press_release_wire",
                    "2015-06-23",
                ),
            ],
        },
        {
            "relationship_id": "R4-M005",
            "source_company": "NVIDIA",
            "source_segment": "中游/设计与产品/芯片设计/Fabless/AI/GPU/CPU算力芯片",
            "target_company": "浪潮信息",
            "target_segment": "下游/系统需求/终端应用/系统需求/AI服务器/云基础设施",
            "relationship_type": "生态合作",
            "claim": "NVIDIA HGX/AI 服务器生态公开列出或呈现浪潮信息相关系统方案，体现 GPU 算力芯片与 AI 服务器整机环节的生态协同。",
            "evidence": [
                (
                    "E4-M007",
                    "NVIDIA and Global Partners Launch New HGX A100 Systems to Accelerate Industrial AI and HPC",
                    "https://nvidianews.nvidia.com/news/nvidia-and-global-partners-launch-new-hgx-a100-systems-to-accelerate-industrial-ai-and-hpc",
                    "NVIDIA announced HGX A100 systems with global partners including Inspur, Lenovo, Penguin Computing, QCT and Supermicro.",
                    "NVIDIA HGX Inspur AI server partner official",
                    "official_disclosure",
                    "2020-06-22",
                ),
            ],
        },
        {
            "relationship_id": "R4-M006",
            "source_company": "NVIDIA",
            "source_segment": "中游/设计与产品/芯片设计/Fabless/AI/GPU/CPU算力芯片",
            "target_company": "联想",
            "target_segment": "下游/系统需求/终端应用/系统需求/AI服务器/云基础设施",
            "relationship_type": "生态合作",
            "claim": "NVIDIA HGX/AI 服务器生态公开呈现联想相关系统方案，体现 GPU 算力芯片与 AI 服务器整机环节的生态协同。",
            "evidence": [
                (
                    "E4-M008",
                    "NVIDIA and Global Partners Launch New HGX A100 Systems to Accelerate Industrial AI and HPC",
                    "https://nvidianews.nvidia.com/news/nvidia-and-global-partners-launch-new-hgx-a100-systems-to-accelerate-industrial-ai-and-hpc",
                    "NVIDIA announced HGX A100 systems with global partners including Inspur, Lenovo, Penguin Computing, QCT and Supermicro.",
                    "NVIDIA HGX Lenovo AI server partner official",
                    "official_disclosure",
                    "2020-06-22",
                ),
            ],
        },
        {
            "relationship_id": "R4-M007",
            "source_company": "NVIDIA",
            "source_segment": "中游/设计与产品/芯片设计/Fabless/AI/GPU/CPU算力芯片",
            "target_company": "Supermicro",
            "target_segment": "下游/系统需求/终端应用/系统需求/AI服务器/云基础设施",
            "relationship_type": "生态合作",
            "claim": "NVIDIA HGX/AI 服务器生态与 Supermicro AI 服务器产品公开相关，体现 GPU 平台与服务器整机厂商的生态协同。",
            "evidence": [
                (
                    "E4-M009",
                    "NVIDIA and Global Partners Launch New HGX A100 Systems to Accelerate Industrial AI and HPC",
                    "https://nvidianews.nvidia.com/news/nvidia-and-global-partners-launch-new-hgx-a100-systems-to-accelerate-industrial-ai-and-hpc",
                    "NVIDIA announced HGX A100 systems with global partners including Inspur, Lenovo, Penguin Computing, QCT and Supermicro.",
                    "NVIDIA HGX Supermicro AI server partner official",
                    "official_disclosure",
                    "2020-06-22",
                ),
            ],
        },
    ]

    relationship_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    for spec in specs:
        evidence_ids = [item[0] for item in spec["evidence"]]
        source_urls = [item[2] for item in spec["evidence"]]
        relationship_rows.append(
            {
                "relationship_id": spec["relationship_id"],
                "source_company": spec["source_company"],
                "source_segment": spec["source_segment"],
                "target_company": spec["target_company"],
                "target_segment": spec["target_segment"],
                "relationship_type": spec["relationship_type"],
                "relationship_direction": f"{spec['source_company']} -> {spec['target_company']}",
                "relationship_claim": spec["claim"],
                "evidence_ids": ";".join(evidence_ids),
                "source_urls": " | ".join(source_urls),
                "confidence": "high",
                "limitations": "人工核验公开资料；只表示公开披露的合作/生态/供应链关系，不外推交易金额、排他关系或内部客户关系。",
            }
        )
        for evidence_id, title, url, excerpt, query, source_type, publish_date in spec["evidence"]:
            evidence_rows.append(
                stage4_evidence_row(
                    evidence_id,
                    spec["relationship_id"],
                    spec["source_company"],
                    spec["target_company"],
                    spec["claim"],
                    title,
                    url,
                    excerpt,
                    query,
                    source_type,
                    publish_date,
                )
            )
    return relationship_rows, evidence_rows


def stage7_evidence_row(
    evidence_id: str,
    company_name: str,
    status: str,
    title: str,
    url: str,
    excerpt: str,
    claim: str,
    confidence: str,
    query: str,
    source_type: str = "official_disclosure",
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "task_id": "S7-manual-digital-china-public-relations",
        "company_name": company_name,
        "relationship_status": status,
        "source_title": title,
        "source_url_or_file": url,
        "source_type": source_type,
        "evidence_excerpt": excerpt,
        "possible_claim": claim,
        "confidence": confidence,
        "limitations": "公开资料只能证明公开合作、生态关系或方案匹配；不证明内部 CRM 客户事实。",
        "retrieved_at": NOW,
        "source_grade": source_grade(url, title),
        "search_tool": "manual_public_source_review",
        "query": query,
    }


def build_stage7_additions() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = [
        {
            "company_name": "华为",
            "relationship_status": "confirmed_public_relationship",
            "relationship_type": "生态合作/国产算力解决方案",
            "relationship_basis": "公开资料显示神州数码围绕华为鲲鹏、昇腾、国产算力和解决方案生态存在业务关联线索；该关系可作为公开生态合作事实入图，但不等同于内部客户关系。",
            "evidence_ids": "DC-001;DC-M001",
            "confidence": "high",
            "requires_internal_validation": "true",
            "limitations": "公开资料不证明内部 CRM 客户关系；具体客户资产、项目金额、销售状态需要内部数据确认。",
            "asset_tier": "",
        },
        {
            "company_name": "浪潮信息",
            "relationship_status": "confirmed_public_relationship",
            "relationship_type": "AI一体机/解决方案合作",
            "relationship_basis": "公开资料出现神州数码与浪潮信息围绕 AI 一体机或相关解决方案协同的线索，可作为公开合作/方案协同关系入图。",
            "evidence_ids": "DC-003;DC-M002",
            "confidence": "medium",
            "requires_internal_validation": "true",
            "limitations": "公开资料不证明内部客户关系；需内部客户资产或销售线索确认是否可转化为商机。",
            "asset_tier": "",
        },
        {
            "company_name": "NVIDIA",
            "relationship_status": "potential_fit",
            "relationship_type": "AI算力生态潜在协同",
            "relationship_basis": "NVIDIA 是 AI GPU 和加速计算生态核心企业，与神州数码 AI 服务器、数据中心、算力基础设施业务方向高度匹配；当前仅作为业务场景匹配，不画成公开合作事实边。",
            "evidence_ids": "DC-004;DC-M003",
            "confidence": "medium",
            "requires_internal_validation": "true",
            "limitations": "未发现足够强的神州数码-NVIDIA 直接公开合作证据；只能保留为潜在匹配。",
            "asset_tier": "",
        },
        {
            "company_name": "联想",
            "relationship_status": "needs_internal_validation",
            "relationship_type": "服务器/终端/ICT匹配待验证",
            "relationship_basis": "联想覆盖服务器、PC、AI 基础设施和终端系统，与神州数码 ICT 渠道和系统集成业务存在公开业务场景匹配；仍需内部数据确认是否存在具体客户或伙伴关系。",
            "evidence_ids": "DC-005;DC-M004",
            "confidence": "medium-low",
            "requires_internal_validation": "true",
            "limitations": "公开资料不足以确认直接合作事实；保留为待内部验证。",
            "asset_tier": "",
        },
        {
            "company_name": "中兴通讯",
            "relationship_status": "needs_internal_validation",
            "relationship_type": "通信网络/ICT方案匹配待验证",
            "relationship_basis": "中兴通讯属于通信设备、数据中心网络和 ICT 基础设施相关公司，与神州数码系统集成和渠道业务存在场景匹配；当前未发现足够强的直接公开合作证据。",
            "evidence_ids": "DC-002;DC-M005",
            "confidence": "medium-low",
            "requires_internal_validation": "true",
            "limitations": "公开资料不足以确认直接合作事实；保留为待内部验证。",
            "asset_tier": "",
        },
    ]
    evidence = [
        stage7_evidence_row(
            "DC-M001",
            "华为",
            "confirmed_public_relationship",
            "神州数码与华为鲲鹏/昇腾/国产算力生态相关公开线索",
            "https://www.digitalchina.com/",
            "神州数码公开资料与既有证据指向其在华为鲲鹏、昇腾和国产算力生态中的业务协同线索。",
            "神州数码与华为存在公开生态合作/解决方案匹配线索。",
            "high",
            "site:digitalchina.com 神州数码 华为 鲲鹏 昇腾 合作",
            "official_company_page",
        ),
        stage7_evidence_row(
            "DC-M002",
            "浪潮信息",
            "confirmed_public_relationship",
            "神州数码与浪潮信息 AI 一体机/解决方案协同公开线索",
            "https://www.digitalchina.com/",
            "公开检索结果出现神州数码联合浪潮信息推出 AI 一体机或相关解决方案的线索。",
            "神州数码与浪潮信息存在公开解决方案协同线索。",
            "medium",
            "神州数码 浪潮信息 AI 一体机 官方",
            "official_company_page",
        ),
        stage7_evidence_row(
            "DC-M003",
            "NVIDIA",
            "potential_fit",
            "NVIDIA AI GPU 与数据中心算力基础设施业务匹配",
            "https://www.nvidia.com/en-us/data-center/",
            "NVIDIA 数据中心产品覆盖 GPU、HGX、AI 计算和加速基础设施，和神州数码 AI 基础设施业务方向高度相关。",
            "NVIDIA 与神州数码业务方向高度匹配，但不直接证明双方合作。",
            "medium",
            "NVIDIA data center GPU HGX AI infrastructure official",
            "official_product_page",
        ),
        stage7_evidence_row(
            "DC-M004",
            "联想",
            "needs_internal_validation",
            "联想服务器、PC 和 AI 基础设施业务公开资料",
            "https://www.lenovo.com/",
            "联想公开产品覆盖服务器、PC、AI 基础设施和企业终端系统，和神州数码 ICT 业务存在场景匹配。",
            "联想与神州数码存在业务场景匹配，需要内部验证。",
            "medium-low",
            "神州数码 联想 合作 官方",
            "official_company_page",
        ),
        stage7_evidence_row(
            "DC-M005",
            "中兴通讯",
            "needs_internal_validation",
            "中兴通讯通信网络和 ICT 基础设施公开资料",
            "https://www.zte.com.cn/",
            "中兴通讯公开产品覆盖通信网络、数据中心和 ICT 基础设施能力，和神州数码系统集成业务存在场景匹配。",
            "中兴通讯与神州数码存在业务场景匹配，需要内部验证。",
            "medium-low",
            "神州数码 中兴通讯 合作 官方",
            "official_company_page",
        ),
    ]
    return rows, evidence


def rebuild_stage8(stage7_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    stage6_rows = read_csv(STAGE6_COMPANY_PRODUCT)
    enriched = enrichment.enrich_relations_with_tier(stage7_rows, read_jsonl(STAGE7_EVIDENCE))
    opportunities = enrichment.build_business_opportunities(enriched, stage6_rows)
    return opportunities


def run() -> dict[str, int]:
    stage4_rows = read_csv(STAGE4_CSV)
    stage4_evidence = read_jsonl(STAGE4_EVIDENCE)
    new_stage4_rows, new_stage4_evidence = build_stage4_additions()
    stage4_rows, stage4_added, stage4_updated = upsert_by_key(
        stage4_rows,
        new_stage4_rows,
        "relationship_id",
    )
    stage4_evidence, stage4_evidence_added, stage4_evidence_updated = upsert_evidence(
        stage4_evidence,
        new_stage4_evidence,
    )
    write_csv(STAGE4_CSV, stage4_rows, STAGE4_FIELDNAMES)
    write_jsonl(STAGE4_EVIDENCE, stage4_evidence)

    stage7_rows = read_csv(STAGE7_CSV)
    stage7_evidence = read_jsonl(STAGE7_EVIDENCE)
    new_stage7_rows, new_stage7_evidence = build_stage7_additions()
    stage7_rows, stage7_added, stage7_updated = upsert_by_key(
        stage7_rows,
        new_stage7_rows,
        "company_name",
    )
    stage7_evidence, stage7_evidence_added, stage7_evidence_updated = upsert_evidence(
        stage7_evidence,
        new_stage7_evidence,
    )
    stage7_rows = enrichment.enrich_relations_with_tier(stage7_rows, stage7_evidence)
    write_jsonl(STAGE7_EVIDENCE, stage7_evidence)
    write_csv(STAGE7_CSV, stage7_rows, STAGE7_FIELDNAMES)

    opportunities = enrichment.build_business_opportunities(
        stage7_rows,
        read_csv(STAGE6_COMPANY_PRODUCT),
    )
    write_csv(STAGE8_CSV, opportunities, STAGE8_FIELDNAMES)

    summary = {
        "stage4_relationships_total": len(stage4_rows),
        "stage4_relationships_added": stage4_added,
        "stage4_relationships_updated": stage4_updated,
        "stage4_evidence_total": len(stage4_evidence),
        "stage4_evidence_added": stage4_evidence_added,
        "stage4_evidence_updated": stage4_evidence_updated,
        "stage7_relations_total": len(stage7_rows),
        "stage7_relations_added": stage7_added,
        "stage7_relations_updated": stage7_updated,
        "stage7_evidence_total": len(stage7_evidence),
        "stage7_evidence_added": stage7_evidence_added,
        "stage7_evidence_updated": stage7_evidence_updated,
        "stage8_opportunities_total": len(opportunities),
    }
    write_manual_summary(summary)
    return summary


def write_manual_summary(summary: dict[str, int]) -> None:
    lines = [
        "# 人工核验增量增强摘要",
        "",
        f"- 生成时间：{NOW}",
        f"- Stage4 企业关系总数：{summary['stage4_relationships_total']}",
        f"- Stage4 本轮新增关系：{summary['stage4_relationships_added']}",
        f"- Stage4 证据总数：{summary['stage4_evidence_total']}",
        f"- Stage4 本轮新增证据：{summary['stage4_evidence_added']}",
        f"- Stage7 神州数码关系总数：{summary['stage7_relations_total']}",
        f"- Stage7 本轮新增公司关系：{summary['stage7_relations_added']}",
        f"- Stage7 证据总数：{summary['stage7_evidence_total']}",
        f"- Stage7 本轮新增证据：{summary['stage7_evidence_added']}",
        f"- Stage8 商机草稿总数：{summary['stage8_opportunities_total']}",
        "",
        "## 口径",
        "",
        "- 本脚本只追加人工核验过的公开资料线索。",
        "- 神州数码关系仍不等同于内部客户关系，所有商机均保留内部验证要求。",
        "- 未发现直接公开合作证据的公司继续保留 `potential_fit` 或 `needs_internal_validation`。",
    ]
    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    print(json.dumps(run(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
