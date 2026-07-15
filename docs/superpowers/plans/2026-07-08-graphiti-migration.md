# Graphiti 迁移 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把现有半导体产业链 Neo4j/CSV 图谱迁移为 Graphiti 可消费的 temporal graph，让 Graphiti 能基于我们的产业链、公司、证据和神州数码业务关系进行问答检索。

**Architecture:** 不直接修改 Graphiti 内核，也不把当前 Neo4j 自定义节点硬塞进 Graphiti。先在本项目里把 CSV/JSONL 主数据补齐时间治理字段，再导出标准 Graphiti episodes JSONL，最后调用 `graphiti_core.Graphiti.add_episode()` 顺序导入到 Graphiti 自己的节点/边模型中。现有 Neo4j Browser 图谱继续保留，Graphiti 图谱作为问答引擎的独立 ingestion 结果。

**Tech Stack:** Python 3, unittest, CSV/JSONL, Neo4j, Graphiti `graphiti_core`, PowerShell, 当前 `task1` Conda 环境。

---

## File Structure

- Modify: `scripts/kg_common.py`
  - 增加通用 JSONL 读取、日期归一化、证据聚合小工具；不放业务逻辑。
- Create: `scripts/temporal_enrichment.py`
  - 给 Stage3/4/6/7/8 CSV 批量补时间治理字段，包括数据截至、首次入库、最近核验、事件开始、事件结束、时间精度和时间依据。
- Create: `scripts/export_graphiti_episodes.py`
  - 从现有 CSV/JSONL 生成 `data/graphiti/semiconductor_episodes.jsonl`。
- Create: `scripts/import_graphiti_episodes.py`
  - 调用本地 `graphiti-main/graphiti-main` 的 `graphiti_core`，把 episode JSONL 导入 Graphiti。
- Create: `scripts/verify_graphiti_export.py`
  - 离线校验 episode 文件字段、数量、时间字段和证据引用。
- Modify: `scripts/verify_graph.py`
  - 增加时间治理字段存在性校验。
- Create: `tests/test_temporal_enrichment.py`
  - 测试时间字段补齐和证据日期聚合。
- Create: `tests/test_graphiti_episode_export.py`
  - 测试 Graphiti episode 导出格式。
- Create: `data/graphiti/.gitkeep`
  - 保留输出目录。
- Create after running scripts: `data/graphiti/semiconductor_episodes.jsonl`
  - Graphiti ingestion 输入。
- Create after running scripts: `data/graphiti/semiconductor_episodes_summary.md`
  - 导出摘要，方便验收说明。

---

### Task 1: Add Temporal Enrichment Helpers

**Files:**
- Modify: `scripts/kg_common.py`
- Test: `tests/test_temporal_enrichment.py`

- [ ] **Step 1: Write failing tests for evidence date aggregation**

Create `tests/test_temporal_enrichment.py` with:

```python
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.temporal_enrichment import (
    DATE_SNAPSHOT,
    add_temporal_fields,
    aggregate_evidence_dates,
    load_evidence_index,
)


class TemporalEnrichmentTest(unittest.TestCase):
    def test_load_evidence_index_reads_jsonl_by_evidence_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "evidence.jsonl"
            path.write_text(
                '{"evidence_id":"E1","publish_date":"2025-01-02T10:00:00+08:00","retrieved_at":"2026-07-05T11:00:00+08:00","source_grade":"A"}\n',
                encoding="utf-8",
            )

            evidence = load_evidence_index([path])

        self.assertIn("E1", evidence)
        self.assertEqual(evidence["E1"]["publish_date"], "2025-01-02T10:00:00+08:00")

    def test_aggregate_evidence_dates_deduplicates_dates(self) -> None:
        evidence = {
            "E1": {
                "publish_date": "2025-01-02T10:00:00+08:00",
                "retrieved_at": "2026-07-05T11:00:00+08:00",
                "source_grade": "A",
            },
            "E2": {
                "publish_date": "2025-01-02T10:00:00+08:00",
                "retrieved_at": "2026-07-06T12:00:00+08:00",
                "source_grade": "B-",
            },
        }

        result = aggregate_evidence_dates(["E1", "E2"], evidence)

        self.assertEqual(result["source_publish_dates"], "2025-01-02")
        self.assertEqual(result["source_retrieved_dates"], "2026-07-05;2026-07-06")
        self.assertEqual(result["primary_evidence_id"], "E1")
        self.assertEqual(result["evidence_grade_summary"], "A:1;B-:1")

    def test_add_temporal_fields_marks_search_snapshot_claim(self) -> None:
        row = {
            "company_name": "NVIDIA",
            "evidence_ids": "E1;E2",
            "confidence": "high",
        }
        evidence = {
            "E1": {
                "publish_date": "2025-01-02T10:00:00+08:00",
                "retrieved_at": "2026-07-05T11:00:00+08:00",
                "source_grade": "A",
            },
            "E2": {
                "publish_date": "",
                "retrieved_at": "2026-07-06T12:00:00+08:00",
                "source_grade": "B-",
            },
        }

        enriched = add_temporal_fields(row, evidence, claim_nature="事实判断")

        self.assertEqual(enriched["data_as_of"], DATE_SNAPSHOT)
        self.assertEqual(enriched["first_seen_at"], DATE_SNAPSHOT)
        self.assertEqual(enriched["last_verified_at"], "2026-07-06")
        self.assertEqual(enriched["source_publish_dates"], "2025-01-02")
        self.assertEqual(enriched["current_validity"], "当前支持")
        self.assertEqual(enriched["claim_nature"], "事实判断")
        self.assertEqual(enriched["event_start_at"], "")
        self.assertEqual(enriched["event_end_at"], "")
        self.assertEqual(enriched["time_precision"], "unknown")
        self.assertEqual(enriched["temporal_basis"], "检索快照")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m unittest tests.test_temporal_enrichment -v
```

Expected: FAIL because `scripts.temporal_enrichment` does not exist.

- [ ] **Step 3: Implement temporal helper module**

Create `scripts/temporal_enrichment.py` with:

```python
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

DATE_SNAPSHOT = "2026-07-08"

TEMPORAL_FIELDS = [
    "record_id",
    "data_as_of",
    "first_seen_at",
    "last_verified_at",
    "event_date",
    "event_start_at",
    "event_end_at",
    "time_precision",
    "temporal_basis",
    "source_publish_dates",
    "source_retrieved_dates",
    "current_validity",
    "claim_nature",
    "primary_evidence_id",
    "evidence_grade_summary",
    "verification_method",
    "needs_refresh_after",
    "risk_note",
]


def split_ids(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.replace(",", ";").split(";") if part.strip()]


def normalize_date(raw: str | None) -> str:
    if not raw:
        return ""
    value = raw.strip()
    if len(value) >= 10 and value[4] == "-" and value[7] == "-":
        return value[:10]
    return value


def load_evidence_index(paths: list[Path]) -> dict[str, dict[str, Any]]:
    evidence: dict[str, dict[str, Any]] = {}
    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                evidence_id = str(item.get("evidence_id", "")).strip()
                if evidence_id:
                    evidence[evidence_id] = item
    return evidence


def aggregate_evidence_dates(
    evidence_ids: list[str],
    evidence: dict[str, dict[str, Any]],
) -> dict[str, str]:
    publish_dates: list[str] = []
    retrieved_dates: list[str] = []
    grades: Counter[str] = Counter()
    primary = ""
    for evidence_id in evidence_ids:
        item = evidence.get(evidence_id, {})
        if not item:
            continue
        if not primary:
            primary = evidence_id
        publish_date = normalize_date(str(item.get("publish_date", "")))
        retrieved_date = normalize_date(str(item.get("retrieved_at", "")))
        if publish_date:
            publish_dates.append(publish_date)
        if retrieved_date:
            retrieved_dates.append(retrieved_date)
        grade = str(item.get("source_grade", "")).strip()
        if grade:
            grades[grade] += 1

    grade_order = ["A", "A-", "B", "B-", "unknown"]
    grade_summary = ";".join(
        f"{grade}:{grades[grade]}" for grade in grade_order if grades.get(grade, 0) > 0
    )
    other_grades = sorted(g for g in grades if g not in grade_order)
    if other_grades:
        suffix = ";".join(f"{grade}:{grades[grade]}" for grade in other_grades)
        grade_summary = f"{grade_summary};{suffix}" if grade_summary else suffix

    return {
        "source_publish_dates": ";".join(sorted(set(publish_dates))),
        "source_retrieved_dates": ";".join(sorted(set(retrieved_dates))),
        "primary_evidence_id": primary,
        "evidence_grade_summary": grade_summary,
    }


def infer_last_verified_at(source_retrieved_dates: str) -> str:
    dates = [part for part in source_retrieved_dates.split(";") if part]
    return max(dates) if dates else DATE_SNAPSHOT


def add_temporal_fields(
    row: dict[str, str],
    evidence: dict[str, dict[str, Any]],
    *,
    claim_nature: str,
    record_id: str = "",
    current_validity: str = "当前支持",
    event_date: str = "",
    event_start_at: str = "",
    event_end_at: str = "",
    time_precision: str = "unknown",
    temporal_basis: str = "检索快照",
    verification_method: str = "公开资料检索",
    needs_refresh_after: str = "2026-10-08",
    risk_note: str = "",
) -> dict[str, str]:
    evidence_ids = split_ids(row.get("evidence_ids"))
    aggregate = aggregate_evidence_dates(evidence_ids, evidence)
    enriched = dict(row)
    enriched.update(
        {
            "record_id": record_id or row.get("record_id", ""),
            "data_as_of": row.get("data_as_of") or DATE_SNAPSHOT,
            "first_seen_at": row.get("first_seen_at") or DATE_SNAPSHOT,
            "last_verified_at": row.get("last_verified_at")
            or infer_last_verified_at(aggregate["source_retrieved_dates"]),
            "event_date": row.get("event_date") or event_date,
            "event_start_at": row.get("event_start_at") or event_start_at,
            "event_end_at": row.get("event_end_at") or event_end_at,
            "time_precision": row.get("time_precision") or time_precision,
            "temporal_basis": row.get("temporal_basis") or temporal_basis,
            "source_publish_dates": row.get("source_publish_dates")
            or aggregate["source_publish_dates"],
            "source_retrieved_dates": row.get("source_retrieved_dates")
            or aggregate["source_retrieved_dates"],
            "current_validity": row.get("current_validity") or current_validity,
            "claim_nature": row.get("claim_nature") or claim_nature,
            "primary_evidence_id": row.get("primary_evidence_id")
            or aggregate["primary_evidence_id"],
            "evidence_grade_summary": row.get("evidence_grade_summary")
            or aggregate["evidence_grade_summary"],
            "verification_method": row.get("verification_method") or verification_method,
            "needs_refresh_after": row.get("needs_refresh_after") or needs_refresh_after,
            "risk_note": row.get("risk_note") or risk_note,
        }
    )
    return enriched


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
```

- [ ] **Step 4: Run the helper tests**

Run:

```powershell
python -m unittest tests.test_temporal_enrichment -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add scripts/temporal_enrichment.py tests/test_temporal_enrichment.py
git commit -m "feat: add temporal enrichment helpers"
```

---

### Task 2: Batch-Enrich Existing CSVs With Time Governance Fields

**Files:**
- Modify: `scripts/temporal_enrichment.py`
- Modify: `scripts/verify_graph.py`
- Test: `tests/test_temporal_enrichment.py`
- Data output: Stage3/4/6/7/8 CSVs updated in place

- [ ] **Step 1: Add failing tests for table-specific record IDs**

Append to `tests/test_temporal_enrichment.py`:

```python
    def test_build_record_id_uses_stable_business_keys(self) -> None:
        from scripts.temporal_enrichment import build_record_id

        self.assertEqual(
            build_record_id(
                "stage3",
                {
                    "company_name": "NVIDIA",
                    "subsegment_name": "AI/GPU/CPU算力芯片",
                },
                1,
            ),
            "stage3::NVIDIA::AI/GPU/CPU算力芯片",
        )
        self.assertEqual(
            build_record_id("stage4", {"relationship_id": "R4-001"}, 1),
            "stage4::R4-001",
        )
        self.assertEqual(
            build_record_id(
                "stage6",
                {
                    "company_name": "NVIDIA",
                    "product_service_name": "AI GPU",
                    "relation_type": "PRODUCES",
                },
                1,
            ),
            "stage6::NVIDIA::PRODUCES::AI GPU",
        )
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m unittest tests.test_temporal_enrichment.TemporalEnrichmentTest.test_build_record_id_uses_stable_business_keys -v
```

Expected: FAIL because `build_record_id` is not defined.

- [ ] **Step 3: Add table-specific enrichment functions**

Append to `scripts/temporal_enrichment.py`:

```python
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

EVIDENCE_PATHS = [
    DATA / "evidence" / "evidence_stage_1.jsonl",
    DATA / "evidence" / "evidence_stage_2.jsonl",
    DATA / "evidence" / "evidence_stage_3.jsonl",
    DATA / "evidence" / "evidence_stage_4_relationships.jsonl",
    DATA / "evidence" / "evidence_stage_7_digital_china.jsonl",
]

TABLES = {
    "stage3": DATA / "company_pool" / "company_leaders_stage_3.csv",
    "stage4": DATA / "company_pool" / "company_relationships_stage_4.csv",
    "stage6": DATA / "business_graph" / "stage6_company_product_relations.csv",
    "stage7": DATA / "business_graph" / "stage7_digital_china_relations.csv",
    "stage8": DATA / "business_graph" / "stage8_business_opportunities.csv",
}


def build_record_id(stage: str, row: dict[str, str], index: int) -> str:
    if stage == "stage3":
        return f"stage3::{row.get('company_name', '')}::{row.get('subsegment_name', '')}"
    if stage == "stage4":
        relationship_id = row.get("relationship_id") or f"row-{index:04d}"
        return f"stage4::{relationship_id}"
    if stage == "stage6":
        return (
            f"stage6::{row.get('company_name', '')}::"
            f"{row.get('relation_type', '')}::{row.get('product_service_name', '')}"
        )
    if stage == "stage7":
        return f"stage7::{row.get('company_name', '')}::{row.get('relationship_status', '')}"
    if stage == "stage8":
        opportunity_id = row.get("opportunity_id") or f"row-{index:04d}"
        return f"stage8::{opportunity_id}"
    return f"{stage}::row-{index:04d}"


def claim_nature_for_stage(stage: str, row: dict[str, str]) -> str:
    if stage in {"stage3", "stage4"}:
        return "事实判断"
    if stage == "stage6":
        if row.get("requires_internal_validation") == "true":
            return "推断关系"
        return "事实判断"
    if stage == "stage7":
        status = row.get("relationship_status", "")
        if status == "confirmed_public_relationship":
            return "事实关系"
        return "候选分析"
    if stage == "stage8":
        return "候选分析"
    return "事实判断"


def validity_for_stage(stage: str, row: dict[str, str]) -> str:
    if row.get("requires_internal_validation") == "true":
        return "需要内部验证"
    if stage == "stage8":
        return "候选分析"
    if stage == "stage7" and row.get("relationship_status") != "confirmed_public_relationship":
        return "需要内部验证"
    return "当前支持"


def risk_note_for_stage(stage: str, row: dict[str, str]) -> str:
    if row.get("requires_internal_validation") == "true":
        return "公开资料不足以证明内部客户或当前交易关系，需要内部销售/客户数据确认。"
    if stage == "stage8":
        return "商机、解决方案和战役计划为候选分析，不代表已发生订单或客户事实。"
    return ""


EXPLICIT_EVENT_DATES = {
    "R4-MANUAL-001": ("2016-04-29", "2016-04-29", "", "day", "公告日期"),
    "R4-MANUAL-002": ("2014-02-20", "2014-02-20", "", "day", "公告日期"),
    "R4-MANUAL-003": ("2015-06-23", "2015-06-23", "", "day", "公告日期"),
    "R4-MANUAL-004": ("2015-06-23", "2015-06-23", "", "day", "公告日期"),
    "R4-MANUAL-005": ("2020-06-22", "2020-06-22", "", "day", "公告日期"),
    "R4-MANUAL-006": ("2020-06-22", "2020-06-22", "", "day", "公告日期"),
    "R4-MANUAL-007": ("2020-06-22", "2020-06-22", "", "day", "公告日期"),
}


def event_time_for_row(stage: str, row: dict[str, str]) -> dict[str, str]:
    if stage != "stage4":
        return {
            "event_date": "",
            "event_start_at": "",
            "event_end_at": "",
            "time_precision": "unknown",
            "temporal_basis": "检索快照",
        }
    relationship_id = row.get("relationship_id", "")
    if relationship_id in EXPLICIT_EVENT_DATES:
        event_date, event_start_at, event_end_at, time_precision, temporal_basis = EXPLICIT_EVENT_DATES[
            relationship_id
        ]
        return {
            "event_date": event_date,
            "event_start_at": event_start_at,
            "event_end_at": event_end_at,
            "time_precision": time_precision,
            "temporal_basis": temporal_basis,
        }
    return {
        "event_date": "",
        "event_start_at": "",
        "event_end_at": "",
        "time_precision": "unknown",
        "temporal_basis": "检索快照",
    }


def enrich_table(stage: str, evidence: dict[str, dict[str, Any]]) -> int:
    path = TABLES[stage]
    rows = read_csv_rows(path)
    enriched_rows: list[dict[str, str]] = []
    for index, row in enumerate(rows, start=1):
        event_time = event_time_for_row(stage, row)
        enriched_rows.append(
            add_temporal_fields(
                row,
                evidence,
                claim_nature=claim_nature_for_stage(stage, row),
                record_id=build_record_id(stage, row, index),
                current_validity=validity_for_stage(stage, row),
                event_date=event_time["event_date"],
                event_start_at=event_time["event_start_at"],
                event_end_at=event_time["event_end_at"],
                time_precision=event_time["time_precision"],
                temporal_basis=event_time["temporal_basis"],
                risk_note=risk_note_for_stage(stage, row),
            )
        )
    write_csv_rows(path, enriched_rows)
    return len(enriched_rows)


def enrich_all_tables() -> dict[str, int]:
    evidence = load_evidence_index(EVIDENCE_PATHS)
    return {stage: enrich_table(stage, evidence) for stage in TABLES}


def main() -> int:
    summary = enrich_all_tables()
    for stage, count in summary.items():
        print(f"{stage}: enriched {count} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m unittest tests.test_temporal_enrichment -v
```

Expected: PASS.

- [ ] **Step 5: Run enrichment on current data**

Run:

```powershell
python -X utf8 scripts\temporal_enrichment.py
```

Expected output includes:

```text
stage3: enriched 204 rows
stage4: enriched 44 rows
stage6: enriched 312 rows
stage7: enriched 5 rows
stage8: enriched 8 rows
```

The exact counts may differ if previous tasks added rows; do not fail only because counts are higher.

- [ ] **Step 6: Add verify_graph temporal checks**

Modify `scripts/verify_graph.py` after loading rows:

```python
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
```

- [ ] **Step 7: Run graph verifier**

Run:

```powershell
python -X utf8 scripts\verify_graph.py
```

Expected: PASS. If existing unrelated checks fail, record them before proceeding.

- [ ] **Step 8: Commit**

```powershell
git add scripts/temporal_enrichment.py scripts/verify_graph.py data/company_pool/company_leaders_stage_3.csv data/company_pool/company_relationships_stage_4.csv data/business_graph/stage6_company_product_relations.csv data/business_graph/stage7_digital_china_relations.csv data/business_graph/stage8_business_opportunities.csv tests/test_temporal_enrichment.py
git commit -m "feat: add temporal governance fields"
```

---

### Task 3: Export Existing Graph as Graphiti Episodes

**Files:**
- Create: `scripts/export_graphiti_episodes.py`
- Create: `tests/test_graphiti_episode_export.py`
- Create: `data/graphiti/.gitkeep`
- Output: `data/graphiti/semiconductor_episodes.jsonl`
- Output: `data/graphiti/semiconductor_episodes_summary.md`

- [ ] **Step 1: Write failing tests for episode export**

Create `tests/test_graphiti_episode_export.py` with:

```python
from __future__ import annotations

import unittest

from scripts.export_graphiti_episodes import (
    build_company_product_episode,
    build_leadership_episode,
    parse_reference_time,
)


class GraphitiEpisodeExportTest(unittest.TestCase):
    def test_parse_reference_time_uses_data_as_of_utc_midnight(self) -> None:
        self.assertEqual(parse_reference_time("2026-07-08"), "2026-07-08T00:00:00Z")

    def test_build_leadership_episode_contains_evidence_and_temporal_context(self) -> None:
        row = {
            "record_id": "stage3::NVIDIA::AI/GPU/CPU算力芯片",
            "company_name": "NVIDIA",
            "subsegment_name": "AI/GPU/CPU算力芯片",
            "leader_level": "全球龙头",
            "selection_basis": "GPU 和 AI 加速计算领域全球代表企业。",
            "confidence": "high",
            "evidence_ids": "E3-001",
            "data_as_of": "2026-07-08",
            "first_seen_at": "2026-07-08",
            "last_verified_at": "2026-07-08",
            "source_publish_dates": "2025-03-01",
            "current_validity": "当前支持",
            "claim_nature": "事实判断",
        }

        episode = build_leadership_episode(row)

        self.assertEqual(episode["episode_id"], "stage3::NVIDIA::AI/GPU/CPU算力芯片")
        self.assertEqual(episode["reference_time"], "2026-07-08T00:00:00Z")
        self.assertEqual(episode["source"], "text")
        self.assertIn("NVIDIA 是 AI/GPU/CPU算力芯片 环节的全球龙头", episode["episode_body"])
        self.assertIn("证据ID：E3-001", episode["episode_body"])
        self.assertIn("当前有效性：当前支持", episode["episode_body"])

    def test_build_company_product_episode_uses_relation_type_cn(self) -> None:
        row = {
            "record_id": "stage6::NVIDIA::PRODUCES::AI GPU",
            "company_name": "NVIDIA",
            "product_service_name": "AI GPU",
            "relation_type": "PRODUCES",
            "l4_name": "AI/GPU/CPU算力芯片",
            "basis": "公开资料显示 NVIDIA 提供 AI GPU。",
            "confidence": "high",
            "evidence_ids": "E3-001",
            "data_as_of": "2026-07-08",
            "first_seen_at": "2026-07-08",
            "last_verified_at": "2026-07-08",
            "source_publish_dates": "2025-03-01",
            "current_validity": "当前支持",
            "claim_nature": "事实判断",
        }

        episode = build_company_product_episode(row)

        self.assertIn("NVIDIA 生产 AI GPU", episode["episode_body"])
        self.assertIn("对应产业链环节：AI/GPU/CPU算力芯片", episode["episode_body"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
python -m unittest tests.test_graphiti_episode_export -v
```

Expected: FAIL because `scripts.export_graphiti_episodes` does not exist.

- [ ] **Step 3: Implement Graphiti episode export**

Create `scripts/export_graphiti_episodes.py` with:

```python
from __future__ import annotations

import json
from pathlib import Path

from temporal_enrichment import read_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT_DIR = DATA / "graphiti"
OUT_JSONL = OUT_DIR / "semiconductor_episodes.jsonl"
OUT_SUMMARY = OUT_DIR / "semiconductor_episodes_summary.md"

LEADERS = DATA / "company_pool" / "company_leaders_stage_3.csv"
RELATIONSHIPS = DATA / "company_pool" / "company_relationships_stage_4.csv"
COMPANY_PRODUCT = DATA / "business_graph" / "stage6_company_product_relations.csv"
DC_RELATIONS = DATA / "business_graph" / "stage7_digital_china_relations.csv"
OPPORTUNITIES = DATA / "business_graph" / "stage8_business_opportunities.csv"

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
    record_id = row.get("record_id") or f"{stage}::{name}"
    return {
        "episode_id": record_id,
        "episode_name": name,
        "episode_body": body,
        "source": "text",
        "source_description": f"半导体产业链图谱 {stage}",
        "reference_time": parse_reference_time(row.get("data_as_of", "")),
        "group_id": GROUP_ID,
        "saga": stage,
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


def build_opportunity_episode(row: dict[str, str]) -> dict[str, str]:
    company = row.get("company_name", "")
    opportunity = row.get("opportunity_name", "")
    body = (
        f"截至 {row.get('data_as_of', '')}，{company} 在 {row.get('product_service_name', '')} 方向存在候选业务机会：{opportunity}。\n"
        f"机会类型：{row.get('opportunity_type', '')}。\n"
        f"机会依据：{row.get('opportunity_basis', '')}\n"
        f"候选解决方案：{row.get('solution_name', '')}。\n"
        f"候选战役计划：{row.get('campaign_name', '')}。\n"
        f"毛利提升逻辑：{row.get('margin_improvement_logic', '')}。\n"
        f"注意：该商机为候选分析，不代表已发生订单或已确认客户事实。\n"
        f"{temporal_block(row)}"
    )
    return base_episode(row, "stage8_opportunity", f"{company}-{opportunity}", body)


def build_episodes() -> list[dict[str, str]]:
    episodes: list[dict[str, str]] = []
    episodes.extend(build_leadership_episode(row) for row in read_csv_rows(LEADERS))
    episodes.extend(build_company_relationship_episode(row) for row in read_csv_rows(RELATIONSHIPS))
    episodes.extend(build_company_product_episode(row) for row in read_csv_rows(COMPANY_PRODUCT))
    episodes.extend(build_digital_china_episode(row) for row in read_csv_rows(DC_RELATIONS))
    episodes.extend(build_opportunity_episode(row) for row in read_csv_rows(OPPORTUNITIES))
    return episodes


def write_outputs(episodes: list[dict[str, str]]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_JSONL.open("w", encoding="utf-8") as handle:
        for episode in episodes:
            handle.write(json.dumps(episode, ensure_ascii=False) + "\n")
    by_saga: dict[str, int] = {}
    for episode in episodes:
        by_saga[episode["saga"]] = by_saga.get(episode["saga"], 0) + 1
    lines = [
        "# Graphiti Episodes 导出摘要",
        "",
        f"- episode 总数：{len(episodes)}",
        f"- group_id：{GROUP_ID}",
        f"- 输出文件：`{OUT_JSONL.as_posix()}`",
        "",
        "## 分组数量",
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
```

- [ ] **Step 4: Add graphiti output directory marker**

Run:

```powershell
New-Item -ItemType Directory -Force data\graphiti | Out-Null
New-Item -ItemType File -Force data\graphiti\.gitkeep | Out-Null
```

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m unittest tests.test_graphiti_episode_export -v
```

Expected: PASS.

- [ ] **Step 6: Export episodes**

Run:

```powershell
python -X utf8 scripts\export_graphiti_episodes.py
```

Expected output:

```text
exported <N> episodes to F:\Java后端资料\实习\神州数码实习\data\graphiti\semiconductor_episodes.jsonl
```

Expected `N` should be roughly `204 + 44 + 312 + 5 + 8 = 573`, unless current data counts changed.

- [ ] **Step 7: Commit**

```powershell
git add scripts/export_graphiti_episodes.py tests/test_graphiti_episode_export.py data/graphiti/.gitkeep data/graphiti/semiconductor_episodes.jsonl data/graphiti/semiconductor_episodes_summary.md
git commit -m "feat: export semiconductor graph as graphiti episodes"
```

---

### Task 4: Verify Graphiti Episode Export Offline

**Files:**
- Create: `scripts/verify_graphiti_export.py`
- Test: `tests/test_graphiti_episode_export.py`

- [ ] **Step 1: Add failing validator test**

Append to `tests/test_graphiti_episode_export.py`:

```python
    def test_validate_episode_rejects_missing_reference_time(self) -> None:
        from scripts.verify_graphiti_export import validate_episode

        errors = validate_episode(
            {
                "episode_id": "e1",
                "episode_name": "n",
                "episode_body": "body",
                "source": "text",
                "source_description": "desc",
                "reference_time": "",
                "group_id": "semiconductor_dc_kg",
            },
            1,
        )

        self.assertIn("line 1 missing reference_time", errors)
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m unittest tests.test_graphiti_episode_export.GraphitiEpisodeExportTest.test_validate_episode_rejects_missing_reference_time -v
```

Expected: FAIL because validator does not exist.

- [ ] **Step 3: Implement export verifier**

Create `scripts/verify_graphiti_export.py` with:

```python
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EPISODES = ROOT / "data" / "graphiti" / "semiconductor_episodes.jsonl"

REQUIRED_FIELDS = [
    "episode_id",
    "episode_name",
    "episode_body",
    "source",
    "source_description",
    "reference_time",
    "group_id",
]


def validate_episode(episode: dict[str, str], line_no: int) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        if not str(episode.get(field, "")).strip():
            errors.append(f"line {line_no} missing {field}")
    if episode.get("source") not in {"text", "json", "message"}:
        errors.append(f"line {line_no} invalid source {episode.get('source')}")
    reference_time = str(episode.get("reference_time", ""))
    if reference_time and not reference_time.endswith("Z"):
        errors.append(f"line {line_no} reference_time must use Z UTC suffix")
    body = str(episode.get("episode_body", ""))
    for required_text in ["数据截至时间", "最近核验时间", "事件开始时间", "事件结束时间", "当前有效性", "证据ID"]:
        if required_text not in body:
            errors.append(f"line {line_no} body missing {required_text}")
    return errors


def load_episodes(path: Path) -> list[dict[str, str]]:
    episodes: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            item["_line_no"] = str(line_no)
            episodes.append(item)
    return episodes


def main() -> int:
    if not EPISODES.exists():
        print(f"FAIL missing {EPISODES}")
        return 1
    episodes = load_episodes(EPISODES)
    errors: list[str] = []
    seen_ids: set[str] = set()
    for index, episode in enumerate(episodes, start=1):
        episode_id = episode.get("episode_id", "")
        if episode_id in seen_ids:
            errors.append(f"line {index} duplicate episode_id {episode_id}")
        seen_ids.add(episode_id)
        errors.extend(validate_episode(episode, index))
    if len(episodes) < 500:
        errors.append(f"episode count too low: {len(episodes)}")
    if errors:
        for error in errors:
            print(f"FAIL {error}")
        return 1
    print(f"PASS graphiti episode export valid: {len(episodes)} episodes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run validator tests**

Run:

```powershell
python -m unittest tests.test_graphiti_episode_export -v
```

Expected: PASS.

- [ ] **Step 5: Run offline export verifier**

Run:

```powershell
python -X utf8 scripts\verify_graphiti_export.py
```

Expected:

```text
PASS graphiti episode export valid: <N> episodes
```

- [ ] **Step 6: Commit**

```powershell
git add scripts/verify_graphiti_export.py tests/test_graphiti_episode_export.py
git commit -m "test: verify graphiti episode export"
```

---

### Task 5: Import Episodes Into Graphiti

**Files:**
- Create: `scripts/import_graphiti_episodes.py`
- Output in Neo4j: Graphiti-created nodes and edges under group/database `semiconductor_dc_kg`

- [ ] **Step 1: Add import script**

Create `scripts/import_graphiti_episodes.py` with:

```python
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPHITI_ROOT = ROOT / "graphiti-main" / "graphiti-main"
sys.path.insert(0, str(GRAPHITI_ROOT))

from graphiti_core import Graphiti  # type: ignore
from graphiti_core.nodes import EpisodeType  # type: ignore

DEFAULT_EPISODES = ROOT / "data" / "graphiti" / "semiconductor_episodes.jsonl"


def parse_reference_time(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def episode_type(value: str) -> EpisodeType:
    if value == "json":
        return EpisodeType.json
    if value == "message":
        return EpisodeType.message
    return EpisodeType.text


def load_episodes(path: Path, limit: int | None = None) -> list[dict[str, str]]:
    episodes: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            episodes.append(json.loads(line))
            if limit and len(episodes) >= limit:
                break
    return episodes


async def import_episodes(args: argparse.Namespace) -> int:
    episodes = load_episodes(args.episodes, args.limit)
    graphiti = Graphiti(args.neo4j_uri, args.neo4j_user, args.neo4j_password)
    previous_by_saga: dict[str, str] = {}
    try:
        for index, episode in enumerate(episodes, start=1):
            saga = episode.get("saga") or "semiconductor_graph"
            result = await graphiti.add_episode(
                name=episode["episode_name"],
                episode_body=episode["episode_body"],
                source=episode_type(episode.get("source", "text")),
                source_description=episode.get("source_description", "半导体图谱导入"),
                reference_time=parse_reference_time(episode["reference_time"]),
                group_id=episode.get("group_id") or args.group_id,
                uuid=episode["episode_id"],
                saga=saga,
                saga_previous_episode_uuid=previous_by_saga.get(saga),
                custom_extraction_instructions=(
                    "抽取事实时必须保留中文公司名、产业链环节、产品服务、证据ID、"
                    "当前有效性、判断性质。不要把候选商机表述为已确认事实。"
                ),
            )
            previous_by_saga[saga] = result.episode.uuid
            if index % 25 == 0:
                print(f"imported {index}/{len(episodes)} episodes")
        print(f"imported {len(episodes)} episodes into Graphiti group {args.group_id}")
        return 0
    finally:
        await graphiti.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=Path, default=DEFAULT_EPISODES)
    parser.add_argument("--neo4j-uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--neo4j-user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--neo4j-password", default=os.getenv("NEO4J_PASSWORD", "password"))
    parser.add_argument("--group-id", default="semiconductor_dc_kg")
    parser.add_argument("--limit", type=int, default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return asyncio.run(import_episodes(args))


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Smoke import 3 episodes**

Run with the task1 environment:

```powershell
F:\panda\miniconda\conda\envs\task1\python.exe -X utf8 scripts\import_graphiti_episodes.py --neo4j-uri bolt://localhost:7687 --neo4j-user neo4j --neo4j-password password --limit 3
```

Expected:

```text
imported 3 episodes into Graphiti group semiconductor_dc_kg
```

If import fails due to missing OpenAI/API environment variables, set them from the existing key file or `.env`, then rerun. Do not paste secrets into chat.

- [ ] **Step 3: Verify Graphiti nodes in Neo4j Browser**

Run in Neo4j Browser:

```cypher
MATCH (e:Episodic)
WHERE e.group_id = 'semiconductor_dc_kg'
RETURN e.name, e.source_description, e.valid_at, e.created_at
ORDER BY e.created_at DESC
LIMIT 20;
```

Expected: at least 3 `Episodic` nodes.

- [ ] **Step 4: Verify extracted facts**

Run in Neo4j Browser:

```cypher
MATCH (a)-[r:RELATES_TO]->(b)
WHERE r.group_id = 'semiconductor_dc_kg'
RETURN a.name, type(r), r.fact, r.valid_at, r.invalid_at, b.name
LIMIT 50;
```

Expected: facts mention semiconductor companies, product services, segments, or Digital China relation status.

- [ ] **Step 5: Full import**

Run:

```powershell
F:\panda\miniconda\conda\envs\task1\python.exe -X utf8 scripts\import_graphiti_episodes.py --neo4j-uri bolt://localhost:7687 --neo4j-user neo4j --neo4j-password password
```

Expected: progress logs every 25 episodes and final success. This can take a long time and will call the configured LLM.

- [ ] **Step 6: Commit import script**

```powershell
git add scripts/import_graphiti_episodes.py
git commit -m "feat: import semiconductor episodes into graphiti"
```

---

### Task 6: Add Graphiti Query Smoke Checks

**Files:**
- Create: `scripts/verify_graphiti_import.py`

- [ ] **Step 1: Create Neo4j smoke verifier**

Create `scripts/verify_graphiti_import.py` with:

```python
from __future__ import annotations

import argparse
import os
from pathlib import Path

from neo4j import GraphDatabase


def scalar(driver, query: str, **params) -> int:
    with driver.session() as session:
        record = session.run(query, **params).single()
        return int(record["count"]) if record else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--neo4j-uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--neo4j-user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--neo4j-password", default=os.getenv("NEO4J_PASSWORD", "password"))
    parser.add_argument("--group-id", default="semiconductor_dc_kg")
    args = parser.parse_args()

    driver = GraphDatabase.driver(args.neo4j_uri, auth=(args.neo4j_user, args.neo4j_password))
    try:
        episode_count = scalar(
            driver,
            "MATCH (e:Episodic {group_id:$group_id}) RETURN count(e) AS count",
            group_id=args.group_id,
        )
        fact_count = scalar(
            driver,
            "MATCH ()-[r:RELATES_TO {group_id:$group_id}]->() RETURN count(r) AS count",
            group_id=args.group_id,
        )
    finally:
        driver.close()

    errors: list[str] = []
    if episode_count < 500:
        errors.append(f"Graphiti episode count too low: {episode_count}")
    if fact_count == 0:
        errors.append("Graphiti extracted fact count is 0")
    if errors:
        for error in errors:
            print(f"FAIL {error}")
        return 1
    print(f"PASS Graphiti import verified: episodes={episode_count}, facts={fact_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run smoke verifier**

Run:

```powershell
F:\panda\miniconda\conda\envs\task1\python.exe -X utf8 scripts\verify_graphiti_import.py --neo4j-uri bolt://localhost:7687 --neo4j-user neo4j --neo4j-password password
```

Expected:

```text
PASS Graphiti import verified: episodes=<N>, facts=<M>
```

- [ ] **Step 3: Commit**

```powershell
git add scripts/verify_graphiti_import.py
git commit -m "test: verify graphiti import"
```

---

### Task 7: Document Demo Queries and Migration Boundaries

**Files:**
- Create: `data/graphiti/graphiti_migration_notes.md`

- [ ] **Step 1: Write migration notes**

Create `data/graphiti/graphiti_migration_notes.md` with:

```markdown
# Graphiti 迁移说明

## 当前方案

现有半导体产业链图谱仍保留在 Neo4j 自定义结构中，用于 Neo4j Browser 可视化。
Graphiti 侧通过 `data/graphiti/semiconductor_episodes.jsonl` 导入同一批事实、证据和业务分析，形成 Graphiti 自己的 temporal graph，用于问答检索。

## 为什么不是直接复用原 Neo4j 节点

Graphiti 的核心对象是 `Episodic` episode、`Entity` 节点和 `RELATES_TO` 事实边。
它需要通过 `add_episode` 执行实体抽取、关系抽取、去重、事实失效和时间字段生成。
如果直接把原图谱节点复制进去，Graphiti 的问答、去重和 temporal 逻辑不会完整生效。

## 时间字段映射

- `data_as_of` -> Graphiti `reference_time`
- Graphiti 自动生成写入时间 `created_at`
- Graphiti 根据 episode 文本和 `reference_time` 抽取事实边的 `valid_at`
- 明确终止关系时，Graphiti 会尝试抽取 `invalid_at`
- `first_seen_at`、`last_verified_at`、`source_publish_dates` 写入 episode 文本，供问答解释和事实抽取参考
- `event_start_at` 只有公告、签约、合作发布、财报披露等明确日期时才填；没有明确证据时保持为空
- `event_end_at` 只有终止、到期、停止合作、关系失效等明确资料时才填；没有明确证据时保持为空
- `event_date` 用于一次性事件日期；它不能替代长期关系的开始/结束时间
- `time_precision` 记录时间精度：`day`、`month`、`year`、`unknown`
- `temporal_basis` 记录时间依据：`公告日期`、`证据发布日期`、`检索快照`、`未明确`

## 事件开始/结束时间原则

不能用检索时间冒充事件开始时间，也不能用证据发布日期冒充合作开始时间。
如果公开资料只证明“某时间点报道过/检索到”，但没有说明关系从何时开始或何时结束，则 `event_start_at` 和 `event_end_at` 留空。
这种情况下通过 `data_as_of`、`last_verified_at`、`current_validity` 和 `temporal_basis` 说明它是当前公开资料快照，而不是精确历史事件边界。

## 事实边界

- 龙头判断：事实判断，但仍受证据等级和数据截至时间约束。
- 企业供应/合作关系：公开资料支持的事实关系。
- 公司-产品关系：公开资料支持或业务归纳关系，`requires_internal_validation=true` 的关系不能说成内部客户事实。
- 神州数码关系：只有 `confirmed_public_relationship` 能称为公开确认关系。
- 商机/解决方案：候选分析，不代表订单、客户关系或已发生项目。

## Neo4j Browser 验证命令

```cypher
MATCH (e:Episodic)
WHERE e.group_id = 'semiconductor_dc_kg'
RETURN e.name, e.source_description, e.valid_at, e.created_at
ORDER BY e.created_at DESC
LIMIT 20;
```

```cypher
MATCH (a)-[r:RELATES_TO]->(b)
WHERE r.group_id = 'semiconductor_dc_kg'
RETURN a.name, r.fact, r.valid_at, r.invalid_at, b.name
LIMIT 50;
```
```

- [ ] **Step 2: Commit**

```powershell
git add data/graphiti/graphiti_migration_notes.md
git commit -m "docs: document graphiti migration"
```

---

## Full Verification

After all tasks, run:

```powershell
python -m unittest discover -s tests -v
python -X utf8 scripts\temporal_enrichment.py
python -X utf8 scripts\verify_graph.py
python -X utf8 scripts\export_graphiti_episodes.py
python -X utf8 scripts\verify_graphiti_export.py
F:\panda\miniconda\conda\envs\task1\python.exe -X utf8 scripts\import_graphiti_episodes.py --neo4j-uri bolt://localhost:7687 --neo4j-user neo4j --neo4j-password password --limit 3
F:\panda\miniconda\conda\envs\task1\python.exe -X utf8 scripts\verify_graphiti_import.py --neo4j-uri bolt://localhost:7687 --neo4j-user neo4j --neo4j-password password
```

For final full import, run without `--limit 3` only after the smoke import works and LLM/API configuration is confirmed:

```powershell
F:\panda\miniconda\conda\envs\task1\python.exe -X utf8 scripts\import_graphiti_episodes.py --neo4j-uri bolt://localhost:7687 --neo4j-user neo4j --neo4j-password password
```

## Self-Review

- Spec coverage: The plan covers time field补齐, event start/end temporal boundaries, Graphiti episode export, offline validation, Graphiti import, Neo4j smoke verification, and documentation.
- Placeholder scan: No placeholder-only task remains; each code step includes concrete file content or exact code blocks.
- Type consistency: Episode fields are consistent across exporter, verifier, and importer: `episode_id`, `episode_name`, `episode_body`, `source`, `source_description`, `reference_time`, `group_id`, `saga`.
- Scope control: This plan does not build a new frontend, does not replace the existing Neo4j visual graph, and does not require full re-search of public evidence.
