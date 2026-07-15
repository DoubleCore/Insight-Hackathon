import type { Conversation, GroupSummary, IndustrySearchResult, Message, QuestionResult, SubmittedQuestion } from "./types";

export const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8001";
export const GROUP_STORAGE_KEY = "graph_group_id";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `请求失败（${response.status}）`);
  }
  return response.json() as Promise<T>;
}

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

export function listConversations(): Promise<Conversation[]> {
  return request("/api/v1/user/conversations");
}

export function createConversation(title?: string): Promise<Conversation> {
  return request("/api/v1/user/conversations", {
    method: "POST",
    body: JSON.stringify({ title: title || null }),
  });
}

export function listMessages(conversationId: string): Promise<Message[]> {
  return request(`/api/v1/user/conversations/${conversationId}/messages`);
}

export function submitQuestion(
  conversationId: string,
  content: string,
  groupId: string,
): Promise<SubmittedQuestion> {
  return request(`/api/v1/user/conversations/${conversationId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content, group_id: groupId }),
  });
}

export function getQuestionResult(requestId: string): Promise<QuestionResult> {
  return request(`/api/v1/user/requests/${requestId}`);
}

export function requestEventSource(requestId: string): EventSource {
  return new EventSource(`${API_BASE}/api/v1/user/requests/${requestId}/events`, {
    withCredentials: true,
  });
}
