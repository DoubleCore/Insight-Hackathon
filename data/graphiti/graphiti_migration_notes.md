# Graphiti 迁移说明

## 当前方案

现有半导体产业链图谱仍保留在 Neo4j 自定义结构中，用于 Neo4j Browser 可视化。Graphiti 侧通过 `data/graphiti/semiconductor_episodes.jsonl` 导入产业链事实、企业关系、公司-产品关系、推定竞争候选和神州数码公开关系，形成 Graphiti 自己的 temporal graph，用于问答检索。

`stage8_business_opportunities.csv` 不导入 Graphiti。它属于商机、解决方案和战役计划推演层，保留在原业务图谱和 CSV 中，避免 Graphiti 问答把候选分析误当作事实关系。

## 为什么不是直接复用原 Neo4j 节点

Graphiti 的核心对象是 `Episodic` episode、`Entity` 节点和 `RELATES_TO` 事实边。它需要通过 `add_episode` 执行实体抽取、关系抽取、去重、事实失效和时间字段生成。如果直接把原图谱节点复制进去，Graphiti 的问答、去重和 temporal 逻辑不会完整生效。

## 时间字段映射

- `data_as_of` -> Graphiti `reference_time`
- Graphiti 自动生成写入时间 `created_at`
- Graphiti 根据 episode 文本和 `reference_time` 抽取事实边的 `valid_at`
- 明确终止关系时，Graphiti 会尝试抽取 `invalid_at`
- `first_seen_at`、`last_verified_at`、`source_publish_dates` 写入 episode 文本，供问答解释和事实抽取参考
- `event_start_at` 只有公告、签约、合作发布、财报披露等明确日期时才填；没有明确证据时保持为空
- `event_end_at` 只有终止、到期、停止合作、关系失效等明确资料时才填；没有明确证据时保持为空
- `event_date` 用于一次性事件日期；它不能替代长期关系的开始/结束时间
- `time_precision` 记录时间精度：`day`、`month`、`year`、`unknown`
- `temporal_basis` 记录时间依据：`公告日期`、`证据发布日期`、`检索快照`、`未明确`

## 事件开始/结束时间原则

不能用检索时间冒充事件开始时间，也不能用证据发布日期冒充合作开始时间。如果公开资料只证明“某时间点报道过/检索到”，但没有说明关系从何时开始或何时结束，则 `event_start_at` 和 `event_end_at` 留空。

这种情况下通过 `data_as_of`、`last_verified_at`、`current_validity` 和 `temporal_basis` 说明它是当前公开资料快照，而不是精确历史事件边界。

## 事实边界

- 龙头判断：事实判断，但仍受证据等级和数据截至时间约束。
- 企业供应/合作关系：公开资料支持的事实关系。
- 公司-产品关系：公开资料支持或业务归纳关系，`requires_internal_validation=true` 的关系不能说成内部客户事实。
- 推定竞争关系：只表示同环节同产品龙头之间的候选竞争关系，需要保留“推定”和“需验证”的限定，不能说成已经证明的直接竞争事件。
- 神州数码关系：只有 `confirmed_public_relationship` 能称为公开确认关系。
- 商机/解决方案：候选分析，不进入 Graphiti，不代表订单、客户关系或已发生项目。

## Neo4j Browser 验证命令

```cypher
MATCH (e:Episodic)
WHERE e.group_id = 'semiconductor_dc_kg'
RETURN e.name, e.source_description, e.valid_at, e.created_at
ORDER BY e.created_at DESC
LIMIT 20;
```

```cypher
MATCH (a)-[r:RELATES_TO]->(b)
WHERE r.group_id = 'semiconductor_dc_kg'
RETURN a.name, r.fact, r.valid_at, r.invalid_at, b.name
LIMIT 50;
```
