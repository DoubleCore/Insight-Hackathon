import type {
  BackgroundJob,
  CommunityOverview,
  DecisionSignalImportResult,
  GraphPayload,
  GraphStats,
  GraphView,
  GroupSummary,
  IndustrySearchResult,
  PendingEpisodeResult,
  QueryRunSummary,
  QueryTrace,
  SagaOverview,
  UnifiedGraphExpandRequest,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8001";
export const ADMIN_UNAUTHORIZED_EVENT = "admin:unauthorized";
export const GROUP_STORAGE_KEY = "graph_group_id";

interface AdminAuthWindow {
  __adminAuthGeneration?: number;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const generation = (window as AdminAuthWindow).__adminAuthGeneration ?? 0;
  const headers = init?.body instanceof FormData
    ? init?.headers
    : { "Content-Type": "application/json", ...init?.headers };
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    if (response.status === 401 && body.detail === "管理员未登录") {
      window.dispatchEvent(new CustomEvent(ADMIN_UNAUTHORIZED_EVENT, { detail: { generation } }));
    }
    const error = new Error(body.detail ?? `请求失败（${response.status}）`);
    Object.assign(error, { status: response.status });
    throw error;
  }
  return response.json() as Promise<T>;
}

export const adminMe = () => request<{ authenticated: boolean }>("/api/v1/admin/me");
export const adminLogin = (password: string) => request<{ authenticated: boolean }>(
  "/api/v1/admin/login",
  { method: "POST", body: JSON.stringify({ password }) },
);
export const adminLogout = () => request<{ authenticated: boolean }>(
  "/api/v1/admin/logout",
  { method: "POST" },
);
export function selectedGroupId(): string | null {
  return window.localStorage.getItem(GROUP_STORAGE_KEY);
}

export function setSelectedGroupId(groupId: string): void {
  window.localStorage.setItem(GROUP_STORAGE_KEY, groupId);
}

export function listGroups(): Promise<GroupSummary[]> {
  return request("/api/v1/groups");
}

export function industrySearch(payload: {
  industry_name: string;
  group_id: string;
  target_mode: "new_group" | "existing_group";
  new_group_id?: string | null;
  search_depth: "quick" | "standard" | "deep";
  relation_types: string[];
  include_digital_china: boolean;
  manual_review_required: boolean;
  providers: Array<"tavily" | "bocha">;
}): Promise<IndustrySearchResult> {
  return request("/api/v1/industry-search", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createPendingIndustryEpisode(payload: {
  group_id: string;
  industry_name: string;
  query: string;
  draft_episode_body: string;
  relation_types: string[];
  search_depth: string;
  include_digital_china: boolean;
  manual_review_required: boolean;
  hits: IndustrySearchResult["hits"];
}): Promise<PendingEpisodeResult> {
  return request("/api/v1/industry-search/pending-episode", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function importDecisionSignal(formData: FormData): Promise<DecisionSignalImportResult> {
  return request("/api/v1/admin/decision-signals", {
    method: "POST",
    body: formData,
  });
}

const groupQuery = (groupId: string) => `?group_id=${encodeURIComponent(groupId)}`;
const appendGroupQuery = (path: string, groupId: string) =>
  `${path}${path.includes("?") ? "&" : "?"}group_id=${encodeURIComponent(groupId)}`;

export const getGraphStats = (groupId: string) => request<GraphStats>(`/api/v1/admin/graph/stats${groupQuery(groupId)}`);
export const getGraphView = (view: GraphView, limit: number, groupId: string) => request<GraphPayload>(
  `/api/v1/admin/graph/views/${view}?limit=${limit}&group_id=${encodeURIComponent(groupId)}`,
);
export const getUnifiedGraphRoot = (groupId: string) => request<GraphPayload>(`/api/v1/admin/graph/unified/root${groupQuery(groupId)}`);
export const expandUnifiedGraph = (payload: UnifiedGraphExpandRequest, groupId: string) => request<GraphPayload>(
  `/api/v1/admin/graph/unified/expand${groupQuery(groupId)}`,
  { method: "POST", body: JSON.stringify(payload) },
);
export const getTraces = () => request<QueryRunSummary[]>("/api/v1/admin/traces");
export const getTrace = (runId: string) => request<QueryTrace>(`/api/v1/admin/traces/${runId}`);
export const getSagas = (groupId: string) => request<SagaOverview[]>(`/api/v1/admin/governance/sagas${groupQuery(groupId)}`);
export const getCommunities = (groupId: string) => request<CommunityOverview[]>(`/api/v1/admin/governance/communities${groupQuery(groupId)}`);
export const getJobs = () => request<BackgroundJob[]>("/api/v1/admin/jobs");
export const getJob = (jobId: string) => request<BackgroundJob>(`/api/v1/admin/jobs/${jobId}`);
export const summarizeSaga = (sagaId: string, groupId: string) => request<BackgroundJob>(
  appendGroupQuery(`/api/v1/admin/governance/sagas/${sagaId}/summarize`, groupId),
  { method: "POST" },
);
export const rebuildCommunities = (groupId: string) => request<BackgroundJob>(
  `/api/v1/admin/governance/communities/rebuild${groupQuery(groupId)}`,
  { method: "POST" },
);
