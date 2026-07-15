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
        "evidence_id": "E3-781",
        "company": "海思",
        "subsegment": "手机SoC/通信基带",
        "title": "Balong 5000 Chipset | HiSilicon Official Site",
        "url": "https://www.hisilicon.com/en/products/balong/balong-5000",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "HiSilicon 官方页面介绍 Balong 5000 为 5G multimode chipset，支持 2G/3G/4G/5G 网络。",
        "claim": "海思覆盖移动通信基带芯片产品，可支撑其在手机SoC/通信基带环节的业务归属。",
    },
    {
        "evidence_id": "E3-782",
        "company": "紫光展锐",
        "subsegment": "手机SoC/通信基带",
        "title": "UNISOC 5G Mobile Platform",
        "url": "https://www.unisoc.com/en_us/secy/5G.html",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "UNISOC 官方 5G 页面展示 5G 移动平台/芯片产品线。",
        "claim": "紫光展锐覆盖 5G 移动平台和蜂窝通信芯片产品，可支撑其在手机SoC/通信基带环节的业务归属。",
    },
    {
        "evidence_id": "E3-783",
        "company": "中兴通讯",
        "subsegment": "消费电子/通信设备",
        "title": "ZTE Official Website - Products",
        "url": "https://www.zte.com.cn/global/products.html",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "ZTE 官方产品页覆盖无线、有线、算力基础设施、终端等通信与 ICT 产品。",
        "claim": "中兴通讯覆盖通信设备、网络设备和企业级 ICT 解决方案，可支撑其在消费电子/通信设备环节的业务归属。",
    },
    {
        "evidence_id": "E3-784",
        "company": "Ericsson",
        "subsegment": "消费电子/通信设备",
        "title": "Ericsson Radio System",
        "url": "https://www.ericsson.com/en/portfolio/networks/ericsson-radio-system",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Ericsson 官方页面称 Ericsson Radio System 是端到端、模块化、可扩展的 radio access network。",
        "claim": "Ericsson 覆盖无线接入网络和通信设备产品，可支撑其在消费电子/通信设备环节的业务归属。",
    },
    {
        "evidence_id": "E3-785",
        "company": "Continental",
        "subsegment": "新能源汽车/汽车电子",
        "title": "Continental zone control units press release",
        "url": "https://www.continental.com/en/press/press-releases/20240418-zonecontrolunits",
        "source_type": "company_or_wire_release",
        "grade": "A-",
        "excerpt": "Continental 公告介绍面向服务器式车辆架构的 Zone Control Units。",
        "claim": "Continental 覆盖车身/区域控制单元和汽车电子系统，可支撑其在新能源汽车/汽车电子环节的业务归属。",
    },
    {
        "evidence_id": "E3-786",
        "company": "Denso",
        "subsegment": "新能源汽车/汽车电子",
        "title": "Electronics Platform | DENSO Global",
        "url": "https://www.denso.com/global/en/business/products-and-services/mobility/pick-up/ep",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "DENSO 官方 Electronics Platform 页面说明其集成车辆电子组件和 ECU。",
        "claim": "DENSO 覆盖汽车电子平台、电子组件和 ECU，可支撑其在新能源汽车/汽车电子环节的业务归属。",
    },
    {
        "evidence_id": "E3-787",
        "company": "华大九天",
        "subsegment": "EDA软件",
        "title": "Product - Empyrean Technology EDA",
        "url": "https://www.empyrean-tech.com/product/eda.html",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Empyrean 官方产品页称其提供模拟设计、数字 SoC、平板显示设计等 EDA 解决方案。",
        "claim": "华大九天覆盖 EDA 软件产品线，可支撑其在 EDA 软件环节的业务归属。",
    },
    {
        "evidence_id": "E3-788",
        "company": "广立微",
        "subsegment": "EDA软件",
        "title": "Semitronix Official Site",
        "url": "https://www.semitronix.com?cur_lang=en",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Semitronix 官方称其提供 characterization and yield improvement solutions，覆盖软件、硬件和服务。",
        "claim": "广立微覆盖成品率提升、测试与 EDA 数据分析相关产品服务，可支撑其在 EDA 软件环节的业务归属。",
    },
    {
        "evidence_id": "E3-789",
        "company": "概伦电子",
        "subsegment": "EDA软件",
        "title": "Primarius Products",
        "url": "https://www.primarius-tech.com/en/products",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Primarius 官方产品页列出 SPICE Model、PDK Verification、Circuit Analysis 等 EDA 产品。",
        "claim": "概伦电子覆盖器件建模、PDK 验证和电路仿真等 EDA 产品，可支撑其在 EDA 软件环节的业务归属。",
    },
    {
        "evidence_id": "E3-790",
        "company": "圣邦股份",
        "subsegment": "模拟/RF/MCU/传感器",
        "title": "SGMICRO Power Management Products",
        "url": "https://www.sg-micro.com/products/power-management",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "SGMICRO 官方页面列出 power management 产品，并说明提供模拟和混合信号 IC 方案。",
        "claim": "圣邦股份覆盖电源管理和模拟 IC 产品，可支撑其在模拟/RF/MCU/传感器环节的业务归属。",
    },
    {
        "evidence_id": "E3-791",
        "company": "Analog Devices",
        "subsegment": "模拟/RF/MCU/传感器",
        "title": "Analog Devices Products",
        "url": "https://www.analog.com/en/products.html",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "ADI 官方产品目录覆盖放大器、数据转换器、电源、RF 和微波等产品。",
        "claim": "Analog Devices 覆盖高性能模拟、RF、信号链和电源管理产品，可支撑其在模拟/RF/MCU/传感器环节的业务归属。",
    },
    {
        "evidence_id": "E3-792",
        "company": "NXP",
        "subsegment": "模拟/RF/MCU/传感器",
        "title": "NXP Products",
        "url": "https://www.nxp.com/products",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "NXP 官方产品目录覆盖汽车、MCU、处理器、连接、安全等芯片产品。",
        "claim": "NXP 覆盖汽车 MCU、连接、传感和安全芯片产品，可支撑其在模拟/RF/MCU/传感器环节的业务归属。",
    },
    {
        "evidence_id": "E3-793",
        "company": "Texas Instruments",
        "subsegment": "模拟/RF/MCU/传感器",
        "title": "Texas Instruments Products",
        "url": "https://www.ti.com/products.html",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "TI 官方产品目录覆盖模拟、嵌入式处理、电源、信号链等产品。",
        "claim": "Texas Instruments 覆盖模拟和嵌入式处理产品，可支撑其在模拟/RF/MCU/传感器环节的业务归属。",
    },
    {
        "evidence_id": "E3-794",
        "company": "华虹半导体",
        "subsegment": "晶圆代工/Foundry",
        "title": "Hua Hong Grace Semiconductor official site",
        "url": "https://www.huahonggrace.com/html",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "华虹官网称其为 specialty technologies pure-play foundry，提供晶圆代工和支持服务。",
        "claim": "华虹半导体覆盖特色工艺晶圆代工服务，可支撑其在晶圆代工/Foundry环节的业务归属。",
    },
    {
        "evidence_id": "E3-795",
        "company": "精测电子",
        "subsegment": "量测检测设备",
        "title": "Jingce Electronic About Us",
        "url": "https://jingceelectronic.com/about-us",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "精测电子官网称其围绕半导体、显示和新能源行业提供测试设备相关产品和服务。",
        "claim": "精测电子覆盖半导体测试/量测检测设备，可支撑其在量测检测设备环节的业务归属。",
    },
    {
        "evidence_id": "E3-796",
        "company": "Onto Innovation",
        "subsegment": "量测检测设备",
        "title": "Onto Innovation Products",
        "url": "https://ontoinnovation.com/products/",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Onto Innovation 官方产品页覆盖 process control、metrology、inspection 等半导体制造产品。",
        "claim": "Onto Innovation 覆盖半导体量测与检测设备，可支撑其在量测检测设备环节的业务归属。",
    },
    {
        "evidence_id": "E3-797",
        "company": "Cohu",
        "subsegment": "测试设备",
        "title": "Cohu Semiconductor Test Products",
        "url": "https://www.cohu.com/products/semiconductor-test/",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Cohu 官方产品页覆盖 semiconductor test 相关设备和解决方案。",
        "claim": "Cohu 覆盖半导体测试设备和处理器产品，可支撑其在测试设备环节的业务归属。",
    },
    {
        "evidence_id": "E3-798",
        "company": "南大光电",
        "subsegment": "电子气体/湿电子化学品",
        "title": "Nata Overview",
        "url": "http://sonatamaterials.com/Nata-Overview",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "南大光电/Nata 官方页面说明其三大业务包括前驱体材料、电子特气、光刻胶及配套材料。",
        "claim": "南大光电覆盖电子特气、前驱体和光刻胶等半导体材料，可支撑其在电子气体/湿电子化学品环节的业务归属。",
    },
    {
        "evidence_id": "E3-799",
        "company": "金宏气体",
        "subsegment": "电子气体/湿电子化学品",
        "title": "JinHong Gas Electronic Specialty Gases",
        "url": "https://jh-gas.com/ja/gas-cat/electronic-specialty-gases",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "金宏气体官网电子特气分类页面覆盖半导体制造相关电子特种气体。",
        "claim": "金宏气体覆盖半导体电子特气产品，可支撑其在电子气体/湿电子化学品环节的业务归属。",
    },
    {
        "evidence_id": "E3-800",
        "company": "JX Advanced Metals",
        "subsegment": "靶材",
        "title": "Sputtering Target for Semiconductor - JX Advanced Metals",
        "url": "https://www.jx-nmm.com/english/products/sputtering/semiconductor_st",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "JX Advanced Metals 官方半导体溅射靶材页面介绍其面向半导体器件提供高质量靶材。",
        "claim": "JX Advanced Metals 覆盖半导体溅射靶材，可支撑其在靶材环节的业务归属。",
    },
    {
        "evidence_id": "E3-801",
        "company": "Materion",
        "subsegment": "靶材",
        "title": "Materion Sputtering Targets for Semiconductor Applications",
        "url": "https://www.materion.com/en/products/electronic-materials/thin-film-deposition-materials/specialty-sputtering-targets",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Materion 官方页面介绍面向半导体应用的溅射靶材和薄膜沉积材料。",
        "claim": "Materion 覆盖半导体溅射靶材和沉积材料，可支撑其在靶材环节的业务归属。",
    },
    {
        "evidence_id": "E3-802",
        "company": "Tosoh",
        "subsegment": "靶材",
        "title": "Tosoh Semiconductor Targets",
        "url": "https://www.tosohsmd.com/our-products/semiconductor-targets",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Tosoh SMD 官方页面介绍其为半导体行业提供高纯金属和合金靶材。",
        "claim": "Tosoh 覆盖半导体靶材产品，可支撑其在靶材环节的业务归属。",
    },
    {
        "evidence_id": "E3-803",
        "company": "安集科技",
        "subsegment": "CMP材料",
        "title": "Anji Microelectronics Solutions",
        "url": "https://www.anjimicro.com/en/jiejuefangan.html",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "安集科技官方页面说明 CMP slurry 是 IC 制造 CMP 过程中的主要加工化学品。",
        "claim": "安集科技覆盖 CMP 抛光液等半导体材料，可支撑其在 CMP材料环节的业务归属。",
    },
    {
        "evidence_id": "E3-804",
        "company": "Fujimi",
        "subsegment": "CMP材料",
        "title": "FUJIMI Products & Services",
        "url": "https://www.fujimiinc.co.jp/english/service/index.html",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Fujimi 官方产品服务页称其处理用于半导体器件生产的多种研磨材料，包括 CMP slurry。",
        "claim": "Fujimi 覆盖 CMP slurry 和半导体研磨材料，可支撑其在 CMP材料环节的业务归属。",
    },
    {
        "evidence_id": "E3-805",
        "company": "Ibiden",
        "subsegment": "封装材料/IC载板",
        "title": "Ibiden Flip Chip PKG",
        "url": "https://www.ibiden.com/product/electronics/merchandise/fliptippkg",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Ibiden 官方页面介绍 IC Package Substrates 和 flip chip package substrate。",
        "claim": "Ibiden 覆盖 IC 封装基板/载板，可支撑其在封装材料/IC载板环节的业务归属。",
    },
    {
        "evidence_id": "E3-806",
        "company": "Shinko Electric",
        "subsegment": "封装材料/IC载板",
        "title": "Shinko Semiconductor Package",
        "url": "https://www.shinko.co.jp/english/product/package",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Shinko 官方 Semiconductor Package 页面介绍 substrate、IC assembly 等封装产品。",
        "claim": "Shinko Electric 覆盖半导体封装基板和封装产品，可支撑其在封装材料/IC载板环节的业务归属。",
    },
    {
        "evidence_id": "E3-807",
        "company": "兴森科技",
        "subsegment": "封装材料/IC载板",
        "title": "Fastprint IC Substrate",
        "url": "https://en.chinafastprint.com/product/ic",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "兴森科技/Fastprint 官方 IC Substrate 页面列出 CSP、FC-CSP、SiP、PBGA 等产品。",
        "claim": "兴森科技覆盖 IC 载板/封装基板产品，可支撑其在封装材料/IC载板环节的业务归属。",
    },
    {
        "evidence_id": "E3-808",
        "company": "深南电路",
        "subsegment": "封装材料/IC载板",
        "title": "SCC official site",
        "url": "https://www.scc.com.cn/scc/en/gysn/index.html",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "深南电路英文官网介绍公司业务与电子互连产品能力。",
        "claim": "深南电路覆盖封装基板/电子互连相关产品，可支撑其在封装材料/IC载板环节的业务归属。",
    },
    {
        "evidence_id": "E3-809",
        "company": "Powertech",
        "subsegment": "传统OSAT封装测试",
        "title": "Powertech Technology official site",
        "url": "https://www.pti.com.tw",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "PTI 官网称其是 chip probing、packaging、testing turnkey services provider。",
        "claim": "Powertech 覆盖芯片探针、封装和测试服务，可支撑其在传统OSAT封装测试环节的业务归属。",
    },
    {
        "evidence_id": "E3-810",
        "company": "晶方科技",
        "subsegment": "传统OSAT封装测试",
        "title": "China Wafer Level CSP official site",
        "url": "http://www.wlcsp.com/EN",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "晶方科技/China Wafer Level CSP 官网称其提供 3DIC 和 TSV 晶圆级封装测试服务。",
        "claim": "晶方科技覆盖 WLCSP、3DIC、TSV 晶圆级封装测试服务，可支撑其在传统OSAT封装测试环节的业务归属。",
    },
    {
        "evidence_id": "E3-811",
        "company": "通富微电",
        "subsegment": "传统OSAT封装测试",
        "title": "Tongfu Microelectronics official news",
        "url": "https://en.tfme.com/news/1070.html",
        "source_type": "company_or_wire_release",
        "grade": "A-",
        "excerpt": "通富微电英文官网新闻提到全球封测市场和公司排名提升。",
        "claim": "通富微电覆盖半导体封装测试服务，可支撑其在传统OSAT封装测试环节的业务归属。",
    },
    {
        "evidence_id": "E3-812",
        "company": "长鑫存储",
        "subsegment": "DRAM/HBM",
        "title": "ABOUT CXMT",
        "url": "https://www.cxmt.com/en/about.html",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "CXMT 官网称其制造 DRAM 芯片，应用于手机、PC、平板、服务器和消费产品。",
        "claim": "长鑫存储覆盖 DRAM 产品，可支撑其在 DRAM/HBM 环节的业务归属。",
    },
    {
        "evidence_id": "E3-813",
        "company": "长江存储",
        "subsegment": "NAND Flash",
        "title": "YMTC Company Profile",
        "url": "http://www.ymtc.com/en/aboutus.html",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "YMTC 官网公司简介提到 3D NAND Flash 和 Xtacking 架构。",
        "claim": "长江存储覆盖 3D NAND Flash 产品，可支撑其在 NAND Flash 环节的业务归属。",
    },
    {
        "evidence_id": "E3-814",
        "company": "Kioxia",
        "subsegment": "NAND Flash",
        "title": "KIOXIA Memory Products",
        "url": "https://americas.kioxia.com/en-us/business/memory.html",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Kioxia 官方 Memory 页面介绍 NAND flash 和 3D flash memory 技术。",
        "claim": "Kioxia 覆盖 NAND Flash 和 3D Flash 产品，可支撑其在 NAND Flash 环节的业务归属。",
    },
    {
        "evidence_id": "E3-815",
        "company": "Micron",
        "subsegment": "NAND Flash",
        "title": "Micron NAND Flash",
        "url": "https://www.micron.com/products/storage/nand-flash",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Micron 官方 NAND flash 页面介绍其设计和制造 NAND flash memory。",
        "claim": "Micron 覆盖 NAND Flash 存储产品，可支撑其在 NAND Flash 环节的业务归属。",
    },
    {
        "evidence_id": "E3-816",
        "company": "SK hynix",
        "subsegment": "NAND Flash",
        "title": "SK hynix 321-High NAND release",
        "url": "https://news.skhynix.com/sk-hynix-starts-mass-production-of-world-first-321-high-nand",
        "source_type": "company_or_wire_release",
        "grade": "A-",
        "excerpt": "SK hynix 官方新闻称其开始量产 321 层 NAND。",
        "claim": "SK hynix 覆盖 NAND Flash 产品，可支撑其在 NAND Flash 环节的业务归属。",
    },
    {
        "evidence_id": "E3-817",
        "company": "Macronix",
        "subsegment": "存储控制/模组/NOR",
        "title": "Macronix Serial NOR Flash",
        "url": "https://www.macronix.com/en-us/products/NOR-Flash/Serial-NOR-Flash",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Macronix 官方页面介绍 3V、2.5V、1.8V Serial NOR Flash 产品。",
        "claim": "Macronix 覆盖 NOR Flash 产品，可支撑其在存储控制/模组/NOR环节的业务归属。",
    },
    {
        "evidence_id": "E3-818",
        "company": "Winbond",
        "subsegment": "存储控制/模组/NOR",
        "title": "Winbond Code Storage Flash",
        "url": "https://www.winbond.com/hq/product/code-storage-flash?__locale=en",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Winbond 官方页面称其 Code Storage Flash 组合包括 NOR Flash、NAND Flash 和安全 Flash。",
        "claim": "Winbond 覆盖 NOR Flash、NAND Flash 和 DRAM 等存储产品，可支撑其在存储控制/模组/NOR环节的业务归属。",
    },
    {
        "evidence_id": "E3-819",
        "company": "Mitsubishi Electric",
        "subsegment": "功率器件/模块",
        "title": "Mitsubishi Electric Power Devices",
        "url": "https://www.mitsubishielectric.com/semiconductors/powerdevices/products",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Mitsubishi Electric 官方 power devices 页面列出 IPM、DIPIPM 和多种 power modules。",
        "claim": "Mitsubishi Electric 覆盖功率器件和功率模块产品，可支撑其在功率器件/模块环节的业务归属。",
    },
    {
        "evidence_id": "E3-820",
        "company": "ROHM",
        "subsegment": "功率器件/模块",
        "title": "ROHM SiC Power Devices",
        "url": "https://www.rohm.com/products/sic-power-devices",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "ROHM 官方页面介绍 SiC power devices、SiC MOSFET 和 SiC power modules。",
        "claim": "ROHM 覆盖 SiC 功率器件和功率模块产品，可支撑其在功率器件/模块与SiC功率器件/模块环节的业务归属。",
    },
    {
        "evidence_id": "E3-821",
        "company": "Coherent",
        "subsegment": "SiC衬底/外延",
        "title": "Coherent SiC for Power Electronics",
        "url": "https://www.coherent.com/materials/wide-bandgap-electronics/sic-substrates-epitaxy/sic-for-power-electronics",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Coherent 官方页面介绍 SiC substrates and epitaxy for power electronics。",
        "claim": "Coherent 覆盖 SiC 衬底和外延产品，可支撑其在 SiC衬底/外延环节的业务归属。",
    },
    {
        "evidence_id": "E3-822",
        "company": "onsemi",
        "subsegment": "SiC功率器件/模块",
        "title": "onsemi Silicon Carbide Products",
        "url": "https://www.onsemi.com/products/discrete-power-modules/silicon-carbide-sic",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "onsemi 官方 SiC 页面介绍端到端 SiC 制造能力和 SiC 产品。",
        "claim": "onsemi 覆盖 SiC 功率器件和模块产品，可支撑其在 SiC功率器件/模块环节的业务归属。",
    },
    {
        "evidence_id": "E3-823",
        "company": "Navitas",
        "subsegment": "GaN功率/RF器件",
        "title": "Navitas GaN Power ICs",
        "url": "https://navitassemi.com/gan-power-ics",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Navitas 官方页面介绍 GaNFast power ICs 和 GaN 功率 IC 产品。",
        "claim": "Navitas 覆盖 GaN 功率 IC 产品，可支撑其在 GaN功率/RF器件环节的业务归属。",
    },
    {
        "evidence_id": "E3-824",
        "company": "Renesas",
        "subsegment": "GaN功率/RF器件",
        "title": "Renesas Gallium Nitride Power Solutions",
        "url": "https://www.renesas.com/en/key-technologies/gallium-nitride-gan-power-solutions",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Renesas 官方 GaN 页面介绍面向高效率、高功率密度系统的 GaN power solutions。",
        "claim": "Renesas 覆盖 GaN 功率解决方案，可支撑其在 GaN功率/RF器件环节的业务归属。",
    },
    {
        "evidence_id": "E3-825",
        "company": "Transphorm",
        "subsegment": "GaN功率/RF器件",
        "title": "Transphorm GaN FET reliability release | Renesas",
        "url": "https://www.renesas.com/en/about/newsroom/transphorm-releases-new-gan-fet-reliability-ratings-now-segmented-power-level",
        "source_type": "company_or_wire_release",
        "grade": "A-",
        "excerpt": "Renesas/Transphorm 新闻稿称 Transphorm 是高可靠高性能 GaN power conversion products 的供应商。",
        "claim": "Transphorm 覆盖 GaN FET/功率转换器件，可支撑其在 GaN功率/RF器件环节的业务归属。",
    },
]

APPEND_MAP = {
    ("华大九天", "EDA软件"): ["E3-787"],
    ("广立微", "EDA软件"): ["E3-788"],
    ("概伦电子", "EDA软件"): ["E3-789"],
    ("海思", "AI/GPU/CPU算力芯片"): ["E3-781"],
    ("海思", "手机SoC/通信基带"): ["E3-781"],
    ("紫光展锐", "手机SoC/通信基带"): ["E3-782"],
    ("圣邦股份", "模拟/RF/MCU/传感器"): ["E3-790"],
    ("Analog Devices", "模拟/RF/MCU/传感器"): ["E3-791"],
    ("NXP", "模拟/RF/MCU/传感器"): ["E3-792"],
    ("Texas Instruments", "模拟/RF/MCU/传感器"): ["E3-793"],
    ("Texas Instruments", "IDM/特色工艺制造"): ["E3-793"],
    ("华虹半导体", "晶圆代工/Foundry"): ["E3-794"],
    ("精测电子", "量测检测设备"): ["E3-795"],
    ("Onto Innovation", "量测检测设备"): ["E3-796"],
    ("Cohu", "测试设备"): ["E3-797"],
    ("南大光电", "电子气体/湿电子化学品"): ["E3-798"],
    ("金宏气体", "电子气体/湿电子化学品"): ["E3-799"],
    ("JX Advanced Metals", "靶材"): ["E3-800"],
    ("Materion", "靶材"): ["E3-801"],
    ("Tosoh", "靶材"): ["E3-802"],
    ("安集科技", "CMP材料"): ["E3-803"],
    ("Fujimi", "CMP材料"): ["E3-804"],
    ("Ibiden", "封装材料/IC载板"): ["E3-805"],
    ("Shinko Electric", "封装材料/IC载板"): ["E3-806"],
    ("兴森科技", "封装材料/IC载板"): ["E3-807"],
    ("深南电路", "封装材料/IC载板"): ["E3-808"],
    ("Powertech", "传统OSAT封装测试"): ["E3-809"],
    ("晶方科技", "传统OSAT封装测试"): ["E3-810"],
    ("通富微电", "传统OSAT封装测试"): ["E3-811"],
    ("长鑫存储", "DRAM/HBM"): ["E3-812"],
    ("长江存储", "NAND Flash"): ["E3-813"],
    ("Kioxia", "NAND Flash"): ["E3-814"],
    ("Micron", "NAND Flash"): ["E3-815"],
    ("SK hynix", "NAND Flash"): ["E3-816"],
    ("Macronix", "存储控制/模组/NOR"): ["E3-817"],
    ("Winbond", "存储控制/模组/NOR"): ["E3-818"],
    ("Mitsubishi Electric", "功率器件/模块"): ["E3-819"],
    ("ROHM", "功率器件/模块"): ["E3-820"],
    ("ROHM", "SiC功率器件/模块"): ["E3-820"],
    ("Coherent", "SiC衬底/外延"): ["E3-821"],
    ("onsemi", "SiC功率器件/模块"): ["E3-822"],
    ("Navitas", "GaN功率/RF器件"): ["E3-823"],
    ("Renesas", "GaN功率/RF器件"): ["E3-824"],
    ("Transphorm", "GaN功率/RF器件"): ["E3-825"],
    ("Continental", "新能源汽车/汽车电子"): ["E3-785"],
    ("Denso", "新能源汽车/汽车电子"): ["E3-786"],
    ("中兴通讯", "消费电子/通信设备"): ["E3-783"],
    ("Ericsson", "消费电子/通信设备"): ["E3-784"],
}

STAGE6_MAP = {
    ("海思", "移动SoC"): ["E3-781"],
    ("海思", "通信基带芯片"): ["E3-781"],
    ("紫光展锐", "移动SoC"): ["E3-782"],
    ("紫光展锐", "通信基带芯片"): ["E3-782"],
    ("Continental", "汽车电子系统"): ["E3-785"],
    ("Denso", "汽车电子系统"): ["E3-786"],
    ("中兴通讯", "通信设备"): ["E3-783"],
    ("中兴通讯", "网络设备"): ["E3-783"],
    ("中兴通讯", "企业级ICT解决方案"): ["E3-783"],
    ("Ericsson", "通信设备"): ["E3-784"],
}


def as_evidence_record(row: dict[str, str]) -> dict[str, object]:
    return {
        "evidence_id": row["evidence_id"],
        "task_id": "S3-authoritative-evidence-enrichment-3",
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
    seen: set[str] = set()
    output: list[dict[str, object]] = []
    replaced = 0

    if EVIDENCE_PATH.exists():
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

    updates = 0
    url_by_evidence = {row["evidence_id"]: row["url"] for row in EVIDENCE_ROWS}
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
                url = url_by_evidence.get(evidence_id, "")
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
    replaced, appended = repair_evidence()
    leader_updates = update_csv(LEADERS_PATH, ("company_name", "subsegment_name"), APPEND_MAP)
    stage6_updates = update_csv(STAGE6_PATH, ("company_name", "product_service_name"), STAGE6_MAP)
    print(
        json.dumps(
            {
                "evidence_replaced": replaced,
                "evidence_appended": appended,
                "leader_updates": leader_updates,
                "stage6_updates": stage6_updates,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
