from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from app.config import PROJECT_ROOT
from app.schemas import Citation, RetrievalCandidate


GRADE_STRENGTH = {"B-": 1, "B": 2, "A-": 3, "A": 4}
STAGE_8_PATTERN = re.compile(r"stage[_-]?8", re.IGNORECASE)


class EvidenceIndex:
    """加载并按 evidence_id 索引项目证据 JSONL。"""

    def __init__(self, evidence_dir: Path | str | None = None) -> None:
        self.evidence_dir = Path(evidence_dir or PROJECT_ROOT / "data" / "evidence")
        self.records: dict[str, dict[str, Any]] = {}
        self.error_count = 0
        self.duplicate_count = 0
        self.load()

    def load(self) -> None:
        self.records.clear()
        self.error_count = 0
        self.duplicate_count = 0
        if not self.evidence_dir.exists():
            return

        for path in sorted(self.evidence_dir.glob("*.jsonl")):
            if STAGE_8_PATTERN.search(path.stem):
                continue
            self._load_file(path)

    def _load_file(self, path: Path) -> None:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    evidence_id = str(record["evidence_id"]).strip()
                    if not evidence_id:
                        raise ValueError("empty evidence_id")
                except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                    self.error_count += 1
                    continue

                current = self.records.get(evidence_id)
                if current is None:
                    self.records[evidence_id] = record
                    continue

                self.duplicate_count += 1
                current_grade = str(current.get("source_grade", "")).upper()
                incoming_grade = str(record.get("source_grade", "")).upper()
                if GRADE_STRENGTH.get(incoming_grade, 0) > GRADE_STRENGTH.get(
                    current_grade, 0
                ):
                    self.records[evidence_id] = record

    def get(self, evidence_id: str) -> dict[str, Any] | None:
        return self.records.get(evidence_id)

    def resolve(self, evidence_ids: Iterable[str]) -> list[Citation]:
        citations: list[Citation] = []
        seen: set[str] = set()
        for evidence_id in evidence_ids:
            if evidence_id in seen:
                continue
            seen.add(evidence_id)
            record = self.get(evidence_id)
            if record is None:
                continue
            citations.append(self._to_citation(record))
        return citations

    def citations_for_candidate(
        self, candidate: RetrievalCandidate
    ) -> list[Citation]:
        return self.resolve(candidate.evidence_ids)

    @staticmethod
    def _to_citation(record: dict[str, Any]) -> Citation:
        return Citation(
            evidence_id=str(record["evidence_id"]),
            title=str(record.get("source_title") or record["evidence_id"]),
            url=record.get("source_url_or_file"),
            excerpt=record.get("evidence_excerpt"),
            grade=str(record.get("source_grade") or "B-"),
            publish_date=record.get("publish_date"),
            retrieved_at=record.get("retrieved_at"),
            limitations=record.get("limitations"),
        )
