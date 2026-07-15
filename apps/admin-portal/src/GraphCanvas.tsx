import cytoscape, { Core, ElementDefinition, StylesheetJson } from "cytoscape";
import { ChevronDown, Maximize2, Minus, Plus, Search, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import type { GraphBranch, GraphEdge, GraphNode, GraphPayload } from "./types";

const COLORS: Record<string, string> = {
  "L1 产业层级": "#0d6156",
  "L2 业务域": "#2e6690",
  "L3 产业环节": "#697339",
  "L4 细分环节": "#a86139",
  "产品服务": "#4f7b61",
  "企业": "#283532",
  "神州数码": "#9b463e",
  "事实实体": "#376f8e",
  "事件": "#ad7241",
  "事件序列": "#7d4d67",
  "知识社区": "#596940",
};

const BRANCH_LABELS: Record<GraphBranch, string> = {
  hierarchy: "展开层级",
  business: "展开业务关系",
  facts: "展开事实关系",
  evidence: "展开证据",
  timeline: "展开事件时序",
  saga: "展开事实时序",
  community: "展开结构聚类",
  digital_china: "展开神州数码关系",
};

const QUALITY_FILTERS = {
  all: "全部质量",
  high: "高可信",
  needs_validation: "需内部验证",
  weak: "弱证据",
  search_only: "仅搜索结果支撑",
} as const;

type QualityFilter = keyof typeof QUALITY_FILTERS;

const STYLES: StylesheetJson = [
  {
    selector: "node",
    style: {
      "background-color": "data(color)",
      label: "data(label)",
      color: "#1f2a27",
      "font-size": 9,
      "font-family": "Microsoft YaHei UI",
      "text-valign": "bottom",
      "text-margin-y": 8,
      "text-wrap": "wrap",
      "text-max-width": "118px",
      width: "data(size)",
      height: "data(size)",
      "border-width": 2,
      "border-color": "#ffffff",
      "overlay-opacity": 0,
    },
  },
  {
    selector: "edge",
    style: {
      width: 1.1,
      "line-color": "#b7c6c1",
      "target-arrow-color": "#8da29b",
      "target-arrow-shape": "triangle",
      "arrow-scale": 0.78,
      "curve-style": "bezier",
      "control-point-step-size": 46,
      label: "data(label)",
      "font-size": 7,
      color: "#60706b",
      "text-background-color": "#fbfcfc",
      "text-background-opacity": 0.9,
      "text-background-padding": "2px",
      "text-rotation": "autorotate",
      "text-margin-y": -5,
      "overlay-opacity": 0,
    },
  },
  { selector: ".dimmed", style: { opacity: 0.12 } },
  { selector: ".quality-hidden", style: { display: "none" } },
  {
    selector: ".matched",
    style: { "border-color": "#c24f3d", "border-width": 4, opacity: 1 },
  },
  {
    selector: ":selected",
    style: { "border-color": "#c24f3d", "border-width": 4 },
  },
];

function nodeName(node: GraphNode): string {
  return String(node.properties["名称"] ?? node.properties.name ?? node.id);
}

function numericProperty(node: GraphNode, key: string, fallback: number): number {
  const value = node.properties[key];
  return typeof value === "number" ? value : fallback;
}

function graphElements(graph: GraphPayload): ElementDefinition[] {
  const levels = new Map<number, GraphNode[]>();
  graph.nodes.forEach((node) => {
    const level = numericProperty(node, "level", 6);
    levels.set(level, [...(levels.get(level) ?? []), node]);
  });
  const fallbackPositions = new Map<string, { x: number; y: number }>();
  for (const [level, nodes] of levels) {
    const ordered = [...nodes].sort((left, right) => nodeName(left).localeCompare(nodeName(right), "zh-Hans-CN"));
    ordered.forEach((node, index) => {
      fallbackPositions.set(node.id, {
        x: (index - (ordered.length - 1) / 2) * 230,
        y: level * 138,
      });
    });
  }

  return [
    ...graph.nodes.map((node) => {
      const kind = node.labels[0] ?? "实体";
      const fallback = fallbackPositions.get(node.id) ?? { x: 0, y: 0 };
      return {
        data: {
          id: node.id,
          label: nodeName(node),
          kind,
          color: COLORS[kind] ?? "#65736f",
          size: numericProperty(node, "level", 6) <= 1 ? 34 : 24,
          properties: node.properties,
        },
        position: {
          x: numericProperty(node, "x", fallback.x),
          y: numericProperty(node, "y", fallback.y),
        },
      };
    }),
    ...graph.edges.map((edge) => ({
      data: {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edgeLabel(edge),
        type: edge.type,
        properties: edge.properties,
      },
    })),
  ];
}

function edgeLabel(edge: GraphEdge): string {
  return String(
    edge.properties.display_label ??
      edge.properties["关系名称"] ??
      edge.properties.name ??
      edge.type,
  );
}

function branchOptions(node: GraphNode): GraphBranch[] {
  const raw = node.properties.branch_options;
  if (Array.isArray(raw)) {
    return raw.filter((value): value is GraphBranch => Object.prototype.hasOwnProperty.call(BRANCH_LABELS, String(value)));
  }
  const label = node.labels[0];
  if (label?.startsWith("L") && label !== "L4 细分环节") return ["hierarchy"];
  if (label === "L4 细分环节") return ["business", "facts", "evidence"];
  if (label === "产品服务") return ["business", "facts", "evidence"];
  if (["企业", "神州数码"].includes(label ?? "")) return ["business", "digital_china", "facts", "evidence", "timeline", "saga", "community"];
  if (label === "事实实体") return ["business", "facts", "evidence", "timeline", "saga", "community"];
  if (label === "事件") return ["facts", "evidence"];
  return [];
}

function branchActionLabel(node: GraphNode, branch: GraphBranch, activeExpansionKeys: string[]): string {
  const label = BRANCH_LABELS[branch];
  if (!activeExpansionKeys.includes(`${node.id}:${branch}`)) return label;
  return label.startsWith("展开") ? label.replace(/^展开/, "收回") : `收回${label}`;
}

function propertyValue(properties: Record<string, unknown>, ...keys: string[]): unknown {
  return keys.map((key) => properties[key]).find((value) => value !== undefined && value !== null && value !== "");
}

function digitalChinaStatusText(value: unknown): string {
  const status = String(value ?? "");
  const labels: Record<string, string> = {
    confirmed_public_relationship: "公开确认",
    potential_fit: "潜在匹配",
    needs_internal_validation: "需内部验证",
    no_public_evidence: "暂无公开证据",
    likely_public_relationship: "公开线索",
    possible_public_relationship: "待确认线索",
    no_public_relationship: "未发现公开关系",
  };
  return labels[status] ?? status;
}

function evidenceIdList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String).filter(Boolean);
  if (typeof value === "string") return value.split(/[,，]/).map((item) => item.trim()).filter(Boolean);
  return [];
}

function DigitalChinaRelationshipCard({ properties }: { properties: Record<string, unknown> }) {
  const status = propertyValue(properties, "digital_china_relationship_status", "relationship_status", "神州数码关系状态", "关系状态");
  const relationshipType = propertyValue(properties, "digital_china_relationship_type", "relationship_type", "神州数码关系类型", "关系类型");
  const basis = propertyValue(properties, "digital_china_relationship_basis", "relationship_basis", "神州数码关系依据", "判断依据");
  const evidenceIds = evidenceIdList(propertyValue(properties, "digital_china_evidence_ids", "evidence_ids", "神州数码关系证据ID", "证据ID"));
  const confidence = propertyValue(properties, "digital_china_confidence", "confidence", "神州数码关系置信度", "置信度");
  const limitations = propertyValue(properties, "digital_china_limitations", "limitations", "神州数码关系局限说明", "局限说明");
  const needsValidation = booleanish(propertyValue(properties, "requires_internal_validation", "是否需要内部验证"));

  if (!status && !relationshipType && !basis && !evidenceIds.length) return null;

  return (
    <section className="digital-china-card">
      <div className="digital-china-card-head">
        <span>神州数码业务关系</span>
        {status ? <b>{digitalChinaStatusText(status)}</b> : null}
      </div>
      {relationshipType ? <strong>{String(relationshipType)}</strong> : null}
      {basis ? <p>{String(basis)}</p> : null}
      <div className="digital-china-meta">
        {confidence ? <span>置信度 {String(confidence)}</span> : null}
        {needsValidation ? <span>需要内部验证</span> : null}
      </div>
      {evidenceIds.length ? (
        <div className="digital-china-evidence">
          {evidenceIds.map((id) => <span key={id}>{id}</span>)}
        </div>
      ) : null}
      {limitations ? <small>{String(limitations)}</small> : null}
    </section>
  );
}

function PropertyInspector({
  node,
  expanding,
  activeExpansionKeys,
  onClose,
  onExpand,
}: {
  node: GraphNode;
  expanding: string | null;
  activeExpansionKeys: string[];
  onClose: () => void;
  onExpand: (node: GraphNode, branch: GraphBranch) => void;
}) {
  const visible = Object.entries(node.properties)
    .filter(([key, value]) =>
      ![
        "branch_options",
        "x",
        "y",
        "level",
        "requires_internal_validation",
        "是否需要内部验证",
        "神州数码关系状态",
        "神州数码关系类型",
        "神州数码关系依据",
        "神州数码关系证据ID",
        "神州数码关系置信度",
        "神州数码关系局限说明",
      ].includes(key) &&
      !key.startsWith("digital_china_") &&
      value !== null &&
      value !== "",
    )
    .slice(0, 18);
  const options = branchOptions(node);
  const primaryOptions = options.filter((branch) => !["saga", "community"].includes(branch));
  const governanceOptions = options.filter((branch) => ["saga", "community"].includes(branch));
  return (
    <aside className="node-inspector">
      <div className="inspector-head">
        <div>
          <span>{node.labels[0] ?? "实体"}</span>
          <h3>{nodeName(node)}</h3>
        </div>
        <button className="tool-icon" aria-label="关闭节点详情" onClick={onClose}><X size={17} /></button>
      </div>
      {primaryOptions.length ? (
        <div className="branch-actions">
          {primaryOptions.map((branch) => (
            <button
              key={branch}
              className={activeExpansionKeys.includes(`${node.id}:${branch}`) ? "active" : ""}
              aria-pressed={activeExpansionKeys.includes(`${node.id}:${branch}`)}
              disabled={expanding === `${node.id}:${branch}`}
              onClick={() => onExpand(node, branch)}
            >
              <ChevronDown size={14} />
              <span>{branchActionLabel(node, branch, activeExpansionKeys)}</span>
            </button>
          ))}
        </div>
      ) : null}
      {governanceOptions.length ? (
        <section className="local-context">
          <div className="local-context-head">
            <span>局部上下文</span>
            <b>{nodeName(node)}</b>
          </div>
          <div className="local-context-list">
            {governanceOptions.map((branch) => (
              <button
                key={branch}
                className={activeExpansionKeys.includes(`${node.id}:${branch}`) ? "active" : ""}
                aria-pressed={activeExpansionKeys.includes(`${node.id}:${branch}`)}
                disabled={expanding === `${node.id}:${branch}`}
                onClick={() => onExpand(node, branch)}
              >
                <strong>{activeExpansionKeys.includes(`${node.id}:${branch}`) ? "收回" : "展开"}{branch === "saga" ? "事实时序" : "结构聚类社区"}</strong>
                <span>
                  {branch === "saga"
                    ? "查看该实体出现在哪些事实序列里"
                    : "查看该实体属于哪些结构聚类社区"}
                </span>
              </button>
            ))}
          </div>
        </section>
      ) : null}
      <DigitalChinaRelationshipCard properties={node.properties} />
      <dl>
        {visible.map(([key, value]) => (
          <div key={key}>
            <dt>{key}</dt>
            <dd>{typeof value === "object" ? JSON.stringify(value) : String(value)}</dd>
          </div>
        ))}
      </dl>
    </aside>
  );
}

function EdgeInspector({
  edge,
  nodeIndex,
  onClose,
}: {
  edge: GraphEdge;
  nodeIndex: Map<string, GraphNode>;
  onClose: () => void;
}) {
  const source = nodeIndex.get(edge.source);
  const target = nodeIndex.get(edge.target);
  const merged: Record<string, unknown> = {
    "起点": source ? nodeName(source) : edge.source,
    "终点": target ? nodeName(target) : edge.target,
    "图上关系": edgeLabel(edge),
    ...edge.properties,
  };
  const important = [
    "起点",
    "终点",
    "图上关系",
    "原始关系类型",
    "原始关系名",
    "name",
    "fact",
    "valid_at",
    "invalid_at",
    "reference_time",
    "created_at",
    "last_verified_at",
    "data_as_of",
    "current_validity",
    "confidence",
    "evidence_ids",
    "证据ID",
  ];
  const ordered = [
    ...important
      .filter((key) => merged[key] !== undefined && merged[key] !== null && merged[key] !== "")
      .map((key) => [key, merged[key]] as [string, unknown]),
    ...Object.entries(merged).filter(
      ([key, value]) =>
        !important.includes(key) &&
        !["display_label", "fact_embedding", "embedding"].some((hidden) => key.includes(hidden)) &&
        value !== null &&
        value !== "",
    ),
  ].slice(0, 28);
  return (
    <aside className="node-inspector edge-inspector">
      <div className="inspector-head">
        <div>
          <span>关系详情</span>
          <h3>{edgeLabel(edge)}</h3>
        </div>
        <button className="tool-icon" aria-label="关闭关系详情" onClick={onClose}><X size={17} /></button>
      </div>
      {edge.properties.fact ? (
        <section className="edge-fact-card">
          <span>事实文本</span>
          <p>{String(edge.properties.fact)}</p>
        </section>
      ) : null}
      <dl>
        {ordered.map(([key, value]) => (
          <div key={key}>
            <dt>{fieldLabel(key)}</dt>
            <dd>{formatValue(value)}</dd>
          </div>
        ))}
      </dl>
    </aside>
  );
}

interface GraphCanvasProps {
  graph: GraphPayload;
  loading: boolean;
  expanding: string | null;
  activeExpansionKeys: string[];
  onExpand: (node: GraphNode, branch: GraphBranch) => void;
  onCollapseNode: (node: GraphNode) => void;
}

export default function GraphCanvas({ graph, loading, expanding, activeExpansionKeys, onExpand, onCollapseNode }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const coreRef = useRef<Core | null>(null);
  const nodeIndexRef = useRef(new Map<string, GraphNode>());
  const edgeIndexRef = useRef(new Map<string, GraphEdge>());
  const onExpandRef = useRef(onExpand);
  const onCollapseNodeRef = useRef(onCollapseNode);
  const [query, setQuery] = useState("");
  const [qualityFilter, setQualityFilter] = useState<QualityFilter>("all");
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);
  const nodeIndex = useMemo(() => new Map(graph.nodes.map((node) => [node.id, node])), [graph.nodes]);
  const edgeIndex = useMemo(() => new Map(graph.edges.map((edge) => [edge.id, edge])), [graph.edges]);

  useEffect(() => {
    nodeIndexRef.current = nodeIndex;
    edgeIndexRef.current = edgeIndex;
    onExpandRef.current = onExpand;
    onCollapseNodeRef.current = onCollapseNode;
  }, [nodeIndex, edgeIndex, onExpand, onCollapseNode]);

  useEffect(() => {
    if (!containerRef.current || loading || coreRef.current) return;
    const core = cytoscape({
      container: containerRef.current,
      elements: graphElements(graph),
      style: STYLES,
      layout: { name: "preset", animate: false, fit: true, padding: 70 },
      minZoom: 0.08,
      maxZoom: 3,
      wheelSensitivity: 0.22,
    });
    core.on("tap", "node", (event) => {
      const node = nodeIndexRef.current.get(event.target.id());
      if (!node) return;
      setSelectedEdge(null);
      const options = branchOptions(node);
      if (options.length === 1) {
        setSelected(null);
        onExpandRef.current(node, options[0]);
        return;
      }
      setSelected(node);
    });
    core.on("cxttap", "node", (event) => {
      const node = nodeIndexRef.current.get(event.target.id());
      if (!node) return;
      (event as { originalEvent?: Event }).originalEvent?.preventDefault();
      setSelected(null);
      setSelectedEdge(null);
      onCollapseNodeRef.current(node);
    });
    core.on("tap", "edge", (event) => {
      const edge = edgeIndexRef.current.get(event.target.id());
      if (!edge) return;
      setSelected(null);
      setSelectedEdge(edge);
    });
    coreRef.current = core;
    return () => {
      core.destroy();
      coreRef.current = null;
    };
  }, [loading]);

  useEffect(() => {
    const core = coreRef.current;
    if (!core || loading) return;
    const pan = { ...core.pan() };
    const zoom = core.zoom();
    core.batch(() => {
      core.elements().remove();
      core.add(graphElements(graph));
    });
    core.layout({ name: "preset", animate: false, fit: false }).run();
    core.zoom(zoom);
    core.pan(pan);
  }, [graph, loading]);

  useEffect(() => {
    const core = coreRef.current;
    if (!core) return;
    core.elements().removeClass("dimmed matched quality-hidden");
    const normalized = query.trim().toLocaleLowerCase();
    if (!normalized) return;
    core.elements().addClass("dimmed");
    core.nodes().filter((node) => String(node.data("label")).toLocaleLowerCase().includes(normalized)).addClass("matched");
  }, [query]);

  useEffect(() => {
    const core = coreRef.current;
    if (!core) return;
    core.elements().removeClass("quality-hidden");
    if (qualityFilter === "all") return;
    core.elements()
      .filter((element) => !matchesQualityFilter(element.data("properties") ?? {}, qualityFilter))
      .addClass("quality-hidden");
  }, [qualityFilter, graph]);

  return (
    <div className="graph-stage" data-testid="graph-canvas">
      <div className="graph-tools">
        <label className="graph-search">
          <Search size={15} />
          <span className="sr-only">搜索节点</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索节点" />
        </label>
        <label className="quality-filter">
          <span>质量筛选</span>
          <select
            aria-label="质量筛选"
            value={qualityFilter}
            onChange={(event) => setQualityFilter(event.target.value as QualityFilter)}
          >
            {Object.entries(QUALITY_FILTERS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
        <button className="tool-icon" aria-label="放大" onClick={() => coreRef.current?.zoom(coreRef.current.zoom() * 1.2)}><Plus size={16} /></button>
        <button className="tool-icon" aria-label="缩小" onClick={() => coreRef.current?.zoom(coreRef.current.zoom() / 1.2)}><Minus size={16} /></button>
        <button className="tool-icon" aria-label="适配画布" onClick={() => coreRef.current?.fit(undefined, 50)}><Maximize2 size={15} /></button>
      </div>
      <div className="graph-legend">
        {[...new Set(graph.nodes.map((node) => node.labels[0] ?? "实体"))].slice(0, 10).map((label) => (
          <span key={label}><i style={{ background: COLORS[label] ?? "#65736f" }} />{label}</span>
        ))}
      </div>
      <div ref={containerRef} className="cytoscape-canvas" />
      {loading ? <div className="graph-loading"><span /><span /><span /></div> : null}
      {!loading && graph.nodes.length === 0 ? <div className="graph-empty">当前图谱暂无节点</div> : null}
      {selected ? (
        <PropertyInspector
          node={selected}
          expanding={expanding}
          activeExpansionKeys={activeExpansionKeys}
          onClose={() => setSelected(null)}
          onExpand={onExpand}
        />
      ) : null}
      {selectedEdge ? (
        <EdgeInspector
          edge={selectedEdge}
          nodeIndex={nodeIndex}
          onClose={() => setSelectedEdge(null)}
        />
      ) : null}
    </div>
  );
}

function fieldLabel(key: string): string {
  const labels: Record<string, string> = {
    name: "原始关系名",
    fact: "事实文本",
    valid_at: "生效时间",
    invalid_at: "失效时间",
    reference_time: "参考时间",
    created_at: "创建时间",
    last_verified_at: "最近核验",
    data_as_of: "数据截至",
    current_validity: "当前有效性",
    confidence: "置信度",
    evidence_ids: "证据ID",
  };
  return labels[key] ?? key;
}

function formatValue(value: unknown): string {
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function matchesQualityFilter(properties: Record<string, unknown>, filter: QualityFilter): boolean {
  const bestGrade = String(properties.best_evidence_grade ?? properties["最高证据等级"] ?? properties.source_grade ?? properties["来源等级"] ?? "").toUpperCase();
  const confidence = String(properties.confidence ?? properties["置信度"] ?? "").toLowerCase();
  const needsValidation = booleanish(properties.requires_internal_validation ?? properties["是否需要内部验证"]);
  const weakEvidence = booleanish(properties.weak_evidence_support ?? properties["是否弱证据支撑"]);
  const searchOnly = booleanish(properties.search_only_evidence ?? properties["是否仅搜索结果支撑"]);
  if (filter === "high") return ["A", "A-"].includes(bestGrade) || confidence === "high";
  if (filter === "needs_validation") return needsValidation;
  if (filter === "weak") return weakEvidence;
  if (filter === "search_only") return searchOnly;
  return true;
}

function booleanish(value: unknown): boolean {
  if (value === true) return true;
  if (typeof value === "number") return value !== 0;
  if (typeof value === "string") return ["true", "1", "yes", "是"].includes(value.trim().toLowerCase());
  return false;
}
