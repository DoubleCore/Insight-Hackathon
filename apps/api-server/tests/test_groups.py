from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from tests.test_api import make_settings


class FakeDriver:
    def execute_query(self, query: str, **kwargs):
        return [], None, None


class FakeGraphService:
    driver = FakeDriver()


def test_groups_returns_default_group_when_graph_has_no_groups(tmp_path: Path) -> None:
    from app.main import create_app

    app = create_app(make_settings(tmp_path / "groups.db"))
    app.state.graph_service_by_group["semiconductor_dc_kg"] = FakeGraphService()
    with TestClient(app) as client:
        response = client.get("/api/v1/groups")

    assert response.status_code == 200
    assert response.json()[0]["id"] == "semiconductor_dc_kg"
    assert response.json()[0]["is_default"] is True
