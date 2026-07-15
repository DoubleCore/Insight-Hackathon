from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas import Citation, RetrievalCandidate, TrustDimension, TrustProfile
from app.services.evidence import EvidenceIndex, GRADE_STRENGTH


FACT_OBJECT_TYPES = {"edge", "episode"}
NO_PUBLIC_EVIDENCE = {"no_public_evidence", "no-public-evidence"}
RISKY_CLAIMS = {
    "potential_fit",
    "needs_internal_validation",
    "inferred",
    "inference",
    "estimated",
    "estimate",
    "speculative",
}
LEVEL_STRENGTH = {
    "low": 1,
    "medium-low": 2,
    "medium": 3,
    "medium-high": 4,
    "high": 5,
}
RELEVANCE_SUPPORT_RATIO = 0.65


class EvidenceGateResult(BaseModel):
    supported: bool
    reason: str
    evidence_limited: bool = False
    citations: list[Citation] = Field(default_factory=list)
    supporting_candidate_ids: list[str] = Field(default_factory=list)


class EvidenceGate:
    def __init__(self, evidence_index: EvidenceIndex) -> None:
        self.evidence_index = evidence_index

    def evaluate(
        self, candidates: Iterable[RetrievalCandidate]
    ) -> EvidenceGateResult:
        selected_facts = [
            candidate for candidate in candidates if _is_selected_fact_object(candidate)
        ]
        if selected_facts and all(
            _is_no_public_evidence(candidate) for candidate in selected_facts
        ):
            return EvidenceGateResult(
                supported=False,
                reason="候选事实均标记为无公开证据，无法据此作答。",
            )
        factual = _relevance_filtered(
            [candidate for candidate in selected_facts if candidate.evidence_ids],
            reference_candidates=selected_facts,
        )

        supporting: list[RetrievalCandidate] = []
        citations: list[Citation] = []
        seen: set[str] = set()
        for candidate in factual:
            if _is_no_public_evidence(candidate):
                continue
            resolved = self.evidence_index.citations_for_candidate(candidate)
            if not resolved:
                continue
            supporting.append(candidate)
            for citation in resolved:
                if citation.evidence_id not in seen:
                    seen.add(citation.evidence_id)
                    citations.append(citation)

        if not supporting:
            return EvidenceGateResult(
                supported=False,
                reason="未检索到可由公开证据支撑的事实，无法作答。",
            )

        evidence_limited = any(citation.grade.upper() == "B-" for citation in citations)
        reason = (
            "存在可引用的公开证据，但包含 B- 级材料，证据有限。"
            if evidence_limited
            else "已通过公开证据门控。"
        )
        return EvidenceGateResult(
            supported=True,
            reason=reason,
            evidence_limited=evidence_limited,
            citations=citations,
            supporting_candidate_ids=[candidate.id for candidate in supporting],
        )


class TrustBuilder:
    def __init__(
        self,
        evidence_index: EvidenceIndex,
        *,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.evidence_index = evidence_index
        self.now_provider = now_provider or (lambda: datetime.now(UTC))

    def build(self, candidates: Iterable[RetrievalCandidate]) -> TrustProfile:
        candidate_list = list(candidates)
        selected_facts = [
            candidate
            for candidate in candidate_list
            if _is_selected_fact_object(candidate)
            and not _is_no_public_evidence(candidate)
        ]
        supporting = _relevance_filtered(
            [
                candidate
                for candidate in selected_facts
                if _is_selected_fact(candidate)
                and self.evidence_index.citations_for_candidate(candidate)
            ],
            reference_candidates=selected_facts,
        )
        dimensions = {
            "evidence": self._evidence_dimension(supporting),
            "confidence": self._confidence_dimension(supporting),
            "freshness": self._freshness_dimension(supporting),
            "verification": self._verification_dimension(supporting),
        }
        return TrustProfile(**dimensions)

    def _evidence_dimension(
        self, candidates: list[RetrievalCandidate]
    ) -> TrustDimension:
        candidate_best_grades: dict[str, str] = {}
        citation_count = 0
        for candidate in candidates:
            citations = self.evidence_index.citations_for_candidate(candidate)
            citation_count += len(citations)
            grades = [citation.grade.upper() for citation in citations]
            candidate_best_grades[candidate.id] = max(
                grades,
                key=lambda grade: GRADE_STRENGTH.get(grade, 0),
                default="",
            )

        weakest = min(
            candidate_best_grades.values(),
            key=lambda grade: GRADE_STRENGTH.get(grade, 0),
            default="",
        )
        level = {
            "A": "high",
            "A-": "medium-high",
            "B": "medium",
            "B-": "low",
        }.get(weakest, "low")
        if not candidate_best_grades:
            explanation = "没有可解析的核心事实公开证据。"
        elif weakest == "B-":
            explanation = "每条核心事实取其最强公开来源后，最低等级为 B-，证据有限。"
        else:
            explanation = f"每条核心事实取其最强公开来源后，最低等级为 {weakest}。"
        return TrustDimension(
            key="evidence",
            label="证据质量",
            level=level,
            explanation=explanation,
            details={
                "candidate_count": len(candidate_best_grades),
                "citation_count": citation_count,
                "candidate_best_grades": candidate_best_grades,
                "weakest_grade": weakest,
            },
        )

    @staticmethod
    def _confidence_dimension(
        candidates: list[RetrievalCandidate],
    ) -> TrustDimension:
        levels = [
            _normalize_confidence(candidate.confidence)
            for candidate in candidates
        ]
        if any(_candidate_risks(candidate) for candidate in candidates):
            levels.append("medium-low")
        level = min(
            levels or ["low"], key=lambda item: LEVEL_STRENGTH.get(item, 0)
        )
        return TrustDimension(
            key="confidence",
            label="事实置信度",
            level=level,
            explanation=f"采用 {len(candidates)} 条核心事实中最保守的业务置信等级。",
            details={"candidate_levels": levels},
        )

    def _freshness_dimension(
        self, candidates: list[RetrievalCandidate]
    ) -> TrustDimension:
        now = _as_aware(self.now_provider())
        verified_dates: list[datetime] = []
        unmarked_time_candidate_ids: list[str] = []
        for candidate in candidates:
            last_verified_at = candidate.last_verified_at
            raw_date = (
                last_verified_at
                if last_verified_at and last_verified_at.strip()
                else candidate.data_as_of
            )
            parsed = _parse_datetime(raw_date)
            if parsed is None or parsed > now:
                unmarked_time_candidate_ids.append(candidate.id)
            else:
                verified_dates.append(parsed)

        stale_validity = [
            candidate.current_validity
            for candidate in candidates
            if _normalized(candidate.current_validity)
            in {"expired", "invalid", "stale", "outdated", "historical"}
        ]
        refresh_deadlines = [
            parsed
            for candidate in candidates
            if (parsed := _parse_datetime(candidate.needs_refresh_after)) is not None
        ]
        overdue = [deadline for deadline in refresh_deadlines if deadline < now]
        if not candidates or unmarked_time_candidate_ids:
            level = "unknown"
            explanation = "存在未标注时间或时间无效的核心事实，无法判断整体时效性。"
        elif stale_validity:
            level = "low"
            explanation = "核心事实包含已失效或过期状态，需要重新核验。"
        elif overdue:
            level = "low"
            explanation = "核心事实已超过刷新期限，需要刷新后再使用。"
        else:
            oldest_days = max((now - value).days for value in verified_dates)
            if oldest_days <= 180:
                level = "high"
            elif oldest_days <= 365:
                level = "medium"
            else:
                level = "low"
            explanation = f"核心事实最久已 {oldest_days} 天未核验。"
        return TrustDimension(
            key="freshness",
            label="时效性",
            level=level,
            explanation=explanation,
            details={
                "stale_validity": stale_validity,
                "overdue_refresh_count": len(overdue),
                "unmarked_time_candidate_ids": unmarked_time_candidate_ids,
            },
        )

    @staticmethod
    def _verification_dimension(
        candidates: list[RetrievalCandidate],
    ) -> TrustDimension:
        risks = _unique(
            risk for candidate in candidates for risk in _candidate_risks(candidate)
        )
        statuses = [
            _normalized(candidate.verification_status or candidate.claim_nature)
            for candidate in candidates
        ]
        if risks:
            level = "low"
            explanation = "核心事实包含推定或内部核验风险，不得升级为已确认关系。"
        elif statuses and all(status.startswith("confirmed_public") for status in statuses):
            level = "high"
            explanation = "核心事实均有公开资料确认。"
        elif statuses and all(
            status.startswith("confirmed_public") or status == "fact"
            for status in statuses
        ):
            level = "medium"
            explanation = "核心事实为公开确认或一般事实，仍需结合原始材料核验。"
        else:
            level = "medium-low" if candidates else "low"
            explanation = "核心事实的核验状态不完整。"
        return TrustDimension(
            key="verification",
            label="核验状态",
            level=level,
            explanation=explanation,
            details={"statuses": statuses, "risks": risks},
        )


def _is_selected_fact(candidate: RetrievalCandidate) -> bool:
    return _is_selected_fact_object(candidate) and bool(candidate.evidence_ids)


def _is_selected_fact_object(candidate: RetrievalCandidate) -> bool:
    return candidate.selected and candidate.object_type.casefold() in FACT_OBJECT_TYPES


def _is_no_public_evidence(candidate: RetrievalCandidate) -> bool:
    return _normalized(candidate.claim_nature) in NO_PUBLIC_EVIDENCE or _normalized(
        candidate.verification_status
    ) in NO_PUBLIC_EVIDENCE


def _candidate_risks(candidate: RetrievalCandidate) -> list[str]:
    risks: list[str] = []
    claim_nature = _normalized(candidate.claim_nature)
    verification = _normalized(candidate.verification_status)
    if claim_nature in RISKY_CLAIMS:
        risks.append(claim_nature)
    if verification in RISKY_CLAIMS:
        risks.append(verification)
    if candidate.requires_internal_validation:
        risks.append("needs_internal_validation")
    return _unique(risks)


def _relevance_filtered(
    candidates: list[RetrievalCandidate],
    *,
    reference_candidates: list[RetrievalCandidate] | None = None,
) -> list[RetrievalCandidate]:
    reference = reference_candidates if reference_candidates is not None else candidates
    scores = [candidate.rerank_score for candidate in reference]
    if not scores or any(score is None for score in scores):
        return candidates
    best = max(float(score) for score in scores if score is not None)
    if best <= 0:
        return candidates
    floor = best * RELEVANCE_SUPPORT_RATIO
    return [
        candidate
        for candidate in candidates
        if candidate.rerank_score is not None and candidate.rerank_score >= floor
    ]


def _normalize_confidence(value: str | None) -> str:
    normalized = _normalized(value)
    aliases = {
        "medium_low": "medium-low",
        "medium low": "medium-low",
        "medium_high": "medium-high",
        "medium high": "medium-high",
    }
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in LEVEL_STRENGTH else "low"


def _normalized(value: Any) -> str:
    return str(value or "").strip().casefold()


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_aware(parsed)


def _as_aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _unique(values: Iterable[Any]) -> list[Any]:
    seen: set[Any] = set()
    result: list[Any] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
