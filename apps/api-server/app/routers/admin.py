from __future__ import annotations

import asyncio
import secrets
import uuid
from contextlib import suppress
from dataclasses import replace
from typing import Any
from typing import Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from pydantic import BaseModel

from app.auth import ADMIN_COOKIE_MAX_AGE, ADMIN_COOKIE_NAME
from app.schemas import (
    BackgroundJob,
    CommunityOverview,
    DecisionSignalImportResult,
    GraphPayload,
    QueryRunSummary,
    QueryTrace,
    SagaOverview,
    UnifiedGraphExpandRequest,
)
from app.services.decision_signals import (
    DecisionSignalCategory,
    DecisionSignalSourceType,
    extract_text_from_upload,
    fetch_link_text,
    import_decision_signal,
)
from app.services.group_context import request_group_id


router = APIRouter(prefix="/api/v1/admin", tags=["管理端"])

GOVERNANCE_JOB_LEASE_SECONDS = 300
GOVERNANCE_JOB_HEARTBEAT_SECONDS = 60


class AdminLogin(BaseModel):
    password: str


def require_admin(request: Request) -> None:
    token = request.cookies.get(ADMIN_COOKIE_NAME)
    if request.app.state.cookie_signer.verify(token, "admin") != "admin":
        raise HTTPException(status_code=401, detail="管理员未登录")


@router.post("/login")
def login(payload: AdminLogin, request: Request, response: Response) -> dict[str, bool]:
    configured_password = request.app.state.settings.admin_password
    if not configured_password:
        raise HTTPException(status_code=503, detail="管理口令未配置")
    if not secrets.compare_digest(payload.password, configured_password):
        raise HTTPException(status_code=401, detail="管理口令错误")
    response.set_cookie(
        ADMIN_COOKIE_NAME,
        request.app.state.cookie_signer.sign(
            "admin", "admin", max_age=ADMIN_COOKIE_MAX_AGE
        ),
        max_age=ADMIN_COOKIE_MAX_AGE,
        httponly=True,
        secure=request.app.state.settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return {"authenticated": True}


@router.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(ADMIN_COOKIE_NAME, path="/", httponly=True, samesite="lax")
    return {"authenticated": False}


@router.get("/me", dependencies=[Depends(require_admin)])
def me() -> dict[str, bool]:
    return {"authenticated": True}


@router.post(
    "/decision-signals",
    dependencies=[Depends(require_admin)],
    response_model=DecisionSignalImportResult,
)
async def import_decision_signal_endpoint(
    request: Request,
    group_id: str | None = Form(default=None),
    category: DecisionSignalCategory = Form(...),
    source_type: DecisionSignalSourceType = Form(...),
    title: str = Form(...),
    source_url: str | None = Form(default=None),
    content: str = Form(default=""),
    keywords: str = Form(default=""),
    industry_impact: str = Form(default=""),
    dc_implication: str = Form(default=""),
    notes: str = Form(default=""),
    file: UploadFile | None = File(default=None),
) -> dict[str, Any]:
    resolved_group_id = request_group_id(request, group_id)
    title = title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="标题不能为空")
    source_url = source_url.strip() if source_url else None
    if source_type == "document":
        if file is None:
            raise HTTPException(status_code=422, detail="document 类型必须上传文件")
        try:
            content = extract_text_from_upload(
                file.filename or "upload.txt", await file.read()
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    elif source_type == "link":
        if not source_url:
            raise HTTPException(status_code=422, detail="link 类型必须提供 source_url")
        if not content.strip():
            content = await fetch_link_text(source_url)
    elif not content.strip():
        raise HTTPException(status_code=422, detail="text 类型必须提供 content")
    if not content.strip():
        raise HTTPException(status_code=422, detail="资料正文不能为空")

    from app.services.runtime import build_graphiti

    result = await import_decision_signal(
        settings=request.app.state.settings,
        graphiti_factory=build_graphiti,
        group_id=resolved_group_id,
        title=title,
        category=category,
        source_type=source_type,
        content=content,
        source_url=source_url,
        keywords=keywords,
        industry_impact=industry_impact,
        dc_implication=dc_implication,
        notes=notes,
        evidence_dir=getattr(request.app.state, "decision_signal_evidence_dir", None),
    )
    await _invalidate_qa_pipeline(request.app, resolved_group_id)
    return result


async def _invalidate_qa_pipeline(application: Any, group_id: str) -> None:
    pipeline = None
    if group_id == application.state.settings.group_id:
        pipeline = application.state.qa_pipeline
        application.state.qa_pipeline = None
    cached = application.state.qa_pipeline_by_group.pop(group_id, None)
    if cached is not None and cached is not pipeline:
        close = getattr(cached, "close", None)
        if close is not None:
            with suppress(Exception):
                await close()
    if pipeline is not None:
        close = getattr(pipeline, "close", None)
        if close is not None:
            with suppress(Exception):
                await close()


@router.get(
    "/traces",
    dependencies=[Depends(require_admin)],
    response_model=list[QueryRunSummary],
)
def traces(request: Request) -> list[dict[str, Any]]:
    return request.app.state.repository.list_query_runs()


@router.get(
    "/traces/{run_id}",
    dependencies=[Depends(require_admin)],
    response_model=QueryTrace,
)
def trace_detail(run_id: str, request: Request) -> QueryTrace:
    trace = request.app.state.repository.get_query_trace(run_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="查询追踪不存在")
    return trace


async def _graph_service(request: Request, group_id: str | None = None):
    resolved_group_id = request_group_id(request, group_id)
    if resolved_group_id == request.app.state.settings.group_id:
        service = request.app.state.graph_service
    else:
        service = request.app.state.graph_service_by_group.get(resolved_group_id)
    if service is not None:
        return service
    async with request.app.state.graph_service_lock:
        if resolved_group_id == request.app.state.settings.group_id and request.app.state.graph_service is not None:
            return request.app.state.graph_service
        cached = request.app.state.graph_service_by_group.get(resolved_group_id)
        if cached is not None:
            return cached
        if resolved_group_id == request.app.state.settings.group_id:
            from app.services.graph import Neo4jGraphService

            request.app.state.graph_service = Neo4jGraphService.from_settings(
                request.app.state.settings
            )
            request.app.state.graph_service_by_group[resolved_group_id] = request.app.state.graph_service
            return request.app.state.graph_service
        from app.services.graph import Neo4jGraphService

        service = Neo4jGraphService.from_settings(
            replace(request.app.state.settings, group_id=resolved_group_id)
        )
        request.app.state.graph_service_by_group[resolved_group_id] = service
        return service


@router.get("/graph/stats", dependencies=[Depends(require_admin)])
async def graph_stats(
    request: Request, group_id: str | None = Query(default=None)
) -> dict[str, int]:
    return await (await _graph_service(request, group_id)).get_stats()


@router.get(
    "/graph/views/{view}",
    dependencies=[Depends(require_admin)],
    response_model=GraphPayload,
)
async def graph_view(
    view: Literal["business", "temporal", "governance"],
    request: Request,
    group_id: str | None = Query(default=None),
    limit: int = Query(default=300, ge=1, le=500),
) -> GraphPayload:
    return await (await _graph_service(request, group_id)).get_view(view, limit=limit)


async def _unified_graph_service(request: Request, group_id: str | None = None):
    resolved_group_id = request_group_id(request, group_id)
    if resolved_group_id == request.app.state.settings.group_id:
        service = request.app.state.unified_graph_service
    else:
        service = request.app.state.unified_graph_service_by_group.get(resolved_group_id)
    if service is not None:
        return service
    async with request.app.state.unified_graph_service_lock:
        if resolved_group_id == request.app.state.settings.group_id and request.app.state.unified_graph_service is not None:
            return request.app.state.unified_graph_service
        cached = request.app.state.unified_graph_service_by_group.get(resolved_group_id)
        if cached is not None:
            return cached
        if resolved_group_id == request.app.state.settings.group_id:
            from app.services.unified_graph import UnifiedGraphService

            request.app.state.unified_graph_service = UnifiedGraphService.from_settings(
                request.app.state.settings
            )
            request.app.state.unified_graph_service_by_group[resolved_group_id] = request.app.state.unified_graph_service
            return request.app.state.unified_graph_service
        from app.services.unified_graph import UnifiedGraphService

        service = UnifiedGraphService.from_settings(
            replace(request.app.state.settings, group_id=resolved_group_id)
        )
        request.app.state.unified_graph_service_by_group[resolved_group_id] = service
        return service


@router.get(
    "/graph/unified/root",
    dependencies=[Depends(require_admin)],
    response_model=GraphPayload,
)
async def unified_graph_root(
    request: Request, group_id: str | None = Query(default=None)
) -> GraphPayload:
    return await (await _unified_graph_service(request, group_id)).root()


@router.post(
    "/graph/unified/expand",
    dependencies=[Depends(require_admin)],
    response_model=GraphPayload,
)
async def unified_graph_expand(
    payload: UnifiedGraphExpandRequest,
    request: Request,
    group_id: str | None = Query(default=None),
) -> GraphPayload:
    return await (await _unified_graph_service(request, group_id)).expand(
        payload.node_id,
        branch=payload.branch,
        cursor=payload.cursor,
        limit=payload.limit,
    )


async def _governance_service(request: Request, group_id: str | None = None):
    resolved_group_id = request_group_id(request, group_id)
    if resolved_group_id == request.app.state.settings.group_id:
        service = request.app.state.governance_service
    else:
        service = request.app.state.governance_service_by_group.get(resolved_group_id)
    if service is not None:
        return service
    async with request.app.state.governance_service_lock:
        if resolved_group_id == request.app.state.settings.group_id and request.app.state.governance_service is not None:
            return request.app.state.governance_service
        cached = request.app.state.governance_service_by_group.get(resolved_group_id)
        if cached is not None:
            return cached
        if resolved_group_id == request.app.state.settings.group_id:
            from app.services.governance import GovernanceService

            request.app.state.governance_service = GovernanceService.from_settings(
                request.app.state.settings
            )
            request.app.state.governance_service_by_group[resolved_group_id] = request.app.state.governance_service
            return request.app.state.governance_service
        from app.services.governance import GovernanceService

        service = GovernanceService.from_settings(
            replace(request.app.state.settings, group_id=resolved_group_id)
        )
        request.app.state.governance_service_by_group[resolved_group_id] = service
        return service


@router.get(
    "/governance/sagas",
    dependencies=[Depends(require_admin)],
    response_model=list[SagaOverview],
)
async def list_sagas(
    request: Request, group_id: str | None = Query(default=None)
) -> list[dict[str, Any]]:
    return await (await _governance_service(request, group_id)).list_sagas()


@router.get(
    "/governance/communities",
    dependencies=[Depends(require_admin)],
    response_model=list[CommunityOverview],
)
async def list_communities(
    request: Request, group_id: str | None = Query(default=None)
) -> list[dict[str, Any]]:
    return await (await _governance_service(request, group_id)).list_communities()


@router.post(
    "/governance/sagas/{saga_id}/summarize",
    dependencies=[Depends(require_admin)],
    response_model=BackgroundJob,
    status_code=202,
)
async def summarize_saga(
    saga_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    group_id: str | None = Query(default=None),
) -> dict[str, Any]:
    resolved_group_id = request_group_id(request, group_id)
    job = request.app.state.repository.create_background_job(
        "summarize_saga", {"saga_id": saga_id, "group_id": resolved_group_id}
    )
    background_tasks.add_task(_run_governance_job, request.app, job["id"])
    return job


@router.post(
    "/governance/communities/rebuild",
    dependencies=[Depends(require_admin)],
    response_model=BackgroundJob,
    status_code=202,
)
async def rebuild_communities(
    request: Request,
    background_tasks: BackgroundTasks,
    group_id: str | None = Query(default=None),
) -> dict[str, Any]:
    resolved_group_id = request_group_id(request, group_id)
    request.app.state.repository.recover_interrupted_jobs(include_queued=False)
    active = next(
        (
            job
            for job in request.app.state.repository.list_background_jobs()
            if job["job_type"] == "rebuild_communities"
            and job["status"] in {"queued", "running"}
        ),
        None,
    )
    if active is not None:
        raise HTTPException(status_code=409, detail="Community 重建任务正在执行")
    job = request.app.state.repository.create_background_job(
        "rebuild_communities", {"group_id": resolved_group_id}
    )
    background_tasks.add_task(_run_governance_job, request.app, job["id"])
    return job


@router.get(
    "/jobs",
    dependencies=[Depends(require_admin)],
    response_model=list[BackgroundJob],
)
def list_jobs(request: Request) -> list[dict[str, Any]]:
    request.app.state.repository.recover_interrupted_jobs(include_queued=False)
    return [
        job
        for job in request.app.state.repository.list_background_jobs()
        if job["job_type"] in {"summarize_saga", "rebuild_communities"}
    ]


@router.get(
    "/jobs/{job_id}",
    dependencies=[Depends(require_admin)],
    response_model=BackgroundJob,
)
def job_detail(job_id: str, request: Request) -> dict[str, Any]:
    request.app.state.repository.recover_interrupted_jobs(include_queued=False)
    job = request.app.state.repository.get_background_job(job_id)
    if job is None or job["job_type"] not in {"summarize_saga", "rebuild_communities"}:
        raise HTTPException(status_code=404, detail="后台任务不存在")
    return job


async def _run_governance_job(application: Any, job_id: str) -> None:
    repository = application.state.repository
    worker_id = f"governance-{uuid.uuid4()}"
    job = repository.claim_background_job(
        job_id,
        worker_id,
        lease_seconds=GOVERNANCE_JOB_LEASE_SECONDS,
    )
    if job is None:
        return

    def renew_lease() -> None:
        renewed = repository.heartbeat_background_job(
            job_id,
            worker_id,
            lease_seconds=GOVERNANCE_JOB_LEASE_SECONDS,
        )
        if renewed is None:
            raise RuntimeError("治理任务租约已丢失")

    async def heartbeat_loop() -> None:
        while True:
            await asyncio.sleep(GOVERNANCE_JOB_HEARTBEAT_SECONDS)
            renew_lease()

    async def progress(payload: dict[str, Any]) -> None:
        renew_lease()
        updated = repository.update_background_job(
            job_id, result=payload, worker_id=worker_id
        )
        if updated is None:
            raise RuntimeError("治理任务进度写入失败，任务租约可能已丢失")

    async def run_work() -> dict[str, Any]:
        service = await _governance_service_for_job(application, job["payload"])
        if job["job_type"] == "summarize_saga":
            return await service.summarize_saga(
                str(job["payload"]["saga_id"]), progress=progress
            )
        if job["job_type"] == "rebuild_communities":
            return await service.rebuild_communities(progress=progress)
        raise ValueError("不支持的治理任务")

    work_task = asyncio.create_task(run_work())
    heartbeat_task = asyncio.create_task(heartbeat_loop())
    try:
        await asyncio.sleep(0)
        done, _ = await asyncio.wait(
            {work_task, heartbeat_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if heartbeat_task in done:
            heartbeat_task.result()
            raise RuntimeError("治理任务心跳意外停止")

        result = work_task.result()
        renew_lease()
        updated = repository.update_background_job(
            job_id, status="completed", result=result, worker_id=worker_id
        )
        if updated is None:
            raise RuntimeError("治理任务完成状态写入失败，任务租约可能已丢失")
    except Exception as exc:
        if not work_task.done():
            work_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await work_task
        failed = repository.update_background_job(
            job_id,
            status="failed",
            error=f"治理任务执行失败：{exc}",
            worker_id=worker_id,
        )
        if failed is None:
            repository.recover_interrupted_jobs(include_queued=False)
            raise RuntimeError("治理任务失败状态写入失败，任务租约可能已丢失") from exc
    finally:
        for task in (work_task, heartbeat_task):
            task.cancel()
        with suppress(asyncio.CancelledError, Exception):
            await asyncio.gather(work_task, heartbeat_task)


async def _governance_service_for_job(application: Any, payload: dict[str, Any]):
    settings = getattr(application.state, "settings", None)
    fallback_service = getattr(application.state, "governance_service", None)
    if settings is None:
        if fallback_service is None:
            raise RuntimeError("治理服务未初始化")
        return fallback_service

    default_group_id = settings.group_id
    group_id = str(payload.get("group_id") or default_group_id)
    cache = getattr(application.state, "governance_service_by_group", None)
    if group_id == default_group_id:
        service = fallback_service
    else:
        service = cache.get(group_id) if cache is not None else None
    if service is not None:
        return service

    lock = getattr(application.state, "governance_service_lock", None)
    if lock is None:
        if fallback_service is None:
            raise RuntimeError("治理服务未初始化")
        return fallback_service

    async with lock:
        if group_id == default_group_id and application.state.governance_service is not None:
            return application.state.governance_service
        if cache is not None and group_id != default_group_id and group_id in cache:
            return cache[group_id]

        from app.services.governance import GovernanceService

        if group_id == default_group_id:
            application.state.governance_service = GovernanceService.from_settings(settings)
            if cache is not None:
                cache[group_id] = application.state.governance_service
            return application.state.governance_service

        service = GovernanceService.from_settings(replace(settings, group_id=group_id))
        if cache is not None:
            cache[group_id] = service
        return service
