from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPHITI_ROOT = ROOT / "graphiti-main" / "graphiti-main"
sys.path.insert(0, str(GRAPHITI_ROOT))

from graphiti_core import Graphiti  # type: ignore  # noqa: E402
from graphiti_core.cross_encoder.openai_reranker_client import (  # type: ignore  # noqa: E402
    OpenAIRerankerClient,
)
from graphiti_core.embedder.openai import (  # type: ignore  # noqa: E402
    OpenAIEmbedder,
    OpenAIEmbedderConfig,
)
from graphiti_core.llm_client.config import LLMConfig  # type: ignore  # noqa: E402
from graphiti_core.llm_client.openai_generic_client import (  # type: ignore  # noqa: E402
    OpenAIGenericClient,
)
from graphiti_core.nodes import EpisodeType  # type: ignore  # noqa: E402

DEFAULT_EPISODES = ROOT / "data" / "graphiti" / "semiconductor_episodes.jsonl"
DEFAULT_FAILURE_LOG = ROOT / "data" / "graphiti" / "import_failures.jsonl"
LAYER_METADATA_FIELDS = [
    "legacy_saga_key",
    "saga_key",
    "saga_name",
    "layer_id",
    "layer_name",
    "fact_set_name",
    "fact_set_type",
    "fact_set_description",
    "display_name",
]


def parse_reference_time(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def episode_type(value: str) -> EpisodeType:
    if value == "json":
        return EpisodeType.json
    if value == "message":
        return EpisodeType.message
    return EpisodeType.text


def load_episodes(path: Path, limit: int | None = None) -> list[dict[str, str]]:
    episodes: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            episodes.append(json.loads(line))
            if limit and len(episodes) >= limit:
                break
    return episodes


async def existing_episode_names(graphiti: Graphiti, group_id: str) -> set[str]:
    records, _, _ = await graphiti.driver.execute_query(
        """
        MATCH (e:Episodic {group_id: $group_id})
        RETURN e.name AS name
        """,
        group_id=group_id,
        routing_="r",
    )
    return {str(record["name"]) for record in records if record.get("name")}


async def update_episode_layer_metadata(
    graphiti: Graphiti,
    *,
    episode_uuid: str,
    saga_name: str,
    episode: dict[str, str],
) -> None:
    metadata = {
        field: episode[field]
        for field in LAYER_METADATA_FIELDS
        if field in episode and str(episode[field]).strip()
    }
    if not metadata:
        return
    await graphiti.driver.execute_query(
        """
        MATCH (e:Episodic {uuid: $episode_uuid, group_id: $group_id})
        SET e += $metadata,
            e.saga = $saga_name,
            e.source_description = $source_description
        WITH e
        OPTIONAL MATCH (s:Saga {group_id: $group_id})-[:HAS_EPISODE]->(e)
        SET s += $metadata,
            s.name = $saga_name
        RETURN count(e) AS updated
        """,
        episode_uuid=episode_uuid,
        group_id=episode.get("group_id"),
        saga_name=saga_name,
        source_description=episode.get("source_description", "半导体图谱导入"),
        metadata=metadata,
    )


def append_failure_log(path: Path, record: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


async def import_episodes(args: argparse.Namespace) -> int:
    episodes = load_episodes(args.episodes, args.limit)
    llm_api_key = os.getenv(args.llm_api_key_env) if args.llm_api_key_env else None
    embedding_api_key = (
        os.getenv(args.embedding_api_key_env) if args.embedding_api_key_env else llm_api_key
    )
    llm_client = None
    embedder = None
    cross_encoder = None
    if llm_api_key or args.llm_base_url or args.llm_model:
        llm_client = OpenAIGenericClient(
            config=LLMConfig(
                api_key=llm_api_key,
                model=args.llm_model,
                base_url=args.llm_base_url,
                temperature=args.llm_temperature,
                small_model=args.llm_small_model,
            ),
            structured_output_mode=args.structured_output_mode,
        )
    if embedding_api_key or args.embedding_base_url or args.embedding_model:
        embedder = OpenAIEmbedder(
            config=OpenAIEmbedderConfig(
                api_key=embedding_api_key,
                base_url=args.embedding_base_url,
                embedding_model=args.embedding_model,
            )
        )
    if llm_api_key or args.llm_base_url or args.llm_small_model or args.llm_model:
        cross_encoder = OpenAIRerankerClient(
            config=LLMConfig(
                api_key=llm_api_key,
                model=args.reranker_model or args.llm_small_model or args.llm_model,
                base_url=args.llm_base_url,
                temperature=0,
            )
        )
    graphiti = Graphiti(
        args.neo4j_uri,
        args.neo4j_user,
        args.neo4j_password,
        llm_client=llm_client,
        embedder=embedder,
        cross_encoder=cross_encoder,
    )
    previous_by_saga: dict[str, str] = {}
    try:
        existing_names = await existing_episode_names(graphiti, args.group_id) if args.skip_existing else set()
        imported = 0
        skipped = 0
        for index, episode in enumerate(episodes, start=1):
            if episode["episode_name"] in existing_names:
                skipped += 1
                continue
            saga = episode.get("saga") or "semiconductor_graph"
            max_attempts = max(1, args.episode_retries + 1)
            result = None
            for attempt in range(1, max_attempts + 1):
                try:
                    result = await graphiti.add_episode(
                        name=episode["episode_name"],
                        episode_body=episode["episode_body"],
                        source=episode_type(episode.get("source", "text")),
                        source_description=episode.get("source_description", "半导体图谱导入"),
                        reference_time=parse_reference_time(episode["reference_time"]),
                        group_id=episode.get("group_id") or args.group_id,
                        saga=saga,
                        saga_previous_episode_uuid=previous_by_saga.get(saga),
                        custom_extraction_instructions=(
                            "抽取事实时必须保留中文公司名、产业链环节、产品服务、证据ID、"
                            "当前有效性、判断性质、事件开始时间和事件结束时间。"
                            "不要把候选商机、候选解决方案或需要内部验证的关系表述为已确认事实。"
                        ),
                    )
                    break
                except Exception as exc:
                    if attempt < max_attempts:
                        delay = min(args.retry_delay_seconds * attempt, 60)
                        print(
                            "episode import failed; "
                            f"retrying {attempt}/{args.episode_retries} after {delay:.1f}s: "
                            f"{episode['episode_name']} ({type(exc).__name__}: {exc})"
                        )
                        await asyncio.sleep(delay)
                        continue
                    append_failure_log(
                        args.failure_log,
                        {
                            "failed_at": datetime.now(timezone.utc).isoformat(),
                            "index": index,
                            "episode_name": episode["episode_name"],
                            "group_id": episode.get("group_id") or args.group_id,
                            "error_type": type(exc).__name__,
                            "error_message": str(exc),
                            "attempts": max_attempts,
                        },
                    )
                    if not args.continue_on_error:
                        raise
                    print(
                        "episode import failed permanently; "
                        f"logged and continuing: {episode['episode_name']} "
                        f"({type(exc).__name__}: {exc})"
                    )
                    break
            if result is None:
                continue
            existing_names.add(episode["episode_name"])
            previous_by_saga[saga] = result.episode.uuid
            await update_episode_layer_metadata(
                graphiti,
                episode_uuid=result.episode.uuid,
                saga_name=saga,
                episode=episode,
            )
            imported += 1
            if imported % 25 == 0:
                print(f"imported {imported} episodes, scanned {index}/{len(episodes)}")
        print(
            f"imported {imported} episodes into Graphiti group {args.group_id}; "
            f"skipped {skipped} existing episodes"
        )
        return 0
    finally:
        await graphiti.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=Path, default=DEFAULT_EPISODES)
    parser.add_argument("--neo4j-uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--neo4j-user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--neo4j-password", default=os.getenv("NEO4J_PASSWORD", "password"))
    parser.add_argument("--group-id", default="semiconductor_dc_kg")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--episode-retries", type=int, default=3)
    parser.add_argument("--retry-delay-seconds", type=float, default=5)
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--failure-log", type=Path, default=DEFAULT_FAILURE_LOG)
    parser.add_argument("--llm-api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--llm-base-url", default=os.getenv("OPENAI_BASE_URL"))
    parser.add_argument("--llm-model", default=os.getenv("GRAPHITI_LLM_MODEL"))
    parser.add_argument("--llm-small-model", default=os.getenv("GRAPHITI_LLM_SMALL_MODEL"))
    parser.add_argument("--reranker-model", default=os.getenv("GRAPHITI_RERANKER_MODEL"))
    parser.add_argument("--llm-temperature", type=float, default=0)
    parser.add_argument(
        "--structured-output-mode",
        choices=["json_schema", "json_object"],
        default=os.getenv("GRAPHITI_STRUCTURED_OUTPUT_MODE", "json_object"),
    )
    parser.add_argument("--embedding-api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--embedding-base-url", default=os.getenv("OPENAI_EMBEDDING_BASE_URL"))
    parser.add_argument(
        "--embedding-model",
        default=os.getenv("GRAPHITI_EMBEDDING_MODEL", "text-embedding-3-small"),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return asyncio.run(import_episodes(args))


if __name__ == "__main__":
    raise SystemExit(main())
