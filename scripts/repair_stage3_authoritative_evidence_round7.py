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
        "evidence_id": "E3-850",
        "company": "北方华创",
        "subsegment": "刻蚀设备",
        "title": "北方华创半导体装备官网：集成电路",
        "url": "https://www.naura.com/product/details_83_1602.html",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "北方华创官网披露，面向 Logic、DRAM、3D NAND、3D IC 等芯片技术，公司可提供等离子刻蚀机、PVD、CVD、ALD、炉管和清洗等设备，并已进入主流芯片工厂。",
        "claim": "北方华创具备等离子刻蚀设备业务和集成电路制造设备供给能力，可支撑其在刻蚀设备环节的业务归属。",
    },
    {
        "evidence_id": "E3-851",
        "company": "北方华创",
        "subsegment": "薄膜沉积设备",
        "title": "北方华创半导体装备官网：产品分类",
        "url": "https://www.naura.com/product/semiconductor.html",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "北方华创官网披露，主要产品包括刻蚀机、PVD、ALD、CVD、氧化/扩散炉、清洗机、气体质量流量计等高端半导体工艺装备及核心零部件。",
        "claim": "北方华创覆盖 PVD、ALD、CVD 等薄膜沉积设备，可支撑其在薄膜沉积设备环节的业务归属。",
    },
    {
        "evidence_id": "E3-852",
        "company": "北方华创",
        "subsegment": "清洗/CMP/热处理设备",
        "title": "北方华创半导体装备官网：备品备件",
        "url": "https://www.naura.com/product/details_83_147.html",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "北方华创官网披露，其备品备件可应用于刻蚀机、PVD、CVD、ALD、清洗机、立式/卧式炉管等半导体装备。",
        "claim": "北方华创覆盖清洗机和炉管/热处理相关半导体装备，可支撑其在清洗/CMP/热处理设备环节的业务归属。",
    },
    {
        "evidence_id": "E3-853",
        "company": "中微公司",
        "subsegment": "刻蚀设备",
        "title": "中微公司官网：刻蚀设备",
        "url": "https://www.amec-inc.com/index/Lists/index/catid/26.html",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "中微公司官网披露，公司专注于研发干法刻蚀/等离子体刻蚀设备，用于在晶圆上加工微观结构。",
        "claim": "中微公司具备等离子体刻蚀设备产品，可支撑其在刻蚀设备环节的业务归属。",
    },
    {
        "evidence_id": "E3-854",
        "company": "中微公司",
        "subsegment": "薄膜沉积设备",
        "title": "中微公司官网：MOCVD设备",
        "url": "https://www.amec-inc.com/index/Lists/index/catid/30.html",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "中微公司官网披露，MOCVD 是用于 LED 芯片和功率器件制造的关键工艺技术，公司在 MOCVD 领域有深厚技术积累。",
        "claim": "中微公司具备 MOCVD 设备产品，可支撑其在薄膜沉积设备/化合物半导体工艺设备环节的业务归属。",
    },
    {
        "evidence_id": "E3-855",
        "company": "TSMC",
        "subsegment": "晶圆代工/Foundry",
        "title": "TSMC Logic Technology",
        "url": "https://www.tsmc.com/english/dedicatedFoundry/technology/logic",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "TSMC 官方技术页面披露，TSMC 的 N2 技术已按计划进入量产，且 TSMC 在 2022 年率先将 3nm FinFET（N3）技术导入高量产。",
        "claim": "TSMC 覆盖 2nm/3nm 等先进逻辑制程代工技术，可支撑其在晶圆代工/先进制程代工环节的业务归属。",
    },
    {
        "evidence_id": "E3-856",
        "company": "TSMC",
        "subsegment": "2.5D/3D/Chiplet先进封装",
        "title": "TSMC 3DFabric",
        "url": "https://3dfabric.tsmc.com/english/dedicatedFoundry/technology/3DFabric.htm",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "TSMC 官方 3DFabric 页面披露，其提供 3D silicon stacking 与先进封装技术，包括 TSMC-SoIC、CoWoS 和 InFO。",
        "claim": "TSMC 覆盖 CoWoS、InFO、SoIC 等 2.5D/3D/Chiplet 先进封装服务，可支撑其在先进封装环节的业务归属。",
    },
    {
        "evidence_id": "E3-857",
        "company": "三安光电",
        "subsegment": "SiC衬底/外延",
        "title": "三安半导体官网：碳化硅及氮化镓材料",
        "url": "https://www.sanan-semiconductor.com/sic-substrate-epitaxy",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "三安半导体官网披露，公司具备大直径晶圆和高质量外延技术量产能力，相关文档列示 N 型碳化硅衬底、高纯半绝缘碳化硅衬底、碳化硅外延片和氮化镓外延片。",
        "claim": "三安光电/三安半导体覆盖 SiC 衬底、SiC 外延片和 GaN 外延片，可支撑其在 SiC衬底/外延环节的业务归属。",
    },
    {
        "evidence_id": "E3-858",
        "company": "三安光电",
        "subsegment": "SiC功率器件/模块",
        "title": "三安半导体官网：SiC二极管与SiC MOSFET",
        "url": "https://www.sanan-semiconductor.com/",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "三安半导体官网披露，公司拥有完整的 SiC 二极管产品组合，并展示 Silicon Carbide MOSFET 产品方向。",
        "claim": "三安光电/三安半导体覆盖 SiC 二极管和 SiC MOSFET 等功率器件，可支撑其在 SiC功率器件/模块环节的业务归属。",
    },
    {
        "evidence_id": "E3-859",
        "company": "三安光电",
        "subsegment": "GaN功率/RF器件",
        "title": "三安光电 2024 年年度报告摘要",
        "url": "https://file.finance.qq.com/finance/hs/pdf/2025/04/26/1223310062.PDF",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "三安光电年报摘要披露，公司集成电路芯片产品包括 GaAs/GaN 射频芯片，以及 SiC/GaN 电力电子芯片，覆盖碳化硅 MOSFET、碳化硅二极管、碳化硅衬底/外延和硅基氮化镓。",
        "claim": "三安光电覆盖 GaN 射频芯片和 SiC/GaN 电力电子芯片，可支撑其在 GaN功率/RF器件环节的业务归属。",
    },
    {
        "evidence_id": "E3-860",
        "company": "华润微",
        "subsegment": "IDM/特色工艺制造",
        "title": "华润微官网：公司架构/功率器件事业群",
        "url": "https://www.crmicro.com/corporateStructure/",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "华润微官网披露，功率器件事业群负责功率器件设计、研发、制造与销售，产品包括 MOS、IGBT、FRED、肖特基二极管及功率模块，并布局 GaN、SiC 第三代功率半导体器件。",
        "claim": "华润微具备功率器件设计、研发、制造与销售的一体化能力，可支撑其在 IDM/特色工艺制造环节的业务归属。",
    },
    {
        "evidence_id": "E3-861",
        "company": "华润微",
        "subsegment": "功率器件/模块",
        "title": "华润微 2024 年年度报告",
        "url": "https://www.crmicro.com/periodicalReports/2025-04-30/6e0cd80d-8132-44ae-a966-e1920700e45c.pdf",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "华润微年报披露，公司 MOSFET、IGBT、SiC MOS、功率 IC 等系列化车规级产品及模块产品进入国内头部车企及汽车零部件 Tier1 供应链体系。",
        "claim": "华润微覆盖 MOSFET、IGBT、SiC MOS 和功率模块，可支撑其在功率器件/模块环节的业务归属。",
    },
    {
        "evidence_id": "E3-862",
        "company": "士兰微",
        "subsegment": "IDM/特色工艺制造",
        "title": "士兰微英文官网：公司介绍",
        "url": "https://www.silan.com.cn/en/about.html",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "士兰微官网披露，公司专注于 IC 芯片设计和半导体微电子相关产品制造，并列示 Planar IGBT、Trench IGBT、SiC Hybrid IGBT、RC IGBT、SiC MOS 等产品方向。",
        "claim": "士兰微具备芯片设计与半导体制造一体化能力，并覆盖 IGBT、SiC 等功率器件方向，可支撑其在 IDM/特色工艺制造环节的业务归属。",
    },
    {
        "evidence_id": "E3-863",
        "company": "士兰微",
        "subsegment": "功率器件/模块",
        "title": "士兰微官网：产品中心",
        "url": "https://www.silan.com.cn/",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "士兰微官网展示 600V 三相全桥驱动智能功率模块和 1200V/50A 半桥驱动 IGBT 功率模块等产品。",
        "claim": "士兰微覆盖 IPM 智能功率模块和 IGBT 功率模块，可支撑其在功率器件/模块环节的业务归属。",
    },
    {
        "evidence_id": "E3-864",
        "company": "士兰微",
        "subsegment": "SiC功率器件/模块",
        "title": "士兰微官网：SiC MOS 产品",
        "url": "https://www.silan.com.cn/index.php/product/index/485.html",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "士兰微官网 SiC MOS 产品页列示 SiC MOS、SiC Module、SiC SBD 等产品类别。",
        "claim": "士兰微覆盖 SiC MOS、SiC 模块和 SiC SBD，可支撑其在 SiC功率器件/模块环节的业务归属。",
    },
    {
        "evidence_id": "E3-865",
        "company": "闻泰科技",
        "subsegment": "IDM/特色工艺制造",
        "title": "Nexperia 官网：产品",
        "url": "https://www.nexperia.com/products",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Nexperia 官网产品页展示二极管、双极晶体管、ESD 保护、MOSFET、GaN FET、模拟与逻辑 IC 等产品组合。",
        "claim": "闻泰科技旗下 Nexperia 覆盖功率与分立器件产品组合，可支撑其在 IDM/特色工艺制造环节的业务归属。",
    },
    {
        "evidence_id": "E3-866",
        "company": "闻泰科技",
        "subsegment": "SiC功率器件/模块",
        "title": "Nexperia 官网：SiC MOSFET",
        "url": "https://www.nexperia.com/products/silicon-carbide-power-devices/sic-mosfets",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Nexperia 官网 SiC MOSFET 产品页展示其碳化硅 MOSFET 产品线。",
        "claim": "闻泰科技旗下 Nexperia 覆盖 SiC MOSFET，可支撑其在 SiC功率器件/模块环节的业务归属。",
    },
    {
        "evidence_id": "E3-867",
        "company": "斯达半导",
        "subsegment": "功率器件/模块",
        "title": "斯达半导体官网",
        "url": "https://www.powersemi.com/",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "斯达半导体官网披露，公司专业从事以 IGBT 为主的功率半导体芯片和模块的设计研发、生产及销售服务，是国内功率半导体器件领域的领军企业。",
        "claim": "斯达半导覆盖以 IGBT 为主的功率半导体芯片和模块，可支撑其在功率器件/模块环节的业务归属。",
    },
    {
        "evidence_id": "E3-868",
        "company": "斯达半导",
        "subsegment": "SiC功率器件/模块",
        "title": "StarPower Products",
        "url": "https://www.powersemi.com/EN/product.html",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "斯达半导英文产品页披露，其 IGBT 模块可覆盖多种应用，并列示 SiC Modules 产品方向。",
        "claim": "斯达半导覆盖 IGBT 模块和 SiC 模块，可支撑其在 SiC功率器件/模块环节的业务归属。",
    },
    {
        "evidence_id": "E3-869",
        "company": "长电科技",
        "subsegment": "传统OSAT封装测试",
        "title": "长电科技 2025 年年度报告摘要",
        "url": "https://pdf.dfcfw.com/pdf/H2_AN202604091821102756_1.pdf",
        "source_type": "official_disclosure",
        "grade": "A-",
        "excerpt": "长电科技年报摘要披露，公司向全球半导体客户提供一站式芯片成品制造解决方案，涵盖晶圆中测、芯片及器件封装、成品测试、产品认证以及全球直运等服务。",
        "claim": "长电科技覆盖封装测试服务，可支撑其在传统OSAT封装测试环节的业务归属。",
    },
    {
        "evidence_id": "E3-870",
        "company": "长电科技",
        "subsegment": "2.5D/3D/Chiplet先进封装",
        "title": "长电科技 2025 年年度报告摘要：先进封装",
        "url": "https://pdf.dfcfw.com/pdf/H2_AN202604091821102756_1.pdf",
        "source_type": "official_disclosure",
        "grade": "A-",
        "excerpt": "长电科技年报摘要披露，公司拥有晶圆级封装、2.5D/3D 封装、系统级封装、倒装芯片封装、引线键合封装及主流封装先进化解决方案。",
        "claim": "长电科技覆盖 2.5D/3D 封装和先进封装解决方案，可支撑其在先进封装环节的业务归属。",
    },
    {
        "evidence_id": "E3-871",
        "company": "华天科技",
        "subsegment": "传统OSAT封装测试",
        "title": "华天科技投资者关系活动记录表",
        "url": "https://static.cninfo.com.cn/finalpage/2026-04-10/1225091662.PDF",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "华天科技投资者关系活动记录表披露，公司自成立以来经过二十余年发展已成为封装测试龙头企业之一，目前业务规模位列中国大陆前三、全球第六。",
        "claim": "华天科技具备封装测试业务规模和行业地位，可支撑其在传统OSAT封装测试环节的业务归属。",
    },
    {
        "evidence_id": "E3-872",
        "company": "华天科技",
        "subsegment": "2.5D/3D/Chiplet先进封装",
        "title": "华天科技 2025 年半年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/2025-08-19/1224503005.pdf",
        "source_type": "official_disclosure",
        "grade": "A",
        "excerpt": "华天科技 2025 年半年度报告披露，半年度募集资金使用情况见 2024 年年报，并涉及集成电路先进封装技术相关投入；公司公告体系同时披露南京华天先进封装等项目。",
        "claim": "华天科技持续布局先进封装业务，可作为其在 2.5D/3D/Chiplet先进封装环节的补充证据；具体技术细项仍建议继续补公司官网或年报全文证据。",
    },
    {
        "evidence_id": "E3-873",
        "company": "Qualcomm",
        "subsegment": "手机SoC/通信基带",
        "title": "Snapdragon Mobile Platforms, Processors, Modems and Chipsets",
        "url": "https://www.qualcomm.com/snapdragon/products",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Qualcomm 官方 Snapdragon 产品页披露，Snapdragon 移动平台包括移动处理器，具备高速连接和高性能能力。",
        "claim": "Qualcomm 覆盖 Snapdragon 移动平台/移动处理器，可支撑其在手机SoC环节的业务归属。",
    },
    {
        "evidence_id": "E3-874",
        "company": "Qualcomm",
        "subsegment": "手机SoC/通信基带",
        "title": "Qualcomm 5G Modems",
        "url": "https://www.qualcomm.com/snapdragon/products/5g-modems",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Qualcomm 官方 5G Modems 页面披露，Snapdragon 5G 方案提供 5G 性能、覆盖和能效，用于先进 5G 设备体验。",
        "claim": "Qualcomm 覆盖 Snapdragon 5G 调制解调器/RF 系统，可支撑其在通信基带芯片环节的业务归属。",
    },
    {
        "evidence_id": "E3-875",
        "company": "ASML",
        "subsegment": "光刻设备",
        "title": "ASML EUV lithography systems",
        "url": "https://www.asml.com/en/products/euv-lithography-systems",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "ASML 官网披露，EUV 光刻系统用于高量产先进逻辑和存储芯片，NXE 系统用于 7nm、5nm 和 3nm 节点复杂基础层。",
        "claim": "ASML 覆盖 EUV 光刻系统，可支撑其在光刻设备环节的业务归属。",
    },
    {
        "evidence_id": "E3-876",
        "company": "ASML",
        "subsegment": "光刻设备",
        "title": "ASML DUV lithography systems",
        "url": "https://www.asml.com/en/products/duv-lithography-systems",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "ASML 官网披露，其 DUV 光刻系统用于打印形成微芯片基础的微小特征，浸没式系统服务于高量产先进逻辑和存储芯片。",
        "claim": "ASML 覆盖 DUV 光刻系统，可进一步支撑其在光刻设备环节的业务归属。",
    },
    {
        "evidence_id": "E3-877",
        "company": "KLA",
        "subsegment": "量测检测设备",
        "title": "KLA 官网",
        "url": "https://www.kla.com/",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "KLA 官网披露，公司开发并制造 process-control 和 process-enabling 解决方案，用于推动电子器件制造。",
        "claim": "KLA 覆盖过程控制、检测和量测相关设备/解决方案，可支撑其在量测检测设备环节的业务归属。",
    },
    {
        "evidence_id": "E3-878",
        "company": "Teradyne",
        "subsegment": "测试设备",
        "title": "Teradyne Semiconductor Test",
        "url": "https://www.teradyne.com/semiconductor-testing/",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Teradyne 官网披露，其半导体测试产品面向独立集成电路、SoC 和 SiP 器件的开发者和制造商。",
        "claim": "Teradyne 覆盖 SoC/SiP 半导体测试系统，可支撑其在测试设备环节的业务归属。",
    },
    {
        "evidence_id": "E3-879",
        "company": "Advantest",
        "subsegment": "测试设备",
        "title": "Advantest SoC Test Systems",
        "url": "https://www.advantest.com/en/products/semiconductor-test-system/soc/",
        "source_type": "official_product_page",
        "grade": "A",
        "excerpt": "Advantest 官网披露，其 SoC 测试系统可测试 SoC 器件中的逻辑、模拟、RF、DC 和图像传感器等集成电路。",
        "claim": "Advantest 覆盖 SoC 测试系统，可支撑其在测试设备环节的业务归属。",
    },
]

APPEND_MAP = {
    ("北方华创", "刻蚀设备"): ["E3-850"],
    ("北方华创", "薄膜沉积设备"): ["E3-851"],
    ("北方华创", "清洗/CMP/热处理设备"): ["E3-852"],
    ("中微公司", "刻蚀设备"): ["E3-853"],
    ("中微公司", "薄膜沉积设备"): ["E3-854"],
    ("TSMC", "晶圆代工/Foundry"): ["E3-855"],
    ("TSMC", "2.5D/3D/Chiplet先进封装"): ["E3-856"],
    ("三安光电", "SiC衬底/外延"): ["E3-857"],
    ("三安光电", "SiC功率器件/模块"): ["E3-858"],
    ("三安光电", "GaN功率/RF器件"): ["E3-859"],
    ("华润微", "IDM/特色工艺制造"): ["E3-860"],
    ("华润微", "功率器件/模块"): ["E3-861"],
    ("士兰微", "IDM/特色工艺制造"): ["E3-862"],
    ("士兰微", "功率器件/模块"): ["E3-863"],
    ("士兰微", "SiC功率器件/模块"): ["E3-864"],
    ("闻泰科技", "IDM/特色工艺制造"): ["E3-865"],
    ("闻泰科技", "SiC功率器件/模块"): ["E3-866"],
    ("斯达半导", "功率器件/模块"): ["E3-867"],
    ("斯达半导", "SiC功率器件/模块"): ["E3-868"],
    ("长电科技", "传统OSAT封装测试"): ["E3-869"],
    ("长电科技", "2.5D/3D/Chiplet先进封装"): ["E3-870"],
    ("华天科技", "传统OSAT封装测试"): ["E3-871"],
    ("华天科技", "2.5D/3D/Chiplet先进封装"): ["E3-872"],
    ("Qualcomm", "手机SoC/通信基带"): ["E3-873", "E3-874"],
    ("ASML", "光刻设备"): ["E3-875", "E3-876"],
    ("KLA", "量测检测设备"): ["E3-877"],
    ("Teradyne", "测试设备"): ["E3-878"],
    ("Advantest", "测试设备"): ["E3-879"],
}


def as_evidence_record(row: dict[str, str]) -> dict[str, object]:
    return {
        "evidence_id": row["evidence_id"],
        "task_id": "S3-authoritative-evidence-enrichment-7",
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
