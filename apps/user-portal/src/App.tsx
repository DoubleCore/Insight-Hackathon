import { FormEvent, useEffect, useRef, useState } from "react";
import {
  ArrowUp,
  BookOpenText,
  ChevronRight,
  ExternalLink,
  Menu,
  MessageSquareText,
  Plus,
  ShieldCheck,
  X,
} from "lucide-react";

import {
  createConversation,
  getQuestionResult,
  listGroups,
  listConversations,
  listMessages,
  requestEventSource,
  selectedGroupId,
  setSelectedGroupId,
  submitQuestion,
} from "./api";
import type {
  Citation,
  Conversation,
  GroupSummary,
  Message,
  MessageMetadata,
  TrustDimension,
  TrustProfile,
} from "./types";
import "./styles.css";

const SUGGESTIONS = [
  "AI/GPU 算力芯片有哪些龙头企业？",
  "NVIDIA 与 TSMC 存在什么产业关系？",
  "哪些公司生产或集成 AI 服务器？",
];

const TRUST_ORDER: Array<keyof TrustProfile> = [
  "evidence",
  "confidence",
  "freshness",
  "verification",
];

function levelLabel(level: string): string {
  return {
    high: "高",
    "medium-high": "较高",
    medium: "中",
    "medium-low": "较低",
    low: "低",
    unknown: "未知",
  }[level] ?? level;
}

function TrustItem({ dimension }: { dimension: TrustDimension }) {
  return (
    <div className={`trust-item trust-${dimension.level}`}>
      <div className="trust-item-head">
        <span>{dimension.label}</span>
        <strong>{levelLabel(dimension.level)}</strong>
      </div>
      <p>{dimension.explanation}</p>
    </div>
  );
}

function CitationItem({ citation, index }: { citation: Citation; index: number }) {
  const content = (
    <>
      <span className="citation-index">{String(index + 1).padStart(2, "0")}</span>
      <span className="citation-main">
        <strong>{citation.title}</strong>
        <span>
          <b>{citation.grade}</b>
          {citation.publish_date ? ` · 发布 ${citation.publish_date}` : ""}
          {citation.evidence_id ? ` · ${citation.evidence_id}` : ""}
        </span>
      </span>
      {citation.url ? <ExternalLink aria-hidden="true" size={15} /> : null}
    </>
  );
  return citation.url ? (
    <a className="citation-item" href={citation.url} target="_blank" rel="noreferrer">
      {content}
    </a>
  ) : (
    <div className="citation-item">{content}</div>
  );
}

function AssistantMessage({ message }: { message: Message }) {
  const citations = message.metadata?.citations ?? [];
  const trust = message.metadata?.trust_profile;
  return (
    <article className="message assistant-message">
      <div className="assistant-mark" aria-hidden="true">
        <BookOpenText size={17} />
      </div>
      <div className="message-body">
        <div className="message-copy">{message.content}</div>
        {trust ? (
          <section className="answer-evidence" aria-label="回答可信度">
            <div className="evidence-section-title">
              <ShieldCheck size={16} />
              <span>可信度</span>
            </div>
            <div className="trust-grid">
              {TRUST_ORDER.map((key) => (
                <TrustItem key={key} dimension={trust[key]} />
              ))}
            </div>
            {citations.length ? (
              <div className="citations">
                <div className="evidence-section-title">
                  <BookOpenText size={16} />
                  <span>引用资料</span>
                  <small>{citations.length}</small>
                </div>
                <div className="citation-list">
                  {citations.map((citation, index) => (
                    <CitationItem key={citation.evidence_id} citation={citation} index={index} />
                  ))}
                </div>
              </div>
            ) : null}
          </section>
        ) : null}
      </div>
    </article>
  );
}

function UserMessage({ message }: { message: Message }) {
  return (
    <article className="message user-message">
      <div className="message-body">
        <div className="message-copy">{message.content}</div>
      </div>
    </article>
  );
}

function App() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [stage, setStage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [groups, setGroups] = useState<GroupSummary[]>([]);
  const [groupId, setGroupId] = useState(selectedGroupId() ?? "semiconductor_dc_kg");
  const messageEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      listGroups().catch(() => [{ id: selectedGroupId() ?? "semiconductor_dc_kg", label: selectedGroupId() ?? "semiconductor_dc_kg", is_default: true }]),
      listConversations(),
    ])
      .then(async (items) => {
        if (cancelled) return;
        const [nextGroups, conversations] = items;
        const safeGroups = Array.isArray(nextGroups) ? nextGroups : [];
        setGroups(safeGroups);
        const stored = selectedGroupId();
        const nextGroupId = stored && safeGroups.some((group) => group.id === stored)
          ? stored
          : safeGroups[0]?.id ?? "semiconductor_dc_kg";
        setGroupId(nextGroupId);
        setSelectedGroupId(nextGroupId);
        setConversations(conversations);
        if (conversations.length) {
          setActiveId(conversations[0].id);
          setMessages(await listMessages(conversations[0].id));
        }
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (typeof messageEndRef.current?.scrollIntoView === "function") {
      messageEndRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [messages, stage]);

  async function selectConversation(conversationId: string) {
    if (conversationId === activeId) {
      setSidebarOpen(false);
      return;
    }
    setActiveId(conversationId);
    setSidebarOpen(false);
    setLoading(true);
    setError(null);
    try {
      setMessages(await listMessages(conversationId));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "会话加载失败");
    } finally {
      setLoading(false);
    }
  }

  function startNewConversation() {
    setActiveId(null);
    setMessages([]);
    setInput("");
    setError(null);
    setSidebarOpen(false);
  }

  async function ensureConversation(question: string): Promise<string> {
    if (activeId) return activeId;
    const created = await createConversation(question.slice(0, 24));
    setConversations((current) => [created, ...current]);
    setActiveId(created.id);
    return created.id;
  }

  async function sendQuestion(question: string) {
    const content = question.trim();
    if (!content || sending) return;
    setSending(true);
    setError(null);
    setInput("");
    try {
      const conversationId = await ensureConversation(content);
      const optimisticUser: Message = {
        id: `local-user-${Date.now()}`,
        role: "user",
        content,
        metadata: {},
        created_at: new Date().toISOString(),
      };
      setMessages((current) => [...current, optimisticUser]);
      setStage("正在检索公开资料");
      const submitted = await submitQuestion(conversationId, content, groupId);
      const temporaryId = `stream-${submitted.request_id}`;
      const source = requestEventSource(submitted.request_id);

      source.addEventListener("stage", (rawEvent) => {
        const payload = JSON.parse((rawEvent as MessageEvent).data) as { name?: string };
        setStage(payload.name ? `正在${payload.name}` : "正在处理");
      });
      source.addEventListener("token", (rawEvent) => {
        const payload = JSON.parse((rawEvent as MessageEvent).data) as { text: string };
        setMessages((current) => {
          const existing = current.find((item) => item.id === temporaryId);
          if (!existing) {
            return [...current, {
              id: temporaryId,
              role: "assistant",
              content: payload.text,
              metadata: {},
              created_at: new Date().toISOString(),
            }];
          }
          return current.map((item) => item.id === temporaryId
            ? { ...item, content: item.content + payload.text }
            : item);
        });
      });
      source.addEventListener("completed", async () => {
        source.close();
        try {
          const result = await getQuestionResult(submitted.request_id);
          const metadata: MessageMetadata = {
            request_id: submitted.request_id,
            citations: result.citations ?? [],
            trust_profile: result.trust_profile,
            degraded: result.degraded,
            degradation_reason: result.degradation_reason,
          };
          setMessages((current) => {
            const completed: Message = {
              id: result.message_id ?? temporaryId,
              role: "assistant",
              content: result.answer ?? "",
              metadata,
              created_at: new Date().toISOString(),
            };
            return current.some((item) => item.id === temporaryId)
              ? current.map((item) => item.id === temporaryId ? completed : item)
              : [...current, completed];
          });
          setConversations(await listConversations());
        } catch (reason) {
          setError(reason instanceof Error ? reason.message : "回答读取失败");
        } finally {
          setStage(null);
          setSending(false);
        }
      });
      source.addEventListener("error", () => {
        source.close();
        setStage(null);
        setSending(false);
        setError("本次问答未完成，请重新发送");
      });
    } catch (reason) {
      setStage(null);
      setSending(false);
      setError(reason instanceof Error ? reason.message : "问题发送失败");
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void sendQuestion(input);
  }

  return (
    <div className="app-shell">
      {sidebarOpen ? <button className="sidebar-scrim" aria-label="关闭会话列表" onClick={() => setSidebarOpen(false)} /> : null}
      <aside className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}>
        <div className="brand-block">
          <div className="brand-mark" aria-hidden="true"><MessageSquareText size={19} /></div>
          <div>
            <strong>半导体产业</strong>
            <span>知识助手</span>
          </div>
          <button className="icon-button sidebar-close" aria-label="关闭会话列表" onClick={() => setSidebarOpen(false)}>
            <X size={18} />
          </button>
        </div>
        <button className="new-chat-button" onClick={startNewConversation}>
          <Plus size={17} />
          <span>新建问答</span>
        </button>
        <div className="conversation-label">最近会话</div>
        <nav className="conversation-list" aria-label="会话列表">
          {conversations.map((conversation) => (
            <button
              key={conversation.id}
              className={`conversation-item ${conversation.id === activeId ? "active" : ""}`}
              onClick={() => void selectConversation(conversation.id)}
            >
              <MessageSquareText size={15} />
              <span>{conversation.title || "未命名会话"}</span>
              {conversation.id === activeId ? <ChevronRight size={14} /> : null}
            </button>
          ))}
        </nav>
        <div className="user-scope">
          <select
            aria-label="当前图谱 group"
            value={groupId}
            onChange={(event) => {
              setGroupId(event.target.value);
              setSelectedGroupId(event.target.value);
            }}
          >
            {(groups.length ? groups : [{ id: groupId, label: groupId, is_default: true }]).map((group) => (
              <option key={group.id} value={group.id}>{group.label ?? group.id}</option>
            ))}
          </select>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <button className="icon-button mobile-menu" aria-label="打开会话列表" onClick={() => setSidebarOpen(true)}>
            <Menu size={19} />
          </button>
          <div>
            <h1>半导体产业知识助手</h1>
            <p>{activeId ? conversations.find((item) => item.id === activeId)?.title : "新问答"}</p>
          </div>
        </header>

        <div className="chat-scroll">
          <div className="chat-column">
            {!loading && messages.length === 0 ? (
              <section className="empty-state">
                <div className="empty-symbol" aria-hidden="true"><BookOpenText size={27} /></div>
                <h2>从一个产业问题开始</h2>
                <div className="suggestion-list">
                  {SUGGESTIONS.map((suggestion) => (
                    <button key={suggestion} onClick={() => void sendQuestion(suggestion)}>
                      <span>{suggestion}</span><ArrowUp size={15} />
                    </button>
                  ))}
                </div>
              </section>
            ) : null}
            {loading ? <div className="loading-line"><span /><span /><span /></div> : null}
            {messages.map((message) => message.role === "assistant"
              ? <AssistantMessage key={message.id} message={message} />
              : <UserMessage key={message.id} message={message} />)}
            {stage ? (
              <div className="stage-line" role="status">
                <span className="stage-pulse" />
                <span>{stage}</span>
              </div>
            ) : null}
            {error ? <div className="error-banner" role="alert">{error}</div> : null}
            <div ref={messageEndRef} />
          </div>
        </div>

        <footer className="composer-wrap">
          <form className="composer" onSubmit={handleSubmit}>
            <label className="sr-only" htmlFor="question-input">输入问题</label>
            <textarea
              id="question-input"
              aria-label="输入问题"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void sendQuestion(input);
                }
              }}
              placeholder="询问产业环节、龙头企业或企业关系"
              rows={2}
              disabled={sending}
            />
            <button className="send-button" type="submit" aria-label="发送问题" disabled={!input.trim() || sending}>
              <ArrowUp size={19} />
            </button>
          </form>
        </footer>
      </main>
    </div>
  );
}

export default App;
