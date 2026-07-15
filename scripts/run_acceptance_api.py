from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api-server"


def find_key_file() -> Path | None:
    """Search for the AI key file in the project root and parent directories."""
    key_filename = "AI 工具密钥.md"
    # Check project root first
    candidate = ROOT / key_filename
    if candidate.is_file():
        return candidate
    # Check parent directories for the original project
    base = ROOT.parent.parent
    for d in base.iterdir():
        if d.is_dir() and (d / ".git").is_dir():
            candidate = d / key_filename
            if candidate.is_file():
                return candidate
    return None


def main() -> None:
    # Try to load AI keys from key file if available
    key_file = find_key_file()
    if key_file is not None:
        sys.path.insert(0, str(ROOT / "scripts"))
        from load_ai_keys import load_service_keys

        keys = load_service_keys(key_file, ["siliconflow", "bocha", "tavily"])
        if "SILICONFLOW_API_KEY" not in keys and not os.getenv("SILICONFLOW_API_KEY"):
            print("WARNING: SILICONFLOW_API_KEY not found in key file or environment")
        os.environ.update(keys)
    else:
        if not os.getenv("SILICONFLOW_API_KEY"):
            print("WARNING: No AI key file found and SILICONFLOW_API_KEY not set in environment")
            print("         The Q&A pipeline and LLM features will not work without API keys")

    os.environ.setdefault("BOCHA_SEARCH_URL", "https://api.bochaai.com/v1/web-search")
    sys.path.insert(0, str(API_ROOT))
    uvicorn.run("app.main:app", host="127.0.0.1", port=8001, workers=1)


if __name__ == "__main__":
    main()
