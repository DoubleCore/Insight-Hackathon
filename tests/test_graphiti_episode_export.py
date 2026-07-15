from __future__ import annotations

import unittest

from scripts.export_graphiti_episodes import (
    build_company_competition_episode,
    build_company_product_episode,
    build_episodes,
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
            "event_date": "",
            "event_start_at": "",
            "event_end_at": "",
            "time_precision": "unknown",
            "temporal_basis": "检索快照",
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
        self.assertIn("事件开始时间：", episode["episode_body"])
        self.assertIn("事件结束时间：", episode["episode_body"])

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
            "event_date": "",
            "event_start_at": "",
            "event_end_at": "",
            "time_precision": "unknown",
            "temporal_basis": "检索快照",
            "source_publish_dates": "2025-03-01",
            "current_validity": "当前支持",
            "claim_nature": "事实判断",
        }

        episode = build_company_product_episode(row)

        self.assertIn("NVIDIA 生产 AI GPU", episode["episode_body"])
        self.assertIn("对应产业链环节：AI/GPU/CPU算力芯片", episode["episode_body"])

    def test_build_company_competition_episode_marks_inferred_relation(self) -> None:
        row = {
            "record_id": "stage6_competition::NVIDIA::AMD::推定竞争",
            "source_company": "NVIDIA",
            "target_company": "AMD",
            "relationship_type": "推定竞争",
            "basis": "同环节同产品龙头推定竞争：AI GPU。",
            "derivation": "same_product_leader_presumed",
            "confidence": "medium-low",
            "requires_internal_validation": "true",
            "evidence_ids": "E3-001;E3-002",
            "data_as_of": "2026-07-08",
            "first_seen_at": "2026-07-08",
            "last_verified_at": "2026-07-08",
            "event_date": "",
            "event_start_at": "",
            "event_end_at": "",
            "time_precision": "unknown",
            "temporal_basis": "检索快照",
            "source_publish_dates": "2025-03-01",
            "current_validity": "需要内部验证",
            "claim_nature": "推断关系",
        }

        episode = build_company_competition_episode(row)

        self.assertEqual(episode["saga"], "stage6_company_competition")
        self.assertIn("NVIDIA 与 AMD 存在 推定竞争 候选关系", episode["episode_body"])
        self.assertIn("不代表公开资料已经证明两家公司发生交易、合作或直接竞争事件", episode["episode_body"])

    def test_build_episodes_excludes_stage8_business_opportunities(self) -> None:
        sagas = {episode["saga"] for episode in build_episodes()}

        self.assertNotIn("stage8_opportunity", sagas)

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


if __name__ == "__main__":
    unittest.main()
