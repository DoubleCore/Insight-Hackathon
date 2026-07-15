# Thin Industry Search Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给用户端和管理端增加可切换 `group_id` 的工作区选择器，并增加一个很薄的产业搜索层，用 Bocha / Tavily 搜索公开资料，返回结构化资料草稿，后续继续复用现有图谱展示、问答、治理和 Graphiti 入库能力。

**Architecture:** 不做复杂 ingestion 平台，不做自动审核流。后端只新增 group 上下文读取、group 列表接口、产业搜索接口和一个可选的手动 episode 写入薄封装；现有问答、图谱展示、saga/community 都通过 `group_id` 参数复用已有服务。前端只加左下角 group 选择器和一个“产业搜索”小面板，搜索结果先作为草稿展示。

**Tech Stack:** FastAPI, SQLite repository, Neo4j/Graphiti, httpx, React/Vite, Vitest, pytest, Tavily Search API, Bocha Web Search API.

---

## Scope Guard

本计划刻意不做以下内容：

- 不做多租户权限系统。
- 不做复杂资料审核工作台。
- 不做自动网页爬虫队列。
- 不直接把搜索结果自动写入正式图谱。
- 不改 Graphiti 核心库。

v1 只做：

- 左下角 `group_id` 可切换。
- 后端接口支持请求级 `group_id`。
- Bocha / Tavily 搜索聚合。
- 搜索结果整理成产业链资料草稿。
- 可选：管理员手动确认后调用 Graphiti `add_episode()` 写入一条资料。

参考资料：

- Tavily 官方文档确认 `/search` 是 Web Search 入口，认证使用 API key，body 至少包含 `query`，并支持 `search_depth`。
- Bocha 官方开放平台提供 Web Search API / Semantic Reranker API，适合中文公开资料搜索。Bocha 具体 endpoint 在 v1 中做成配置项，不在代码里写死。

---

## File Map

后端：

- `apps/api-server/app/schemas.py`
  - 增加 `GroupSummary`、`IndustrySearchRequest`、`IndustrySearchResult`、`ManualEpisodeRequest` 等轻量 schema。
- `apps/api-server/app/config.py`
  - 增加 Tavily / Bocha API key 和 Bocha search URL 配置。
- `apps/api-server/app/services/group_context.py`
  - 新建：统一读取、校验请求里的 `group_id`。
- `apps/api-server/app/services/web_search.py`
  - 新建：统一封装 Tavily / Bocha 搜索，返回标准 `WebSearchHit`。
- `apps/api-server/app/routers/groups.py`
  - 新建：`GET /api/v1/groups`，返回已有 group。
- `apps/api-server/app/routers/industry_search.py`
  - 新建：`POST /api/v1/industry-search`，返回搜索结果和资料草稿。
- `apps/api-server/app/routers/admin.py`
  - 修改：管理端图谱、治理接口支持 `group_id` query 参数。
- `apps/api-server/app/routers/user.py`
  - 修改：用户问答接口支持 `group_id`，并按 group 缓存 pipeline。
- `apps/api-server/app/main.py`
  - 注册新 router；把单例 service 改成按 group 缓存。
- `apps/api-server/tests/test_groups.py`
  - 新增 group 接口和 group 校验测试。
- `apps/api-server/tests/test_industry_search.py`
  - 新增搜索聚合测试。

前端共享：

- `apps/admin-portal/src/api.ts`
- `apps/user-portal/src/api.ts`
  - 请求支持传 `group_id`。

管理端：

- `apps/admin-portal/src/App.tsx`
  - 左下角显示 group selector。
  - GraphCenter / TraceMonitor / GovernancePanel 读取当前 group。
- `apps/admin-portal/src/IndustrySearchPanel.tsx`
  - 新建：产业搜索小面板。
- `apps/admin-portal/src/types.ts`
  - 增加 group/search 类型。
- `apps/admin-portal/src/styles.css`
  - 增加 group selector 和 search panel 样式。
- `apps/admin-portal/src/App.test.tsx`
  - 增加 group 切换和搜索面板测试。

用户端：

- `apps/user-portal/src/App.tsx`
  - 左下角显示 group selector。
- `apps/user-portal/src/api.ts`
  - 问答提交携带当前 group。
- `apps/user-portal/src/types.ts`
  - 增加 group 类型。
- `apps/user-portal/src/App.test.tsx`
  - 增加 group 切换后提交问题携带 group 的测试。

---

### Task 1: 后端 Group 上下文薄封装

**Files:**
- Create: `apps/api-server/app/services/group_context.py`
- Create: `apps/api-server/app/routers/groups.py`
- Modify: `apps/api-server/app/schemas.py`
- Modify: `apps/api-server/app/main.py`
- Test: `apps/api-server/tests/test_groups.py`

- [ ] **Step 1: 增加 schema**

在 `apps/api-server/app/schemas.py` 增加：

```python
class GroupSummary(BaseModel):
    id: str
    label: str | None = None
    is_default: bool = False
```

- [ ] **Step 2: 新建 group context helper**

创建 `apps/api-server/app/services/group_context.py`：

```python
from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException, Request

GROUP_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$")


def validate_group_id(value: str) -> str:
    normalized = value.strip()
    if not GROUP_ID_PATTERN.fullmatch(normalized):
        raise HTTPException(status_code=422, detail="group_id 只能包含字母、数字、下划线和短横线，长度 2-64")
    return normalized


def request_group_id(request: Request, group_id: str | None = None) -> str:
    if group_id is not None and group_id.strip():
        return validate_group_id(group_id)
    header_value = request.headers.get("X-Graph-Group")
    if header_value:
        return validate_group_id(header_value)
    return request.app.state.settings.group_id


async def list_existing_groups(driver: Any, default_group_id: str) -> list[str]:
    query = """
    CALL {
      MATCH (n:Entity) WHERE n.group_id IS NOT NULL RETURN n.group_id AS group_id
      UNION
      MATCH (n:Episodic) WHERE n.group_id IS NOT NULL RETURN n.group_id AS group_id
      UNION
      MATCH (n:Saga) WHERE n.group_id IS NOT NULL RETURN n.group_id AS group_id
      UNION
      MATCH (n:Community) WHERE n.group_id IS NOT NULL RETURN n.group_id AS group_id
    }
    RETURN DISTINCT group_id ORDER BY group_id
    """
    records, _, _ = await driver.execute_query(query, routing_="r")
    groups = [str(record["group_id"]) for record in records if record.get("group_id")]
    if default_group_id not in groups:
        groups.insert(0, default_group_id)
    return groups
```

- [ ] **Step 3: 新增 groups router**

创建 `apps/api-server/app/routers/groups.py`：

```python
from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas import GroupSummary
from app.services.group_context import list_existing_groups

router = APIRouter(prefix="/api/v1/groups", tags=["group"])


@router.get("", response_model=list[GroupSummary])
async def groups(request: Request) -> list[GroupSummary]:
    default_group = request.app.state.settings.group_id
    graph_service = request.app.state.graph_service_by_group.get(default_group)
    if graph_service is None:
        from app.services.graph import Neo4jGraphService

        graph_service = Neo4jGraphService.from_settings(request.app.state.settings)
        request.app.state.graph_service_by_group[default_group] = graph_service
    group_ids = await list_existing_groups(graph_service.driver, default_group)
    return [
        GroupSummary(id=item, label=item, is_default=item == default_group)
        for item in group_ids
    ]
```

- [ ] **Step 4: 注册 router 和 service cache**

在 `apps/api-server/app/main.py`：

```python
from app.routers import admin, groups, industry_search, user
```

在 `create_app()` 初始化 state：

```python
application.state.qa_pipeline_by_group = {}
application.state.graph_service_by_group = {}
application.state.unified_graph_service_by_group = {}
application.state.governance_service_by_group = {}
```

注册 router：

```python
application.include_router(groups.router)
```

- [ ] **Step 5: 写测试**

创建 `apps/api-server/tests/test_groups.py`：

```python
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from tests.test_api import make_settings


def test_groups_returns_default_group_when_graph_has_no_groups(tmp_path: Path) -> None:
    from app.main import create_app

    app = create_app(make_settings(tmp_path / "groups.db"))
    with TestClient(app) as client:
        response = client.get("/api/v1/groups")

    assert response.status_code == 200
    assert response.json()[0]["id"] == "semiconductor_dc_kg"
    assert response.json()[0]["is_default"] is True
```

- [ ] **Step 6: 运行测试**

Run:

```powershell
$env:PYTHONUTF8='1'
F:\panda\miniconda\conda\envs\task1-semiconductor-ui\python.exe -m pytest apps/api-server/tests/test_groups.py -q
```

Expected: `1 passed`

---

### Task 2: 让现有用户/管理接口按 group 复用服务

**Files:**
- Modify: `apps/api-server/app/routers/user.py`
- Modify: `apps/api-server/app/routers/admin.py`
- Modify: `apps/api-server/app/main.py`
- Test: `apps/api-server/tests/test_api.py`

- [ ] **Step 1: 修改用户提交问题 schema**

在 `apps/api-server/app/routers/user.py` 的 `MessageCreate` 增加：

```python
class MessageCreate(BaseModel):
    content: str
    group_id: str | None = None
```

- [ ] **Step 2: 按 group 缓存 pipeline**

把 `_pipeline(request)` 改成：

```python
async def _pipeline(request: Request, group_id: str):
    pipeline = request.app.state.qa_pipeline_by_group.get(group_id)
    if pipeline is not None:
        return pipeline
    async with request.app.state.pipeline_lock:
        pipeline = request.app.state.qa_pipeline_by_group.get(group_id)
        if pipeline is None:
            from dataclasses import replace
            from app.services.runtime import build_default_pipeline

            settings = replace(request.app.state.settings, group_id=group_id)
            pipeline = build_default_pipeline(settings, request.app.state.repository)
            request.app.state.qa_pipeline_by_group[group_id] = pipeline
        return pipeline
```

- [ ] **Step 3: submit_message 使用请求 group**

在 `submit_message()` 中：

```python
from app.services.group_context import request_group_id

group_id = request_group_id(request, payload.group_id)
```

创建 run 时把 group 写入阶段 detail 或 query metadata 不改表结构；最小实现只传入 `_execute_request`：

```python
background_tasks.add_task(
    _execute_request, request, conversation_id, run["id"], payload.content, group_id
)
```

把 `_execute_request` 签名改成：

```python
async def _execute_request(
    request: Request,
    conversation_id: str,
    request_id: str,
    question: str,
    group_id: str,
) -> None:
```

内部使用：

```python
pipeline = await _pipeline(request, group_id)
```

- [ ] **Step 4: 管理图谱接口支持 query group_id**

在 `apps/api-server/app/routers/admin.py` 的图谱相关接口参数加：

```python
group_id: str | None = Query(default=None)
```

然后：

```python
from dataclasses import replace
from app.services.group_context import request_group_id

resolved_group_id = request_group_id(request, group_id)
settings = replace(request.app.state.settings, group_id=resolved_group_id)
```

按 `resolved_group_id` 缓存 `Neo4jGraphService`、`UnifiedGraphService`、`GovernanceService`。不要修改全局 `settings.group_id`。

- [ ] **Step 5: 写测试**

在 `apps/api-server/tests/test_api.py` 增加：

```python
def test_user_question_accepts_group_id_in_payload(tmp_path: Path, monkeypatch) -> None:
    from app.main import create_app
    from app.routers import user as user_router

    app = create_app(make_settings(tmp_path / "group-question.db"))
    seen_groups: list[str] = []

    async def fake_execute(request, conversation_id, request_id, question, group_id):
        seen_groups.append(group_id)
        request.app.state.repository.update_query_run(request_id, status="completed", answer="ok")

    monkeypatch.setattr(user_router, "_execute_request", fake_execute)

    with TestClient(app) as client:
        conversation = client.post("/api/v1/user/conversations", json={"title": "t"}).json()
        response = client.post(
            f"/api/v1/user/conversations/{conversation['id']}/messages",
            json={"content": "查一下机器人产业链", "group_id": "robotics_kg"},
        )

    assert response.status_code == 202
    assert seen_groups == ["robotics_kg"]
```

- [ ] **Step 6: 运行测试**

Run:

```powershell
$env:PYTHONUTF8='1'
F:\panda\miniconda\conda\envs\task1-semiconductor-ui\python.exe -m pytest apps/api-server/tests/test_api.py::test_user_question_accepts_group_id_in_payload -q
```

Expected: `1 passed`

---

### Task 3: 增加 Bocha / Tavily 薄搜索层

**Files:**
- Modify: `apps/api-server/app/config.py`
- Modify: `apps/api-server/app/schemas.py`
- Create: `apps/api-server/app/services/web_search.py`
- Create: `apps/api-server/app/routers/industry_search.py`
- Modify: `apps/api-server/app/main.py`
- Test: `apps/api-server/tests/test_industry_search.py`

- [ ] **Step 1: 增加配置**

在 `Settings` 增加：

```python
tavily_api_key: str = ""
bocha_api_key: str = ""
bocha_search_url: str = ""
```

在 `from_environment()` 增加：

```python
tavily_api_key=env.get("TAVILY_API_KEY", ""),
bocha_api_key=env.get("BOCHA_API_KEY", ""),
bocha_search_url=env.get("BOCHA_SEARCH_URL", ""),
```

- [ ] **Step 2: 增加搜索 schema**

在 `apps/api-server/app/schemas.py` 增加：

```python
class IndustrySearchRequest(BaseModel):
    industry_name: str = Field(min_length=1, max_length=80)
    group_id: str | None = None
    providers: list[Literal["tavily", "bocha"]] = Field(default_factory=lambda: ["tavily", "bocha"])
    max_results: int = Field(default=8, ge=1, le=20)
    include_digital_china: bool = True


class IndustrySearchHit(BaseModel):
    provider: str
    title: str
    url: str
    content: str = ""
    published_at: str | None = None
    score: float | None = None


class IndustrySearchResult(BaseModel):
    group_id: str
    industry_name: str
    query: str
    hits: list[IndustrySearchHit]
    draft_episode_body: str
```

- [ ] **Step 3: 新建 web_search service**

创建 `apps/api-server/app/services/web_search.py`：

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings


@dataclass(slots=True)
class WebSearchHit:
    provider: str
    title: str
    url: str
    content: str = ""
    published_at: str | None = None
    score: float | None = None


class WebSearchService:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.client = client or httpx.AsyncClient(timeout=20)
        self._owned_client = client is None

    async def close(self) -> None:
        if self._owned_client:
            await self.client.aclose()

    async def search(
        self,
        query: str,
        *,
        providers: list[str],
        max_results: int,
    ) -> list[WebSearchHit]:
        results: list[WebSearchHit] = []
        if "tavily" in providers and self.settings.tavily_api_key:
            results.extend(await self._search_tavily(query, max_results=max_results))
        if "bocha" in providers and self.settings.bocha_api_key and self.settings.bocha_search_url:
            results.extend(await self._search_bocha(query, max_results=max_results))
        return _dedupe_hits(results)[:max_results]

    async def _search_tavily(self, query: str, *, max_results: int) -> list[WebSearchHit]:
        response = await self.client.post(
            "https://api.tavily.com/search",
            headers={
                "Authorization": f"Bearer {self.settings.tavily_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "search_depth": "basic",
                "max_results": max_results,
            },
        )
        response.raise_for_status()
        payload = response.json()
        return [
            WebSearchHit(
                provider="tavily",
                title=str(item.get("title") or ""),
                url=str(item.get("url") or ""),
                content=str(item.get("content") or ""),
                score=float(item["score"]) if item.get("score") is not None else None,
            )
            for item in payload.get("results", [])
            if item.get("url")
        ]

    async def _search_bocha(self, query: str, *, max_results: int) -> list[WebSearchHit]:
        response = await self.client.post(
            self.settings.bocha_search_url,
            headers={
                "Authorization": f"Bearer {self.settings.bocha_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "count": max_results,
            },
        )
        response.raise_for_status()
        payload = response.json()
        raw_items = payload.get("data", {}).get("webPages", {}).get("value", [])
        if not isinstance(raw_items, list):
            raw_items = payload.get("results", [])
        return [
            WebSearchHit(
                provider="bocha",
                title=str(item.get("name") or item.get("title") or ""),
                url=str(item.get("url") or ""),
                content=str(item.get("snippet") or item.get("summary") or item.get("content") or ""),
                published_at=item.get("datePublished") or item.get("published_at"),
            )
            for item in raw_items
            if isinstance(item, dict) and item.get("url")
        ]


def _dedupe_hits(hits: list[WebSearchHit]) -> list[WebSearchHit]:
    seen: set[str] = set()
    deduped: list[WebSearchHit] = []
    for hit in hits:
        if hit.url in seen:
            continue
        seen.add(hit.url)
        deduped.append(hit)
    return deduped
```

- [ ] **Step 4: 新建 industry_search router**

创建 `apps/api-server/app/routers/industry_search.py`：

```python
from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas import IndustrySearchHit, IndustrySearchRequest, IndustrySearchResult
from app.services.group_context import request_group_id
from app.services.web_search import WebSearchService

router = APIRouter(prefix="/api/v1/industry-search", tags=["industry-search"])


@router.post("", response_model=IndustrySearchResult)
async def industry_search(payload: IndustrySearchRequest, request: Request) -> IndustrySearchResult:
    group_id = request_group_id(request, payload.group_id)
    query = _build_query(payload.industry_name, payload.include_digital_china)
    service = request.app.state.web_search_service
    hits = await service.search(query, providers=payload.providers, max_results=payload.max_results)
    return IndustrySearchResult(
        group_id=group_id,
        industry_name=payload.industry_name,
        query=query,
        hits=[IndustrySearchHit(**hit.__dict__) for hit in hits],
        draft_episode_body=_build_draft(payload.industry_name, hits, payload.include_digital_china),
    )


def _build_query(industry_name: str, include_digital_china: bool) -> str:
    base = f"{industry_name} 产业链 产品 服务 生产 采购 销售 使用 企业 合作 竞争 渠道"
    if include_digital_china:
        base += " 神州数码 客户 合作伙伴 公开关系"
    return base[:380]


def _build_draft(industry_name: str, hits, include_digital_china: bool) -> str:
    source_lines = "\n".join(
        f"- [{hit.title}]({hit.url})：{hit.content[:180]}"
        for hit in hits
    )
    digital_china_line = "需要判断企业与神州数码的公开关系状态、证据 ID、是否需要内部验证。" if include_digital_china else "本次不判断神州数码关系。"
    return f"""产业名称：{industry_name}
目标结构：
- L4 细分产业链节点
- 产品/服务
- 生产、采购、销售、使用这些产品/服务的企业主体
- 企业之间的交易、合作、股权、竞争、渠道关系
- {digital_china_line}

公开资料来源：
{source_lines if source_lines else "- 未检索到可用公开资料"}
"""
```

- [ ] **Step 5: main 注册 service/router**

在 `apps/api-server/app/main.py`：

```python
from app.routers import admin, groups, industry_search, user
from app.services.web_search import WebSearchService
```

初始化：

```python
application.state.web_search_service = WebSearchService(configured_settings)
```

lifespan 关闭：

```python
await application.state.web_search_service.close()
```

注册：

```python
application.include_router(industry_search.router)
```

- [ ] **Step 6: 写测试**

创建 `apps/api-server/tests/test_industry_search.py`：

```python
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.services.web_search import WebSearchHit
from tests.test_api import make_settings


class FakeSearch:
    async def search(self, query, *, providers, max_results):
        return [
            WebSearchHit(
                provider="tavily",
                title="机器人产业链资料",
                url="https://example.com/robotics",
                content="机器人产业链包含减速器、控制器、伺服系统和系统集成企业。",
                score=0.9,
            )
        ]

    async def close(self):
        return None


def test_industry_search_returns_hits_and_draft(tmp_path: Path) -> None:
    from app.main import create_app

    app = create_app(make_settings(tmp_path / "industry-search.db"))
    app.state.web_search_service = FakeSearch()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/industry-search",
            json={"industry_name": "机器人", "group_id": "robotics_kg", "providers": ["tavily"]},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["group_id"] == "robotics_kg"
    assert payload["hits"][0]["url"] == "https://example.com/robotics"
    assert "L4 细分产业链节点" in payload["draft_episode_body"]
    assert "神州数码" in payload["draft_episode_body"]
```

- [ ] **Step 7: 运行测试**

Run:

```powershell
$env:PYTHONUTF8='1'
F:\panda\miniconda\conda\envs\task1-semiconductor-ui\python.exe -m pytest apps/api-server/tests/test_industry_search.py -q
```

Expected: `1 passed`

---

### Task 4: 前端加全局 GroupSelector 和产业搜索小面板

**Files:**
- Modify: `apps/admin-portal/src/types.ts`
- Modify: `apps/admin-portal/src/api.ts`
- Modify: `apps/admin-portal/src/App.tsx`
- Create: `apps/admin-portal/src/IndustrySearchPanel.tsx`
- Modify: `apps/admin-portal/src/styles.css`
- Modify: `apps/user-portal/src/types.ts`
- Modify: `apps/user-portal/src/api.ts`
- Modify: `apps/user-portal/src/App.tsx`
- Test: `apps/admin-portal/src/App.test.tsx`
- Test: `apps/user-portal/src/App.test.tsx`
- Test: `apps/user-portal/src/api.test.ts`

- [ ] **Step 1: 增加共享类型**

在两个 portal 的 `src/types.ts` 增加：

```ts
export interface GroupSummary {
  id: string;
  label?: string | null;
  is_default: boolean;
}

export interface IndustrySearchHit {
  provider: string;
  title: string;
  url: string;
  content: string;
  published_at?: string | null;
  score?: number | null;
}

export interface IndustrySearchResult {
  group_id: string;
  industry_name: string;
  query: string;
  hits: IndustrySearchHit[];
  draft_episode_body: string;
}
```

- [ ] **Step 2: API 客户端支持 group**

在两个 portal 的 `src/api.ts` 增加：

```ts
import type { GroupSummary, IndustrySearchResult } from "./types";

export const GROUP_STORAGE_KEY = "graph_group_id";

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
  providers: Array<"tavily" | "bocha">;
}): Promise<IndustrySearchResult> {
  return request("/api/v1/industry-search", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
```

管理端图谱 API 调整为 query 参数：

```ts
const groupQuery = (groupId: string) => `?group_id=${encodeURIComponent(groupId)}`;
export const getGraphStats = (groupId: string) => request<GraphStats>(`/api/v1/admin/graph/stats${groupQuery(groupId)}`);
export const getUnifiedGraphRoot = (groupId: string) => request<GraphPayload>(`/api/v1/admin/graph/unified/root${groupQuery(groupId)}`);
```

用户端提交问题调整 body：

```ts
export function submitQuestion(conversationId: string, content: string, groupId: string): Promise<SubmittedQuestion> {
  return request(`/api/v1/user/conversations/${conversationId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content, group_id: groupId }),
  });
}
```

- [ ] **Step 3: 管理端 App 加 group state**

在 `apps/admin-portal/src/App.tsx`：

```tsx
const [groups, setGroups] = useState<GroupSummary[]>([]);
const [groupId, setGroupId] = useState(selectedGroupId() ?? "semiconductor_dc_kg");

useEffect(() => {
  listGroups().then((items) => {
    setGroups(items);
    const stored = selectedGroupId();
    const next = stored && items.some((item) => item.id === stored)
      ? stored
      : items[0]?.id ?? "semiconductor_dc_kg";
    setGroupId(next);
    setSelectedGroupId(next);
  });
}, []);
```

左下角替换固定 `semiconductor_dc_kg`：

```tsx
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
    {groups.map((group) => <option key={group.id} value={group.id}>{group.label ?? group.id}</option>)}
  </select>
</div>
```

把 `groupId` 传给 `GraphCenter`、`TraceMonitor`、`GovernancePanel`。

- [ ] **Step 4: 新建管理端 IndustrySearchPanel**

创建 `apps/admin-portal/src/IndustrySearchPanel.tsx`：

```tsx
import { FormEvent, useState } from "react";
import { industrySearch } from "./api";
import type { IndustrySearchResult } from "./types";

export default function IndustrySearchPanel({ groupId }: { groupId: string }) {
  const [industryName, setIndustryName] = useState("");
  const [providers, setProviders] = useState<Array<"tavily" | "bocha">>(["tavily", "bocha"]);
  const [result, setResult] = useState<IndustrySearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      setResult(await industrySearch({ industry_name: industryName, group_id: groupId, providers }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "产业搜索失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="industry-search-panel" aria-label="产业搜索">
      <form onSubmit={submit}>
        <input
          aria-label="产业名称"
          value={industryName}
          onChange={(event) => setIndustryName(event.target.value)}
          placeholder="输入产业名称，例如机器人产业链"
        />
        <label><input type="checkbox" checked={providers.includes("bocha")} onChange={(event) => setProviders(event.target.checked ? [...providers, "bocha"] : providers.filter((item) => item !== "bocha"))} /> Bocha</label>
        <label><input type="checkbox" checked={providers.includes("tavily")} onChange={(event) => setProviders(event.target.checked ? [...providers, "tavily"] : providers.filter((item) => item !== "tavily"))} /> Tavily</label>
        <button disabled={!industryName.trim() || loading || providers.length === 0}>搜索资料</button>
      </form>
      {error ? <p role="alert">{error}</p> : null}
      {result ? (
        <div className="industry-search-result">
          <h3>{result.industry_name}</h3>
          <pre>{result.draft_episode_body}</pre>
          {result.hits.map((hit) => (
            <a key={hit.url} href={hit.url} target="_blank" rel="noreferrer">
              <strong>{hit.title}</strong>
              <span>{hit.provider}</span>
            </a>
          ))}
        </div>
      ) : null}
    </section>
  );
}
```

- [ ] **Step 5: 用户端左下角加 group selector**

在 `apps/user-portal/src/App.tsx` 增加同样的 `groups/groupId` state。提交问题时：

```ts
const submitted = await submitQuestion(conversationId, content, groupId);
```

侧边栏底部加：

```tsx
<div className="user-scope">
  <select
    aria-label="当前图谱 group"
    value={groupId}
    onChange={(event) => {
      setGroupId(event.target.value);
      setSelectedGroupId(event.target.value);
    }}
  >
    {groups.map((group) => <option key={group.id} value={group.id}>{group.label ?? group.id}</option>)}
  </select>
</div>
```

- [ ] **Step 6: 样式**

在两个 portal 的 `styles.css` 增加：

```css
.admin-scope select,
.user-scope select {
  width: 100%;
  min-width: 0;
  height: 28px;
  color: #34413d;
  background: #f8fbfa;
  border: 1px solid #dce7e3;
  border-radius: 4px;
  font: inherit;
}

.industry-search-panel {
  padding: 12px;
  background: #fff;
  border-top: 1px solid var(--line);
}

.industry-search-panel form {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.industry-search-result pre {
  max-height: 220px;
  overflow: auto;
  white-space: pre-wrap;
}
```

- [ ] **Step 7: 写前端测试**

在 `apps/user-portal/src/api.test.ts` 增加：

```ts
it("提交问题时携带 group_id", async () => {
  const fetchMock = vi.fn(() => jsonResponse({ request_id: "r1" }));
  vi.stubGlobal("fetch", fetchMock);

  await submitQuestion("c1", "查机器人产业链", "robotics_kg");

  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("/api/v1/user/conversations/c1/messages"),
    expect.objectContaining({
      body: JSON.stringify({ content: "查机器人产业链", group_id: "robotics_kg" }),
    }),
  );
});
```

在 `apps/admin-portal/src/App.test.tsx` 增加：

```tsx
it("管理端可以切换 group 并发起产业搜索", async () => {
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith("/api/v1/admin/me")) return jsonResponse({ authenticated: true });
    if (url.endsWith("/api/v1/groups")) return jsonResponse([
      { id: "semiconductor_dc_kg", label: "半导体", is_default: true },
      { id: "robotics_kg", label: "机器人", is_default: false },
    ]);
    if (url.endsWith("/api/v1/industry-search")) return jsonResponse({
      group_id: "robotics_kg",
      industry_name: "机器人",
      query: "机器人 产业链",
      hits: [{ provider: "tavily", title: "机器人资料", url: "https://example.com", content: "机器人产业链资料" }],
      draft_episode_body: "产业名称：机器人\n- L4 细分产业链节点",
    });
    if (url.includes("/graph/stats")) return jsonResponse({});
    if (url.includes("/graph/unified/root")) return jsonResponse({ nodes: [], edges: [] });
    if (url.endsWith("/api/v1/admin/governance/sagas")) return jsonResponse([]);
    if (url.endsWith("/api/v1/admin/governance/communities")) return jsonResponse([]);
    if (url.endsWith("/api/v1/admin/jobs")) return jsonResponse([]);
    return jsonResponse({});
  });
  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  const selector = await screen.findByLabelText("当前图谱 group");
  await userEvent.selectOptions(selector, "robotics_kg");
  await userEvent.type(screen.getByLabelText("产业名称"), "机器人");
  await userEvent.click(screen.getByRole("button", { name: "搜索资料" }));

  expect(await screen.findByText("产业名称：机器人")).toBeInTheDocument();
});
```

- [ ] **Step 8: 运行前端测试**

Run:

```powershell
npm test
```

分别在：

```text
apps/admin-portal
apps/user-portal
```

Expected: 两边测试都通过。

---

### Task 5: 最终验证

**Files:**
- `apps/api-server/tests`
- `apps/admin-portal`
- `apps/user-portal`

- [ ] **Step 1: API server 测试**

Run:

```powershell
$env:PYTHONUTF8='1'
F:\panda\miniconda\conda\envs\task1-semiconductor-ui\python.exe -m pytest apps/api-server/tests -q
```

Expected: 全部通过。

- [ ] **Step 2: 管理端测试和构建**

Run:

```powershell
npm test
npm run build
```

Workdir:

```text
apps/admin-portal
```

Expected: 测试通过，构建成功。

- [ ] **Step 3: 用户端测试和构建**

Run:

```powershell
npm test
npm run build
```

Workdir:

```text
apps/user-portal
```

Expected: 测试通过，构建成功。

- [ ] **Step 4: 手动检查**

启动前端后检查：

```text
http://127.0.0.1:7870/
http://127.0.0.1:7871/
```

检查点：

- 用户端左下角能切换 group。
- 用户端提交问题时请求体带 `group_id`。
- 管理端左下角能切换 group。
- 管理端图谱统计和 root 请求带 `group_id`。
- 产业搜索输入“机器人”，能显示搜索来源和资料草稿。
- 没配置 Tavily / Bocha key 时，接口返回空 hits 但不报 500。

---

## Self Review

- Spec coverage:
  - group 可切换：Task 1、Task 2、Task 4 覆盖。
  - 用户和管理都可切换：Task 4 覆盖两个 portal。
  - 使用 Bocha / Tavily：Task 3 覆盖。
  - 不复杂、薄搜索层：Scope Guard 和 Task 3 限定只返回草稿，不自动入库。
  - 复用已有后端接口/服务：Task 2 通过 group 参数复用现有问答、图谱、治理服务。

- Placeholder scan:
  - 无 TBD / TODO。
  - Bocha endpoint 未硬编码，使用 `BOCHA_SEARCH_URL` 配置，避免错误绑定不确定官方 URL。

- Type consistency:
  - `group_id` 在后端 request/schema、前端 API、测试中统一。
  - `IndustrySearchResult` 后端和前端字段一致。
