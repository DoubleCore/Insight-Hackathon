from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "data" / "quality" / "graph_quality_audit.jsonl"
LEADERS_PATH = ROOT / "data" / "company_pool" / "company_leaders_stage_3.csv"
RELATIONSHIPS_PATH = ROOT / "data" / "company_pool" / "company_relationships_stage_4.csv"

P1_TYPES = {
    "high_confidence_weak_leader_evidence",
    "high_confidence_weak_company_relationship_evidence",
}

DOWNGRADE_NOTE = (
    "证据强度审计显示该判断主要依赖搜索结果或 B/B- 来源；"
    "已降为 medium，待补官网、公告、年报、招股书或权威市场份额报告后再恢复 high。"
)


def read_audit_targets() -> tuple[set[tuple[str, str]], set[str]]:
    leader_targets: set[tuple[str, str]] = set()
    relationship_targets: set[str] = set()
    if not AUDIT_PATH.exists():
        raise FileNotFoundError(f"缺少审计报告，请先运行 scripts/audit_graph_quality.py --write: {AUDIT_PATH}")

    with AUDIT_PATH.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            issue = json.loads(line)
            if issue.get("issue_type") not in P1_TYPES:
                continue
            if issue["issue_type"] == "high_confidence_weak_leader_evidence":
                leader_targets.add((issue.get("entity", ""), issue.get("relation", "")))
            elif issue["issue_type"] == "high_confidence_weak_company_relationship_evidence":
                row_ref = issue.get("row_ref", "")
                try:
                    line_no = int(row_ref.rsplit(":", 1)[1])
                except (IndexError, ValueError):
                    continue
                relationship_targets.add(str(line_no))
    return leader_targets, relationship_targets


def append_note(existing: str) -> str:
    existing = (existing or "").strip()
    if DOWNGRADE_NOTE in existing:
        return existing
    if not existing:
        return DOWNGRADE_NOTE
    return f"{existing} {DOWNGRADE_NOTE}"


def update_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def downgrade_leaders(targets: set[tuple[str, str]]) -> int:
    with LEADERS_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    changed = 0
    for row in rows:
        key = (row.get("company_name", "").strip(), row.get("subsegment_name", "").strip())
        if key not in targets or row.get("confidence") != "high":
            continue
        row["confidence"] = "medium"
        row["limitations"] = append_note(row.get("limitations", ""))
        changed += 1

    update_csv(LEADERS_PATH, rows, fieldnames)
    return changed


def downgrade_relationships(target_lines: set[str]) -> int:
    with RELATIONSHIPS_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    changed = 0
    for idx, row in enumerate(rows, start=2):
        if str(idx) not in target_lines or row.get("confidence") != "high":
            continue
        row["confidence"] = "medium"
        row["limitations"] = append_note(row.get("limitations", ""))
        changed += 1

    update_csv(RELATIONSHIPS_PATH, rows, fieldnames)
    return changed


def main() -> None:
    leader_targets, relationship_targets = read_audit_targets()
    result = {
        "leader_targets": len(leader_targets),
        "relationship_targets": len(relationship_targets),
        "leaders_downgraded": downgrade_leaders(leader_targets),
        "relationships_downgraded": downgrade_relationships(relationship_targets),
    }
    result["total_downgraded"] = result["leaders_downgraded"] + result["relationships_downgraded"]
    result["target_issue_types"] = dict(Counter(P1_TYPES))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
