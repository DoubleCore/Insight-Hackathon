from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


DEFAULT_NEO4J_URI = "bolt://localhost:7687"
DEFAULT_NEO4J_USER = "neo4j"
DEFAULT_NEO4J_PASSWORD = "password"
DEFAULT_GROUP_ID = "semiconductor_dc_kg"
DEFAULT_API_PORT = 8001
DEFAULT_LLM_BASE_URL = "https://api.siliconflow.cn/v1"
DEFAULT_LLM_MODEL = "deepseek-ai/DeepSeek-V3.2"
DEFAULT_EMBEDDING_BASE_URL = "https://api.siliconflow.cn/v1"
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"
DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
DEFAULT_RETRIEVAL_SLICE_LIMIT = 20
DEFAULT_CANDIDATE_POOL_LIMIT = 60
DEFAULT_FINAL_RESULT_LIMIT = 12
DEFAULT_SEARCH_TIMEOUT_SECONDS = 20.0
DEFAULT_OTEL_SERVICE_NAME = "dual-frontend-api-server"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SQLITE_PATH = str(PROJECT_ROOT / "data/runtime/qa_observability.db")


def _parse_boolean(value: str, variable_name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{variable_name} 必须是 true 或 false")


def _resolve_sqlite_path(value: str) -> str:
    if value == ":memory:":
        return value
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return str(path.resolve())


@dataclass(frozen=True, slots=True)
class Settings:
    app_env: str = "development"
    neo4j_uri: str = DEFAULT_NEO4J_URI
    neo4j_user: str = DEFAULT_NEO4J_USER
    neo4j_password: str = DEFAULT_NEO4J_PASSWORD
    group_id: str = DEFAULT_GROUP_ID
    api_port: int = DEFAULT_API_PORT
    admin_password: str = ""
    session_secret: str = ""
    sqlite_path: str = DEFAULT_SQLITE_PATH
    cookie_secure: bool = True
    llm_base_url: str = DEFAULT_LLM_BASE_URL
    llm_model: str = DEFAULT_LLM_MODEL
    embedding_base_url: str = DEFAULT_EMBEDDING_BASE_URL
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    reranker_model: str = DEFAULT_RERANKER_MODEL
    siliconflow_api_key: str = ""
    retrieval_slice_limit: int = DEFAULT_RETRIEVAL_SLICE_LIMIT
    candidate_pool_limit: int = DEFAULT_CANDIDATE_POOL_LIMIT
    final_result_limit: int = DEFAULT_FINAL_RESULT_LIMIT
    search_timeout_seconds: float = DEFAULT_SEARCH_TIMEOUT_SECONDS
    otel_enabled: bool = False
    otel_service_name: str = DEFAULT_OTEL_SERVICE_NAME
    otel_exporter_otlp_endpoint: str = ""
    tavily_api_key: str = ""
    bocha_api_key: str = ""
    bocha_search_url: str = ""

    def validate_for_startup(self) -> None:
        if self.app_env.lower() != "development" and not self.session_secret:
            raise ValueError("非开发环境必须设置 SESSION_SECRET")
        if min(
            self.retrieval_slice_limit,
            self.candidate_pool_limit,
            self.final_result_limit,
        ) <= 0:
            raise ValueError("检索限制必须为正整数")
        if self.candidate_pool_limit < self.final_result_limit:
            raise ValueError("候选池限制不得小于最终结果限制")
        if self.search_timeout_seconds <= 0:
            raise ValueError("检索超时必须大于 0 秒")

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if environment is None else environment
        app_env = env.get("APP_ENV", "development").strip().lower()
        session_secret = env.get("SESSION_SECRET", "")
        if not session_secret and app_env == "development":
            session_secret = secrets.token_urlsafe(32)
        settings = cls(
            app_env=app_env,
            neo4j_uri=env.get("NEO4J_URI", DEFAULT_NEO4J_URI),
            neo4j_user=env.get("NEO4J_USER", DEFAULT_NEO4J_USER),
            neo4j_password=env.get("NEO4J_PASSWORD", DEFAULT_NEO4J_PASSWORD),
            group_id=env.get("GROUP_ID", DEFAULT_GROUP_ID),
            api_port=int(env.get("API_PORT", str(DEFAULT_API_PORT))),
            admin_password=env.get("ADMIN_PASSWORD", ""),
            session_secret=session_secret,
            sqlite_path=_resolve_sqlite_path(
                env.get("SQLITE_PATH", DEFAULT_SQLITE_PATH)
            ),
            cookie_secure=_parse_boolean(env.get("COOKIE_SECURE", "true"), "COOKIE_SECURE"),
            llm_base_url=env.get("GRAPHITI_LLM_BASE_URL", DEFAULT_LLM_BASE_URL),
            llm_model=env.get("GRAPHITI_LLM_MODEL", DEFAULT_LLM_MODEL),
            embedding_base_url=env.get(
                "GRAPHITI_EMBEDDING_BASE_URL", DEFAULT_EMBEDDING_BASE_URL
            ),
            embedding_model=env.get(
                "GRAPHITI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL
            ),
            reranker_model=env.get(
                "GRAPHITI_RERANKER_MODEL", DEFAULT_RERANKER_MODEL
            ),
            siliconflow_api_key=env.get("SILICONFLOW_API_KEY", ""),
            retrieval_slice_limit=int(
                env.get(
                    "RETRIEVAL_SLICE_LIMIT", str(DEFAULT_RETRIEVAL_SLICE_LIMIT)
                )
            ),
            candidate_pool_limit=int(
                env.get(
                    "RETRIEVAL_CANDIDATE_POOL_LIMIT",
                    str(DEFAULT_CANDIDATE_POOL_LIMIT),
                )
            ),
            final_result_limit=int(
                env.get(
                    "RETRIEVAL_FINAL_RESULT_LIMIT", str(DEFAULT_FINAL_RESULT_LIMIT)
                )
            ),
            search_timeout_seconds=float(
                env.get(
                    "RETRIEVAL_SEARCH_TIMEOUT_SECONDS",
                    str(DEFAULT_SEARCH_TIMEOUT_SECONDS),
                )
            ),
            otel_enabled=_parse_boolean(env.get("OTEL_ENABLED", "false"), "OTEL_ENABLED"),
            otel_service_name=env.get("OTEL_SERVICE_NAME", DEFAULT_OTEL_SERVICE_NAME),
            otel_exporter_otlp_endpoint=env.get("OTEL_EXPORTER_OTLP_ENDPOINT", ""),
            tavily_api_key=env.get("TAVILY_API_KEY", ""),
            bocha_api_key=env.get("BOCHA_API_KEY", ""),
            bocha_search_url=env.get("BOCHA_SEARCH_URL", ""),
        )
        settings.validate_for_startup()
        return settings
