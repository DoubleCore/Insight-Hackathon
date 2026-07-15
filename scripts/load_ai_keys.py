from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KEY_FILE = ROOT / "AI 工具密钥.md"

SERVICE_ENV = {
    "bocha": "BOCHA_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "moonshot": "MOONSHOT_API_KEY",
    "siliconflow": "SILICONFLOW_API_KEY",
    "tavily": "TAVILY_API_KEY",
}


def extract_service_key(text: str, service: str) -> str:
    marker = f"  {service}:"
    start = text.find(marker)
    if start < 0:
        return ""
    tail = text[start:]
    next_service = re.search(r"\n  [a-zA-Z0-9_-]+:\n", tail[len(marker) :])
    block = tail if not next_service else tail[: len(marker) + next_service.start()]
    match = re.search(r'key:\s*"([^"]+)"', block)
    return match.group(1).strip() if match else ""


def load_service_keys(key_file: Path, services: list[str]) -> dict[str, str]:
    text = key_file.read_text(encoding="utf-8")
    values: dict[str, str] = {}
    for service in services:
        env_name = SERVICE_ENV[service]
        key = os.getenv(env_name) or extract_service_key(text, service)
        if key:
            values[env_name] = key
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--key-file", type=Path, default=DEFAULT_KEY_FILE)
    parser.add_argument("--services", nargs="+", choices=sorted(SERVICE_ENV), required=True)
    parser.add_argument("--command", required=True)
    args = parser.parse_args()

    loaded = load_service_keys(args.key_file, args.services)
    if not loaded:
        print("FAIL no requested keys found")
        return 1
    env = dict(os.environ)
    env.update(loaded)
    completed = subprocess.run(
        args.command,
        shell=True,
        cwd=ROOT,
        env=env,
    )
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
