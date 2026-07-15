from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn


ROOT = Path(__file__).resolve().parents[1]
BASE_DIRECTORY = ROOT.parent.parent
API_ROOT = ROOT / "apps" / "api-server"


def find_original_root() -> Path:
    if (ROOT / "graphiti-main").is_dir():
        return ROOT
    for candidate in BASE_DIRECTORY.iterdir():
        if candidate.is_dir() and (candidate / ".git").is_dir() and (
            candidate / "graphiti-main"
        ).is_dir():
            return candidate
    raise RuntimeError("Original project root was not found")


def find_key_file(original_root: Path) -> Path:
    for candidate in original_root.glob("*.md"):
        if "siliconflow:" in candidate.read_text(encoding="utf-8"):
            return candidate
    raise RuntimeError("AI key file was not found")


def main() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from load_ai_keys import load_service_keys

    keys = load_service_keys(
        find_key_file(find_original_root()), ["siliconflow", "bocha", "tavily"]
    )
    if "SILICONFLOW_API_KEY" not in keys:
        raise RuntimeError("SILICONFLOW_API_KEY was not found")
    os.environ.update(keys)
    os.environ.setdefault("BOCHA_SEARCH_URL", "https://api.bochaai.com/v1/web-search")
    sys.path.insert(0, str(API_ROOT))
    uvicorn.run("app.main:app", host="127.0.0.1", port=8001, workers=1)


if __name__ == "__main__":
    main()
