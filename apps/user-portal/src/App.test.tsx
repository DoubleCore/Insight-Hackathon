import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const jsonResponse = (data: unknown) =>
  Promise.resolve(new Response(JSON.stringify(data), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  }));

describe("用户问答端", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(() => jsonResponse([])));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("以问答和可信度为唯一用户任务", async () => {
    render(<App />);

    expect(await screen.findByText("半导体产业知识助手")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "输入问题" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "发送问题" })).toBeDisabled();
    expect(screen.queryByText("图谱中心")).not.toBeInTheDocument();
    expect(screen.queryByText("召回链路")).not.toBeInTheDocument();
  });

  it("输入问题后允许发送", async () => {
    const user = userEvent.setup();
    render(<App />);

    const input = await screen.findByRole("textbox", { name: "输入问题" });
    await user.type(input, "AI/GPU 算力芯片有哪些龙头？");

    expect(screen.getByRole("button", { name: "发送问题" })).toBeEnabled();
  });

  it("可以切换 group 并在发送问题时携带当前 group", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/v1/groups")) return jsonResponse([
        { id: "semiconductor_dc_kg", label: "半导体图谱", is_default: true },
        { id: "robotics_kg", label: "机器人图谱", is_default: false },
      ]);
      if (url.endsWith("/api/v1/user/conversations")) {
        if (init?.method === "POST") {
          return jsonResponse({ id: "c-new", title: "查机器人产业链", created_at: "2026-07-15", updated_at: "2026-07-15" });
        }
        return jsonResponse([]);
      }
      if (url.endsWith("/api/v1/user/conversations/c-new/messages") && init?.method === "POST") {
        return jsonResponse({
          request_id: "r1",
          conversation_id: "c-new",
          user_message_id: "m1",
          status: "queued",
          events_url: "/events",
        });
      }
      return jsonResponse([]);
    });
    class FakeEventSource extends EventTarget {
      withCredentials = true;
      url: string;
      constructor(url: string) {
        super();
        this.url = url;
      }
      close() {}
    }
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("EventSource", FakeEventSource);
    render(<App />);

    const selector = await screen.findByLabelText("当前图谱 group");
    await user.selectOptions(selector, "robotics_kg");
    await user.type(screen.getByRole("textbox", { name: "输入问题" }), "查机器人产业链");
    await user.click(screen.getByRole("button", { name: "发送问题" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/user/conversations/c-new/messages"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ content: "查机器人产业链", group_id: "robotics_kg" }),
        }),
      ),
    );
  });

  it("加载会话并展示历史回答的四维可信度和引用", async () => {
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith("/api/v1/groups")) return jsonResponse([
        { id: "semiconductor_dc_kg", label: "半导体图谱", is_default: true },
      ]);
      if (url.endsWith("/api/v1/user/conversations")) return jsonResponse([
        { id: "c1", title: "NVIDIA 产业关系", created_at: "2026-07-15", updated_at: "2026-07-15" },
      ]);
      if (url.endsWith("/api/v1/user/conversations/c1/messages")) return jsonResponse([
        { id: "m1", role: "user", content: "NVIDIA 提供什么？", metadata: {}, created_at: "2026-07-15" },
        {
          id: "m2",
          role: "assistant",
          content: "NVIDIA 提供 GPU 加速芯片。[E-1]",
          created_at: "2026-07-15",
          metadata: {
            citations: [{ evidence_id: "E-1", title: "NVIDIA 官方资料", grade: "A", url: "https://example.com" }],
            trust_profile: {
              evidence: { key: "evidence", label: "证据质量", level: "high", explanation: "官方资料" },
              confidence: { key: "confidence", label: "事实置信度", level: "high", explanation: "高置信" },
              freshness: { key: "freshness", label: "时效性", level: "medium", explanation: "近期核验" },
              verification: { key: "verification", label: "核验状态", level: "high", explanation: "公开确认" },
            },
          },
        },
      ]);
      return jsonResponse([]);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByText("NVIDIA 提供 GPU 加速芯片。[E-1]")) .toBeInTheDocument();
    expect(screen.getByText("证据质量")).toBeInTheDocument();
    expect(screen.getByText("事实置信度")).toBeInTheDocument();
    expect(screen.getByText("时效性")).toBeInTheDocument();
    expect(screen.getByText("核验状态")).toBeInTheDocument();
    expect(screen.getByText("NVIDIA 官方资料")).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  });
});
