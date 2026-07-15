import { FormEvent, useMemo, useState } from "react";
import { CheckCircle2, FileSearch, PackageCheck, Search, ShieldCheck } from "lucide-react";

import { createPendingIndustryEpisode, industrySearch } from "./api";
import type { GroupSummary, IndustrySearchResult, PendingEpisodeResult } from "./types";

type SearchProvider = "tavily" | "bocha";
type TargetMode = "new_group" | "existing_group";
type SearchDepth = "quick" | "standard" | "deep";

const RELATION_TYPES = ["生产", "采购", "销售", "使用", "合作", "股权", "竞争", "渠道"];
const DEPTH_OPTIONS: Array<{ value: SearchDepth; label: string; description: string }> = [
  { value: "quick", label: "快速", description: "少量来源，适合快速判断方向" },
  { value: "standard", label: "标准", description: "覆盖产业链、产品、企业和公开关系" },
  { value: "deep", label: "深度", description: "更多来源，加入官网、年报、公告、招投标口径" },
];

interface IndustrySearchPanelProps {
  groupId: string;
  groups: GroupSummary[];
}

export default function IndustrySearchPanel({ groupId, groups }: IndustrySearchPanelProps) {
  const [industryName, setIndustryName] = useState("");
  const [targetMode, setTargetMode] = useState<TargetMode>("existing_group");
  const [selectedGroupId, setSelectedGroupId] = useState(groupId);
  const [newGroupId, setNewGroupId] = useState("");
  const [searchDepth, setSearchDepth] = useState<SearchDepth>("standard");
  const [relationTypes, setRelationTypes] = useState<string[]>(["生产", "采购", "销售", "使用", "合作", "竞争", "渠道"]);
  const [includeDigitalChina, setIncludeDigitalChina] = useState(true);
  const [manualReviewRequired, setManualReviewRequired] = useState(true);
  const [providers, setProviders] = useState<SearchProvider[]>(["tavily", "bocha"]);
  const [result, setResult] = useState<IndustrySearchResult | null>(null);
  const [pendingEpisode, setPendingEpisode] = useState<PendingEpisodeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [creatingEpisode, setCreatingEpisode] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const targetGroup = targetMode === "new_group" ? newGroupId.trim() : selectedGroupId;
  const canSubmit = industryName.trim() && targetGroup && relationTypes.length > 0 && providers.length > 0 && !loading;
  const hasPublicSources = Boolean(result?.hits.length);
  const displayedGroups = useMemo(
    () => (groups.length ? groups : [{ id: groupId, label: groupId, is_default: true }]),
    [groupId, groups],
  );

  function toggleValue<T extends string>(value: T, checked: boolean, setter: (next: T[]) => void, current: T[]) {
    if (checked && !current.includes(value)) setter([...current, value]);
    if (!checked) setter(current.filter((item) => item !== value));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!canSubmit) return;
    setLoading(true);
    setError(null);
    setPendingEpisode(null);
    try {
      setResult(await industrySearch({
        industry_name: industryName.trim(),
        group_id: selectedGroupId,
        target_mode: targetMode,
        new_group_id: targetMode === "new_group" ? newGroupId.trim() : null,
        search_depth: searchDepth,
        relation_types: relationTypes,
        include_digital_china: includeDigitalChina,
        manual_review_required: manualReviewRequired,
        providers,
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "产业扩展搜索失败");
    } finally {
      setLoading(false);
    }
  }

  async function createPendingEpisode() {
    if (!result || creatingEpisode) return;
    setCreatingEpisode(true);
    setError(null);
    try {
      setPendingEpisode(await createPendingIndustryEpisode({
        group_id: result.group_id,
        industry_name: result.industry_name,
        query: result.query,
        draft_episode_body: result.draft_episode_body,
        relation_types: result.relation_types,
        search_depth: result.search_depth,
        include_digital_china: result.include_digital_china,
        manual_review_required: result.manual_review_required,
        hits: result.hits,
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "生成待入库 Episode 失败");
    } finally {
      setCreatingEpisode(false);
    }
  }

  return (
    <section className="workspace extension-workspace">
      <header className="workspace-header">
        <div>
          <span className="section-kicker">资料扩展</span>
          <h1>产业扩展</h1>
        </div>
        <div className="extension-status">
          <span><b>{targetMode === "new_group" ? "新建" : "补充"}</b>扩展目标</span>
          <span><b>{searchDepthLabel(searchDepth)}</b>搜索深度</span>
          <span><b>{manualReviewRequired ? "需要" : "不强制"}</b>人工审核</span>
        </div>
      </header>

      <div className="extension-body">
        <form className="extension-form" onSubmit={submit}>
          <section className="extension-section">
            <div className="extension-section-head">
              <FileSearch size={16} />
              <span>扩展对象</span>
            </div>
            <label className="field-block">
              <span>产业名称</span>
              <input
                aria-label="产业名称"
                value={industryName}
                onChange={(event) => setIndustryName(event.target.value)}
                placeholder="例如：机器人产业链、汽车电子、数据中心网络"
              />
            </label>
            <div className="segmented-control" aria-label="扩展目标">
              <button type="button" aria-pressed={targetMode === "existing_group"} onClick={() => setTargetMode("existing_group")}>补充已有 group</button>
              <button type="button" aria-pressed={targetMode === "new_group"} onClick={() => setTargetMode("new_group")}>新建 group</button>
            </div>
            {targetMode === "existing_group" ? (
              <label className="field-block">
                <span>目标 group</span>
                <select aria-label="目标 group" value={selectedGroupId} onChange={(event) => setSelectedGroupId(event.target.value)}>
                  {displayedGroups.map((group) => (
                    <option key={group.id} value={group.id}>{group.label ?? group.id}</option>
                  ))}
                </select>
              </label>
            ) : (
              <label className="field-block">
                <span>新 group_id</span>
                <input
                  aria-label="新 group_id"
                  value={newGroupId}
                  onChange={(event) => setNewGroupId(event.target.value)}
                  placeholder="例如：robotics_kg"
                />
              </label>
            )}
          </section>

          <section className="extension-section">
            <div className="extension-section-head">
              <Search size={16} />
              <span>搜索策略</span>
            </div>
            <div className="depth-grid" role="radiogroup" aria-label="搜索深度">
              {DEPTH_OPTIONS.map((option) => (
                <button
                  type="button"
                  key={option.value}
                  aria-pressed={searchDepth === option.value}
                  onClick={() => setSearchDepth(option.value)}
                >
                  <strong>{option.label}</strong>
                  <span>{option.description}</span>
                </button>
              ))}
            </div>
            <div className="check-grid" aria-label="关系类型">
              {RELATION_TYPES.map((type) => (
                <label key={type}>
                  <input
                    type="checkbox"
                    checked={relationTypes.includes(type)}
                    onChange={(event) => toggleValue(type, event.target.checked, setRelationTypes, relationTypes)}
                  />
                  {type}
                </label>
              ))}
            </div>
            <div className="provider-row">
              <span>搜索来源</span>
              {(["bocha", "tavily"] as SearchProvider[]).map((provider) => (
                <label key={provider}>
                  <input
                    type="checkbox"
                    checked={providers.includes(provider)}
                    onChange={(event) => toggleValue(provider, event.target.checked, setProviders, providers)}
                  />
                  {provider === "bocha" ? "Bocha" : "Tavily"}
                </label>
              ))}
            </div>
          </section>

          <section className="extension-section">
            <div className="extension-section-head">
              <ShieldCheck size={16} />
              <span>业务与入库口径</span>
            </div>
            <label className="switch-row">
              <input type="checkbox" checked={includeDigitalChina} onChange={(event) => setIncludeDigitalChina(event.target.checked)} />
              <span>分析与神州数码关系</span>
            </label>
            <label className="switch-row">
              <input type="checkbox" checked={manualReviewRequired} onChange={(event) => setManualReviewRequired(event.target.checked)} />
              <span>需要人工审核后入库</span>
            </label>
          </section>

          {error ? <p className="extension-error" role="alert">{error}</p> : null}
          <button className="extension-submit" type="submit" disabled={!canSubmit}>
            {loading ? "正在搜索" : "搜索并生成草稿"}
          </button>
        </form>

        <section className="extension-result" aria-label="产业扩展结果">
          {result ? (
            <>
              <div className="result-head">
                <div>
                  <span>{result.group_id}</span>
                  <h2>{result.industry_name}</h2>
                </div>
                <strong>{result.ingestion_status}</strong>
              </div>
              <div className="result-metrics">
                <span><b>{searchDepthLabel(result.search_depth)}</b>搜索深度</span>
                <span><b>{result.relation_types.length}</b>关系类型</span>
                <span><b>{result.hits.length}</b>公开来源</span>
                <span><b>{result.include_digital_china ? "是" : "否"}</b>神州数码</span>
              </div>
              <div className="query-card">
                <span>实际检索式</span>
                <p>{result.query}</p>
              </div>
              <div className="draft-card">
                <span>资料草稿</span>
                <pre>{result.draft_episode_body}</pre>
              </div>
              {!hasPublicSources ? (
                <p className="extension-warning">没有公开来源时只能保留任务草稿，不能生成待入库 Episode。</p>
              ) : null}
              <button className="pending-episode-button" type="button" onClick={createPendingEpisode} disabled={creatingEpisode || !hasPublicSources}>
                <PackageCheck size={16} />
                {creatingEpisode
                  ? "正在生成待入库 Episode"
                  : hasPublicSources
                    ? "审核通过并生成待入库 Episode"
                    : "缺少公开来源，不能生成待入库 Episode"}
              </button>
              {pendingEpisode ? (
                <div className="pending-episode-card" aria-label="待入库 Episode">
                  <div className="pending-episode-head">
                    <span>{pendingEpisode.status}</span>
                    <strong>{String(pendingEpisode.episode.episode_name ?? "未命名 Episode")}</strong>
                  </div>
                  <dl>
                    <div>
                      <dt>group_id</dt>
                      <dd>{String(pendingEpisode.episode.group_id ?? "-")}</dd>
                    </div>
                    <div>
                      <dt>reference_time</dt>
                      <dd>{String(pendingEpisode.episode.reference_time ?? "-")}</dd>
                    </div>
                    <div>
                      <dt>claim_nature</dt>
                      <dd>{String(pendingEpisode.episode.claim_nature ?? "-")}</dd>
                    </div>
                    <div>
                      <dt>状态</dt>
                      <dd>{String(pendingEpisode.episode.ingestion_status ?? "-")}</dd>
                    </div>
                  </dl>
                  <pre>{String(pendingEpisode.episode.episode_body ?? "")}</pre>
                  <details>
                    <summary>查看标准 JSON</summary>
                    <pre>{JSON.stringify(pendingEpisode.episode, null, 2)}</pre>
                  </details>
                </div>
              ) : null}
              <div className="hit-list">
                {result.hits.map((hit) => (
                  <a key={hit.url} href={hit.url} target="_blank" rel="noreferrer">
                    <strong>{hit.title || hit.url}</strong>
                    <span>{hit.provider}{hit.published_at ? ` · ${hit.published_at}` : ""}</span>
                    <p>{hit.content}</p>
                  </a>
                ))}
                {!result.hits.length ? <div className="extension-empty">没有搜索结果。可能是搜索密钥未配置，或当前关键词没有可用公开资料。</div> : null}
              </div>
            </>
          ) : (
            <div className="extension-placeholder">
              <CheckCircle2 size={22} />
              <h2>配置扩展参数后生成资料草稿</h2>
              <p>这里不会自动写入正式图谱。结果会保留搜索来源、关系类型、目标 group 和人工审核口径，方便后续确认后再入库。</p>
            </div>
          )}
        </section>
      </div>
    </section>
  );
}

function searchDepthLabel(value: string): string {
  return { quick: "快速", standard: "标准", deep: "深度" }[value] ?? value;
}
