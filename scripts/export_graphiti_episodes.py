from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from temporal_enrichment import read_csv_rows
from graphiti_layer_mapping import meta_for_legacy_saga

DATA = ROOT / "data"
OUT_DIR = DATA / "graphiti"
OUT_JSONL = OUT_DIR / "semiconductor_episodes.jsonl"
OUT_SUMMARY = OUT_DIR / "semiconductor_episodes_summary.md"

LEADERS = DATA / "company_pool" / "company_leaders_stage_3.csv"
RELATIONSHIPS = DATA / "company_pool" / "company_relationships_stage_4.csv"
COMPANY_PRODUCT = DATA / "business_graph" / "stage6_company_product_relations.csv"
COMPANY_COMPETITION = DATA / "business_graph" / "stage6_company_competition.csv"
DC_RELATIONS = DATA / "business_graph" / "stage7_digital_china_relations.csv"

GROUP_ID = "semiconductor_dc_kg"

RELATION_TYPE_CN = {
    "PRODUCES": "生产",
    "SELLS": "销售",
    "USES": "使用",
    "PROCURES": "采购",
    "INTEGRATES": "集成",
}


def parse_reference_time(data_as_of: str) -> str:
    value = (data_as_of or "2026-07-08").strip()
    if "T" in value:
        return value.replace("+00:00", "Z")
    return f"{value}T00:00:00Z"


def temporal_block(row: dict[str, str]) -> str:
    return (
        f"数据截至时间：{row.get('data_as_of', '')}。\n"
        f"首次入库时间：{row.get('first_seen_at', '')}。\n"
        f"最近核验时间：{row.get('last_verified_at', '')}。\n"
        f"事件日期：{row.get('event_date', '')}。\n"
        f"事件开始时间：{row.get('event_start_at', '')}。\n"
        f"事件结束时间：{row.get('event_end_at', '')}。\n"
        f"时间精度：{row.get('time_precision', '')}。\n"
        f"时间依据：{row.get('temporal_basis', '')}。\n"
        f"证据发布日期：{row.get('source_publish_dates', '')}。\n"
        f"当前有效性：{row.get('current_validity', '')}。\n"
        f"判断性质：{row.get('claim_nature', '')}。\n"
        f"证据ID：{row.get('evidence_ids', '')}。"
    )


def base_episode(row: dict[str, str], stage: str, name: str, body: str) -> dict[str, str]:
    saga_meta = meta_for_legacy_saga(stage)
    record_id = row.get("record_id") or f"{stage}::{name}"
    layer_properties = saga_meta.as_properties()
    return {
        "episode_id": record_id,
        "episode_name": name,
        "episode_body": body,
        "source": "text",
        "source_description": saga_meta.source_description,
        "reference_time": parse_reference_time(row.get("data_as_of", "")),
        "group_id": GROUP_ID,
        "saga": saga_meta.saga_name,
        **layer_properties,
    }


def build_leadership_episode(row: dict[str, str]) -> dict[str, str]:
    company = row.get("company_name", "")
    segment = row.get("subsegment_name", "")
    leader_level = row.get("leader_level", "")
    body = (
        f"截至 {row.get('data_as_of', '')}，公开资料支持 {company} 是 {segment} 环节的{leader_level}。\n"
        f"判断依据：{row.get('selection_basis', '')}\n"
        f"置信度：{row.get('confidence', '')}。\n"
        f"局限说明：{row.get('limitations', '')}\n"
        f"{temporal_block(row)}"
    )
    return base_episode(row, "stage3_leadership", f"{company}-{segment}-龙头判断", body)


def build_company_relationship_episode(row: dict[str, str]) -> dict[str, str]:
    source = row.get("source_company", "")
    target = row.get("target_company", "")
    relation = row.get("relationship_type", "")
    body = (
        f"截至 {row.get('data_as_of', '')}，公开资料支持 {source} 与 {target} 存在 {relation} 关系。\n"
        f"关系方向：{row.get('relationship_direction', '')}。\n"
        f"关系说明：{row.get('relationship_claim', '')}\n"
        f"置信度：{row.get('confidence', '')}。\n"
        f"局限说明：{row.get('limitations', '')}\n"
        f"{temporal_block(row)}"
    )
    return base_episode(row, "stage4_company_relationship", f"{source}-{target}-{relation}", body)


def build_company_product_episode(row: dict[str, str]) -> dict[str, str]:
    company = row.get("company_name", "")
    product = row.get("product_service_name", "")
    relation = RELATION_TYPE_CN.get(row.get("relation_type", ""), row.get("relation_type", ""))
    body = (
        f"截至 {row.get('data_as_of', '')}，公开资料支持 {company} {relation} {product}。\n"
        f"对应产业链环节：{row.get('l4_name', '')}。\n"
        f"判断依据：{row.get('basis', '')}\n"
        f"置信度：{row.get('confidence', '')}。\n"
        f"是否需要内部验证：{row.get('requires_internal_validation', '')}。\n"
        f"{temporal_block(row)}"
    )
    return base_episode(row, "stage6_company_product", f"{company}-{relation}-{product}", body)


def build_company_competition_episode(row: dict[str, str]) -> dict[str, str]:
    source = row.get("source_company", "")
    target = row.get("target_company", "")
    relation = row.get("relationship_type", "")
    body = (
        f"截至 {row.get('data_as_of', '')}，{source} 与 {target} 存在 {relation} 候选关系。\n"
        f"判断依据：{row.get('basis', '')}\n"
        f"推导方式：{row.get('derivation', '')}。\n"
        f"置信度：{row.get('confidence', '')}。\n"
        f"是否需要内部验证：{row.get('requires_internal_validation', '')}。\n"
        f"注意：该关系来自同环节同产品龙头推定，不代表公开资料已经证明两家公司发生交易、合作或直接竞争事件。\n"
        f"{temporal_block(row)}"
    )
    return base_episode(
        row,
        "stage6_company_competition",
        f"{source}-{target}-{relation}候选",
        body,
    )


def build_digital_china_episode(row: dict[str, str]) -> dict[str, str]:
    company = row.get("company_name", "")
    status = row.get("relationship_status", "")
    body = (
        f"截至 {row.get('data_as_of', '')}，{company} 与神州数码的公开关系状态为 {status}。\n"
        f"关系类型：{row.get('relationship_type', '')}。\n"
        f"判断依据：{row.get('relationship_basis', '')}\n"
        f"客户资产分层：{row.get('asset_tier', '')}。\n"
        f"是否需要内部验证：{row.get('requires_internal_validation', '')}。\n"
        f"局限说明：{row.get('limitations', '')}\n"
        f"{temporal_block(row)}"
    )
    return base_episode(row, "stage7_digital_china", f"{company}-神州数码关系状态", body)


def build_episodes() -> list[dict[str, str]]:
    episodes: list[dict[str, str]] = []
    episodes.extend(build_leadership_episode(row) for row in read_csv_rows(LEADERS))
    episodes.extend(build_company_relationship_episode(row) for row in read_csv_rows(RELATIONSHIPS))
    episodes.extend(build_company_product_episode(row) for row in read_csv_rows(COMPANY_PRODUCT))
    episodes.extend(build_company_competition_episode(row) for row in read_csv_rows(COMPANY_COMPETITION))
    episodes.extend(build_digital_china_episode(row) for row in read_csv_rows(DC_RELATIONS))
    return episodes


def write_outputs(episodes: list[dict[str, str]]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_JSONL.open("w", encoding="utf-8") as handle:
        for episode in episodes:
            handle.write(json.dumps(episode, ensure_ascii=False) + "\n")
    by_saga: dict[str, int] = {}
    for episode in episodes:
        key = str(episode["display_name"])
        by_saga[key] = by_saga.get(key, 0) + 1
    lines = [
        "# 图谱事实输入单元导出摘要",
        "",
        f"- 事实输入单元总数：{len(episodes)}",
        f"- group_id：{GROUP_ID}",
        f"- 输出文件：`{OUT_JSONL.as_posix()}`",
        "",
        "## 主流程分组数量",
        "",
    ]
    lines.extend(f"- {key}: {count}" for key, count in sorted(by_saga.items()))
    OUT_SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    episodes = build_episodes()
    write_outputs(episodes)
    print(f"exported {len(episodes)} episodes to {OUT_JSONL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
