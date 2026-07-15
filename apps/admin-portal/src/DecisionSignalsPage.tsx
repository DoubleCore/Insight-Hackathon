import { FormEvent, useState } from "react";
import { FileText, Link, Type, Upload } from "lucide-react";

import { importDecisionSignal } from "./api";
import type {
  DecisionSignalCategory,
  DecisionSignalImportResult,
  DecisionSignalSourceType,
} from "./types";

const CATEGORY_OPTIONS: Array<{ value: DecisionSignalCategory; label: string }> = [
  { value: "policy", label: "政策风向" },
  { value: "technology", label: "技术趋势" },
  { value: "industry_rule", label: "行业规律" },
  { value: "business_implication", label: "企业战略含义" },
];

const SOURCE_OPTIONS: Array<{ value: DecisionSignalSourceType; label: string; icon: typeof Type }> = [
  { value: "text", label: "手动文本", icon: Type },
  { value: "link", label: "链接", icon: Link },
  { value: "document", label: "文档", icon: FileText },
];

export default function DecisionSignalsPage({ groupId }: { groupId: string }) {
  const [sourceType, setSourceType] = useState<DecisionSignalSourceType>("text");
  const [category, setCategory] = useState<DecisionSignalCategory>("technology");
  const [title, setTitle] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [keywords, setKeywords] = useState("");
  const [content, setContent] = useState("");
  const [industryImpact, setIndustryImpact] = useState("");
  const [dcImplication, setDcImplication] = useState("");
  const [notes, setNotes] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<DecisionSignalImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const canSubmit = Boolean(
    title.trim()
    && !loading
    && (
      (sourceType === "document" && file)
      || (sourceType === "link" && sourceUrl.trim())
      || (sourceType === "text" && content.trim())
    ),
  );

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!canSubmit) return;
    setLoading(true);
    setError(null);
    const form = new FormData();
    form.set("group_id", groupId);
    form.set("category", category);
    form.set("source_type", sourceType);
    form.set("title", title.trim());
    form.set("source_url", sourceUrl.trim());
    form.set("keywords", keywords.trim());
    form.set("content", content.trim());
    form.set("industry_impact", industryImpact.trim());
    form.set("dc_implication", dcImplication.trim());
    form.set("notes", notes.trim());
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
        <div className="decision-status">
          <span><b>{groupId}</b>当前 group</span>
          <span><b>决策信号层</b>固定 saga</span>
          <span><b>{CATEGORY_OPTIONS.find((item) => item.value === category)?.label}</b>资料分类</span>
        </div>
      </header>

      <div className="decision-body">
        <form className="decision-form" onSubmit={submit}>
          <section className="decision-section">
            <div className="decision-section-head">
              <Upload size={16} />
              <span>资料来源</span>
            </div>
            <div className="source-type-grid" aria-label="上传方式">
              {SOURCE_OPTIONS.map((option) => {
                const Icon = option.icon;
                return (
                  <button
                    type="button"
                    key={option.value}
                    aria-pressed={sourceType === option.value}
                    onClick={() => setSourceType(option.value)}
                  >
                    <Icon size={15} />
                    {option.label}
                  </button>
                );
              })}
            </div>
            <label className="field-block">
              <span>资料分类</span>
              <select aria-label="资料分类" value={category} onChange={(event) => setCategory(event.target.value as DecisionSignalCategory)}>
                {CATEGORY_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </label>
            <label className="field-block">
              <span>标题</span>
              <input aria-label="标题" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="例如：摩尔定律放缓与先进封装趋势" />
            </label>
            <label className="field-block">
              <span>关键词</span>
              <input aria-label="关键词" value={keywords} onChange={(event) => setKeywords(event.target.value)} placeholder="摩尔定律, Chiplet, 先进封装" />
            </label>
            {sourceType === "link" ? (
              <label className="field-block">
                <span>来源链接</span>
                <input aria-label="来源链接" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="https://..." />
              </label>
            ) : null}
            {sourceType === "document" ? (
              <label className="field-block">
                <span>上传文档</span>
                <input aria-label="上传文档" type="file" accept=".txt,.md,.pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
              </label>
            ) : null}
            {sourceType !== "document" ? (
              <label className="field-block decision-textarea">
                <span>核心内容</span>
                <textarea aria-label="核心内容" value={content} onChange={(event) => setContent(event.target.value)} placeholder="粘贴政策、论文摘要、技术趋势说明。链接模式下可留空，由后端抓取基础文本。" />
              </label>
            ) : null}
          </section>

          <section className="decision-section">
            <div className="decision-section-head">
              <FileText size={16} />
              <span>辅助字段</span>
            </div>
            <label className="field-block decision-textarea compact">
              <span>对产业链的可能影响</span>
              <textarea aria-label="对产业链的可能影响" value={industryImpact} onChange={(event) => setIndustryImpact(event.target.value)} placeholder="例如：先进封装、HBM、AI 服务器需求增强。" />
            </label>
            <label className="field-block decision-textarea compact">
              <span>对神州数码业务判断的可能影响</span>
              <textarea aria-label="对神州数码业务判断的可能影响" value={dcImplication} onChange={(event) => setDcImplication(event.target.value)} placeholder="例如：支撑 AI 基础设施、算力服务和供应链合作判断。" />
            </label>
            <label className="field-block decision-textarea compact">
              <span>备注</span>
              <textarea aria-label="备注" value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="资料来源、可信度、使用场景等补充说明。" />
            </label>
          </section>

          {error ? <p className="extension-error" role="alert">{error}</p> : null}
          <button className="extension-submit" type="submit" disabled={!canSubmit}>
            {loading ? "正在导入" : "上传到决策信号层"}
          </button>
        </form>

        <section className="decision-result" aria-label="决策资料导入结果">
          {result ? (
            <>
              <div className="result-head">
                <div>
                  <span>{result.group_id} / {result.saga}</span>
                  <h2>{result.title}</h2>
                </div>
                <strong>{result.source_type}</strong>
              </div>
              <div className="result-metrics">
                <span><b>{result.category}</b>分类</span>
                <span><b>{result.source_type}</b>来源</span>
                <span><b>{result.episode_uuid}</b>episode_uuid</span>
                <span><b>{result.evidence_id}</b>evidence_id</span>
                <span><b>{result.source_url ?? "-"}</b>链接</span>
              </div>
              {result.fallback_reason ? (
                <p className="decision-fallback">Graphiti 抽取降级，已保存原始资料用于召回：{result.fallback_reason}</p>
              ) : null}
              <div className="draft-card">
                <span>入库内容预览</span>
                <pre>{result.content_preview}</pre>
              </div>
            </>
          ) : (
            <div className="extension-placeholder">
              <FileText size={22} />
              <h2>把政策、论文和技术趋势变成可召回资料</h2>
              <p>资料会写入当前 group，并挂到固定 saga“决策信号层”。问答时可以和产业链、企业关系一起被召回，用于解释政策背景、技术风向和业务判断依据。</p>
            </div>
          )}
        </section>
      </div>
    </section>
  );
}
