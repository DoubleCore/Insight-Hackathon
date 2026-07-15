# 工具运行参考（脱敏）

依据 `F:\Java后端资料\实习\神州数码实习\AI 工具密钥.md` 生成。本文件只记录工具用途、环境变量名和接口入口，不写入真实 key。

| 工具 | 用途 | 环境变量 | Endpoint/入口 | Stage 1 用法 | 安全注意 |
|---|---|---|---|---|---|
| Bocha | 中文行业搜索、政策、研报和产业新闻入口 | `BOCHA_API_KEY` | `https://api.bochaai.com/v1/web-search` | 中文产业链、国产替代、资本开支线索 | 结果仅作候选证据入口 |
| Tavily | 海外网页搜索、公司 IR、SEMI/SIA 入口 | `TAVILY_API_KEY` | `https://api.tavily.com/search` | 英文行业框架、海外资料入口 | 新闻不得直接证明长期关系 |
| DeepSeek | 低成本筛选和短摘要 | `DEEPSEEK_API_KEY` | `https://api.deepseek.com/chat/completions` | 本阶段由 Codex 本地规则替代筛选 | 不输出密钥 |
| Kimi | 长上下文 PDF/报告证据摘录 | `MOONSHOT_API_KEY` | `https://api.moonshot.ai/v1/chat/completions` | 本阶段未做长报告全文摘录 | 后续阶段补页码和原文 |
