from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from app.auth import USER_COOKIE_MAX_AGE, USER_COOKIE_NAME
from app.services.group_context import request_group_id
from app.services.tracing import safe_hash, start_span


router = APIRouter(prefix="/api/v1/user", tags=["用户端"])


class ConversationCreate(BaseModel):
    title: str | None = None


class MessageCreate(BaseModel):
    content: str
    group_id: str | None = None

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("问题不能为空")
        return normalized


def _public_conversation(conversation: dict[str, Any]) -> dict[str, Any]:
    return {
        key: conversation[key]
        for key in ("id", "title", "created_at", "updated_at")
    }


def _user_identity(request: Request, response: Response) -> str:
    signer = request.app.state.cookie_signer
    owner_id = signer.verify(request.cookies.get(USER_COOKIE_NAME), "user")
    if owner_id is None:
        owner_id = str(uuid4())
        response.set_cookie(
            USER_COOKIE_NAME,
            signer.sign(owner_id, "user"),
            max_age=USER_COOKIE_MAX_AGE,
            httponly=True,
            secure=request.app.state.settings.cookie_secure,
            samesite="lax",
            path="/",
        )
    return owner_id


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
def create_conversation(
    request: Request,
    response: Response,
    payload: ConversationCreate | None = None,
) -> dict[str, Any]:
    owner_id = _user_identity(request, response)
    conversation = request.app.state.repository.create_conversation(
        owner_id, title=payload.title if payload else None
    )
    return _public_conversation(conversation)


@router.get("/conversations")
def list_conversations(request: Request, response: Response) -> list[dict[str, Any]]:
    owner_id = _user_identity(request, response)
    conversations = request.app.state.repository.list_conversations(owner_id)
    return [_public_conversation(item) for item in conversations]


@router.get("/conversations/{conversation_id}/messages")
def list_messages(
    conversation_id: str, request: Request, response: Response
) -> list[dict[str, Any]]:
    owner_id = _user_identity(request, response)
    conversation = request.app.state.repository.get_conversation(conversation_id)
    if conversation is None or conversation["owner_id"] != owner_id:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    return request.app.state.repository.list_messages(conversation_id)


def _owned_run(request: Request, owner_id: str, request_id: str) -> dict[str, Any]:
    run = request.app.state.repository.get_query_run(request_id)
    if run is None:
        raise HTTPException(status_code=404, detail="问答请求不存在或无权访问")
    conversation = request.app.state.repository.get_conversation(run["conversation_id"])
    if conversation is None or conversation["owner_id"] != owner_id:
        raise HTTPException(status_code=404, detail="问答请求不存在或无权访问")
    return run


async def _pipeline(request: Request, group_id: str):
    if group_id == request.app.state.settings.group_id:
        pipeline = request.app.state.qa_pipeline
    else:
        pipeline = request.app.state.qa_pipeline_by_group.get(group_id)
    if pipeline is not None:
        return pipeline
    async with request.app.state.pipeline_lock:
        if group_id == request.app.state.settings.group_id and request.app.state.qa_pipeline is not None:
            return request.app.state.qa_pipeline
        cached = request.app.state.qa_pipeline_by_group.get(group_id)
        if cached is not None:
            return cached
        if group_id == request.app.state.settings.group_id:
            from app.services.runtime import build_default_pipeline

            request.app.state.qa_pipeline = build_default_pipeline(
                request.app.state.settings, request.app.state.repository
            )
            request.app.state.qa_pipeline_by_group[group_id] = request.app.state.qa_pipeline
            return request.app.state.qa_pipeline
        from dataclasses import replace
        from app.services.runtime import build_default_pipeline

        settings = replace(request.app.state.settings, group_id=group_id)
        pipeline = build_default_pipeline(settings, request.app.state.repository)
        request.app.state.qa_pipeline_by_group[group_id] = pipeline
        return pipeline


async def _execute_request(
    request: Request,
    conversation_id: str,
    request_id: str,
    question: str,
    group_id: str,
) -> None:
    broker = request.app.state.event_broker

    async def emit(event: str, data: dict[str, Any]) -> None:
        await broker.publish(request_id, event, data)

    question_hash = safe_hash(question.strip().casefold())
    with start_span(
        'qa.request',
        {
            'query_run_id': request_id,
            'conversation_id': conversation_id,
            'group_id': group_id,
            'question_length': len(question),
            'question_hash': question_hash,
        },
    ) as span:
        if span.trace_id is not None:
            request.app.state.repository.update_query_run(request_id, trace_id=span.trace_id)
        try:
            pipeline = await _pipeline(request, group_id)
            result = await pipeline.run(
                conversation_id=conversation_id,
                query_run_id=request_id,
                question=question,
                emit=emit,
            )
            message = request.app.state.repository.get_message(result.message_id)
            if message is None:
                message = request.app.state.repository.append_message(
                    conversation_id,
                    "assistant",
                    result.answer,
                    metadata={
                        "request_id": request_id,
                        "trace_id": span.trace_id,
                        "citations": [item.model_dump(mode="json") for item in result.citations],
                        "trust_profile": result.trust_profile.model_dump(mode="json"),
                        "degraded": result.degraded,
                        "degradation_reason": result.degradation_reason,
                    },
                )
                request.app.state.repository.update_query_run(
                    request_id, status="completed", answer=result.answer
                )
            else:
                request.app.state.repository.update_query_run(
                    request_id, status="completed", answer=result.answer
                )
            await emit(
                "completed",
                {"request_id": request_id, "message_id": message["id"]},
            )
        except Exception as exc:
            request.app.state.repository.update_query_run(
                request_id,
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
            )
            await emit(
                "error",
                {"request_id": request_id, "message": "问答处理失败，请稍后重试"},
            )


@router.post(
    "/conversations/{conversation_id}/messages",
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_message(
    conversation_id: str,
    payload: MessageCreate,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    owner_id = _user_identity(request, response)
    conversation = request.app.state.repository.get_conversation(conversation_id)
    if conversation is None or conversation["owner_id"] != owner_id:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    group_id = request_group_id(request, payload.group_id)
    message = request.app.state.repository.append_message(
        conversation_id, "user", payload.content
    )
    run = request.app.state.repository.create_query_run(
        conversation_id, payload.content, status="queued"
    )
    request.app.state.event_broker.create(run["id"])
    background_tasks.add_task(
        _execute_request, request, conversation_id, run["id"], payload.content, group_id
    )
    return {
        "request_id": run["id"],
        "conversation_id": conversation_id,
        "user_message_id": message["id"],
        "status": "queued",
        "events_url": f"/api/v1/user/requests/{run['id']}/events",
    }


@router.get("/requests/{request_id}/events")
async def request_events(
    request_id: str, request: Request, response: Response
) -> StreamingResponse:
    owner_id = _user_identity(request, response)
    run = _owned_run(request, owner_id, request_id)
    broker = request.app.state.event_broker
    if not broker.has(request_id) and run["status"] in {"completed", "failed", "interrupted"}:
        broker.create(request_id)
        terminal_event = "completed" if run["status"] == "completed" else "error"
        await broker.publish(
            request_id,
            terminal_event,
            {"request_id": request_id, "status": run["status"]},
        )

    async def stream():
        async for event, data in broker.stream(request_id):
            payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            yield f"event: {event}\ndata: {payload}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/requests/{request_id}")
def request_result(
    request_id: str, request: Request, response: Response
) -> dict[str, Any]:
    owner_id = _user_identity(request, response)
    run = _owned_run(request, owner_id, request_id)
    result: dict[str, Any] = {
        "request_id": request_id,
        "conversation_id": run["conversation_id"],
        "status": run["status"],
        "answer": run.get("answer"),
        "error": "问答处理失败，请稍后重试" if run["status"] == "failed" else None,
    }
    if run["status"] == "completed":
        assistant = next(
            (
                item
                for item in reversed(
                    request.app.state.repository.list_messages(run["conversation_id"])
                )
                if item["role"] == "assistant"
                and item["metadata"].get("request_id") == request_id
            ),
            None,
        )
        if assistant is not None:
            metadata = assistant["metadata"]
            result.update(
                {
                    "message_id": assistant["id"],
                    "trace_id": run.get("trace_id"),
                    "citations": metadata.get("citations", []),
                    "trust_profile": metadata.get("trust_profile"),
                    "degraded": metadata.get("degraded", False),
                    "degradation_reason": metadata.get("degradation_reason"),
                }
            )
        else:
            result["trace_id"] = run.get("trace_id")
    return result
