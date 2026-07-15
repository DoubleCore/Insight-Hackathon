from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from graphiti_layer_mapping import SAGA_LAYER_MAPPING


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EPISODES = ROOT / "data" / "graphiti" / "semiconductor_episodes.jsonl"
DEFAULT_GROUP_ID = "semiconductor_dc_kg"


def migrate_jsonl(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    rows: list[dict[str, object]] = []
    changed = 0
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            original = dict(item)
            value = str(item.get("legacy_saga_key") or item.get("saga") or "")
            meta = SAGA_LAYER_MAPPING.get(value)
            if meta is not None:
                item.update(meta.as_properties())
                item["saga"] = meta.saga_name
                item["source_description"] = meta.source_description
            if item != original:
                changed += 1
            rows.append(item)
    with path.open("w", encoding="utf-8") as handle:
        for item in rows:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    return len(rows), changed


def migrate_neo4j(uri: str, user: str, password: str, group_id: str) -> tuple[int, int]:
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        saga_count = 0
        episode_count = 0
        for legacy_key, meta in SAGA_LAYER_MAPPING.items():
            properties = meta.as_properties()
            result = driver.execute_query(
                """
                MATCH (s:Saga {group_id: $group_id})
                WHERE s.name = $legacy_key
                   OR s.name = $saga_key
                   OR s.name = $saga_name
                   OR s.legacy_saga_key = $legacy_key
                SET s += $properties,
                    s.name = $saga_name
                WITH collect(s) AS sagas
                UNWIND sagas AS saga
                OPTIONAL MATCH (saga)-[:HAS_EPISODE]->(e:Episodic {group_id: $group_id})
                SET e += $properties,
                    e.saga = $saga_name,
                    e.source_description = $source_description
                RETURN count(DISTINCT saga) AS saga_count, count(DISTINCT e) AS episode_count
                """,
                group_id=group_id,
                legacy_key=legacy_key,
                saga_key=meta.saga_key,
                saga_name=meta.saga_name,
                source_description=meta.source_description,
                properties=properties,
            )
            record = result.records[0] if result.records else None
            saga_count += int(record["saga_count"] if record else 0)
            episode_count += int(record["episode_count"] if record else 0)
            result = driver.execute_query(
                """
                MATCH (s:Saga {group_id: $group_id, name: $saga_name})
                MATCH (e:Episodic {group_id: $group_id})
                WHERE e.legacy_saga_key = $legacy_key
                   OR e.saga = $legacy_key
                   OR e.source_description CONTAINS $legacy_key
                SET e += $properties,
                    e.saga = $saga_name,
                    e.source_description = $source_description
                MERGE (s)-[:HAS_EPISODE]->(e)
                RETURN count(DISTINCT e) AS episode_count
                """,
                group_id=group_id,
                legacy_key=legacy_key,
                saga_name=meta.saga_name,
                source_description=meta.source_description,
                properties=properties,
            )
            record = result.records[0] if result.records else None
            episode_count += int(record["episode_count"] if record else 0)
        return saga_count, episode_count
    finally:
        driver.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=Path, default=DEFAULT_EPISODES)
    parser.add_argument("--neo4j-uri", default="bolt://localhost:7687")
    parser.add_argument("--neo4j-user", default="neo4j")
    parser.add_argument("--neo4j-password", default="password")
    parser.add_argument("--group-id", default=DEFAULT_GROUP_ID)
    parser.add_argument("--skip-jsonl", action="store_true")
    parser.add_argument("--skip-neo4j", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.skip_jsonl:
        total, changed = migrate_jsonl(args.episodes)
        print(f"JSONL migrated: {changed}/{total} episodes updated")
    if not args.skip_neo4j:
        saga_count, episode_count = migrate_neo4j(
            args.neo4j_uri,
            args.neo4j_user,
            args.neo4j_password,
            args.group_id,
        )
        print(f"Neo4j migrated: {saga_count} Saga nodes, {episode_count} Episodic nodes updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
