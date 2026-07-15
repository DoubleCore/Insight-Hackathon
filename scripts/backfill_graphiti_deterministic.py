from __future__ import annotations

import argparse
import csv
import json
import os
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase

from load_ai_keys import DEFAULT_KEY_FILE, load_service_keys

ROOT = Path(__file__).resolve().parents[1]
EPISODES_PATH = ROOT / "data" / "graphiti" / "semiconductor_episodes.jsonl"
COMPETITION_PATH = ROOT / "data" / "business_graph" / "stage6_company_competition.csv"
DIGITAL_CHINA_PATH = ROOT / "data" / "business_graph" / "stage7_digital_china_relations.csv"
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "semiconductor_dc_kg_graphiti_backfill")


def stable_uuid(*parts: str) -> str:
    return str(uuid.uuid5(NAMESPACE, "::".join(parts)))


def parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    normalized = value.strip().replace("Z", "+00:00")
    if not normalized:
        return datetime.now(timezone.utc)
    if len(normalized) == 10:
        normalized = f"{normalized}T00:00:00+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


class EmbeddingClient:
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.endpoint = base_url.rstrip("/") + "/embeddings"
        self.model = model
        self.cache: dict[str, list[float]] = {}

    def embed(self, text: str) -> list[float] | None:
        if not self.api_key:
            return None
        if text in self.cache:
            return self.cache[text]
        payload = json.dumps({"model": self.model, "input": text}, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError):
            return None
        data = body.get("data") or []
        if not data:
            return None
        embedding = data[0].get("embedding")
        if not isinstance(embedding, list):
            return None
        self.cache[text] = embedding
        return embedding


def episode_map() -> dict[str, dict[str, Any]]:
    return {row["episode_name"]: row for row in read_jsonl(EPISODES_PATH)}


def build_competition_facts(episodes: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for row in read_csv(COMPETITION_PATH):
        source = row["source_company"].strip()
        target = row["target_company"].strip()
        episode_name = f"{source}-{target}-推定竞争候选"
        episode = episodes.get(episode_name)
        if not episode:
            continue
        fact = (
            f"{source} 与 {target} 存在推定竞争候选关系；"
            f"判断依据：{row['basis']}；"
            f"证据ID：{row['evidence_ids']}；"
            f"判断性质：{row['claim_nature']}；"
            f"当前有效性：{row['current_validity']}。"
        )
        facts.append(
            {
                "episode": episode,
                "source": source,
                "target": target,
                "relationship": "推定竞争",
                "fact": fact,
                "properties": {
                    "relationship_type": row["relationship_type"],
                    "basis": row["basis"],
                    "evidence_ids": row["evidence_ids"],
                    "confidence": row["confidence"],
                    "requires_internal_validation": truthy(row["requires_internal_validation"]),
                    "claim_nature": row["claim_nature"],
                    "current_validity": row["current_validity"],
                    "data_as_of": row["data_as_of"],
                    "first_seen_at": row["first_seen_at"],
                    "last_verified_at": row["last_verified_at"],
                    "event_start_at": row["event_start_at"],
                    "event_end_at": row["event_end_at"],
                    "time_precision": row["time_precision"],
                    "primary_evidence_id": row["primary_evidence_id"],
                    "evidence_grade_summary": row["evidence_grade_summary"],
                    "deterministic_backfill": True,
                },
                "valid_at": row["event_start_at"] or row["data_as_of"],
            }
        )
    return facts


def digital_china_relationship_name(status: str) -> str:
    if status == "confirmed_public_relationship":
        return "公开可验证关系"
    if status == "potential_fit":
        return "潜在业务匹配"
    if status == "needs_internal_validation":
        return "需内部验证关系"
    return "关系状态"


def build_digital_china_facts(episodes: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for row in read_csv(DIGITAL_CHINA_PATH):
        company = row["company_name"].strip()
        episode_name = f"{company}-神州数码关系状态"
        episode = episodes.get(episode_name)
        if not episode:
            continue
        status = row["relationship_status"]
        fact = (
            f"截至 {row['data_as_of']}，{company} 与神州数码的关系状态为 {status}；"
            f"关系类型：{row['relationship_type']}；"
            f"判断依据：{row['relationship_basis']}；"
            f"是否需要内部验证：{row['requires_internal_validation']}；"
            f"证据ID：{row['evidence_ids']}；"
            f"证据发布日期：{row.get('source_publish_dates', '')}；"
            f"最近核验时间：{row.get('last_verified_at', '')}；"
            f"当前有效性：{row.get('current_validity', '')}。"
        )
        facts.append(
            {
                "episode": episode,
                "source": company,
                "target": "神州数码",
                "relationship": digital_china_relationship_name(status),
                "fact": fact,
                "properties": {
                    "relationship_status": status,
                    "relationship_type": row["relationship_type"],
                    "relationship_basis": row["relationship_basis"],
                    "evidence_ids": row["evidence_ids"],
                    "confidence": row["confidence"],
                    "requires_internal_validation": truthy(row["requires_internal_validation"]),
                    "limitations": row["limitations"],
                    "asset_tier": row["asset_tier"],
                    "claim_nature": row["claim_nature"],
                    "current_validity": row["current_validity"],
                    "data_as_of": row["data_as_of"],
                    "first_seen_at": row["first_seen_at"],
                    "last_verified_at": row["last_verified_at"],
                    "event_date": row["event_date"],
                    "event_start_at": row["event_start_at"],
                    "event_end_at": row["event_end_at"],
                    "time_precision": row["time_precision"],
                    "temporal_basis": row["temporal_basis"],
                    "source_publish_dates": row["source_publish_dates"],
                    "source_retrieved_dates": row["source_retrieved_dates"],
                    "primary_evidence_id": row["primary_evidence_id"],
                    "evidence_grade_summary": row["evidence_grade_summary"],
                    "verification_method": row["verification_method"],
                    "needs_refresh_after": row["needs_refresh_after"],
                    "risk_note": row["risk_note"],
                    "deterministic_backfill": True,
                },
                "valid_at": row["event_start_at"] or row["data_as_of"],
            }
        )
    return facts


def existing_episode_names(driver: Any, group_id: str) -> set[str]:
    records, _, _ = driver.execute_query(
        "MATCH (e:Episodic {group_id: $group_id}) RETURN e.name AS name",
        group_id=group_id,
        routing_="r",
    )
    return {record["name"] for record in records}


def upsert_fact(driver: Any, group_id: str, item: dict[str, Any], embedder: EmbeddingClient | None) -> bool:
    episode = item["episode"]
    episode_name = episode["episode_name"]
    episode_uuid = stable_uuid("episode", episode_name)
    source_name = item["source"]
    target_name = item["target"]
    source_uuid = stable_uuid("entity", group_id, source_name)
    target_uuid = stable_uuid("entity", group_id, target_name)
    edge_uuid = stable_uuid("edge", group_id, episode_name, source_name, item["relationship"], target_name)
    now = datetime.now(timezone.utc)
    reference_time = parse_datetime(episode["reference_time"])
    valid_at = parse_datetime(item["valid_at"])
    fact_embedding = embedder.embed(item["fact"]) if embedder else None
    source_embedding = embedder.embed(source_name) if embedder else None
    target_embedding = embedder.embed(target_name) if embedder else None

    edge_props = {
        **item["properties"],
        "uuid": edge_uuid,
        "name": item["relationship"],
        "fact": item["fact"],
        "group_id": group_id,
        "source_node_uuid": source_uuid,
        "target_node_uuid": target_uuid,
        "created_at": now,
        "reference_time": reference_time,
        "valid_at": valid_at,
        "episodes": [episode_uuid],
    }
    if fact_embedding is not None:
        edge_props["fact_embedding"] = fact_embedding

    driver.execute_query(
        """
        MERGE (source:Entity {group_id: $group_id, name: $source_name})
        ON CREATE SET
            source.uuid = $source_uuid,
            source.created_at = $now,
            source.summary = $source_summary
        SET source.name_embedding = coalesce(source.name_embedding, $source_embedding)
        MERGE (target:Entity {group_id: $group_id, name: $target_name})
        ON CREATE SET
            target.uuid = $target_uuid,
            target.created_at = $now,
            target.summary = $target_summary
        SET target.name_embedding = coalesce(target.name_embedding, $target_embedding)
        MERGE (episode:Episodic {group_id: $group_id, name: $episode_name})
        ON CREATE SET
            episode.uuid = $episode_uuid,
            episode.created_at = $now,
            episode.valid_at = $reference_time,
            episode.source = $episode_source,
            episode.source_description = $source_description,
            episode.content = $episode_body,
            episode.entity_edges = [$edge_uuid]
        SET episode.entity_edges = CASE
            WHEN episode.entity_edges IS NULL THEN [$edge_uuid]
            WHEN $edge_uuid IN episode.entity_edges THEN episode.entity_edges
            ELSE episode.entity_edges + $edge_uuid
        END
        MERGE (source)-[rel:RELATES_TO {uuid: $edge_uuid}]->(target)
        SET rel = $edge_props
        RETURN rel.uuid AS uuid
        """,
        group_id=group_id,
        source_name=source_name,
        target_name=target_name,
        source_uuid=source_uuid,
        target_uuid=target_uuid,
        source_summary=f"{source_name} 是半导体产业链图谱实体",
        target_summary=f"{target_name} 是半导体产业链图谱实体",
        source_embedding=source_embedding,
        target_embedding=target_embedding,
        now=now,
        episode_name=episode_name,
        episode_uuid=episode_uuid,
        reference_time=reference_time,
        episode_source=episode.get("source", "text"),
        source_description=episode.get("source_description", "半导体产业链图谱 deterministic backfill"),
        episode_body=episode["episode_body"],
        edge_uuid=edge_uuid,
        edge_props=edge_props,
        routing_="w",
    )
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--neo4j-uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--neo4j-user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--neo4j-password", default=os.getenv("NEO4J_PASSWORD", "password"))
    parser.add_argument("--group-id", default="semiconductor_dc_kg")
    parser.add_argument(
        "--include",
        nargs="+",
        choices=["competition", "digital_china"],
        default=["competition", "digital_china"],
    )
    parser.add_argument("--with-embeddings", action="store_true")
    parser.add_argument("--embedding-base-url", default="https://api.siliconflow.cn/v1")
    parser.add_argument("--embedding-model", default="BAAI/bge-m3")
    parser.add_argument(
        "--force-upsert-facts",
        action="store_true",
        help="Upsert deterministic RELATES_TO facts even when the source Episodic node already exists.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    episodes = episode_map()
    items: list[dict[str, Any]] = []
    if "competition" in args.include:
        items.extend(build_competition_facts(episodes))
    if "digital_china" in args.include:
        items.extend(build_digital_china_facts(episodes))

    embedder = None
    if args.with_embeddings:
        key = (
            os.getenv("SILICONFLOW_API_KEY")
            or load_service_keys(DEFAULT_KEY_FILE, ["siliconflow"]).get("SILICONFLOW_API_KEY", "")
        )
        embedder = EmbeddingClient(key, args.embedding_base_url, args.embedding_model)

    with GraphDatabase.driver(args.neo4j_uri, auth=(args.neo4j_user, args.neo4j_password)) as driver:
        existing = existing_episode_names(driver, args.group_id)
        pending = items if args.force_upsert_facts else [
            item for item in items if item["episode"]["episode_name"] not in existing
        ]
        for index, item in enumerate(pending, start=1):
            upsert_fact(driver, args.group_id, item, embedder)
            if index % 25 == 0:
                print(f"backfilled {index}/{len(pending)} episodes")
        print(f"backfilled {len(pending)} deterministic Graphiti episodes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
