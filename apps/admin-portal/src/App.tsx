import {
  Activity,
  Database,
  FileSearch,
  FileText,
  LogOut,
  Network,
  RefreshCw,
  Shield,
} from "lucide-react";
import { FormEvent, lazy, Suspense, useEffect, useState } from "react";

import {
  ADMIN_UNAUTHORIZED_EVENT,
  adminLogin,
  adminLogout,
  adminMe,
  expandUnifiedGraph,
  getGraphStats,
  getUnifiedGraphRoot,
  listGroups,
  selectedGroupId,
  setSelectedGroupId,
} from "./api";
import DecisionSignalsPage from "./DecisionSignalsPage";
import GovernancePanel from "./GovernancePanel";
import IndustrySearchPanel from "./IndustrySearchPanel";
import TraceMonitor from "./TraceMonitor";
import type { GraphBranch, GraphNode, GraphPayload, GraphStats, GroupSummary } from "./types";
import "./styles.css";

const EMPTY_GRAPH: GraphPayload = { nodes: [], edges: [] };
const GraphCanvas = lazy(() => import("./GraphCanvas"));

interface AdminAuthWindow {
  __adminAuthGeneration?: number;
}

interface ExpansionRecord {
  parentId: string;
  branch: GraphBranch;
  nodeIds: string[];
  edgeIds: string[];
}

function Login({ onAuthenticated }: { onAuthenticated: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await adminLogin(password);
      onAuthenticated();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "登录失败");
    } finally {
      setSubmitting(false);
    }
  }
  return (
    <main className="login-page">
      <form className="login-panel" onSubmit={submit}>
        <div className="login-mark"><Network size={24} /></div>
        <h1>图谱管理台</h1>
        <label htmlFor="admin-password">管理口令</label>
        <input id="admin-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" />
        {error ? <p role="alert">{error}</p> : null}
        <button type="submit" disabled={!password || submitting}>进入管理台</button>
      </form>
    </main>
  );
}

function GraphCenter({ groupId }: { groupId: string }) {
  const [graph, setGraph] = useState<GraphPayload>(EMPTY_GRAPH);
  const [stats, setStats] = useState<GraphStats>({});
  const [loading, setLoading] = useState(true);
  const [expanding, setExpanding] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [baseNodeIds, setBaseNodeIds] = useState<Set<string>>(new Set());
  const [baseEdgeIds, setBaseEdgeIds] = useState<Set<string>>(new Set());
  const [expansions, setExpansions] = useState<Record<string, ExpansionRecord>>({});

  useEffect(() => {
    getGraphStats(groupId).then(setStats).catch(() => setStats({}));
  }, [groupId, revision]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getUnifiedGraphRoot(groupId)
      .then((payload) => {
        if (!cancelled) {
          setGraph(payload);
          setBaseNodeIds(new Set(payload.nodes.map((node) => node.id)));
          setBaseEdgeIds(new Set(payload.edges.map((edge) => edge.id)));
          setExpansions({});
        }
      })
      .catch((reason: Error) => { if (!cancelled) setError(reason.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [groupId, revision]);

  function collapseExpansionKeys(keys: string[]) {
    if (!keys.length) return;
    setGraph((current) => {
      const result = removeExpansions(current, expansions, keys, baseNodeIds, baseEdgeIds);
      setExpansions(result.expansions);
      return result.graph;
    });
  }

  function collapseNode(node: GraphNode) {
    collapseExpansionKeys(
      Object.entries(expansions)
        .filter(([, record]) => record.parentId === node.id)
        .map(([key]) => key),
    );
  }

  async function expandNode(node: GraphNode, branch: GraphBranch) {
    const key = `${node.id}:${branch}`;
    if (expansions[key]) {
      collapseExpansionKeys([key]);
      return;
    }
    setExpanding(key);
    setError(null);
    try {
      const payload = await expandUnifiedGraph({ node_id: node.id, branch, limit: 20 }, groupId);
      const positioned = positionIncoming(payload, node);
      setGraph((current) => mergeGraph(current, positioned));
      setExpansions((current) => ({
        ...current,
        [key]: {
          parentId: node.id,
          branch,
          nodeIds: positioned.nodes.filter((candidate) => candidate.id !== node.id).map((candidate) => candidate.id),
          edgeIds: positioned.edges.map((edge) => edge.id),
        },
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "图谱展开失败");
    } finally {
      setExpanding(null);
    }
  }

  return (
    <section className="workspace graph-workspace">
      <header className="workspace-header">
        <div>
          <span className="section-kicker">知识图谱</span>
          <h1>统一产业图谱</h1>
        </div>
        <div className="graph-stats">
          <span><b>{stats.industry_nodes ?? "-"}</b>产业节点</span>
          <span><b>{stats.facts ?? "-"}</b>事实关系</span>
          <span><b>{stats.episodes ?? "-"}</b>事件</span>
          <span><b>{stats.sagas ?? "-"}</b>事实集</span>
        </div>
        <button className="refresh-button" aria-label="刷新图谱" onClick={() => setRevision((value) => value + 1)}><RefreshCw size={16} /></button>
      </header>
      {error ? <div className="workspace-error" role="alert">{error}</div> : null}
      <div className="graph-body">
        <Suspense fallback={<div className="graph-loading"><span /><span /><span /></div>}>
          <GraphCanvas
            graph={graph}
            loading={loading}
            expanding={expanding}
            activeExpansionKeys={Object.keys(expansions)}
            onExpand={expandNode}
            onCollapseNode={collapseNode}
          />
        </Suspense>
        <GovernancePanel
          groupId={groupId}
          communityCount={stats.communities ?? 0}
          onCompleted={() => setRevision((value) => value + 1)}
        />
      </div>
    </section>
  );
}

function mergeGraph(current: GraphPayload, incoming: GraphPayload): GraphPayload {
  const nodes = new Map(current.nodes.map((node) => [node.id, node]));
  for (const node of incoming.nodes) nodes.set(node.id, node);
  const edges = new Map(current.edges.map((edge) => [edge.id, edge]));
  for (const edge of incoming.edges) edges.set(edge.id, edge);
  return { nodes: [...nodes.values()], edges: [...edges.values()] };
}

function removeExpansions(
  graph: GraphPayload,
  expansions: Record<string, ExpansionRecord>,
  initialKeys: string[],
  baseNodeIds: Set<string>,
  baseEdgeIds: Set<string>,
): { graph: GraphPayload; expansions: Record<string, ExpansionRecord> } {
  const keysToRemove = new Set(initialKeys.filter((key) => expansions[key]));
  let changed = true;
  while (changed) {
    changed = false;
    const removingNodeIds = new Set<string>();
    for (const key of keysToRemove) {
      expansions[key]?.nodeIds.forEach((nodeId) => removingNodeIds.add(nodeId));
    }
    for (const [key, record] of Object.entries(expansions)) {
      if (!keysToRemove.has(key) && removingNodeIds.has(record.parentId)) {
        keysToRemove.add(key);
        changed = true;
      }
    }
  }

  if (keysToRemove.size === 0) return { graph, expansions };

  const remainingExpansions = Object.fromEntries(
    Object.entries(expansions).filter(([key]) => !keysToRemove.has(key)),
  ) as Record<string, ExpansionRecord>;
  const remainingNodeIds = new Set(baseNodeIds);
  const remainingEdgeIds = new Set(baseEdgeIds);
  for (const record of Object.values(remainingExpansions)) {
    remainingNodeIds.add(record.parentId);
    record.nodeIds.forEach((nodeId) => remainingNodeIds.add(nodeId));
    record.edgeIds.forEach((edgeId) => remainingEdgeIds.add(edgeId));
  }

  const candidateNodeIds = new Set<string>();
  const candidateEdgeIds = new Set<string>();
  for (const key of keysToRemove) {
    const record = expansions[key];
    if (!record) continue;
    record.nodeIds.forEach((nodeId) => candidateNodeIds.add(nodeId));
    record.edgeIds.forEach((edgeId) => candidateEdgeIds.add(edgeId));
  }

  const removableNodeIds = new Set(
    [...candidateNodeIds].filter((nodeId) => !remainingNodeIds.has(nodeId)),
  );
  const removableEdgeIds = new Set(
    [...candidateEdgeIds].filter((edgeId) => !remainingEdgeIds.has(edgeId)),
  );

  return {
    graph: {
      nodes: graph.nodes.filter((node) => !removableNodeIds.has(node.id)),
      edges: graph.edges.filter((edge) => {
        if (baseEdgeIds.has(edge.id) || remainingEdgeIds.has(edge.id)) return true;
        if (removableEdgeIds.has(edge.id)) return false;
        return !removableNodeIds.has(edge.source) && !removableNodeIds.has(edge.target);
      }),
    },
    expansions: remainingExpansions,
  };
}

function numericProperty(node: GraphNode, key: string, fallback: number): number {
  const value = node.properties[key];
  return typeof value === "number" ? value : fallback;
}

function positionIncoming(incoming: GraphPayload, parent: GraphNode): GraphPayload {
  const parentX = numericProperty(parent, "x", 0);
  const parentLevel = numericProperty(parent, "level", 0);
  const grouped = new Map<number, GraphNode[]>();
  for (const node of incoming.nodes) {
    const level = numericProperty(node, "level", parentLevel + 1);
    grouped.set(level, [...(grouped.get(level) ?? []), node]);
  }
  for (const [level, nodes] of grouped) {
    const ordered = [...nodes].sort((left, right) =>
      String(left.properties["名称"] ?? left.properties.name ?? left.id).localeCompare(
        String(right.properties["名称"] ?? right.properties.name ?? right.id),
        "zh-Hans-CN",
      ),
    );
    ordered.forEach((node, index) => {
      node.properties = {
        ...node.properties,
        x: Math.round(parentX + (index - (ordered.length - 1) / 2) * 210),
        y: level * 138,
      };
    });
  }
  return incoming;
}

function App() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [page, setPage] = useState<"graph" | "extension" | "signals" | "traces">("graph");
  const [groups, setGroups] = useState<GroupSummary[]>([]);
  const [groupId, setGroupId] = useState(selectedGroupId() ?? "semiconductor_dc_kg");

  useEffect(() => {
    if (!authenticated) return;
    let cancelled = false;
    listGroups()
      .then((items) => {
        if (cancelled) return;
        const safeItems = Array.isArray(items) ? items : [];
        setGroups(safeItems);
        const stored = selectedGroupId();
        const next = stored && safeItems.some((item) => item.id === stored)
          ? stored
          : safeItems[0]?.id ?? "semiconductor_dc_kg";
        setGroupId(next);
        setSelectedGroupId(next);
      })
      .catch(() => {
        if (!cancelled) {
          const fallback = selectedGroupId() ?? "semiconductor_dc_kg";
          setGroups([{ id: fallback, label: fallback, is_default: true }]);
          setGroupId(fallback);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [authenticated]);

  useEffect(() => {
    const authWindow = window as AdminAuthWindow;
    authWindow.__adminAuthGeneration = (authWindow.__adminAuthGeneration ?? 0) + 1;
    adminMe().then(() => setAuthenticated(true)).catch(() => setAuthenticated(false));
  }, []);
  useEffect(() => {
    const currentGeneration = (window as AdminAuthWindow).__adminAuthGeneration ?? 0;
    const expireSession = (event: Event) => {
      const generation = (event as CustomEvent<{ generation?: number }>).detail?.generation;
      if (generation === currentGeneration) setAuthenticated(false);
    };
    window.addEventListener(ADMIN_UNAUTHORIZED_EVENT, expireSession);
    return () => window.removeEventListener(ADMIN_UNAUTHORIZED_EVENT, expireSession);
  }, []);

  if (authenticated === null) return <div className="boot-screen"><Network size={26} /></div>;
  if (!authenticated) return <Login onAuthenticated={() => setAuthenticated(true)} />;

  return (
    <div className="admin-shell">
      <aside className="admin-sidebar">
        <div className="admin-brand"><Network size={20} /><span>图谱管理台</span></div>
        <nav aria-label="管理导航">
          <button aria-label="图谱中心" className={page === "graph" ? "active" : ""} onClick={() => setPage("graph")}><Database size={18} /><span>图谱中心</span></button>
          <button aria-label="产业扩展" className={page === "extension" ? "active" : ""} onClick={() => setPage("extension")}><FileSearch size={18} /><span>产业扩展</span></button>
          <button aria-label="决策资料" className={page === "signals" ? "active" : ""} onClick={() => setPage("signals")}><FileText size={18} /><span>决策资料</span></button>
          <button aria-label="链路观测" className={page === "traces" ? "active" : ""} onClick={() => setPage("traces")}><Activity size={18} /><span>链路观测</span></button>
        </nav>
        <div className="admin-scope">
          <Shield size={15} />
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
        <button className="logout-button" aria-label="退出管理台" onClick={async () => { await adminLogout(); setAuthenticated(false); }}><LogOut size={17} /><span>退出</span></button>
      </aside>
      <main className="admin-main">
        {page === "graph" ? <GraphCenter groupId={groupId} /> : null}
        {page === "extension" ? <IndustrySearchPanel groupId={groupId} groups={groups} /> : null}
        {page === "signals" ? <DecisionSignalsPage groupId={groupId} /> : null}
        {page === "traces" ? <TraceMonitor /> : null}
      </main>
    </div>
  );
}

export default App;
