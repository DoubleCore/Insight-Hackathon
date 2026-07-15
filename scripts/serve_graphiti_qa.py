from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
QUERY_SCRIPT = ROOT / "scripts" / "query_graphiti.py"

HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>半导体 Graphiti 问答</title>
  <style>
    :root {
      --bg: #f6f7f9;
      --panel: #ffffff;
      --line: #d9dee7;
      --text: #17202a;
      --muted: #627084;
      --accent: #1f6feb;
      --accent-strong: #1757b8;
      --good: #126b45;
      --warn: #8a5a00;
      --shadow: 0 12px 30px rgba(15, 23, 42, .08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--text);
      background: var(--bg);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
      letter-spacing: 0;
    }
    .app {
      min-height: 100vh;
      display: grid;
      grid-template-columns: 280px minmax(0, 1fr);
    }
    aside {
      border-right: 1px solid var(--line);
      background: #eef1f5;
      padding: 20px 16px;
    }
    main {
      padding: 24px;
      display: grid;
      grid-template-rows: auto auto minmax(0, 1fr);
      gap: 16px;
    }
    h1 {
      font-size: 22px;
      line-height: 1.25;
      margin: 0 0 6px;
      font-weight: 700;
    }
    .sub {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.55;
    }
    .status {
      margin-top: 18px;
      padding: 12px;
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      font-size: 13px;
      line-height: 1.6;
    }
    .status b { color: var(--good); }
    .samples {
      margin-top: 18px;
      display: grid;
      gap: 8px;
    }
    .samples button {
      width: 100%;
      text-align: left;
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--text);
      border-radius: 8px;
      padding: 10px 11px;
      cursor: pointer;
      line-height: 1.45;
      font-size: 13px;
    }
    .samples button:hover { border-color: var(--accent); }
    .query {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      box-shadow: var(--shadow);
    }
    label {
      display: block;
      font-size: 13px;
      color: var(--muted);
      margin-bottom: 8px;
    }
    textarea {
      width: 100%;
      min-height: 94px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      font: inherit;
      font-size: 15px;
      line-height: 1.55;
      outline: none;
      background: #fbfcfe;
    }
    textarea:focus { border-color: var(--accent); background: #fff; }
    .controls {
      margin-top: 12px;
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
    }
    .controls input {
      width: 84px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 9px 10px;
      font: inherit;
    }
    .primary {
      border: 0;
      border-radius: 8px;
      background: var(--accent);
      color: #fff;
      padding: 10px 16px;
      font-weight: 650;
      cursor: pointer;
      min-width: 112px;
    }
    .primary:hover { background: var(--accent-strong); }
    .primary:disabled {
      opacity: .58;
      cursor: wait;
    }
    .meta {
      color: var(--muted);
      font-size: 13px;
    }
    .results {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(360px, .9fr);
      gap: 16px;
      min-height: 0;
    }
    section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      min-height: 260px;
      overflow: auto;
      box-shadow: var(--shadow);
    }
    h2 {
      margin: 0 0 12px;
      font-size: 16px;
      line-height: 1.3;
    }
    .answer {
      white-space: pre-wrap;
      line-height: 1.7;
      font-size: 15px;
    }
    .facts {
      white-space: pre-wrap;
      color: #263442;
      line-height: 1.55;
      font-family: "Cascadia Mono", Consolas, "Microsoft YaHei", monospace;
      font-size: 13px;
    }
    .error {
      color: #9d1c1c;
      white-space: pre-wrap;
    }
    @media (max-width: 900px) {
      .app { grid-template-columns: 1fr; }
      aside { border-right: 0; border-bottom: 1px solid var(--line); }
      .results { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside>
      <h1>半导体 Graphiti 问答</h1>
      <div class="sub">基于现有 Graphiti 图谱检索事实，并调用 DeepSeek 生成答案。</div>
      <div class="status">
        <div><b>group_id</b> semiconductor_dc_kg</div>
        <div><b>规模</b> 818 episodes / 1376 facts</div>
        <div><b>检索</b> Graphiti semantic + 词面补召回</div>
        <div><b>生成</b> DeepSeek</div>
      </div>
      <div class="samples">
        <button data-q="神州数码和浪潮信息有什么关系？">神州数码和浪潮信息有什么关系？</button>
        <button data-q="神州数码和沐曦、壁仞、海思有什么关系？">神州数码和沐曦、壁仞、海思有什么关系？</button>
        <button data-q="神州数码在AI服务器和数据中心基础设施能做什么？">神州数码在AI服务器和数据中心基础设施能做什么？</button>
        <button data-q="哪些公司和神州数码是公开可验证关系，哪些还需要内部验证？">公开关系和待验证关系分别有哪些？</button>
        <button data-q="AI/GPU算力芯片有哪些龙头公司？">AI/GPU算力芯片有哪些龙头公司？</button>
        <button data-q="NVIDIA和浪潮信息、联想、Supermicro有什么关系？">NVIDIA和服务器厂商有什么关系？</button>
        <button data-q="晶圆代工和先进封装相关公司有哪些关系？">晶圆代工和先进封装相关公司有哪些关系？</button>
        <button data-q="这个图谱里哪些关系不能当作已确认客户或交易关系？">哪些关系不能当作已确认客户？</button>
      </div>
    </aside>
    <main>
      <div class="query">
        <label for="question">问题</label>
        <textarea id="question">神州数码和浪潮信息有什么关系？</textarea>
        <div class="controls">
          <label for="limit" style="margin:0;">事实数</label>
          <input id="limit" type="number" min="3" max="30" value="10" />
          <button id="ask" class="primary">查询</button>
          <span id="meta" class="meta">等待查询</span>
        </div>
      </div>
      <div class="results">
        <section>
          <h2>答案</h2>
          <div id="answer" class="answer"></div>
        </section>
        <section>
          <h2>Graphiti 检索事实</h2>
          <div id="facts" class="facts"></div>
        </section>
      </div>
    </main>
  </div>
  <script>
    const q = document.getElementById('question');
    const limit = document.getElementById('limit');
    const ask = document.getElementById('ask');
    const answer = document.getElementById('answer');
    const facts = document.getElementById('facts');
    const meta = document.getElementById('meta');

    function splitOutput(text) {
      const marker = 'Graphiti 检索事实：';
      const idx = text.indexOf(marker);
      let answerText = text;
      let factsText = '';
      if (idx >= 0) {
        answerText = text.slice(0, idx).trim();
        factsText = text.slice(idx + marker.length).trim();
      }
      answerText = answerText.replace(/^问题：[\s\S]*?\n\n回答：\n?/, '').trim();
      return { answerText, factsText };
    }

    async function runQuery() {
      const question = q.value.trim();
      if (!question) return;
      ask.disabled = true;
      answer.textContent = '';
      facts.textContent = '';
      meta.textContent = '查询中...';
      const started = performance.now();
      try {
        const res = await fetch('/api/query', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question, num_results: Number(limit.value) || 10 })
        });
        const data = await res.json();
        if (!data.ok) {
          answer.innerHTML = '<span class="error"></span>';
          answer.querySelector('span').textContent = data.error || data.stderr || '查询失败';
          facts.textContent = data.stdout || '';
          return;
        }
        const parts = splitOutput(data.stdout || '');
        answer.textContent = parts.answerText;
        facts.textContent = parts.factsText || data.stdout;
        meta.textContent = `完成，用时 ${((performance.now() - started) / 1000).toFixed(1)}s`;
      } catch (err) {
        answer.innerHTML = '<span class="error"></span>';
        answer.querySelector('span').textContent = String(err);
        meta.textContent = '查询失败';
      } finally {
        ask.disabled = false;
      }
    }

    document.querySelectorAll('.samples button').forEach((btn) => {
      btn.addEventListener('click', () => {
        q.value = btn.dataset.q || '';
        runQuery();
      });
    });
    ask.addEventListener('click', runQuery);
    q.addEventListener('keydown', (event) => {
      if (event.ctrlKey && event.key === 'Enter') runQuery();
    });
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "GraphitiQAServer/1.0"

    def send_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self.send_json(200, {"ok": True})
            return
        if path != "/":
            self.send_error(404)
            return
        body = HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/query":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        question = str(payload.get("question") or "").strip()
        num_results = int(payload.get("num_results") or 10)
        if not question:
            self.send_json(400, {"ok": False, "error": "question is required"})
            return
        command = [
            sys.executable,
            "-X",
            "utf8",
            str(QUERY_SCRIPT),
            question,
            "--num-results",
            str(num_results),
        ]
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            completed = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=240,
            )
        except subprocess.TimeoutExpired:
            self.send_json(504, {"ok": False, "error": "query timeout"})
            return
        self.send_json(
            200 if completed.returncode == 0 else 500,
            {
                "ok": completed.returncode == 0,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "returncode": completed.returncode,
            },
        )

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Graphiti QA frontend running at http://{args.host}:{args.port}/")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
