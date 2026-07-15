from __future__ import annotations

import asyncio
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


def make_settings(database_path: Path):
    from app.config import Settings

    return Settings(
        neo4j_password="neo4j-secret-value",
        admin_password="admin-secret-value",
        session_secret="session-secret-value",
        sqlite_path=str(database_path),
        cookie_secure=False,
    )


def test_build_graphiti_uses_configured_reranker_by_default(
    tmp_path: Path, monkeypatch
) -> None:
    from app.config import Settings
    import app.services.runtime as runtime

    captured: dict[str, object] = {}

    class FakeGraphiti:
        def __init__(self, uri, user, password, **kwargs):
            captured["uri"] = uri
            captured["user"] = user
            captured["password"] = password
            captured["kwargs"] = kwargs

    class FakeReranker:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(runtime, "SiliconFlowReranker", FakeReranker)
    monkeypatch.setattr("graphiti_core.Graphiti", FakeGraphiti)

    settings = Settings(
        sqlite_path=str(tmp_path / "runtime.db"),
        siliconflow_api_key="siliconflow-key",
        admin_password="admin-secret-value",
        session_secret="session-secret-value",
        cookie_secure=False,
    )

    runtime.build_graphiti(settings)

    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert isinstance(kwargs["cross_encoder"], FakeReranker)
    assert kwargs["cross_encoder"].kwargs["api_key"] == "siliconflow-key"


def test_health_is_safe_and_cors_allows_only_local_frontends(tmp_path: Path) -> None:
    from app.main import create_app

    app = create_app(make_settings(tmp_path / "health.db"))
    with TestClient(app) as client:
        response = client.get("/health")
        allowed = client.options(
            "/health",
            headers={
                "Origin": "http://127.0.0.1:7870",
                "Access-Control-Request-Method": "GET",
            },
        )
        second_allowed = client.options(
            "/health",
            headers={
                "Origin": "http://127.0.0.1:7871",
                "Access-Control-Request-Method": "GET",
            },
        )
        denied = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:7870",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
    serialized = response.text
    assert "neo4j-secret-value" not in serialized
    assert "admin-secret-value" not in serialized
    assert "session-secret-value" not in serialized
    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:7870"
    assert allowed.headers["access-control-allow-credentials"] == "true"
    assert second_allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:7871"
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


def test_user_cookie_is_http_only_and_isolates_conversations(tmp_path: Path) -> None:
    from app.main import create_app

    app = create_app(make_settings(tmp_path / "users.db"))
    with TestClient(app) as owner_client, TestClient(app) as other_client:
        created = owner_client.post(
            "/api/v1/user/conversations", json={"title": "我的会话"}
        )
        conversation_id = created.json()["id"]
        app.state.repository.append_message(conversation_id, "assistant", "仅所有者可见")

        owner_conversations = owner_client.get("/api/v1/user/conversations")
        owner_messages = owner_client.get(
            f"/api/v1/user/conversations/{conversation_id}/messages"
        )
        other_conversations = other_client.get("/api/v1/user/conversations")
        forbidden_messages = other_client.get(
            f"/api/v1/user/conversations/{conversation_id}/messages"
        )

    assert created.status_code == 201
    assert "httponly" in created.headers["set-cookie"].lower()
    assert "owner_id" not in created.json()
    assert [item["id"] for item in owner_conversations.json()] == [conversation_id]
    assert owner_messages.json()[0]["content"] == "仅所有者可见"
    assert other_conversations.json() == []
    assert forbidden_messages.status_code == 404
    assert forbidden_messages.json()["detail"] == "会话不存在或无权访问"


def test_tampered_user_cookie_cannot_reuse_an_identity(tmp_path: Path) -> None:
    from app.main import USER_COOKIE_NAME, create_app

    app = create_app(make_settings(tmp_path / "tamper.db"))
    with TestClient(app) as client:
        created = client.post("/api/v1/user/conversations", json={})
        original_cookie = client.cookies.get(USER_COOKIE_NAME)
        client.cookies.set(USER_COOKIE_NAME, f"{original_cookie}tampered")
        conversations = client.get("/api/v1/user/conversations")

    assert created.status_code == 201
    assert conversations.status_code == 200
    assert conversations.json() == []


def test_cookie_secure_policy_and_admin_session_ttl_follow_settings(tmp_path: Path) -> None:
    from app.config import Settings
    from app.main import create_app

    settings = Settings(
        admin_password="admin-secret-value",
        session_secret="stable-session-secret",
        sqlite_path=str(tmp_path / "secure-cookie.db"),
        cookie_secure=True,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        user_cookie = client.post("/api/v1/user/conversations", json={})
        admin_cookie = client.post(
            "/api/v1/admin/login", json={"password": "admin-secret-value"}
        )

    assert "secure" in user_cookie.headers["set-cookie"].lower()
    admin_set_cookie = admin_cookie.headers["set-cookie"].lower()
    assert "secure" in admin_set_cookie
    assert "max-age=28800" in admin_set_cookie


def test_admin_authentication_and_trace_listing(tmp_path: Path) -> None:
    from app.main import create_app
    from app.routers.admin import router as admin_router
    from app.schemas import QueryRunSummary, QueryTrace

    app = create_app(make_settings(tmp_path / "admin.db"))
    with TestClient(app) as client:
        unauthenticated = client.get("/api/v1/admin/me")
        wrong_password = client.post(
            "/api/v1/admin/login", json={"password": "wrong"}
        )
        login = client.post(
            "/api/v1/admin/login", json={"password": "admin-secret-value"}
        )
        conversation = app.state.repository.create_conversation("trace-owner")
        query_run = app.state.repository.create_query_run(
            conversation["id"],
            "追踪问题",
            trace_id="0123456789abcdef0123456789abcdef",
        )
        me = client.get("/api/v1/admin/me")
        traces = client.get("/api/v1/admin/traces")
        trace_detail = client.get(f"/api/v1/admin/traces/{query_run['id']}")
        missing_trace = client.get("/api/v1/admin/traces/missing-run")
        logout = client.post("/api/v1/admin/logout")
        after_logout = client.get("/api/v1/admin/me")

    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["detail"] == "管理员未登录"
    assert wrong_password.status_code == 401
    assert wrong_password.json()["detail"] == "管理口令错误"
    assert login.status_code == 200
    assert login.json() == {"authenticated": True}
    assert "httponly" in login.headers["set-cookie"].lower()
    assert me.json() == {"authenticated": True}
    assert traces.status_code == 200
    assert traces.json()[0]["id"] == query_run["id"]
    assert traces.json()[0]["trace_id"] == "0123456789abcdef0123456789abcdef"
    assert QueryRunSummary.model_validate(traces.json()[0]).id == query_run["id"]
    assert trace_detail.status_code == 200
    assert QueryTrace.model_validate(trace_detail.json()).id == query_run["id"]
    assert trace_detail.json()["trace_id"] == "0123456789abcdef0123456789abcdef"
    assert missing_trace.status_code == 404
    assert missing_trace.json() == {"detail": "查询追踪不存在"}
    list_route = next(
        route
        for route in admin_router.routes
        if getattr(route, "path", None) == "/api/v1/admin/traces"
    )
    detail_route = next(
        route
        for route in admin_router.routes
        if getattr(route, "path", None) == "/api/v1/admin/traces/{run_id}"
    )
    assert list_route.response_model == list[QueryRunSummary]
    assert detail_route.response_model is QueryTrace
    assert logout.status_code == 200
    assert after_logout.status_code == 401


def test_admin_can_import_text_decision_signal(tmp_path: Path, monkeypatch) -> None:
    from app.main import create_app

    class FakeEpisode:
        uuid = "episode-1"

    class FakeResult:
        episode = FakeEpisode()

    class FakeGraphiti:
        def __init__(self) -> None:
            self.kwargs = {}
            self.closed = False

        async def add_episode(self, **kwargs):
            self.kwargs = kwargs
            return FakeResult()

        async def close(self):
            self.closed = True

    fake_graphiti = FakeGraphiti()

    def fake_factory(settings):
        assert settings.group_id == "semiconductor_dc_kg"
        return fake_graphiti

    monkeypatch.setattr("app.services.runtime.build_graphiti", fake_factory)
    app = create_app(make_settings(tmp_path / "decision-signals.db"))
    app.state.decision_signal_evidence_dir = tmp_path / "evidence"

    with TestClient(app) as client:
        client.post("/api/v1/admin/login", json={"password": "admin-secret-value"})
        response = client.post(
            "/api/v1/admin/decision-signals",
            data={
                "group_id": "semiconductor_dc_kg",
                "category": "technology",
                "source_type": "text",
                "title": "摩尔定律放缓",
                "content": "摩尔定律放缓推动先进封装和 Chiplet。",
                "keywords": "摩尔定律,先进封装",
            },
        )

    assert response.status_code == 200
    assert response.json()["episode_uuid"] == "episode-1"
    assert response.json()["saga"] == "决策信号层"
    assert response.json()["evidence_id"].startswith("DS-")
    assert fake_graphiti.kwargs["group_id"] == "semiconductor_dc_kg"
    assert fake_graphiti.kwargs["saga"] == "决策信号层"
    assert "资料类型：技术趋势" in fake_graphiti.kwargs["episode_body"]
    assert "证据ID：DS-" in fake_graphiti.kwargs["episode_body"]
    assert "摩尔定律放缓" in fake_graphiti.kwargs["episode_body"]
    assert fake_graphiti.closed is True


def test_decision_signal_import_invalidates_cached_qa_pipeline(
    tmp_path: Path, monkeypatch
) -> None:
    from app.main import create_app

    class FakeEpisode:
        uuid = "episode-1"

    class FakeResult:
        episode = FakeEpisode()

    class FakeGraphiti:
        async def add_episode(self, **_kwargs):
            return FakeResult()

        async def close(self):
            return None

    class CachedPipeline:
        def __init__(self) -> None:
            self.closed = False

        async def close(self):
            self.closed = True

    monkeypatch.setattr("app.services.runtime.build_graphiti", lambda _settings: FakeGraphiti())
    app = create_app(make_settings(tmp_path / "decision-signals-cache.db"))
    app.state.decision_signal_evidence_dir = tmp_path / "evidence"
    cached = CachedPipeline()
    app.state.qa_pipeline = cached
    app.state.qa_pipeline_by_group["semiconductor_dc_kg"] = cached

    with TestClient(app) as client:
        client.post("/api/v1/admin/login", json={"password": "admin-secret-value"})
        response = client.post(
            "/api/v1/admin/decision-signals",
            data={
                "group_id": "semiconductor_dc_kg",
                "category": "business_implication",
                "source_type": "text",
                "title": "华为与稻盛经营哲学",
                "content": "资料内容",
            },
        )

    assert response.status_code == 200
    assert cached.closed is True
    assert app.state.qa_pipeline is None
    assert "semiconductor_dc_kg" not in app.state.qa_pipeline_by_group


def test_application_startup_marks_unfinished_jobs_interrupted(tmp_path: Path) -> None:
    from app.main import create_app
    from app.storage import Repository

    settings = make_settings(tmp_path / "recovery.db")
    repository = Repository(settings.sqlite_path)
    repository.initialize()
    queued = repository.create_background_job("refresh", {})
    conversation = repository.create_conversation("owner")
    query_run = repository.create_query_run(conversation["id"], "未完成问答")
    now = datetime.now(UTC)
    active = repository.create_background_job(
        "refresh",
        {},
        status="running",
        worker_id="other-worker",
        heartbeat_at=now.isoformat(),
        lease_expires_at=(now + timedelta(minutes=5)).isoformat(),
    )

    app = create_app(settings)
    with TestClient(app):
        recovered = app.state.repository.get_background_job(queued["id"])
        recovered_query = app.state.repository.get_query_run(query_run["id"])
        active_after_startup = app.state.repository.get_background_job(active["id"])

    assert recovered["status"] == "interrupted"
    assert recovered_query["status"] == "interrupted"
    assert active_after_startup["status"] == "interrupted"


def test_framework_errors_return_understandable_chinese_detail(tmp_path: Path) -> None:
    from app.main import create_app

    app = create_app(make_settings(tmp_path / "errors.db"))
    with TestClient(app) as client:
        invalid_payload = client.post("/api/v1/admin/login", json={})
        missing_route = client.get("/api/v1/not-found")

    assert invalid_payload.status_code == 422
    assert invalid_payload.json() == {"detail": "请求参数不完整或格式错误"}
    assert missing_route.status_code == 404
    assert missing_route.json() == {"detail": "接口不存在"}


def test_sqlite_errors_return_stable_503_without_internal_details(
    tmp_path: Path, monkeypatch
) -> None:
    from app.main import create_app

    app = create_app(make_settings(tmp_path / "sqlite-error.db"))
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/admin/login", json={"password": "admin-secret-value"}
        )
        assert login.status_code == 200

        def fail_query_runs(*, limit: int = 100):
            raise sqlite3.OperationalError("internal-database-secret")

        monkeypatch.setattr(app.state.repository, "list_query_runs", fail_query_runs)
        response = client.get("/api/v1/admin/traces")

    assert response.status_code == 503
    assert response.json() == {"detail": "数据库服务暂时不可用"}
    assert "internal-database-secret" not in response.text


def test_user_question_request_exposes_sse_and_public_result_only(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from app.main import create_app
    from app.schemas import Citation, TrustDimension, TrustProfile
    from app.services.qa_pipeline import QaPipelineResult

    class FakePipeline:
        async def run(self, *, conversation_id, query_run_id, question, emit=None):
            await emit("stage", {"name": "深度检索", "status": "running"})
            await emit("token", {"text": "有证据的回答"})
            trust = TrustProfile(
                evidence=TrustDimension(key="evidence", label="证据质量", level="high", explanation="A"),
                confidence=TrustDimension(key="confidence", label="事实置信度", level="high", explanation="high"),
                freshness=TrustDimension(key="freshness", label="时效性", level="high", explanation="fresh"),
                verification=TrustDimension(key="verification", label="核验状态", level="high", explanation="verified"),
            )
            return QaPipelineResult(
                message_id="unused",
                answer="有证据的回答",
                citations=[Citation(evidence_id="E-1", title="官方资料", grade="A")],
                trust_profile=trust,
            )

    class FakeSpan:
        trace_id = "f" * 32

        def set_attribute(self, _key, _value) -> None:
            return None

        def set_attributes(self, _attributes) -> None:
            return None

    @contextmanager
    def fake_start_span(*_args, **_kwargs):
        yield FakeSpan()

    monkeypatch.setattr("app.routers.user.start_span", fake_start_span)

    app = create_app(make_settings(tmp_path / "question-api.db"))
    app.state.qa_pipeline = FakePipeline()
    with TestClient(app) as owner, TestClient(app) as other:
        conversation = owner.post("/api/v1/user/conversations", json={}).json()
        submitted = owner.post(
            f"/api/v1/user/conversations/{conversation['id']}/messages",
            json={"content": "NVIDIA 有哪些产品？"},
        )
        request_id = submitted.json()["request_id"]
        events = owner.get(f"/api/v1/user/requests/{request_id}/events")
        result = owner.get(f"/api/v1/user/requests/{request_id}")
        forbidden = other.get(f"/api/v1/user/requests/{request_id}")

    assert submitted.status_code == 202
    assert submitted.json()["status"] == "queued"
    assert "event: stage" in events.text
    assert "event: token" in events.text
    assert "event: completed" in events.text
    payload = result.json()
    assert result.status_code == 200
    assert payload["answer"] == "有证据的回答"
    assert payload["trace_id"] == "f" * 32
    assert app.state.repository.get_query_run(request_id)["trace_id"] == "f" * 32
    assert payload["citations"][0]["evidence_id"] == "E-1"
    assert set(payload["trust_profile"]) == {
        "evidence",
        "confidence",
        "freshness",
        "verification",
    }
    assert "retrieval_slices" not in payload
    assert forbidden.status_code == 404


def test_user_question_rejects_blank_content_and_foreign_conversation(
    tmp_path: Path,
) -> None:
    from app.main import create_app

    app = create_app(make_settings(tmp_path / "question-validation.db"))
    with TestClient(app) as owner, TestClient(app) as other:
        conversation = owner.post("/api/v1/user/conversations", json={}).json()
        blank = owner.post(
            f"/api/v1/user/conversations/{conversation['id']}/messages",
            json={"content": "   "},
        )
        foreign = other.post(
            f"/api/v1/user/conversations/{conversation['id']}/messages",
            json={"content": "问题"},
        )

    assert blank.status_code == 422
    assert foreign.status_code == 404


def test_user_question_accepts_group_id_in_payload(tmp_path: Path, monkeypatch) -> None:
    from app.main import create_app
    from app.routers import user as user_router

    app = create_app(make_settings(tmp_path / "group-question.db"))
    seen_groups: list[str] = []

    async def fake_execute(request, conversation_id, request_id, question, group_id):
        seen_groups.append(group_id)
        request.app.state.repository.update_query_run(
            request_id, status="completed", answer="ok"
        )

    monkeypatch.setattr(user_router, "_execute_request", fake_execute)

    with TestClient(app) as client:
        conversation = client.post(
            "/api/v1/user/conversations", json={"title": "t"}
        ).json()
        response = client.post(
            f"/api/v1/user/conversations/{conversation['id']}/messages",
            json={"content": "查一下机器人产业链", "group_id": "robotics_kg"},
        )

    assert response.status_code == 202
    assert seen_groups == ["robotics_kg"]


def test_admin_graph_endpoints_require_login_and_return_three_views(
    tmp_path: Path,
) -> None:
    from app.main import create_app
    from app.schemas import GraphEdge, GraphNode, GraphPayload

    class FakeGraphService:
        async def get_stats(self):
            return {"industry_nodes": 10, "facts": 5}

        async def get_view(self, view: str, *, limit: int):
            return GraphPayload(
                nodes=[GraphNode(id="n1", labels=["企业"], properties={"名称": "NVIDIA"})],
                edges=[GraphEdge(id="e1", source="n1", target="n2", type="事实关系")],
            )

    app = create_app(make_settings(tmp_path / "admin-graph.db"))
    app.state.graph_service = FakeGraphService()
    with TestClient(app) as client:
        unauthorized = client.get("/api/v1/admin/graph/stats")
        client.post("/api/v1/admin/login", json={"password": "admin-secret-value"})
        stats = client.get("/api/v1/admin/graph/stats")
        views = {
            view: client.get(f"/api/v1/admin/graph/views/{view}?limit=100")
            for view in ("business", "temporal", "governance")
        }
        invalid = client.get("/api/v1/admin/graph/views/other")

    assert unauthorized.status_code == 401
    assert stats.json() == {"industry_nodes": 10, "facts": 5}
    assert all(response.status_code == 200 for response in views.values())
    assert views["business"].json()["nodes"][0]["properties"]["名称"] == "NVIDIA"
    assert invalid.status_code == 422


def test_admin_unified_graph_endpoints_are_login_protected_and_expandable(
    tmp_path: Path,
) -> None:
    from app.main import create_app
    from app.schemas import GraphEdge, GraphNode, GraphPayload

    class FakeUnifiedGraphService:
        async def root(self):
            return GraphPayload(
                nodes=[
                    GraphNode(
                        id="taxonomy:l1:上游",
                        labels=["L1 产业层级"],
                        properties={"名称": "上游", "level": 0, "x": -230, "y": 0},
                    )
                ],
                edges=[],
            )

        async def expand(self, node_id: str, *, branch: str, cursor=None, limit: int):
            assert node_id == "taxonomy:l1:上游"
            assert branch == "hierarchy"
            assert cursor is None
            assert limit == 20
            return GraphPayload(
                nodes=[
                    GraphNode(
                        id="taxonomy:l2:上游|设计与产品",
                        labels=["L2 业务域"],
                        properties={"名称": "设计与产品", "level": 1, "x": 0, "y": 138},
                    )
                ],
                edges=[
                    GraphEdge(
                        id="taxonomy:l1:上游->taxonomy:l2:上游|设计与产品",
                        source="taxonomy:l1:上游",
                        target="taxonomy:l2:上游|设计与产品",
                        type="包含",
                    )
                ],
            )

    app = create_app(make_settings(tmp_path / "unified-graph.db"))
    app.state.unified_graph_service = FakeUnifiedGraphService()
    with TestClient(app) as client:
        unauthorized = client.get("/api/v1/admin/graph/unified/root")
        client.post("/api/v1/admin/login", json={"password": "admin-secret-value"})
        root = client.get("/api/v1/admin/graph/unified/root")
        expanded = client.post(
            "/api/v1/admin/graph/unified/expand",
            json={"node_id": "taxonomy:l1:上游", "branch": "hierarchy", "limit": 20},
        )

    assert unauthorized.status_code == 401
    assert root.status_code == 200
    assert root.json()["nodes"][0]["properties"]["名称"] == "上游"
    assert expanded.status_code == 200
    assert expanded.json()["edges"][0]["type"] == "包含"


def test_admin_governance_endpoints_run_scoped_background_jobs(tmp_path: Path) -> None:
    from app.main import create_app

    class FakeGovernanceService:
        async def list_sagas(self):
            return [
                {
                    "uuid": "saga-1",
                    "name": "AI 算力产业链",
                    "summary": "已有摘要",
                    "episode_count": 12,
                    "last_summarized_at": None,
                    "last_summarized_episode_valid_at": None,
                }
            ]

        async def list_communities(self):
            return [
                {
                    "uuid": "community-1",
                    "name": "AI 算力产业链社区",
                    "summary": "围绕 GPU、HBM、晶圆代工形成的结构聚类。",
                    "member_count": 18,
                    "representative_entities": ["NVIDIA", "TSMC", "SK hynix"],
                    "created_at": None,
                }
            ]

        async def summarize_saga(self, saga_id: str, progress=None):
            assert saga_id == "saga-1"
            if progress:
                await progress({"progress": 60, "message": "正在汇总"})
            return {"saga_id": saga_id, "summary": "新摘要", "episode_count": 12, "pages": 1}

        async def rebuild_communities(self, progress=None):
            if progress:
                await progress({"progress": 50, "message": "正在聚类"})
            return {"community_count": 4, "membership_count": 20}

    app = create_app(make_settings(tmp_path / "governance.db"))
    app.state.governance_service = FakeGovernanceService()
    with TestClient(app) as client:
        unauthorized = client.get("/api/v1/admin/governance/sagas")
        unauthorized_communities = client.get("/api/v1/admin/governance/communities")
        client.post("/api/v1/admin/login", json={"password": "admin-secret-value"})
        sagas = client.get("/api/v1/admin/governance/sagas")
        communities = client.get("/api/v1/admin/governance/communities")
        summary_job = client.post("/api/v1/admin/governance/sagas/saga-1/summarize")
        community_job = client.post("/api/v1/admin/governance/communities/rebuild")
        jobs = client.get("/api/v1/admin/jobs")
        summary_result = client.get(f"/api/v1/admin/jobs/{summary_job.json()['id']}")
        missing = client.get("/api/v1/admin/jobs/missing")

    assert unauthorized.status_code == 401
    assert unauthorized_communities.status_code == 401
    assert sagas.status_code == 200
    assert sagas.json()[0]["name"] == "AI 算力产业链"
    assert communities.status_code == 200
    assert communities.json()[0]["name"] == "AI 算力产业链社区"
    assert communities.json()[0]["representative_entities"] == ["NVIDIA", "TSMC", "SK hynix"]
    assert summary_job.status_code == 202
    assert community_job.status_code == 202
    assert {item["job_type"] for item in jobs.json()} == {
        "summarize_saga",
        "rebuild_communities",
    }
    assert summary_result.json()["status"] == "completed"
    assert summary_result.json()["result"]["summary"] == "新摘要"
    assert missing.status_code == 404
    assert missing.json()["detail"] == "后台任务不存在"


def test_admin_rejects_duplicate_active_community_rebuild(tmp_path: Path) -> None:
    from app.main import create_app

    app = create_app(make_settings(tmp_path / "governance-duplicate.db"))
    with TestClient(app) as client:
        client.post("/api/v1/admin/login", json={"password": "admin-secret-value"})
        active = app.state.repository.create_background_job(
            "rebuild_communities", {"group_id": "semiconductor_dc_kg"}
        )
        response = client.post("/api/v1/admin/governance/communities/rebuild")

    assert active["status"] == "queued"
    assert response.status_code == 409
    assert response.json()["detail"] == "Community 重建任务正在执行"


@pytest.mark.asyncio
async def test_governance_job_renews_short_lease_while_running(monkeypatch) -> None:
    from app.routers import admin

    class FakeRepository:
        def __init__(self) -> None:
            self.claim_leases: list[int] = []
            self.heartbeat_leases: list[int] = []
            self.updates: list[dict[str, object]] = []

        def claim_background_job(self, _job_id, _worker_id, *, lease_seconds):
            self.claim_leases.append(lease_seconds)
            return {
                "job_type": "summarize_saga",
                "payload": {"saga_id": "saga-1"},
            }

        def heartbeat_background_job(self, _job_id, _worker_id, *, lease_seconds):
            self.heartbeat_leases.append(lease_seconds)
            return {"status": "running"}

        def update_background_job(self, _job_id, **values):
            self.updates.append(values)
            return {"status": values.get("status", "running")}

    class SlowGovernanceService:
        async def summarize_saga(self, _saga_id, progress=None):
            await asyncio.sleep(0.04)
            return {"summary": "完成"}

    repository = FakeRepository()
    application = SimpleNamespace(
        state=SimpleNamespace(
            repository=repository,
            governance_service=SlowGovernanceService(),
        )
    )
    monkeypatch.setattr(admin, "GOVERNANCE_JOB_HEARTBEAT_SECONDS", 0.01, raising=False)

    await admin._run_governance_job(application, "job-1")

    assert repository.claim_leases == [300]
    assert repository.heartbeat_leases
    assert set(repository.heartbeat_leases) == {300}
    assert repository.updates[-1]["status"] == "completed"


@pytest.mark.asyncio
async def test_governance_job_cancels_work_immediately_when_lease_is_lost(
    monkeypatch,
) -> None:
    from app.routers import admin

    cancelled = asyncio.Event()

    class FakeRepository:
        def claim_background_job(self, _job_id, _worker_id, *, lease_seconds):
            return {
                "job_type": "rebuild_communities",
                "payload": {},
            }

        def heartbeat_background_job(self, _job_id, _worker_id, *, lease_seconds):
            return None

        def update_background_job(self, _job_id, **_values):
            return None

        def recover_interrupted_jobs(self, **_kwargs):
            return 1

    class BlockingGovernanceService:
        async def rebuild_communities(self, progress=None):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

    application = SimpleNamespace(
        state=SimpleNamespace(
            repository=FakeRepository(),
            governance_service=BlockingGovernanceService(),
        )
    )
    monkeypatch.setattr(admin, "GOVERNANCE_JOB_HEARTBEAT_SECONDS", 0.01)

    with pytest.raises(RuntimeError, match="失败状态写入失败"):
        await asyncio.wait_for(
            admin._run_governance_job(application, "job-lost"), timeout=0.2
        )

    assert cancelled.is_set()
