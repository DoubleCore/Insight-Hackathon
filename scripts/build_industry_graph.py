"""
半导体产业链知识图谱一键构建脚本

功能：
1. 调用 Bocha + Tavily 搜索半导体产业链相关信息
2. 将搜索结果喂给 Graphiti 自动提取实体关系
3. 存入 Neo4j 图数据库，用 Neo4j Browser 可视化

使用前准备：
1. 启动 Neo4j（默认 bolt://localhost:7687，用户名 neo4j，密码 password）
2. 安装依赖：pip install graphiti-core requests python-dotenv
3. 配置 LLM（默认用 DeepSeek，也可以改成 OpenAI）

运行：
    python scripts/build_industry_graph.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

# ============================================================
# 配置
# ============================================================

ROOT = Path(__file__).resolve().parents[1]
SECRET_FILE = ROOT / "AI 工具密钥.md"

# Neo4j 连接配置
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# 搜索配置
SEARCH_QUERIES = {
    "国内": [
        "中国半导体产业链 上下游 龙头企业 2025 2026",
        "半导体设备 材料 设计 制造 封测 产业链分析",
        "国产替代 半导体 核心公司 市场份额",
    ],
    "海外": [
        "global semiconductor supply chain leaders foundry equipment materials 2025",
        "semiconductor industry value chain TSMC ASML NVIDIA Samsung",
        "semiconductor equipment materials market share leaders 2025",
    ],
}

MAX_RESULTS_PER_QUERY = 5


# ============================================================
# 工具函数：读取密钥
# ============================================================

def parse_key(section: str, env_var: str) -> str | None:
    """从密钥文件或环境变量中读取 API key"""
    # 优先从环境变量读
    if os.getenv(env_var):
        return os.getenv(env_var)

    # 从密钥文件读
    if not SECRET_FILE.exists():
        return None

    text = SECRET_FILE.read_text(encoding="utf-8", errors="ignore")
    match = re.search(rf"{re.escape(section)}:\s*[\s\S]*?key:\s*\"([^\"]+)\"", text)
    return match.group(1) if match else None


def parse_base_url(section: str) -> str | None:
    """从密钥文件中读取 base_url"""
    if not SECRET_FILE.exists():
        return None

    text = SECRET_FILE.read_text(encoding="utf-8", errors="ignore")
    match = re.search(rf"{re.escape(section)}:\s*[\s\S]*?base_url:\s*\"([^\"]+)\"", text)
    return match.group(1) if match else None


# ============================================================
# 搜索：Bocha
# ============================================================

def search_bocha(query: str, count: int = 5) -> list[dict[str, Any]]:
    """调用 Bocha API 搜索中文内容"""
    key = parse_key("bocha", "BOCHA_API_KEY")
    if not key:
        print("⚠️  未找到 Bocha API key，跳过 Bocha 搜索")
        return []

    try:
        resp = requests.post(
            "https://api.bochaai.com/v1/web-search",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"query": query, "freshness": "noLimit", "summary": True, "count": count},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", {}).get("webPages", {}).get("value", []) or []

        results = []
        for item in items[:count]:
            results.append({
                "title": item.get("name", ""),
                "url": item.get("url", ""),
                "snippet": item.get("summary") or item.get("snippet") or "",
                "source": "Bocha",
            })
        return results
    except Exception as e:
        print(f"⚠️  Bocha 搜索失败: {e}")
        return []


# ============================================================
# 搜索：Tavily
# ============================================================

def search_tavily(query: str, count: int = 5) -> list[dict[str, Any]]:
    """调用 Tavily API 搜索英文内容"""
    key = parse_key("tavily", "TAVILY_API_KEY")
    if not key:
        print("⚠️  未找到 Tavily API key，跳过 Tavily 搜索")
        return []

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
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("results", [])[:count]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", ""),
                "source": "Tavily",
            })
        return results
    except Exception as e:
        print(f"⚠️  Tavily 搜索失败: {e}")
        return []


# ============================================================
# 执行所有搜索
# ============================================================

def run_all_searches() -> list[dict[str, Any]]:
    """执行所有搜索，返回合并后的结果"""
    all_results = []
    seen_urls = set()

    print("\n" + "=" * 60)
    print("🔍 开始搜索半导体产业链信息...")
    print("=" * 60)

    # 中文搜索（Bocha）
    print("\n📱 中文搜索（Bocha）...")
    for query in SEARCH_QUERIES["国内"]:
        print(f"  - {query}")
        results = search_bocha(query, MAX_RESULTS_PER_QUERY)
        for r in results:
            if r["url"] and r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                all_results.append(r)
        time.sleep(0.5)

    # 英文搜索（Tavily）
    print("\n🌐 英文搜索（Tavily）...")
    for query in SEARCH_QUERIES["海外"]:
        print(f"  - {query}")
        results = search_tavily(query, MAX_RESULTS_PER_QUERY)
        for r in results:
            if r["url"] and r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                all_results.append(r)
        time.sleep(0.5)

    print(f"\n✅ 搜索完成，共找到 {len(all_results)} 条结果")
    return all_results


# ============================================================
# 构建知识图谱：Graphiti
# ============================================================

def build_graph(search_results: list[dict[str, Any]]) -> dict[str, Any]:
    """使用 Graphiti 构建知识图谱"""
    try:
        from graphiti_core import Graphiti
        from graphiti_core.nodes import EpisodeType
    except ImportError:
        print("\n❌ 未安装 graphiti-core，请先运行：pip install graphiti-core")
        print("   或者跳过建图，只保存搜索结果。")
        return {"status": "skipped", "reason": "graphiti-core not installed"}

    print("\n" + "=" * 60)
    print("🧠 开始构建知识图谱（Graphiti + Neo4j）...")
    print("=" * 60)

    # ========== 1. 配置 LLM（DeepSeek）==========
    deepseek_key = parse_key("deepseek", "DEEPSEEK_API_KEY")
    deepseek_base_url = parse_base_url("deepseek") or "https://api.deepseek.com/v1"

    llm_client = None
    llm_config = None

    if deepseek_key:
        print("\n🤖 配置 LLM：DeepSeek")
        try:
            from graphiti_core.llm_client.config import LLMConfig
            from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient

            llm_config = LLMConfig(
                api_key=deepseek_key,
                model="deepseek-chat",
                small_model="deepseek-chat",
                base_url=deepseek_base_url,
            )
            # 重要：DeepSeek 不支持 json_schema，必须用 json_object 模式
            llm_client = OpenAIGenericClient(
                config=llm_config,
                structured_output_mode="json_object",
            )
            print(f"   ✅ LLM 配置成功：deepseek-chat")
        except Exception as e:
            print(f"   ❌ LLM 配置失败: {e}")
    else:
        print("   ⚠️  未找到 DeepSeek API key")

    # ========== 2. 配置 Embedding（硅基流动 + BGE 中文嵌入）==========
    siliconflow_key = parse_key("siliconflow", "SILICONFLOW_API_KEY")
    siliconflow_base_url = parse_base_url("siliconflow") or "https://api.siliconflow.cn/v1"

    embedder = None

    if siliconflow_key:
        print("\n📐 配置嵌入模型：硅基流动 + BGE 中文嵌入")
        try:
            from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig

            embedder = OpenAIEmbedder(
                config=OpenAIEmbedderConfig(
                    api_key=siliconflow_key,
                    embedding_model="BAAI/bge-large-zh-v1.5",
                    embedding_dim=1024,
                    base_url=siliconflow_base_url,
                )
            )
            print(f"   ✅ Embedding 配置成功：BAAI/bge-large-zh-v1.5 (1024 维)")
        except Exception as e:
            print(f"   ❌ Embedding 配置失败: {e}")
    else:
        print("   ⚠️  未找到 SiliconFlow API key")

    # ========== 3. 配置 Cross Encoder（复用 LLM）==========
    cross_encoder = None

    if llm_client and llm_config:
        print("\n🔄 配置 Cross Encoder：复用 DeepSeek LLM")
        try:
            from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient

            cross_encoder = OpenAIRerankerClient(
                config=llm_config,
                client=llm_client,  # 复用同一个 LLM client
            )
            print(f"   ✅ Cross Encoder 配置成功（复用 LLM）")
        except Exception as e:
            print(f"   ⚠️  Cross Encoder 配置失败: {e}")
            print("      不影响建图，只是搜索结果不会重排序")

    # ========== 4. 初始化 Graphiti ==========
    print("\n🔗 连接 Neo4j 并初始化 Graphiti...")

    try:
        graphiti = Graphiti(
            NEO4J_URI,
            NEO4J_USER,
            NEO4J_PASSWORD,
            llm_client=llm_client,
            embedder=embedder,
            cross_encoder=cross_encoder,
        )
        print(f"   ✅ Graphiti 初始化成功")
        print(f"   Neo4j 地址：{NEO4J_URI}")
    except Exception as e:
        print(f"\n❌ Graphiti 初始化失败: {e}")
        print("   请确保 Neo4j 已启动，并且连接配置正确")
        print(f"   Neo4j URI: {NEO4J_URI}")
        print(f"   Neo4j User: {NEO4J_USER}")
        return {"status": "error", "reason": f"Graphiti init failed: {e}"}

    try:
        # 添加搜索结果到图谱
        print(f"\n📥 正在处理 {len(search_results)} 条搜索结果...")
        success_count = 0
        fail_count = 0

        import asyncio

        async def add_episodes():
            nonlocal success_count, fail_count
            for i, result in enumerate(search_results):
                # 把标题和摘要拼起来作为内容
                content = f"标题：{result['title']}\n\n内容摘要：{result['snippet']}"
                source = result.get("url", "")

                try:
                    await graphiti.add_episode(
                        name=f"Search Result {i+1}: {result['title'][:50]}",
                        episode_body=content,
                        source=EpisodeType.text,
                        source_description=f"来自 {result['source']} 的搜索结果: {source}",
                        reference_time=datetime.now(timezone.utc),
                    )
                    success_count += 1
                    print(f"  ✅ [{i+1}/{len(search_results)}] {result['title'][:40]}...")
                except Exception as e:
                    fail_count += 1
                    print(f"  ❌ [{i+1}/{len(search_results)}] 失败: {str(e)[:50]}")

                # 避免请求太快
                if (i + 1) % 3 == 0:
                    time.sleep(1)

        asyncio.run(add_episodes())

        print(f"\n✅ 建图完成！成功 {success_count} 条，失败 {fail_count} 条")

        # 简单统计
        try:
            # 尝试查询节点数
            from graphiti_core.helpers import get_driver
            driver = get_driver()
            with driver.session() as session:
                node_count = session.run("MATCH (n:EntityNode) RETURN count(n) as count").single()["count"]
                edge_count = session.run("MATCH ()-[e:ENTITY_EDGE]->() RETURN count(e) as count").single()["count"]
                print(f"\n📊 图谱统计：")
                print(f"   实体节点数：{node_count}")
                print(f"   关系边数：{edge_count}")
        except Exception:
            pass

        return {
            "status": "success",
            "success_count": success_count,
            "fail_count": fail_count,
        }

    finally:
        # 关闭连接
        try:
            import asyncio
            asyncio.run(graphiti.close())
        except Exception:
            pass


# ============================================================
# 保存搜索结果
# ============================================================

def save_search_results(results: list[dict[str, Any]]) -> Path:
    """保存搜索结果到 JSON 文件"""
    output_dir = ROOT / "data" / "search_results"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"semiconductor_search_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n💾 搜索结果已保存到：{output_file}")
    return output_file


# ============================================================
# 主函数
# ============================================================

def main():
    print("🚀 半导体产业链知识图谱构建工具")
    print("=" * 60)

    # 1. 搜索
    search_results = run_all_searches()

    if not search_results:
        print("\n❌ 没有搜索到任何结果，请检查 API key 是否正确")
        return

    # 2. 保存搜索结果
    save_search_results(search_results)

    # 3. 构建图谱
    print("\n" + "=" * 60)
    print("是否开始构建知识图谱？（需要 Neo4j 已启动）")
    print("输入 y 继续，其他键跳过建图")

    # 简单的交互确认
    if "--no-graph" in sys.argv:
        print("\n⏭️  跳过建图（--no-graph 参数）")
        return

    try:
        response = input("\n是否继续建图？(y/n): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        response = "n"

    if response in ("y", "yes", "是"):
        result = build_graph(search_results)

        if result.get("status") == "success":
            print("\n" + "=" * 60)
            print("🎉 图谱构建完成！")
            print("=" * 60)
            print(f"\n📊 查看图谱：")
            print(f"   打开 Neo4j Browser: http://localhost:7474")
            print(f"   连接地址：{NEO4J_URI}")
            print(f"   用户名：{NEO4J_USER}")
            print(f"\n🔍 示例查询：")
            print(f"   查看所有节点：MATCH (n) RETURN n LIMIT 50")
            print(f"   查看所有关系：MATCH ()-[r]->() RETURN r LIMIT 50")
            print(f"   查看某个公司的关系：MATCH (n:EntityNode {{name: '中芯国际'}})-[r]-(m) RETURN n, r, m")
        else:
            print(f"\n⚠️  建图未完成：{result.get('reason', '未知原因')}")
    else:
        print("\n⏭️  跳过建图")
        print("   可以稍后手动运行建图，或者查看保存的搜索结果")

    print("\n👋 完成！")


if __name__ == "__main__":
    main()
