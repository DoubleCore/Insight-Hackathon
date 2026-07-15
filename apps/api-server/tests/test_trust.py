from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest


def _write_evidence(path: Path, evidence_id: str, grade: str) -> None:
    path.write_text(
        json.dumps(
            {
                "evidence_id": evidence_id,
                "source_title": f"Source {evidence_id}",
                "source_url_or_file": f"https://example.com/{evidence_id}",
                "evidence_excerpt": "public evidence",
                "source_grade": grade,
                "publish_date": "2026-01-01",
                "retrieved_at": "2026-07-01",
                "limitations": "excerpt",
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _candidate(candidate_id: str, **overrides: object):
    from app.schemas import RetrievalCandidate

    values: dict[str, object] = {
        "id": candidate_id,
        "uuid": candidate_id,
        "title": "fact",
        "content": "A supplies B",
        "score": 1.0,
        "algorithm": "vector",
        "object_type": "edge",
        "selected": True,
        "evidence_ids": ["E-A"],
        "confidence": "high",
        "current_validity": "current",
        "last_verified_at": "2026-07-01",
        "claim_nature": "confirmed_public",
        "verification_status": "confirmed_public",
    }
    values.update(overrides)
    return RetrievalCandidate(**values)


def test_gate_rejects_background_only_and_no_public_evidence(tmp_path: Path) -> None:
    from app.services.evidence import EvidenceIndex
    from app.services.trust import EvidenceGate

    _write_evidence(tmp_path / "evidence_stage_1.jsonl", "E-A", "A")
    gate = EvidenceGate(EvidenceIndex(tmp_path))
    background = _candidate("entity-1", object_type="entity")
    no_public = _candidate(
        "edge-1",
        evidence_ids=[],
        claim_nature="no_public_evidence",
        verification_status="no_public_evidence",
    )

    background_result = gate.evaluate([background])
    no_public_result = gate.evaluate([no_public])

    assert background_result.supported is False
    assert "公开证据" in background_result.reason
    assert no_public_result.supported is False
    assert "无公开证据" in no_public_result.reason
    assert no_public_result.citations == []


def test_gate_allows_b_minus_but_marks_evidence_limited(tmp_path: Path) -> None:
    from app.services.evidence import EvidenceIndex
    from app.services.trust import EvidenceGate

    _write_evidence(tmp_path / "evidence_stage_1.jsonl", "E-B", "B-")
    gate = EvidenceGate(EvidenceIndex(tmp_path))

    result = gate.evaluate([_candidate("edge-1", evidence_ids=["E-B"])])

    assert result.supported is True
    assert result.evidence_limited is True
    assert "证据有限" in result.reason
    assert [citation.evidence_id for citation in result.citations] == ["E-B"]


def test_low_relevance_fact_does_not_pollute_citations_or_trust(tmp_path: Path) -> None:
    from app.services.evidence import EvidenceIndex
    from app.services.trust import EvidenceGate, TrustBuilder

    evidence_path = tmp_path / "evidence_stage_1.jsonl"
    evidence_path.write_text(
        "\n".join(
            [
                json.dumps({"evidence_id": "E-CORE", "source_title": "Core", "source_grade": "A"}),
                json.dumps({"evidence_id": "E-NOISE", "source_title": "Noise", "source_grade": "B-"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    evidence_index = EvidenceIndex(tmp_path)
    core = _candidate("core", evidence_ids=["E-CORE"], rerank_score=0.98)
    noise = _candidate(
        "noise",
        evidence_ids=["E-NOISE"],
        rerank_score=0.50,
        confidence=None,
        claim_nature="potential_fit",
        requires_internal_validation=True,
    )

    gate = EvidenceGate(evidence_index).evaluate([core, noise])
    profile = TrustBuilder(evidence_index).build([core, noise])

    assert [citation.evidence_id for citation in gate.citations] == ["E-CORE"]
    assert gate.evidence_limited is False
    assert profile.evidence.level == "high"
    assert profile.confidence.level == "high"
    assert profile.verification.level == "high"


def test_high_relevance_fact_without_evidence_blocks_low_relevance_support(
    tmp_path: Path,
) -> None:
    from app.services.evidence import EvidenceIndex
    from app.services.trust import EvidenceGate

    _write_evidence(tmp_path / "evidence_stage_1.jsonl", "E-NOISE", "A")
    primary = _candidate(
        "primary-without-evidence", evidence_ids=[], rerank_score=0.99
    )
    noise = _candidate("low-relevance-support", evidence_ids=["E-NOISE"], rerank_score=0.01)

    result = EvidenceGate(EvidenceIndex(tmp_path)).evaluate([primary, noise])

    assert result.supported is False
    assert result.citations == []


def test_trust_builder_returns_four_explicit_dimensions_without_total_score(
    tmp_path: Path,
) -> None:
    from app.services.evidence import EvidenceIndex
    from app.services.trust import TrustBuilder

    evidence_path = tmp_path / "evidence_stage_1.jsonl"
    evidence_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "evidence_id": "E-A",
                        "source_title": "Official filing",
                        "source_grade": "A",
                    }
                ),
                json.dumps(
                    {
                        "evidence_id": "E-B",
                        "source_title": "Industry report",
                        "source_grade": "B",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    builder = TrustBuilder(
        EvidenceIndex(tmp_path),
        now_provider=lambda: datetime(2026, 7, 15, tzinfo=UTC),
    )
    candidates = [
        _candidate("edge-a", evidence_ids=["E-A"]),
        _candidate(
            "episode-b",
            object_type="episode",
            evidence_ids=["E-B"],
            confidence="medium-low",
            claim_nature="fact",
            verification_status="fact",
            last_verified_at="2026-06-01",
        ),
    ]

    profile = builder.build(candidates)
    payload = profile.model_dump()

    assert set(payload) == {
        "evidence",
        "confidence",
        "freshness",
        "verification",
    }
    assert "overall_confidence" not in payload
    assert "summary_label" not in payload
    assert profile.evidence.key == "evidence"
    assert profile.evidence.level == "medium"
    assert profile.confidence.level == "medium-low"
    assert profile.freshness.level == "high"
    assert profile.verification.level == "medium"


def test_evidence_dimension_uses_weakest_core_candidate_best_grade(
    tmp_path: Path,
) -> None:
    from app.services.evidence import EvidenceIndex
    from app.services.trust import TrustBuilder

    evidence_path = tmp_path / "evidence_stage_1.jsonl"
    evidence_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "evidence_id": "E-A",
                        "source_title": "Official filing",
                        "source_grade": "A",
                    }
                ),
                json.dumps(
                    {
                        "evidence_id": "E-B-MINUS",
                        "source_title": "Search excerpt",
                        "source_grade": "B-",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    builder = TrustBuilder(EvidenceIndex(tmp_path))

    mixed_profile = builder.build(
        [
            _candidate("strong-fact", evidence_ids=["E-A"]),
            _candidate("weak-fact", evidence_ids=["E-B-MINUS"]),
        ]
    )
    single_fact_profile = builder.build(
        [
            _candidate(
                "multi-source-fact",
                evidence_ids=["E-A", "E-B-MINUS"],
            )
        ]
    )

    assert mixed_profile.evidence.level == "low"
    assert "证据有限" in mixed_profile.evidence.explanation
    assert mixed_profile.evidence.details["candidate_best_grades"] == {
        "strong-fact": "A",
        "weak-fact": "B-",
    }
    assert single_fact_profile.evidence.level == "high"
    assert single_fact_profile.evidence.details["candidate_best_grades"] == {
        "multi-source-fact": "A"
    }


def test_potential_fit_and_refresh_deadline_are_not_upgraded(tmp_path: Path) -> None:
    from app.services.evidence import EvidenceIndex
    from app.services.trust import TrustBuilder

    _write_evidence(tmp_path / "evidence_stage_1.jsonl", "E-A", "A")
    builder = TrustBuilder(
        EvidenceIndex(tmp_path),
        now_provider=lambda: datetime(2026, 7, 15, tzinfo=UTC),
    )
    candidate = _candidate(
        "potential",
        claim_nature="potential_fit",
        verification_status="confirmed_public",
        requires_internal_validation=True,
        needs_refresh_after="2026-06-30",
    )

    assert candidate.needs_refresh_after == "2026-06-30"

    profile = builder.build([candidate])

    assert profile.verification.level == "low"
    assert "potential_fit" in profile.verification.details["risks"]
    assert "needs_internal_validation" in profile.verification.details["risks"]
    assert "风险" in profile.verification.explanation
    assert profile.freshness.level == "low"
    assert "刷新" in profile.freshness.explanation


@pytest.mark.parametrize("missing_date", [None, " ", "not-a-date"])
def test_freshness_is_unknown_when_any_core_fact_has_no_valid_date(
    tmp_path: Path,
    missing_date: str | None,
) -> None:
    from app.services.evidence import EvidenceIndex
    from app.services.trust import TrustBuilder

    _write_evidence(tmp_path / "evidence_stage_1.jsonl", "E-A", "A")
    builder = TrustBuilder(
        EvidenceIndex(tmp_path),
        now_provider=lambda: datetime(2026, 7, 15, tzinfo=UTC),
    )
    candidates = [
        _candidate("fresh", last_verified_at="2026-07-01"),
        _candidate(
            "unmarked-time",
            last_verified_at=missing_date,
            data_as_of=None,
        ),
    ]

    profile = builder.build(candidates)

    assert profile.freshness.level == "unknown"
    assert "未标注时间" in profile.freshness.explanation
    assert profile.freshness.details["unmarked_time_candidate_ids"] == [
        "unmarked-time"
    ]
