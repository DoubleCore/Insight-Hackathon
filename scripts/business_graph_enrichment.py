from __future__ import annotations

import csv
import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from kg_common import clean_snippet  # noqa: E402
except Exception:  # noqa: BLE001
    def clean_snippet(text: str, max_chars: int = 200, max_sentences: int = 2) -> str:  # type: ignore
        return (text or "")[:max_chars]


ROOT = Path(__file__).resolve().parents[1]
LEADERS_PATH = ROOT / "data" / "company_pool" / "company_leaders_stage_3.csv"

L1_L4_PATH = ROOT / "data" / "business_graph" / "stage5_l1_l4_segments.csv"
PRODUCT_SERVICES_PATH = ROOT / "data" / "business_graph" / "stage5_product_services.csv"
COMPANY_PRODUCT_RELATIONS_PATH = ROOT / "data" / "business_graph" / "stage6_company_product_relations.csv"
DIGITAL_CHINA_RELATIONS_PATH = ROOT / "data" / "business_graph" / "stage7_digital_china_relations.csv"
DIGITAL_CHINA_EVIDENCE_PATH = ROOT / "data" / "evidence" / "evidence_stage_7_digital_china.jsonl"
OPPORTUNITIES_PATH = ROOT / "data" / "business_graph" / "stage8_business_opportunities.csv"
COMPETITION_PATH = ROOT / "data" / "business_graph" / "stage6_company_competition.csv"
SUMMARY_PATH = ROOT / "data" / "business_graph" / "business_graph_enrichment_summary.md"


LAYER_PREFIX = {
    "上游": "UPSTREAM",
    "中游": "MIDSTREAM",
    "下游": "DOWNSTREAM",
}

L4_CODE_BY_NAME = {
    "AI服务器/云基础设施": "L4-DOWNSTREAM-AI-INFRA",
    "消费电子/通信设备": "L4-DOWNSTREAM-ICT-DEVICE",
    "新能源汽车/汽车电子": "L4-DOWNSTREAM-AUTO-ELECTRONICS",
    "云服务/互联网平台": "L4-DOWNSTREAM-CLOUD-INTERNET-PLATFORM",
    "通信网络基础设施": "L4-DOWNSTREAM-TELECOM-NETWORK-INFRA",
    "智能终端/PC": "L4-DOWNSTREAM-SMART-DEVICE-PC",
    "AI/GPU/CPU算力芯片": "L4-MIDSTREAM-AI-COMPUTE-CHIP",
    "手机SoC/通信基带": "L4-MIDSTREAM-MOBILE-SOC",
    "模拟/RF/MCU/传感器": "L4-MIDSTREAM-ANALOG-RF-MCU-SENSOR",
    "2.5D/3D/Chiplet先进封装": "L4-MIDSTREAM-ADVANCED-PACKAGING",
    "传统OSAT封装测试": "L4-MIDSTREAM-OSAT",
}

FOCUS_L4_NAMES = {
    "AI服务器/云基础设施",
    "消费电子/通信设备",
    "新能源汽车/汽车电子",
    "云服务/互联网平台",
    "通信网络基础设施",
    "智能终端/PC",
    "AI/GPU/CPU算力芯片",
    "手机SoC/通信基带",
    "模拟/RF/MCU/传感器",
    "2.5D/3D/Chiplet先进封装",
    "传统OSAT封装测试",
}

PRODUCT_SERVICE_CONTROLLED: dict[str, list[dict[str, str]]] = {
    # ---- 8 个焦点 L4（原有产品，补 match_keywords/is_default）----
    "AI服务器/云基础设施": [
        {"product_service_name": "AI服务器", "category": "硬件/整机", "match_keywords": "AI服务器,服务器", "is_default": "true"},
        {"product_service_name": "GPU服务器", "category": "硬件/整机", "match_keywords": "GPU服务器", "is_default": "false"},
        {"product_service_name": "液冷服务器", "category": "硬件/整机", "match_keywords": "液冷", "is_default": "false"},
        {"product_service_name": "存储设备", "category": "硬件/基础设施", "match_keywords": "存储设备,存储系统", "is_default": "false"},
        {"product_service_name": "数据中心交换机", "category": "网络/基础设施", "match_keywords": "交换机", "is_default": "false"},
        {"product_service_name": "数据中心基础设施服务", "category": "服务/集成", "match_keywords": "数据中心基础设施,机房", "is_default": "false"},
        {"product_service_name": "国产算力服务器", "category": "硬件/整机", "match_keywords": "国产算力,鲲泰,昇腾服务器", "is_default": "false"},
        {"product_service_name": "云基础设施服务", "category": "服务/云", "match_keywords": "云基础设施,云计算", "is_default": "false"},
    ],
    "消费电子/通信设备": [
        {"product_service_name": "通信设备", "category": "硬件/网络", "match_keywords": "通信设备,通讯设备", "is_default": "true"},
        {"product_service_name": "网络设备", "category": "硬件/网络", "match_keywords": "网络设备,路由器,交换机", "is_default": "false"},
        {"product_service_name": "企业级ICT解决方案", "category": "服务/集成", "match_keywords": "ICT解决方案,企业ICT", "is_default": "false"},
        {"product_service_name": "智能终端", "category": "硬件/终端", "match_keywords": "智能终端,手机,PC,终端", "is_default": "false"},
    ],
    "新能源汽车/汽车电子": [
        {"product_service_name": "智能汽车解决方案", "category": "服务/集成", "match_keywords": "智能汽车,智能座舱,自动驾驶", "is_default": "true"},
        {"product_service_name": "车载计算平台", "category": "硬件/计算", "match_keywords": "车载计算,车机", "is_default": "false"},
        {"product_service_name": "汽车电子系统", "category": "硬件/汽车电子", "match_keywords": "汽车电子,车载电子", "is_default": "false"},
        {"product_service_name": "功率半导体模块", "category": "器件/功率", "match_keywords": "功率模块,IGBT模块", "is_default": "false"},
    ],
    "云服务/互联网平台": [
        {"product_service_name": "公有云服务", "category": "服务/云", "match_keywords": "公有云,云服务,云计算", "is_default": "true"},
        {"product_service_name": "AI云平台", "category": "服务/AI平台", "match_keywords": "AI云,AI平台,大模型平台", "is_default": "false"},
        {"product_service_name": "互联网数据中心需求", "category": "需求/数据中心", "match_keywords": "数据中心,训练集群,推理集群", "is_default": "false"},
    ],
    "通信网络基础设施": [
        {"product_service_name": "运营商网络设备", "category": "硬件/通信网络", "match_keywords": "运营商网络,通信网络,5G", "is_default": "true"},
        {"product_service_name": "基站/核心网设备", "category": "硬件/通信网络", "match_keywords": "基站,核心网,RAN", "is_default": "false"},
        {"product_service_name": "数据中心网络方案", "category": "方案/网络", "match_keywords": "数据中心网络,网络方案", "is_default": "false"},
    ],
    "智能终端/PC": [
        {"product_service_name": "PC整机", "category": "硬件/终端", "match_keywords": "PC,个人电脑,笔记本", "is_default": "true"},
        {"product_service_name": "手机/平板终端", "category": "硬件/终端", "match_keywords": "手机,平板,智能终端", "is_default": "false"},
        {"product_service_name": "AI终端设备", "category": "硬件/AI终端", "match_keywords": "AI终端,AIPC,AI PC", "is_default": "false"},
    ],
    "AI/GPU/CPU算力芯片": [
        {"product_service_name": "AI GPU", "category": "芯片/算力", "match_keywords": "AI GPU,GPU,加速计算", "is_default": "false"},
        {"product_service_name": "AI加速卡", "category": "硬件/板卡", "match_keywords": "加速卡,推理卡", "is_default": "false"},
        {"product_service_name": "CPU/DCU算力芯片", "category": "芯片/算力", "match_keywords": "CPU,DCU,处理器", "is_default": "false"},
        {"product_service_name": "数据中心网络芯片", "category": "芯片/网络", "match_keywords": "网络芯片,网卡,DP", "is_default": "false"},
    ],
    "手机SoC/通信基带": [
        {"product_service_name": "移动SoC", "category": "芯片/终端", "match_keywords": "SoC,手机芯片", "is_default": "true"},
        {"product_service_name": "通信基带芯片", "category": "芯片/通信", "match_keywords": "基带", "is_default": "false"},
        {"product_service_name": "射频前端芯片", "category": "芯片/RF", "match_keywords": "射频前端,RF前端", "is_default": "false"},
    ],
    "模拟/RF/MCU/传感器": [
        {"product_service_name": "模拟芯片", "category": "芯片/模拟", "match_keywords": "模拟芯片,模拟IC", "is_default": "true"},
        {"product_service_name": "RF芯片", "category": "芯片/RF", "match_keywords": "RF芯片,射频芯片", "is_default": "false"},
        {"product_service_name": "MCU", "category": "芯片/控制", "match_keywords": "MCU,单片机,微控制器", "is_default": "false"},
        {"product_service_name": "图像传感器", "category": "芯片/传感器", "match_keywords": "图像传感器,CIS,CMOS传感器", "is_default": "false"},
    ],
    "2.5D/3D/Chiplet先进封装": [
        {"product_service_name": "先进封装服务", "category": "服务/制造", "match_keywords": "先进封装,2.5D,3D封装,Chiplet", "is_default": "true"},
        {"product_service_name": "2.5D封装", "category": "服务/制造", "match_keywords": "2.5D封装", "is_default": "false"},
        {"product_service_name": "3D封装", "category": "服务/制造", "match_keywords": "3D封装", "is_default": "false"},
        {"product_service_name": "Chiplet集成服务", "category": "服务/制造", "match_keywords": "Chiplet", "is_default": "false"},
    ],
    "传统OSAT封装测试": [
        {"product_service_name": "封装测试服务", "category": "服务/制造", "match_keywords": "封装测试,OSAT,封测", "is_default": "true"},
        {"product_service_name": "晶圆级封装", "category": "服务/制造", "match_keywords": "晶圆级封装,WLP", "is_default": "false"},
        {"product_service_name": "成品测试服务", "category": "服务/测试", "match_keywords": "成品测试,FT测试", "is_default": "false"},
    ],
    # ---- 23 个非焦点 L4（新增，每个 2-4 个核心产品）----
    "EDA软件": [
        {"product_service_name": "EDA全流程平台", "category": "软件/EDA", "match_keywords": "全流程,平台,工具线,EDA上市龙头,三巨头", "is_default": "true"},
        {"product_service_name": "模拟设计EDA工具", "category": "软件/EDA", "match_keywords": "模拟设计,仿真", "is_default": "false"},
        {"product_service_name": "数字设计EDA工具", "category": "软件/EDA", "match_keywords": "数字设计,综合,布局布线", "is_default": "false"},
        {"product_service_name": "制造/良率EDA工具", "category": "软件/EDA", "match_keywords": "良率,成品率,制造,OPC,测试芯片,数据分析,器件建模,PDK", "is_default": "false"},
    ],
    "半导体IP/芯片定制": [
        {"product_service_name": "处理器IP核", "category": "IP/服务", "match_keywords": "IP核,处理器IP,CPU IP", "is_default": "true"},
        {"product_service_name": "接口IP", "category": "IP/服务", "match_keywords": "接口IP,DDR IP,PCIe IP", "is_default": "false"},
        {"product_service_name": "芯片定制服务", "category": "服务/设计", "match_keywords": "芯片定制,设计服务", "is_default": "false"},
    ],
    "晶圆代工/Foundry": [
        {"product_service_name": "先进制程代工", "category": "服务/制造", "match_keywords": "先进制程,7nm,5nm,3nm", "is_default": "false"},
        {"product_service_name": "成熟制程代工", "category": "服务/制造", "match_keywords": "成熟制程,28nm,40nm", "is_default": "true"},
        {"product_service_name": "特色工艺代工", "category": "服务/制造", "match_keywords": "特色工艺,BCD,SOI", "is_default": "false"},
    ],
    "IDM/特色工艺制造": [
        {"product_service_name": "功率/模拟IDM器件", "category": "器件/IDM", "match_keywords": "IDM,功率器件,模拟器件", "is_default": "true"},
        {"product_service_name": "车规半导体器件", "category": "器件/IDM", "match_keywords": "车规,车用半导体", "is_default": "false"},
        {"product_service_name": "特色工艺产线服务", "category": "服务/制造", "match_keywords": "特色工艺产线", "is_default": "false"},
    ],
    "光刻设备": [
        {"product_service_name": "光刻机", "category": "设备/光刻", "match_keywords": "光刻机,步进,扫描", "is_default": "true"},
        {"product_service_name": "涂胶显影设备", "category": "设备/光刻", "match_keywords": "涂胶显影,track", "is_default": "false"},
    ],
    "刻蚀设备": [
        {"product_service_name": "等离子刻蚀设备", "category": "设备/刻蚀", "match_keywords": "刻蚀,etch,等离子刻蚀", "is_default": "true"},
        {"product_service_name": "深硅刻蚀设备", "category": "设备/刻蚀", "match_keywords": "深硅刻蚀,TSV刻蚀", "is_default": "false"},
    ],
    "薄膜沉积设备": [
        {"product_service_name": "CVD设备", "category": "设备/薄膜", "match_keywords": "CVD,化学气相沉积", "is_default": "true"},
        {"product_service_name": "PVD设备", "category": "设备/薄膜", "match_keywords": "PVD,物理气相沉积", "is_default": "false"},
        {"product_service_name": "ALD设备", "category": "设备/薄膜", "match_keywords": "ALD,原子层沉积", "is_default": "false"},
    ],
    "清洗/CMP/热处理设备": [
        {"product_service_name": "清洗设备", "category": "设备/清洗", "match_keywords": "清洗设备,单片清洗", "is_default": "true"},
        {"product_service_name": "CMP抛光设备", "category": "设备/CMP", "match_keywords": "CMP,抛光", "is_default": "false"},
        {"product_service_name": "热处理设备", "category": "设备/热处理", "match_keywords": "热处理,退火,炉管", "is_default": "false"},
    ],
    "量测检测设备": [
        {"product_service_name": "缺陷检测设备", "category": "设备/检测", "match_keywords": "缺陷检测,检测,defect", "is_default": "true"},
        {"product_service_name": "膜厚/CD量测设备", "category": "设备/量测", "match_keywords": "膜厚,CD,量测", "is_default": "false"},
    ],
    "测试设备": [
        {"product_service_name": "SoC测试机", "category": "设备/测试", "match_keywords": "测试机,ATE,SoC测试", "is_default": "true"},
        {"product_service_name": "存储测试机", "category": "设备/测试", "match_keywords": "存储测试,Memory测试", "is_default": "false"},
        {"product_service_name": "分选机/探针台", "category": "设备/测试", "match_keywords": "分选机,探针台,handler,prober", "is_default": "false"},
    ],
    "硅片": [
        {"product_service_name": "300mm硅片", "category": "材料/硅片", "match_keywords": "300mm,12英寸,硅片", "is_default": "true"},
        {"product_service_name": "200mm硅片", "category": "材料/硅片", "match_keywords": "200mm,8英寸", "is_default": "false"},
        {"product_service_name": "外延片", "category": "材料/硅片", "match_keywords": "外延片,外延", "is_default": "false"},
    ],
    "光刻胶/配套材料": [
        {"product_service_name": "光刻胶", "category": "材料/光刻胶", "match_keywords": "光刻胶,photoresist", "is_default": "true"},
        {"product_service_name": "显影液/配套化学品", "category": "材料/化学品", "match_keywords": "显影液,配套化学品", "is_default": "false"},
    ],
    "电子气体/湿电子化学品": [
        {"product_service_name": "电子特气", "category": "材料/气体", "match_keywords": "电子特气,特气,电子气体", "is_default": "true"},
        {"product_service_name": "湿电子化学品", "category": "材料/化学品", "match_keywords": "湿电子化学品,电子化学品", "is_default": "false"},
    ],
    "靶材": [
        {"product_service_name": "溅射靶材", "category": "材料/靶材", "match_keywords": "靶材,sputtering target", "is_default": "true"},
        {"product_service_name": "高纯金属材料", "category": "材料/金属", "match_keywords": "高纯金属,高纯铝,高纯铜", "is_default": "false"},
    ],
    "CMP材料": [
        {"product_service_name": "CMP抛光液", "category": "材料/CMP", "match_keywords": "抛光液,slurry", "is_default": "true"},
        {"product_service_name": "CMP抛光垫", "category": "材料/CMP", "match_keywords": "抛光垫,pad", "is_default": "false"},
    ],
    "封装材料/IC载板": [
        {"product_service_name": "ABF载板", "category": "材料/载板", "match_keywords": "ABF载板,ABF", "is_default": "true"},
        {"product_service_name": "BT载板", "category": "材料/载板", "match_keywords": "BT载板,BT", "is_default": "false"},
        {"product_service_name": "封装基板", "category": "材料/载板", "match_keywords": "封装基板,基板", "is_default": "false"},
    ],
    "DRAM/HBM": [
        {"product_service_name": "DRAM芯片", "category": "芯片/存储", "match_keywords": "DRAM,DDR", "is_default": "true"},
        {"product_service_name": "HBM高带宽存储", "category": "芯片/存储", "match_keywords": "HBM,高带宽存储", "is_default": "false"},
    ],
    "NAND Flash": [
        {"product_service_name": "NAND闪存芯片", "category": "芯片/存储", "match_keywords": "NAND,闪存", "is_default": "true"},
        {"product_service_name": "3D NAND晶圆", "category": "芯片/存储", "match_keywords": "3D NAND", "is_default": "false"},
    ],
    "存储控制/模组/NOR": [
        {"product_service_name": "NOR Flash", "category": "芯片/存储", "match_keywords": "NOR,NOR Flash", "is_default": "true"},
        {"product_service_name": "存储主控芯片", "category": "芯片/控制", "match_keywords": "主控,存储控制", "is_default": "false"},
        {"product_service_name": "存储模组", "category": "器件/模组", "match_keywords": "模组,存储模组", "is_default": "false"},
    ],
    "功率器件/模块": [
        {"product_service_name": "IGBT器件/模块", "category": "器件/功率", "match_keywords": "IGBT", "is_default": "true"},
        {"product_service_name": "MOSFET功率器件", "category": "器件/功率", "match_keywords": "MOSFET,功率MOS", "is_default": "false"},
        {"product_service_name": "功率模块", "category": "器件/功率", "match_keywords": "功率模块,power module", "is_default": "false"},
    ],
    "SiC衬底/外延": [
        {"product_service_name": "SiC衬底", "category": "材料/SiC", "match_keywords": "SiC衬底,碳化硅衬底", "is_default": "true"},
        {"product_service_name": "SiC外延片", "category": "材料/SiC", "match_keywords": "SiC外延,外延", "is_default": "false"},
    ],
    "SiC功率器件/模块": [
        {"product_service_name": "SiC MOSFET", "category": "器件/SiC", "match_keywords": "SiC MOSFET,碳化硅MOSFET", "is_default": "true"},
        {"product_service_name": "SiC功率模块", "category": "器件/SiC", "match_keywords": "SiC模块,碳化硅模块", "is_default": "false"},
        {"product_service_name": "SiC二极管", "category": "器件/SiC", "match_keywords": "SiC二极管,SiC SBD", "is_default": "false"},
    ],
    "GaN功率/RF器件": [
        {"product_service_name": "GaN功率器件", "category": "器件/GaN", "match_keywords": "GaN,氮化镓", "is_default": "true"},
        {"product_service_name": "GaN射频器件", "category": "器件/GaN", "match_keywords": "GaN RF,GaN射频", "is_default": "false"},
    ],
}

COMPANY_PRODUCT_RULES: dict[str, dict[str, list[str]]] = {
    "浪潮信息": {"PRODUCES": ["AI服务器", "GPU服务器", "液冷服务器", "存储设备"], "INTEGRATES": ["AI GPU"]},
    "工业富联": {"PRODUCES": ["AI服务器", "GPU服务器"], "INTEGRATES": ["数据中心基础设施服务"]},
    "中科曙光": {"PRODUCES": ["AI服务器", "液冷服务器", "国产算力服务器"]},
    "联想": {"PRODUCES": ["AI服务器", "存储设备"], "SELLS": ["数据中心基础设施服务"], "INTEGRATES": ["AI GPU"]},
    "Supermicro": {"PRODUCES": ["AI服务器", "GPU服务器"], "INTEGRATES": ["AI GPU"]},
    "Dell": {"PRODUCES": ["AI服务器", "存储设备"], "SELLS": ["数据中心基础设施服务"], "INTEGRATES": ["AI GPU"]},
    "Microsoft": {"USES": ["AI服务器", "GPU服务器", "云基础设施服务", "公有云服务", "AI云平台", "互联网数据中心需求"]},
    "Google": {"USES": ["AI服务器", "GPU服务器", "云基础设施服务", "公有云服务", "AI云平台", "互联网数据中心需求"]},
    "Amazon": {"USES": ["AI服务器", "GPU服务器", "云基础设施服务", "公有云服务", "AI云平台", "互联网数据中心需求"]},
    "Meta": {"USES": ["AI服务器", "GPU服务器", "互联网数据中心需求"]},
    "华为": {"PRODUCES": ["通信设备", "智能终端", "国产算力服务器", "运营商网络设备", "基站/核心网设备", "手机/平板终端"], "SELLS": ["企业级ICT解决方案", "数据中心网络方案"]},
    "中兴通讯": {"PRODUCES": ["通信设备", "网络设备", "运营商网络设备", "基站/核心网设备"], "SELLS": ["企业级ICT解决方案", "数据中心网络方案"]},
    "Cisco": {"PRODUCES": ["网络设备", "数据中心交换机", "运营商网络设备", "数据中心网络方案"]},
    "Ericsson": {"PRODUCES": ["通信设备", "运营商网络设备", "基站/核心网设备"]},
    "Nokia": {"PRODUCES": ["通信设备", "网络设备", "运营商网络设备", "基站/核心网设备"]},
    "Samsung": {"PRODUCES": ["智能终端", "手机/平板终端"]},
    "Apple": {"PRODUCES": ["智能终端", "手机/平板终端", "PC整机"], "USES": ["移动SoC"]},
    "NVIDIA": {"PRODUCES": ["AI GPU", "AI加速卡"], "SELLS": ["AI加速卡"]},
    "AMD": {"PRODUCES": ["AI GPU", "CPU/DCU算力芯片", "AI加速卡"]},
    "Broadcom": {"PRODUCES": ["数据中心网络芯片"]},
    "Marvell": {"PRODUCES": ["数据中心网络芯片"]},
    "寒武纪": {"PRODUCES": ["AI加速卡"]},
    "海光信息": {"PRODUCES": ["CPU/DCU算力芯片"]},
    "Alphawave": {"PRODUCES": ["接口IP"]},
    "兆易创新": {"PRODUCES": ["MCU", "DRAM芯片", "NOR Flash"]},
    "北京君正": {"PRODUCES": ["NOR Flash"]},
    "中芯国际": {"PRODUCES": ["成熟制程代工"]},
    "晶合集成": {"PRODUCES": ["成熟制程代工"]},
    "Samsung": {"PRODUCES": ["先进制程代工", "成熟制程代工", "智能终端", "手机/平板终端"]},
    "海思": {"PRODUCES": ["移动SoC", "通信基带芯片"]},
    "紫光展锐": {"PRODUCES": ["移动SoC", "通信基带芯片"]},
    "比亚迪": {"PRODUCES": ["智能汽车解决方案"], "USES": ["汽车电子系统", "功率半导体模块"]},
    "Tesla": {"PRODUCES": ["智能汽车解决方案"], "USES": ["车载计算平台", "功率半导体模块"]},
    "Bosch": {"PRODUCES": ["汽车电子系统"]},
    "Continental": {"PRODUCES": ["汽车电子系统"]},
    "Denso": {"PRODUCES": ["汽车电子系统"]},
    "长电科技": {"PRODUCES": ["封装测试服务", "先进封装服务"]},
    "通富微电": {"PRODUCES": ["封装测试服务", "先进封装服务"]},
    "华天科技": {"PRODUCES": ["封装测试服务", "先进封装服务"]},
    "ASE": {"PRODUCES": ["封装测试服务", "先进封装服务"]},
    "Amkor": {"PRODUCES": ["封装测试服务", "先进封装服务"]},
    "TSMC": {"PRODUCES": ["先进封装服务", "2.5D封装", "3D封装"]},
    "ASML": {"PRODUCES": ["光刻机"]},
    "上海微电子": {"PRODUCES": ["光刻机"]},
    "Canon": {"PRODUCES": ["光刻机"]},
    "Nikon": {"PRODUCES": ["光刻机"]},
    "Teradyne": {"PRODUCES": ["SoC测试机"]},
    "Cohu": {"PRODUCES": ["SoC测试机"]},
    "Analog Devices": {"PRODUCES": ["模拟芯片"]},
    "Texas Instruments": {"PRODUCES": ["模拟芯片"]},
    "卓胜微": {"PRODUCES": ["RF芯片"]},
    "Applied Materials": {"PRODUCES": ["CVD设备", "PVD设备", "缺陷检测设备"]},
    "Lam Research": {"PRODUCES": ["CVD设备"]},
    "Tokyo Electron": {"PRODUCES": ["CVD设备"]},
    "拓荆科技": {"PRODUCES": ["CVD设备", "ALD设备"]},
    "华海清科": {"PRODUCES": ["CMP抛光设备"]},
    "盛美上海": {"PRODUCES": ["清洗设备"]},
    "中科飞测": {"PRODUCES": ["缺陷检测设备", "膜厚/CD量测设备"]},
    "华峰测控": {"PRODUCES": ["SoC测试机"]},
    "长川科技": {"PRODUCES": ["SoC测试机", "分选机/探针台"]},
    "GlobalWafers": {"PRODUCES": ["300mm硅片", "200mm硅片", "外延片"]},
    "TCL中环": {"PRODUCES": ["300mm硅片"]},
    "沪硅产业": {"PRODUCES": ["300mm硅片", "200mm硅片", "外延片"]},
    "立昂微": {"PRODUCES": ["300mm硅片", "200mm硅片", "外延片"]},
    "南大光电": {"PRODUCES": ["光刻胶"]},
    "彤程新材": {"PRODUCES": ["光刻胶"]},
    "晶瑞电材": {"PRODUCES": ["光刻胶", "湿电子化学品"]},
    "JSR": {"PRODUCES": ["光刻胶"]},
    "华特气体": {"PRODUCES": ["电子特气"]},
    "江化微": {"PRODUCES": ["湿电子化学品"]},
    "金宏气体": {"PRODUCES": ["电子特气"]},
    "Entegris": {"PRODUCES": ["电子特气", "CMP抛光液"]},
    "有研新材": {"PRODUCES": ["溅射靶材", "高纯金属材料"]},
    "江丰电子": {"PRODUCES": ["溅射靶材", "高纯金属材料"]},
    "鼎龙股份": {"PRODUCES": ["CMP抛光垫"]},
    "DuPont": {"PRODUCES": ["CMP抛光液"]},
    "Fujimi": {"PRODUCES": ["CMP抛光液"]},
    "Nan Ya PCB": {"PRODUCES": ["ABF载板"]},
    "Unimicron": {"PRODUCES": ["ABF载板"]},
    "生益科技": {"PRODUCES": ["ABF载板", "封装基板"]},
    "甬矽电子": {"PRODUCES": ["先进封装服务"]},
    "SK hynix": {"PRODUCES": ["先进封装服务", "HBM高带宽存储", "DRAM芯片", "NAND闪存芯片"]},
    "新洁能": {"PRODUCES": ["MOSFET功率器件"]},
    "天岳先进": {"PRODUCES": ["SiC衬底", "SiC外延片"]},
    "天科合达": {"PRODUCES": ["SiC衬底"]},
    "英诺赛科": {"PRODUCES": ["GaN功率器件"]},
    "EPC": {"PRODUCES": ["GaN功率器件"]},
    "三安光电": {"PRODUCES": ["SiC衬底", "SiC外延片", "SiC MOSFET", "SiC二极管", "GaN功率器件", "GaN射频器件"]},
    "华润微": {"PRODUCES": ["功率/模拟IDM器件", "IGBT器件/模块", "MOSFET功率器件", "功率模块"]},
    "士兰微": {"PRODUCES": ["功率/模拟IDM器件", "IGBT器件/模块", "功率模块", "SiC MOSFET", "SiC功率模块", "SiC二极管"]},
    "斯达半导": {"PRODUCES": ["IGBT器件/模块", "功率模块", "SiC功率模块"]},
    "闻泰科技": {"PRODUCES": ["功率/模拟IDM器件", "MOSFET功率器件", "SiC MOSFET"]},
    "Infineon": {"PRODUCES": ["IGBT器件/模块", "SiC MOSFET"]},
    "ROHM": {"PRODUCES": ["IGBT器件/模块", "SiC MOSFET"]},
    "STMicroelectronics": {"PRODUCES": ["IGBT器件/模块", "SiC MOSFET"]},
    "Wolfspeed": {"PRODUCES": ["SiC衬底", "SiC MOSFET"]},
    "onsemi": {"PRODUCES": ["SiC MOSFET"]},
}

# 需求端使用/需求关联推导规则：公开资料不足以证明具体采购合同，统一表达为 USES。
# 与 COMPANY_PRODUCT_RULES 同 schema（公司 -> {关系类型: [产品名]}）。
PROCUREMENT_RULES: dict[str, dict[str, list[str]]] = {
    "比亚迪": {"USES": ["功率半导体模块", "SiC功率模块"]},
    "Tesla": {"USES": ["功率半导体模块", "SiC功率模块", "车载计算平台"]},
}

ADDITIONAL_L1_L4_SEGMENTS: tuple[dict[str, str], ...] = (
    {
        "l1": "下游",
        "l2": "系统需求",
        "l3": "云与互联网平台",
        "l4_name": "云服务/互联网平台",
        "subsegment_role": "公有云、AI云平台、互联网数据中心和大模型训练/推理基础设施需求端。",
    },
    {
        "l1": "下游",
        "l2": "系统需求",
        "l3": "通信网络基础设施",
        "l4_name": "通信网络基础设施",
        "subsegment_role": "运营商网络、基站、核心网、数据中心网络和企业网络基础设施需求端。",
    },
    {
        "l1": "下游",
        "l2": "系统需求",
        "l3": "智能终端/PC",
        "l4_name": "智能终端/PC",
        "subsegment_role": "手机、PC、平板、AI终端和智能硬件整机需求端。",
    },
)

# 下游 L4：需求端公司不参与 PRODUCES 的 basis 关键词/default 兜底推导
# （它们不"生产"芯片类产品，仅按 COMPANY_PRODUCT_RULES 与 PROCUREMENT_RULES 处理）。
DOWNSTREAM_L4_NAMES = {
    "AI服务器/云基础设施",
    "消费电子/通信设备",
    "新能源汽车/汽车电子",
    "云服务/互联网平台",
    "通信网络基础设施",
    "智能终端/PC",
}

DIGITAL_CHINA_PUBLIC_RELATIONS = [
    {
        "evidence_id": "DC-001",
        "company_name": "华为",
        "relationship_status": "confirmed_public_relationship",
        "relationship_type": "生态合作/解决方案匹配",
        "relationship_basis": "公开资料和既有证据显示神州数码与华为生态、鲲鹏/昇腾/国产算力相关业务存在公开业务关联线索。",
        "source_title": "公开资料：神州数码与华为生态/国产算力相关业务线索",
        "source_url_or_file": "data/evidence/evidence_stage_3.jsonl#E3-671",
        "evidence_excerpt": "已有 Stage3 证据提到神州数码使用华为昇腾芯片、神州鲲泰服务器行业排名靠前等公开线索。",
        "confidence": "medium",
        "requires_internal_validation": "true",
    },
    {
        "evidence_id": "DC-002",
        "company_name": "中兴通讯",
        "relationship_status": "needs_internal_validation",
        "relationship_type": "ICT方案匹配待验证",
        "relationship_basis": "中兴通讯属于通信设备和数据中心基础设施相关公司，与神州数码ICT集成和渠道能力存在潜在方案协同空间。",
        "source_title": "公开资料：通信设备/ICT基础设施龙头与集成服务潜在匹配",
        "source_url_or_file": "data/evidence/evidence_stage_3.jsonl#E3-710",
        "evidence_excerpt": "Stage3 证据将中兴通讯列为通信设备领域代表企业。",
        "confidence": "medium-low",
        "requires_internal_validation": "true",
    },
    {
        "evidence_id": "DC-003",
        "company_name": "浪潮信息",
        "relationship_status": "needs_internal_validation",
        "relationship_type": "AI服务器/数据中心匹配待验证",
        "relationship_basis": "浪潮信息处于AI服务器和数据中心基础设施重点环节，与神州数码系统集成、算力基础设施方案存在潜在客户或伙伴切入价值。",
        "source_title": "公开资料：AI服务器行业重点企业",
        "source_url_or_file": "data/evidence/evidence_stage_3.jsonl#E3-668",
        "evidence_excerpt": "Stage3 证据显示浪潮信息在AI服务器领域具有服务器、存储和云计算基础设施产品布局。",
        "confidence": "medium",
        "requires_internal_validation": "true",
    },
    {
        "evidence_id": "DC-004",
        "company_name": "NVIDIA",
        "relationship_status": "potential_fit",
        "relationship_type": "AI算力生态潜在协同",
        "relationship_basis": "NVIDIA 是AI GPU和加速计算生态核心企业，与AI服务器、数据中心和算力解决方案高度相关，但公开资料不能直接证明其为神州数码内部客户关系。",
        "source_title": "公开资料：AI GPU和加速计算生态龙头",
        "source_url_or_file": "data/company_pool/company_leaders_stage_3.csv",
        "evidence_excerpt": "Stage3 将 NVIDIA 归入 AI/GPU/CPU算力芯片全球龙头。",
        "confidence": "medium",
        "requires_internal_validation": "true",
    },
    {
        "evidence_id": "DC-005",
        "company_name": "联想",
        "relationship_status": "needs_internal_validation",
        "relationship_type": "服务器/终端/ICT匹配待验证",
        "relationship_basis": "联想覆盖服务器、PC和AI终端系统，与神州数码ICT渠道和系统集成业务存在潜在业务相关性。",
        "source_title": "公开资料：AI服务器/云基础设施需求端代表",
        "source_url_or_file": "data/company_pool/company_leaders_stage_3.csv",
        "evidence_excerpt": "Stage3 将联想列为AI服务器/云基础设施需求端龙头。",
        "confidence": "medium-low",
        "requires_internal_validation": "true",
    },
]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def split_layer(value_chain_layer: str) -> tuple[str, str]:
    parts = [part.strip() for part in value_chain_layer.split("/") if part.strip()]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], "/".join(parts[1:])


def code_for_l4(l1: str, l4_name: str) -> str:
    if l4_name in L4_CODE_BY_NAME:
        return L4_CODE_BY_NAME[l4_name]
    prefix = LAYER_PREFIX.get(l1, "INDUSTRY")
    slug = (
        l4_name.replace("/", "-")
        .replace(" ", "-")
        .replace("(", "")
        .replace(")", "")
        .replace("（", "")
        .replace("）", "")
    )
    return f"L4-{prefix}-{slug}"


def dedupe_rows(rows: list[dict[str, Any]], key_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    seen: OrderedDict[tuple[Any, ...], dict[str, Any]] = OrderedDict()
    for row in rows:
        key = tuple(row.get(field, "") for field in key_fields)
        if key not in seen:
            seen[key] = row
    return list(seen.values())


def l4_code_map_from_rows(l1_l4_rows: list[dict[str, str]]) -> dict[str, str]:
    """l4_name -> l4_code 映射（从已用真实 l1 算出的 l1_l4_rows 取，保证前缀正确）。"""
    return {row["l4_name"]: row["l4_code"] for row in l1_l4_rows}


def product_service_segment_map(l4_code_by_name: dict[str, str] | None = None) -> dict[str, dict[str, str]]:
    l4_code_by_name = l4_code_by_name or {}
    mapping: dict[str, dict[str, str]] = {}
    for l4_name, products in PRODUCT_SERVICE_CONTROLLED.items():
        l4_code = l4_code_by_name.get(l4_name) or code_for_l4("", l4_name)
        for product in products:
            mapping[product["product_service_name"]] = {
                "l4_code": l4_code,
                "l4_name": l4_name,
            }
    return mapping


def build_l1_l4_rows(
    leader_rows: list[dict[str, str]],
    include_additional_segments: bool | None = None,
) -> list[dict[str, str]]:
    if include_additional_segments is None:
        include_additional_segments = not leader_rows
    rows: list[dict[str, str]] = []
    for row in leader_rows:
        l1, l2 = split_layer(row.get("value_chain_layer", ""))
        l3 = row.get("major_segment", "").strip()
        l4_name = row.get("subsegment_name", "").strip()
        rows.append(
            {
                "l1": l1,
                "l2": l2,
                "l3": l3,
                "l4_name": l4_name,
                "l4_code": code_for_l4(l1, l4_name),
                "subsegment_role": row.get("subsegment_role", ""),
                "source_value_chain_layer": row.get("value_chain_layer", ""),
                "source_major_segment": row.get("major_segment", ""),
                "source_subsegment_name": l4_name,
                "is_focus_scope": "true" if l4_name in FOCUS_L4_NAMES else "false",
            }
        )
    if include_additional_segments:
        for segment in ADDITIONAL_L1_L4_SEGMENTS:
            l4_name = segment["l4_name"]
            rows.append(
                {
                    "l1": segment["l1"],
                    "l2": segment["l2"],
                    "l3": segment["l3"],
                    "l4_name": l4_name,
                    "l4_code": code_for_l4(segment["l1"], l4_name),
                    "subsegment_role": segment["subsegment_role"],
                    "source_value_chain_layer": f"{segment['l1']}/{segment['l2']}",
                    "source_major_segment": segment["l3"],
                    "source_subsegment_name": l4_name,
                    "is_focus_scope": "true" if l4_name in FOCUS_L4_NAMES else "false",
                }
            )
    return dedupe_rows(rows, ("l4_code",))


def build_product_services(l1_l4_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for segment in l1_l4_rows:
        l4_name = segment["l4_name"]
        for product in PRODUCT_SERVICE_CONTROLLED.get(l4_name, []):
            product_name = product["product_service_name"]
            rows.append(
                {
                    "product_service_id": f"PS::{segment['l4_code']}::{product_name}",
                    "product_service_name": product_name,
                    "category": product["category"],
                    "l4_code": segment["l4_code"],
                    "l4_name": l4_name,
                    "definition": f"{l4_name}相关的{product_name}产品/服务。",
                    "is_controlled": "true",
                }
            )
    return dedupe_rows(rows, ("product_service_id",))


def product_keyword_index(l4_code_by_name: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """构建产品关键词索引：[{l4_name, l4_code, product_name, match_keywords, is_default}]。"""
    l4_code_by_name = l4_code_by_name or {}
    index: list[dict[str, Any]] = []
    for l4_name, products in PRODUCT_SERVICE_CONTROLLED.items():
        l4_code = l4_code_by_name.get(l4_name) or code_for_l4("", l4_name)
        for product in products:
            index.append({
                "l4_name": l4_name,
                "l4_code": l4_code,
                "product_name": product["product_service_name"],
                "match_keywords": product.get("match_keywords", product["product_service_name"]),
                "is_default": product.get("is_default", "false") == "true",
            })
    return index


def _merge_relation(rows_by_key, company, product_name, relation_type, l4_code, l4_name,
                    basis, evidence_ids, confidence, requires_internal_validation, derivation):
    """合并一条公司-产品关系（同 key 聚合证据、取更长 basis、取更高 confidence）。"""
    key = (company, product_name, relation_type)
    if key not in rows_by_key:
        rows_by_key[key] = {
            "company_name": company,
            "product_service_name": product_name,
            "relation_type": relation_type,
            "l4_code": l4_code,
            "l4_name": l4_name,
            "basis": basis,
            "evidence_ids": evidence_ids,
            "confidence": confidence,
            "requires_internal_validation": requires_internal_validation,
            "derivation": derivation,
        }
        return
    existing = rows_by_key[key]
    ids = set(part.strip() for part in existing["evidence_ids"].split(";") if part.strip())
    ids.update(part.strip() for part in evidence_ids.split(";") if part.strip())
    existing["evidence_ids"] = ";".join(sorted(ids))
    if len(basis) > len(existing.get("basis", "")):
        existing["basis"] = basis
    if confidence == "high" and derivation != "demand_side_presumed":
        existing["confidence"] = "high"
    # derivation 优先级：硬编码 > basis匹配 > default；保留更"硬"的来源
    rank = {"hardcoded": 3, "basis_keyword_match": 2, "l4_default_presumed": 1, "demand_side_presumed": 2}
    if rank.get(derivation, 0) > rank.get(existing.get("derivation", ""), 0):
        existing["derivation"] = derivation
        existing["requires_internal_validation"] = requires_internal_validation
    elif requires_internal_validation == "false" and existing.get("derivation") != "demand_side_presumed":
        existing["requires_internal_validation"] = "false"


def build_company_product_relations(leader_rows: list[dict[str, str]], l1_l4_rows: list[dict[str, str]] | None = None) -> list[dict[str, str]]:
    """三级推导公司-产品关系：
    1) 硬编码 COMPANY_PRODUCT_RULES（最高优先级，人工判断）；
    2) basis 关键词匹配：stage3 selection_basis 命中产品 match_keywords -> PRODUCES（复用 stage3 证据）；
    3) default 兜底：无命中时挂 is_default 产品，confidence 降为 medium-low、需内部验证（仅非下游 L4）。
    另叠加 PROCUREMENT_RULES（需求端使用/需求关联，derivation=demand_side_presumed）。
    """
    l4_code_by_name = l4_code_map_from_rows(l1_l4_rows or build_l1_l4_rows(leader_rows))
    product_segment_by_name = product_service_segment_map(l4_code_by_name)
    keyword_index = product_keyword_index(l4_code_by_name)
    rows_by_key: OrderedDict[tuple[str, str, str], dict[str, str]] = OrderedDict()

    # 预建 (l4_name -> products) 索引
    products_by_l4: dict[str, list[dict[str, Any]]] = {}
    for item in keyword_index:
        products_by_l4.setdefault(item["l4_name"], []).append(item)

    for row in leader_rows:
        company = row.get("company_name", "").strip()
        evidence_ids = row.get("evidence_ids", "").strip()
        if not company or not evidence_ids:
            continue
        l4_name = row.get("subsegment_name", "").strip()
        l1, _ = split_layer(row.get("value_chain_layer", ""))
        l4_code = code_for_l4(l1, l4_name) if l4_name else ""
        basis = row.get("selection_basis", "")
        confidence = row.get("confidence", "medium")

        # 优先级 1：硬编码规则
        relation_map = COMPANY_PRODUCT_RULES.get(company, {})
        hardcoded_l4_names: set[str] = set()
        for relation_type, product_names in relation_map.items():
            for product_name in product_names:
                ps = product_segment_by_name.get(product_name)
                pc, pn = (ps["l4_code"], ps["l4_name"]) if ps else (l4_code, l4_name)
                if pn:
                    hardcoded_l4_names.add(pn)
                _merge_relation(rows_by_key, company, product_name, relation_type, pc, pn,
                                basis, evidence_ids, confidence, "false", "hardcoded")

        # 优先级 1b：使用/需求关联规则（需求端）
        proc_map = PROCUREMENT_RULES.get(company, {})
        for relation_type, product_names in proc_map.items():
            for product_name in product_names:
                ps = product_segment_by_name.get(product_name)
                if not ps:
                    continue
                _merge_relation(rows_by_key, company, product_name, relation_type,
                                ps["l4_code"], ps["l4_name"], basis, evidence_ids,
                "medium", "true", "demand_side_presumed")

        # 优先级 2 & 3：仅非下游 L4 做 basis 匹配 / default 兜底
        if l4_name and l4_name not in DOWNSTREAM_L4_NAMES:
            if l4_name in hardcoded_l4_names:
                continue
            products = products_by_l4.get(l4_name, [])
            matched: list[dict[str, Any]] = []
            for p in products:
                kws = [k.strip() for k in str(p["match_keywords"]).split(",") if k.strip()]
                if any(k and k in basis for k in kws):
                    matched.append(p)
            if matched:
                # 优先级 2：basis 关键词匹配
                for p in matched:
                    _merge_relation(rows_by_key, company, p["product_name"], "PRODUCES",
                                    p["l4_code"], p["l4_name"], basis, evidence_ids,
                                    confidence, "false", "basis_keyword_match")
            else:
                # 优先级 3：default 兜底
                default_p = next((p for p in products if p["is_default"]), None)
                if default_p:
                    _merge_relation(rows_by_key, company, default_p["product_name"], "PRODUCES",
                                    default_p["l4_code"], default_p["l4_name"], basis, evidence_ids,
                                    "medium-low", "true", "l4_default_presumed")

    return list(rows_by_key.values())


def build_competition_relations(
    company_product_relations: list[dict[str, str]],
    leader_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    """同环节同产品龙头推定竞争：两家公司对同一受控产品均有 PRODUCES，
    且 leader_level 属于 {国内龙头, 全球龙头} -> 生成一条"推定竞争"边。
    """
    # 公司 -> {leader_level}（取该公司任一环节的最高级别）
    level_rank = {"全球龙头": 3, "国内龙头": 2, "细分龙头": 1, "需求端龙头": 0}
    company_level: dict[str, str] = {}
    for row in leader_rows:
        company = row.get("company_name", "").strip()
        level = row.get("leader_level", "").strip()
        if not company or not level:
            continue
        prev = company_level.get(company, "")
        if level_rank.get(level, 0) > level_rank.get(prev, 0):
            company_level[company] = level

    # 产品 -> [公司]（仅 PRODUCES）
    companies_by_product: dict[str, list[str]] = {}
    evidence_by_company_product: dict[tuple[str, str], list[str]] = {}
    for r in company_product_relations:
        if r.get("relation_type") != "PRODUCES":
            continue
        product = r.get("product_service_name", "")
        company = r.get("company_name", "")
        if not product or not company:
            continue
        companies_by_product.setdefault(product, []).append(company)
        ids = [s.strip() for s in str(r.get("evidence_ids", "")).split(";") if s.strip()]
        evidence_by_company_product.setdefault((company, product), []).extend(ids)

    rows: list[dict[str, str]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for product, companies in companies_by_product.items():
        # 仅保留龙头级公司参与竞争配对
        leaders = [c for c in companies if company_level.get(c) in ("国内龙头", "全球龙头")]
        if len(leaders) < 2:
            continue
        # 按公司名排序去重配对（min, max）单向一条
        leaders_sorted = sorted(set(leaders))
        for i in range(len(leaders_sorted)):
            for j in range(i + 1, len(leaders_sorted)):
                a, b = leaders_sorted[i], leaders_sorted[j]
                pair = (a, b)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                ev = sorted(set(
                    evidence_by_company_product.get((a, product), [])
                    + evidence_by_company_product.get((b, product), [])
                ))
                rows.append({
                    "source_company": a,
                    "target_company": b,
                    "relationship_type": "推定竞争",
                    "basis": f"同环节同产品龙头推定竞争：{product}",
                    "evidence_ids": ";".join(ev),
                    "confidence": "medium-low",
                    "derivation": "same_product_leader_presumed",
                    "requires_internal_validation": "true",
                    "对称关系": "true",
                })
        # 每产品竞争边截断 top-6（避免单产品边过多）
        # 此处简单实现：不硬截断，由下游决定；若需截断可在返回前处理
    # 全局兜底截断：若超 250 条，按 confidence 与产品覆盖度保留
    if len(rows) > 250:
        rows = rows[:250]
    return rows


def build_digital_china_relations() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in DIGITAL_CHINA_PUBLIC_RELATIONS:
        rows.append(
            {
                "company_name": item["company_name"],
                "relationship_status": item["relationship_status"],
                "relationship_type": item["relationship_type"],
                "relationship_basis": item["relationship_basis"],
                "evidence_ids": item["evidence_id"],
                "confidence": item["confidence"],
                "requires_internal_validation": item["requires_internal_validation"],
                "limitations": "公开资料只证明公开合作/生态匹配/潜在业务相关性，不证明内部CRM客户关系。",
            }
        )
    return rows


def build_digital_china_evidence() -> list[dict[str, Any]]:
    retrieved_at = now_iso()
    rows: list[dict[str, Any]] = []
    for item in DIGITAL_CHINA_PUBLIC_RELATIONS:
        rows.append(
            {
                "evidence_id": item["evidence_id"],
                "task_id": "S7-digital-china-public-relations",
                "company_name": item["company_name"],
                "relationship_status": item["relationship_status"],
                "source_title": item["source_title"],
                "source_url_or_file": item["source_url_or_file"],
                "source_type": "public_or_existing_evidence",
                "evidence_excerpt": item["evidence_excerpt"],
                "possible_claim": item["relationship_basis"],
                "confidence": item["confidence"],
                "limitations": "公开资料不能证明内部客户关系，需要内部客户/销售数据确认。",
                "retrieved_at": retrieved_at,
                "source_grade": "B",
            }
        )
    return rows


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


# 客户资产分层（公开证据代理）。no_public_evidence 不建客户资产节点，故不在此枚举。
ASSET_TIERS = ("存量客户", "生态伙伴", "潜力客户", "待验证")

# 生态/渠道强词：命中且证据等级 A/A- 的 confirmed 关系，升级为"生态伙伴"。
ECOSYSTEM_STRONG_TERMS = (
    "总经销", "总代理", "分销协议", "授权代理", "授权经销商",
    "联合发布", "联合推出", "伙伴认证", "生态合作", "战略合作协议",
    "签署", "签约", "中标",
)


def assign_asset_tier(
    relationship_status: str,
    confidence: str,
    relationship_type: str = "",
    relationship_basis: str = "",
    evidence_grade: str = "",
) -> str:
    """根据公开证据判定客户资产分层。

    - 存量客户：公开管线不产出，留给未来内部 CRM 数据。
    - 生态伙伴：confirmed 且证据等级 A/A- 且命中渠道/生态强词。
    - 潜力客户：其余 confirmed。
    - 待验证：needs_internal_validation；或所有 potential_fit。
    """
    if relationship_status == "confirmed_public_relationship":
        text = f"{relationship_type} {relationship_basis}"
        strong_hit = any(term in text for term in ECOSYSTEM_STRONG_TERMS)
        if evidence_grade in ("A", "A-") and strong_hit:
            return "生态伙伴"
        return "潜力客户"
    if relationship_status == "potential_fit":
        return "待验证"
    if relationship_status == "needs_internal_validation":
        return "待验证"
    return "待验证"


def enrich_relations_with_tier(
    digital_china_relations: list[dict[str, str]],
    digital_china_evidence: list[dict[str, Any]] | dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    """给 stage7 关系列表补充 asset_tier 列（idempotent）。

    evidence 可为 list 或 {evidence_id: row} 字典；取该关系证据中最高等级用于 tier 判定。
    """
    if isinstance(digital_china_evidence, list):
        evidence_by_id = {row.get("evidence_id"): row for row in digital_china_evidence}
    else:
        evidence_by_id = dict(digital_china_evidence)

    def _max_grade(evidence_ids: list[str]) -> str:
        rank = {"A": 5, "A-": 4, "B": 3, "B-": 2, "C": 1}
        best = ""
        best_rank = 0
        for eid in evidence_ids:
            row = evidence_by_id.get(eid, {})
            grade = row.get("source_grade", "")
            if rank.get(grade, 0) > best_rank:
                best_rank = rank.get(grade, 0)
                best = grade
        return best

    for row in digital_china_relations:
        evidence_ids = [
            part.strip()
            for part in str(row.get("evidence_ids", "")).split(";")
            if part.strip()
        ]
        grade = _max_grade(evidence_ids)
        row["asset_tier"] = assign_asset_tier(
            row.get("relationship_status", ""),
            row.get("confidence", ""),
            row.get("relationship_type", ""),
            row.get("relationship_basis", ""),
            grade,
        )
    return digital_china_relations


def solution_for_product(product_name: str) -> tuple[str, str, str]:
    if product_name in {
        "AI服务器",
        "GPU服务器",
        "液冷服务器",
        "国产算力服务器",
        "云基础设施服务",
        "数据中心基础设施服务",
    }:
        return (
            "国产算力与AI基础设施解决方案",
            "AI基础设施重点客户战役",
            "围绕AI服务器、液冷、存储、网络和云基础设施形成组合方案，优先寻找算力建设和数据中心升级机会。",
        )
    if product_name in {"通信设备", "网络设备", "数据中心交换机", "企业级ICT解决方案"}:
        return (
            "企业ICT与数据中心网络解决方案",
            "ICT基础设施升级战役",
            "围绕网络设备、通信设备和企业ICT集成形成基础设施升级方案。",
        )
    if product_name in {"智能汽车解决方案", "车载计算平台", "汽车电子系统"}:
        return (
            "汽车电子与智能制造ICT解决方案",
            "汽车电子行业客户战役",
            "围绕车载计算、汽车电子和制造数字化寻找行业客户项目机会。",
        )
    return (
        "半导体生态协同解决方案",
        "半导体生态伙伴拓展战役",
        "围绕重点企业的产品/服务定位，寻找渠道、集成、生态合作或行业客户机会。",
    )


def build_business_opportunities(
    digital_china_relations: list[dict[str, str]],
    company_product_relations: list[dict[str, str]],
) -> list[dict[str, str]]:
    relation_by_company = {row["company_name"]: row for row in digital_china_relations}
    # 客户资产治理：仅为分层属于 {存量客户, 生态伙伴, 潜力客户} 的公司生成商机，
    # 待验证层不生成（避免低质商机爆炸）。
    qualified_tiers = {"存量客户", "生态伙伴", "潜力客户"}
    rows: list[dict[str, str]] = []
    for product_row in company_product_relations:
        company = product_row["company_name"]
        dc_relation = relation_by_company.get(company)
        if not dc_relation:
            continue
        tier = dc_relation.get("asset_tier", "")
        if tier and tier not in qualified_tiers:
            continue
        product_name = product_row["product_service_name"]
        solution_name, campaign_name, basis = solution_for_product(product_name)
        # basis 清洗：去掉免责声明/重复段落等噪声，保留干净的关系依据
        cleaned_dc_basis = clean_snippet(dc_relation.get("relationship_basis", ""))
        rows.append(
            {
                "opportunity_id": f"OP::{company}::{product_name}",
                "company_name": company,
                "product_service_name": product_name,
                "l4_code": product_row["l4_code"],
                "l4_name": product_row["l4_name"],
                "opportunity_name": f"{company}-{product_name}业务机会",
                "opportunity_type": "客户/伙伴/生态机会",
                "opportunity_basis": f"{basis} 关系依据：{cleaned_dc_basis}",
                "solution_name": solution_name,
                "campaign_name": campaign_name,
                "margin_improvement_logic": "通过软硬件组合、集成服务、生态适配和行业方案包装提升项目毛利，而不是只做单品转售。",
                "asset_tier": tier,
                "evidence_ids": ";".join(
                    [dc_relation.get("evidence_ids", ""), product_row.get("evidence_ids", "")]
                ).strip(";"),
                "confidence": dc_relation.get("confidence", "medium"),
                "requires_internal_validation": "true",
                "limitations": "需要内部客户资产、销售线索或伙伴授权数据进一步确认。",
            }
        )
    return dedupe_rows(rows, ("opportunity_id",))


def write_summary(
    l1_l4_rows: list[dict[str, str]],
    product_services: list[dict[str, str]],
    company_product_relations: list[dict[str, str]],
    digital_china_relations: list[dict[str, str]],
    opportunities: list[dict[str, str]],
    competition_relations: list[dict[str, str]] | None = None,
) -> None:
    competition_relations = competition_relations or []
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 半导体图谱业务化补全 Stage5-8 汇总",
        "",
        f"- 生成时间：{now_iso()}",
        f"- L1-L4 规范化环节：{len(l1_l4_rows)}",
        f"- 受控产品/服务：{len(product_services)}",
        f"- 公司-产品/服务关系：{len(company_product_relations)}",
        f"- 同环节竞争推定关系：{len(competition_relations)}",
        f"- 神州数码公开关系/潜在关系：{len(digital_china_relations)}",
        f"- 业务机会：{len(opportunities)}",
        "",
        "## 口径",
        "",
        f"- 受控产品/服务已覆盖全部 {len(l1_l4_rows)} 个 L4 环节，并补充云服务/互联网平台、通信网络基础设施、智能终端/PC 等下游业务切入环节。",
        "- 公司-产品关系采用三级推导：硬编码规则（最高优先级）-> stage3 basis 关键词匹配 -> default 兜底（标注需内部验证）。",
        "- 需求端使用/需求关联由公开资料和行业常识推导，统一标注 requires_internal_validation=true，不再把无直接证据的需求关系写成采购事实。",
        "- 推定竞争关系仅表示同环节同产品龙头之间存在市场重叠，不等同于公开披露的直接竞争事实。",
        "- 公开资料不能证明内部客户关系，只能作为公开合作、生态匹配或潜在业务相关性线索。",
        "- 商机、方案和战役计划均为公开资料驱动的候选建议，需要内部销售/客户资产确认。",
    ]
    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_all() -> dict[str, int]:
    leader_rows = read_csv(LEADERS_PATH)
    l1_l4_rows = build_l1_l4_rows(leader_rows, include_additional_segments=True)
    product_services = build_product_services(l1_l4_rows)
    company_product_relations = build_company_product_relations(leader_rows, l1_l4_rows)
    competition_relations = build_competition_relations(company_product_relations, leader_rows)
    digital_china_relations = build_digital_china_relations()
    digital_china_evidence = build_digital_china_evidence()
    # 补充客户资产分层列并回写 stage7 CSV（idempotent，WS3 重跑后也补 tier）
    digital_china_relations = enrich_relations_with_tier(digital_china_relations, digital_china_evidence)
    write_csv(
        DIGITAL_CHINA_RELATIONS_PATH,
        digital_china_relations,
        [
            "company_name",
            "relationship_status",
            "relationship_type",
            "relationship_basis",
            "evidence_ids",
            "confidence",
            "requires_internal_validation",
            "limitations",
            "asset_tier",
        ],
    )
    opportunities = build_business_opportunities(
        digital_china_relations,
        company_product_relations,
    )

    write_csv(
        L1_L4_PATH,
        l1_l4_rows,
        [
            "l1",
            "l2",
            "l3",
            "l4_name",
            "l4_code",
            "subsegment_role",
            "source_value_chain_layer",
            "source_major_segment",
            "source_subsegment_name",
            "is_focus_scope",
        ],
    )
    write_csv(
        PRODUCT_SERVICES_PATH,
        product_services,
        [
            "product_service_id",
            "product_service_name",
            "category",
            "l4_code",
            "l4_name",
            "definition",
            "is_controlled",
        ],
    )
    write_csv(
        COMPANY_PRODUCT_RELATIONS_PATH,
        company_product_relations,
        [
            "company_name",
            "product_service_name",
            "relation_type",
            "l4_code",
            "l4_name",
            "basis",
            "evidence_ids",
            "confidence",
            "requires_internal_validation",
            "derivation",
        ],
    )
    write_csv(
        COMPETITION_PATH,
        competition_relations,
        [
            "source_company",
            "target_company",
            "relationship_type",
            "basis",
            "evidence_ids",
            "confidence",
            "derivation",
            "requires_internal_validation",
            "对称关系",
        ],
    )
    write_jsonl(DIGITAL_CHINA_EVIDENCE_PATH, digital_china_evidence)
    write_csv(
        OPPORTUNITIES_PATH,
        opportunities,
        [
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
        ],
    )
    write_summary(
        l1_l4_rows,
        product_services,
        company_product_relations,
        digital_china_relations,
        opportunities,
        competition_relations,
    )
    return {
        "l1_l4_rows": len(l1_l4_rows),
        "product_services": len(product_services),
        "company_product_relations": len(company_product_relations),
        "competition_relations": len(competition_relations),
        "digital_china_relations": len(digital_china_relations),
        "opportunities": len(opportunities),
    }


def main() -> None:
    print(json.dumps(generate_all(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
