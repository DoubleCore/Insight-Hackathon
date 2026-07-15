import { describe, expect, it, vi } from "vitest";

import { createConversation, submitQuestion } from "./api";

describe("用户 API 客户端", () => {
  it("所有跨端口请求都携带匿名会话凭证", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "c1" }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ request_id: "r1" }), { status: 202 }));
    vi.stubGlobal("fetch", fetchMock);

    await createConversation("新会话");
    await submitQuestion("c1", "问题", "semiconductor_dc_kg");

    expect(fetchMock.mock.calls[0][1]).toMatchObject({ credentials: "include" });
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ credentials: "include" });
    expect(fetchMock.mock.calls[1][1]).toMatchObject({
      body: JSON.stringify({ content: "问题", group_id: "semiconductor_dc_kg" }),
    });
    vi.unstubAllGlobals();
  });

  it("提交问题时携带 group_id", async () => {
    const fetchMock = vi.fn(() => new Response(JSON.stringify({ request_id: "r1" }), {
      status: 202,
      headers: { "Content-Type": "application/json" },
    }));
    vi.stubGlobal("fetch", fetchMock);

    await submitQuestion("c1", "查机器人产业链", "robotics_kg");

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/user/conversations/c1/messages"),
      expect.objectContaining({
        body: JSON.stringify({ content: "查机器人产业链", group_id: "robotics_kg" }),
      }),
    );
    vi.unstubAllGlobals();
  });
});
