from __future__ import annotations

import csv
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import stage2_company_leaders as s2


LEADERS_PATH = ROOT / "data" / "company_pool" / "company_leaders_stage_3.csv"
EVIDENCE_PATH = ROOT / "data" / "evidence" / "evidence_stage_4_relationships.jsonl"
RELATIONSHIPS_PATH = ROOT / "data" / "company_pool" / "company_relationships_stage_4.csv"
SUMMARY_PATH = ROOT / "data" / "company_pool" / "company_relationships_stage_4_summary.md"
NOW = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


DEFAULT_RELATIONSHIP_TERMS = (
    "customer",
    "customers",
    "supplier",
    "suppliers",
    "supply",
    "supplies",
    "supplied",
    "partnership",
    "partner",
    "agreement",
    "collaboration",
    "collaborate",
    "license",
    "licensing",
    "uses",
    "used",
    "adopts",
    "foundry",
    "manufacture",
    "manufacturing",
    "fab",
    "wafer",
    "packaging",
    "assembly",
    "test",
    "testing",
    "CoWoS",
    "HBM",
    "SiC",
    "substrate",
    "equipment",
    "lithography",
    "供应",
    "供应商",
    "客户",
    "采购",
    "合作",
    "伙伴",
    "协议",
    "授权",
    "采用",
    "导入",
    "认证",
    "代工",
    "制造",
    "晶圆",
    "封装",
    "测试",
    "产能",
    "光刻",
    "设备",
    "材料",
    "载板",
    "碳化硅",
)


BLOCKED_SOURCE_DOMAINS = (
    "facebook.com",
    "instagram.com",
    "reddit.com",
    "linkedin.com",
    "x.com",
    "twitter.com",
    "youtube.com",
    "youtu.be",
    "quora.com",
    "news.ycombinator.com",
    "bilibili.com",
    "zhihu.com",
    "medium.com",
    "substack.com",
    "wikipedia.org",
    "scribd.com",
    "alibaba.com",
    "moomoo.com",
    "quora.com",
    "semiconductorx.com",
    "semilens.vercel.app",
    "makesureiknowit.com",
    "thebuildout.ai",
    "applemagazine.com",
    "technetbooks.com",
    "saifu888.com",
    "huluic.cn",
    "hddun.com",
    "abachy.com",
    "wonderfulpcb.com",
    "smbom.com",
)


OFFICIAL_SOURCE_DOMAINS = (
    "sec.gov",
    "apple.com",
    "arm.com",
    "qualcomm.com",
    "investor.qualcomm.com",
    "mediatek.com",
    "synopsys.com",
    "cadence.com",
    "nvidia.com",
    "nvidianews.nvidia.com",
    "blogs.nvidia.com",
    "amd.com",
    "ir.amd.com",
    "tsmc.com",
    "pr.tsmc.com",
    "semiconductor.samsung.com",
    "samsung.com",
    "investors.gf.com",
    "asml.com",
    "newsroom.intel.com",
    "intel.com",
    "ir.appliedmaterials.com",
    "appliedmaterials.com",
    "investor.lamresearch.com",
    "lamresearch.com",
    "kla.com",
    "shinetsu.co.jp",
    "sumcosi.com",
    "amkor.com",
    "ir.amkor.com",
    "en.tfme.com",
    "qualcomm.com",
    "skhynix.com",
    "investors.micron.com",
    "micron.com",
    "wolfspeed.com",
    "coherent.com",
    "shinko.co.jp",
    "ibiden.com",
)


HIGH_QUALITY_MEDIA_DOMAINS = (
    "reuters.com",
    "bloomberg.com",
    "asia.nikkei.com",
    "digitimes.com",
    "trendforce.com",
    "cnbc.com",
    "wsj.com",
    "eetimes.com",
    "businesswire.com",
    "prnewswire.com",
)


ALIASES: dict[str, tuple[str, ...]] = {
    "华大九天": ("华大九天", "Empyrean"),
    "广立微": ("广立微", "Semitronix"),
    "概伦电子": ("概伦电子", "Primarius"),
    "Cadence": ("Cadence", "楷登"),
    "Siemens EDA": ("Siemens EDA", "Mentor Graphics"),
    "Synopsys": ("Synopsys", "新思"),
    "芯原股份": ("芯原股份", "芯原", "VeriSilicon"),
    "Alphawave": ("Alphawave", "Alphawave Semi"),
    "Arm": ("Arm", "ARM"),
    "Rambus": ("Rambus",),
    "寒武纪": ("寒武纪", "Cambricon"),
    "海光信息": ("海光信息", "Hygon"),
    "海思": ("海思", "HiSilicon", "Huawei HiSilicon"),
    "澜起科技": ("澜起科技", "Montage"),
    "AMD": ("AMD",),
    "Broadcom": ("Broadcom", "博通"),
    "Marvell": ("Marvell", "迈威尔"),
    "NVIDIA": ("NVIDIA", "英伟达"),
    "MediaTek": ("MediaTek", "联发科"),
    "卓胜微": ("卓胜微", "Maxscend"),
    "紫光展锐": ("紫光展锐", "UNISOC"),
    "Apple": ("Apple", "苹果"),
    "Qualcomm": ("Qualcomm", "高通"),
    "兆易创新": ("兆易创新", "GigaDevice"),
    "韦尔股份": ("韦尔股份", "韦尔", "OmniVision"),
    "Analog Devices": ("Analog Devices", "ADI", "亚德诺"),
    "NXP": ("NXP", "恩智浦"),
    "Texas Instruments": ("Texas Instruments", "TI", "德州仪器"),
    "TSMC": ("TSMC", "台积电", "Taiwan Semiconductor"),
    "UMC": ("UMC", "联电", "United Microelectronics"),
    "中芯国际": ("中芯国际", "SMIC"),
    "华虹半导体": ("华虹半导体", "华虹", "Hua Hong"),
    "GlobalFoundries": ("GlobalFoundries", "GF"),
    "Samsung": ("Samsung", "三星"),
    "华润微": ("华润微", "CR Micro"),
    "Intel": ("Intel", "英特尔"),
    "Infineon": ("Infineon", "英飞凌"),
    "ASML": ("ASML", "阿斯麦"),
    "Applied Materials": ("Applied Materials", "AMAT", "应用材料"),
    "Lam Research": ("Lam Research", "泛林"),
    "Tokyo Electron": ("Tokyo Electron", "TEL", "东京电子"),
    "KLA": ("KLA", "科磊"),
    "Shin-Etsu": ("Shin-Etsu", "信越"),
    "SUMCO": ("SUMCO",),
    "GlobalWafers": ("GlobalWafers", "环球晶"),
    "Entegris": ("Entegris",),
    "JSR": ("JSR",),
    "TOK": ("TOK", "Tokyo Ohka"),
    "Ibiden": ("Ibiden",),
    "Shinko Electric": ("Shinko Electric", "Shinko"),
    "Unimicron": ("Unimicron", "欣兴"),
    "Nan Ya PCB": ("Nan Ya PCB", "南亚电路板"),
    "ASE": ("ASE", "日月光"),
    "Amkor": ("Amkor",),
    "通富微电": ("通富微电", "Tongfu Microelectronics", "TFME"),
    "长电科技": ("长电科技", "JCET"),
    "SK hynix": ("SK hynix", "SK海力士", "海力士"),
    "Micron": ("Micron", "美光"),
    "STMicroelectronics": ("STMicroelectronics", "STMicro", "意法半导体"),
    "ROHM": ("ROHM", "罗姆"),
    "Wolfspeed": ("Wolfspeed",),
    "Coherent": ("Coherent",),
    "onsemi": ("onsemi", "安森美"),
    "斯达半导": ("斯达半导", "StarPower"),
    "Tesla": ("Tesla", "特斯拉"),
    "Denso": ("Denso", "电装"),
    "比亚迪": ("比亚迪", "BYD"),
    "华为": ("华为", "Huawei"),
    "Google": ("Google",),
    "Dell": ("Dell",),
    "Microsoft": ("Microsoft",),
    "Meta": ("Meta",),
}


@dataclass(frozen=True)
class RelationshipSpec:
    relationship_id: str
    source_company: str
    source_subsegment: str
    target_company: str
    target_subsegment: str
    relationship_type: str
    relationship_claim: str
    queries: tuple[str, ...]
    relationship_terms: tuple[str, ...] = DEFAULT_RELATIONSHIP_TERMS


def r(
    relationship_id: str,
    source_company: str,
    source_subsegment: str,
    target_company: str,
    target_subsegment: str,
    relationship_type: str,
    relationship_claim: str,
    queries: tuple[str, ...],
    relationship_terms: tuple[str, ...] = DEFAULT_RELATIONSHIP_TERMS,
) -> RelationshipSpec:
    return RelationshipSpec(
        relationship_id=relationship_id,
        source_company=source_company,
        source_subsegment=source_subsegment,
        target_company=target_company,
        target_subsegment=target_subsegment,
        relationship_type=relationship_type,
        relationship_claim=relationship_claim,
        queries=queries,
        relationship_terms=relationship_terms,
    )


RELATIONSHIP_SPECS: tuple[RelationshipSpec, ...] = (
    r(
        "R4-001",
        "Arm",
        "半导体IP/芯片定制",
        "Apple",
        "手机SoC/通信基带",
        "IP授权",
        "Arm 向 Apple 提供处理器架构/IP授权，支撑 Apple 自研 SoC 生态。",
        (
            "Apple Arm architecture license agreement chips official",
            "Apple Arm IP license custom silicon relationship",
            "site:sec.gov/Archives/edgar/data/1973239 Apple Arm agreement extends beyond 2040",
        ),
    ),
    r(
        "R4-002",
        "Arm",
        "半导体IP/芯片定制",
        "Qualcomm",
        "手机SoC/通信基带",
        "IP授权",
        "Arm 向 Qualcomm 提供处理器架构/IP授权，支撑移动 SoC 产品。",
        (
            "Qualcomm Arm architecture license agreement Snapdragon official",
            "Qualcomm Arm IP license semiconductor relationship",
        ),
    ),
    r(
        "R4-003",
        "Arm",
        "半导体IP/芯片定制",
        "MediaTek",
        "手机SoC/通信基带",
        "IP授权",
        "Arm 向 MediaTek 提供处理器架构/IP授权，支撑移动 SoC 产品。",
        (
            "MediaTek Arm IP license smartphone SoC relationship",
            "MediaTek Arm architecture license chips official",
        ),
    ),
    r(
        "R4-004",
        "Synopsys",
        "EDA软件",
        "NVIDIA",
        "AI/GPU/CPU算力芯片",
        "EDA/IP供应",
        "Synopsys 的 EDA/IP 工具链服务于 NVIDIA 等高性能芯片设计客户或合作生态。",
        (
            "Synopsys NVIDIA EDA IP chip design collaboration official",
            "NVIDIA Synopsys EDA tools AI chip design",
        ),
    ),
    r(
        "R4-005",
        "Cadence",
        "EDA软件",
        "NVIDIA",
        "AI/GPU/CPU算力芯片",
        "EDA/IP供应",
        "Cadence 的 EDA/系统设计工具链服务于 NVIDIA 等高性能芯片设计客户或合作生态。",
        (
            "Cadence NVIDIA EDA chip design collaboration official",
            "NVIDIA Cadence EDA tools semiconductor design",
        ),
    ),
    r(
        "R4-006",
        "TSMC",
        "晶圆代工/Foundry",
        "NVIDIA",
        "AI/GPU/CPU算力芯片",
        "晶圆代工",
        "TSMC 为 NVIDIA 高端 GPU/AI 芯片提供晶圆制造或先进制程代工能力。",
        (
            "NVIDIA TSMC foundry manufactures GPUs official",
            "NVIDIA TSMC wafer foundry AI GPU relationship",
            "site:nvidianews.nvidia.com TSMC NVIDIA manufacturing GPU",
        ),
    ),
    r(
        "R4-007",
        "TSMC",
        "晶圆代工/Foundry",
        "AMD",
        "AI/GPU/CPU算力芯片",
        "晶圆代工",
        "TSMC 为 AMD CPU/GPU/AI 芯片提供晶圆制造或先进制程代工能力。",
        (
            "AMD TSMC foundry wafer manufacturing official annual report",
            "AMD TSMC manufactures CPUs GPUs foundry relationship",
            "site:ir.amd.com TSMC foundry AMD annual report",
        ),
    ),
    r(
        "R4-008",
        "TSMC",
        "晶圆代工/Foundry",
        "Apple",
        "手机SoC/通信基带",
        "晶圆代工",
        "TSMC 为 Apple 自研 SoC 提供晶圆制造或先进制程代工能力。",
        (
            "Apple TSMC foundry manufactures A-series chips official",
            "Apple TSMC wafer manufacturing SoC relationship",
            "site:apple.com newsroom TSMC Apple silicon produced",
        ),
    ),
    r(
        "R4-009",
        "TSMC",
        "晶圆代工/Foundry",
        "Qualcomm",
        "手机SoC/通信基带",
        "晶圆代工",
        "TSMC 为 Qualcomm 移动 SoC 提供晶圆制造或先进制程代工能力。",
        (
            "Qualcomm TSMC foundry Snapdragon wafer manufacturing relationship",
            "Qualcomm TSMC manufactures chips official",
            "site:pr.tsmc.com Qualcomm TSMC Snapdragon",
        ),
    ),
    r(
        "R4-010",
        "TSMC",
        "晶圆代工/Foundry",
        "MediaTek",
        "手机SoC/通信基带",
        "晶圆代工",
        "TSMC 为 MediaTek 移动 SoC 提供晶圆制造或先进制程代工能力。",
        (
            "MediaTek TSMC foundry smartphone SoC wafer manufacturing",
            "MediaTek TSMC manufactures chips official",
        ),
    ),
    r(
        "R4-011",
        "Samsung",
        "晶圆代工/Foundry",
        "Qualcomm",
        "手机SoC/通信基带",
        "晶圆代工",
        "Samsung Foundry 为 Qualcomm 部分 Snapdragon 产品提供晶圆代工能力。",
        (
            "Samsung Foundry Qualcomm Snapdragon manufacturing relationship official",
            "Qualcomm Samsung foundry Snapdragon chips",
            "site:semiconductor.samsung.com Qualcomm Samsung Foundry Snapdragon",
        ),
    ),
    r(
        "R4-012",
        "GlobalFoundries",
        "晶圆代工/Foundry",
        "AMD",
        "AI/GPU/CPU算力芯片",
        "晶圆代工",
        "GlobalFoundries 与 AMD 存在晶圆供应/制造协议关系。",
        (
            "GlobalFoundries AMD wafer supply agreement official",
            "AMD GlobalFoundries wafer supply relationship annual report",
        ),
    ),
    r(
        "R4-013",
        "中芯国际",
        "晶圆代工/Foundry",
        "海思",
        "手机SoC/通信基带",
        "晶圆代工",
        "中芯国际与海思/华为芯片存在晶圆代工关系线索。",
        (
            "中芯国际 海思 华为 麒麟 芯片 代工 公开 证据",
            "SMIC HiSilicon Huawei chip foundry relationship",
        ),
    ),
    r(
        "R4-014",
        "ASML",
        "光刻设备",
        "TSMC",
        "晶圆代工/Foundry",
        "设备供应",
        "ASML 向 TSMC 等先进制程晶圆厂供应光刻设备。",
        (
            "ASML TSMC customer lithography systems annual report",
            "ASML TSMC EUV lithography equipment supplier relationship",
            "site:pr.tsmc.com ASML TSMC supplier award",
        ),
    ),
    r(
        "R4-015",
        "ASML",
        "光刻设备",
        "Samsung",
        "晶圆代工/Foundry",
        "设备供应",
        "ASML 向 Samsung Foundry/半导体制造业务供应光刻设备。",
        (
            "ASML Samsung customer EUV lithography systems official",
            "ASML Samsung lithography equipment supplier relationship",
        ),
    ),
    r(
        "R4-016",
        "ASML",
        "光刻设备",
        "Intel",
        "IDM/特色工艺制造",
        "设备供应",
        "ASML 向 Intel 先进制造业务供应光刻设备。",
        (
            "ASML Intel customer EUV lithography systems official",
            "Intel ASML High NA EUV lithography equipment relationship",
        ),
    ),
    r(
        "R4-017",
        "Applied Materials",
        "薄膜沉积设备",
        "TSMC",
        "晶圆代工/Foundry",
        "设备供应",
        "Applied Materials 的材料工程/沉积等设备进入 TSMC 等晶圆制造生态。",
        (
            "Applied Materials TSMC supplier equipment relationship official",
            "Applied Materials TSMC semiconductor equipment customer",
            "site:pr.tsmc.com Applied Materials TSMC supplier award",
        ),
    ),
    r(
        "R4-018",
        "Lam Research",
        "刻蚀设备",
        "Samsung",
        "晶圆代工/Foundry",
        "设备供应",
        "Lam Research 的刻蚀/沉积相关设备进入 Samsung 半导体制造生态。",
        (
            "Lam Research Samsung semiconductor equipment supplier relationship",
            "Lam Research Samsung customer etch deposition equipment official",
            "site:investor.lamresearch.com Samsung Lam Research customer supplier",
        ),
    ),
    r(
        "R4-019",
        "KLA",
        "量测检测设备",
        "TSMC",
        "晶圆代工/Foundry",
        "设备供应",
        "KLA 的过程控制/量测检测设备进入 TSMC 等先进晶圆制造生态。",
        (
            "KLA TSMC process control equipment supplier relationship",
            "KLA TSMC customer semiconductor inspection metrology official",
            "site:pr.tsmc.com KLA TSMC supplier award",
            "site:kla.com TSMC KLA process control",
        ),
    ),
    r(
        "R4-020",
        "Tokyo Electron",
        "薄膜沉积设备",
        "TSMC",
        "晶圆代工/Foundry",
        "设备供应",
        "Tokyo Electron 的涂胶显影、沉积或热处理设备进入 TSMC 等晶圆制造生态。",
        (
            "Tokyo Electron TSMC semiconductor equipment supplier relationship",
            "TEL TSMC customer semiconductor equipment official",
        ),
    ),
    r(
        "R4-021",
        "Shin-Etsu",
        "硅片",
        "TSMC",
        "晶圆代工/Foundry",
        "材料供应",
        "Shin-Etsu 向 TSMC 等晶圆制造厂供应半导体硅片/材料。",
        (
            "Shin-Etsu TSMC silicon wafer supplier relationship",
            "Shin-Etsu TSMC semiconductor materials customer",
            "site:shinetsu.co.jp TSMC Excellent Performance Award Shin-Etsu",
        ),
    ),
    r(
        "R4-022",
        "SUMCO",
        "硅片",
        "TSMC",
        "晶圆代工/Foundry",
        "材料供应",
        "SUMCO 向 TSMC 等晶圆制造厂供应半导体硅片。",
        (
            "SUMCO TSMC silicon wafer supplier relationship",
            "SUMCO TSMC semiconductor wafer customer official",
            "site:sumcosi.com TSMC SUMCO silicon wafer supplier",
        ),
    ),
    r(
        "R4-023",
        "TSMC",
        "2.5D/3D/Chiplet先进封装",
        "NVIDIA",
        "AI/GPU/CPU算力芯片",
        "先进封装",
        "TSMC CoWoS/先进封装产能服务于 NVIDIA AI GPU。",
        (
            "NVIDIA TSMC CoWoS advanced packaging supplier official",
            "NVIDIA TSMC CoWoS packaging relationship AI GPU",
        ),
    ),
    r(
        "R4-024",
        "TSMC",
        "2.5D/3D/Chiplet先进封装",
        "AMD",
        "AI/GPU/CPU算力芯片",
        "先进封装",
        "TSMC 先进封装/CoWoS 产能服务于 AMD 高性能芯片。",
        (
            "AMD TSMC CoWoS advanced packaging relationship",
            "AMD TSMC advanced packaging supplier official",
            "site:ir.amd.com TSMC CoWoS AMD advanced packaging",
        ),
    ),
    r(
        "R4-025",
        "TSMC",
        "2.5D/3D/Chiplet先进封装",
        "Broadcom",
        "AI/GPU/CPU算力芯片",
        "先进封装",
        "TSMC 先进封装/CoWoS 产能服务于 Broadcom 定制 AI ASIC 等产品。",
        (
            "Broadcom TSMC CoWoS advanced packaging relationship",
            "Broadcom TSMC advanced packaging AI ASIC supplier",
            "site:pr.tsmc.com Broadcom TSMC CoWoS advanced packaging",
        ),
    ),
    r(
        "R4-026",
        "通富微电",
        "2.5D/3D/Chiplet先进封装",
        "AMD",
        "AI/GPU/CPU算力芯片",
        "封装测试",
        "通富微电与 AMD 在封装测试/合资公司方面存在明确合作关系。",
        (
            "通富微电 AMD 合资 封装 测试 合作 官方",
            "Tongfu Microelectronics AMD joint venture assembly test relationship",
        ),
    ),
    r(
        "R4-027",
        "长电科技",
        "传统OSAT封装测试",
        "Qualcomm",
        "手机SoC/通信基带",
        "封装测试",
        "长电科技与 Qualcomm 在封装测试或供应链方面存在客户/合作关系线索。",
        (
            "长电科技 高通 Qualcomm 封装 测试 客户 合作",
            "JCET Qualcomm semiconductor packaging test relationship",
        ),
    ),
    r(
        "R4-028",
        "ASE",
        "传统OSAT封装测试",
        "Qualcomm",
        "手机SoC/通信基带",
        "封装测试",
        "ASE 向 Qualcomm 等移动芯片客户提供封装测试服务。",
        (
            "ASE Qualcomm packaging test supplier relationship",
            "Qualcomm ASE semiconductor assembly test supplier",
        ),
    ),
    r(
        "R4-029",
        "Amkor",
        "2.5D/3D/Chiplet先进封装",
        "Apple",
        "手机SoC/通信基带",
        "封装测试",
        "Amkor 向 Apple 等客户提供先进封装/封测能力。",
        (
            "Amkor Apple advanced packaging supplier relationship",
            "Apple Amkor semiconductor packaging test supplier",
            "site:apple.com/newsroom Amkor Apple first largest customer silicon packaging",
            "site:ir.amkor.com Apple Amkor advanced packaging customer",
        ),
    ),
    r(
        "R4-030",
        "SK hynix",
        "DRAM/HBM",
        "NVIDIA",
        "AI/GPU/CPU算力芯片",
        "HBM供应",
        "SK hynix 向 NVIDIA AI GPU 生态供应 HBM 存储。",
        (
            "SK hynix NVIDIA HBM supplier official",
            "NVIDIA SK hynix HBM memory supply relationship",
        ),
    ),
    r(
        "R4-031",
        "Micron",
        "DRAM/HBM",
        "NVIDIA",
        "AI/GPU/CPU算力芯片",
        "HBM供应",
        "Micron 向 NVIDIA AI GPU 生态供应或导入 HBM 存储。",
        (
            "Micron NVIDIA HBM3E supplier official",
            "NVIDIA Micron HBM memory supply relationship",
        ),
    ),
    r(
        "R4-032",
        "Samsung",
        "DRAM/HBM",
        "NVIDIA",
        "AI/GPU/CPU算力芯片",
        "HBM供应",
        "Samsung 向 NVIDIA AI GPU 生态供应或认证 HBM 存储。",
        (
            "Samsung NVIDIA HBM supplier qualification official",
            "NVIDIA Samsung HBM memory supply relationship",
        ),
    ),
    r(
        "R4-033",
        "SK hynix",
        "DRAM/HBM",
        "AMD",
        "AI/GPU/CPU算力芯片",
        "HBM供应",
        "SK hynix 向 AMD 高性能 GPU/AI 芯片生态供应 HBM 存储。",
        (
            "SK hynix AMD HBM supplier relationship",
            "AMD SK hynix HBM memory supply official",
            "site:news.skhynix.com AMD HBM jointly developed",
            "site:trendforce.com AMD SK hynix HBM3 supplied",
        ),
    ),
    r(
        "R4-034",
        "Micron",
        "DRAM/HBM",
        "AMD",
        "AI/GPU/CPU算力芯片",
        "HBM供应",
        "Micron 向 AMD 高性能 GPU/AI 芯片生态供应 HBM 存储。",
        (
            "Micron AMD HBM supplier relationship",
            "AMD Micron HBM memory supply official",
        ),
    ),
    r(
        "R4-035",
        "STMicroelectronics",
        "SiC功率器件/模块",
        "Tesla",
        "新能源汽车/汽车电子",
        "功率器件供应",
        "STMicroelectronics 向 Tesla 新能源汽车供应 SiC/功率器件。",
        (
            "STMicroelectronics Tesla SiC supplier relationship official",
            "Tesla STMicroelectronics silicon carbide power semiconductor supplier",
        ),
    ),
    r(
        "R4-036",
        "Infineon",
        "功率器件/模块",
        "Tesla",
        "新能源汽车/汽车电子",
        "功率器件供应",
        "Infineon 向 Tesla 或新能源汽车电子生态供应功率半导体。",
        (
            "Infineon Tesla power semiconductor supplier relationship",
            "Tesla Infineon SiC power module supplier",
            "Infineon Tesla Model 3 supply Reuters",
            "Infineon supplying power chips to Tesla EE Times",
        ),
    ),
    r(
        "R4-037",
        "ROHM",
        "SiC功率器件/模块",
        "Denso",
        "新能源汽车/汽车电子",
        "功率器件供应/合作",
        "ROHM 与 Denso 在 SiC/功率器件方面存在供应或合作关系。",
        (
            "ROHM Denso SiC power semiconductor partnership official",
            "Denso ROHM silicon carbide power module relationship",
        ),
    ),
    r(
        "R4-038",
        "Wolfspeed",
        "SiC衬底/外延",
        "Infineon",
        "SiC功率器件/模块",
        "SiC材料供应",
        "Wolfspeed 向 Infineon 等功率半导体厂商供应 SiC 衬底/材料。",
        (
            "Wolfspeed Infineon SiC wafer supply agreement official",
            "Infineon Wolfspeed silicon carbide wafer supplier relationship",
        ),
    ),
    r(
        "R4-039",
        "Coherent",
        "SiC衬底/外延",
        "Infineon",
        "SiC功率器件/模块",
        "SiC材料供应",
        "Coherent 向 Infineon 等功率半导体厂商供应 SiC 衬底/材料。",
        (
            "Coherent Infineon SiC wafer supply agreement official",
            "Infineon Coherent silicon carbide wafer supplier relationship",
        ),
    ),
    r(
        "R4-040",
        "onsemi",
        "SiC功率器件/模块",
        "Tesla",
        "新能源汽车/汽车电子",
        "功率器件供应",
        "onsemi 向 Tesla 或新能源汽车电子生态供应 SiC/功率器件。",
        (
            "onsemi Tesla SiC power semiconductor supplier relationship",
            "Tesla onsemi silicon carbide supplier official",
            "onsemi Tesla silicon carbide supplier Reuters",
        ),
    ),
    r(
        "R4-041",
        "斯达半导",
        "功率器件/模块",
        "比亚迪",
        "新能源汽车/汽车电子",
        "功率器件供应",
        "斯达半导向比亚迪等新能源车客户供应 IGBT/功率模块线索。",
        (
            "斯达半导 比亚迪 IGBT 功率模块 供应商 客户",
            "StarPower BYD IGBT power module supplier relationship",
        ),
    ),
    r(
        "R4-042",
        "Ibiden",
        "封装材料/IC载板",
        "Intel",
        "2.5D/3D/Chiplet先进封装",
        "封装载板供应",
        "Ibiden 向 Intel 等高端封装/处理器客户供应 IC 载板。",
        (
            "Ibiden Intel IC substrate supplier relationship",
            "Intel Ibiden ABF substrate supplier official",
            "site:ibiden.com Intel IC package substrate customer",
        ),
    ),
    r(
        "R4-043",
        "Shinko Electric",
        "封装材料/IC载板",
        "Intel",
        "2.5D/3D/Chiplet先进封装",
        "封装载板供应",
        "Shinko Electric 向 Intel 等高端封装/处理器客户供应 IC 载板。",
        (
            "Shinko Electric Intel IC substrate supplier relationship",
            "Intel Shinko ABF substrate supplier",
        ),
    ),
    r(
        "R4-044",
        "Unimicron",
        "封装材料/IC载板",
        "NVIDIA",
        "AI/GPU/CPU算力芯片",
        "封装载板供应",
        "Unimicron 向 NVIDIA AI 芯片生态供应高端 IC 载板线索。",
        (
            "Unimicron NVIDIA IC substrate supplier relationship",
            "NVIDIA Unimicron ABF substrate supplier",
        ),
    ),
    r(
        "R4-045",
        "Ibiden",
        "封装材料/IC载板",
        "NVIDIA",
        "AI/GPU/CPU算力芯片",
        "封装载板供应",
        "Ibiden 向 NVIDIA AI 芯片生态供应高端 IC 载板线索。",
        (
            "Ibiden NVIDIA IC substrate supplier relationship",
            "NVIDIA Ibiden ABF substrate supplier",
        ),
    ),
)


def ensure_dirs() -> None:
    RELATIONSHIPS_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_leader_index() -> dict[tuple[str, str], dict[str, str]]:
    if not LEADERS_PATH.exists():
        raise FileNotFoundError(f"missing Stage 3 leaders file: {LEADERS_PATH}")
    index: dict[tuple[str, str], dict[str, str]] = {}
    with LEADERS_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            segment = "/".join(
                [
                    row["value_chain_layer"],
                    row["major_segment"],
                    row["subsegment_name"],
                ]
            )
            row = dict(row)
            row["segment"] = segment
            index[(row["company_name"], row["subsegment_name"])] = row
    return index


def validate_specs(index: dict[tuple[str, str], dict[str, str]]) -> None:
    missing: list[str] = []
    for spec in RELATIONSHIP_SPECS:
        if (spec.source_company, spec.source_subsegment) not in index:
            missing.append(f"{spec.relationship_id}: source {spec.source_company}/{spec.source_subsegment}")
        if (spec.target_company, spec.target_subsegment) not in index:
            missing.append(f"{spec.relationship_id}: target {spec.target_company}/{spec.target_subsegment}")
    if missing:
        raise ValueError("relationship specs do not match Stage 3 rows:\n" + "\n".join(missing))


def aliases_for(company: str) -> tuple[str, ...]:
    return ALIASES.get(company, (company,))


def contains_company(text: str, company: str) -> bool:
    return any(s2.alias_matches(text, alias) for alias in aliases_for(company))


def matched_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    hits: list[str] = []
    for term in terms:
        if s2.alias_matches(text, term) if re.search(r"[A-Za-z0-9]", term) else term in text:
            hits.append(term)
    return hits


def pick_search_tool(query: str) -> str:
    return "Bocha" if re.search(r"[\u4e00-\u9fff]", query) else "Tavily"


def search(query: str, count: int = 5) -> list[dict[str, Any]]:
    tool = pick_search_tool(query)
    if tool == "Bocha":
        return s2.search_bocha(query, count=count)
    return s2.search_tavily(query, count=count)


def source_type_for(url: str, title: str) -> str:
    text = f"{url} {title}".lower()
    if any(token in text for token in ["annual", "10-k", "sec.gov", "cninfo", "investor", "ir."]):
        return "official_disclosure"
    if any(token in text for token in ["press", "newsroom", "prnewswire", "globenewswire"]):
        return "company_or_wire_release"
    if any(token in text for token in ["trendforce", "counterpoint", "semi.org", "semianalysis"]):
        return "industry_report"
    return "industry_search"


def source_domain(url: str) -> str:
    match = re.match(r"^[a-z]+://([^/]+)", url.lower())
    if not match:
        return ""
    return match.group(1).removeprefix("www.")


def is_blocked_source(url: str) -> bool:
    domain = source_domain(url)
    return any(domain == blocked or domain.endswith(f".{blocked}") for blocked in BLOCKED_SOURCE_DOMAINS)


def source_grade(url: str, title: str) -> str:
    domain = source_domain(url)
    if any(domain == official or domain.endswith(f".{official}") for official in OFFICIAL_SOURCE_DOMAINS):
        return "A"
    if any(domain == media or domain.endswith(f".{media}") for media in HIGH_QUALITY_MEDIA_DOMAINS):
        return "A-"
    return s2.source_grade(url, title)


def is_direct_relationship_hit(spec: RelationshipSpec, row: dict[str, Any]) -> tuple[bool, list[str]]:
    text = " ".join([row.get("title", ""), row.get("snippet", ""), row.get("url", "")])
    if not contains_company(text, spec.source_company):
        return False, []
    if not contains_company(text, spec.target_company):
        return False, []
    terms = matched_terms(text, spec.relationship_terms)
    return bool(terms), terms


def run_searches(index: dict[tuple[str, str], dict[str, str]]) -> list[dict[str, Any]]:
    evidence_rows: list[dict[str, Any]] = []
    evidence_id = 1
    seen: set[tuple[str, str, str]] = set()

    for spec in RELATIONSHIP_SPECS:
        source_segment = index[(spec.source_company, spec.source_subsegment)]["segment"]
        target_segment = index[(spec.target_company, spec.target_subsegment)]["segment"]
        for query in spec.queries:
            try:
                result_rows = search(query, count=5)
            except Exception as exc:
                result_rows = [
                    {
                        "search_tool": pick_search_tool(query),
                        "query": query,
                        "title": f"ERROR: {type(exc).__name__}",
                        "url": "",
                        "snippet": str(exc),
                        "publish_date": "",
                    }
                ]
            time.sleep(0.2)

            for row in result_rows:
                if is_blocked_source(row.get("url", "")):
                    continue
                is_hit, terms = is_direct_relationship_hit(spec, row)
                if not is_hit:
                    continue
                dedupe_key = (spec.relationship_id, row.get("url", ""), row.get("title", ""))
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)

                ev_id = f"E4-{evidence_id:03d}"
                evidence_id += 1
                url = row.get("url", "")
                title = row.get("title", "")
                evidence_rows.append(
                    {
                        "evidence_id": ev_id,
                        "task_id": "S4-company-relationships",
                        "relationship_id": spec.relationship_id,
                        "question": f"{spec.source_company} 与 {spec.target_company} 在半导体产业链中的硬关系是什么？",
                        "source_company": spec.source_company,
                        "source_segment": source_segment,
                        "target_company": spec.target_company,
                        "target_segment": target_segment,
                        "relationship_type": spec.relationship_type,
                        "relationship_direction": f"{spec.source_company} -> {spec.target_company}",
                        "relationship_claim": spec.relationship_claim,
                        "source_title": title,
                        "source_url_or_file": url,
                        "source_type": source_type_for(url, title),
                        "publish_date": row.get("publish_date", ""),
                        "entities": [spec.source_company, spec.target_company],
                        "evidence_excerpt": (row.get("snippet", "") or "")[:1200],
                        "possible_claim": spec.relationship_claim,
                        "claim_type_guess": "company_relationship_direct",
                        "confidence": "medium",
                        "limitations": "搜索摘要层证据；正式入图前建议回到公司公告、年报、IR或可信行业报告核验原文。",
                        "retrieved_at": NOW,
                        "source_grade": source_grade(url, title),
                        "search_tool": row.get("search_tool", pick_search_tool(query)),
                        "query": query,
                        "matched_terms": terms,
                    }
                )
    return evidence_rows


def evidence_confidence(evidence_ids: list[str], evidence_by_id: dict[str, dict[str, Any]]) -> str:
    grade_rank = {"A": 4, "A-": 3, "B": 2, "B-": 1}
    best = max((grade_rank.get(evidence_by_id[eid].get("source_grade", "B-"), 1) for eid in evidence_ids), default=1)
    if best >= 3:
        return "high"
    if len(evidence_ids) >= 2 or best == 2:
        return "medium"
    return "medium-low"


def build_relationship_rows(evidence_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    evidence_by_id = {row["evidence_id"]: row for row in evidence_rows}
    grouped: dict[str, list[str]] = {}
    for row in evidence_rows:
        grouped.setdefault(row["relationship_id"], []).append(row["evidence_id"])

    spec_by_id = {spec.relationship_id: spec for spec in RELATIONSHIP_SPECS}
    rows: list[dict[str, str]] = []
    for relationship_id in sorted(grouped):
        spec = spec_by_id[relationship_id]
        evidence_ids = sorted(set(grouped[relationship_id]))
        first = evidence_by_id[evidence_ids[0]]
        urls: list[str] = []
        for eid in evidence_ids:
            url = evidence_by_id[eid].get("source_url_or_file", "")
            if url and url not in urls:
                urls.append(url)
        rows.append(
            {
                "relationship_id": spec.relationship_id,
                "source_company": spec.source_company,
                "source_segment": first["source_segment"],
                "target_company": spec.target_company,
                "target_segment": first["target_segment"],
                "relationship_type": spec.relationship_type,
                "relationship_direction": first["relationship_direction"],
                "relationship_claim": spec.relationship_claim,
                "evidence_ids": ";".join(evidence_ids),
                "source_urls": " | ".join(urls[:6]),
                "confidence": evidence_confidence(evidence_ids, evidence_by_id),
                "limitations": "仅保留搜索结果中直接点名双方公司的供应链硬关系；未命中公开直接证据的候选关系不入表。",
            }
        )
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
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
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path: Path, rows: list[dict[str, str]], evidence_rows: list[dict[str, Any]]) -> None:
    type_counts: dict[str, int] = {}
    confidence_counts: dict[str, int] = {}
    for row in rows:
        type_counts[row["relationship_type"]] = type_counts.get(row["relationship_type"], 0) + 1
        confidence_counts[row["confidence"]] = confidence_counts.get(row["confidence"], 0) + 1

    lines = [
        "# Stage 4 半导体公司关系表",
        "",
        f"- 生成时间：{NOW}",
        f"- 候选关系规格：{len(RELATIONSHIP_SPECS)} 条",
        f"- 直接证据：{len(evidence_rows)} 条",
        f"- 入表关系：{len(rows)} 条",
        "- 口径：只保留搜索结果中直接点名双方公司的供应链硬关系；未命中直接证据的候选关系不入表。",
        "- 环节：严格沿用 Stage 3 的公司-子环节匹配，不扩展新环节。",
        "",
        "## 关系类型分布",
        "",
    ]
    for name, count in sorted(type_counts.items()):
        lines.append(f"- {name}：{count}")
    lines.extend(["", "## 置信度分布", ""])
    for name, count in sorted(confidence_counts.items()):
        lines.append(f"- {name}：{count}")
    lines.extend(
        [
            "",
            "## 关系明细",
            "",
            "| 上游/服务方 | 上游/服务方环节 | 关系 | 下游/客户方 | 下游/客户方环节 | 置信度 | 判断依据 |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row["source_company"],
                    row["source_segment"],
                    row["relationship_type"],
                    row["target_company"],
                    row["target_segment"],
                    row["confidence"],
                    row["relationship_claim"],
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_existing_evidence() -> list[dict[str, Any]]:
    if not EVIDENCE_PATH.exists():
        raise FileNotFoundError(f"missing evidence file: {EVIDENCE_PATH}")
    return [
        json.loads(line)
        for line in EVIDENCE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> None:
    ensure_dirs()
    leader_index = load_leader_index()
    validate_specs(leader_index)
    if "--from-existing-evidence" in sys.argv:
        evidence_rows = load_existing_evidence()
    else:
        evidence_rows = run_searches(leader_index)
        write_jsonl(EVIDENCE_PATH, evidence_rows)
    relationship_rows = build_relationship_rows(evidence_rows)
    write_csv(RELATIONSHIPS_PATH, relationship_rows)
    write_summary(SUMMARY_PATH, relationship_rows, evidence_rows)
    print(
        json.dumps(
            {
                "relationship_specs": len(RELATIONSHIP_SPECS),
                "evidence": len(evidence_rows),
                "relationship_rows": len(relationship_rows),
                "evidence_path": str(EVIDENCE_PATH),
                "relationships_path": str(RELATIONSHIPS_PATH),
                "summary_path": str(SUMMARY_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
