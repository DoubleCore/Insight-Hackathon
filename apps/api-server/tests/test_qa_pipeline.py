from __future__ import annotations

import json
from pathlib import Path

import pytest


def _write_evidence(path: Path, evidence_id: str = "E-1", grade: str = "A") -> None:
    path.write_text(
        json.dumps(
            {
                "evidence_id": evidence_id,
                "source_title": "官方产品资料",
                "source_url_or_file": "https://example.com/source",
                "evidence_excerpt": "NVIDIA 提供 GPU 加速芯片。",
                "source_grade": grade,
                "publish_date": "2026-03-01",
                "retrieved_at": "2026-07-10",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _candidate(*, evidence_ids: list[str] | None = None, claim_nature: str = "fact"):
    from app.schemas import RetrievalCandidate

    return RetrievalCandidate(
        id="edge-1",
        uuid="edge-1",
        title="生产",
        content="NVIDIA 生产 GPU 加速芯片。",
        score=0.95,
        algorithm="vector",
        algorithms=["vector", "bm25"],
        object_type="edge",
        selected=True,
        evidence_ids=evidence_ids if evidence_ids is not None else ["E-1"],
        source="NVIDIA",
        target="GPU 加速芯片",
        relation="生产",
        confidence="high",
        last_verified_at="2026-07-10",
        current_validity="current",
        claim_nature=claim_nature,
        verification_status="confirmed_public",
    )


class FakeSearch:
    def __init__(self, candidate):
        self.candidate = candidate
        self.queries: list[str] = []

    async def search(self, query: str):
        from app.schemas import RetrievalSlice
        from app.services.retrieval import DeepSearchResult

        self.queries.append(query)
        return DeepSearchResult(
            slices=[
                RetrievalSlice(
                    id="vector-slice",
                    name="vector",
                    algorithm="vector",
                    query=query,
                    candidates=[self.candidate.model_copy(update={"selected": False})],
                )
            ],
            candidates=[self.candidate],
            rerank_method="cross_encoder",
        )


class FakeChat:
    def __init__(self, *, fail_answer: bool = False):
        self.fail_answer = fail_answer
        self.rewrite_calls: list[tuple[str, list[dict[str, str]]]] = []
        self.answer_calls: list[tuple[str, str]] = []

    async def rewrite(self, question: str, history: list[dict[str, str]]):
        from app.services.qa_pipeline import LlmResult

        self.rewrite_calls.append((question, history))
        return LlmResult(text="NVIDIA 生产哪些 GPU 产品？", request_tokens=12, response_tokens=8)

    async def answer(self, question: str, context: str):
        from app.services.qa_pipeline import LlmResult

        self.answer_calls.append((question, context))
        if self.fail_answer:
            raise RuntimeError("provider unavailable")
        return LlmResult(
            text="NVIDIA 提供 GPU 加速芯片。[E-1]",
            request_tokens=30,
            response_tokens=15,
        )

    async def close(self) -> None:
        return None


@pytest.fixture
def repository(tmp_path: Path):
    from app.storage import Repository

    repo = Repository(tmp_path / "pipeline.db")
    repo.initialize()
    return repo


def _pipeline(tmp_path: Path, repository, search, chat):
    from app.services.evidence import EvidenceIndex
    from app.services.qa_pipeline import QuestionAnsweringPipeline
    from app.services.trust import EvidenceGate, TrustBuilder

    _write_evidence(tmp_path / "evidence_stage_1.jsonl")
    index = EvidenceIndex(tmp_path)
    return QuestionAnsweringPipeline(
        repository=repository,
        search_service=search,
        evidence_gate=EvidenceGate(index),
        trust_builder=TrustBuilder(index),
        chat_client=chat,
        model="test-deepseek",
    )


@pytest.mark.asyncio
async def test_pipeline_rewrites_follow_up_persists_trace_and_returns_public_result(
    tmp_path: Path, repository
) -> None:
    conversation = repository.create_conversation("owner")
    repository.append_message(conversation["id"], "user", "介绍 NVIDIA")
    repository.append_message(conversation["id"], "assistant", "NVIDIA 是算力芯片企业。")
    repository.append_message(conversation["id"], "user", "它有哪些产品？")
    run = repository.create_query_run(conversation["id"], "它有哪些产品？")
    search = FakeSearch(_candidate())
    chat = FakeChat()
    pipeline = _pipeline(tmp_path, repository, search, chat)
    events: list[tuple[str, dict[str, object]]] = []

    result = await pipeline.run(
        conversation_id=conversation["id"],
        query_run_id=run["id"],
        question="它有哪些产品？",
        emit=lambda event, data: events.append((event, data)),
    )

    assert search.queries == ["NVIDIA 生产哪些 GPU 产品？"]
    assert chat.rewrite_calls[0][1][-1]["role"] == "assistant"
    assert "E-1" in chat.answer_calls[0][1]
    assert result.answer == "NVIDIA 提供 GPU 加速芯片。[E-1]"
    assert [item.evidence_id for item in result.citations] == ["E-1"]
    assert result.trust_profile.evidence.level == "high"
    assert result.degraded is False
    assert any(event == "token" for event, _ in events)

    trace = repository.get_query_trace(run["id"])
    assert trace.status == "completed"
    assert {stage.name for stage in trace.stages} >= {
        "问题改写",
        "深度检索",
        "证据门控",
        "回答生成",
    }
    assert {slice_.algorithm for slice_ in trace.retrieval_slices} == {
        "vector",
        "cross_encoder",
    }
    final_candidate = next(
        slice_ for slice_ in trace.retrieval_slices if slice_.algorithm == "cross_encoder"
    ).candidates[0]
    assert final_candidate.selected is True
    assert final_candidate.evidence_ids == ["E-1"]
    assert final_candidate.source == "NVIDIA"
    assert final_candidate.target == "GPU 加速芯片"
    assert {call.purpose for call in trace.llm_calls} == {"rewrite", "answer"}
    assistant = repository.list_messages(conversation["id"])[-1]
    assert assistant["metadata"]["request_id"] == run["id"]
    assert "retrieval_slices" not in assistant["metadata"]


@pytest.mark.asyncio
async def test_pipeline_refuses_when_no_public_evidence_and_skips_answer_llm(
    tmp_path: Path, repository
) -> None:
    conversation = repository.create_conversation("owner")
    repository.append_message(conversation["id"], "user", "这是客户吗？")
    run = repository.create_query_run(conversation["id"], "这是客户吗？")
    candidate = _candidate(evidence_ids=[], claim_nature="no_public_evidence")
    chat = FakeChat()
    pipeline = _pipeline(tmp_path, repository, FakeSearch(candidate), chat)

    result = await pipeline.run(
        conversation_id=conversation["id"],
        query_run_id=run["id"],
        question="这是客户吗？",
    )

    assert "无法" in result.answer
    assert result.citations == []
    assert chat.answer_calls == []
    assert {call.purpose for call in repository.get_query_trace(run["id"]).llm_calls} == set()


@pytest.mark.asyncio
async def test_pipeline_uses_structured_fact_summary_when_answer_llm_fails(
    tmp_path: Path, repository
) -> None:
    conversation = repository.create_conversation("owner")
    repository.append_message(conversation["id"], "user", "NVIDIA 提供什么？")
    run = repository.create_query_run(conversation["id"], "NVIDIA 提供什么？")
    pipeline = _pipeline(
        tmp_path,
        repository,
        FakeSearch(_candidate()),
        FakeChat(fail_answer=True),
    )

    result = await pipeline.run(
        conversation_id=conversation["id"],
        query_run_id=run["id"],
        question="NVIDIA 提供什么？",
    )

    assert result.degraded is True
    assert "NVIDIA 生产 GPU 加速芯片" in result.answer
    assert "E-1" in result.answer
    answer_call = repository.get_query_trace(run["id"]).llm_calls[-1]
    assert answer_call.status == "failed"
    assert "provider unavailable" in answer_call.error
