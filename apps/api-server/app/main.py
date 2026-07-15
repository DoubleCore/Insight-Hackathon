from __future__ import annotations

import sqlite3
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.auth import ADMIN_COOKIE_NAME, USER_COOKIE_NAME, CookieSigner
from app.config import Settings
from app.routers import admin, groups, industry_search, user
from app.storage import Repository
from app.services.events import RequestEventBroker
from app.services.tracing import configure_tracing
from app.services.web_search import WebSearchService


ALLOWED_ORIGINS = ["http://127.0.0.1:7870", "http://127.0.0.1:7871"]


def create_app(settings: Settings | None = None) -> FastAPI:
    configured_settings = settings or Settings.from_environment()
    configured_settings.validate_for_startup()
    configure_tracing(configured_settings)
    repository = Repository(configured_settings.sqlite_path)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        repository.initialize()
        repository.recover_interrupted_query_runs()
        repository.recover_interrupted_jobs(include_active=True)
        yield
        services = [
            application.state.qa_pipeline,
            application.state.graph_service,
            application.state.unified_graph_service,
            application.state.governance_service,
            *application.state.qa_pipeline_by_group.values(),
            *application.state.graph_service_by_group.values(),
            *application.state.unified_graph_service_by_group.values(),
            *application.state.governance_service_by_group.values(),
        ]
        closed: set[int] = set()
        for service in services:
            if service is not None and id(service) not in closed and hasattr(service, "close"):
                closed.add(id(service))
                await service.close()
        await application.state.web_search_service.close()

    application = FastAPI(title="双前端验收平台 API", lifespan=lifespan)
    application.state.settings = configured_settings
    application.state.repository = repository
    application.state.cookie_signer = CookieSigner(configured_settings.session_secret)
    application.state.event_broker = RequestEventBroker()
    application.state.qa_pipeline = None
    application.state.qa_pipeline_by_group = {}
    application.state.pipeline_lock = asyncio.Lock()
    application.state.graph_service = None
    application.state.graph_service_by_group = {}
    application.state.graph_service_lock = asyncio.Lock()
    application.state.unified_graph_service = None
    application.state.unified_graph_service_by_group = {}
    application.state.unified_graph_service_lock = asyncio.Lock()
    application.state.governance_service = None
    application.state.governance_service_by_group = {}
    application.state.governance_service_lock = asyncio.Lock()
    application.state.web_search_service = WebSearchService(configured_settings)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _: Request, __: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422, content={"detail": "请求参数不完整或格式错误"}
        )

    @application.exception_handler(sqlite3.Error)
    async def sqlite_error_handler(_: Request, __: sqlite3.Error) -> JSONResponse:
        return JSONResponse(
            status_code=503, content={"detail": "数据库服务暂时不可用"}
        )

    @application.exception_handler(StarletteHTTPException)
    async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        standard_details = {
            "Not Found": "接口不存在",
            "Method Not Allowed": "请求方法不允许",
        }
        detail = standard_details.get(str(exc.detail), exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})

    application.include_router(user.router)
    application.include_router(admin.router)
    application.include_router(groups.router)
    application.include_router(industry_search.router)

    @application.get("/health")
    def health() -> dict[str, str]:
        repository.list_query_runs(limit=1)
        return {"status": "ok", "database": "ok"}

    return application


app = create_app()

__all__ = [
    "ADMIN_COOKIE_NAME",
    "USER_COOKIE_NAME",
    "app",
    "create_app",
]
