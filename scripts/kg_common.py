"""产业图谱通用工具模块。

统一各 stage 脚本重复实现的 IO、来源分级、文本清洗与搜索封装，
供 WS2/WS3/WS4 新代码使用。已跑完的 stage2/3/4 不重构，保持现状。

设计原则（务实，不过度设计）：
- 失败的搜索不再写成 title="ERROR:..." 伪结果混入证据 JSONL，
  改为记录到 data/evidence/search_failures.jsonl 并计入未完成清单。
- source_grade 以 stage4 的域名精确匹配版为准（stage2 关键词版仅作兜底）。
- clean_snippet 清洗 basis/摘要文本：删除免责声明等噪声行、句级去重、截断。
"""
from __future__ import annotations

import csv
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests

# 项目根目录（scripts/kg_common.py 的上一级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SECRET_REF = PROJECT_ROOT / "AI 工具密钥.md"
EVIDENCE_DIR = PROJECT_ROOT / "data" / "evidence"
SEARCH_FAILURES_LOG = EVIDENCE_DIR / "search_failures.jsonl"


# ---------------------------------------------------------------------------
# 时间
# ---------------------------------------------------------------------------
def now_iso() -> str:
    """当前本地时间 ISO 字符串（秒精度）。"""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# IO：CSV / JSONL
# ---------------------------------------------------------------------------
def read_csv(path) -> list[dict[str, Any]]:
    """读取 utf-8-sig CSV 为 dict 列表。"""
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fieldnames=None) -> None:
    """写入 utf-8-sig CSV。fieldnames 取首行键或显式指定。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not fieldnames:
        fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path, rows) -> None:
    """覆写写入 JSONL（整批）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_jsonl(path, rows) -> None:
    """追加写入 JSONL（断点续跑用：按公司完成即追加）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


# ---------------------------------------------------------------------------
# 来源分级（以 stage4 域名精确匹配版为准）
# ---------------------------------------------------------------------------
OFFICIAL_SOURCE_DOMAINS: tuple[str, ...] = (
    "sec.gov", "cninfo.com.cn", "sse.com.cn", "szse.cn", "gov.cn",
    "apple.com", "arm.com", "qualcomm.com", "investor.qualcomm.com",
    "mediatek.com", "synopsys.com", "cadence.com", "nvidia.com",
    "nvidianews.nvidia.com", "blogs.nvidia.com", "amd.com", "ir.amd.com",
    "tsmc.com", "pr.tsmc.com", "semiconductor.samsung.com", "samsung.com",
    "investors.gf.com", "asml.com", "newsroom.intel.com", "intel.com",
    "ir.appliedmaterials.com", "appliedmaterials.com", "investor.lamresearch.com",
    "lamresearch.com", "kla.com", "shinetsu.co.jp", "sumcosi.com",
    "amkor.com", "ir.amkor.com", "en.tfme.com", "skhynix.com",
    "investors.micron.com", "micron.com", "wolfspeed.com", "coherent.com",
    "shinko.co.jp", "ibiden.com",
    "digitalchina.com", "huawei.com", "lenovo.com", "zte.com.cn", "inspur.com",
)

HIGH_QUALITY_MEDIA_DOMAINS: tuple[str, ...] = (
    "reuters.com", "bloomberg.com", "asia.nikkei.com", "digitimes.com",
    "trendforce.com", "cnbc.com", "wsj.com", "eetimes.com",
    "businesswire.com", "prnewswire.com",
)

BLOCKED_SOURCE_DOMAINS: tuple[str, ...] = (
    "facebook.com", "instagram.com", "reddit.com", "linkedin.com",
    "x.com", "twitter.com", "youtube.com", "youtu.be", "quora.com",
    "news.ycombinator.com", "bilibili.com", "zhihu.com", "medium.com",
    "substack.com", "wikipedia.org", "scribd.com", "alibaba.com",
    "moomoo.com", "xueqiu.com",
)


def source_domain(url: str) -> str:
    """从 URL 提取主域名（去掉协议和 www.）。"""
    match = re.match(r"^[a-z]+://([^/]+)", (url or "").lower())
    if not match:
        return ""
    return match.group(1).removeprefix("www.")


def _domain_matches(domain: str, candidates: tuple[str, ...]) -> bool:
    return any(domain == c or domain.endswith(f".{c}") for c in candidates)


def source_grade(url: str, title: str = "") -> str:
    """来源等级：A 官方披露 / A- 权威媒体 / B 行业媒体 / B- 其他。

    以 stage4 的域名精确匹配为主，stage2 的关键词版（含 annual/investor 等）
    作为补充兜底，兼顾年报/PDF 链接未命中精确域名的情况。
    """
    domain = source_domain(url)
    if _domain_matches(domain, OFFICIAL_SOURCE_DOMAINS):
        return "A"
    if _domain_matches(domain, HIGH_QUALITY_MEDIA_DOMAINS):
        return "A-"
    combined = f"{url} {title}".lower()
    if any(kw in combined for kw in ("annual", "investor", "公司公告", "年报")):
        return "A"
    if any(kw in combined for kw in ("trendforce", "counterpoint", "idc", "gartner", "semi.org")):
        return "A-"
    if any(kw in combined for kw in ("eastmoney", "sina", "qianzhan", "pedaily", "yicai", "eet", "36kr", "ithome")):
        return "B"
    return "B-"


def is_blocked_source(url: str) -> bool:
    """是否为应剔除的来源（社交/论坛/百科等）。"""
    return _domain_matches(source_domain(url), BLOCKED_SOURCE_DOMAINS)


# ---------------------------------------------------------------------------
# 文本清洗
# ---------------------------------------------------------------------------
_NOISE_LINE_PREFIXES = (
    "免责声明", "声明:", "声明：", "来源:", "来源：", "答复时间:",
    "答复时间：", "本信息由", "下载", "扫码", "点击查看", "风险提示",
    "证券之星", "同花顺", "东方财富网", "新浪财经",
)

_SENTENCE_SPLITS = "。；;！!？?\n"


def clean_snippet(text: str, max_chars: int = 200, max_sentences: int = 2) -> str:
    """清洗搜索摘要/basis 文本：去噪声行、句级去重、截断。"""
    if not text:
        return ""
    # 先按句切分（兼容无换行的整段文本），再过滤含噪声标记的句子
    joined = str(text).strip()

    def _split_sentences(text: str) -> list[str]:
        sentences: list[str] = []
        buf = ""
        for ch in text:
            buf += ch
            if ch in _SENTENCE_SPLITS:
                if buf.strip():
                    sentences.append(buf.strip())
                buf = ""
        if buf.strip():
            sentences.append(buf.strip())
        return sentences

    raw_sentences = _split_sentences(joined)
    # 去噪声句（噪声标记出现在句中任意位置即剔除整句）+ 句级去重
    sentences: list[str] = []
    seen: set[str] = set()
    for s in raw_sentences:
        low = s.lower()
        if any(marker.lower() in low for marker in _NOISE_LINE_PREFIXES):
            continue
        if s in seen:
            continue
        seen.add(s)
        sentences.append(s)

    out = "".join(sentences[:max_sentences])
    if len(out) > max_chars:
        out = out[: max_chars - 1] + "…"
    return out


# ---------------------------------------------------------------------------
# 搜索封装（带重试/退避，失败不污染证据集）
# ---------------------------------------------------------------------------
def parse_key_from_secret(section: str, env: str) -> str | None:
    """从根目录 AI 工具密钥.md 解析密钥，环境变量优先。"""
    if os.getenv(env):
        return os.getenv(env)
    if not SECRET_REF.exists():
        return None
    text = SECRET_REF.read_text(encoding="utf-8", errors="ignore")
    match = re.search(rf"{re.escape(section)}:\s*[\s\S]*?key:\s*\"([^\"]+)\"", text)
    return match.group(1) if match else None


def _log_search_failure(tool: str, query: str, error: str) -> None:
    """记录搜索失败到独立日志，不写入证据 JSONL。"""
    try:
        SEARCH_FAILURES_LOG.parent.mkdir(parents=True, exist_ok=True)
        with SEARCH_FAILURES_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(
                {"search_tool": tool, "query": query, "error": error, "retrieved_at": now_iso()},
                ensure_ascii=False,
            ) + "\n")
    except OSError:
        pass


def search_bocha(query: str, count: int = 6, retries: int = 3) -> list[dict[str, Any]]:
    """Bocha 中文搜索，指数退避重试，失败返回空列表并记日志。"""
    key = parse_key_from_secret("bocha", "BOCHA_API_KEY")
    if not key:
        _log_search_failure("Bocha", query, "missing API key")
        return []
    for attempt in range(retries):
        try:
            resp = requests.post(
                "https://api.bochaai.com/v1/web-search",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"query": query, "freshness": "noLimit", "summary": True, "count": count},
                timeout=45,
            )
            if resp.status_code == 429 and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data", {}).get("webPages", {}).get("value", []) or []
            return [
                {
                    "search_tool": "Bocha",
                    "query": query,
                    "title": item.get("name", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("summary") or item.get("snippet") or "",
                    "publish_date": item.get("datePublished") or "",
                }
                for item in items[:count]
            ]
        except Exception as exc:  # noqa: BLE001
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            _log_search_failure("Bocha", query, f"{type(exc).__name__}: {exc}")
            return []
    return []


def search_tavily(query: str, count: int = 6, retries: int = 3) -> list[dict[str, Any]]:
    """Tavily 英文搜索，指数退避重试，失败返回空列表并记日志。"""
    key = parse_key_from_secret("tavily", "TAVILY_API_KEY")
    if not key:
        _log_search_failure("Tavily", query, "missing API key")
        return []
    for attempt in range(retries):
        try:
            resp = requests.post(
                "https://api.tavily.com/search",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "query": query,
                    "search_depth": "basic",
                    "topic": "general",
                    "max_results": count,
                    "include_answer": False,
                },
                timeout=45,
            )
            if resp.status_code == 429 and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            data = resp.json()
            return [
                {
                    "search_tool": "Tavily",
                    "query": query,
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", ""),
                    "publish_date": item.get("published_date") or "",
                }
                for item in data.get("results", [])[:count]
            ]
        except Exception as exc:  # noqa: BLE001
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            _log_search_failure("Tavily", query, f"{type(exc).__name__}: {exc}")
            return []
    return []


def pick_search_tool(query: str) -> str:
    """含中文走 Bocha，否则走 Tavily。"""
    return "Bocha" if re.search(r"[一-鿿]", query) else "Tavily"


def search_with_retry(query: str, count: int = 6) -> list[dict[str, Any]]:
    """按 query 语言自动选工具并搜索。"""
    if pick_search_tool(query) == "Bocha":
        return search_bocha(query, count=count)
    return search_tavily(query, count=count)


# ---------------------------------------------------------------------------
# 别名匹配（中英文词边界）
# ---------------------------------------------------------------------------
def alias_matches(text: str, alias: str) -> bool:
    """中文子串匹配；英文按词边界匹配（大小写不敏感）。"""
    if not alias:
        return False
    if re.search(r"[一-鿿]", alias):
        return alias in (text or "")
    pattern = rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])"
    return re.search(pattern, text or "", flags=re.IGNORECASE) is not None


def has_any_term(text: str, terms: Iterable[str]) -> bool:
    """文本是否命中任一别名/词。"""
    return any(alias_matches(text, t) for t in terms)


if __name__ == "__main__":
    print(f"PROJECT_ROOT = {PROJECT_ROOT}")
    print(f"SECRET_REF exists = {SECRET_REF.exists()}")
    print(f"bocha key available = {bool(parse_key_from_secret('bocha', 'BOCHA_API_KEY'))}")
    print(f"source_grade cninfo = {source_grade('https://www.cninfo.com.cn/xxx')}")
    print(f"source_grade reuters = {source_grade('https://www.reuters.com/xxx')}")
    print(f"source_grade blog    = {source_grade('https://blog.example.com/xxx')}")
    sample = "免责声明:本信息由证券之星提供。来源:互动易 答复时间:2025/8/20。神州数码与华为签署战略合作协议，联合发布解决方案。神州数码与华为签署战略合作协议，联合发布解决方案。"
    print(f"clean_snippet = {clean_snippet(sample)}")
