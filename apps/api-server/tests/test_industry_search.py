from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.services.web_search import WebSearchHit
from tests.test_api import make_settings


class FakeSearch:
    async def search(self, query, *, providers, max_results):
        return [
            WebSearchHit(
                provider="tavily",
                title="机器人产业链资料",
                url="https://example.com/robotics",
                content="机器人产业链包含减速器、控制器、伺服系统和系统集成企业。",
                score=0.9,
            )
        ]

    async def close(self):
        return None


def test_industry_search_returns_hits_and_draft(tmp_path: Path) -> None:
    from app.main import create_app

    app = create_app(make_settings(tmp_path / "industry-search.db"))
    app.state.web_search_service = FakeSearch()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/industry-search",
            json={
                "industry_name": "机器人",
                "group_id": "semiconductor_dc_kg",
                "target_mode": "new_group",
                "new_group_id": "robotics_kg",
                "search_depth": "deep",
                "relation_types": ["生产", "合作", "渠道"],
                "include_digital_china": True,
                "manual_review_required": True,
                "providers": ["tavily"],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["group_id"] == "robotics_kg"
    assert payload["target_mode"] == "new_group"
    assert payload["search_depth"] == "deep"
    assert payload["relation_types"] == ["生产", "合作", "渠道"]
    assert payload["ingestion_status"] == "待人工审核"
    assert payload["hits"][0]["url"] == "https://example.com/robotics"
    assert "L4 细分产业链节点" in payload["draft_episode_body"]
    assert "神州数码" in payload["draft_episode_body"]
    assert "目标 group：robotics_kg" in payload["draft_episode_body"]


def test_industry_search_creates_pending_episode_draft(tmp_path: Path) -> None:
    from app.main import create_app

    app = create_app(make_settings(tmp_path / "industry-search-pending.db"))

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/industry-search/pending-episode",
            json={
                "group_id": "robotics_kg",
                "industry_name": "机器人",
                "query": "机器人 产业链 生产 合作 公开资料",
                "draft_episode_body": "产业名称：机器人\n公开资料来源：\n- 机器人产业链资料",
                "relation_types": ["生产", "合作", "渠道"],
                "search_depth": "deep",
                "include_digital_china": True,
                "manual_review_required": True,
                "hits": [
                    {
                        "provider": "tavily",
                        "title": "机器人产业链资料",
                        "url": "https://example.com/robotics",
                        "content": "机器人产业链包含系统集成企业。",
                        "score": 0.9,
                    }
                ],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pending_ingest"
    episode = payload["episode"]
    assert episode["group_id"] == "robotics_kg"
    assert episode["source"] == "text"
    assert episode["claim_nature"] == "public_search_draft"
    assert episode["requires_internal_validation"] is True
    assert episode["ingestion_status"] == "pending_ingest"
    assert episode["layer_name"] == "资料证据层"
    assert episode["fact_set_type"] == "public_search_draft"
    assert "机器人-公开资料扩展草稿" == episode["episode_name"]
    assert "公开搜索草稿" in episode["episode_body"]
    assert "待人工审核" in episode["episode_body"]
    assert "https://example.com/robotics" in episode["episode_body"]


def test_key_loader_supports_search_provider_keys(tmp_path: Path) -> None:
    import sys

    scripts_path = Path(__file__).resolve().parents[3] / "scripts"
    sys.path.insert(0, str(scripts_path))
    try:
        from load_ai_keys import load_service_keys
    finally:
        sys.path.remove(str(scripts_path))

    key_file = tmp_path / "keys.md"
    key_file.write_text(
        """
services:
  bocha:
    key: "bocha-test-key"
  tavily:
    key: "tavily-test-key"
""",
        encoding="utf-8",
    )

    keys = load_service_keys(key_file, ["bocha", "tavily"])

    assert keys == {
        "BOCHA_API_KEY": "bocha-test-key",
        "TAVILY_API_KEY": "tavily-test-key",
    }
