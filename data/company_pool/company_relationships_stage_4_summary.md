# Stage 4 半导体公司关系表

- 生成时间：2026-07-06T17:29:07+08:00
- 候选关系规格：45 条
- 直接证据：175 条
- 入表关系：37 条
- 口径：只保留搜索结果中直接点名双方公司的供应链硬关系；未命中直接证据的候选关系不入表。
- 环节：严格沿用 Stage 3 的公司-子环节匹配，不扩展新环节。

## 关系类型分布

- EDA/IP供应：2
- HBM供应：2
- IP授权：3
- SiC材料供应：2
- 先进封装：3
- 功率器件供应/合作：1
- 封装测试：4
- 封装载板供应：4
- 晶圆代工：7
- 材料供应：2
- 设备供应：7

## 置信度分布

- high：35
- medium：2

## 关系明细

| 上游/服务方 | 上游/服务方环节 | 关系 | 下游/客户方 | 下游/客户方环节 | 置信度 | 判断依据 |
|---|---|---|---|---|---|---|
| Arm | 上游/设计支撑/EDA/IP/半导体IP/芯片定制 | IP授权 | Apple | 中游/设计与产品/芯片设计/Fabless/手机SoC/通信基带 | high | Arm 向 Apple 提供处理器架构/IP授权，支撑 Apple 自研 SoC 生态。 |
| Arm | 上游/设计支撑/EDA/IP/半导体IP/芯片定制 | IP授权 | Qualcomm | 中游/设计与产品/芯片设计/Fabless/手机SoC/通信基带 | high | Arm 向 Qualcomm 提供处理器架构/IP授权，支撑移动 SoC 产品。 |
| Arm | 上游/设计支撑/EDA/IP/半导体IP/芯片定制 | IP授权 | MediaTek | 中游/设计与产品/芯片设计/Fabless/手机SoC/通信基带 | high | Arm 向 MediaTek 提供处理器架构/IP授权，支撑移动 SoC 产品。 |
| Synopsys | 上游/设计支撑/EDA/IP/EDA软件 | EDA/IP供应 | NVIDIA | 中游/设计与产品/芯片设计/Fabless/AI/GPU/CPU算力芯片 | high | Synopsys 的 EDA/IP 工具链服务于 NVIDIA 等高性能芯片设计客户或合作生态。 |
| Cadence | 上游/设计支撑/EDA/IP/EDA软件 | EDA/IP供应 | NVIDIA | 中游/设计与产品/芯片设计/Fabless/AI/GPU/CPU算力芯片 | high | Cadence 的 EDA/系统设计工具链服务于 NVIDIA 等高性能芯片设计客户或合作生态。 |
| TSMC | 中游/制造/晶圆制造/Foundry-IDM/晶圆代工/Foundry | 晶圆代工 | NVIDIA | 中游/设计与产品/芯片设计/Fabless/AI/GPU/CPU算力芯片 | high | TSMC 为 NVIDIA 高端 GPU/AI 芯片提供晶圆制造或先进制程代工能力。 |
| TSMC | 中游/制造/晶圆制造/Foundry-IDM/晶圆代工/Foundry | 晶圆代工 | AMD | 中游/设计与产品/芯片设计/Fabless/AI/GPU/CPU算力芯片 | high | TSMC 为 AMD CPU/GPU/AI 芯片提供晶圆制造或先进制程代工能力。 |
| TSMC | 中游/制造/晶圆制造/Foundry-IDM/晶圆代工/Foundry | 晶圆代工 | Apple | 中游/设计与产品/芯片设计/Fabless/手机SoC/通信基带 | high | TSMC 为 Apple 自研 SoC 提供晶圆制造或先进制程代工能力。 |
| TSMC | 中游/制造/晶圆制造/Foundry-IDM/晶圆代工/Foundry | 晶圆代工 | Qualcomm | 中游/设计与产品/芯片设计/Fabless/手机SoC/通信基带 | high | TSMC 为 Qualcomm 移动 SoC 提供晶圆制造或先进制程代工能力。 |
| TSMC | 中游/制造/晶圆制造/Foundry-IDM/晶圆代工/Foundry | 晶圆代工 | MediaTek | 中游/设计与产品/芯片设计/Fabless/手机SoC/通信基带 | high | TSMC 为 MediaTek 移动 SoC 提供晶圆制造或先进制程代工能力。 |
| Samsung | 中游/制造/晶圆制造/Foundry-IDM/晶圆代工/Foundry | 晶圆代工 | Qualcomm | 中游/设计与产品/芯片设计/Fabless/手机SoC/通信基带 | high | Samsung Foundry 为 Qualcomm 部分 Snapdragon 产品提供晶圆代工能力。 |
| GlobalFoundries | 中游/制造/晶圆制造/Foundry-IDM/晶圆代工/Foundry | 晶圆代工 | AMD | 中游/设计与产品/芯片设计/Fabless/AI/GPU/CPU算力芯片 | high | GlobalFoundries 与 AMD 存在晶圆供应/制造协议关系。 |
| ASML | 上游/制造支撑/半导体设备/光刻设备 | 设备供应 | TSMC | 中游/制造/晶圆制造/Foundry-IDM/晶圆代工/Foundry | high | ASML 向 TSMC 等先进制程晶圆厂供应光刻设备。 |
| ASML | 上游/制造支撑/半导体设备/光刻设备 | 设备供应 | Samsung | 中游/制造/晶圆制造/Foundry-IDM/晶圆代工/Foundry | high | ASML 向 Samsung Foundry/半导体制造业务供应光刻设备。 |
| ASML | 上游/制造支撑/半导体设备/光刻设备 | 设备供应 | Intel | 中游/制造/晶圆制造/Foundry-IDM/IDM/特色工艺制造 | high | ASML 向 Intel 先进制造业务供应光刻设备。 |
| Applied Materials | 上游/制造支撑/半导体设备/薄膜沉积设备 | 设备供应 | TSMC | 中游/制造/晶圆制造/Foundry-IDM/晶圆代工/Foundry | high | Applied Materials 的材料工程/沉积等设备进入 TSMC 等晶圆制造生态。 |
| Lam Research | 上游/制造支撑/半导体设备/刻蚀设备 | 设备供应 | Samsung | 中游/制造/晶圆制造/Foundry-IDM/晶圆代工/Foundry | high | Lam Research 的刻蚀/沉积相关设备进入 Samsung 半导体制造生态。 |
| KLA | 上游/制造支撑/半导体设备/量测检测设备 | 设备供应 | TSMC | 中游/制造/晶圆制造/Foundry-IDM/晶圆代工/Foundry | high | KLA 的过程控制/量测检测设备进入 TSMC 等先进晶圆制造生态。 |
| Tokyo Electron | 上游/制造支撑/半导体设备/薄膜沉积设备 | 设备供应 | TSMC | 中游/制造/晶圆制造/Foundry-IDM/晶圆代工/Foundry | high | Tokyo Electron 的涂胶显影、沉积或热处理设备进入 TSMC 等晶圆制造生态。 |
| Shin-Etsu | 上游/制造支撑/半导体材料/硅片 | 材料供应 | TSMC | 中游/制造/晶圆制造/Foundry-IDM/晶圆代工/Foundry | high | Shin-Etsu 向 TSMC 等晶圆制造厂供应半导体硅片/材料。 |
| SUMCO | 上游/制造支撑/半导体材料/硅片 | 材料供应 | TSMC | 中游/制造/晶圆制造/Foundry-IDM/晶圆代工/Foundry | high | SUMCO 向 TSMC 等晶圆制造厂供应半导体硅片。 |
| TSMC | 中游/封装测试/先进封装/2.5D/3D/Chiplet先进封装 | 先进封装 | NVIDIA | 中游/设计与产品/芯片设计/Fabless/AI/GPU/CPU算力芯片 | high | TSMC CoWoS/先进封装产能服务于 NVIDIA AI GPU。 |
| TSMC | 中游/封装测试/先进封装/2.5D/3D/Chiplet先进封装 | 先进封装 | AMD | 中游/设计与产品/芯片设计/Fabless/AI/GPU/CPU算力芯片 | high | TSMC 先进封装/CoWoS 产能服务于 AMD 高性能芯片。 |
| TSMC | 中游/封装测试/先进封装/2.5D/3D/Chiplet先进封装 | 先进封装 | Broadcom | 中游/设计与产品/芯片设计/Fabless/AI/GPU/CPU算力芯片 | high | TSMC 先进封装/CoWoS 产能服务于 Broadcom 定制 AI ASIC 等产品。 |
| 通富微电 | 中游/封装测试/先进封装/2.5D/3D/Chiplet先进封装 | 封装测试 | AMD | 中游/设计与产品/芯片设计/Fabless/AI/GPU/CPU算力芯片 | high | 通富微电与 AMD 在封装测试/合资公司方面存在明确合作关系。 |
| 长电科技 | 中游/封装测试/传统封装测试/OSAT/传统OSAT封装测试 | 封装测试 | Qualcomm | 中游/设计与产品/芯片设计/Fabless/手机SoC/通信基带 | high | 长电科技与 Qualcomm 在封装测试或供应链方面存在客户/合作关系线索。 |
| ASE | 中游/封装测试/传统封装测试/OSAT/传统OSAT封装测试 | 封装测试 | Qualcomm | 中游/设计与产品/芯片设计/Fabless/手机SoC/通信基带 | high | ASE 向 Qualcomm 等移动芯片客户提供封装测试服务。 |
| Amkor | 中游/封装测试/先进封装/2.5D/3D/Chiplet先进封装 | 封装测试 | Apple | 中游/设计与产品/芯片设计/Fabless/手机SoC/通信基带 | high | Amkor 向 Apple 等客户提供先进封装/封测能力。 |
| SK hynix | 中游/产品与制造/存储/HBM/DRAM/HBM | HBM供应 | NVIDIA | 中游/设计与产品/芯片设计/Fabless/AI/GPU/CPU算力芯片 | high | SK hynix 向 NVIDIA AI GPU 生态供应 HBM 存储。 |
| Micron | 中游/产品与制造/存储/HBM/DRAM/HBM | HBM供应 | NVIDIA | 中游/设计与产品/芯片设计/Fabless/AI/GPU/CPU算力芯片 | medium | Micron 向 NVIDIA AI GPU 生态供应或导入 HBM 存储。 |
| ROHM | 中游/特色器件/功率半导体/SiC-GaN/SiC功率器件/模块 | 功率器件供应/合作 | Denso | 下游/系统需求/终端应用/系统需求/新能源汽车/汽车电子 | high | ROHM 与 Denso 在 SiC/功率器件方面存在供应或合作关系。 |
| Wolfspeed | 中游/特色器件/功率半导体/SiC-GaN/SiC衬底/外延 | SiC材料供应 | Infineon | 中游/特色器件/功率半导体/SiC-GaN/SiC功率器件/模块 | high | Wolfspeed 向 Infineon 等功率半导体厂商供应 SiC 衬底/材料。 |
| Coherent | 中游/特色器件/功率半导体/SiC-GaN/SiC衬底/外延 | SiC材料供应 | Infineon | 中游/特色器件/功率半导体/SiC-GaN/SiC功率器件/模块 | high | Coherent 向 Infineon 等功率半导体厂商供应 SiC 衬底/材料。 |
| Ibiden | 上游/制造支撑/半导体材料/封装材料/IC载板 | 封装载板供应 | Intel | 中游/封装测试/先进封装/2.5D/3D/Chiplet先进封装 | high | Ibiden 向 Intel 等高端封装/处理器客户供应 IC 载板。 |
| Shinko Electric | 上游/制造支撑/半导体材料/封装材料/IC载板 | 封装载板供应 | Intel | 中游/封装测试/先进封装/2.5D/3D/Chiplet先进封装 | high | Shinko Electric 向 Intel 等高端封装/处理器客户供应 IC 载板。 |
| Unimicron | 上游/制造支撑/半导体材料/封装材料/IC载板 | 封装载板供应 | NVIDIA | 中游/设计与产品/芯片设计/Fabless/AI/GPU/CPU算力芯片 | medium | Unimicron 向 NVIDIA AI 芯片生态供应高端 IC 载板线索。 |
| Ibiden | 上游/制造支撑/半导体材料/封装材料/IC载板 | 封装载板供应 | NVIDIA | 中游/设计与产品/芯片设计/Fabless/AI/GPU/CPU算力芯片 | high | Ibiden 向 NVIDIA AI 芯片生态供应高端 IC 载板线索。 |
