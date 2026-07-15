export type GraphView = "business" | "temporal" | "governance";
export type GraphBranch = "hierarchy" | "business" | "facts" | "timeline" | "saga" | "community" | "evidence" | "digital_china";

export interface GraphNode {
  id: string;
  labels: string[];
  properties: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  properties: Record<string, unknown>;
}

export interface GraphPayload {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface GroupSummary {
  id: string;
  label?: string | null;
  is_default: boolean;
}

export interface IndustrySearchHit {
  provider: string;
  title: string;
  url: string;
  content: string;
  published_at?: string | null;
  score?: number | null;
}

export interface IndustrySearchResult {
  group_id: string;
  industry_name: string;
  query: string;
  target_mode: string;
  search_depth: string;
  relation_types: string[];
  include_digital_china: boolean;
  manual_review_required: boolean;
  ingestion_status: string;
  hits: IndustrySearchHit[];
  draft_episode_body: string;
}

export type DecisionSignalCategory = "policy" | "technology" | "industry_rule" | "business_implication";
export type DecisionSignalSourceType = "link" | "document" | "text";

export interface DecisionSignalImportResult {
  group_id: string;
  saga: string;
  evidence_id: string;
  episode_uuid: string;
  title: string;
  category: DecisionSignalCategory;
  source_type: DecisionSignalSourceType;
  source_url?: string | null;
  content_preview: string;
  fallback_reason?: string | null;
}

export interface PendingEpisodeResult {
  status: "pending_ingest";
  episode: Record<string, unknown>;
}

export interface UnifiedGraphExpandRequest {
  node_id: string;
  branch: GraphBranch;
  cursor?: string | null;
  limit?: number;
}

export interface GraphStats {
  industry_nodes?: number;
  industry_edges?: number;
  entities?: number;
  episodes?: number;
  facts?: number;
  sagas?: number;
  communities?: number;
}

export interface QueryRunSummary {
  id: string;
  conversation_id: string;
  query: string;
  status: string;
  answer?: string | null;
  error?: string | null;
  trace_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface QueryStage {
  name: string;
  status: string;
  algorithm?: string | null;
  detail?: Record<string, unknown>;
  duration_ms?: number | null;
}

export interface RetrievalCandidate {
  id: string;
  title: string;
  content: string;
  score: number;
  algorithm: string;
  metadata?: Record<string, unknown>;
  rank?: number | null;
  selected?: boolean;
  evidence_ids?: string[];
  object_type?: string;
  source?: string | null;
  target?: string | null;
  relation?: string | null;
  evidence_level?: string | null;
  confidence?: string | null;
  valid_from?: string | null;
  valid_to?: string | null;
  verification_status?: string | null;
  data_as_of?: string | null;
  last_verified_at?: string | null;
  needs_refresh_after?: string | null;
  current_validity?: string | null;
  requires_internal_validation?: boolean;
  claim_nature?: string | null;
  rerank_score?: number | null;
  rerank_fallback_reason?: string | null;
}

export interface RetrievalSlice {
  id: string;
  name: string;
  algorithm: string;
  query: string;
  status: string;
  error?: string | null;
  duration_ms?: number | null;
  started_at?: string | null;
  completed_at?: string | null;
  candidates: RetrievalCandidate[];
  metadata?: Record<string, unknown>;
}

export interface LlmCall {
  id: string;
  query_run_id: string;
  model: string;
  purpose: string;
  status: string;
  request_tokens?: number | null;
  response_tokens?: number | null;
  latency_ms?: number | null;
  request?: Record<string, unknown>;
  response?: Record<string, unknown>;
  error?: string | null;
}

export interface QueryTrace extends QueryRunSummary {
  stages: QueryStage[];
  retrieval_slices: RetrievalSlice[];
  llm_calls: LlmCall[];
}

export interface SagaOverview {
  uuid: string;
  name: string;
  summary: string;
  legacy_saga_key?: string | null;
  saga_key?: string | null;
  layer_id?: number | null;
  layer_name?: string | null;
  fact_set_name?: string | null;
  fact_set_type?: string | null;
  fact_set_description?: string | null;
  display_name?: string | null;
  episode_count: number;
  last_summarized_at?: string | null;
  last_summarized_episode_valid_at?: string | null;
}

export interface CommunityOverview {
  uuid: string;
  name: string;
  summary: string;
  member_count: number;
  representative_entities: string[];
  created_at?: string | null;
}

export interface BackgroundJob {
  id: string;
  job_type: "summarize_saga" | "rebuild_communities";
  status: "queued" | "running" | "completed" | "failed" | "interrupted";
  payload: Record<string, unknown>;
  result?: Record<string, unknown> | null;
  error?: string | null;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}
