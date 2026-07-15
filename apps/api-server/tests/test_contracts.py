from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest


def test_settings_use_documented_defaults_and_allow_injection() -> None:
    from app.config import Settings

    defaults = Settings.from_environment({})
    assert defaults.neo4j_uri == "bolt://localhost:7687"
    assert defaults.neo4j_user == "neo4j"
    assert defaults.neo4j_password == "password"
    assert defaults.group_id == "semiconductor_dc_kg"
    assert defaults.api_port == 8001
    assert defaults.app_env == "development"
    assert defaults.cookie_secure is True
    assert Path(defaults.sqlite_path).is_absolute()
    assert defaults.llm_base_url == "https://api.siliconflow.cn/v1"
    assert defaults.llm_model == "deepseek-ai/DeepSeek-V3.2"
    assert defaults.embedding_base_url == "https://api.siliconflow.cn/v1"
    assert defaults.embedding_model == "BAAI/bge-m3"
    assert defaults.reranker_model == "BAAI/bge-reranker-v2-m3"
    assert defaults.siliconflow_api_key == ""
    assert defaults.retrieval_slice_limit == 20
    assert defaults.candidate_pool_limit == 60
    assert defaults.final_result_limit == 12
    assert defaults.search_timeout_seconds == 20

    injected = Settings.from_environment(
        {
            "NEO4J_URI": "bolt://graph:7687",
            "NEO4J_USER": "tester",
            "NEO4J_PASSWORD": "secret",
            "GROUP_ID": "test-group",
            "API_PORT": "9001",
            "ADMIN_PASSWORD": "admin-secret",
            "SESSION_SECRET": "cookie-secret",
            "SQLITE_PATH": ":memory:",
            "SILICONFLOW_API_KEY": "server-only-key",
            "RETRIEVAL_SLICE_LIMIT": "18",
            "RETRIEVAL_CANDIDATE_POOL_LIMIT": "50",
            "RETRIEVAL_FINAL_RESULT_LIMIT": "10",
            "RETRIEVAL_SEARCH_TIMEOUT_SECONDS": "0.25",
        }
    )
    assert injected.api_port == 9001
    assert injected.admin_password == "admin-secret"
    assert injected.session_secret == "cookie-secret"
    assert injected.sqlite_path == ":memory:"
    assert injected.siliconflow_api_key == "server-only-key"
    assert injected.retrieval_slice_limit == 18
    assert injected.candidate_pool_limit == 50
    assert injected.final_result_limit == 10
    assert injected.search_timeout_seconds == 0.25


def test_settings_reject_non_positive_or_inconsistent_retrieval_limits() -> None:
    from app.config import Settings

    with pytest.raises(ValueError, match="检索限制"):
        Settings.from_environment({"RETRIEVAL_SLICE_LIMIT": "0"})
    with pytest.raises(ValueError, match="候选池"):
        Settings.from_environment(
            {
                "RETRIEVAL_CANDIDATE_POOL_LIMIT": "10",
                "RETRIEVAL_FINAL_RESULT_LIMIT": "12",
            }
        )
    with pytest.raises(ValueError, match="超时"):
        Settings.from_environment({"RETRIEVAL_SEARCH_TIMEOUT_SECONDS": "0"})


def test_settings_resolve_sqlite_paths_from_project_root_regardless_of_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import PROJECT_ROOT, Settings

    monkeypatch.chdir(tmp_path)
    defaults = Settings.from_environment({})
    relative = Settings.from_environment({"SQLITE_PATH": "custom/observability.db"})
    absolute_path = tmp_path / "absolute.db"
    absolute = Settings.from_environment({"SQLITE_PATH": str(absolute_path)})

    assert Path(defaults.sqlite_path) == PROJECT_ROOT / "data/runtime/qa_observability.db"
    assert Path(relative.sqlite_path) == PROJECT_ROOT / "custom/observability.db"
    assert Path(absolute.sqlite_path) == absolute_path.resolve()


def test_non_development_requires_stable_session_secret() -> None:
    from app.config import Settings
    from app.main import create_app

    with pytest.raises(ValueError, match="非开发环境必须设置 SESSION_SECRET"):
        Settings.from_environment({"APP_ENV": "production"})

    with pytest.raises(ValueError, match="非开发环境必须设置 SESSION_SECRET"):
        create_app(Settings(app_env="production", session_secret=""))

    production = Settings.from_environment(
        {"APP_ENV": "production", "SESSION_SECRET": "stable-secret"}
    )
    development = Settings.from_environment(
        {"APP_ENV": "development", "COOKIE_SECURE": "false"}
    )
    assert production.cookie_secure is True
    assert development.cookie_secure is False


def test_public_contracts_serialize_evidence_temporal_and_algorithm_fields() -> None:
    from app.schemas import (
        AnswerResponse,
        Citation,
        RetrievalCandidate,
        RetrievalSlice,
        TrustDimension,
        TrustProfile,
    )

    candidate = RetrievalCandidate(
        id="candidate-1",
        title="英伟达年度报告",
        content="数据中心业务披露",
        score=0.94,
        algorithm="hybrid_vector_graph",
        evidence_level="A",
        confidence="high",
        valid_from="2025-01-01",
        valid_to=None,
        verification_status="verified",
    )
    retrieval_slice = RetrievalSlice(
        id="slice-1",
        name="企业证据",
        algorithm="hybrid_vector_graph",
        query="英伟达 数据中心",
        candidates=[candidate],
    )
    trust = TrustProfile(
        evidence=TrustDimension(
            key="evidence",
            label="证据质量",
            level="high",
            explanation="官方披露",
            details={"grades": ["A"]},
        ),
        confidence=TrustDimension(
            key="confidence",
            label="事实置信度",
            level="high",
            explanation="核心事实均为高置信度",
        ),
        freshness=TrustDimension(
            key="freshness",
            label="时效性",
            level="high",
            explanation="仍在有效期",
        ),
        verification=TrustDimension(
            key="verification",
            label="核验状态",
            level="high",
            explanation="公开资料已确认",
        ),
    )
    response = AnswerResponse(
        conversation_id="conversation-1",
        message_id="message-1",
        answer="回答",
        citations=[
            Citation(
                evidence_id="citation-1",
                title="英伟达年度报告",
                grade="A",
                publish_date="2025-01-01",
                retrieved_at="2026-07-15",
                limitations="无",
            )
        ],
        trust_profile=trust,
        retrieval_slices=[retrieval_slice],
    )

    payload = response.model_dump(mode="json")
    assert payload["citations"][0]["grade"] == "A"
    assert payload["citations"][0]["publish_date"] == "2025-01-01"
    assert payload["trust_profile"]["verification"]["level"] == "high"
    assert "overall_confidence" not in payload["trust_profile"]
    assert "summary_label" not in payload["trust_profile"]
    assert set(payload["trust_profile"]) == {
        "evidence",
        "confidence",
        "freshness",
        "verification",
    }
    assert payload["retrieval_slices"][0]["algorithm"] == "hybrid_vector_graph"


def test_trace_graph_and_background_job_contracts_round_trip() -> None:
    from app.schemas import (
        BackgroundJob,
        GraphEdge,
        GraphNode,
        GraphPayload,
        LlmCallTrace,
        QueryStage,
        QueryTrace,
    )

    now = datetime.now(UTC)
    trace = QueryTrace(
        id="run-1",
        conversation_id="conversation-1",
        query="测试问题",
        status="completed",
        stages=[QueryStage(name="retrieval", status="completed", algorithm="hybrid")],
        retrieval_slices=[],
        llm_calls=[
            LlmCallTrace(
                id="call-1",
                query_run_id="run-1",
                model="test-model",
                purpose="answer",
                status="completed",
            )
        ],
        created_at=now,
        updated_at=now,
    )
    graph = GraphPayload(
        nodes=[GraphNode(id="n1", labels=["Company"], properties={"name": "NVIDIA"})],
        edges=[GraphEdge(id="e1", source="n1", target="n2", type="生产")],
    )
    job = BackgroundJob(
        id="job-1",
        job_type="refresh",
        status="queued",
        payload={"scope": "all"},
        created_at=now,
        updated_at=now,
    )

    assert QueryTrace.model_validate(trace.model_dump()).id == "run-1"
    assert GraphPayload.model_validate(graph.model_dump()).edges[0].type == "生产"
    assert BackgroundJob.model_validate(job.model_dump()).payload == {"scope": "all"}
