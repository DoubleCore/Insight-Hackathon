from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field

from app.schemas import Citation, LlmCallTrace, QueryStage, RetrievalCandidate, RetrievalSlice, TrustProfile
from app.services.trust import EvidenceGate, TrustBuilder
from app.services.tracing import start_span
from app.storage import Repository


EmitCallback = Callable[[str, dict[str, Any]], Awaitable[None] | None]


class LlmResult(BaseModel):
    text: str
    request_tokens: int | None = None
    response_tokens: int | None = None


class QaPipelineResult(BaseModel):
    message_id: str
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    trust_profile: TrustProfile
    degraded: bool = False
    degradation_reason: str | None = None


class ChatClient(Protocol):
    async def rewrite(self, question: str, history: list[dict[str, str]]) -> LlmResult: ...

    async def answer(self, question: str, context: str) -> LlmResult: ...

    async def close(self) -> None: ...


class SearchService(Protocol):
    async def search(self, query: str) -> Any: ...


class QuestionAnsweringPipeline:
    def __init__(
        self,
        *,
        repository: Repository,
        search_service: SearchService,
        evidence_gate: EvidenceGate,
        trust_builder: TrustBuilder,
        chat_client: ChatClient,
        model: str,
        graphiti: Any | None = None,
    ) -> None:
        self.repository = repository
        self.search_service = search_service
        self.evidence_gate = evidence_gate
        self.trust_builder = trust_builder
        self.chat_client = chat_client
        self.model = model
        self.graphiti = graphiti

    async def run(
        self,
        *,
        conversation_id: str,
        query_run_id: str,
        question: str,
        emit: EmitCallback | None = None,
    ) -> QaPipelineResult:
        stages: list[QueryStage] = []
        self.repository.update_query_run(query_run_id, status="running", stages=[])

        history = self._history_before_current(conversation_id, question)
        rewritten_question = question
        degraded_reasons: list[str] = []
        if history:
            with start_span(
                "qa.rewrite",
                {
                    "query_run_id": query_run_id,
                    "history_turns": len(history),
                    "question_length": len(question),
                    "model": self.model,
                },
            ):
                rewritten_question, rewrite_stage, rewrite_degraded = await self._rewrite(
                    query_run_id, question, history, emit
                )
            stages.append(rewrite_stage)
            if rewrite_degraded:
                degraded_reasons.append(rewrite_degraded)
            self._save_stages(query_run_id, stages)

        retrieval_started = perf_counter()
        await _emit(emit, "stage", {"name": "深度检索", "status": "running"})
        with start_span(
            "qa.retrieval",
            {
                "query_run_id": query_run_id,
                "question_length": len(rewritten_question),
                "slice_limit": getattr(self.search_service, "slice_limit", None),
                "candidate_pool_limit": getattr(self.search_service, "candidate_pool_limit", None),
            },
        ) as retrieval_span:
            search_result = await self.search_service.search(rewritten_question)
            retrieval_span.set_attributes(
                {
                    "slice_count": len(search_result.slices),
                    "candidate_count": len(search_result.candidates),
                    "selected_count": len(search_result.selected_candidates),
                    "rerank_method": search_result.rerank_method,
                    "fallback_reason": search_result.fallback_reason,
                }
            )
        for slice_ in search_result.slices:
            self.repository.write_retrieval_slice(
                query_run_id, _trace_slice(slice_, slice_.algorithm)
            )
        final_slice = RetrievalSlice(
            id=f"final-{query_run_id}",
            name="Cross Encoder 重排结果",
            algorithm=search_result.rerank_method,
            query=rewritten_question,
            candidates=search_result.candidates,
            metadata={"fallback_reason": search_result.fallback_reason},
        )
        self.repository.write_retrieval_slice(
            query_run_id, _trace_slice(final_slice, search_result.rerank_method)
        )
        retrieval_stage = QueryStage(
            name="深度检索",
            status="completed",
            algorithm=search_result.rerank_method,
            detail={
                "query": rewritten_question,
                "slice_count": len(search_result.slices),
                "candidate_count": len(search_result.candidates),
                "selected_count": len(search_result.selected_candidates),
                "fallback_reason": search_result.fallback_reason,
            },
            duration_ms=(perf_counter() - retrieval_started) * 1000,
        )
        stages.append(retrieval_stage)
        self._save_stages(query_run_id, stages)
        await _emit(
            emit,
            "stage",
            {
                "name": "深度检索",
                "status": "completed",
                "selected_count": len(search_result.selected_candidates),
            },
        )

        with start_span(
            "qa.evidence_gate",
            {
                "query_run_id": query_run_id,
                "candidate_count": len(search_result.candidates),
            },
        ) as gate_span:
            gate = self.evidence_gate.evaluate(search_result.candidates)
            trust = self.trust_builder.build(search_result.candidates)
            gate_span.set_attributes(
                {
                    "supported": gate.supported,
                    "reason": gate.reason,
                    "citation_count": len(gate.citations),
                    "supporting_candidate_count": len(gate.supporting_candidate_ids),
                }
            )
        stages.append(
            QueryStage(
                name="证据门控",
                status="completed" if gate.supported else "refused",
                detail={
                    "supported": gate.supported,
                    "reason": gate.reason,
                    "citation_count": len(gate.citations),
                    "supporting_candidate_ids": gate.supporting_candidate_ids,
                },
            )
        )
        self._save_stages(query_run_id, stages)
        await _emit(
            emit,
            "stage",
            {"name": "证据门控", "status": "completed", "supported": gate.supported},
        )

        degraded = bool(degraded_reasons)
        if not gate.supported:
            answer = f"根据当前图谱，{gate.reason}"
            stages.append(QueryStage(name="回答生成", status="refused", detail={"reason": gate.reason}))
        else:
            supporting = [
                candidate
                for candidate in search_result.selected_candidates
                if candidate.id in gate.supporting_candidate_ids
            ]
            with start_span(
                "qa.answer_generation",
                {
                    "query_run_id": query_run_id,
                    "candidate_count": len(supporting),
                    "model": self.model,
                },
            ) as answer_span:
                try:
                    answer = await self._generate_answer(
                        query_run_id, rewritten_question, supporting, emit
                    )
                    answer_span.set_attribute("status", "completed")
                    stages.append(QueryStage(name="回答生成", status="completed", algorithm=self.model))
                except Exception as exc:
                    answer = _fact_summary(supporting)
                    degraded = True
                    reason = f"大模型回答失败，已使用图谱事实摘要：{type(exc).__name__}: {exc}"
                    degraded_reasons.append(reason)
                    answer_span.set_attribute("status", "degraded")
                    answer_span.set_attribute("fallback_reason", reason)
                    stages.append(
                        QueryStage(
                            name="回答生成",
                            status="degraded",
                            algorithm=self.model,
                            detail={"reason": reason},
                        )
                    )
                    for chunk in _chunks(answer):
                        await _emit(emit, "token", {"text": chunk})

        metadata = {
            "request_id": query_run_id,
            "citations": [citation.model_dump(mode="json") for citation in gate.citations],
            "trust_profile": trust.model_dump(mode="json"),
            "degraded": degraded,
            "degradation_reason": "；".join(degraded_reasons) or None,
        }
        message = self.repository.append_message(
            conversation_id, "assistant", answer, metadata=metadata
        )
        self.repository.update_query_run(
            query_run_id,
            status="completed",
            answer=answer,
            stages=[stage.model_dump(mode="json") for stage in stages],
        )
        return QaPipelineResult(
            message_id=message["id"],
            answer=answer,
            citations=gate.citations,
            trust_profile=trust,
            degraded=degraded,
            degradation_reason=metadata["degradation_reason"],
        )

    def _history_before_current(
        self, conversation_id: str, question: str
    ) -> list[dict[str, str]]:
        messages = self.repository.list_messages(conversation_id)
        if messages and messages[-1]["role"] == "user" and messages[-1]["content"] == question:
            messages = messages[:-1]
        return [
            {"role": item["role"], "content": item["content"]}
            for item in messages[-8:]
            if item["role"] in {"user", "assistant"}
        ]

    async def _rewrite(
        self,
        query_run_id: str,
        question: str,
        history: list[dict[str, str]],
        emit: EmitCallback | None,
    ) -> tuple[str, QueryStage, str | None]:
        started_at = datetime.now(UTC)
        started = perf_counter()
        call_id = str(uuid4())
        await _emit(emit, "stage", {"name": "问题改写", "status": "running"})
        try:
            result = await self.chat_client.rewrite(question, history)
            completed_at = datetime.now(UTC)
            self.repository.write_llm_call(
                query_run_id,
                LlmCallTrace(
                    id=call_id,
                    query_run_id=query_run_id,
                    model=self.model,
                    purpose="rewrite",
                    status="completed",
                    request_tokens=result.request_tokens,
                    response_tokens=result.response_tokens,
                    latency_ms=(perf_counter() - started) * 1000,
                    request={"question": question, "history": history},
                    response={"rewritten_question": result.text},
                    started_at=started_at,
                    completed_at=completed_at,
                ),
            )
            await _emit(emit, "stage", {"name": "问题改写", "status": "completed"})
            return result.text.strip() or question, QueryStage(
                name="问题改写",
                status="completed",
                algorithm=self.model,
                detail={"original": question, "rewritten": result.text.strip() or question},
                duration_ms=(perf_counter() - started) * 1000,
            ), None
        except Exception as exc:
            reason = f"问题改写失败，沿用原问题：{type(exc).__name__}: {exc}"
            self.repository.write_llm_call(
                query_run_id,
                LlmCallTrace(
                    id=call_id,
                    query_run_id=query_run_id,
                    model=self.model,
                    purpose="rewrite",
                    status="failed",
                    latency_ms=(perf_counter() - started) * 1000,
                    request={"question": question, "history": history},
                    error=str(exc),
                    started_at=started_at,
                    completed_at=datetime.now(UTC),
                ),
            )
            await _emit(emit, "stage", {"name": "问题改写", "status": "degraded"})
            return question, QueryStage(
                name="问题改写",
                status="degraded",
                algorithm=self.model,
                detail={"reason": reason},
                duration_ms=(perf_counter() - started) * 1000,
            ), reason

    async def _generate_answer(
        self,
        query_run_id: str,
        question: str,
        candidates: list[RetrievalCandidate],
        emit: EmitCallback | None,
    ) -> str:
        context = _answer_context(candidates)
        started_at = datetime.now(UTC)
        started = perf_counter()
        call_id = str(uuid4())
        await _emit(emit, "stage", {"name": "回答生成", "status": "running"})
        try:
            result = await self.chat_client.answer(question, context)
        except Exception as exc:
            self.repository.write_llm_call(
                query_run_id,
                LlmCallTrace(
                    id=call_id,
                    query_run_id=query_run_id,
                    model=self.model,
                    purpose="answer",
                    status="failed",
                    latency_ms=(perf_counter() - started) * 1000,
                    request={"question": question, "context": context},
                    error=str(exc),
                    started_at=started_at,
                    completed_at=datetime.now(UTC),
                ),
            )
            raise
        self.repository.write_llm_call(
            query_run_id,
            LlmCallTrace(
                id=call_id,
                query_run_id=query_run_id,
                model=self.model,
                purpose="answer",
                status="completed",
                request_tokens=result.request_tokens,
                response_tokens=result.response_tokens,
                latency_ms=(perf_counter() - started) * 1000,
                request={"question": question, "context": context},
                response={"answer": result.text},
                started_at=started_at,
                completed_at=datetime.now(UTC),
            ),
        )
        for chunk in _chunks(result.text):
            await _emit(emit, "token", {"text": chunk})
        return result.text.strip()

    def _save_stages(self, query_run_id: str, stages: list[QueryStage]) -> None:
        self.repository.update_query_run(
            query_run_id,
            stages=[stage.model_dump(mode="json") for stage in stages],
        )

    async def close(self) -> None:
        await self.chat_client.close()
        close_search = getattr(self.search_service, "close", None)
        if close_search is not None:
            result = close_search()
            if inspect.isawaitable(result):
                await result
        if self.graphiti is not None:
            await self.graphiti.close()


async def _emit(
    callback: EmitCallback | None, event: str, data: dict[str, Any]
) -> None:
    if callback is None:
        return
    result = callback(event, data)
    if inspect.isawaitable(result):
        await result


def _trace_slice(slice_: RetrievalSlice, algorithm: str) -> RetrievalSlice:
    candidates: list[RetrievalCandidate] = []
    for candidate in slice_.candidates:
        payload = candidate.model_dump(mode="json")
        metadata = {**candidate.metadata, **payload, "original_candidate_id": candidate.id}
        candidates.append(
            candidate.model_copy(
                update={
                    "id": f"{slice_.id}:{candidate.id}",
                    "slice_id": slice_.id,
                    "algorithm": algorithm,
                    "metadata": metadata,
                }
            )
        )
    return slice_.model_copy(update={"candidates": candidates})


def _answer_context(candidates: list[RetrievalCandidate]) -> str:
    blocks: list[str] = []
    for index, candidate in enumerate(candidates, start=1):
        fields = [f"[{index}] 事实：{candidate.content}"]
        if candidate.relation:
            fields.append(f"关系：{candidate.relation}")
        if candidate.evidence_ids:
            fields.append(f"证据ID：{', '.join(candidate.evidence_ids)}")
        if candidate.verification_status:
            fields.append(f"核验状态：{candidate.verification_status}")
        if candidate.last_verified_at or candidate.data_as_of:
            fields.append(f"最近核验：{candidate.last_verified_at or candidate.data_as_of}")
        if candidate.requires_internal_validation:
            fields.append("需要内部验证：是")
        blocks.append("\n".join(fields))
    return "\n\n".join(blocks)


def _fact_summary(candidates: list[RetrievalCandidate]) -> str:
    if not candidates:
        return "当前图谱没有可用于回答的公开证据事实。"
    lines = []
    for candidate in candidates[:8]:
        evidence = f"（证据：{', '.join(candidate.evidence_ids)}）" if candidate.evidence_ids else ""
        lines.append(f"- {candidate.content}{evidence}")
    return "大模型暂时不可用，以下为图谱直接返回的事实：\n" + "\n".join(lines)


def _chunks(text: str, size: int = 16) -> list[str]:
    return [text[index : index + size] for index in range(0, len(text), size)]
