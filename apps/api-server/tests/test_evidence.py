from __future__ import annotations

import json
from pathlib import Path


def _write_jsonl(path: Path, rows: list[dict[str, object] | str]) -> None:
    lines = [row if isinstance(row, str) else json.dumps(row) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _evidence(evidence_id: str, grade: str, title: str) -> dict[str, object]:
    return {
        "evidence_id": evidence_id,
        "source_title": title,
        "source_url_or_file": f"https://example.com/{evidence_id}",
        "evidence_excerpt": f"excerpt-{evidence_id}",
        "source_grade": grade,
        "publish_date": "2026-01-01",
        "retrieved_at": "2026-07-01",
        "limitations": "search excerpt only",
    }


def test_evidence_index_skips_bad_lines_stage8_and_keeps_stronger_duplicate(
    tmp_path: Path,
) -> None:
    from app.services.evidence import EvidenceIndex

    _write_jsonl(
        tmp_path / "evidence_stage_1.jsonl",
        [_evidence("E-1", "B-", "weak first"), "{bad-json"],
    )
    _write_jsonl(
        tmp_path / "evidence_stage_2.jsonl",
        [
            _evidence("E-1", "A-", "stronger replacement"),
            _evidence("E-2", "B", "first equal grade"),
            _evidence("E-2", "B", "second equal grade"),
        ],
    )
    _write_jsonl(
        tmp_path / "evidence_stage_8.jsonl",
        [_evidence("E-8", "A", "must not load")],
    )

    index = EvidenceIndex(tmp_path)

    assert index.error_count == 1
    assert index.duplicate_count == 2
    assert index.get("E-1")["source_title"] == "stronger replacement"
    assert index.get("E-2")["source_title"] == "first equal grade"
    assert index.get("E-8") is None


def test_evidence_index_resolves_candidate_ids_to_citations(tmp_path: Path) -> None:
    from app.schemas import RetrievalCandidate
    from app.services.evidence import EvidenceIndex

    _write_jsonl(
        tmp_path / "evidence_stage_1.jsonl",
        [_evidence("E-1", "A", "Official filing")],
    )
    index = EvidenceIndex(tmp_path)
    candidate = RetrievalCandidate(
        id="edge-1",
        title="relationship",
        content="A supplies B",
        score=1.0,
        algorithm="vector",
        object_type="edge",
        evidence_ids=["E-1", "missing", "E-1"],
    )

    citations = index.citations_for_candidate(candidate)

    assert len(citations) == 1
    assert citations[0].model_dump() == {
        "evidence_id": "E-1",
        "title": "Official filing",
        "url": "https://example.com/E-1",
        "excerpt": "excerpt-E-1",
        "grade": "A",
        "publish_date": "2026-01-01",
        "retrieved_at": "2026-07-01",
        "limitations": "search excerpt only",
    }
