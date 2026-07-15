from __future__ import annotations

import argparse
import os

from neo4j import GraphDatabase


def scalar(driver, query: str, **params) -> int:
    with driver.session() as session:
        record = session.run(query, **params).single()
        return int(record["count"]) if record else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--neo4j-uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--neo4j-user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--neo4j-password", default=os.getenv("NEO4J_PASSWORD", "password"))
    parser.add_argument("--group-id", default="semiconductor_dc_kg")
    parser.add_argument("--min-episodes", type=int, default=500)
    args = parser.parse_args()

    driver = GraphDatabase.driver(args.neo4j_uri, auth=(args.neo4j_user, args.neo4j_password))
    try:
        episode_count = scalar(
            driver,
            "MATCH (e:Episodic {group_id:$group_id}) RETURN count(e) AS count",
            group_id=args.group_id,
        )
        fact_count = scalar(
            driver,
            "MATCH ()-[r:RELATES_TO {group_id:$group_id}]->() RETURN count(r) AS count",
            group_id=args.group_id,
        )
    finally:
        driver.close()

    errors: list[str] = []
    if episode_count < args.min_episodes:
        errors.append(f"Graphiti episode count too low: {episode_count}")
    if fact_count == 0:
        errors.append("Graphiti extracted fact count is 0")
    if errors:
        for error in errors:
            print(f"FAIL {error}")
        return 1
    print(f"PASS Graphiti import verified: episodes={episode_count}, facts={fact_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
