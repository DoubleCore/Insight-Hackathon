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

    def test_add_temporal_fields_prefers_explicit_time_over_snapshot_placeholder(self) -> None:
        row = {
            "relationship_id": "R4-001",
            "evidence_ids": "E1",
            "time_precision": "unknown",
            "temporal_basis": "检索快照",
            "source_publish_dates": "2020-01-01",
        }
        evidence = {
            "E1": {
                "publish_date": "2024-02-26T09:00:00+08:00",
                "retrieved_at": "2026-07-08T18:30:00+08:00",
                "source_grade": "A",
            },
        }

        enriched = add_temporal_fields(
            row,
            evidence,
            claim_nature="事实判断",
            event_start_at="2024-02-26",
            time_precision="day",
            temporal_basis="官方公告日期",
        )

        self.assertEqual(enriched["event_start_at"], "2024-02-26")
        self.assertEqual(enriched["time_precision"], "day")
        self.assertEqual(enriched["temporal_basis"], "官方公告日期")
        self.assertEqual(enriched["source_publish_dates"], "2024-02-26")

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

    def test_event_time_for_row_only_sets_explicit_stage4_events(self) -> None:
        from scripts.temporal_enrichment import event_time_for_row

        explicit = event_time_for_row("stage4", {"relationship_id": "R4-MANUAL-001"})
        self.assertEqual(explicit["event_start_at"], "2016-04-29")
        self.assertEqual(explicit["event_end_at"], "")
        self.assertEqual(explicit["time_precision"], "day")
        self.assertEqual(explicit["temporal_basis"], "公告日期")

        current_id = event_time_for_row("stage4", {"relationship_id": "R4-M005"})
        self.assertEqual(current_id["event_start_at"], "2021-06-28")
        self.assertEqual(current_id["event_end_at"], "")
        self.assertEqual(current_id["time_precision"], "day")
        self.assertEqual(current_id["temporal_basis"], "官方公告日期")

        hbm = event_time_for_row("stage4", {"relationship_id": "R4-031"})
        self.assertEqual(hbm["event_start_at"], "2024-02-26")
        self.assertEqual(hbm["event_end_at"], "")
        self.assertEqual(hbm["temporal_basis"], "官方公告日期")

        unknown = event_time_for_row("stage3", {"relationship_id": "R4-MANUAL-001"})
        self.assertEqual(unknown["event_start_at"], "")
        self.assertEqual(unknown["event_end_at"], "")
        self.assertEqual(unknown["temporal_basis"], "检索快照")


if __name__ == "__main__":
    unittest.main()
