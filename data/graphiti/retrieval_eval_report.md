# Graphiti 问答召回评估报告

- Gold 问题数：33
- 检索模式：semantic_only, lexical_only, hybrid
- K 值：5, 8, 10, 20
- 主验收 K：8

## 整体指标

| mode | K | questions | Recall@K | Hit@K | Strict Hit@K | MRR@K |
|---|---:|---:|---:|---:|---:|---:|
| hybrid | 5 | 33 | 0.730 | 0.909 | 0.576 | 0.801 |
| hybrid | 8 | 33 | 0.808 | 0.909 | 0.667 | 0.801 |
| hybrid | 10 | 33 | 0.879 | 0.970 | 0.758 | 0.807 |
| hybrid | 20 | 33 | 0.894 | 0.970 | 0.788 | 0.807 |
| lexical_only | 5 | 33 | 0.717 | 0.879 | 0.545 | 0.817 |
| lexical_only | 8 | 33 | 0.775 | 0.879 | 0.667 | 0.817 |
| lexical_only | 10 | 33 | 0.806 | 0.909 | 0.697 | 0.820 |
| lexical_only | 20 | 33 | 0.896 | 0.939 | 0.848 | 0.822 |
| semantic_only | 5 | 33 | 0.624 | 0.879 | 0.424 | 0.622 |
| semantic_only | 8 | 33 | 0.725 | 0.909 | 0.545 | 0.626 |
| semantic_only | 10 | 33 | 0.747 | 0.970 | 0.545 | 0.632 |
| semantic_only | 20 | 33 | 0.848 | 0.970 | 0.727 | 0.632 |

## 分类指标（K=8）

| mode | category | questions | Recall | Hit Rate | Strict Hit Rate | MRR |
|---|---|---:|---:|---:|---:|---:|
| hybrid | 企业关系 | 6 | 0.750 | 0.833 | 0.667 | 0.667 |
| hybrid | 公司-产品关系 | 6 | 0.778 | 0.833 | 0.667 | 0.708 |
| hybrid | 时间字段关系 | 3 | 0.667 | 0.667 | 0.667 | 0.667 |
| hybrid | 神州数码关系 | 6 | 1.000 | 1.000 | 1.000 | 1.000 |
| hybrid | 风险口径 | 4 | 0.875 | 1.000 | 0.750 | 0.542 |
| hybrid | 龙头判断 | 8 | 0.750 | 1.000 | 0.375 | 1.000 |
| lexical_only | 企业关系 | 6 | 0.750 | 0.833 | 0.667 | 0.750 |
| lexical_only | 公司-产品关系 | 6 | 0.861 | 1.000 | 0.667 | 0.742 |
| lexical_only | 时间字段关系 | 3 | 0.667 | 0.667 | 0.667 | 0.667 |
| lexical_only | 神州数码关系 | 6 | 0.889 | 1.000 | 0.833 | 1.000 |
| lexical_only | 风险口径 | 4 | 0.500 | 0.500 | 0.500 | 0.500 |
| lexical_only | 龙头判断 | 8 | 0.823 | 1.000 | 0.625 | 1.000 |
| semantic_only | 企业关系 | 6 | 0.806 | 1.000 | 0.667 | 0.485 |
| semantic_only | 公司-产品关系 | 6 | 0.778 | 0.833 | 0.667 | 0.597 |
| semantic_only | 时间字段关系 | 3 | 0.667 | 0.667 | 0.667 | 0.667 |
| semantic_only | 神州数码关系 | 6 | 0.944 | 1.000 | 0.833 | 0.833 |
| semantic_only | 风险口径 | 4 | 0.875 | 1.000 | 0.750 | 0.646 |
| semantic_only | 龙头判断 | 8 | 0.406 | 0.875 | 0.000 | 0.573 |

## Hybrid 未命中问题（K=8）

- `rel_huawei_smic_2015` 华为和中芯国际在2015年有什么公开联合研发投资关系？：漏召回 华为-中芯国际2015联合研发投资
- `rel_asml_tsmc_equipment` ASML 和 TSMC 在光刻设备上有什么关系？：漏召回 ASML-TSMC光刻设备关系
- `product_hbm_memory` HBM 和 AI 存储相关的公司产品关系有哪些？：漏召回 SK hynix-HBM先进封装能力; Micron-HBM供应NVIDIA

## 口径说明

- 本报告只评估检索召回，不评估 DeepSeek 最终答案生成质量。
- 命中规则支持 evidence ID、实体名、事实关键词组合匹配；不依赖 Graphiti 自动生成的 uuid。
- `stage8_business_opportunities.csv` 未进入 Graphiti，因此不作为 gold 标准事实。
