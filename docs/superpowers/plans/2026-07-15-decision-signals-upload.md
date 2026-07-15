# Decision Signals Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在管理端新增一个轻量“决策资料”页面，支持上传政策/论文/技术风向链接或文档，并把资料作为 `决策信号层` episode 写入当前 `group_id`，让问答能简单召回政策、技术规律和行业风向内容。

**Architecture:** 不做复杂审核系统，不做批量爬虫，不做独立决策知识图谱。后端只新增一个管理端上传接口，把链接/文档/纯文本包装成标准 episode，调用 Graphiti `add_episode()` 写入当前 group 的 `决策信号层` saga。前端只新增一个管理页，表单提交后显示导入结果和可复制的资料摘要。

**Tech Stack:** FastAPI, Graphiti, Neo4j, httpx, pypdf, React/Vite, pytest, Vitest.

---

## Scope

v1 只支持：

- 管理端新增页面：`决策资料`
- 资料类型：
  - 链接：URL + 可选标题/备注
  - 文档：`.txt` / `.md` / `.pdf`
  - 手动文本：标题 + 正文
- 分类：
  - `policy` 政策风向
  - `technology` 技术趋势
  - `industry_rule` 行业规律
  - `business_implication` 企业战略含义
- 写入方式：
  - 使用当前左下角选择的 `group_id`
  - saga 固定为：`决策信号层`
  - episode 内容使用统一模板

v1 不做：

- 不做 Word/Excel 解析。
- 不做多文件批量上传。
- 不做自动审核流。
- 不做复杂网页正文抽取，只做标题和基础文本抽取。
- 不自动判断“政策正确性”，只保留来源和备注。

---

## Episode 模板

每条资料入库前包装成：

```text
资料类型：政策风向 / 技术趋势 / 行业规律 / 企业战略含义
标题：{title}
关键词：{keywords}
来源链接：{source_url}
上传方式：link / document / text

核心内容：
{content}

对产业链的可能影响：
{industry_impact}

对神州数码业务判断的可能影响：
{dc_implication}

备注：
{notes}
```

最小可用原则：

- 如果用户没有填 `industry_impact`，用空字符串。
- 如果用户没有填 `dc_implication`，用空字符串。
- 如果是 PDF，只抽前 12 页文本，避免过慢。
- 每次正文最多写入 12,000 字符，避免 LLM 上下文过长。

---

### Task 1: 后端 schema 和依赖

**Files:**
- Modify: `apps/api-server/pyproject.toml`
- Modify: `apps/api-server/app/schemas.py`

- [ ] **Step 1: 增加 PDF 解析依赖**

在 `apps/api-server/pyproject.toml` dependencies 增加：

```toml
"pypdf>=5,<7",
```

- [ ] **Step 2: 增加 schema**

在 `apps/api-server/app/schemas.py` 增加：

```python
class DecisionSignalImportResult(BaseModel):
    group_id: str
    saga: str
    episode_uuid: str
    title: str
    category: Literal["policy", "technology", "industry_rule", "business_implication"]
    source_type: Literal["link", "document", "text"]
    source_url: str | None = None
    content_preview: str
```

- [ ] **Step 3: 运行 schema 导入测试**

Run:

```powershell
$env:PYTHONUTF8='1'
F:\panda\miniconda\conda\envs\task1-semiconductor-ui\python.exe -c "from app.schemas import DecisionSignalImportResult; print(DecisionSignalImportResult.__name__)"
```

Expected:

```text
DecisionSignalImportResult
```

---

### Task 2: 后端决策资料导入 service

**Files:**
- Create: `apps/api-server/app/services/decision_signals.py`
- Test: `apps/api-server/tests/test_decision_signals.py`

- [ ] **Step 1: 创建 service**

创建 `apps/api-server/app/services/decision_signals.py`：

```python
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from io import BytesIO
from typing import Any, Literal

import httpx
from pypdf import PdfReader

from app.config import Settings

DECISION_SIGNAL_SAGA = "决策信号层"
MAX_CONTENT_CHARS = 12000
MAX_PDF_PAGES = 12

CATEGORY_LABELS = {
    "policy": "政策风向",
    "technology": "技术趋势",
    "industry_rule": "行业规律",
    "business_implication": "企业战略含义",
}


def build_decision_signal_episode_body(
    *,
    title: str,
    category: str,
    source_type: str,
    content: str,
    source_url: str | None = None,
    keywords: str = "",
    industry_impact: str = "",
    dc_implication: str = "",
    notes: str = "",
) -> str:
    trimmed_content = content.strip()[:MAX_CONTENT_CHARS]
    return f"""资料类型：{CATEGORY_LABELS.get(category, category)}
标题：{title.strip()}
关键词：{keywords.strip()}
来源链接：{source_url or ""}
上传方式：{source_type}

核心内容：
{trimmed_content}

对产业链的可能影响：
{industry_impact.strip()}

对神州数码业务判断的可能影响：
{dc_implication.strip()}

备注：
{notes.strip()}
"""


def extract_text_from_upload(filename: str, payload: bytes) -> str:
    lower_name = filename.lower()
    if lower_name.endswith((".txt", ".md")):
        return payload.decode("utf-8", errors="ignore")
    if lower_name.endswith(".pdf"):
        reader = PdfReader(BytesIO(payload))
        pages = reader.pages[:MAX_PDF_PAGES]
        return "\n".join(page.extract_text() or "" for page in pages)
    raise ValueError("仅支持 .txt / .md / .pdf 文档")


async def fetch_link_text(url: str) -> str:
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        text = response.text
    return text[:MAX_CONTENT_CHARS]


async def import_decision_signal(
    *,
    settings: Settings,
    graphiti_factory: Any,
    group_id: str,
    title: str,
    category: Literal["policy", "technology", "industry_rule", "business_implication"],
    source_type: Literal["link", "document", "text"],
    content: str,
    source_url: str | None = None,
    keywords: str = "",
    industry_impact: str = "",
    dc_implication: str = "",
    notes: str = "",
) -> dict[str, Any]:
    scoped_settings = replace(settings, group_id=group_id)
    graphiti = graphiti_factory(scoped_settings)
    body = build_decision_signal_episode_body(
        title=title,
        category=category,
        source_type=source_type,
        content=content,
        source_url=source_url,
        keywords=keywords,
        industry_impact=industry_impact,
        dc_implication=dc_implication,
        notes=notes,
    )
    try:
        result = await graphiti.add_episode(
            name=title,
            episode_body=body,
            source_description=f"决策信号层/{CATEGORY_LABELS[category]}",
            reference_time=datetime.now(UTC),
            group_id=group_id,
            saga=DECISION_SIGNAL_SAGA,
        )
        return {
            "group_id": group_id,
            "saga": DECISION_SIGNAL_SAGA,
            "episode_uuid": result.episode.uuid,
            "title": title,
            "category": category,
            "source_type": source_type,
            "source_url": source_url,
            "content_preview": body[:500],
        }
    finally:
        close = getattr(graphiti, "close", None)
        if close is not None:
            await close()
```

- [ ] **Step 2: 写 service 单测**

创建 `apps/api-server/tests/test_decision_signals.py`：

```python
from __future__ import annotations


def test_build_decision_signal_episode_body_contains_policy_context() -> None:
    from app.services.decision_signals import build_decision_signal_episode_body

    body = build_decision_signal_episode_body(
        title="摩尔定律放缓与先进封装",
        category="technology",
        source_type="text",
        content="摩尔定律放缓推动 Chiplet 和先进封装发展。",
        keywords="摩尔定律, Chiplet, 先进封装",
        industry_impact="封装测试、HBM、AI服务器需求增强。",
        dc_implication="有助于解释 AI 基础设施业务机会。",
    )

    assert "资料类型：技术趋势" in body
    assert "摩尔定律放缓与先进封装" in body
    assert "对神州数码业务判断的可能影响" in body
```

- [ ] **Step 3: 运行测试**

Run:

```powershell
$env:PYTHONUTF8='1'
F:\panda\miniconda\conda\envs\task1-semiconductor-ui\python.exe -m pytest apps/api-server/tests/test_decision_signals.py -q
```

Expected: `1 passed`

---

### Task 3: 后端管理端上传接口

**Files:**
- Modify: `apps/api-server/app/routers/admin.py`
- Test: `apps/api-server/tests/test_api.py`

- [ ] **Step 1: 增加 multipart 依赖检查**

如果本地缺 `python-multipart`，在 `apps/api-server/pyproject.toml` dependencies 增加：

```toml
"python-multipart>=0.0.20,<1",
```

- [ ] **Step 2: 增加 router endpoint**

在 `apps/api-server/app/routers/admin.py` 增加 imports：

```python
from fastapi import File, Form, UploadFile
from app.schemas import DecisionSignalImportResult
from app.services.decision_signals import (
    extract_text_from_upload,
    fetch_link_text,
    import_decision_signal,
)
from app.services.group_context import request_group_id
```

新增 endpoint：

```python
@router.post(
    "/decision-signals",
    dependencies=[Depends(require_admin)],
    response_model=DecisionSignalImportResult,
)
async def import_decision_signal_endpoint(
    request: Request,
    group_id: str | None = Form(default=None),
    category: Literal["policy", "technology", "industry_rule", "business_implication"] = Form(...),
    source_type: Literal["link", "document", "text"] = Form(...),
    title: str = Form(...),
    source_url: str | None = Form(default=None),
    content: str = Form(default=""),
    keywords: str = Form(default=""),
    industry_impact: str = Form(default=""),
    dc_implication: str = Form(default=""),
    notes: str = Form(default=""),
    file: UploadFile | None = File(default=None),
) -> dict[str, Any]:
    resolved_group_id = request_group_id(request, group_id)
    if source_type == "document":
        if file is None:
            raise HTTPException(status_code=422, detail="document 类型必须上传文件")
        content = extract_text_from_upload(file.filename or "upload.txt", await file.read())
    elif source_type == "link":
        if not source_url:
            raise HTTPException(status_code=422, detail="link 类型必须提供 source_url")
        if not content.strip():
            content = await fetch_link_text(source_url)
    elif not content.strip():
        raise HTTPException(status_code=422, detail="text 类型必须提供 content")

    from app.services.runtime import build_graphiti

    return await import_decision_signal(
        settings=request.app.state.settings,
        graphiti_factory=build_graphiti,
        group_id=resolved_group_id,
        title=title,
        category=category,
        source_type=source_type,
        content=content,
        source_url=source_url,
        keywords=keywords,
        industry_impact=industry_impact,
        dc_implication=dc_implication,
        notes=notes,
    )
```

- [ ] **Step 3: 抽出 build_graphiti helper**

在 `apps/api-server/app/services/runtime.py` 从 `build_default_pipeline()` 中抽出：

```python
def build_graphiti(settings: Settings):
    from graphiti_core import Graphiti
    from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
    from graphiti_core.llm_client import LLMConfig
    from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient

    graphiti_llm = OpenAIGenericClient(
        config=LLMConfig(
            api_key=settings.siliconflow_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
        )
    )
    embedder = OpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            api_key=settings.siliconflow_api_key,
            base_url=settings.embedding_base_url,
            model=settings.embedding_model,
        )
    )
    return Graphiti(
        settings.neo4j_uri,
        settings.neo4j_user,
        settings.neo4j_password,
        llm_client=graphiti_llm,
        embedder=embedder,
    )
```

然后 `build_default_pipeline()` 复用 `build_graphiti(settings)`，避免重复创建逻辑。

- [ ] **Step 4: 写 endpoint 测试**

在 `apps/api-server/tests/test_api.py` 增加：

```python
def test_admin_can_import_text_decision_signal(tmp_path: Path, monkeypatch) -> None:
    from app.main import create_app

    class FakeEpisode:
        uuid = "episode-1"

    class FakeResult:
        episode = FakeEpisode()

    class FakeGraphiti:
        async def add_episode(self, **kwargs):
            self.kwargs = kwargs
            return FakeResult()

        async def close(self):
            return None

    fake_graphiti = FakeGraphiti()

    def fake_factory(settings):
        return fake_graphiti

    monkeypatch.setattr("app.services.runtime.build_graphiti", fake_factory)
    app = create_app(make_settings(tmp_path / "decision-signals.db"))

    with TestClient(app) as client:
        client.post("/api/v1/admin/login", json={"password": "admin-secret-value"})
        response = client.post(
            "/api/v1/admin/decision-signals",
            data={
                "group_id": "semiconductor_dc_kg",
                "category": "technology",
                "source_type": "text",
                "title": "摩尔定律放缓",
                "content": "摩尔定律放缓推动先进封装和 Chiplet。",
                "keywords": "摩尔定律,先进封装",
            },
        )

    assert response.status_code == 200
    assert response.json()["episode_uuid"] == "episode-1"
    assert fake_graphiti.kwargs["saga"] == "决策信号层"
    assert "摩尔定律放缓" in fake_graphiti.kwargs["episode_body"]
```

- [ ] **Step 5: 运行测试**

Run:

```powershell
$env:PYTHONUTF8='1'
F:\panda\miniconda\conda\envs\task1-semiconductor-ui\python.exe -m pytest apps/api-server/tests/test_api.py::test_admin_can_import_text_decision_signal -q
```

Expected: `1 passed`

---

### Task 4: 管理端新增“决策资料”页面

**Files:**
- Modify: `apps/admin-portal/src/types.ts`
- Modify: `apps/admin-portal/src/api.ts`
- Create: `apps/admin-portal/src/DecisionSignalsPage.tsx`
- Modify: `apps/admin-portal/src/App.tsx`
- Modify: `apps/admin-portal/src/styles.css`
- Test: `apps/admin-portal/src/App.test.tsx`

- [ ] **Step 1: 增加前端类型**

在 `apps/admin-portal/src/types.ts` 增加：

```ts
export type DecisionSignalCategory = "policy" | "technology" | "industry_rule" | "business_implication";
export type DecisionSignalSourceType = "link" | "document" | "text";

export interface DecisionSignalImportResult {
  group_id: string;
  saga: string;
  episode_uuid: string;
  title: string;
  category: DecisionSignalCategory;
  source_type: DecisionSignalSourceType;
  source_url?: string | null;
  content_preview: string;
}
```

- [ ] **Step 2: 增加 API 方法**

在 `apps/admin-portal/src/api.ts` 增加：

```ts
import type { DecisionSignalImportResult } from "./types";

export function importDecisionSignal(formData: FormData): Promise<DecisionSignalImportResult> {
  return request("/api/v1/admin/decision-signals", {
    method: "POST",
    body: formData,
  });
}
```

如果当前 `request()` 默认强制设置 `Content-Type: application/json`，调整为：

```ts
const headers = init?.body instanceof FormData ? undefined : { "Content-Type": "application/json" };
```

- [ ] **Step 3: 新建页面组件**

创建 `apps/admin-portal/src/DecisionSignalsPage.tsx`：

```tsx
import { FormEvent, useState } from "react";
import { Upload } from "lucide-react";

import { importDecisionSignal } from "./api";
import type { DecisionSignalImportResult, DecisionSignalSourceType } from "./types";

export default function DecisionSignalsPage({ groupId }: { groupId: string }) {
  const [sourceType, setSourceType] = useState<DecisionSignalSourceType>("text");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [keywords, setKeywords] = useState("");
  const [category, setCategory] = useState("technology");
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<DecisionSignalImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    const form = new FormData();
    form.set("group_id", groupId);
    form.set("source_type", sourceType);
    form.set("category", category);
    form.set("title", title);
    form.set("content", content);
    form.set("source_url", sourceUrl);
    form.set("keywords", keywords);
    if (file) form.set("file", file);
    try {
      setResult(await importDecisionSignal(form));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "资料导入失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="workspace decision-workspace">
      <header className="workspace-header">
        <div>
          <span className="section-kicker">决策信号层</span>
          <h1>政策 / 论文 / 技术风向资料</h1>
        </div>
      </header>
      <form className="decision-form" onSubmit={submit}>
        <select aria-label="资料类型" value={sourceType} onChange={(event) => setSourceType(event.target.value as DecisionSignalSourceType)}>
          <option value="text">手动文本</option>
          <option value="link">链接</option>
          <option value="document">文档</option>
        </select>
        <select aria-label="资料分类" value={category} onChange={(event) => setCategory(event.target.value)}>
          <option value="policy">政策风向</option>
          <option value="technology">技术趋势</option>
          <option value="industry_rule">行业规律</option>
          <option value="business_implication">企业战略含义</option>
        </select>
        <input aria-label="标题" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="例如：摩尔定律放缓与先进封装趋势" />
        <input aria-label="关键词" value={keywords} onChange={(event) => setKeywords(event.target.value)} placeholder="摩尔定律, Chiplet, 先进封装" />
        {sourceType === "link" ? <input aria-label="来源链接" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="https://..." /> : null}
        {sourceType === "document" ? <input aria-label="上传文档" type="file" accept=".txt,.md,.pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /> : null}
        {sourceType !== "document" ? <textarea aria-label="正文" value={content} onChange={(event) => setContent(event.target.value)} placeholder="粘贴政策、论文摘要、技术趋势说明..." /> : null}
        <button disabled={!title.trim() || loading}><Upload size={15} />上传到决策信号层</button>
      </form>
      {error ? <div className="workspace-error" role="alert">{error}</div> : null}
      {result ? (
        <section className="decision-result">
          <h2>导入成功</h2>
          <p>{result.title}</p>
          <small>{result.group_id} / {result.saga} / {result.episode_uuid}</small>
          <pre>{result.content_preview}</pre>
        </section>
      ) : null}
    </section>
  );
}
```

- [ ] **Step 4: App 增加页面入口**

在 `apps/admin-portal/src/App.tsx`：

```tsx
import FileText from "lucide-react";
import DecisionSignalsPage from "./DecisionSignalsPage";
```

将页面状态从：

```ts
const [page, setPage] = useState<"graph" | "trace">("graph");
```

改为：

```ts
const [page, setPage] = useState<"graph" | "signals" | "trace">("graph");
```

导航增加：

```tsx
<button aria-label="决策资料" className={page === "signals" ? "active" : ""} onClick={() => setPage("signals")}>
  <FileText size={18} />
  <span>决策资料</span>
</button>
```

页面渲染：

```tsx
{page === "graph" ? <GraphCenter groupId={groupId} /> : null}
{page === "signals" ? <DecisionSignalsPage groupId={groupId} /> : null}
{page === "trace" ? <TraceMonitor /> : null}
```

- [ ] **Step 5: 增加样式**

在 `apps/admin-portal/src/styles.css` 增加：

```css
.decision-workspace { background: #fbfcfc; }
.decision-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  max-width: 880px;
  padding: 22px;
}
.decision-form input,
.decision-form select,
.decision-form textarea {
  min-height: 34px;
  padding: 8px 10px;
  color: #34413d;
  background: #fff;
  border: 1px solid #dce7e3;
  border-radius: 5px;
}
.decision-form textarea {
  grid-column: 1 / -1;
  min-height: 180px;
  resize: vertical;
}
.decision-form button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 36px;
  color: #fff;
  background: var(--teal);
  border: 0;
  border-radius: 5px;
  font-weight: 750;
}
.decision-result {
  max-width: 880px;
  margin: 0 22px 22px;
  padding: 16px;
  background: #fff;
  border: 1px solid #dfe8e5;
  border-radius: 6px;
}
.decision-result pre {
  max-height: 260px;
  overflow: auto;
  white-space: pre-wrap;
}
```

- [ ] **Step 6: 写前端测试**

在 `apps/admin-portal/src/App.test.tsx` 增加：

```tsx
it("管理端可以上传决策资料文本", async () => {
  const user = userEvent.setup();
  const fetchMock = vi.fn((input: string | URL | Request) => {
    const url = String(input);
    if (url.endsWith("/api/v1/admin/me")) return jsonResponse({ authenticated: true });
    if (url.endsWith("/api/v1/admin/decision-signals")) return jsonResponse({
      group_id: "semiconductor_dc_kg",
      saga: "决策信号层",
      episode_uuid: "episode-1",
      title: "摩尔定律放缓",
      category: "technology",
      source_type: "text",
      source_url: null,
      content_preview: "资料类型：技术趋势\n标题：摩尔定律放缓",
    });
    if (url.includes("/graph/stats")) return jsonResponse({});
    if (url.endsWith("/api/v1/admin/graph/unified/root")) return jsonResponse({ nodes: [], edges: [] });
    if (url.endsWith("/api/v1/admin/governance/sagas")) return jsonResponse([]);
    if (url.endsWith("/api/v1/admin/governance/communities")) return jsonResponse([]);
    if (url.endsWith("/api/v1/admin/jobs")) return jsonResponse([]);
    return jsonResponse({});
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);

  await user.click(await screen.findByRole("button", { name: "决策资料" }));
  await user.type(screen.getByLabelText("标题"), "摩尔定律放缓");
  await user.type(screen.getByLabelText("正文"), "摩尔定律放缓推动先进封装发展。");
  await user.click(screen.getByRole("button", { name: "上传到决策信号层" }));

  expect(await screen.findByText("导入成功")).toBeInTheDocument();
  expect(screen.getByText("episode-1")).toBeInTheDocument();
});
```

- [ ] **Step 7: 运行前端测试**

Run:

```powershell
npm test
```

Workdir:

```text
apps/admin-portal
```

Expected: 测试通过。

---

### Task 5: 准备首批答辩资料

**Files:**
- Create: `data/decision_signals/seed_decision_signals.md`

- [ ] **Step 1: 创建资料清单**

创建 `data/decision_signals/seed_decision_signals.md`：

```markdown
# 决策信号层首批资料清单

## 政策风向

1. 数字中国建设整体布局规划
   - 关键词：数字中国、数据要素、数字经济
   - 答辩用途：说明项目响应数字经济和数据要素建设方向

2. 人工智能+ / 新质生产力相关政策表述
   - 关键词：人工智能、新质生产力、产业升级
   - 答辩用途：说明 AI 赋能产业分析的政策背景

3. 产业链供应链韧性与安全
   - 关键词：供应链安全、国产替代、关键核心技术
   - 答辩用途：说明半导体产业链图谱的必要性

## 技术趋势

1. 摩尔定律放缓
   - 关键词：摩尔定律、制程缩小、成本上升
   - 答辩用途：回答“摩尔定律变化对行业的影响”

2. More than Moore 与先进封装
   - 关键词：Chiplet、先进封装、HBM
   - 答辩用途：解释先进封装、AI 算力和产业链机会

3. RAG 与知识图谱问答
   - 关键词：RAG、知识图谱、证据召回
   - 答辩用途：说明本项目技术路线不是简单 prompt 问答

## 行业规律

1. AI 算力需求带动服务器、存储、网络设备需求
2. 国产替代推动半导体设备、材料、EDA、封测关注度提升
3. 企业竞争从单点产品转向生态和供应链协同
```

- [ ] **Step 2: 人工收集资料**

按清单收集 15-25 条资料即可。每条资料控制在：

```text
标题：1 行
来源链接：1 个
核心内容：200-800 字
对产业链影响：1-3 点
对神州数码影响：1-3 点
```

- [ ] **Step 3: 用管理端页面上传**

打开：

```text
http://127.0.0.1:7871/
```

进入：

```text
决策资料 -> 选择分类 -> 填标题/正文/链接 -> 上传到决策信号层
```

- [ ] **Step 4: 验证问答能召回**

在用户端提问：

```text
摩尔定律放缓对半导体产业链有什么影响？
```

期望回答包含：

```text
先进封装 / Chiplet / HBM / AI 算力基础设施 / 供应链分工
```

---

### Task 6: 最终验证

**Files:**
- `apps/api-server/tests`
- `apps/admin-portal`

- [ ] **Step 1: 后端测试**

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

- [ ] **Step 3: 手动冒烟测试**

检查：

- 管理端导航出现 `决策资料`。
- 纯文本能上传成功。
- 链接能上传成功。
- `.txt` 或 `.pdf` 能上传成功。
- 返回结果里能看到 `决策信号层` 和 `episode_uuid`。
- 用户端问答能召回刚上传的资料。

---

## 答辩讲法

这部分可以作为 PPT 一页：

```text
为了让系统不只回答“企业之间有什么关系”，还能够回答“为什么这个方向重要”，我们补充了一个轻量决策信号层。

这一层收集政策文件、论文摘要、技术趋势和行业规律，例如新质生产力、产业链供应链安全、摩尔定律放缓、先进封装、Chiplet、AI 算力基础设施等。

这些资料不单独做复杂图谱，而是作为可追溯的 episode 写入现有知识图谱，因此问答时可以和产业链、企业关系一起被召回。

这样既满足院长关注的政策与学术支撑，也能帮助企业老师看到项目对真实产业判断的辅助价值。
```

---

## Self Review

- 已满足方案 1：只做 20-40 条资料的轻量决策信号层。
- 已覆盖用户补充：管理端新增页面，支持上传链接和文档。
- 未引入复杂审核、队列、权限和批处理。
- 与现有 Graphiti 入库方式兼容：写入 episode + saga。
- 可支撑答辩问题：政策方向、技术趋势、摩尔定律/先进封装对行业影响。
