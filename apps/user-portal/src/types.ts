export interface Conversation {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface Citation {
  evidence_id: string;
  title: string;
  url?: string | null;
  excerpt?: string | null;
  grade: string;
  publish_date?: string | null;
  retrieved_at?: string | null;
  limitations?: string | null;
}

export interface TrustDimension {
  key: string;
  label: string;
  level: string;
  explanation: string;
  details?: Record<string, unknown>;
}

export interface TrustProfile {
  evidence: TrustDimension;
  confidence: TrustDimension;
  freshness: TrustDimension;
  verification: TrustDimension;
}

export interface MessageMetadata {
  request_id?: string;
  citations?: Citation[];
  trust_profile?: TrustProfile;
  degraded?: boolean;
  degradation_reason?: string | null;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  metadata: MessageMetadata;
  created_at: string;
}

export interface SubmittedQuestion {
  request_id: string;
  conversation_id: string;
  user_message_id: string;
  status: string;
  events_url: string;
}

export interface QuestionResult {
  request_id: string;
  conversation_id: string;
  status: string;
  message_id?: string;
  answer?: string | null;
  error?: string | null;
  citations?: Citation[];
  trust_profile?: TrustProfile;
  degraded?: boolean;
  degradation_reason?: string | null;
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
