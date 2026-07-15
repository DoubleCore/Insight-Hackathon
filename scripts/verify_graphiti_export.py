from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EPISODES = ROOT / "data" / "graphiti" / "semiconductor_episodes.jsonl"

REQUIRED_FIELDS = [
    "episode_id",
    "episode_name",
    "episode_body",
    "source",
    "source_description",
    "reference_time",
    "group_id",
    "saga",
    "legacy_saga_key",
    "saga_key",
    "layer_id",
    "layer_name",
    "fact_set_name",
    "fact_set_type",
    "display_name",
]


def validate_episode(episode: dict[str, str], line_no: int) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        if not str(episode.get(field, "")).strip():
            errors.append(f"line {line_no} missing {field}")
    if episode.get("source") not in {"text", "json", "message"}:
        errors.append(f"line {line_no} invalid source {episode.get('source')}")
    if str(episode.get("saga", "")).startswith("stage"):
        errors.append(f"line {line_no} saga still uses legacy stage key")
    if "stage" in str(episode.get("source_description", "")):
        errors.append(f"line {line_no} source_description still uses legacy stage wording")
    reference_time = str(episode.get("reference_time", ""))
    if reference_time and not reference_time.endswith("Z"):
        errors.append(f"line {line_no} reference_time must use Z UTC suffix")
    body = str(episode.get("episode_body", ""))
    for required_text in [
        "数据截至时间",
        "最近核验时间",
        "事件开始时间",
        "事件结束时间",
        "当前有效性",
        "证据ID",
    ]:
        if required_text not in body:
            errors.append(f"line {line_no} body missing {required_text}")
    return errors


def load_episodes(path: Path) -> list[dict[str, str]]:
    episodes: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            item["_line_no"] = str(line_no)
            episodes.append(item)
    return episodes


def main() -> int:
    if not EPISODES.exists():
        print(f"FAIL missing {EPISODES}")
        return 1
    episodes = load_episodes(EPISODES)
    errors: list[str] = []
    seen_ids: set[str] = set()
    for index, episode in enumerate(episodes, start=1):
        episode_id = episode.get("episode_id", "")
        if episode_id in seen_ids:
            errors.append(f"line {index} duplicate episode_id {episode_id}")
        seen_ids.add(episode_id)
        errors.extend(validate_episode(episode, index))
    if len(episodes) < 500:
        errors.append(f"episode count too low: {len(episodes)}")
    if errors:
        for error in errors:
            print(f"FAIL {error}")
        return 1
    print(f"PASS graphiti episode export valid: {len(episodes)} episodes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
