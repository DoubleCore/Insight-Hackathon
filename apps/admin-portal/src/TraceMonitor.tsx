import {
  AlertTriangle,
  ArrowRight,
  Bot,
  Check,
  ChevronRight,
  Clock3,
  FileSearch,
  RefreshCw,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { getTrace, getTraces } from "./api";
import type { QueryRunSummary, QueryTrace, RetrievalCandidate, RetrievalSlice } from "./types";

const ALGORITHM_NAMES: Record<string, string> = {
  vector: "向量召回",
  bm25: "BM25 召回",
  bfs: "图遍历",
  lexical: "词面补召回",
  cross_encoder: "Cross Encoder",
  rrf: "RRF 重排",
};

const STATUS_NAMES: Record<string, string> = {
  queued: "排队中",
  running: "运行中",
  completed: "完成",
  failed: "失败",
  interrupted: "已中断",
  degraded: "降级",
  refused: "拒答",
};

function shortTime(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString("zh-CN", { hour12: false });
}

function statusName(status: string): string {
  return STATUS_NAMES[status] ?? status;
}

function hasValue(value: unknown): boolean {
  return value !== null && value !== undefined && value !== "";
}

function formatNumber(value: number): string {
  return value.toLocaleString("zh-CN", { maximumFractionDigits: 3 });
}

function formatDuration(value?: number | null): string {
  return value == null || !Number.isFinite(value) ? "-" : `${formatNumber(Math.round(value))} ms`;
}

function formatValue(value: unknown): string {
  if (!hasValue(value)) return "-";
  if (typeof value === "number") return Number.isFinite(value) ? formatNumber(value) : "-";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (Array.isArray(value)) return value.length ? value.map(formatValue).join(", ") : "-";
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return "-";
    }
  }
  return String(value);
}

function scoreText(value: unknown): string {
  const score = typeof value === "number" ? value : Number(value);
  return Number.isFinite(score) ? score.toFixed(3) : "-";
}

function timeDiffMs(start: string, end: string): number | null {
  const startedAt = new Date(start).getTime();
  const endedAt = new Date(end).getTime();
  if (!Number.isFinite(startedAt) || !Number.isFinite(endedAt) || endedAt < startedAt) return null;
  return endedAt - startedAt;
}

function sliceDurationMs(slice: RetrievalSlice): number | null {
  if (slice.duration_ms != null && Number.isFinite(slice.duration_ms)) return slice.duration_ms;
  if (!slice.started_at || !slice.completed_at) return null;
  return timeDiffMs(slice.started_at, slice.completed_at);
}

function sumDurations(values: Array<number | null | undefined>): number | null {
  const usable = values.filter((value): value is number => value != null && Number.isFinite(value));
  return usable.length ? usable.reduce((total, value) => total + value, 0) : null;
}

function candidateValue(candidate: RetrievalCandidate, key: string): unknown {
  const topLevel = (candidate as unknown as Record<string, unknown>)[key];
  if (hasValue(topLevel)) return topLevel;
  return candidate.metadata?.[key];
}

function candidateText(candidate: RetrievalCandidate, key: string): string {
  return formatValue(candidateValue(candidate, key));
}

function traceFallbackReason(trace: QueryTrace): string {
  if (trace.error) return trace.error;

  const notableStage = trace.stages.find((stage) =>
    ["failed", "degraded", "refused", "interrupted"].includes(stage.status),
  );
  const notableStageReason = notableStage?.detail?.fallback_reason
    ?? notableStage?.detail?.reason
    ?? notableStage?.detail?.error;
  if (hasValue(notableStageReason)) return formatValue(notableStageReason);

  const sliceError = trace.retrieval_slices.find((slice) => hasValue(slice.error))?.error;
  if (hasValue(sliceError)) return formatValue(sliceError);

  const fallbackReason = trace.stages.find((stage) => hasValue(stage.detail?.fallback_reason))
    ?.detail?.fallback_reason
    ?? trace.retrieval_slices.find((slice) => hasValue(slice.metadata?.fallback_reason))
      ?.metadata?.fallback_reason;
  return formatValue(fallbackReason);
}

function TraceList({ runs, activeId, onSelect }: { runs: QueryRunSummary[]; activeId: string | null; onSelect: (id: string) => void }) {
  return (
    <aside className="trace-list">
      <div className="trace-list-head"><span>问答请求</span><b>{runs.length}</b></div>
      <div className="trace-list-scroll">
        {runs.map((run) => (
          <button key={run.id} className={run.id === activeId ? "active" : ""} onClick={() => onSelect(run.id)}>
            <span className={`run-status status-${run.status}`}><i />{statusName(run.status)}</span>
            <strong>{run.query}</strong>
            <small>{shortTime(run.created_at)}</small>
            <ChevronRight size={14} />
          </button>
        ))}
        {!runs.length ? <div className="trace-list-empty">暂无问答请求</div> : null}
      </div>
    </aside>
  );
}

function TraceOverview({ trace }: { trace: QueryTrace }) {
  const candidates = trace.retrieval_slices.flatMap((slice) => slice.candidates);
  const llmDuration = sumDurations(trace.llm_calls.map((call) => call.latency_ms));
  const retrievalDuration = sumDurations(trace.retrieval_slices.map(sliceDurationMs));
  const totalTokens = trace.llm_calls.reduce(
    (total, call) => total + (call.request_tokens ?? 0) + (call.response_tokens ?? 0),
    0,
  );

  return (
    <section className="trace-overview" aria-label="链路总览">
      <div className="trace-metric">
        <span>总耗时</span>
        <b>{formatDuration(timeDiffMs(trace.created_at, trace.updated_at))}</b>
        <small>updated_at - created_at</small>
      </div>
      <div className="trace-metric">
        <span>召回耗时</span>
        <b>{formatDuration(retrievalDuration)}</b>
        <small>retrieval_slices</small>
      </div>
      <div className="trace-metric">
        <span>LLM 耗时</span>
        <b>{formatDuration(llmDuration)}</b>
        <small>llm_calls.latency_ms</small>
      </div>
      <div className="trace-metric">
        <span>总 token</span>
        <b>{formatNumber(totalTokens)}</b>
        <small>request + response</small>
      </div>
      <div className="trace-metric">
        <span>候选数</span>
        <b>{formatNumber(candidates.length)}</b>
        <small>candidate rows</small>
      </div>
      <div className="trace-metric">
        <span>入选数</span>
        <b>{formatNumber(candidates.filter((candidate) => candidate.selected).length)}</b>
        <small>selected candidates</small>
      </div>
      <div className="trace-metric trace-metric-wide">
        <span>失败/降级原因</span>
        <b>{traceFallbackReason(trace)}</b>
        <small>error / fallback_reason</small>
      </div>
    </section>
  );
}

function StageTimeline({ trace }: { trace: QueryTrace }) {
  return (
    <section className="stage-section">
      <div className="trace-section-title"><span>执行阶段</span><small>{trace.stages.length}</small></div>
      <div className="stage-timeline">
        {trace.stages.map((stage, index) => (
          <div className={`stage-node stage-${stage.status}`} key={`${stage.name}-${index}`}>
            <div className="stage-index">{stage.status === "completed" ? <Check size={12} /> : index + 1}</div>
            <div>
              <strong>{stage.name}</strong>
              <span>{stage.algorithm ? ALGORITHM_NAMES[stage.algorithm] ?? stage.algorithm : statusName(stage.status)}</span>
            </div>
            {stage.duration_ms != null ? <small>{Math.round(stage.duration_ms)} ms</small> : null}
            {index < trace.stages.length - 1 ? <ArrowRight className="stage-arrow" size={14} /> : null}
          </div>
        ))}
      </div>
      <div className="stage-detail-list">
        {trace.stages.map((stage, index) => {
          const entries = Object.entries(stage.detail ?? {});
          return (
            <details className="stage-detail" key={`${stage.name}-${index}-detail`}>
              <summary>
                <span>
                  <strong>{stage.name}</strong>
                  <small>{statusName(stage.status)} · {formatDuration(stage.duration_ms)}</small>
                </span>
                <ChevronRight size={14} />
              </summary>
              {entries.length ? (
                <div className="detail-grid">
                  {entries.map(([key, value]) => (
                    <div className="detail-row" key={key}>
                      <span>{key}</span>
                      <b>{formatValue(value)}</b>
                    </div>
                  ))}
                </div>
              ) : <div className="detail-empty">该阶段没有 detail</div>}
            </details>
          );
        })}
      </div>
    </section>
  );
}

function CandidateRow({ candidate }: { candidate: RetrievalCandidate }) {
  const score = candidateValue(candidate, "rerank_score") ?? candidate.score;
  const source = candidateText(candidate, "source");
  const target = candidateText(candidate, "target");
  const endpoints = source === "-" && target === "-" ? "-" : `${source} -> ${target}`;
  return (
    <div className={`candidate-row ${candidate.selected ? "candidate-selected" : ""}`}>
      <span className="candidate-rank">{candidate.rank ?? "-"}</span>
      <div className="candidate-fact">
        <strong>{candidate.title}</strong>
        <p>{candidate.content}</p>
        <div className="candidate-badges">
          <span className="candidate-badge">{candidateText(candidate, "object_type")}</span>
          <span className="candidate-badge">{candidate.selected ? "入选" : "候选"}</span>
          <span className="candidate-badge">confidence {candidateText(candidate, "confidence")}</span>
          <span className="candidate-badge">evidence {candidateText(candidate, "evidence_level")}</span>
        </div>
        <div className="candidate-meta">
          <span><b>source -&gt; target</b>{endpoints}</span>
          <span><b>relation</b>{candidateText(candidate, "relation")}</span>
          <span><b>last_verified_at</b>{candidateText(candidate, "last_verified_at")}</span>
          <span><b>verification_status</b>{candidateText(candidate, "verification_status")}</span>
          <span><b>rerank_score</b>{scoreText(candidateValue(candidate, "rerank_score"))}</span>
        </div>
        <span>
          {candidateText(candidate, "relation") !== "-" ? `${candidateText(candidate, "relation")} · ` : ""}
          {candidate.evidence_ids?.length ? `证据 ${candidate.evidence_ids.join(", ")}` : "无证据 ID"}
        </span>
      </div>
      <div className="candidate-score"><b>{scoreText(score)}</b><span>{candidate.selected ? "入选" : "候选"}</span></div>
    </div>
  );
}

function RetrievalPanel({ trace }: { trace: QueryTrace }) {
  const initial = trace.retrieval_slices.find((slice) => slice.algorithm === "cross_encoder" || slice.algorithm === "rrf") ?? trace.retrieval_slices[0];
  const [activeId, setActiveId] = useState(initial?.id ?? "");
  useEffect(() => setActiveId(initial?.id ?? ""), [initial?.id]);
  const active: RetrievalSlice | undefined = trace.retrieval_slices.find((slice) => slice.id === activeId) ?? initial;
  return (
    <section className="retrieval-section">
      <div className="trace-section-title"><span>召回切面</span><small>{trace.retrieval_slices.length}</small></div>
      <div className="slice-tabs" role="tablist">
        {trace.retrieval_slices.map((slice) => (
          <button key={slice.id} role="tab" aria-selected={slice.id === active?.id} onClick={() => setActiveId(slice.id)}>
            <span>{ALGORITHM_NAMES[slice.algorithm] ?? slice.algorithm}</span>
            <b>{slice.candidates.length}</b>
          </button>
        ))}
      </div>
      {active ? (
        <div className="slice-content">
          <div className="slice-meta">
            <span><FileSearch size={13} />{active.query}</span>
            <span><Clock3 size={13} />{formatDuration(sliceDurationMs(active))}</span>
            <span className={`slice-status status-${active.status}`}>{statusName(active.status)}</span>
          </div>
          <div className="slice-diagnostics">
            <div className="slice-diagnostic">
              <span>status</span>
              <b>{statusName(active.status)}</b>
            </div>
            <div className={`slice-diagnostic ${active.error ? "slice-error" : ""}`}>
              <span>error</span>
              <b>{formatValue(active.error)}</b>
            </div>
            <div className="slice-diagnostic">
              <span>metadata.fallback_reason</span>
              <b>{formatValue(active.metadata?.fallback_reason)}</b>
            </div>
          </div>
          <div className="candidate-table">
            {active.candidates.map((candidate) => <CandidateRow key={candidate.id} candidate={candidate} />)}
            {!active.candidates.length ? <div className="candidate-empty">该切面没有返回候选</div> : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function LlmCalls({ trace }: { trace: QueryTrace }) {
  return (
    <section className="llm-section">
      <div className="trace-section-title"><span>大模型调用</span><small>{trace.llm_calls.length}</small></div>
      <div className="llm-call-list">
        {trace.llm_calls.map((call) => (
          <details key={call.id} className="llm-call">
            <summary>
              <Bot size={16} />
              <span><strong>{call.purpose === "rewrite" ? "问题改写" : "回答生成"}</strong><small>{call.model}</small></span>
              <b className={`status-${call.status}`}>{statusName(call.status)}</b>
              <span className="llm-metrics">{call.latency_ms == null ? "-" : `${Math.round(call.latency_ms)} ms`} · {(call.request_tokens ?? 0) + (call.response_tokens ?? 0)} tokens</span>
            </summary>
            <div className="llm-payloads">
              <div><span>请求</span><pre>{JSON.stringify(call.request ?? {}, null, 2)}</pre></div>
              <div><span>响应</span><pre>{call.error ?? JSON.stringify(call.response ?? {}, null, 2)}</pre></div>
            </div>
          </details>
        ))}
        {!trace.llm_calls.length ? <div className="candidate-empty">本次请求没有大模型调用</div> : null}
      </div>
    </section>
  );
}

function TraceDetail({ trace }: { trace: QueryTrace }) {
  return (
    <div className="trace-detail">
      <header className="trace-detail-head">
        <div>
          <span className={`run-status status-${trace.status}`}><i />{statusName(trace.status)}</span>
          <h2>{trace.query}</h2>
          <div className="trace-ids">
            <small>{shortTime(trace.created_at)}</small>
            <small>run_id {trace.id}</small>
            <small>trace_id {trace.trace_id ?? "-"}</small>
          </div>
        </div>
        {trace.error ? <div className="trace-error"><AlertTriangle size={15} />{trace.error}</div> : null}
      </header>
      <TraceOverview trace={trace} />
      <StageTimeline trace={trace} />
      <RetrievalPanel trace={trace} />
      <LlmCalls trace={trace} />
    </div>
  );
}

export default function TraceMonitor() {
  const [runs, setRuns] = useState<QueryRunSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [trace, setTrace] = useState<QueryTrace | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getTraces()
      .then(async (items) => {
        if (cancelled) return;
        setRuns(items);
        const nextId = activeId && items.some((item) => item.id === activeId) ? activeId : items[0]?.id;
        setActiveId(nextId ?? null);
        const detail = nextId ? await getTrace(nextId) : null;
        if (!cancelled) setTrace(detail);
      })
      .catch((reason: Error) => {
        if (!cancelled) {
          setTrace(null);
          setError(reason.message);
        }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [revision]);

  async function selectRun(runId: string) {
    setActiveId(runId);
    setLoading(true);
    setError(null);
    try { setTrace(await getTrace(runId)); }
    catch (reason) {
      setTrace(null);
      setError(reason instanceof Error ? reason.message : "追踪加载失败");
    }
    finally { setLoading(false); }
  }

  const totals = useMemo(() => ({
    completed: runs.filter((run) => run.status === "completed").length,
    failed: runs.filter((run) => run.status === "failed").length,
  }), [runs]);

  return (
    <section className="workspace trace-workspace">
      <header className="trace-header">
        <div><span className="section-kicker">运行观测</span><h1>链路观测</h1></div>
        <div className="trace-totals"><span><b>{runs.length}</b>请求</span><span><b>{totals.completed}</b>完成</span><span><b>{totals.failed}</b>失败</span></div>
        <button className="refresh-button" aria-label="刷新追踪" onClick={() => setRevision((value) => value + 1)}><RefreshCw size={16} /></button>
      </header>
      <div className="trace-body">
        <TraceList runs={runs} activeId={activeId} onSelect={(id) => void selectRun(id)} />
        <main className="trace-detail-wrap">
          {loading ? <div className="trace-loading"><span /><span /><span /></div> : null}
          {!loading && trace ? <TraceDetail trace={trace} /> : null}
          {!loading && !trace ? <div className="trace-empty"><FileSearch size={24} /><span>{error ?? "暂无可查看的追踪"}</span></div> : null}
        </main>
      </div>
    </section>
  );
}
