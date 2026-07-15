# -*- coding: utf-8 -*-
"""图谱只读校验：核对数据层完整性与链路连通性（不连数据库）。

用法：python scripts/verify_graph.py
退出码 0 表示全部通过，非 0 表示有 FAIL 项。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import csv
from collections import defaultdict

from kg_common import read_csv

DATA = ROOT / "data"
LEADERS = DATA / "company_pool" / "company_leaders_stage_3.csv"
RELATIONSHIPS = DATA / "company_pool" / "company_relationships_stage_4.csv"
L1_L4 = DATA / "business_graph" / "stage5_l1_l4_segments.csv"
PRODUCTS = DATA / "business_graph" / "stage5_product_services.csv"
COMPANY_PRODUCT = DATA / "business_graph" / "stage6_company_product_relations.csv"
COMPETITION = DATA / "business_graph" / "stage6_company_competition.csv"
DC_RELATIONS = DATA / "business_graph" / "stage7_digital_china_relations.csv"
OPPORTUNITIES = DATA / "business_graph" / "stage8_business_opportunities.csv"

failures: list[str] = []
checks: list[str] = []


def ok(msg: str) -> None:
    checks.append(f"PASS  {msg}")


def fail(msg: str) -> None:
    failures.append(msg)
    checks.append(f"FAIL  {msg}")


def load(path: Path) -> list[dict[str, str]]:
    return read_csv(path) if path.exists() else []


# ---------------------------------------------------------------------------
# 1. 基础计数与文件存在性
# ---------------------------------------------------------------------------
leaders = load(LEADERS)
l1_l4 = load(L1_L4)
products = load(PRODUCTS)
company_product = load(COMPANY_PRODUCT)
competition = load(COMPETITION)
dc_relations = load(DC_RELATIONS)
opportunities = load(OPPORTUNITIES)
relationships = load(RELATIONSHIPS)

required_temporal_fields = {
    "record_id",
    "data_as_of",
    "first_seen_at",
    "last_verified_at",
    "current_validity",
    "claim_nature",
    "time_precision",
    "temporal_basis",
}

for name, rows_for_check in [
    ("stage3 龙头判断", leaders),
    ("stage4 企业关系", relationships),
    ("stage6 公司产品关系", company_product),
    ("stage7 神州数码关系", dc_relations),
    ("stage8 商机分析", opportunities),
]:
    if not rows_for_check:
        continue
    missing_fields = required_temporal_fields - set(rows_for_check[0].keys())
    if missing_fields:
        fail(f"{name} 缺少时间治理字段：{sorted(missing_fields)}")
    else:
        empty_required = [
            field
            for field in required_temporal_fields
            if any(not row.get(field, "").strip() for row in rows_for_check)
        ]
        if empty_required:
            fail(f"{name} 时间治理字段存在空值：{sorted(empty_required)}")
        else:
            ok(f"{name} 已补齐时间治理字段")

if not l1_l4:
    fail("stage5 L1-L4 环节表为空或缺失")
else:
    ok(f"L1-L4 环节：{len(l1_l4)} 个")

if len(products) == 0:
    fail("产品/服务表为空")
else:
    ok(f"产品/服务：{len(products)} 个")

# 2. 全部 L4 都有产品（断链消除）
l4_codes_with_product = {p["l4_code"] for p in products}
l4_codes = {x["l4_code"] for x in l1_l4}
l4_without_product = l4_codes - l4_codes_with_product
if l4_without_product:
    fail(f"无产品的 L4：{sorted(l4_without_product)}")
else:
    ok("全部 L4 环节均挂载了产品/服务（断链消除）")

# 3. 需求端使用/需求关联存在
demand_side_uses = [
    r for r in company_product
    if r.get("relation_type") == "USES" and r.get("derivation") == "demand_side_presumed"
]
if not demand_side_uses:
    fail("需求端使用/需求关联边为 0，需求端推导未生效")
else:
    ok(f"需求端使用/需求关联边：{len(demand_side_uses)} 条")

# 4. 竞争边
if not competition:
    fail("推定竞争关系表为空或缺失")
else:
    presumed = [r for r in competition if r.get("derivation") == "same_product_leader_presumed"]
    relation_types = {r.get("relationship_type") for r in competition}
    if relation_types != {"推定竞争"}:
        fail(f"推定竞争关系类型异常：{relation_types}")
    ok(f"推定竞争关系：{len(competition)} 条（推定 {len(presumed)}）")

# 5. Stage7 神州数码关系状态枚举覆盖
tiers = {r.get("asset_tier", "") for r in dc_relations}
valid_tiers = {"存量客户", "生态伙伴", "潜力客户", "待验证", ""}
invalid = tiers - valid_tiers
if invalid:
    fail(f"Stage7 业务分层字段出现非法枚举值：{invalid}")
else:
    ok(f"Stage7 业务分层字段枚举合法，分布：{ {t: sum(1 for r in dc_relations if r.get('asset_tier')==t) for t in tiers if t} }")

# 6. Stage8 商机文件仅作为后续战略分析草稿，不导入当前 Neo4j 主图
qualified = {"存量客户", "生态伙伴", "潜力客户"}
opp_companies = {r["company_name"] for r in opportunities}
dc_by_company = {r["company_name"]: r.get("asset_tier", "") for r in dc_relations}
bad_opp = [c for c in opp_companies if dc_by_company.get(c) == "待验证"]
if bad_opp:
    fail(f"待验证层公司仍生成了商机：{bad_opp}")
else:
    ok(f"Stage8 商机草稿 {len(opportunities)} 条，均由合格 tier 生成；当前 Neo4j 主图不导入该层")

# 7. 孤立公司占比（无任何关系的公司）
companies_in_leaders = {r["company_name"] for r in leaders}
companies_in_relations = set()
for r in company_product:
    companies_in_relations.add(r["company_name"])
for r in competition:
    companies_in_relations.add(r["source_company"])
    companies_in_relations.add(r["target_company"])
for r in relationships:
    companies_in_relations.add(r.get("source_company", ""))
    companies_in_relations.add(r.get("target_company", ""))
for r in dc_relations:
    companies_in_relations.add(r.get("company_name", ""))
companies_in_relations.discard("")
isolated = companies_in_leaders - companies_in_relations
isolated_ratio = len(isolated) / len(companies_in_leaders) if companies_in_leaders else 0
if isolated_ratio > 0.15:
    fail(f"孤立公司占比 {isolated_ratio:.1%}（{len(isolated)}/{len(companies_in_leaders)}），超过 15% 阈值")
else:
    ok(f"孤立公司占比 {isolated_ratio:.1%}（{len(isolated)}/{len(companies_in_leaders)}），低于 15% 阈值")

# 8. stage4 关系全部有 relationship_id（稳定 key）
missing_id = [r for r in relationships if not r.get("relationship_id")]
if missing_id:
    fail(f"stage4 有 {len(missing_id)} 条关系缺少 relationship_id（导入 key 不稳定）")
else:
    ok(f"stage4 全部 {len(relationships)} 条关系均有 relationship_id（key 稳定）")

# 9. 产品-环节引用一致性
product_l4_codes = {p["l4_code"] for p in products}
cp_orphans = [r for r in company_product if r.get("l4_code") and r["l4_code"] not in l4_codes]
if cp_orphans:
    fail(f"公司-产品关系有 {len(cp_orphans)} 条引用了不存在的 L4 编码")
else:
    ok("公司-产品关系的 L4 编码全部可回链环节表")

# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------
print("\n".join(checks))
print("\n" + "=" * 60)
if failures:
    print(f"结果：{len(failures)} 项 FAIL")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print(f"结果：全部 {len(checks)} 项 PASS")
sys.exit(0)
