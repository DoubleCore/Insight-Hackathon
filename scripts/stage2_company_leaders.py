from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[1]
SECRET_REF = ROOT / "AI 工具密钥.md"
SEGMENTS_PATH = ROOT / "data" / "graph" / "segment_candidates.csv"
OUTPUT_DIR = ROOT / "data" / "company_pool"
EVIDENCE_PATH = ROOT / "data" / "evidence" / "evidence_stage_2.jsonl"
COMPANY_POOL_PATH = OUTPUT_DIR / "company_candidates_stage_2.csv"
SUMMARY_PATH = OUTPUT_DIR / "company_candidates_stage_2_summary.md"
NOW = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


@dataclass(frozen=True)
class SegmentSearchSpec:
    segment: str
    domestic_queries: list[str]
    global_queries: list[str]
    company_keywords: dict[str, list[str]]
    company_regions: dict[str, str]


SEGMENT_SPECS: list[SegmentSearchSpec] = [
    SegmentSearchSpec(
        "EDA/IP",
        [
            "中国 EDA 龙头 企业 华大九天 概伦电子 广立微 芯原 2026",
            "中国 半导体 IP 龙头 芯原股份 芯动科技 芯和半导体 EDA 2026",
        ],
        [
            "global EDA leaders Synopsys Cadence Siemens EDA market share 2026",
            "global semiconductor IP core leaders Arm Synopsys Cadence VeriSilicon Alphawave 2026",
        ],
        {
            "华大九天": ["华大九天", "Empyrean"],
            "概伦电子": ["概伦电子", "Primarius"],
            "广立微": ["广立微", "Semitronix"],
            "芯原股份": ["芯原", "VeriSilicon"],
            "芯华章": ["芯华章"],
            "芯和半导体": ["芯和半导体", "Xpeedic"],
            "Synopsys": ["Synopsys", "新思"],
            "Cadence": ["Cadence", "楷登"],
            "Siemens EDA": ["Siemens EDA", "Mentor Graphics"],
            "Arm": ["Arm", "ARM"],
            "Alphawave": ["Alphawave", "Alphawave Semi"],
        },
        {
            "华大九天": "国内",
            "概伦电子": "国内",
            "广立微": "国内",
            "芯原股份": "国内",
            "芯华章": "国内",
            "芯和半导体": "国内",
            "Synopsys": "海外",
            "Cadence": "海外",
            "Siemens EDA": "海外",
            "Arm": "海外",
            "Alphawave": "海外",
        },
    ),
    SegmentSearchSpec(
        "芯片设计/Fabless",
        [
            "中国 芯片设计 fabless 龙头 企业 海思 韦尔 卓胜微 兆易创新 紫光展锐 2026",
            "中国 AI芯片 CPU GPU fabless 龙头 寒武纪 海光信息 澜起科技 瑞芯微 2026",
        ],
        [
            "global fabless semiconductor leaders Nvidia Qualcomm Broadcom AMD MediaTek 2026",
            "top fabless semiconductor companies NVIDIA Broadcom Qualcomm AMD MediaTek Marvell 2026",
        ],
        {
            "海思": ["海思", "HiSilicon"],
            "韦尔股份": ["韦尔", "OmniVision"],
            "卓胜微": ["卓胜微", "Maxscend"],
            "兆易创新": ["兆易创新", "GigaDevice"],
            "紫光展锐": ["紫光展锐", "UNISOC"],
            "澜起科技": ["澜起科技", "Montage"],
            "寒武纪": ["寒武纪", "Cambricon"],
            "海光信息": ["海光信息", "Hygon"],
            "晶晨股份": ["晶晨股份", "Amlogic"],
            "瑞芯微": ["瑞芯微", "Rockchip"],
            "NVIDIA": ["NVIDIA", "英伟达"],
            "Qualcomm": ["Qualcomm", "高通"],
            "Broadcom": ["Broadcom", "博通"],
            "AMD": ["AMD"],
            "MediaTek": ["MediaTek", "联发科"],
            "Marvell": ["Marvell", "迈威尔"],
        },
        {
            "海思": "国内",
            "韦尔股份": "国内",
            "卓胜微": "国内",
            "兆易创新": "国内",
            "紫光展锐": "国内",
            "澜起科技": "国内",
            "寒武纪": "国内",
            "海光信息": "国内",
            "晶晨股份": "国内",
            "瑞芯微": "国内",
            "NVIDIA": "海外",
            "Qualcomm": "海外",
            "Broadcom": "海外",
            "AMD": "海外",
            "MediaTek": "海外",
            "Marvell": "海外",
        },
    ),
    SegmentSearchSpec(
        "晶圆制造/Foundry-IDM",
        [
            "中国 晶圆代工 IDM 龙头 中芯国际 华虹 半导体 士兰微 2026",
            "中国 成熟制程 晶圆制造 龙头 晶合集成 华润微 粤芯半导体 2026",
        ],
        [
            "global foundry IDM leaders TSMC Samsung Intel GlobalFoundries UMC SMIC 2026",
            "global semiconductor foundry market share TSMC Samsung UMC GlobalFoundries Tower 2026",
        ],
        {
            "中芯国际": ["中芯国际", "SMIC"],
            "华虹半导体": ["华虹", "Hua Hong"],
            "士兰微": ["士兰微", "Silan"],
            "晶合集成": ["晶合集成", "Nexchip"],
            "华润微": ["华润微", "CR Micro"],
            "粤芯半导体": ["粤芯半导体", "CanSemi"],
            "TSMC": ["TSMC", "台积电"],
            "Samsung": ["Samsung", "三星"],
            "Intel": ["Intel", "英特尔"],
            "GlobalFoundries": ["GlobalFoundries"],
            "UMC": ["UMC", "联电"],
            "Tower Semiconductor": ["Tower Semiconductor", "Tower"],
        },
        {
            "中芯国际": "国内",
            "华虹半导体": "国内",
            "士兰微": "国内",
            "晶合集成": "国内",
            "华润微": "国内",
            "粤芯半导体": "国内",
            "TSMC": "海外",
            "Samsung": "海外",
            "Intel": "海外",
            "GlobalFoundries": "海外",
            "UMC": "海外",
            "Tower Semiconductor": "海外",
        },
    ),
    SegmentSearchSpec(
        "半导体设备",
        [
            "中国 半导体设备 龙头 北方华创 中微公司 盛美上海 拓荆科技 华海清科 2026",
            "中国 半导体量测检测 涂胶显影 清洗 CMP 设备 龙头 中科飞测 芯源微 精测电子 2026",
        ],
        [
            "global semiconductor equipment leaders ASML Applied Materials Lam Research Tokyo Electron KLA 2026",
            "global lithography etch deposition metrology test equipment leaders ASML AMAT Lam TEL KLA Advantest ASM 2026",
        ],
        {
            "北方华创": ["北方华创", "NAURA"],
            "中微公司": ["中微公司", "AMEC"],
            "盛美上海": ["盛美", "ACM Research"],
            "拓荆科技": ["拓荆", "Piotech"],
            "华海清科": ["华海清科", "Hwatsing"],
            "中科飞测": ["中科飞测"],
            "芯源微": ["芯源微"],
            "精测电子": ["精测电子"],
            "ASML": ["ASML", "阿斯麦"],
            "Applied Materials": ["Applied Materials", "AMAT", "应用材料"],
            "Lam Research": ["Lam Research", "泛林"],
            "Tokyo Electron": ["Tokyo Electron", "TEL", "东京电子"],
            "KLA": ["KLA", "科磊"],
            "Advantest": ["Advantest", "爱德万"],
            "ASM International": ["ASM International", "ASM"],
        },
        {
            "北方华创": "国内",
            "中微公司": "国内",
            "盛美上海": "国内",
            "拓荆科技": "国内",
            "华海清科": "国内",
            "中科飞测": "国内",
            "芯源微": "国内",
            "精测电子": "国内",
            "ASML": "海外",
            "Applied Materials": "海外",
            "Lam Research": "海外",
            "Tokyo Electron": "海外",
            "KLA": "海外",
            "Advantest": "海外",
            "ASM International": "海外",
        },
    ),
    SegmentSearchSpec(
        "半导体材料",
        [
            "中国 半导体材料 龙头 沪硅产业 彤程新材 安集科技 江丰电子 雅克科技 鼎龙股份 2026",
            "中国 半导体材料 光刻胶 电子气体 龙头 南大光电 华特气体 TCL中环 立昂微 2026",
        ],
        [
            "global semiconductor materials leaders Shin-Etsu SUMCO JSR TOK Entegris Merck 2026",
            "global silicon wafer photoresist electronic gases semiconductor materials leaders GlobalWafers Siltronic DuPont Air Liquide 2026",
        ],
        {
            "沪硅产业": ["沪硅产业", "NSIG"],
            "TCL中环": ["TCL中环", "TCL Zhonghuan"],
            "立昂微": ["立昂微", "Lion Micro"],
            "彤程新材": ["彤程新材"],
            "安集科技": ["安集科技", "Anji"],
            "江丰电子": ["江丰电子"],
            "雅克科技": ["雅克科技"],
            "鼎龙股份": ["鼎龙股份"],
            "南大光电": ["南大光电"],
            "华特气体": ["华特气体"],
            "Shin-Etsu": ["Shin-Etsu", "信越"],
            "SUMCO": ["SUMCO"],
            "JSR": ["JSR"],
            "TOK": ["Tokyo Ohka", "TOK"],
            "Entegris": ["Entegris"],
            "Merck KGaA": ["Merck KGaA", "默克"],
            "GlobalWafers": ["GlobalWafers", "环球晶"],
            "Siltronic": ["Siltronic"],
            "DuPont": ["DuPont", "杜邦"],
            "Air Liquide": ["Air Liquide", "液化空气"],
        },
        {
            "沪硅产业": "国内",
            "TCL中环": "国内",
            "立昂微": "国内",
            "彤程新材": "国内",
            "安集科技": "国内",
            "江丰电子": "国内",
            "雅克科技": "国内",
            "鼎龙股份": "国内",
            "南大光电": "国内",
            "华特气体": "国内",
            "Shin-Etsu": "海外",
            "SUMCO": "海外",
            "JSR": "海外",
            "TOK": "海外",
            "Entegris": "海外",
            "Merck KGaA": "海外",
            "GlobalWafers": "海外",
            "Siltronic": "海外",
            "DuPont": "海外",
            "Air Liquide": "海外",
        },
    ),
    SegmentSearchSpec(
        "先进封装",
        [
            "中国 先进封装 龙头 长电科技 通富微电 华天科技 甬矽电子 2026",
            "中国 Chiplet 2.5D 3D 先进封装 龙头 长电 通富 华天 盛合晶微 2026",
        ],
        [
            "global advanced packaging leaders TSMC CoWoS ASE Amkor Intel Samsung JCET 2026",
            "global CoWoS 2.5D 3D advanced packaging capacity leaders TSMC ASE Amkor Samsung Intel SK hynix 2026",
        ],
        {
            "长电科技": ["长电科技", "JCET"],
            "通富微电": ["通富微电", "TFME"],
            "华天科技": ["华天科技", "Huatian"],
            "甬矽电子": ["甬矽电子"],
            "盛合晶微": ["盛合晶微"],
            "TSMC": ["TSMC", "CoWoS", "台积电"],
            "ASE": ["ASE", "日月光"],
            "Amkor": ["Amkor", "安靠"],
            "Intel": ["Intel", "Foveros"],
            "Samsung": ["Samsung", "I-Cube"],
            "SK hynix": ["SK hynix", "海力士"],
        },
        {
            "长电科技": "国内",
            "通富微电": "国内",
            "华天科技": "国内",
            "甬矽电子": "国内",
            "盛合晶微": "国内",
            "TSMC": "海外",
            "ASE": "海外",
            "Amkor": "海外",
            "Intel": "海外",
            "Samsung": "海外",
            "SK hynix": "海外",
        },
    ),
    SegmentSearchSpec(
        "传统封装测试/OSAT",
        [
            "中国 封测 龙头 长电科技 通富微电 华天科技 晶方科技 2026",
            "中国 OSAT 封装测试 排名 龙头 长电 通富 华天 晶方 利扬芯片 2026",
        ],
        [
            "global OSAT leaders ASE Amkor JCET Powertech Tongfu Huatian 2026",
            "top OSAT companies ranking ASE Amkor JCET Powertech KYEC ChipMOS UTAC 2026",
        ],
        {
            "长电科技": ["长电科技", "JCET"],
            "通富微电": ["通富微电", "TFME"],
            "华天科技": ["华天科技", "Huatian"],
            "晶方科技": ["晶方科技"],
            "利扬芯片": ["利扬芯片"],
            "ASE": ["ASE", "日月光"],
            "Amkor": ["Amkor"],
            "Powertech": ["Powertech", "PTI", "力成"],
            "KYEC": ["KYEC", "King Yuan"],
            "ChipMOS": ["ChipMOS"],
            "UTAC": ["UTAC"],
        },
        {
            "长电科技": "国内",
            "通富微电": "国内",
            "华天科技": "国内",
            "晶方科技": "国内",
            "利扬芯片": "国内",
            "ASE": "海外",
            "Amkor": "海外",
            "Powertech": "海外",
            "KYEC": "海外",
            "ChipMOS": "海外",
            "UTAC": "海外",
        },
    ),
    SegmentSearchSpec(
        "存储/HBM",
        [
            "中国 存储芯片 龙头 长江存储 长鑫存储 兆易创新 北京君正 HBM 2026",
            "中国 DRAM NAND 存储 龙头 长江存储 长鑫存储 佰维存储 江波龙 2026",
        ],
        [
            "global memory HBM leaders SK hynix Samsung Micron Kioxia Western Digital 2026",
            "HBM market share leaders SK hynix Samsung Micron 2026",
        ],
        {
            "长江存储": ["长江存储", "YMTC"],
            "长鑫存储": ["长鑫存储", "CXMT"],
            "兆易创新": ["兆易创新", "GigaDevice"],
            "北京君正": ["北京君正"],
            "佰维存储": ["佰维存储", "Biwin"],
            "江波龙": ["江波龙", "Longsys"],
            "SK hynix": ["SK hynix", "海力士"],
            "Samsung": ["Samsung", "三星"],
            "Micron": ["Micron", "美光"],
            "Kioxia": ["Kioxia", "铠侠"],
            "Western Digital": ["Western Digital", "西部数据"],
        },
        {
            "长江存储": "国内",
            "长鑫存储": "国内",
            "兆易创新": "国内",
            "北京君正": "国内",
            "佰维存储": "国内",
            "江波龙": "国内",
            "SK hynix": "海外",
            "Samsung": "海外",
            "Micron": "海外",
            "Kioxia": "海外",
            "Western Digital": "海外",
        },
    ),
    SegmentSearchSpec(
        "功率半导体/SiC-GaN",
        [
            "中国 功率半导体 SiC GaN 龙头 士兰微 斯达半导 闻泰科技 三安光电 天岳先进 2026",
            "中国 SiC 衬底 外延 功率器件 龙头 天岳先进 天科合达 华润微 新洁能 2026",
        ],
        [
            "global power semiconductor SiC GaN leaders Infineon STMicroelectronics Wolfspeed onsemi ROHM 2026",
            "global GaN power semiconductor leaders Navitas Transphorm EPC Infineon 2026",
        ],
        {
            "士兰微": ["士兰微", "Silan"],
            "斯达半导": ["斯达半导", "StarPower"],
            "闻泰科技": ["闻泰科技", "Nexperia"],
            "三安光电": ["三安光电", "Sanan"],
            "天岳先进": ["天岳先进"],
            "天科合达": ["天科合达"],
            "华润微": ["华润微", "CR Micro"],
            "新洁能": ["新洁能"],
            "Infineon": ["Infineon", "英飞凌"],
            "STMicroelectronics": ["STMicroelectronics", "意法半导体"],
            "Wolfspeed": ["Wolfspeed"],
            "onsemi": ["onsemi", "安森美"],
            "ROHM": ["ROHM", "罗姆"],
            "Navitas": ["Navitas"],
            "Transphorm": ["Transphorm"],
            "EPC": ["EPC", "Efficient Power Conversion"],
        },
        {
            "士兰微": "国内",
            "斯达半导": "国内",
            "闻泰科技": "国内",
            "三安光电": "国内",
            "天岳先进": "国内",
            "天科合达": "国内",
            "华润微": "国内",
            "新洁能": "国内",
            "Infineon": "海外",
            "STMicroelectronics": "海外",
            "Wolfspeed": "海外",
            "onsemi": "海外",
            "ROHM": "海外",
            "Navitas": "海外",
            "Transphorm": "海外",
            "EPC": "海外",
        },
    ),
    SegmentSearchSpec(
        "终端应用/系统需求",
        [
            "中国 AI服务器 新能源汽车 消费电子 通信设备 龙头 浪潮信息 比亚迪 华为 小米 2026",
            "中国 AI服务器 通信设备 云基础设施 龙头 工业富联 联想 中科曙光 中兴通讯 2026",
        ],
        [
            "global AI server automotive electronics consumer electronics telecom leaders Dell Supermicro Tesla Apple Cisco 2026",
            "global cloud AI server infrastructure leaders Microsoft Amazon Google Meta Dell Supermicro 2026",
        ],
        {
            "浪潮信息": ["浪潮信息", "Inspur"],
            "工业富联": ["工业富联", "Foxconn Industrial Internet", "FII"],
            "比亚迪": ["比亚迪", "BYD"],
            "华为": ["华为", "Huawei"],
            "小米": ["小米", "Xiaomi"],
            "联想": ["联想", "Lenovo"],
            "中科曙光": ["中科曙光", "Sugon"],
            "中兴通讯": ["中兴通讯", "ZTE"],
            "Dell": ["Dell"],
            "Supermicro": ["Supermicro", "Super Micro"],
            "Tesla": ["Tesla", "特斯拉"],
            "Apple": ["Apple", "苹果"],
            "Cisco": ["Cisco", "思科"],
            "Microsoft": ["Microsoft", "微软"],
            "Amazon": ["Amazon", "AWS"],
            "Google": ["Google", "谷歌"],
            "Meta": ["Meta"],
        },
        {
            "浪潮信息": "国内",
            "工业富联": "国内",
            "比亚迪": "国内",
            "华为": "国内",
            "小米": "国内",
            "联想": "国内",
            "中科曙光": "国内",
            "中兴通讯": "国内",
            "Dell": "海外",
            "Supermicro": "海外",
            "Tesla": "海外",
            "Apple": "海外",
            "Cisco": "海外",
            "Microsoft": "海外",
            "Amazon": "海外",
            "Google": "海外",
            "Meta": "海外",
        },
    ),
]


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)


def parse_key_from_secret(section: str, env: str) -> str | None:
    if os.getenv(env):
        return os.getenv(env)
    if not SECRET_REF.exists():
        return None
    text = SECRET_REF.read_text(encoding="utf-8", errors="ignore")
    match = re.search(rf"{re.escape(section)}:\s*[\s\S]*?key:\s*\"([^\"]+)\"", text)
    return match.group(1) if match else None


def search_bocha(query: str, count: int = 6) -> list[dict[str, Any]]:
    key = parse_key_from_secret("bocha", "BOCHA_API_KEY")
    if not key:
        return []
    resp = requests.post(
        "https://api.bochaai.com/v1/web-search",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"query": query, "freshness": "noLimit", "summary": True, "count": count},
        timeout=45,
    )
    resp.raise_for_status()
    data = resp.json()
    items = data.get("data", {}).get("webPages", {}).get("value", []) or []
    rows = []
    for item in items[:count]:
        rows.append(
            {
                "search_tool": "Bocha",
                "query": query,
                "title": item.get("name", ""),
                "url": item.get("url", ""),
                "snippet": item.get("summary") or item.get("snippet") or "",
                "publish_date": item.get("datePublished") or "",
            }
        )
    return rows


def search_tavily(query: str, count: int = 6) -> list[dict[str, Any]]:
    key = parse_key_from_secret("tavily", "TAVILY_API_KEY")
    if not key:
        return []
    resp = requests.post(
        "https://api.tavily.com/search",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "query": query,
            "search_depth": "basic",
            "topic": "general",
            "max_results": count,
            "include_answer": False,
        },
        timeout=45,
    )
    resp.raise_for_status()
    data = resp.json()
    rows = []
    for item in data.get("results", [])[:count]:
        rows.append(
            {
                "search_tool": "Tavily",
                "query": query,
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", ""),
                "publish_date": item.get("published_date") or "",
            }
        )
    return rows


def alias_matches(text: str, alias: str) -> bool:
    if re.search(r"[\u4e00-\u9fff]", alias):
        return alias in text
    pattern = rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def find_company_hits(text: str, keywords: dict[str, list[str]]) -> list[str]:
    hits = []
    for company, aliases in keywords.items():
        if any(alias_matches(text, alias) for alias in aliases):
            hits.append(company)
    return hits


def region_for_query(query_type: str) -> str:
    return "domestic" if query_type == "domestic" else "global"


def source_grade(url: str, title: str) -> str:
    combined = f"{url} {title}".lower()
    if any(domain in combined for domain in ["annual", "investor", "sec.gov", "cninfo", "公司公告"]):
        return "A"
    if any(domain in combined for domain in ["semi.org", "semiconductors.org", "gartner", "trendforce", "counterpoint", "idc"]):
        return "A-"
    if any(domain in combined for domain in ["eastmoney", "sina", "qianzhan", "pedaily", "yicai", "eet"]):
        return "B"
    return "B-"


def run_searches() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    evidence_rows: list[dict[str, Any]] = []
    company_rows: list[dict[str, Any]] = []
    evidence_id = 1
    seen_company_segment: set[tuple[str, str, str]] = set()

    for spec in SEGMENT_SPECS:
        query_groups = [
            ("domestic", "Bocha", spec.domestic_queries),
            ("global", "Tavily", spec.global_queries),
        ]
        for query_type, tool, queries in query_groups:
            for query in queries:
                try:
                    rows = search_bocha(query) if tool == "Bocha" else search_tavily(query)
                except Exception as exc:
                    rows = [
                        {
                            "search_tool": tool,
                            "query": query,
                            "title": f"ERROR: {type(exc).__name__}",
                            "url": "",
                            "snippet": str(exc),
                            "publish_date": "",
                        }
                    ]
                time.sleep(0.3)
                for row in rows:
                    text = " ".join([row.get("title", ""), row.get("snippet", ""), row.get("url", "")])
                    companies = find_company_hits(text, spec.company_keywords)
                    ev_id = f"E2-{evidence_id:03d}"
                    evidence_id += 1
                    evidence_rows.append(
                        {
                            "evidence_id": ev_id,
                            "task_id": "S2-company-leaders",
                            "question": f"{spec.segment} 环节的国内/海外龙头企业有哪些？",
                            "segment_name": spec.segment,
                            "region": region_for_query(query_type),
                            "source_title": row.get("title", ""),
                            "source_url_or_file": row.get("url", ""),
                            "source_type": "industry_search",
                            "publish_date": row.get("publish_date", ""),
                            "entities": companies,
                            "evidence_excerpt": (row.get("snippet", "") or "")[:900],
                            "possible_claim": (
                                f"该来源可作为 {spec.segment} 环节"
                                f"{'国内' if query_type == 'domestic' else '海外'}龙头候选线索。"
                            ),
                            "claim_type_guess": "company_leader_candidate",
                            "confidence": "medium" if companies else "low",
                            "limitations": "搜索结果层证据，需后续回到年报、公司 IR、招股书、市场份额报告核验。",
                            "retrieved_at": NOW,
                            "source_grade": source_grade(row.get("url", ""), row.get("title", "")),
                            "search_tool": row.get("search_tool", tool),
                            "query": query,
                        }
                    )
                    for company in companies:
                        company_region = spec.company_regions.get(
                            company,
                            "国内" if query_type == "domestic" else "海外",
                        )
                        key = (spec.segment, company, company_region)
                        if key in seen_company_segment:
                            continue
                        seen_company_segment.add(key)
                        aliases = spec.company_keywords.get(company, [])
                        company_rows.append(
                            {
                                "segment_name": spec.segment,
                                "company_name": company,
                                "region": company_region,
                                "aliases": ";".join(aliases),
                                "leader_type": "龙头候选",
                                "evidence_ids": ev_id,
                                "confidence": "medium",
                                "limitations": "候选池阶段，未完成财报/份额硬核验。",
                            }
                        )

    return evidence_rows, merge_company_rows(company_rows)


def spec_by_segment() -> dict[str, SegmentSearchSpec]:
    return {spec.segment: spec for spec in SEGMENT_SPECS}


def rebuild_company_rows_from_evidence(evidence_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    specs = spec_by_segment()
    company_rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for evidence in evidence_rows:
        segment = evidence.get("segment_name", "")
        spec = specs.get(segment)
        if not spec:
            continue
        for company in evidence.get("entities", []) or []:
            company_region = spec.company_regions.get(company, "待确认")
            key = (segment, company, company_region)
            aliases = spec.company_keywords.get(company, [])
            if key in seen:
                for row in company_rows:
                    if (
                        row["segment_name"] == segment
                        and row["company_name"] == company
                        and row["region"] == company_region
                    ):
                        ids = set(row["evidence_ids"].split(";"))
                        ids.add(evidence["evidence_id"])
                        row["evidence_ids"] = ";".join(sorted(ids))
                        break
                continue
            seen.add(key)
            company_rows.append(
                {
                    "segment_name": segment,
                    "company_name": company,
                    "region": company_region,
                    "aliases": ";".join(aliases),
                    "leader_type": "龙头候选",
                    "evidence_ids": evidence["evidence_id"],
                    "confidence": "medium",
                    "limitations": "候选池阶段，未完成财报/份额硬核验。",
                }
            )

    return merge_company_rows(company_rows)


def merge_company_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["segment_name"], row["company_name"], row["region"])
        if key not in merged:
            merged[key] = row.copy()
            continue
        ids = set(merged[key]["evidence_ids"].split(";")) | set(row["evidence_ids"].split(";"))
        merged[key]["evidence_ids"] = ";".join(sorted(ids))
    return sorted(merged.values(), key=lambda r: (r["segment_name"], r["region"], r["company_name"]))


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "segment_name",
        "company_name",
        "region",
        "aliases",
        "leader_type",
        "evidence_ids",
        "confidence",
        "limitations",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path: Path, rows: list[dict[str, Any]]) -> None:
    grouped: dict[str, dict[str, list[str]]] = {}
    for row in rows:
        grouped.setdefault(row["segment_name"], {}).setdefault(row["region"], []).append(row["company_name"])

    lines = [
        "# Stage 2 半导体环节龙头企业候选池",
        "",
        f"- 生成时间：{NOW}",
        f"- 候选公司记录：{len(rows)} 条",
        "- 说明：这是搜索结果层候选池，不等同于最终排名；后续需要用年报、招股书、公司 IR、市场份额报告做硬核验。",
        "",
        "| 环节 | 国内龙头候选 | 海外龙头候选 |",
        "|---|---|---|",
    ]
    for spec in SEGMENT_SPECS:
        domestic = "、".join(grouped.get(spec.segment, {}).get("国内", [])) or "待补充"
        global_ = "、".join(grouped.get(spec.segment, {}).get("海外", [])) or "待补充"
        lines.append(f"| {spec.segment} | {domestic} | {global_} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ensure_dirs()
    if not SEGMENTS_PATH.exists():
        raise FileNotFoundError(f"missing segment file: {SEGMENTS_PATH}")
    if "--from-existing-evidence" in sys.argv:
        if not EVIDENCE_PATH.exists():
            raise FileNotFoundError(f"missing evidence file: {EVIDENCE_PATH}")
        evidence_rows = [
            json.loads(line)
            for line in EVIDENCE_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        company_rows = rebuild_company_rows_from_evidence(evidence_rows)
    else:
        evidence_rows, company_rows = run_searches()
        write_jsonl(EVIDENCE_PATH, evidence_rows)
        company_rows = rebuild_company_rows_from_evidence(evidence_rows)
    write_csv(COMPANY_POOL_PATH, company_rows)
    write_summary(SUMMARY_PATH, company_rows)
    print(
        json.dumps(
            {
                "evidence": len(evidence_rows),
                "company_candidates": len(company_rows),
                "evidence_path": str(EVIDENCE_PATH),
                "company_pool_path": str(COMPANY_POOL_PATH),
                "summary_path": str(SUMMARY_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
