from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


JobStatus = Literal["queued", "running", "completed", "failed", "interrupted"]
RunStatus = Literal["queued", "running", "completed", "failed", "interrupted"]


class Citation(BaseModel):
    evidence_id: str
    title: str
    url: str | None = None
    excerpt: str | None = None
    grade: str
    publish_date: str | None = None
    retrieved_at: str | None = None
    limitations: str | None = None


class TrustDimension(BaseModel):
    key: str
    label: str
    level: str
    explanation: str
    details: dict[str, Any] = Field(default_factory=dict)


class TrustProfile(BaseModel):
    evidence: TrustDimension
    confidence: TrustDimension
    freshness: TrustDimension
    verification: TrustDimension


class RetrievalCandidate(BaseModel):
    id: str
    uuid: str | None = None
    slice_id: str | None = None
    title: str
    content: str
    score: float
    algorithm: str
    algorithms: list[str] = Field(default_factory=list)
    object_type: str = "unknown"
    rank: int | None = None
    selected: bool = False
    evidence_ids: list[str] = Field(default_factory=list)
    source: str | None = None
    target: str | None = None
    relation: str | None = None
    evidence_level: str | None = None
    confidence: str | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    data_as_of: str | None = None
    last_verified_at: str | None = None
    needs_refresh_after: str | None = None
    current_validity: str | None = None
    requires_internal_validation: bool = False
    claim_nature: str | None = None
    verification_status: str | None = None
    rerank_score: float | None = None
    rerank_fallback_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, value: Any) -> Any:
        if value is None or isinstance(value, str):
            return value
        if isinstance(value, (int, float)):
            if value >= 0.8:
                return "high"
            if value >= 0.6:
                return "medium"
            if value >= 0.4:
                return "medium-low"
            return "low"
        return value


class RetrievalSlice(BaseModel):
    id: str
    query_run_id: str | None = None
    name: str
    algorithm: str
    query: str
    status: str = "completed"
    error: str | None = None
    duration_ms: float | None = None
    candidates: list[RetrievalCandidate] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class LlmCallTrace(BaseModel):
    id: str
    query_run_id: str
    model: str
    purpose: str
    status: str
    request_tokens: int | None = None
    response_tokens: int | None = None
    latency_ms: float | None = None
    request: dict[str, Any] = Field(default_factory=dict)
    response: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class QueryStage(BaseModel):
    name: str
    status: str
    algorithm: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: float | None = None


class QueryRunSummary(BaseModel):
    id: str
    conversation_id: str
    query: str
    status: RunStatus
    answer: str | None = None
    error: str | None = None
    trace_id: str | None = None
    created_at: datetime
    updated_at: datetime


class QueryTrace(BaseModel):
    id: str
    conversation_id: str
    query: str
    status: RunStatus
    answer: str | None = None
    error: str | None = None
    trace_id: str | None = None
    stages: list[QueryStage]
    retrieval_slices: list[RetrievalSlice]
    llm_calls: list[LlmCallTrace]
    created_at: datetime
    updated_at: datetime


class GraphNode(BaseModel):
    id: str
    labels: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphPayload(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class GroupSummary(BaseModel):
    id: str
    label: str | None = None
    is_default: bool = False


class DecisionSignalImportResult(BaseModel):
    group_id: str
    saga: str
    evidence_id: str
    episode_uuid: str
    title: str
    category: Literal["policy", "technology", "industry_rule", "business_implication"]
    source_type: Literal["link", "document", "text"]
    source_url: str | None = None
    content_preview: str
    fallback_reason: str | None = None


class IndustrySearchRequest(BaseModel):
    industry_name: str = Field(min_length=1, max_length=80)
    group_id: str | None = None
    target_mode: Literal["new_group", "existing_group"] = "existing_group"
    new_group_id: str | None = Field(default=None, max_length=64)
    search_depth: Literal["quick", "standard", "deep"] = "standard"
    relation_types: list[Literal["生产", "采购", "销售", "使用", "合作", "股权", "竞争", "渠道"]] = Field(
        default_factory=lambda: ["生产", "采购", "销售", "使用", "合作", "竞争"]
    )
    providers: list[Literal["tavily", "bocha"]] = Field(
        default_factory=lambda: ["tavily", "bocha"]
    )
    max_results: int = Field(default=8, ge=1, le=20)
    include_digital_china: bool = True
    manual_review_required: bool = True


class IndustrySearchHit(BaseModel):
    provider: str
    title: str
    url: str
    content: str = ""
    published_at: str | None = None
    score: float | None = None


class IndustrySearchResult(BaseModel):
    group_id: str
    industry_name: str
    query: str
    target_mode: str = "existing_group"
    search_depth: str = "standard"
    relation_types: list[str] = Field(default_factory=list)
    include_digital_china: bool = True
    manual_review_required: bool = True
    ingestion_status: str = "draft_only"
    hits: list[IndustrySearchHit]
    draft_episode_body: str


class IndustryPendingEpisodeRequest(BaseModel):
    group_id: str = Field(min_length=1, max_length=80)
    industry_name: str = Field(min_length=1, max_length=80)
    query: str = Field(min_length=1)
    draft_episode_body: str = Field(min_length=1)
    relation_types: list[str] = Field(default_factory=list)
    search_depth: str = "standard"
    include_digital_china: bool = True
    manual_review_required: bool = True
    hits: list[IndustrySearchHit] = Field(default_factory=list)


class IndustryPendingEpisodeResult(BaseModel):
    status: Literal["pending_ingest"] = "pending_ingest"
    episode: dict[str, Any]


class UnifiedGraphExpandRequest(BaseModel):
    node_id: str
    branch: Literal["hierarchy", "business", "facts", "timeline", "saga", "community", "evidence", "digital_china"]
    cursor: str | None = None
    limit: int = Field(default=20, ge=1, le=50)


class AnswerResponse(BaseModel):
    conversation_id: str
    message_id: str
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    trust_profile: TrustProfile
    retrieval_slices: list[RetrievalSlice] = Field(default_factory=list)
    trace_id: str | None = None


class BackgroundJob(BaseModel):
    id: str
    job_type: str
    status: JobStatus
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    worker_id: str | None = None
    heartbeat_at: datetime | None = None
    lease_expires_at: datetime | None = None


class SagaOverview(BaseModel):
    uuid: str
    name: str
    summary: str = ""
    legacy_saga_key: str | None = None
    saga_key: str | None = None
    layer_id: int | None = None
    layer_name: str | None = None
    fact_set_name: str | None = None
    fact_set_type: str | None = None
    fact_set_description: str | None = None
    display_name: str | None = None
    episode_count: int = 0
    last_summarized_at: datetime | None = None
    last_summarized_episode_valid_at: datetime | None = None


class CommunityOverview(BaseModel):
    uuid: str
    name: str
    summary: str = ""
    member_count: int = 0
    representative_entities: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
