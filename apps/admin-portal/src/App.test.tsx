import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import GovernancePanel from "./GovernancePanel";

const cytoscapeState = vi.hoisted(() => ({
  nodeTapHandler: null as null | ((event: { target: { id: () => string } }) => void),
  edgeTapHandler: null as null | ((event: { target: { id: () => string } }) => void),
  contextTapHandler: null as null | ((event: { target: { id: () => string } }) => void),
  latestAddedElements: [] as unknown[],
  initCount: 0,
  destroyCount: 0,
}));

vi.mock("cytoscape", () => ({
  default: vi.fn((options?: { elements?: unknown[] }) => {
    cytoscapeState.initCount += 1;
    cytoscapeState.latestAddedElements = options?.elements ?? [];
    return {
      destroy: vi.fn(() => {
        cytoscapeState.destroyCount += 1;
      }),
      fit: vi.fn(),
      zoom: vi.fn((value?: number) => value ?? 1),
      pan: vi.fn((value?: { x: number; y: number }) => value ?? { x: 0, y: 0 }),
      center: vi.fn(),
      add: vi.fn((elements?: unknown[]) => {
        cytoscapeState.latestAddedElements = Array.isArray(elements) ? elements : [];
      }),
      batch: vi.fn((callback: () => void) => callback()),
      on: vi.fn((event: string, selector: string, handler: (event: { target: { id: () => string } }) => void) => {
        if (event === "tap" && selector === "node") cytoscapeState.nodeTapHandler = handler;
        if (event === "tap" && selector === "edge") cytoscapeState.edgeTapHandler = handler;
        if (event === "cxttap" && selector === "node") cytoscapeState.contextTapHandler = handler;
      }),
      elements: vi.fn(() => ({ removeClass: vi.fn(), addClass: vi.fn(), remove: vi.fn(), filter: vi.fn(() => ({ addClass: vi.fn() })) })),
      nodes: vi.fn(() => ({ filter: vi.fn(() => ({ addClass: vi.fn() })) })),
      layout: vi.fn(() => ({ run: vi.fn() })),
    };
  }),
}));

const jsonResponse = (data: unknown, status = 200) => Promise.resolve(
  new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } }),
);

function latestElementIds(): string[] {
  return cytoscapeState.latestAddedElements.map((element) => String((element as { data?: { id?: string } }).data?.id ?? ""));
}

afterEach(() => {
  cytoscapeState.nodeTapHandler = null;
  cytoscapeState.edgeTapHandler = null;
  cytoscapeState.contextTapHandler = null;
  cytoscapeState.latestAddedElements = [];
  cytoscapeState.initCount = 0;
  cytoscapeState.destroyCount = 0;
  window.localStorage.clear();
  vi.unstubAllGlobals();
});

describe("管理端", () => {
  it("治理数据刷新成功后清除之前的网络错误", async () => {
    const user = userEvent.setup();
    let sagaAttempts = 0;
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = String(input);
      if (url.includes("/api/v1/admin/governance/sagas")) {
        sagaAttempts += 1;
        if (sagaAttempts === 1) return Promise.reject(new Error("Failed to fetch"));
        return jsonResponse([]);
      }
      if (url.endsWith("/api/v1/admin/jobs")) return jsonResponse([]);
      return jsonResponse({});
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GovernancePanel groupId="semiconductor_dc_kg" communityCount={18} onCompleted={vi.fn()} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Failed to fetch");
    await user.click(screen.getByRole("button", { name: "刷新治理数据" }));

    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
  });

  it("图谱治理面板可以关闭并从右下角入口恢复", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = String(input);
      if (url.includes("/api/v1/admin/governance/sagas")) return jsonResponse([
        {
          uuid: "saga-1",
          name: "Layer 3 企业实体层 / 龙头企业判断",
          layer_id: 3,
          layer_name: "企业实体层",
          fact_set_name: "龙头企业判断",
          fact_set_description: "按产业环节整理代表企业。",
          summary: "",
          episode_count: 204,
        },
      ]);
      if (url.includes("/api/v1/admin/governance/communities")) return jsonResponse([
        {
          uuid: "community-1",
          name: "AI 算力产业链社区",
          summary: "",
          member_count: 18,
          representative_entities: [],
          created_at: null,
        },
      ]);
      if (url.endsWith("/api/v1/admin/jobs")) return jsonResponse([]);
      return jsonResponse({});
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GovernancePanel groupId="semiconductor_dc_kg" communityCount={18} onCompleted={vi.fn()} />);

    await user.click(await screen.findByRole("tab", { name: /结构聚类/ }));
    await user.click(screen.getByRole("button", { name: "关闭图谱治理" }));

    expect(screen.queryByLabelText("图谱治理")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "打开图谱治理" })).toHaveTextContent("事实时序 1");
    expect(screen.getByRole("button", { name: "打开图谱治理" })).toHaveTextContent("结构聚类 1");

    await user.click(screen.getByRole("button", { name: "打开图谱治理" }));

    expect(screen.getByLabelText("图谱治理")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /结构聚类/ })).toHaveAttribute("aria-selected", "true");
  });

  it("未登录时只展示管理口令入口", async () => {
    vi.stubGlobal("fetch", vi.fn(() => jsonResponse({ detail: "管理员未登录" }, 401)));
    render(<App />);

    expect(await screen.findByRole("heading", { name: "图谱管理台" })).toBeInTheDocument();
    expect(screen.getByLabelText("管理口令")).toBeInTheDocument();
    expect(screen.queryByText("图谱中心")).not.toBeInTheDocument();
  });

  it("登录态过期时从管理台退回登录页", async () => {
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith("/api/v1/admin/me")) return jsonResponse({ authenticated: true });
      if (url.includes("/api/v1/admin/graph/stats")) return jsonResponse({ detail: "管理员未登录" }, 401);
      if (url.includes("/api/v1/admin/graph/unified/root")) return jsonResponse({ nodes: [], edges: [] });
      if (url.includes("/api/v1/admin/governance/sagas")) return jsonResponse([]);
      if (url.includes("/api/v1/admin/governance/communities")) return jsonResponse([]);
      if (url.endsWith("/api/v1/admin/jobs")) return jsonResponse([]);
      return jsonResponse({});
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    expect(await screen.findByRole("heading", { name: "图谱管理台" })).toBeInTheDocument();
    expect(await screen.findByLabelText("管理口令")).toBeInTheDocument();
    expect(screen.queryByText("统一产业图谱")).not.toBeInTheDocument();
  });

  it("登录后展示两项主导航和统一图谱", async () => {
    const user = userEvent.setup();
    const graph = {
      nodes: [{ id: "n1", labels: ["企业"], properties: { "名称": "NVIDIA" } }],
      edges: [],
    };
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse({ detail: "管理员未登录" }, 401))
      .mockImplementationOnce(() => jsonResponse({ authenticated: true }))
      .mockImplementationOnce(() => jsonResponse({ industry_nodes: 1487, facts: 1376 }))
      .mockImplementation(() => jsonResponse(graph));
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    await user.type(await screen.findByLabelText("管理口令"), "admin");
    await user.click(screen.getByRole("button", { name: "进入管理台" }));

    expect(await screen.findByRole("button", { name: "图谱中心" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "链路观测" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "统一产业图谱" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "产业业务图" })).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "事实时序图" })).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Saga / Community" })).not.toBeInTheDocument();
    expect(await screen.findByTestId("graph-canvas")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/admin/graph/unified/root"),
      expect.any(Object),
    );
  });

  it("管理端可以进入产业扩展页面并按配置发起搜索", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/v1/admin/me")) return jsonResponse({ authenticated: true });
      if (url.endsWith("/api/v1/groups")) return jsonResponse([
        { id: "semiconductor_dc_kg", label: "半导体图谱", is_default: true },
        { id: "robotics_kg", label: "机器人图谱", is_default: false },
      ]);
      if (url.includes("/api/v1/admin/graph/stats")) return jsonResponse({});
      if (url.includes("/api/v1/admin/graph/unified/root")) return jsonResponse({ nodes: [], edges: [] });
      if (url.includes("/api/v1/admin/governance/sagas")) return jsonResponse([]);
      if (url.includes("/api/v1/admin/governance/communities")) return jsonResponse([]);
      if (url.endsWith("/api/v1/admin/jobs")) return jsonResponse([]);
      if (url.endsWith("/api/v1/industry-search") && init?.method === "POST") {
        return jsonResponse({
          group_id: "robotics_kg",
          industry_name: "机器人",
          query: "机器人 产业链",
          target_mode: "new_group",
          search_depth: "deep",
          relation_types: ["生产", "合作", "股权"],
          include_digital_china: true,
          manual_review_required: true,
          ingestion_status: "待人工审核",
          hits: [{ provider: "tavily", title: "机器人资料", url: "https://example.com", content: "机器人产业链资料" }],
          draft_episode_body: "产业名称：机器人\n- L4 细分产业链节点",
        });
      }
      if (url.endsWith("/api/v1/industry-search/pending-episode") && init?.method === "POST") {
        return jsonResponse({
          status: "pending_ingest",
          episode: {
            episode_id: "industry_extension::robotics_kg::机器人::20260715120000",
            episode_name: "机器人-公开资料扩展草稿",
            episode_body: "公开搜索草稿\n当前有效性：待人工审核",
            source: "text",
            source_description: "产业扩展公开搜索草稿 / 待人工审核",
            reference_time: "2026-07-15T12:00:00Z",
            group_id: "robotics_kg",
            saga_name: "Layer 2 资料证据层 / 产业扩展公开搜索草稿",
            layer_name: "资料证据层",
            claim_nature: "public_search_draft",
            requires_internal_validation: true,
            ingestion_status: "pending_ingest",
          },
        });
      }
      return jsonResponse({});
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "产业扩展" }));
    await user.click(screen.getByRole("button", { name: "新建 group" }));
    await user.type(screen.getByLabelText("新 group_id"), "robotics_kg");
    await user.type(screen.getByLabelText("产业名称"), "机器人");
    await user.click(screen.getByRole("button", { name: /深度/ }));
    await user.click(screen.getByLabelText("采购"));
    await user.click(screen.getByLabelText("销售"));
    await user.click(screen.getByLabelText("使用"));
    await user.click(screen.getByRole("button", { name: "搜索并生成草稿" }));

    expect(await screen.findByText(/产业名称：机器人/)).toBeInTheDocument();
    expect(screen.getByText("待人工审核")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "审核通过并生成待入库 Episode" }));
    expect((await screen.findAllByText("pending_ingest")).length).toBeGreaterThan(0);
    expect(screen.getByText("机器人-公开资料扩展草稿")).toBeInTheDocument();
    expect(screen.getAllByText(/公开搜索草稿/).length).toBeGreaterThan(0);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/industry-search"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          industry_name: "机器人",
          group_id: "semiconductor_dc_kg",
          target_mode: "new_group",
          new_group_id: "robotics_kg",
          search_depth: "deep",
          relation_types: ["生产", "合作", "竞争", "渠道"],
          include_digital_china: true,
          manual_review_required: true,
          providers: ["tavily", "bocha"],
        }),
      }),
    );
  });

  it("产业扩展没有公开来源时不允许生成待入库 Episode", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/v1/admin/me")) return jsonResponse({ authenticated: true });
      if (url.endsWith("/api/v1/groups")) return jsonResponse([
        { id: "semiconductor_dc_kg", label: "半导体图谱", is_default: true },
      ]);
      if (url.includes("/api/v1/admin/graph/stats")) return jsonResponse({});
      if (url.includes("/api/v1/admin/graph/unified/root")) return jsonResponse({ nodes: [], edges: [] });
      if (url.includes("/api/v1/admin/governance/sagas")) return jsonResponse([]);
      if (url.includes("/api/v1/admin/governance/communities")) return jsonResponse([]);
      if (url.endsWith("/api/v1/admin/jobs")) return jsonResponse([]);
      if (url.endsWith("/api/v1/industry-search") && init?.method === "POST") {
        return jsonResponse({
          group_id: "semiconductor_dc_kg",
          industry_name: "汽车电子",
          query: "汽车电子 产业链",
          target_mode: "existing_group",
          search_depth: "standard",
          relation_types: ["生产", "合作"],
          include_digital_china: true,
          manual_review_required: true,
          ingestion_status: "未检索到公开来源",
          hits: [],
          draft_episode_body: "产业名称：汽车电子\n公开资料来源：\n- 未检索到可用公开资料",
        });
      }
      return jsonResponse({});
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "产业扩展" }));
    await user.type(screen.getByLabelText("产业名称"), "汽车电子");
    await user.click(screen.getByRole("button", { name: "搜索并生成草稿" }));

    expect(await screen.findByText("没有搜索结果。可能是搜索密钥未配置，或当前关键词没有可用公开资料。")).toBeInTheDocument();
    expect(screen.getByText("没有公开来源时只能保留任务草稿，不能生成待入库 Episode。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "缺少公开来源，不能生成待入库 Episode" })).toBeDisabled();
  });

  it("单击只有一个展开分支的节点会直接展开", async () => {
    const rootGraph = {
      nodes: [
        {
          id: "taxonomy:l1:上游",
          labels: ["L1 产业层级"],
          properties: { "名称": "上游", name: "上游", level: 0, x: -230, y: 0, branch_options: ["hierarchy"] },
        },
      ],
      edges: [],
    };
    const expandedGraph = {
      nodes: [
        {
          id: "taxonomy:l2:上游|设计支撑",
          labels: ["L2 业务域"],
          properties: { "名称": "设计支撑", name: "设计支撑", level: 1, x: -230, y: 138 },
        },
      ],
      edges: [{ id: "e1", source: "taxonomy:l1:上游", target: "taxonomy:l2:上游|设计支撑", type: "包含", properties: {} }],
    };
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith("/api/v1/admin/me")) return jsonResponse({ authenticated: true });
      if (url.includes("/api/v1/admin/governance/sagas")) return jsonResponse([]);
      if (url.endsWith("/api/v1/admin/jobs")) return jsonResponse([]);
      if (url.includes("/graph/stats")) return jsonResponse({});
      if (url.includes("/api/v1/admin/graph/unified/root")) return jsonResponse(rootGraph);
      if (url.includes("/api/v1/admin/graph/unified/expand")) return jsonResponse(expandedGraph);
      return jsonResponse({});
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    await screen.findByTestId("graph-canvas");
    await waitFor(() => expect(cytoscapeState.nodeTapHandler).toBeTruthy());
    const initBeforeExpand = cytoscapeState.initCount;
    const destroyBeforeExpand = cytoscapeState.destroyCount;
    cytoscapeState.nodeTapHandler?.({ target: { id: () => "taxonomy:l1:上游" } });

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/admin/graph/unified/expand"),
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"branch":"hierarchy"'),
        }),
      ),
    );
    await waitFor(() => expect(cytoscapeState.initCount).toBe(initBeforeExpand));
    expect(cytoscapeState.destroyCount).toBe(destroyBeforeExpand);
  });

  it("管理端可以上传决策资料文本", async () => {
    const user = userEvent.setup();
    let decisionRequest: RequestInit | undefined;
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/v1/admin/me")) return jsonResponse({ authenticated: true });
      if (url.endsWith("/api/v1/groups")) return jsonResponse([
        { id: "semiconductor_dc_kg", label: "半导体图谱", is_default: true },
      ]);
      if (url.includes("/api/v1/admin/graph/stats")) return jsonResponse({});
      if (url.includes("/api/v1/admin/graph/unified/root")) return jsonResponse({ nodes: [], edges: [] });
      if (url.includes("/api/v1/admin/governance/sagas")) return jsonResponse([]);
      if (url.includes("/api/v1/admin/governance/communities")) return jsonResponse([]);
      if (url.endsWith("/api/v1/admin/jobs")) return jsonResponse([]);
      if (url.endsWith("/api/v1/admin/decision-signals") && init?.method === "POST") {
        decisionRequest = init;
        return jsonResponse({
          group_id: "semiconductor_dc_kg",
          saga: "决策信号层",
          evidence_id: "DS-20260715-ABC123",
          episode_uuid: "episode-1",
          title: "摩尔定律放缓",
          category: "technology",
          source_type: "text",
          source_url: null,
          content_preview: "资料类型：技术趋势\n标题：摩尔定律放缓",
        });
      }
      return jsonResponse({});
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "决策资料" }));
    await user.type(screen.getByLabelText("标题"), "摩尔定律放缓");
    await user.type(screen.getByLabelText("核心内容"), "摩尔定律放缓推动先进封装和 Chiplet。");
    await user.type(screen.getByLabelText("关键词"), "摩尔定律, Chiplet");
    await user.click(screen.getByRole("button", { name: "上传到决策信号层" }));

    expect(await screen.findByText("摩尔定律放缓")).toBeInTheDocument();
    expect(screen.getByText("semiconductor_dc_kg / 决策信号层")).toBeInTheDocument();
    expect(screen.getByText("episode-1")).toBeInTheDocument();
    expect(screen.getByText(/资料类型：技术趋势/)).toBeInTheDocument();
    expect(decisionRequest?.body).toBeInstanceOf(FormData);
    expect((decisionRequest?.headers as Record<string, string> | undefined)?.["Content-Type"]).toBeUndefined();
  });

  it("clicking the same single branch again collapses the expanded children", async () => {
    const rootGraph = {
      nodes: [
        {
          id: "root",
          labels: ["BusinessNode"],
          properties: { name: "Root", level: 0, branch_options: ["hierarchy"] },
        },
      ],
      edges: [],
    };
    const expandedGraph = {
      nodes: [
        {
          id: "child",
          labels: ["BusinessNode"],
          properties: { name: "Child", level: 1 },
        },
      ],
      edges: [{ id: "root-child", source: "root", target: "child", type: "contains", properties: {} }],
    };
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith("/api/v1/admin/me")) return jsonResponse({ authenticated: true });
      if (url.includes("/api/v1/admin/governance/sagas")) return jsonResponse([]);
      if (url.includes("/api/v1/admin/governance/communities")) return jsonResponse([]);
      if (url.endsWith("/api/v1/admin/jobs")) return jsonResponse([]);
      if (url.includes("/graph/stats")) return jsonResponse({});
      if (url.includes("/api/v1/admin/graph/unified/root")) return jsonResponse(rootGraph);
      if (url.includes("/api/v1/admin/graph/unified/expand")) return jsonResponse(expandedGraph);
      return jsonResponse({});
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    await screen.findByTestId("graph-canvas");
    await waitFor(() => expect(cytoscapeState.nodeTapHandler).toBeTruthy());
    cytoscapeState.nodeTapHandler?.({ target: { id: () => "root" } });
    await waitFor(() => expect(latestElementIds()).toContain("child"));

    cytoscapeState.nodeTapHandler?.({ target: { id: () => "root" } });

    await waitFor(() => expect(latestElementIds()).not.toContain("child"));
    expect(fetchMock.mock.calls.filter(([input]) => String(input).includes("/api/v1/admin/graph/unified/expand"))).toHaveLength(1);
  });

  it("right clicking a node collapses children expanded from that node", async () => {
    const rootGraph = {
      nodes: [
        {
          id: "root",
          labels: ["BusinessNode"],
          properties: { name: "Root", level: 0, branch_options: ["hierarchy"] },
        },
      ],
      edges: [],
    };
    const expandedGraph = {
      nodes: [
        {
          id: "child",
          labels: ["BusinessNode"],
          properties: { name: "Child", level: 1 },
        },
      ],
      edges: [{ id: "root-child", source: "root", target: "child", type: "contains", properties: {} }],
    };
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith("/api/v1/admin/me")) return jsonResponse({ authenticated: true });
      if (url.includes("/api/v1/admin/governance/sagas")) return jsonResponse([]);
      if (url.includes("/api/v1/admin/governance/communities")) return jsonResponse([]);
      if (url.endsWith("/api/v1/admin/jobs")) return jsonResponse([]);
      if (url.includes("/graph/stats")) return jsonResponse({});
      if (url.includes("/api/v1/admin/graph/unified/root")) return jsonResponse(rootGraph);
      if (url.includes("/api/v1/admin/graph/unified/expand")) return jsonResponse(expandedGraph);
      return jsonResponse({});
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    await screen.findByTestId("graph-canvas");
    await waitFor(() => expect(cytoscapeState.nodeTapHandler).toBeTruthy());
    await waitFor(() => expect(cytoscapeState.contextTapHandler).toBeTruthy());
    cytoscapeState.nodeTapHandler?.({ target: { id: () => "root" } });
    await waitFor(() => expect(latestElementIds()).toContain("child"));

    cytoscapeState.contextTapHandler?.({ target: { id: () => "root" } });

    await waitFor(() => expect(latestElementIds()).not.toContain("child"));
  });

  it("企业节点可以展开证据并提供质量筛选器", async () => {
    const rootGraph = {
      nodes: [
        {
          id: "company:NVIDIA",
          labels: ["企业"],
          properties: { "名称": "NVIDIA", name: "NVIDIA", level: 5, branch_options: ["facts", "evidence"] },
        },
      ],
      edges: [],
    };
    const evidenceGraph = {
      nodes: [
        {
          id: "evidence:E4-001",
          labels: ["证据"],
          properties: { "名称": "E4-001", "来源标题": "NVIDIA 与 TSMC 代工资料", "来源等级": "A", level: 8 },
        },
      ],
      edges: [
        {
          id: "company:NVIDIA->evidence:E4-001",
          source: "company:NVIDIA",
          target: "evidence:E4-001",
          type: "证据支持",
          properties: { display_label: "证据支持" },
        },
      ],
    };
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/v1/admin/me")) return jsonResponse({ authenticated: true });
      if (url.includes("/api/v1/admin/governance/sagas")) return jsonResponse([]);
      if (url.includes("/api/v1/admin/governance/communities")) return jsonResponse([]);
      if (url.endsWith("/api/v1/admin/jobs")) return jsonResponse([]);
      if (url.includes("/graph/stats")) return jsonResponse({});
      if (url.includes("/api/v1/admin/graph/unified/root")) return jsonResponse(rootGraph);
      if (url.includes("/api/v1/admin/graph/unified/expand") && init?.method === "POST") {
        return jsonResponse(evidenceGraph);
      }
      return jsonResponse({});
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    await screen.findByTestId("graph-canvas");
    expect(screen.getByLabelText("质量筛选")).toBeInTheDocument();
    await waitFor(() => expect(cytoscapeState.nodeTapHandler).toBeTruthy());
    cytoscapeState.nodeTapHandler?.({ target: { id: () => "company:NVIDIA" } });

    await userEvent.click(await screen.findByRole("button", { name: "展开证据" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/admin/graph/unified/expand"),
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"branch":"evidence"'),
        }),
      ),
    );
  });

  it("企业节点展示独立的神州数码业务关系卡片", async () => {
    const rootGraph = {
      nodes: [
        {
          id: "company:浪潮信息",
          labels: ["企业"],
          properties: {
            "名称": "浪潮信息",
            name: "浪潮信息",
            level: 5,
            branch_options: ["business", "digital_china", "facts"],
            digital_china_relationship_status: "confirmed_public_relationship",
            digital_china_relationship_type: "联合发布AI一体机解决方案",
            digital_china_relationship_basis: "神州数码官网新闻显示双方联合发布AI一体机解决方案。",
            digital_china_evidence_ids: ["DC-008"],
            digital_china_confidence: "high",
            requires_internal_validation: true,
            digital_china_limitations: "公开资料不能等同于内部客户关系。",
          },
        },
      ],
      edges: [],
    };
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith("/api/v1/admin/me")) return jsonResponse({ authenticated: true });
      if (url.includes("/api/v1/admin/governance/sagas")) return jsonResponse([]);
      if (url.includes("/api/v1/admin/governance/communities")) return jsonResponse([]);
      if (url.endsWith("/api/v1/admin/jobs")) return jsonResponse([]);
      if (url.includes("/graph/stats")) return jsonResponse({});
      if (url.includes("/api/v1/admin/graph/unified/root")) return jsonResponse(rootGraph);
      return jsonResponse({ nodes: [], edges: [] });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    await screen.findByTestId("graph-canvas");
    await waitFor(() => expect(cytoscapeState.nodeTapHandler).toBeTruthy());
    cytoscapeState.nodeTapHandler?.({ target: { id: () => "company:浪潮信息" } });

    expect(await screen.findByText("神州数码业务关系")).toBeInTheDocument();
    expect(screen.getByText("公开确认")).toBeInTheDocument();
    expect(screen.getByText("联合发布AI一体机解决方案")).toBeInTheDocument();
    expect(screen.getByText("神州数码官网新闻显示双方联合发布AI一体机解决方案。")).toBeInTheDocument();
    expect(screen.getByText("DC-008")).toBeInTheDocument();
    expect(screen.getByText("需要内部验证")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "展开神州数码关系" })).toBeInTheDocument();
  });

  it("链路观测展示召回切面、阶段和 LLM 调用", async () => {
    const user = userEvent.setup();
    const trace = {
      id: "run-1",
      conversation_id: "c1",
      trace_id: "0123456789abcdef0123456789abcdef",
      query: "NVIDIA 和 TSMC 有什么关系？",
      status: "completed",
      answer: "存在晶圆代工关系",
      error: null,
      created_at: "2026-07-15T10:00:00Z",
      updated_at: "2026-07-15T10:00:03Z",
      stages: [
        {
          name: "深度检索",
          status: "completed",
          algorithm: "cross_encoder",
          detail: { selected_count: 8, candidate_count: 24, fallback_reason: "reranker-normal" },
          duration_ms: 820,
        },
        { name: "证据门控", status: "completed", detail: { supported: true, citation_count: 3 } },
      ],
      retrieval_slices: [
        {
          id: "v",
          name: "vector",
          algorithm: "vector",
          query: "NVIDIA TSMC",
          status: "completed",
          started_at: "2026-07-15T10:00:00.000Z",
          completed_at: "2026-07-15T10:00:00.080Z",
          candidates: [],
        },
        { id: "b", name: "bm25", algorithm: "bm25", query: "NVIDIA TSMC", status: "completed", duration_ms: 70, candidates: [] },
        { id: "g", name: "bfs", algorithm: "bfs", query: "NVIDIA TSMC", status: "completed", duration_ms: 60, candidates: [] },
        { id: "l", name: "lexical", algorithm: "lexical", query: "NVIDIA TSMC", status: "completed", duration_ms: 50, candidates: [] },
        {
          id: "f",
          name: "重排",
          algorithm: "cross_encoder",
          query: "NVIDIA TSMC",
          status: "completed",
          duration_ms: 420,
          metadata: { fallback_reason: "reranker-normal" },
          candidates: [
            {
              id: "e1",
              title: "晶圆代工",
              content: "TSMC 为 NVIDIA 提供晶圆代工。",
              score: 0.98,
              algorithm: "cross_encoder",
              selected: true,
              evidence_ids: ["E4-001"],
              rank: 1,
              object_type: "edge",
              source: "NVIDIA",
              target: "TSMC",
              relation: "FOUNDRY_SUPPLIER",
              confidence: "high",
              evidence_level: "public",
              last_verified_at: "2026-07-01",
              verification_status: "confirmed_public",
              rerank_score: 0.991,
            },
            {
              id: "e2",
              title: "metadata fallback",
              content: "metadata-only candidate",
              score: 0.76,
              algorithm: "cross_encoder",
              selected: false,
              rank: 2,
              metadata: {
                object_type: "fallback-edge",
                source: "GPU",
                target: "CoWoS",
                relation: "USES",
                confidence: "metadata-high",
                evidence_level: "metadata-public",
                last_verified_at: "2026-07-02",
                verification_status: "metadata-confirmed",
                rerank_score: 0.887,
              },
            },
            {
              id: "e3",
              title: "字段缺失",
              content: "missing metadata candidate",
              score: 0.5,
              algorithm: "cross_encoder",
              selected: false,
              rank: 3,
            },
          ],
        },
      ],
      llm_calls: [
        { id: "llm-1", query_run_id: "run-1", model: "deepseek-ai/DeepSeek-V3.2", purpose: "answer", status: "completed", request_tokens: 120, response_tokens: 40, latency_ms: 630, request: {}, response: {} },
      ],
    };
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith("/api/v1/admin/me")) return jsonResponse({ authenticated: true });
      if (url.endsWith("/api/v1/admin/traces/run-1")) return jsonResponse(trace);
      if (url.endsWith("/api/v1/admin/traces")) return jsonResponse([{ ...trace, stages: undefined, retrieval_slices: undefined, llm_calls: undefined }]);
      if (url.includes("/graph/stats")) return jsonResponse({});
      return jsonResponse({ nodes: [], edges: [] });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "链路观测" }));

    expect((await screen.findAllByText("NVIDIA 和 TSMC 有什么关系？")).length).toBeGreaterThan(0);
    expect(screen.getByRole("tab", { name: /^向量召回/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /^BM25 召回/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /^图遍历/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /^词面补召回/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /^Cross Encoder/ })).toBeInTheDocument();
    expect(screen.getByText("TSMC 为 NVIDIA 提供晶圆代工。")).toBeInTheDocument();
    expect(screen.getByText("总耗时")).toBeInTheDocument();
    expect(screen.getByText("3,000 ms")).toBeInTheDocument();
    expect(screen.getByText("trace_id 0123456789abcdef0123456789abcdef")).toBeInTheDocument();
    expect(screen.getByText("总 token")).toBeInTheDocument();
    expect(screen.getByText("selected_count")).toBeInTheDocument();
    expect(screen.getByText("candidate_count")).toBeInTheDocument();
    expect(screen.getAllByText("reranker-normal").length).toBeGreaterThan(0);
    expect(screen.getByText("edge")).toBeInTheDocument();
    expect(screen.getByText("NVIDIA -> TSMC")).toBeInTheDocument();
    expect(screen.getByText("confirmed_public")).toBeInTheDocument();
    expect(screen.getByText("2026-07-01")).toBeInTheDocument();
    expect(screen.getAllByText("0.991").length).toBeGreaterThan(0);
    expect(screen.getByText("fallback-edge")).toBeInTheDocument();
    expect(screen.getByText("GPU -> CoWoS")).toBeInTheDocument();
    expect(screen.getByText(/metadata-high/)).toBeInTheDocument();
    expect(screen.getByText(/metadata-confirmed/)).toBeInTheDocument();
    expect(screen.getAllByText("-").length).toBeGreaterThan(0);
    expect(screen.getByText("deepseek-ai/DeepSeek-V3.2")).toBeInTheDocument();
  });

  it("治理视图可以总结 Saga 并重建 Community", async () => {
    const user = userEvent.setup();
    const job = {
      id: "job-1",
      job_type: "summarize_saga",
      status: "completed",
      payload: { saga_id: "saga-1" },
      result: { summary: "AI 算力产业链摘要" },
      error: null,
      created_at: "2026-07-15T10:00:00Z",
      updated_at: "2026-07-15T10:00:01Z",
    };
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/v1/admin/me")) return jsonResponse({ authenticated: true });
      if (url.includes("/sagas/saga-1/summarize") && init?.method === "POST") {
        return jsonResponse(job, 202);
      }
      if (url.includes("/communities/rebuild") && init?.method === "POST") {
        return jsonResponse({ ...job, id: "job-2", job_type: "rebuild_communities" }, 202);
      }
      if (url.includes("/api/v1/admin/governance/sagas")) return jsonResponse([
        {
          uuid: "saga-1",
          name: "stage3_leadership",
          summary: "",
          episode_count: 204,
          last_summarized_at: null,
          last_summarized_episode_valid_at: null,
        },
      ]);
      if (url.includes("/api/v1/admin/governance/communities")) return jsonResponse([
        {
          uuid: "community-1",
          name: "AI 算力产业链社区",
          summary: "围绕 GPU、HBM、晶圆代工形成的结构聚类。",
          member_count: 18,
          representative_entities: ["NVIDIA", "TSMC", "SK hynix"],
          created_at: "2026-07-15T10:00:00Z",
        },
      ]);
      if (url.endsWith("/api/v1/admin/jobs")) return jsonResponse([]);
      if (url.includes("/api/v1/admin/jobs/job-")) return jsonResponse(job);
      if (url.includes("/graph/stats")) return jsonResponse({ sagas: 5, communities: 0 });
      return jsonResponse({ nodes: [], edges: [] });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    await screen.findByTestId("graph-canvas");
    expect(await screen.findByText("Layer 3")).toBeInTheDocument();
    expect(screen.getByText("企业实体层")).toBeInTheDocument();
    expect(screen.getByText("龙头企业判断")).toBeInTheDocument();
    expect(screen.getAllByText("204 条事件").length).toBeGreaterThan(0);
    expect(screen.getByRole("tab", { name: /事实时序/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /结构聚类/ })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "总结 龙头企业判断" }));
    await user.click(screen.getByRole("tab", { name: /结构聚类/ }));
    expect(screen.getAllByText("结构聚类").length).toBeGreaterThan(0);
    expect(screen.getByText("AI 算力产业链社区")).toBeInTheDocument();
    expect(screen.getByText("18 个成员")).toBeInTheDocument();
    expect(screen.getByText("NVIDIA")).toBeInTheDocument();
    expect(screen.getByText("TSMC")).toBeInTheDocument();
    const rebuildButton = screen.getByRole("button", { name: "重建结构聚类" });
    await waitFor(() => expect(rebuildButton).toBeEnabled());
    await user.click(rebuildButton);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/sagas/saga-1/summarize"),
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/communities/rebuild"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("刷新页面后恢复运行中治理任务并禁用重复写操作", async () => {
    const user = userEvent.setup();
    const runningJob = {
      id: "job-running",
      job_type: "rebuild_communities",
      status: "running",
      payload: {},
      result: { progress: 50, message: "正在聚类" },
      created_at: "2026-07-15T10:00:00Z",
      updated_at: "2026-07-15T10:00:01Z",
    };
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith("/api/v1/admin/me")) return jsonResponse({ authenticated: true });
      if (url.includes("/api/v1/admin/governance/sagas")) return jsonResponse([]);
      if (url.endsWith("/api/v1/admin/jobs")) return jsonResponse([runningJob]);
      if (url.endsWith("/api/v1/admin/jobs/job-running")) return new Promise(() => undefined);
      if (url.includes("/graph/stats")) return jsonResponse({ communities: 0 });
      return jsonResponse({ nodes: [], edges: [] });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    await screen.findByTestId("graph-canvas");
    await user.click(await screen.findByRole("tab", { name: /结构聚类/ }));
    const rebuild = await screen.findByRole("button", { name: "重建结构聚类" });

    expect(rebuild).toBeDisabled();
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/admin/jobs/job-running"),
        expect.any(Object),
      ),
    );
  });
});
