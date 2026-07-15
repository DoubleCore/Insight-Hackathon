from __future__ import annotations

import csv
import json
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

OUTPUT_DIR = ROOT / "data" / "company_pool"
EVIDENCE_PATH = ROOT / "data" / "evidence" / "evidence_stage_3.jsonl"
LEADERS_PATH = OUTPUT_DIR / "company_leaders_stage_3.csv"
SUMMARY_PATH = OUTPUT_DIR / "company_leaders_stage_3_summary.md"
NOW = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


@dataclass(frozen=True)
class Candidate:
    name: str
    region: str
    aliases: tuple[str, ...]
    leader_level: str
    basis: str


@dataclass(frozen=True)
class SubsegmentSpec:
    value_chain_layer: str
    major_segment: str
    subsegment_name: str
    subsegment_role: str
    domestic_queries: tuple[str, ...]
    global_queries: tuple[str, ...]
    candidates: tuple[Candidate, ...]


def c(name: str, region: str, aliases: list[str], level: str, basis: str) -> Candidate:
    return Candidate(name, region, tuple(aliases), level, basis)


SUBSEGMENTS: tuple[SubsegmentSpec, ...] = (
    SubsegmentSpec(
        "上游/设计支撑",
        "EDA/IP",
        "EDA软件",
        "芯片设计软件、验证、仿真和全流程设计平台。",
        (
            "中国 EDA 软件 龙头 市场份额 华大九天 概伦电子 广立微 2026",
            "国产 EDA 全流程 点工具 龙头 华大九天 概伦电子 广立微 芯华章",
        ),
        (
            "global EDA software market share leaders Synopsys Cadence Siemens EDA 2026",
            "top EDA companies Synopsys Cadence Siemens EDA Ansys market share 2026",
        ),
        (
            c("华大九天", "中国大陆", ["华大九天", "Empyrean"], "国内龙头", "国内EDA上市龙头，覆盖模拟/数字/制造/封装等EDA工具线。"),
            c("概伦电子", "中国大陆", ["概伦电子", "Primarius"], "细分龙头", "器件建模、PDK、良率提升等EDA点工具代表企业。"),
            c("广立微", "中国大陆", ["广立微", "Semitronix"], "细分龙头", "测试芯片、成品率提升与EDA数据分析领域代表企业。"),
            c("Synopsys", "海外", ["Synopsys", "新思"], "全球龙头", "全球EDA三巨头之一，覆盖设计、验证、IP和软件安全。"),
            c("Cadence", "海外", ["Cadence", "楷登"], "全球龙头", "全球EDA三巨头之一，模拟/数字设计和系统设计平台领先。"),
            c("Siemens EDA", "海外", ["Siemens EDA", "Mentor Graphics"], "全球龙头", "全球EDA三巨头之一，IC验证、DFT、PCB/封装设计工具领先。"),
        ),
    ),
    SubsegmentSpec(
        "上游/设计支撑",
        "EDA/IP",
        "半导体IP/芯片定制",
        "可复用IP核、接口IP、处理器IP和芯片定制服务。",
        (
            "中国 半导体 IP 龙头 芯原股份 芯和半导体 芯动科技 2026",
            "国产 芯片 IP 授权 芯片定制 龙头 芯原股份 芯和半导体",
        ),
        (
            "global semiconductor IP leaders Arm Synopsys Cadence Rambus Alphawave 2026",
            "semiconductor IP market share Arm Synopsys Cadence Rambus 2026",
        ),
        (
            c("芯原股份", "中国大陆", ["芯原股份", "芯原", "VeriSilicon"], "国内龙头", "国内半导体IP和一站式芯片定制服务代表企业。"),
            c("芯和半导体", "中国大陆", ["芯和半导体", "Xpeedic"], "细分龙头", "高速高频EDA/IP和Chiplet相关设计平台代表企业。"),
            c("Arm", "海外", ["Arm", "ARM"], "全球龙头", "CPU/GPU/NPU处理器IP生态全球领先。"),
            c("Synopsys", "海外", ["Synopsys", "新思"], "全球龙头", "接口IP、基础IP和EDA协同生态领先。"),
            c("Cadence", "海外", ["Cadence", "楷登"], "全球龙头", "接口IP、验证IP和EDA平台协同能力领先。"),
            c("Rambus", "海外", ["Rambus"], "细分龙头", "高速内存和接口IP代表企业。"),
            c("Alphawave", "海外", ["Alphawave", "Alphawave Semi"], "细分龙头", "高速连接IP和chiplet互连IP代表企业。"),
        ),
    ),
    SubsegmentSpec(
        "中游/设计与产品",
        "芯片设计/Fabless",
        "AI/GPU/CPU算力芯片",
        "AI训练/推理、GPU、CPU、DPU和定制加速芯片。",
        (
            "中国 AI 芯片 GPU CPU 龙头 寒武纪 海光信息 海思 摩尔线程 2026",
            "国产 算力芯片 龙头 寒武纪 海光信息 华为海思 澜起科技 2026",
        ),
        (
            "global AI GPU CPU accelerator chip leaders NVIDIA AMD Broadcom Marvell 2026",
            "AI semiconductor leaders NVIDIA AMD Broadcom custom ASIC Marvell 2026",
        ),
        (
            c("寒武纪", "中国大陆", ["寒武纪", "Cambricon"], "国内龙头", "国内AI训练/推理芯片代表企业。"),
            c("海光信息", "中国大陆", ["海光信息", "Hygon"], "国内龙头", "国产CPU/DCU算力芯片代表企业。"),
            c("海思", "中国大陆", ["海思", "HiSilicon"], "国内龙头", "华为旗下芯片设计平台，覆盖AI、通信和SoC。"),
            c("澜起科技", "中国大陆", ["澜起科技", "Montage"], "细分龙头", "内存接口芯片和CXL相关产品服务AI服务器。"),
            c("NVIDIA", "海外", ["NVIDIA", "英伟达"], "全球龙头", "AI GPU和加速计算生态全球领先。"),
            c("AMD", "海外", ["AMD"], "全球龙头", "CPU/GPU/AI加速器主要供应商。"),
            c("Broadcom", "海外", ["Broadcom", "博通"], "全球龙头", "网络芯片和定制AI ASIC代表企业。"),
            c("Marvell", "海外", ["Marvell", "迈威尔"], "细分龙头", "数据中心互连、网络和定制硅芯片代表企业。"),
        ),
    ),
    SubsegmentSpec(
        "中游/设计与产品",
        "芯片设计/Fabless",
        "手机SoC/通信基带",
        "移动SoC、蜂窝基带、射频前端和通信处理器。",
        (
            "中国 手机 SoC 基带 芯片设计 龙头 海思 紫光展锐 2026",
            "国产 通信芯片 手机SoC 龙头 海思 紫光展锐 卓胜微 2026",
        ),
        (
            "global smartphone SoC modem leaders Qualcomm MediaTek Apple Samsung 2026",
            "mobile application processor baseband market share Qualcomm MediaTek Apple 2026",
        ),
        (
            c("海思", "中国大陆", ["海思", "HiSilicon"], "国内龙头", "移动SoC、通信芯片和终端芯片平台代表企业。"),
            c("紫光展锐", "中国大陆", ["紫光展锐", "UNISOC"], "国内龙头", "手机SoC和蜂窝基带芯片国内代表企业。"),
            c("卓胜微", "中国大陆", ["卓胜微", "Maxscend"], "细分龙头", "射频前端芯片国内代表企业。"),
            c("Qualcomm", "海外", ["Qualcomm", "高通"], "全球龙头", "手机SoC、基带和无线通信专利生态领先。"),
            c("MediaTek", "中国台湾", ["MediaTek", "联发科"], "全球龙头", "移动SoC和连接芯片全球主要供应商。"),
            c("Apple", "海外", ["Apple", "苹果"], "细分龙头", "自研A/M系列SoC代表终端厂商垂直整合能力。"),
        ),
    ),
    SubsegmentSpec(
        "中游/设计与产品",
        "芯片设计/Fabless",
        "模拟/RF/MCU/传感器",
        "模拟芯片、射频、MCU、CIS图像传感器等产品。",
        (
            "中国 模拟芯片 射频 MCU CIS 龙头 韦尔股份 卓胜微 圣邦股份 兆易创新 2026",
            "国产 图像传感器 模拟芯片 MCU 龙头 韦尔 圣邦 兆易 卓胜微",
        ),
        (
            "global analog RF MCU image sensor semiconductor leaders Texas Instruments Analog Devices Sony NXP Infineon 2026",
            "top analog semiconductor companies Texas Instruments Analog Devices Infineon NXP 2026",
        ),
        (
            c("韦尔股份", "中国大陆", ["韦尔股份", "韦尔", "OmniVision"], "国内龙头", "CIS图像传感器和汽车/消费传感器代表企业。"),
            c("卓胜微", "中国大陆", ["卓胜微", "Maxscend"], "细分龙头", "射频前端芯片国内代表企业。"),
            c("圣邦股份", "中国大陆", ["圣邦股份", "SG Micro"], "细分龙头", "模拟芯片国内代表企业。"),
            c("兆易创新", "中国大陆", ["兆易创新", "GigaDevice"], "细分龙头", "NOR Flash、MCU和存储控制相关产品代表企业。"),
            c("Texas Instruments", "海外", ["Texas Instruments", "TI", "德州仪器"], "全球龙头", "模拟和嵌入式处理全球龙头。"),
            c("Analog Devices", "海外", ["Analog Devices", "ADI", "亚德诺"], "全球龙头", "高性能模拟、信号链和电源管理全球龙头。"),
            c("Sony", "海外", ["Sony", "索尼"], "全球龙头", "CIS图像传感器全球龙头。"),
            c("NXP", "海外", ["NXP", "恩智浦"], "细分龙头", "汽车、MCU和安全连接芯片全球主要厂商。"),
        ),
    ),
    SubsegmentSpec(
        "中游/制造",
        "晶圆制造/Foundry-IDM",
        "晶圆代工/Foundry",
        "为Fabless客户提供逻辑、成熟制程、特色工艺晶圆制造。",
        (
            "中国 晶圆代工 龙头 中芯国际 华虹半导体 晶合集成 市场份额 2026",
            "中国 成熟制程 特色工艺 晶圆代工 龙头 中芯国际 华虹 晶合集成",
        ),
        (
            "global foundry market share leaders TSMC Samsung UMC GlobalFoundries SMIC 2026",
            "top semiconductor foundry companies TSMC Samsung GlobalFoundries UMC SMIC 2026",
        ),
        (
            c("中芯国际", "中国大陆", ["中芯国际", "SMIC"], "国内龙头", "中国大陆晶圆代工规模和制程能力领先。"),
            c("华虹半导体", "中国大陆", ["华虹半导体", "华虹", "Hua Hong"], "国内龙头", "特色工艺和成熟制程代工代表企业。"),
            c("晶合集成", "中国大陆", ["晶合集成", "Nexchip"], "细分龙头", "显示驱动、CIS和成熟制程代工代表企业。"),
            c("TSMC", "中国台湾", ["TSMC", "台积电"], "全球龙头", "先进制程和晶圆代工份额全球领先。"),
            c("Samsung", "海外", ["Samsung", "三星"], "全球龙头", "先进逻辑代工和存储制造综合能力领先。"),
            c("GlobalFoundries", "海外", ["GlobalFoundries"], "全球龙头", "特色工艺和成熟制程代工全球主要厂商。"),
            c("UMC", "中国台湾", ["UMC", "联电"], "全球龙头", "成熟制程晶圆代工全球主要厂商。"),
        ),
    ),
    SubsegmentSpec(
        "中游/制造",
        "晶圆制造/Foundry-IDM",
        "IDM/特色工艺制造",
        "自有设计与制造一体化，覆盖模拟、功率、汽车和特色工艺。",
        (
            "中国 IDM 特色工艺 半导体制造 龙头 华润微 士兰微 闻泰科技 2026",
            "中国 模拟 功率 IDM 龙头 华润微 士兰微 闻泰科技 2026",
        ),
        (
            "global semiconductor IDM leaders Intel Samsung Texas Instruments STMicroelectronics Infineon 2026",
            "top integrated device manufacturers IDM semiconductor Intel Samsung TI Infineon ST 2026",
        ),
        (
            c("华润微", "中国大陆", ["华润微", "CR Micro"], "国内龙头", "功率器件、模拟和特色工艺制造一体化代表企业。"),
            c("士兰微", "中国大陆", ["士兰微", "Silan"], "国内龙头", "IDM模式覆盖功率、模拟和特色工艺。"),
            c("闻泰科技", "中国大陆", ["闻泰科技", "Nexperia"], "国内龙头", "通过Nexperia覆盖功率和分立器件IDM能力。"),
            c("Intel", "海外", ["Intel", "英特尔"], "全球龙头", "CPU和先进制造IDM代表企业。"),
            c("Samsung", "海外", ["Samsung", "三星"], "全球龙头", "存储、逻辑和代工综合IDM能力领先。"),
            c("Texas Instruments", "海外", ["Texas Instruments", "TI", "德州仪器"], "全球龙头", "模拟和嵌入式芯片IDM龙头。"),
            c("Infineon", "海外", ["Infineon", "英飞凌"], "全球龙头", "功率、汽车和安全芯片IDM龙头。"),
            c("STMicroelectronics", "海外", ["STMicroelectronics", "意法半导体"], "全球龙头", "汽车、工业、功率和MCU综合IDM厂商。"),
        ),
    ),
    SubsegmentSpec(
        "上游/制造支撑",
        "半导体设备",
        "光刻设备",
        "光刻机、涂胶显影及图形化关键设备。",
        (
            "中国 光刻设备 龙头 上海微电子 芯源微 2026",
            "国产 光刻机 涂胶显影设备 龙头 上海微电子 芯源微",
        ),
        (
            "global lithography equipment leaders ASML Nikon Canon market share 2026",
            "semiconductor lithography equipment market share ASML Nikon Canon 2026",
        ),
        (
            c("上海微电子", "中国大陆", ["上海微电子", "SMEE"], "国内龙头", "国产光刻机和图形化设备代表企业。"),
            c("芯源微", "中国大陆", ["芯源微"], "细分龙头", "涂胶显影和清洗设备国产代表企业。"),
            c("ASML", "海外", ["ASML", "阿斯麦"], "全球龙头", "EUV/DUV光刻设备全球核心供应商。"),
            c("Nikon", "海外", ["Nikon", "尼康"], "全球龙头", "DUV/i-line等光刻设备全球主要供应商。"),
            c("Canon", "海外", ["Canon", "佳能"], "全球龙头", "i-line、KrF和纳米压印等光刻设备代表厂商。"),
        ),
    ),
    SubsegmentSpec(
        "上游/制造支撑",
        "半导体设备",
        "刻蚀设备",
        "等离子刻蚀、介质刻蚀、硅刻蚀和深硅刻蚀设备。",
        (
            "中国 半导体 刻蚀设备 龙头 中微公司 北方华创 2026",
            "国产 刻蚀设备 市场 龙头 中微公司 北方华创",
        ),
        (
            "global etch equipment leaders Lam Research Applied Materials Tokyo Electron 2026",
            "semiconductor etch equipment market share Lam Research TEL Applied Materials 2026",
        ),
        (
            c("中微公司", "中国大陆", ["中微公司", "AMEC"], "国内龙头", "介质刻蚀、MOCVD和高端刻蚀设备国产代表。"),
            c("北方华创", "中国大陆", ["北方华创", "NAURA"], "国内龙头", "刻蚀、薄膜、清洗和热处理平台型设备企业。"),
            c("Lam Research", "海外", ["Lam Research", "泛林"], "全球龙头", "刻蚀和薄膜设备全球龙头。"),
            c("Applied Materials", "海外", ["Applied Materials", "AMAT", "应用材料"], "全球龙头", "刻蚀、沉积和工艺设备综合龙头。"),
            c("Tokyo Electron", "海外", ["Tokyo Electron", "TEL", "东京电子"], "全球龙头", "刻蚀、涂胶显影和沉积设备全球主要厂商。"),
        ),
    ),
    SubsegmentSpec(
        "上游/制造支撑",
        "半导体设备",
        "薄膜沉积设备",
        "PVD、CVD、ALD、外延等薄膜工艺设备。",
        (
            "中国 半导体 薄膜沉积设备 龙头 北方华创 拓荆科技 中微公司 2026",
            "国产 CVD ALD PVD 薄膜设备 龙头 拓荆科技 北方华创",
        ),
        (
            "global deposition equipment leaders Applied Materials Lam Research Tokyo Electron ASM International 2026",
            "semiconductor CVD ALD PVD equipment market leaders AMAT Lam TEL ASM 2026",
        ),
        (
            c("北方华创", "中国大陆", ["北方华创", "NAURA"], "国内龙头", "PVD、CVD、ALD等薄膜设备国产平台型企业。"),
            c("拓荆科技", "中国大陆", ["拓荆科技", "拓荆", "Piotech"], "国内龙头", "PECVD、ALD、SACVD等薄膜沉积设备代表企业。"),
            c("中微公司", "中国大陆", ["中微公司", "AMEC"], "细分龙头", "MOCVD和先进工艺设备代表企业。"),
            c("Applied Materials", "海外", ["Applied Materials", "AMAT", "应用材料"], "全球龙头", "沉积设备和材料工程解决方案全球龙头。"),
            c("Lam Research", "海外", ["Lam Research", "泛林"], "全球龙头", "沉积、刻蚀和清洗工艺设备全球主要厂商。"),
            c("Tokyo Electron", "海外", ["Tokyo Electron", "TEL", "东京电子"], "全球龙头", "沉积、涂胶显影和热处理设备全球主要厂商。"),
            c("ASM International", "海外", ["ASM International", "ASM"], "细分龙头", "ALD和外延沉积设备全球代表厂商。"),
        ),
    ),
    SubsegmentSpec(
        "上游/制造支撑",
        "半导体设备",
        "清洗/CMP/热处理设备",
        "清洗、CMP抛光、热处理和相关晶圆制程设备。",
        (
            "中国 半导体 清洗 CMP 热处理设备 龙头 盛美上海 华海清科 北方华创 2026",
            "国产 清洗设备 CMP设备 龙头 盛美上海 华海清科",
        ),
        (
            "global wafer cleaning CMP equipment leaders SCREEN Ebara Applied Materials 2026",
            "semiconductor cleaning CMP equipment market share SCREEN Ebara AMAT 2026",
        ),
        (
            c("盛美上海", "中国大陆", ["盛美上海", "盛美", "ACM Research"], "国内龙头", "半导体清洗和电镀设备国产代表企业。"),
            c("华海清科", "中国大陆", ["华海清科", "Hwatsing"], "国内龙头", "CMP设备国产代表企业。"),
            c("北方华创", "中国大陆", ["北方华创", "NAURA"], "细分龙头", "热处理、清洗和平台型设备能力覆盖广。"),
            c("SCREEN", "海外", ["SCREEN", "Screen Semiconductor"], "全球龙头", "晶圆清洗设备全球龙头之一。"),
            c("Ebara", "海外", ["Ebara", "荏原"], "全球龙头", "CMP设备和真空设备全球主要供应商。"),
            c("Applied Materials", "海外", ["Applied Materials", "AMAT", "应用材料"], "全球龙头", "CMP和多类工艺设备全球综合龙头。"),
        ),
    ),
    SubsegmentSpec(
        "上游/制造支撑",
        "半导体设备",
        "量测检测设备",
        "缺陷检测、薄膜量测、CD量测和过程控制设备。",
        (
            "中国 半导体 量测检测设备 龙头 中科飞测 精测电子 2026",
            "国产 半导体 检测量测设备 龙头 中科飞测 精测电子 上海睿励",
        ),
        (
            "global semiconductor metrology inspection equipment leaders KLA Onto Innovation Applied Materials 2026",
            "semiconductor process control equipment market share KLA Onto Applied Materials 2026",
        ),
        (
            c("中科飞测", "中国大陆", ["中科飞测"], "国内龙头", "半导体检测和量测设备国产代表企业。"),
            c("精测电子", "中国大陆", ["精测电子"], "细分龙头", "显示和半导体检测设备国产代表企业。"),
            c("KLA", "海外", ["KLA", "科磊"], "全球龙头", "过程控制、检测和量测设备全球龙头。"),
            c("Onto Innovation", "海外", ["Onto Innovation", "Onto"], "细分龙头", "量测、检测和先进封装过程控制代表厂商。"),
            c("Applied Materials", "海外", ["Applied Materials", "AMAT", "应用材料"], "全球龙头", "过程控制和工艺设备综合供应商。"),
        ),
    ),
    SubsegmentSpec(
        "上游/制造支撑",
        "半导体设备",
        "测试设备",
        "SoC、存储、模拟和功率器件测试机及分选设备。",
        (
            "中国 半导体 测试设备 龙头 华峰测控 长川科技 2026",
            "国产 半导体 测试机 分选机 龙头 华峰测控 长川科技",
        ),
        (
            "global semiconductor test equipment leaders Advantest Teradyne Cohu 2026",
            "semiconductor ATE market share Advantest Teradyne Cohu 2026",
        ),
        (
            c("华峰测控", "中国大陆", ["华峰测控"], "国内龙头", "模拟和功率半导体测试设备国产代表企业。"),
            c("长川科技", "中国大陆", ["长川科技"], "国内龙头", "测试机、分选机和探针台国产代表企业。"),
            c("Advantest", "海外", ["Advantest", "爱德万"], "全球龙头", "半导体ATE测试设备全球龙头。"),
            c("Teradyne", "海外", ["Teradyne", "泰瑞达"], "全球龙头", "SoC、存储和系统级测试设备全球龙头。"),
            c("Cohu", "海外", ["Cohu"], "细分龙头", "测试、分选和接口解决方案全球主要厂商。"),
        ),
    ),
    SubsegmentSpec(
        "上游/制造支撑",
        "半导体材料",
        "硅片",
        "半导体级硅片、外延片和相关晶圆基材。",
        (
            "中国 半导体 硅片 龙头 沪硅产业 TCL中环 立昂微 2026",
            "国产 半导体硅片 12英寸 龙头 沪硅产业 TCL中环 立昂微",
        ),
        (
            "global semiconductor silicon wafer leaders Shin-Etsu SUMCO GlobalWafers Siltronic 2026",
            "semiconductor silicon wafer market share Shin-Etsu SUMCO GlobalWafers Siltronic 2026",
        ),
        (
            c("沪硅产业", "中国大陆", ["沪硅产业", "NSIG"], "国内龙头", "中国大陆半导体硅片代表企业。"),
            c("TCL中环", "中国大陆", ["TCL中环", "TCL Zhonghuan"], "国内龙头", "大尺寸硅片和半导体材料布局代表企业。"),
            c("立昂微", "中国大陆", ["立昂微", "Lion Micro"], "细分龙头", "硅片、功率半导体和射频芯片制造布局代表企业。"),
            c("Shin-Etsu", "海外", ["Shin-Etsu", "信越"], "全球龙头", "半导体硅片全球龙头。"),
            c("SUMCO", "海外", ["SUMCO"], "全球龙头", "半导体硅片全球龙头。"),
            c("GlobalWafers", "中国台湾", ["GlobalWafers", "环球晶"], "全球龙头", "半导体硅片全球主要供应商。"),
            c("Siltronic", "海外", ["Siltronic"], "全球龙头", "半导体硅片全球主要供应商。"),
        ),
    ),
    SubsegmentSpec(
        "上游/制造支撑",
        "半导体材料",
        "光刻胶/配套材料",
        "光刻胶、显影液、BARC和光刻配套材料。",
        (
            "中国 半导体 光刻胶 龙头 彤程新材 南大光电 晶瑞电材 2026",
            "国产 光刻胶 半导体 材料 龙头 彤程新材 南大光电 晶瑞电材",
        ),
        (
            "global semiconductor photoresist leaders JSR TOK DuPont Shin-Etsu 2026",
            "photoresist market share semiconductor JSR Tokyo Ohka DuPont Shin-Etsu 2026",
        ),
        (
            c("彤程新材", "中国大陆", ["彤程新材"], "国内龙头", "半导体光刻胶和电子材料国产代表企业。"),
            c("南大光电", "中国大陆", ["南大光电"], "细分龙头", "ArF光刻胶、电子特气和MO源材料代表企业。"),
            c("晶瑞电材", "中国大陆", ["晶瑞电材"], "细分龙头", "光刻胶和湿电子化学品国产代表企业。"),
            c("JSR", "海外", ["JSR"], "全球龙头", "半导体光刻胶全球核心供应商。"),
            c("TOK", "海外", ["TOK", "Tokyo Ohka"], "全球龙头", "光刻胶和高纯化学品全球核心供应商。"),
            c("DuPont", "海外", ["DuPont", "杜邦"], "全球龙头", "光刻胶、CMP和电子材料全球主要供应商。"),
            c("Shin-Etsu", "海外", ["Shin-Etsu", "信越"], "全球龙头", "光刻胶、硅片和电子材料综合供应商。"),
        ),
    ),
    SubsegmentSpec(
        "上游/制造支撑",
        "半导体材料",
        "电子气体/湿电子化学品",
        "电子特气、高纯化学品、清洗和蚀刻用湿化学品。",
        (
            "中国 电子特气 湿电子化学品 龙头 华特气体 金宏气体 南大光电 江化微 2026",
            "国产 半导体电子气体 湿电子化学品 龙头 华特气体 金宏气体 江化微",
        ),
        (
            "global electronic gases wet chemicals semiconductor leaders Air Liquide Linde Merck Entegris 2026",
            "semiconductor electronic materials gases wet chemicals Air Liquide Linde Merck Entegris 2026",
        ),
        (
            c("华特气体", "中国大陆", ["华特气体"], "国内龙头", "电子特气国产代表企业。"),
            c("金宏气体", "中国大陆", ["金宏气体"], "细分龙头", "电子大宗气体和特种气体国产代表企业。"),
            c("南大光电", "中国大陆", ["南大光电"], "细分龙头", "电子特气、MO源和光刻胶多材料平台。"),
            c("江化微", "中国大陆", ["江化微"], "细分龙头", "湿电子化学品国产代表企业。"),
            c("Air Liquide", "海外", ["Air Liquide", "液化空气"], "全球龙头", "半导体电子气体全球核心供应商。"),
            c("Linde", "海外", ["Linde", "林德"], "全球龙头", "电子气体和工业气体全球龙头。"),
            c("Merck KGaA", "海外", ["Merck KGaA", "默克"], "全球龙头", "电子材料和高纯化学品全球主要供应商。"),
            c("Entegris", "海外", ["Entegris"], "全球龙头", "电子材料、过滤和高纯化学品全球供应商。"),
        ),
    ),
    SubsegmentSpec(
        "上游/制造支撑",
        "半导体材料",
        "靶材",
        "溅射靶材、金属材料和先进制程薄膜材料。",
        (
            "中国 半导体 靶材 龙头 江丰电子 有研新材 2026",
            "国产 溅射靶材 半导体 龙头 江丰电子 有研新材",
        ),
        (
            "global semiconductor sputtering target leaders JX Advanced Metals Tosoh Materion 2026",
            "semiconductor target materials market leaders JX Nippon Tosoh Materion 2026",
        ),
        (
            c("江丰电子", "中国大陆", ["江丰电子"], "国内龙头", "高纯溅射靶材国产代表企业。"),
            c("有研新材", "中国大陆", ["有研新材"], "细分龙头", "高纯金属材料和靶材国产代表企业。"),
            c("JX Advanced Metals", "海外", ["JX Advanced Metals", "JX Nippon", "JX金属"], "全球龙头", "半导体靶材和高纯金属材料全球核心供应商。"),
            c("Tosoh", "海外", ["Tosoh", "东曹"], "全球龙头", "溅射靶材和电子材料全球主要供应商。"),
            c("Materion", "海外", ["Materion"], "细分龙头", "高性能材料和靶材全球供应商。"),
        ),
    ),
    SubsegmentSpec(
        "上游/制造支撑",
        "半导体材料",
        "CMP材料",
        "CMP抛光液、抛光垫和相关平坦化材料。",
        (
            "中国 CMP 抛光液 抛光垫 龙头 安集科技 鼎龙股份 2026",
            "国产 半导体 CMP材料 龙头 安集科技 鼎龙股份",
        ),
        (
            "global CMP slurry pad semiconductor materials leaders Entegris DuPont Fujimi 2026",
            "CMP materials market share semiconductor Entegris DuPont Fujimi 2026",
        ),
        (
            c("安集科技", "中国大陆", ["安集科技", "Anji"], "国内龙头", "CMP抛光液和湿电子化学品国产代表企业。"),
            c("鼎龙股份", "中国大陆", ["鼎龙股份"], "细分龙头", "CMP抛光垫和半导体材料国产代表企业。"),
            c("Entegris", "海外", ["Entegris"], "全球龙头", "CMP材料、过滤和电子材料全球供应商。"),
            c("DuPont", "海外", ["DuPont", "杜邦"], "全球龙头", "CMP垫、光刻胶和电子材料全球主要供应商。"),
            c("Fujimi", "海外", ["Fujimi", "FUJIMI"], "细分龙头", "CMP抛光材料全球代表供应商。"),
        ),
    ),
    SubsegmentSpec(
        "上游/制造支撑",
        "半导体材料",
        "封装材料/IC载板",
        "ABF载板、BT载板、封装基板和封装材料。",
        (
            "中国 IC载板 封装材料 龙头 兴森科技 深南电路 生益科技 2026",
            "国产 ABF载板 BT载板 封装基板 龙头 兴森科技 深南电路 生益科技",
        ),
        (
            "global ABF substrate IC substrate leaders Ibiden Shinko Unimicron Nan Ya 2026",
            "IC substrate market share leaders Ibiden Shinko Unimicron Nan Ya 2026",
        ),
        (
            c("兴森科技", "中国大陆", ["兴森科技"], "国内龙头", "IC载板和封装基板国产代表企业。"),
            c("深南电路", "中国大陆", ["深南电路"], "国内龙头", "封装基板和PCB制造国产代表企业。"),
            c("生益科技", "中国大陆", ["生益科技"], "细分龙头", "覆铜板和电子材料国产代表企业。"),
            c("Ibiden", "海外", ["Ibiden", "揖斐电"], "全球龙头", "ABF载板全球核心供应商。"),
            c("Shinko Electric", "海外", ["Shinko Electric", "新光电气"], "全球龙头", "高端封装基板全球主要供应商。"),
            c("Unimicron", "中国台湾", ["Unimicron", "欣兴"], "全球龙头", "IC载板和PCB全球主要供应商。"),
            c("Nan Ya PCB", "中国台湾", ["Nan Ya PCB", "南亚电路"], "细分龙头", "IC载板全球主要供应商。"),
        ),
    ),
    SubsegmentSpec(
        "中游/封装测试",
        "先进封装",
        "2.5D/3D/Chiplet先进封装",
        "CoWoS、Fan-out、Foveros、Chiplet和异构集成。",
        (
            "中国 先进封装 Chiplet 2.5D 3D 龙头 长电科技 通富微电 华天科技 甬矽电子 2026",
            "国产 先进封装 龙头 长电科技 通富微电 华天科技 盛合晶微",
        ),
        (
            "global advanced packaging CoWoS 2.5D 3D leaders TSMC ASE Amkor Intel Samsung 2026",
            "advanced packaging market leaders TSMC ASE Amkor Intel Samsung SK hynix 2026",
        ),
        (
            c("长电科技", "中国大陆", ["长电科技", "JCET"], "国内龙头", "中国大陆封测和先进封装代表企业。"),
            c("通富微电", "中国大陆", ["通富微电", "TFME"], "国内龙头", "AMD等客户协同和先进封装能力代表企业。"),
            c("华天科技", "中国大陆", ["华天科技", "Huatian"], "国内龙头", "国内封测和先进封装能力代表企业。"),
            c("甬矽电子", "中国大陆", ["甬矽电子"], "细分龙头", "先进封装和系统级封装代表企业。"),
            c("TSMC", "中国台湾", ["TSMC", "台积电", "CoWoS"], "全球龙头", "CoWoS和先进逻辑封装产能全球核心。"),
            c("ASE", "中国台湾", ["ASE", "日月光"], "全球龙头", "全球OSAT和先进封装龙头。"),
            c("Amkor", "海外", ["Amkor", "安靠"], "全球龙头", "全球OSAT和先进封装主要厂商。"),
            c("Intel", "海外", ["Intel", "英特尔", "Foveros"], "细分龙头", "Foveros、EMIB等先进封装技术代表。"),
            c("Samsung", "海外", ["Samsung", "三星", "I-Cube"], "全球龙头", "先进封装和存储/逻辑制造协同能力领先。"),
            c("SK hynix", "海外", ["SK hynix", "海力士"], "细分龙头", "HBM堆叠与先进封装能力服务AI存储。"),
        ),
    ),
    SubsegmentSpec(
        "中游/封装测试",
        "传统封装测试/OSAT",
        "传统OSAT封装测试",
        "传统封装、测试和后段制造服务。",
        (
            "中国 OSAT 封装测试 龙头 长电科技 通富微电 华天科技 晶方科技 2026",
            "中国 封测 排名 龙头 长电 通富 华天 晶方",
        ),
        (
            "global OSAT leaders ASE Amkor JCET Powertech KYEC ChipMOS 2026",
            "top outsourced semiconductor assembly test companies ASE Amkor JCET Powertech 2026",
        ),
        (
            c("长电科技", "中国大陆", ["长电科技", "JCET"], "国内龙头", "中国大陆封测规模龙头。"),
            c("通富微电", "中国大陆", ["通富微电", "TFME"], "国内龙头", "中国大陆封测龙头之一，覆盖CPU/GPU等封装测试。"),
            c("华天科技", "中国大陆", ["华天科技", "Huatian"], "国内龙头", "中国大陆封测龙头之一。"),
            c("晶方科技", "中国大陆", ["晶方科技"], "细分龙头", "CIS晶圆级封装代表企业。"),
            c("ASE", "中国台湾", ["ASE", "日月光"], "全球龙头", "全球OSAT龙头。"),
            c("Amkor", "海外", ["Amkor"], "全球龙头", "全球OSAT主要厂商。"),
            c("Powertech", "中国台湾", ["Powertech", "PTI", "力成"], "全球龙头", "存储封测和OSAT全球主要厂商。"),
            c("KYEC", "中国台湾", ["KYEC", "King Yuan", "京元电子"], "细分龙头", "独立测试和封测服务代表企业。"),
            c("ChipMOS", "中国台湾", ["ChipMOS"], "细分龙头", "显示驱动和存储封测代表企业。"),
        ),
    ),
    SubsegmentSpec(
        "中游/产品与制造",
        "存储/HBM",
        "DRAM/HBM",
        "DRAM、HBM高带宽存储及AI服务器存储产品。",
        (
            "中国 DRAM HBM 存储 龙头 长鑫存储 兆易创新 2026",
            "国产 DRAM 存储芯片 龙头 长鑫存储 HBM 2026",
        ),
        (
            "global DRAM HBM leaders SK hynix Samsung Micron market share 2026",
            "HBM market share leaders SK hynix Samsung Micron 2026",
        ),
        (
            c("长鑫存储", "中国大陆", ["长鑫存储", "CXMT"], "国内龙头", "中国大陆DRAM制造代表企业。"),
            c("兆易创新", "中国大陆", ["兆易创新", "GigaDevice"], "细分龙头", "存储和MCU设计代表企业，覆盖Nor Flash等产品。"),
            c("SK hynix", "海外", ["SK hynix", "海力士"], "全球龙头", "HBM和DRAM全球龙头之一。"),
            c("Samsung", "海外", ["Samsung", "三星"], "全球龙头", "DRAM、NAND和HBM综合存储龙头。"),
            c("Micron", "海外", ["Micron", "美光"], "全球龙头", "DRAM、NAND和HBM全球主要厂商。"),
        ),
    ),
    SubsegmentSpec(
        "中游/产品与制造",
        "存储/HBM",
        "NAND Flash",
        "NAND闪存、3D NAND和存储晶圆制造。",
        (
            "中国 NAND Flash 龙头 长江存储 2026",
            "国产 3D NAND 存储 龙头 长江存储 2026",
        ),
        (
            "global NAND flash leaders Samsung Kioxia Western Digital Micron SK hynix 2026",
            "NAND flash market share leaders Samsung Kioxia Western Digital Micron SK hynix 2026",
        ),
        (
            c("长江存储", "中国大陆", ["长江存储", "YMTC"], "国内龙头", "中国大陆3D NAND制造代表企业。"),
            c("Samsung", "海外", ["Samsung", "三星"], "全球龙头", "NAND和存储综合龙头。"),
            c("Kioxia", "海外", ["Kioxia", "铠侠"], "全球龙头", "NAND Flash全球主要厂商。"),
            c("Western Digital", "海外", ["Western Digital", "西部数据"], "全球龙头", "NAND和存储产品全球主要厂商。"),
            c("Micron", "海外", ["Micron", "美光"], "全球龙头", "NAND和DRAM全球主要厂商。"),
            c("SK hynix", "海外", ["SK hynix", "海力士"], "全球龙头", "NAND和DRAM全球主要厂商。"),
        ),
    ),
    SubsegmentSpec(
        "中游/产品与制造",
        "存储/HBM",
        "存储控制/模组/NOR",
        "NOR Flash、存储控制器、企业级/消费级存储模组。",
        (
            "中国 NOR Flash 存储模组 龙头 兆易创新 江波龙 佰维存储 北京君正 2026",
            "国产 存储控制 模组 NOR 龙头 兆易创新 江波龙 佰维存储",
        ),
        (
            "global NOR flash memory controller module leaders Winbond Macronix Phison Kingston 2026",
            "NOR flash market leaders Winbond Macronix GigaDevice 2026",
        ),
        (
            c("兆易创新", "中国大陆", ["兆易创新", "GigaDevice"], "国内龙头", "NOR Flash和MCU国内代表企业。"),
            c("江波龙", "中国大陆", ["江波龙", "Longsys"], "国内龙头", "存储模组和嵌入式存储产品代表企业。"),
            c("佰维存储", "中国大陆", ["佰维存储", "Biwin"], "细分龙头", "存储模组和封测一体化代表企业。"),
            c("北京君正", "中国大陆", ["北京君正"], "细分龙头", "车规存储、处理器和模拟互补产品代表企业。"),
            c("Winbond", "中国台湾", ["Winbond", "华邦"], "全球龙头", "NOR Flash和利基型DRAM代表厂商。"),
            c("Macronix", "中国台湾", ["Macronix", "旺宏"], "全球龙头", "NOR Flash全球主要供应商。"),
            c("Phison", "中国台湾", ["Phison", "群联"], "细分龙头", "NAND控制器和存储解决方案代表厂商。"),
            c("Kingston", "海外", ["Kingston", "金士顿"], "细分龙头", "存储模组和品牌存储产品全球代表企业。"),
        ),
    ),
    SubsegmentSpec(
        "中游/特色器件",
        "功率半导体/SiC-GaN",
        "功率器件/模块",
        "IGBT、MOSFET、功率模块和汽车/工业功率器件。",
        (
            "中国 功率半导体 IGBT MOSFET 模块 龙头 斯达半导 士兰微 华润微 闻泰科技 2026",
            "国产 功率器件 龙头 斯达半导 士兰微 华润微 新洁能 2026",
        ),
        (
            "global power semiconductor leaders Infineon STMicroelectronics onsemi ROHM Mitsubishi 2026",
            "power semiconductor market share leaders Infineon ST onsemi ROHM Mitsubishi 2026",
        ),
        (
            c("斯达半导", "中国大陆", ["斯达半导", "StarPower"], "国内龙头", "IGBT模块和功率模块国内代表企业。"),
            c("士兰微", "中国大陆", ["士兰微", "Silan"], "国内龙头", "功率器件IDM和特色工艺代表企业。"),
            c("华润微", "中国大陆", ["华润微", "CR Micro"], "国内龙头", "功率器件、模拟和制造一体化代表企业。"),
            c("新洁能", "中国大陆", ["新洁能"], "细分龙头", "MOSFET和功率器件设计代表企业。"),
            c("Infineon", "海外", ["Infineon", "英飞凌"], "全球龙头", "功率半导体和汽车功率器件全球龙头。"),
            c("STMicroelectronics", "海外", ["STMicroelectronics", "意法半导体"], "全球龙头", "汽车和工业功率半导体全球主要厂商。"),
            c("onsemi", "海外", ["onsemi", "安森美"], "全球龙头", "功率、汽车和SiC器件全球主要厂商。"),
            c("ROHM", "海外", ["ROHM", "罗姆"], "全球龙头", "功率器件和SiC解决方案全球主要厂商。"),
            c("Mitsubishi Electric", "海外", ["Mitsubishi Electric", "三菱电机"], "细分龙头", "IGBT和功率模块全球代表厂商。"),
        ),
    ),
    SubsegmentSpec(
        "中游/特色器件",
        "功率半导体/SiC-GaN",
        "SiC衬底/外延",
        "碳化硅衬底、外延片和上游材料。",
        (
            "中国 SiC 衬底 外延 龙头 天岳先进 天科合达 三安光电 2026",
            "国产 碳化硅 衬底 龙头 天岳先进 天科合达 2026",
        ),
        (
            "global SiC substrate wafer leaders Wolfspeed Coherent ROHM SK siltron 2026",
            "silicon carbide substrate market share leaders Wolfspeed Coherent SK siltron ROHM 2026",
        ),
        (
            c("天岳先进", "中国大陆", ["天岳先进"], "国内龙头", "SiC衬底国产代表企业。"),
            c("天科合达", "中国大陆", ["天科合达"], "国内龙头", "SiC衬底国产代表企业。"),
            c("三安光电", "中国大陆", ["三安光电", "Sanan"], "细分龙头", "SiC/GaN化合物半导体材料和器件布局代表企业。"),
            c("Wolfspeed", "海外", ["Wolfspeed"], "全球龙头", "SiC材料和器件全球核心厂商。"),
            c("Coherent", "海外", ["Coherent"], "全球龙头", "SiC衬底和化合物材料全球主要供应商。"),
            c("SK siltron", "海外", ["SK siltron", "SK Siltron"], "细分龙头", "SiC和硅片材料全球供应商。"),
            c("ROHM", "海外", ["ROHM", "罗姆"], "全球龙头", "SiC材料、器件和模块一体化厂商。"),
        ),
    ),
    SubsegmentSpec(
        "中游/特色器件",
        "功率半导体/SiC-GaN",
        "SiC功率器件/模块",
        "SiC MOSFET、二极管、功率模块和车规应用。",
        (
            "中国 SiC 功率器件 模块 龙头 三安光电 斯达半导 士兰微 闻泰科技 2026",
            "国产 SiC MOSFET 功率模块 龙头 三安光电 斯达半导 士兰微",
        ),
        (
            "global SiC power device leaders Infineon STMicroelectronics Wolfspeed onsemi ROHM 2026",
            "SiC MOSFET power module market leaders Infineon ST Wolfspeed onsemi ROHM 2026",
        ),
        (
            c("三安光电", "中国大陆", ["三安光电", "Sanan"], "国内龙头", "SiC/GaN化合物半导体制造和器件布局代表企业。"),
            c("斯达半导", "中国大陆", ["斯达半导", "StarPower"], "国内龙头", "功率模块和SiC模块布局代表企业。"),
            c("士兰微", "中国大陆", ["士兰微", "Silan"], "国内龙头", "SiC功率器件和IDM能力布局代表企业。"),
            c("闻泰科技", "中国大陆", ["闻泰科技", "Nexperia"], "细分龙头", "功率半导体和车规分立器件代表企业。"),
            c("Infineon", "海外", ["Infineon", "英飞凌"], "全球龙头", "SiC功率器件和汽车功率全球龙头。"),
            c("STMicroelectronics", "海外", ["STMicroelectronics", "意法半导体"], "全球龙头", "SiC功率器件和汽车应用全球主要厂商。"),
            c("Wolfspeed", "海外", ["Wolfspeed"], "全球龙头", "SiC材料和器件全球代表企业。"),
            c("onsemi", "海外", ["onsemi", "安森美"], "全球龙头", "SiC功率器件和汽车应用全球主要厂商。"),
            c("ROHM", "海外", ["ROHM", "罗姆"], "全球龙头", "SiC功率器件和模块全球主要厂商。"),
        ),
    ),
    SubsegmentSpec(
        "中游/特色器件",
        "功率半导体/SiC-GaN",
        "GaN功率/RF器件",
        "氮化镓功率器件、射频器件和快充/通信应用。",
        (
            "中国 GaN 功率 射频 器件 龙头 英诺赛科 三安光电 2026",
            "国产 氮化镓 功率器件 龙头 英诺赛科 三安光电",
        ),
        (
            "global GaN power device leaders Navitas EPC Infineon Renesas Transphorm 2026",
            "GaN power semiconductor market leaders Navitas EPC Infineon Transphorm Renesas 2026",
        ),
        (
            c("英诺赛科", "中国大陆", ["英诺赛科", "Innoscience"], "国内龙头", "GaN功率器件和8英寸GaN-on-Si量产代表企业。"),
            c("三安光电", "中国大陆", ["三安光电", "Sanan"], "国内龙头", "GaN射频和化合物半导体制造代表企业。"),
            c("Navitas", "海外", ["Navitas"], "全球龙头", "GaN功率芯片全球代表企业。"),
            c("EPC", "海外", ["EPC", "Efficient Power Conversion"], "全球龙头", "GaN功率器件全球代表企业。"),
            c("Infineon", "海外", ["Infineon", "英飞凌"], "全球龙头", "GaN和功率半导体综合龙头。"),
            c("Renesas", "海外", ["Renesas", "瑞萨"], "细分龙头", "通过收购和产品布局覆盖GaN功率器件。"),
            c("Transphorm", "海外", ["Transphorm"], "细分龙头", "GaN功率器件代表企业，现属瑞萨体系。"),
        ),
    ),
    SubsegmentSpec(
        "下游/系统需求",
        "终端应用/系统需求",
        "AI服务器/云基础设施",
        "AI服务器、云计算、数据中心和AI基础设施需求端。",
        (
            "中国 AI服务器 云基础设施 龙头 浪潮信息 工业富联 中科曙光 联想 2026",
            "中国 AI服务器 产业链 龙头 浪潮信息 工业富联 联想 中科曙光",
        ),
        (
            "global AI server cloud infrastructure leaders Dell Supermicro Microsoft Amazon Google Meta 2026",
            "AI server market leaders Dell Supermicro cloud Microsoft Amazon Google Meta 2026",
        ),
        (
            c("浪潮信息", "中国大陆", ["浪潮信息", "Inspur"], "需求端龙头", "AI服务器和数据中心服务器国内代表企业。"),
            c("工业富联", "中国大陆", ["工业富联", "Foxconn Industrial Internet", "FII"], "需求端龙头", "AI服务器制造和云基础设施制造代表企业。"),
            c("中科曙光", "中国大陆", ["中科曙光", "Sugon"], "需求端龙头", "高性能计算和服务器国内代表企业。"),
            c("联想", "中国大陆", ["联想", "Lenovo"], "需求端龙头", "服务器、PC和AI终端系统全球主要厂商。"),
            c("Dell", "海外", ["Dell"], "需求端龙头", "服务器和企业基础设施全球主要厂商。"),
            c("Supermicro", "海外", ["Supermicro", "Super Micro"], "需求端龙头", "AI服务器和高密度服务器全球代表企业。"),
            c("Microsoft", "海外", ["Microsoft", "微软"], "需求端龙头", "云计算和AI基础设施需求核心厂商。"),
            c("Amazon", "海外", ["Amazon", "AWS"], "需求端龙头", "云计算和自研AI芯片/数据中心需求核心厂商。"),
            c("Google", "海外", ["Google", "谷歌"], "需求端龙头", "云计算、TPU和AI基础设施需求核心厂商。"),
            c("Meta", "海外", ["Meta"], "需求端龙头", "AI训练集群和数据中心需求核心厂商。"),
        ),
    ),
    SubsegmentSpec(
        "下游/系统需求",
        "终端应用/系统需求",
        "新能源汽车/汽车电子",
        "新能源车、智能驾驶、车载计算和汽车电子需求端。",
        (
            "中国 新能源汽车 汽车电子 龙头 比亚迪 华为 2026",
            "中国 智能汽车 半导体需求 龙头 比亚迪 华为 蔚来 小鹏 理想 2026",
        ),
        (
            "global electric vehicle automotive electronics leaders Tesla Bosch Denso Continental 2026",
            "automotive semiconductor demand leaders Tesla Bosch Denso Continental 2026",
        ),
        (
            c("比亚迪", "中国大陆", ["比亚迪", "BYD"], "需求端龙头", "新能源汽车和功率半导体/汽车电子需求端代表。"),
            c("华为", "中国大陆", ["华为", "Huawei"], "需求端龙头", "智能汽车解决方案、通信和终端生态需求代表。"),
            c("Tesla", "海外", ["Tesla", "特斯拉"], "需求端龙头", "新能源汽车、智能驾驶和功率/算力芯片需求代表。"),
            c("Bosch", "海外", ["Bosch", "博世"], "需求端龙头", "汽车电子和功率/传感器系统全球Tier 1。"),
            c("Denso", "海外", ["Denso", "电装"], "需求端龙头", "汽车电子和功率模块全球Tier 1。"),
            c("Continental", "海外", ["Continental", "大陆集团"], "需求端龙头", "汽车电子和智能驾驶系统全球Tier 1。"),
        ),
    ),
    SubsegmentSpec(
        "下游/系统需求",
        "终端应用/系统需求",
        "消费电子/通信设备",
        "智能手机、PC、通信设备、网络设备和终端生态。",
        (
            "中国 消费电子 通信设备 龙头 华为 小米 中兴通讯 联想 2026",
            "中国 半导体 下游 终端需求 龙头 华为 小米 中兴通讯 联想",
        ),
        (
            "global consumer electronics telecom equipment leaders Apple Samsung Cisco Ericsson Nokia 2026",
            "semiconductor demand consumer electronics telecom equipment leaders Apple Samsung Cisco Ericsson Nokia 2026",
        ),
        (
            c("华为", "中国大陆", ["华为", "Huawei"], "需求端龙头", "通信设备、手机、AI和智能终端生态代表。"),
            c("小米", "中国大陆", ["小米", "Xiaomi"], "需求端龙头", "智能手机、IoT和汽车终端需求代表。"),
            c("中兴通讯", "中国大陆", ["中兴通讯", "ZTE"], "需求端龙头", "通信设备和算力基础设施需求代表。"),
            c("联想", "中国大陆", ["联想", "Lenovo"], "需求端龙头", "PC、服务器和AI终端需求代表。"),
            c("Apple", "海外", ["Apple", "苹果"], "需求端龙头", "消费电子和自研芯片需求全球代表。"),
            c("Samsung", "海外", ["Samsung", "三星"], "需求端龙头", "消费电子、存储和显示终端生态全球代表。"),
            c("Cisco", "海外", ["Cisco", "思科"], "需求端龙头", "网络设备和数据中心通信需求代表。"),
            c("Ericsson", "海外", ["Ericsson", "爱立信"], "需求端龙头", "通信设备和5G基础设施全球主要厂商。"),
            c("Nokia", "海外", ["Nokia", "诺基亚"], "需求端龙头", "通信设备和网络基础设施全球主要厂商。"),
        ),
    ),
)


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)


def candidate_keywords(spec: SubsegmentSpec) -> dict[str, list[str]]:
    return {candidate.name: list(candidate.aliases) for candidate in spec.candidates}


def query_side_label(query_type: str) -> str:
    return "国内线索" if query_type == "domestic" else "境外线索"


def run_searches() -> list[dict[str, Any]]:
    evidence_rows: list[dict[str, Any]] = []
    evidence_id = 1

    for spec in SUBSEGMENTS:
        query_groups = (
            ("domestic", "Bocha", spec.domestic_queries),
            ("global", "Tavily", spec.global_queries),
        )
        keywords = candidate_keywords(spec)
        for query_type, tool, queries in query_groups:
            for query in queries:
                try:
                    rows = s2.search_bocha(query, count=6) if tool == "Bocha" else s2.search_tavily(query, count=6)
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
                time.sleep(0.25)
                for row in rows:
                    text = " ".join([row.get("title", ""), row.get("snippet", ""), row.get("url", "")])
                    entities = s2.find_company_hits(text, keywords)
                    ev_id = f"E3-{evidence_id:03d}"
                    evidence_id += 1
                    evidence_rows.append(
                        {
                            "evidence_id": ev_id,
                            "task_id": "S3-segment-leader-matching",
                            "question": f"{spec.value_chain_layer}/{spec.major_segment}/{spec.subsegment_name} 的龙头企业有哪些？",
                            "value_chain_layer": spec.value_chain_layer,
                            "major_segment": spec.major_segment,
                            "subsegment_name": spec.subsegment_name,
                            "subsegment_role": spec.subsegment_role,
                            "query_side": query_side_label(query_type),
                            "source_title": row.get("title", ""),
                            "source_url_or_file": row.get("url", ""),
                            "source_type": "industry_search",
                            "publish_date": row.get("publish_date", ""),
                            "entities": entities,
                            "evidence_excerpt": (row.get("snippet", "") or "")[:1000],
                            "possible_claim": (
                                f"该来源可作为 {spec.subsegment_name} 子环节龙头企业匹配线索，"
                                "仍需结合业务归属、市场地位、技术壁垒和客户/产能证据判断。"
                            ),
                            "claim_type_guess": "segment_leader_match",
                            "confidence": "medium" if entities else "low",
                            "limitations": "搜索结果层证据；最终龙头判断需优先核验年报、招股书、IR、行业份额报告。",
                            "retrieved_at": NOW,
                            "source_grade": s2.source_grade(row.get("url", ""), row.get("title", "")),
                            "search_tool": row.get("search_tool", tool),
                            "query": query,
                        }
                    )
    return evidence_rows


def evidence_score(evidence_ids: list[str], evidence_by_id: dict[str, dict[str, Any]]) -> tuple[str, int]:
    grades = [evidence_by_id[eid].get("source_grade", "B-") for eid in evidence_ids if eid in evidence_by_id]
    grade_rank = {"A": 4, "A-": 3, "B": 2, "B-": 1}
    best = max((grade_rank.get(g, 1) for g in grades), default=1)
    if len(evidence_ids) >= 4 or best >= 3:
        return "high", best
    if len(evidence_ids) >= 2:
        return "medium", best
    return "medium-low", best


def build_leader_rows(evidence_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence_by_id = {row["evidence_id"]: row for row in evidence_rows}
    hit_map: dict[tuple[str, str, str, str], list[str]] = {}

    for evidence in evidence_rows:
        key_prefix = (
            evidence["value_chain_layer"],
            evidence["major_segment"],
            evidence["subsegment_name"],
        )
        for entity in evidence.get("entities", []) or []:
            hit_map.setdefault((*key_prefix, entity), []).append(evidence["evidence_id"])

    rows: list[dict[str, Any]] = []
    for spec in SUBSEGMENTS:
        for candidate in spec.candidates:
            key = (spec.value_chain_layer, spec.major_segment, spec.subsegment_name, candidate.name)
            evidence_ids = sorted(set(hit_map.get(key, [])))
            if not evidence_ids:
                continue
            confidence, _ = evidence_score(evidence_ids, evidence_by_id)
            urls = []
            for eid in evidence_ids:
                url = evidence_by_id[eid].get("source_url_or_file", "")
                if url and url not in urls:
                    urls.append(url)
            rows.append(
                {
                    "value_chain_layer": spec.value_chain_layer,
                    "major_segment": spec.major_segment,
                    "subsegment_name": spec.subsegment_name,
                    "subsegment_role": spec.subsegment_role,
                    "company_name": candidate.name,
                    "company_region": candidate.region,
                    "leader_level": candidate.leader_level,
                    "selection_basis": candidate.basis,
                    "evidence_ids": ";".join(evidence_ids),
                    "evidence_count": str(len(evidence_ids)),
                    "source_urls": " | ".join(urls[:5]),
                    "confidence": confidence,
                    "limitations": "同一公司可重复出现在不同环节；本行只表示其在该子环节具备龙头/代表性地位线索。",
                }
            )

    order = {(
        spec.value_chain_layer,
        spec.major_segment,
        spec.subsegment_name,
    ): idx for idx, spec in enumerate(SUBSEGMENTS)}
    return sorted(
        rows,
        key=lambda row: (
            order[(row["value_chain_layer"], row["major_segment"], row["subsegment_name"])],
            row["company_region"],
            row["company_name"],
        ),
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "value_chain_layer",
        "major_segment",
        "subsegment_name",
        "subsegment_role",
        "company_name",
        "company_region",
        "leader_level",
        "selection_basis",
        "evidence_ids",
        "evidence_count",
        "source_urls",
        "confidence",
        "limitations",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def format_company_cell(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "待补充"
    return "<br>".join(
        f"{row['company_name']}（{row['leader_level']}：{row['selection_basis']}）"
        for row in rows
    )


def write_summary(path: Path, rows: list[dict[str, Any]]) -> None:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (row["value_chain_layer"], row["major_segment"], row["subsegment_name"])
        grouped.setdefault(key, []).append(row)

    lines = [
        "# Stage 3 半导体产业链环节龙头公司匹配表",
        "",
        f"- 生成时间：{NOW}",
        f"- 子环节数量：{len(SUBSEGMENTS)} 个",
        f"- 龙头匹配记录：{len(rows)} 条",
        "- 口径：不强制限定每个子环节公司数量；只要符合龙头/细分龙头标准且搜索证据命中即可保留。",
        "- 重要规则：同一家公司可以重复出现在不同环节，但每一行只代表它在对应子环节的角色。",
        "",
        "## 龙头判断标准",
        "",
        "1. 业务归属：主营业务、核心产品或产能必须直接落在该子环节。",
        "2. 市场地位：优先采用市场份额、行业排名、规模、出货量或产能证据。",
        "3. 技术壁垒：先进制程、专利/IP、设备工艺、材料纯度、封装能力等可形成代表性。",
        "4. 客户/生态：进入头部客户供应链、形成平台生态或绑定关键应用需求。",
        "5. 证据等级：搜索证据只是初筛，最终应优先回到年报、招股书、IR和行业份额报告。",
        "",
        "| 上下游 | 大环节 | 子环节 | 中国大陆龙头/依据 | 中国台湾龙头/依据 | 海外龙头/依据 |",
        "|---|---|---|---|---|---|",
    ]
    for spec in SUBSEGMENTS:
        key = (spec.value_chain_layer, spec.major_segment, spec.subsegment_name)
        sub_rows = grouped.get(key, [])
        mainland = [row for row in sub_rows if row["company_region"] == "中国大陆"]
        taiwan = [row for row in sub_rows if row["company_region"] == "中国台湾"]
        overseas = [row for row in sub_rows if row["company_region"] == "海外"]
        lines.append(
            "| "
            + " | ".join(
                [
                    spec.value_chain_layer,
                    spec.major_segment,
                    spec.subsegment_name,
                    format_company_cell(mainland),
                    format_company_cell(taiwan),
                    format_company_cell(overseas),
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
    if "--from-existing-evidence" in sys.argv:
        evidence_rows = load_existing_evidence()
    else:
        evidence_rows = run_searches()
        write_jsonl(EVIDENCE_PATH, evidence_rows)
    leader_rows = build_leader_rows(evidence_rows)
    write_csv(LEADERS_PATH, leader_rows)
    write_summary(SUMMARY_PATH, leader_rows)
    print(
        json.dumps(
            {
                "subsegments": len(SUBSEGMENTS),
                "evidence": len(evidence_rows),
                "leader_rows": len(leader_rows),
                "evidence_path": str(EVIDENCE_PATH),
                "leaders_path": str(LEADERS_PATH),
                "summary_path": str(SUMMARY_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
