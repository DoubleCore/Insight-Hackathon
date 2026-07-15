# 双前端验收平台 API Server

本目录提供可独立运行的 FastAPI 服务，包含匿名会话隔离、管理口令鉴权和 SQLite 观测数据存储。默认数据库固定在当前 worktree 根目录的 `data/runtime/qa_observability.db`，不受启动目录影响。

## 安装

使用任务专用 Python 环境安装，避免修改 base 环境：

```powershell
cd apps/api-server
F:\panda\miniconda\conda\envs\task1-semiconductor-ui\python.exe -m pip install -e .
```

## 环境变量

| 变量名 | 默认值或说明 |
| --- | --- |
| `APP_ENV` | `development`；其他值视为非开发环境 |
| `NEO4J_URI` | `bolt://localhost:7687` |
| `NEO4J_USER` | `neo4j` |
| `NEO4J_PASSWORD` | 默认值仅用于本地开发，部署时必须覆盖 |
| `GROUP_ID` | `semiconductor_dc_kg` |
| `API_PORT` | `8001` |
| `SQLITE_PATH` | `data/runtime/qa_observability.db` |
| `ADMIN_PASSWORD` | 管理端登录口令；必须由运行环境设置 |
| `SESSION_SECRET` | Cookie 签名密钥；非开发环境必须设置稳定值，否则服务拒绝启动 |
| `COOKIE_SECURE` | `true`；仅本地 HTTP 开发可显式设置为 `false` |
| `SILICONFLOW_API_KEY` | Graphiti 检索嵌入与服务端重排使用的密钥，只从服务端环境读取 |
| `GRAPHITI_LLM_BASE_URL` | `https://api.siliconflow.cn/v1` |
| `GRAPHITI_LLM_MODEL` | `deepseek-ai/DeepSeek-V3.2` |
| `GRAPHITI_EMBEDDING_BASE_URL` | `https://api.siliconflow.cn/v1` |
| `GRAPHITI_EMBEDDING_MODEL` | `BAAI/bge-m3` |
| `GRAPHITI_RERANKER_MODEL` | `deepseek-ai/DeepSeek-V3.2` |
| `RETRIEVAL_SLICE_LIMIT` | 单路检索上限，默认 `20` |
| `RETRIEVAL_CANDIDATE_POOL_LIMIT` | 去重后的候选池上限，默认 `60` |
| `RETRIEVAL_FINAL_RESULT_LIMIT` | 最终选中结果上限，默认 `12` |

开发环境未设置 `SESSION_SECRET` 时会生成进程级临时密钥，服务重启后旧 Cookie 自动失效。不要把真实口令或密钥写入仓库、命令历史或日志。

## 深度检索与可信度

深度检索通过依赖注入组合四个独立切面：vector 对 edge、node、community 执行余弦检索；BM25 对 edge、node、episode、community 执行关键词检索；BFS 使用前两路命中的 Entity UUID 作为起点遍历 edge 与 node；lexical 使用参数化 Neo4j 查询补召回精确词面。Graphiti 适配器只调用高级 `search_`，任一路失败都会记录该路状态、错误和耗时，不阻塞其他切面。

候选优先按对象类型与 UUID 去重，无 UUID 时使用规范化内容哈希，并保留来源算法、原排名和原分数。候选池最多保留 60 条，服务端 CrossEncoder 全局重排失败时自动降级为 RRF，最终最多选择 12 条。

只有携带可解析 `evidence_ids` 的事实边或 episode 能通过证据门控；Entity 与 Community 只能提供背景。没有公开证据或全部标记为 `no_public_evidence` 时服务拒绝生成有事实断言的回答，B- 级证据可回答但必须标记“证据有限”。可信度契约只输出证据质量、事实置信度、时效性和核验状态四个独立维度，不计算或暴露综合分；`potential_fit`、推定关系和需要内部核验的候选不会升级为已确认关系。

模型、base URL、密钥和检索上限均由服务端 `Settings` 管理，不提供面向用户的配置 API。

## 运行

在仓库根目录设置环境变量后启动：

```powershell
$env:APP_ENV = "development"
$env:ADMIN_PASSWORD = "<管理口令>"
$env:SESSION_SECRET = "<高强度随机会话密钥>"
$env:COOKIE_SECURE = "false"
$env:API_PORT = "8001"
F:\panda\miniconda\conda\envs\task1-semiconductor-ui\python.exe -m uvicorn app.main:app --app-dir apps/api-server --host 127.0.0.1 --port $env:API_PORT --workers 1
```

健康检查地址为 `http://127.0.0.1:8001/health`。浏览器跨域请求只接受 `http://127.0.0.1:7870` 和 `http://127.0.0.1:7871`，并允许携带 Cookie。

当前服务按单 worker 运行。后台任务记录包含 worker、heartbeat 和 lease 字段，启动恢复只中断无租约或租约已过期的任务，不会中断仍持有有效租约的 worker。

## 测试

```powershell
cd apps/api-server
F:\panda\miniconda\conda\envs\task1-semiconductor-ui\python.exe -m pytest -q
```

## 一键验收启动

在仓库根目录运行 `start-acceptance-platform.bat`。脚本复用原 Neo4j 数据库，启动 API、用户端和管理端，并从原项目的 `AI 工具密钥.md` 向 API 子进程注入 SiliconFlow 密钥。日志与稳定会话密钥只写入已忽略的 `data/runtime/`。

- 用户端：`http://127.0.0.1:7870`
- 管理端：`http://127.0.0.1:7871`
- API：`http://127.0.0.1:8001`
- 默认本地管理口令：`admin`

停止新平台运行 `stop-acceptance-platform.bat`。该脚本不停止 Neo4j，也不处理原 `7860` 页面。
