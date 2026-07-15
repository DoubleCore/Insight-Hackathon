import {
  AlertCircle,
  Boxes,
  CheckCircle2,
  FileText,
  LoaderCircle,
  RotateCcw,
  RefreshCw,
  X,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { CSSProperties, PointerEvent as ReactPointerEvent } from "react";

import { getCommunities, getJob, getJobs, getSagas, rebuildCommunities, summarizeSaga } from "./api";
import type { BackgroundJob, CommunityOverview, SagaOverview } from "./types";

interface SagaDisplayMeta {
  layer: number;
  layerName: string;
  title: string;
  description: string;
}

const SAGA_META: Record<string, SagaDisplayMeta> = {
  stage3_leadership: {
    layer: 3,
    layerName: "企业实体层",
    title: "龙头企业判断",
    description: "按产业环节整理国内外候选企业和代表企业。",
  },
  stage4_company_relationship: {
    layer: 4,
    layerName: "关系事实层",
    title: "企业产业关系",
    description: "供应、授权、代工、封测等企业主体之间的公开事实关系。",
  },
  stage6_company_product: {
    layer: 4,
    layerName: "关系事实层",
    title: "公司-产品服务关系",
    description: "企业与产品服务之间的生产、销售、使用、采购、集成关系。",
  },
  stage6_company_competition: {
    layer: 4,
    layerName: "关系事实层",
    title: "竞争候选关系",
    description: "同环节同产品企业之间的候选竞争关系，保留推定和验证限制。",
  },
  stage7_digital_china: {
    layer: 5,
    layerName: "业务关联层",
    title: "神州数码业务关系",
    description: "公开确认、潜在匹配和需内部验证的神州数码业务关系。",
  },
};
for (const [legacyKey, meta] of Object.entries({
  layer3_leadership: SAGA_META.stage3_leadership,
  layer4_company_relationship: SAGA_META.stage4_company_relationship,
  layer4_company_product: SAGA_META.stage6_company_product,
  layer4_company_competition: SAGA_META.stage6_company_competition,
  layer5_digital_china: SAGA_META.stage7_digital_china,
})) {
  SAGA_META[legacyKey] = meta;
}

const STATUS_LABELS: Record<BackgroundJob["status"], string> = {
  queued: "排队中",
  running: "执行中",
  completed: "已完成",
  failed: "失败",
  interrupted: "已中断",
};

const MIN_DOCK_WIDTH = 360;
const MIN_DOCK_HEIGHT = 260;
const DEFAULT_DOCK_WIDTH = 680;
const DEFAULT_DOCK_HEIGHT = 440;

interface GovernancePanelProps {
  groupId: string;
  communityCount: number;
  onCompleted: () => void;
}

interface DockFrame {
  x: number;
  y: number;
  width: number;
  height: number;
}

export default function GovernancePanel({ groupId, communityCount, onCompleted }: GovernancePanelProps) {
  const panelRef = useRef<HTMLElement | null>(null);
  const [activeTab, setActiveTab] = useState<"saga" | "community">("saga");
  const [sagas, setSagas] = useState<SagaOverview[]>([]);
  const [communities, setCommunities] = useState<CommunityOverview[]>([]);
  const [jobs, setJobs] = useState<BackgroundJob[]>([]);
  const [trackedJobId, setTrackedJobId] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [frame, setFrame] = useState<DockFrame | null>(null);
  const [collapsed, setCollapsed] = useState(false);

  const load = useCallback(async () => {
    const [nextSagas, nextCommunities, nextJobs] = await Promise.all([
      getSagas(groupId),
      getCommunities(groupId),
      getJobs(),
    ]);
    const safeSagas = Array.isArray(nextSagas) ? nextSagas : [];
    const safeCommunities = Array.isArray(nextCommunities) ? nextCommunities : [];
    const safeJobs = Array.isArray(nextJobs) ? nextJobs : [];
    setSagas(safeSagas);
    setCommunities(safeCommunities);
    setJobs(safeJobs.slice(0, 5));
    setError(null);
    const active = safeJobs.find((job) => ["queued", "running"].includes(job.status));
    setTrackedJobId((current) => current ?? active?.id ?? null);
  }, [groupId]);

  useEffect(() => {
    load().catch((reason: Error) => setError(reason.message));
  }, [load]);

  useEffect(() => {
    if (!trackedJobId) return undefined;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const job = await getJob(trackedJobId);
        if (cancelled) return;
        setJobs((current) => [job, ...current.filter((item) => item.id !== job.id)].slice(0, 5));
        if (["completed", "failed", "interrupted"].includes(job.status)) {
          setTrackedJobId(null);
          await load();
          if (job.status === "completed") onCompleted();
          return;
        }
        timer = setTimeout(poll, 1400);
      } catch (reason) {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : "任务状态读取失败");
          timer = setTimeout(poll, 2000);
        }
      }
    };
    void poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [load, onCompleted, trackedJobId]);

  async function run(actionKey: string, operation: () => Promise<BackgroundJob>) {
    setBusyAction(actionKey);
    setError(null);
    try {
      const job = await operation();
      setJobs((current) => [job, ...current.filter((item) => item.id !== job.id)].slice(0, 5));
      setTrackedJobId(job.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "治理任务提交失败");
    } finally {
      setBusyAction(null);
    }
  }

  function resetFrame() {
    setFrame(null);
  }

  function startDrag(event: ReactPointerEvent<HTMLElement>) {
    if (event.button !== 0 || (event.target as HTMLElement).closest("button")) return;
    event.preventDefault();
    const startFrame = frame ?? frameFromElement(panelRef.current);
    const startClientX = event.clientX;
    const startClientY = event.clientY;
    startPointerOperation(event, startFrame, (pointerEvent) => {
      const bounds = panelRef.current?.parentElement?.getBoundingClientRect();
      return clampFrame(
        {
          ...startFrame,
          x: startFrame.x + pointerEvent.clientX - startClientX,
          y: startFrame.y + pointerEvent.clientY - startClientY,
        },
        bounds,
      );
    });
  }

  function startResize(event: ReactPointerEvent<HTMLButtonElement>) {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    const startFrame = frame ?? frameFromElement(panelRef.current);
    const startClientX = event.clientX;
    const startClientY = event.clientY;
    startPointerOperation(event, startFrame, (pointerEvent) => {
      const bounds = panelRef.current?.parentElement?.getBoundingClientRect();
      return clampFrame(
        {
          ...startFrame,
          width: startFrame.width + pointerEvent.clientX - startClientX,
          height: startFrame.height + pointerEvent.clientY - startClientY,
        },
        bounds,
      );
    });
  }

  function startPointerOperation(
    _event: ReactPointerEvent,
    startFrame: DockFrame,
    nextFrame: (event: PointerEvent) => DockFrame,
  ) {
    setFrame(startFrame);
    const move = (pointerEvent: PointerEvent) => setFrame(nextFrame(pointerEvent));
    const end = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", end);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", end, { once: true });
  }

  const dockStyle: CSSProperties | undefined = frame
    ? {
        left: frame.x,
        top: frame.y,
        right: "auto",
        bottom: "auto",
        width: frame.width,
        height: frame.height,
      }
    : undefined;

  const currentJob = jobs.find((job) => job.id === trackedJobId) ?? jobs[0];
  const sagaGroups = groupSagasByLayer(sagas);
  if (collapsed) {
    return (
      <button
        className="governance-launcher"
        aria-label="打开图谱治理"
        onClick={() => setCollapsed(false)}
      >
        <span>图谱治理</span>
        <b>事实时序 {sagas.length}</b>
        <b>结构聚类 {communities.length || communityCount}</b>
      </button>
    );
  }
  return (
    <aside ref={panelRef} className="governance-dock" style={dockStyle} aria-label="图谱治理">
      <header className="governance-head" onPointerDown={startDrag} title="拖动治理面板">
        <div>
          <span>图谱治理</span>
          <strong>{activeTab === "saga" ? "事件时间维度" : "结构聚类维度"}</strong>
        </div>
        <div className="governance-window-tools">
          <button className="dock-icon" aria-label="复位治理面板" title="复位治理面板" onClick={resetFrame}>
            <RotateCcw size={14} />
          </button>
          <button
            className="dock-icon"
            aria-label="刷新治理数据"
            title="刷新治理数据"
            onClick={() => void load().catch((reason: Error) => setError(reason.message))}
          >
            <RefreshCw size={14} />
          </button>
          <button className="dock-icon" aria-label="关闭图谱治理" title="关闭图谱治理" onClick={() => setCollapsed(true)}>
            <X size={14} />
          </button>
        </div>
      </header>

      <div className="governance-tabs" role="tablist" aria-label="治理维度">
        <button role="tab" aria-selected={activeTab === "saga"} onClick={() => setActiveTab("saga")}>
          <FileText size={13} />
          <span>事实时序</span>
          <b>{sagas.length}</b>
        </button>
        <button role="tab" aria-selected={activeTab === "community"} onClick={() => setActiveTab("community")}>
          <Boxes size={13} />
          <span>结构聚类</span>
          <b>{communities.length || communityCount}</b>
        </button>
      </div>

      {activeTab === "saga" ? (
        <>
          <div className="saga-list-head">
            <span>事实序列</span>
            <b>{sagas.length}</b>
          </div>
          <div className="saga-list">
            {sagaGroups.map((group) => (
              <section className="saga-layer-group" key={group.key}>
                <div className="saga-layer-head">
                  <span>{group.layerLabel}</span>
                  <strong>{group.layerName}</strong>
                  <small>{group.totalEpisodes} 条事件</small>
                </div>
                {group.items.map(({ saga, meta }) => {
                  const actionKey = `saga:${saga.uuid}`;
                  return (
                    <article className="saga-row" key={saga.uuid}>
                      <div className="saga-row-title">
                        <FileText size={14} />
                        <strong>{meta.title}</strong>
                        <button
                          aria-label={`总结 ${meta.title}`}
                          title={`总结 ${meta.title}`}
                          disabled={busyAction !== null || trackedJobId !== null}
                          onClick={() => void run(actionKey, () => summarizeSaga(saga.uuid, groupId))}
                        >
                          {busyAction === actionKey ? <LoaderCircle className="spinning" size={13} /> : <FileText size={13} />}
                        </button>
                      </div>
                      <div className="saga-meta">
                        <span>{saga.episode_count} 条事件</span>
                        <span>{saga.last_summarized_at ? "已总结" : "待总结"}</span>
                        {saga.last_summarized_at ? <span>{String(saga.last_summarized_at).slice(0, 10)}</span> : null}
                        {saga.last_summarized_episode_valid_at ? <span>截至 {String(saga.last_summarized_episode_valid_at).slice(0, 10)}</span> : null}
                      </div>
                      <p className="saga-description">{meta.description}</p>
                      {saga.summary ? <p>{saga.summary}</p> : null}
                    </article>
                  );
                })}
              </section>
            ))}
            {!sagas.length && !error ? <div className="governance-empty">暂无事实序列</div> : null}
          </div>
        </>
      ) : (
        <div className="community-pane">
          <section className="community-control">
            <div className="community-metric">
              <Boxes size={16} />
              <span><b>{communities.length || communityCount}</b> 个知识社区</span>
            </div>
            <button
              aria-label="重建结构聚类"
              disabled={busyAction !== null || trackedJobId !== null}
              onClick={() => void run("community", () => rebuildCommunities(groupId))}
            >
              {busyAction === "community" ? <LoaderCircle className="spinning" size={13} /> : <RefreshCw size={13} />}
              重建
            </button>
          </section>
          <div className="community-explain">
            <strong>结构聚类</strong>
            <p>结构聚类用于观察实体群、产品服务和产业环节之间的结构聚合；下方展示每个社区的摘要、成员数和代表实体。</p>
          </div>
          <div className="community-list">
            {communities.map((community, index) => (
              <details className="community-row" key={community.uuid} open={index === 0}>
                <summary className="community-row-title">
                  <Boxes size={14} />
                  <strong>{community.name}</strong>
                  <span>{community.member_count} 个成员</span>
                </summary>
                {community.summary ? <p>{community.summary}</p> : null}
                {community.representative_entities?.length ? (
                  <div className="community-members" aria-label={`${community.name} 代表实体`}>
                    {community.representative_entities.slice(0, 8).map((name) => (
                      <span key={name}>{name}</span>
                    ))}
                  </div>
                ) : null}
                {community.created_at ? <small>创建于 {String(community.created_at).slice(0, 10)}</small> : null}
              </details>
            ))}
            {!communities.length && !error ? (
              <div className="governance-empty">暂无结构聚类列表，点击重建后可生成结果。</div>
            ) : null}
          </div>
          {currentJob ? (
            <div className="community-job-card">
              <span>最近任务</span>
              <b>{currentJob.job_type === "summarize_saga" ? "事实序列总结" : "结构聚类重建"}</b>
              <small>{currentJob.error || String(currentJob.result?.message ?? STATUS_LABELS[currentJob.status])}</small>
            </div>
          ) : null}
        </div>
      )}

      {activeTab === "saga" && currentJob ? (
        <div className={`governance-job job-${currentJob.status}`}>
          {currentJob.status === "completed" ? <CheckCircle2 size={14} /> : currentJob.status === "failed" ? <AlertCircle size={14} /> : <LoaderCircle className={currentJob.status === "running" ? "spinning" : ""} size={14} />}
          <span>
            <b>{currentJob.job_type === "summarize_saga" ? "事实序列总结" : "结构聚类重建"}</b>
            <small>{currentJob.error || String(currentJob.result?.message ?? STATUS_LABELS[currentJob.status])}</small>
          </span>
        </div>
      ) : null}
      {error ? <p className="governance-error" role="alert">{error}</p> : null}
      <button
        className="governance-resize-handle"
        aria-label="调整治理面板大小"
        title="拖动调整大小"
        onPointerDown={startResize}
      />
    </aside>
  );
}

function defaultFrame(container: Element | null | undefined): DockFrame {
  const bounds = container?.getBoundingClientRect();
  const width = Math.min(
    DEFAULT_DOCK_WIDTH,
    Math.max(MIN_DOCK_WIDTH, (bounds?.width ?? DEFAULT_DOCK_WIDTH + 32) - 32),
  );
  const height = Math.min(
    DEFAULT_DOCK_HEIGHT,
    Math.max(MIN_DOCK_HEIGHT, (bounds?.height ?? DEFAULT_DOCK_HEIGHT + 92) - 92),
  );
  return clampFrame(
    {
      x: Math.max(16, (bounds?.width ?? width + 32) - width - 16),
      y: Math.max(14, (bounds?.height ?? height + 92) - height - 14),
      width,
      height,
    },
    bounds,
  );
}

function frameFromElement(element: HTMLElement | null): DockFrame {
  const parentBounds = element?.parentElement?.getBoundingClientRect();
  const bounds = element?.getBoundingClientRect();
  if (!parentBounds || !bounds) return defaultFrame(element?.parentElement);
  return clampFrame(
    {
      x: bounds.left - parentBounds.left,
      y: bounds.top - parentBounds.top,
      width: bounds.width,
      height: bounds.height,
    },
    parentBounds,
  );
}

function clampFrame(frame: DockFrame, bounds: DOMRect | undefined): DockFrame {
  const maxWidth = Math.max(MIN_DOCK_WIDTH, (bounds?.width ?? frame.width) - 20);
  const maxHeight = Math.max(MIN_DOCK_HEIGHT, (bounds?.height ?? frame.height) - 20);
  const width = Math.min(Math.max(frame.width, MIN_DOCK_WIDTH), maxWidth);
  const height = Math.min(Math.max(frame.height, MIN_DOCK_HEIGHT), maxHeight);
  const maxX = Math.max(10, (bounds?.width ?? width + 20) - width - 10);
  const maxY = Math.max(10, (bounds?.height ?? height + 20) - height - 10);
  return {
    x: Math.min(Math.max(frame.x, 10), maxX),
    y: Math.min(Math.max(frame.y, 10), maxY),
    width,
    height,
  };
}

function sagaMeta(saga: SagaOverview): SagaDisplayMeta {
  if (saga.layer_id && saga.layer_name && saga.fact_set_name) {
    return {
      layer: saga.layer_id,
      layerName: saga.layer_name,
      title: saga.fact_set_name,
      description: saga.fact_set_description || saga.display_name || saga.name,
    };
  }
  return SAGA_META[saga.name] ?? SAGA_META[saga.saga_key || ""] ?? SAGA_META[saga.legacy_saga_key || ""] ?? {
    layer: 99,
    layerName: "未归类事实序列",
    title: saga.name,
    description: "该事实序列暂未映射到标准 Layer，需要后续治理补充分类。",
  };
}

function groupSagasByLayer(sagas: SagaOverview[]) {
  const groups = new Map<
    string,
    {
      key: string;
      layerLabel: string;
      layerName: string;
      totalEpisodes: number;
      items: Array<{ saga: SagaOverview; meta: SagaDisplayMeta }>;
    }
  >();
  for (const saga of sagas) {
    const meta = sagaMeta(saga);
    const key = `${meta.layer}:${meta.layerName}`;
    const group = groups.get(key) ?? {
      key,
      layerLabel: meta.layer === 99 ? "未归类" : `Layer ${meta.layer}`,
      layerName: meta.layerName,
      totalEpisodes: 0,
      items: [],
    };
    group.totalEpisodes += saga.episode_count;
    group.items.push({ saga, meta });
    groups.set(key, group);
  }
  return [...groups.values()].sort((left, right) => left.key.localeCompare(right.key, "zh-Hans-CN"));
}
