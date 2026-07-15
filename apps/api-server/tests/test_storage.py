from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest


@pytest.fixture
def repository(tmp_path: Path):
    from app.storage import Repository

    repo = Repository(tmp_path / "observability.db")
    repo.initialize()
    return repo


def test_repository_rejects_process_local_memory_database() -> None:
    from app.storage import Repository

    with pytest.raises(ValueError, match="不支持 :memory:"):
        Repository(":memory:")


def test_initialize_creates_required_tables_and_enables_wal(tmp_path: Path) -> None:
    from app.storage import Repository

    database_path = tmp_path / "nested" / "observability.db"
    Repository(database_path).initialize()

    with sqlite3.connect(database_path) as connection:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert journal_mode == "wal"
    assert {
        "conversations",
        "messages",
        "query_runs",
        "retrieval_slices",
        "retrieval_candidates",
        "llm_calls",
        "background_jobs",
    }.issubset(tables)


def test_connection_context_sets_pragmas_rolls_back_and_closes(repository) -> None:
    connection = None
    with pytest.raises(RuntimeError, match="force rollback"):
        with repository.connection() as connection:
            assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            assert connection.execute("PRAGMA synchronous").fetchone()[0] == 1
            assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 10_000
            connection.execute(
                "INSERT INTO conversations (id, owner_id, created_at, updated_at) "
                "VALUES ('rollback-id', 'owner', 'now', 'now')"
            )
            raise RuntimeError("force rollback")

    assert repository.get_conversation("rollback-id") is None
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connection.execute("SELECT 1")


def test_repository_persists_conversations_messages_and_query_runs(repository) -> None:
    conversation = repository.create_conversation("owner-1", title="验收会话")
    repository.create_conversation("owner-2", title="其他用户")

    assert [item["id"] for item in repository.list_conversations("owner-1")] == [
        conversation["id"]
    ]
    assert repository.get_conversation(conversation["id"])["owner_id"] == "owner-1"

    message = repository.append_message(
        conversation["id"], "user", "查询问题", metadata={"source": "test"}
    )
    assert repository.list_messages(conversation["id"])[0] == message

    query_run = repository.create_query_run(conversation["id"], "查询问题")
    updated = repository.update_query_run(
        query_run["id"],
        status="completed",
        answer="查询回答",
        trace_id="0123456789abcdef0123456789abcdef",
    )
    assert updated["status"] == "completed"
    assert updated["trace_id"] == "0123456789abcdef0123456789abcdef"
    assert repository.list_query_runs()[0]["answer"] == "查询回答"
    assert repository.list_query_runs()[0]["trace_id"] == "0123456789abcdef0123456789abcdef"


def test_repository_marks_unfinished_query_runs_interrupted(repository) -> None:
    conversation = repository.create_conversation("owner")
    queued = repository.create_query_run(conversation["id"], "排队问题")
    running = repository.create_query_run(
        conversation["id"], "执行问题", status="running"
    )
    completed = repository.create_query_run(
        conversation["id"], "完成问题", status="completed"
    )

    recovered = repository.recover_interrupted_query_runs()

    assert recovered == 2
    assert repository.get_query_run(queued["id"])["status"] == "interrupted"
    assert repository.get_query_run(running["id"])["status"] == "interrupted"
    assert "服务重启" in repository.get_query_run(running["id"])["error"]
    assert repository.get_query_run(completed["id"])["status"] == "completed"


def test_repository_persists_retrieval_and_llm_observability(repository) -> None:
    from app.schemas import LlmCallTrace, RetrievalCandidate, RetrievalSlice

    conversation = repository.create_conversation("owner-1")
    query_run = repository.create_query_run(conversation["id"], "芯片问题")
    retrieval_slice = repository.write_retrieval_slice(
        query_run["id"],
        RetrievalSlice(
            id="slice-1",
            name="图谱召回",
            algorithm="graph_traversal",
            query="芯片问题",
            metadata={"depth": 2},
        ),
    )
    candidate = repository.write_retrieval_candidate(
        retrieval_slice["id"],
        RetrievalCandidate(
            id="candidate-1",
            title="企业证据",
            content="证据内容",
            score=0.88,
            algorithm="graph_traversal",
            evidence_level="A",
            confidence=0.9,
            valid_from="2025-01-01",
            verification_status="verified",
            metadata={"node_id": "n1"},
        ),
    )
    llm_call = repository.write_llm_call(
        query_run["id"],
        LlmCallTrace(
            id="call-1",
            query_run_id=query_run["id"],
            model="test-model",
            purpose="answer",
            status="completed",
            request_tokens=10,
            response_tokens=20,
            request={"prompt": "测试"},
            response={"answer": "结果"},
        ),
    )

    slices = repository.list_retrieval_slices(query_run["id"])
    candidates = repository.list_retrieval_candidates(retrieval_slice["id"])
    calls = repository.list_llm_calls(query_run["id"])
    assert slices[0]["metadata"] == {"depth": 2}
    assert candidates[0] == candidate
    assert candidates[0]["evidence_level"] == "A"
    assert calls[0] == llm_call
    assert calls[0]["request"] == {"prompt": "测试"}


def test_write_retrieval_slice_upserts_and_synchronizes_candidates(repository) -> None:
    from app.schemas import RetrievalCandidate, RetrievalSlice

    conversation = repository.create_conversation("owner-1")
    query_run = repository.create_query_run(conversation["id"], "召回问题")
    first = RetrievalSlice(
        id="slice-upsert",
        name="首次召回",
        algorithm="hybrid",
        query="召回问题",
        candidates=[
            RetrievalCandidate(
                id="candidate-a",
                title="证据 A",
                content="旧内容",
                score=0.8,
                algorithm="hybrid",
            ),
            RetrievalCandidate(
                id="candidate-b",
                title="证据 B",
                content="将被移除",
                score=0.7,
                algorithm="hybrid",
            ),
        ],
    )
    repository.write_retrieval_slice(query_run["id"], first)

    second = first.model_copy(
        update={
            "name": "更新召回",
            "candidates": [
                first.candidates[0].model_copy(update={"content": "新内容", "score": 0.95}),
                RetrievalCandidate(
                    id="candidate-c",
                    title="证据 C",
                    content="新增内容",
                    score=0.85,
                    algorithm="hybrid",
                ),
            ],
        }
    )
    stored_slice = repository.write_retrieval_slice(query_run["id"], second)
    candidates = repository.list_retrieval_candidates(first.id)

    assert stored_slice["name"] == "更新召回"
    assert {item["id"] for item in candidates} == {"candidate-a", "candidate-c"}
    assert next(item for item in candidates if item["id"] == "candidate-a")["content"] == "新内容"


def test_get_query_trace_aggregates_every_persisted_stage(repository) -> None:
    from app.schemas import LlmCallTrace, QueryTrace, RetrievalCandidate, RetrievalSlice

    conversation = repository.create_conversation("owner-1")
    query_run = repository.create_query_run(conversation["id"], "完整追踪")
    repository.update_query_run(
        query_run["id"],
        status="completed",
        answer="回答",
        stages=[{"name": "retrieval", "status": "completed", "algorithm": "graph"}],
    )
    retrieval_slice = repository.write_retrieval_slice(
        query_run["id"],
        RetrievalSlice(
            id="trace-slice",
            name="图谱召回",
            algorithm="graph",
            query="完整追踪",
        ),
    )
    repository.write_retrieval_candidate(
        retrieval_slice["id"],
        RetrievalCandidate(
            id="trace-candidate",
            title="图谱证据",
            content="证据",
            score=0.9,
            algorithm="graph",
        ),
    )
    repository.write_llm_call(
        query_run["id"],
        LlmCallTrace(
            id="trace-call",
            query_run_id=query_run["id"],
            model="test-model",
            purpose="answer",
            status="completed",
        ),
    )

    trace = repository.get_query_trace(query_run["id"])

    assert isinstance(trace, QueryTrace)
    assert trace.stages[0].algorithm == "graph"
    assert trace.retrieval_slices[0].candidates[0].id == "trace-candidate"
    assert trace.llm_calls[0].id == "trace-call"
    assert repository.get_query_trace("missing-run") is None


def test_repository_recovers_unfinished_background_jobs(repository) -> None:
    now = datetime.now(UTC)
    queued = repository.create_background_job("refresh", {"scope": "queued"})
    running = repository.create_background_job(
        "refresh", {"scope": "running"}, status="running"
    )
    active = repository.create_background_job(
        "refresh",
        {"scope": "active"},
        status="running",
        worker_id="worker-active",
        heartbeat_at=now.isoformat(),
        lease_expires_at=(now + timedelta(minutes=5)).isoformat(),
    )
    expired = repository.create_background_job(
        "refresh",
        {"scope": "expired"},
        status="running",
        worker_id="worker-expired",
        heartbeat_at=(now - timedelta(minutes=10)).isoformat(),
        lease_expires_at=(now - timedelta(minutes=5)).isoformat(),
    )
    completed = repository.create_background_job(
        "refresh", {"scope": "completed"}, status="completed"
    )

    assert repository.recover_interrupted_jobs(now=now) == 3
    assert repository.get_background_job(queued["id"])["status"] == "interrupted"
    assert repository.get_background_job(running["id"])["status"] == "interrupted"
    assert repository.get_background_job(active["id"])["status"] == "running"
    assert repository.get_background_job(expired["id"])["status"] == "interrupted"
    assert repository.get_background_job(completed["id"])["status"] == "completed"

    updated = repository.update_background_job(
        queued["id"], status="interrupted", error="重试失败", result={"retry": 1}
    )
    assert updated is None
    assert repository.get_background_job(queued["id"])["result"] is None


def test_background_job_heartbeat_rejects_queued_job(repository) -> None:
    now = datetime.now(UTC)
    job = repository.create_background_job("refresh", {})

    heartbeat = repository.heartbeat_background_job(
        job["id"], "worker-1", lease_seconds=120, now=now
    )

    assert heartbeat is None
    stored = repository.get_background_job(job["id"])
    assert stored["status"] == "queued"
    assert stored["worker_id"] is None
    assert stored["heartbeat_at"] is None
    assert stored["lease_expires_at"] is None


def test_background_job_heartbeat_renews_active_owner_lease(repository) -> None:
    now = datetime.now(UTC)
    job = repository.create_background_job(
        "refresh",
        {},
        status="running",
        worker_id="worker-1",
        heartbeat_at=now.isoformat(),
        lease_expires_at=(now + timedelta(minutes=5)).isoformat(),
    )
    renewed_at = now + timedelta(seconds=30)

    heartbeat = repository.heartbeat_background_job(
        job["id"], "worker-1", lease_seconds=120, now=renewed_at
    )

    assert heartbeat["status"] == "running"
    assert heartbeat["worker_id"] == "worker-1"
    assert heartbeat["heartbeat_at"] == renewed_at.isoformat()
    assert heartbeat["lease_expires_at"] == (
        renewed_at + timedelta(seconds=120)
    ).isoformat()


def test_write_retrieval_slice_rejects_moving_existing_slice_to_another_run(
    repository,
) -> None:
    from app.schemas import RetrievalCandidate, RetrievalSlice

    conversation = repository.create_conversation("owner-1")
    original_run = repository.create_query_run(conversation["id"], "original query")
    other_run = repository.create_query_run(conversation["id"], "other query")
    original_slice = RetrievalSlice(
        id="owned-slice",
        name="original slice",
        algorithm="hybrid",
        query="original query",
        candidates=[
            RetrievalCandidate(
                id="owned-candidate",
                title="original candidate",
                content="original content",
                score=0.8,
                algorithm="hybrid",
            )
        ],
    )
    repository.write_retrieval_slice(original_run["id"], original_slice)

    moved_slice = original_slice.model_copy(
        update={
            "name": "moved slice",
            "candidates": [
                original_slice.candidates[0].model_copy(
                    update={"content": "moved content"}
                )
            ],
        }
    )
    with pytest.raises(ValueError, match="owned-slice"):
        repository.write_retrieval_slice(other_run["id"], moved_slice)

    assert [item["id"] for item in repository.list_retrieval_slices(original_run["id"])] == [
        "owned-slice"
    ]
    assert repository.list_retrieval_slices(other_run["id"]) == []
    assert repository.get_retrieval_slice("owned-slice")["name"] == "original slice"
    assert repository.get_retrieval_candidate("owned-candidate")["content"] == "original content"


def test_write_retrieval_candidate_rejects_moving_existing_candidate_to_another_slice(
    repository,
) -> None:
    from app.schemas import RetrievalCandidate, RetrievalSlice

    conversation = repository.create_conversation("owner-1")
    query_run = repository.create_query_run(conversation["id"], "query")
    for slice_id in ("original-slice", "other-slice"):
        repository.write_retrieval_slice(
            query_run["id"],
            RetrievalSlice(
                id=slice_id,
                name=slice_id,
                algorithm="hybrid",
                query="query",
            ),
        )
    original_candidate = RetrievalCandidate(
        id="owned-candidate",
        title="original candidate",
        content="original content",
        score=0.8,
        algorithm="hybrid",
    )
    repository.write_retrieval_candidate("original-slice", original_candidate)

    with pytest.raises(ValueError, match="owned-candidate"):
        repository.write_retrieval_candidate(
            "other-slice",
            original_candidate.model_copy(update={"content": "moved content"}),
        )

    assert repository.get_retrieval_candidate("owned-candidate")["slice_id"] == "original-slice"
    assert repository.get_retrieval_candidate("owned-candidate")["content"] == "original content"
    assert [
        item["id"] for item in repository.list_retrieval_candidates("original-slice")
    ] == ["owned-candidate"]
    assert repository.list_retrieval_candidates("other-slice") == []


def test_write_retrieval_candidate_updates_within_same_slice(repository) -> None:
    from app.schemas import RetrievalCandidate, RetrievalSlice

    conversation = repository.create_conversation("owner-1")
    query_run = repository.create_query_run(conversation["id"], "query")
    repository.write_retrieval_slice(
        query_run["id"],
        RetrievalSlice(
            id="same-slice",
            name="same slice",
            algorithm="hybrid",
            query="query",
        ),
    )
    candidate = RetrievalCandidate(
        id="same-candidate",
        title="candidate",
        content="old content",
        score=0.5,
        algorithm="hybrid",
    )
    repository.write_retrieval_candidate("same-slice", candidate)

    updated = repository.write_retrieval_candidate(
        "same-slice",
        candidate.model_copy(update={"content": "new content", "score": 0.9}),
    )

    assert updated["slice_id"] == "same-slice"
    assert updated["content"] == "new content"
    assert updated["score"] == 0.9


def test_background_job_heartbeat_cannot_steal_another_workers_active_lease(
    repository,
) -> None:
    now = datetime.now(UTC)
    job = repository.create_background_job(
        "refresh",
        {},
        status="running",
        worker_id="worker-a",
        heartbeat_at=now.isoformat(),
        lease_expires_at=(now + timedelta(minutes=5)).isoformat(),
    )

    heartbeat = repository.heartbeat_background_job(
        job["id"], "worker-b", lease_seconds=120, now=now + timedelta(seconds=30)
    )

    assert heartbeat is None
    stored = repository.get_background_job(job["id"])
    assert stored["status"] == "running"
    assert stored["worker_id"] == "worker-a"
    assert stored["heartbeat_at"] == now.isoformat()
    assert stored["lease_expires_at"] == (now + timedelta(minutes=5)).isoformat()


@pytest.mark.parametrize("terminal_status", ["completed", "failed", "interrupted"])
def test_background_job_heartbeat_cannot_revive_terminal_job(
    repository, terminal_status: str
) -> None:
    now = datetime.now(UTC)
    job = repository.create_background_job("refresh", {}, status=terminal_status)

    heartbeat = repository.heartbeat_background_job(
        job["id"], "worker-a", lease_seconds=120, now=now
    )

    assert heartbeat is None
    stored = repository.get_background_job(job["id"])
    assert stored["status"] == terminal_status
    assert stored["worker_id"] is None
    assert stored["heartbeat_at"] is None
    assert stored["lease_expires_at"] is None


def test_claim_background_job_can_take_over_expired_running_lease(repository) -> None:
    now = datetime.now(UTC)
    job = repository.create_background_job(
        "refresh",
        {},
        status="running",
        worker_id="worker-a",
        heartbeat_at=(now - timedelta(minutes=10)).isoformat(),
        lease_expires_at=(now - timedelta(minutes=5)).isoformat(),
    )

    claimed = repository.claim_background_job(
        job["id"], "worker-b", lease_seconds=120, now=now
    )

    assert claimed["status"] == "running"
    assert claimed["worker_id"] == "worker-b"
    assert claimed["heartbeat_at"] == now.isoformat()
    assert claimed["lease_expires_at"] == (now + timedelta(seconds=120)).isoformat()


def test_claim_background_job_claims_queued_job(repository) -> None:
    now = datetime.now(UTC)
    job = repository.create_background_job("refresh", {})

    claimed = repository.claim_background_job(
        job["id"], "worker-a", lease_seconds=120, now=now
    )

    assert claimed["status"] == "running"
    assert claimed["worker_id"] == "worker-a"
    assert claimed["heartbeat_at"] == now.isoformat()
    assert claimed["lease_expires_at"] == (now + timedelta(seconds=120)).isoformat()


def test_claim_background_job_cannot_take_over_active_running_lease(repository) -> None:
    now = datetime.now(UTC)
    job = repository.create_background_job(
        "refresh",
        {},
        status="running",
        worker_id="worker-a",
        heartbeat_at=now.isoformat(),
        lease_expires_at=(now + timedelta(minutes=5)).isoformat(),
    )

    claimed = repository.claim_background_job(
        job["id"], "worker-b", lease_seconds=120, now=now + timedelta(seconds=30)
    )

    assert claimed is None
    stored = repository.get_background_job(job["id"])
    assert stored["worker_id"] == "worker-a"
    assert stored["heartbeat_at"] == now.isoformat()
    assert stored["lease_expires_at"] == (now + timedelta(minutes=5)).isoformat()


def test_background_job_heartbeat_rejects_expired_owner_lease(repository) -> None:
    now = datetime.now(UTC)
    expired_at = now - timedelta(seconds=1)
    job = repository.create_background_job(
        "refresh",
        {},
        status="running",
        worker_id="worker-a",
        heartbeat_at=(now - timedelta(minutes=5)).isoformat(),
        lease_expires_at=expired_at.isoformat(),
    )

    heartbeat = repository.heartbeat_background_job(
        job["id"], "worker-a", lease_seconds=120, now=now
    )

    assert heartbeat is None
    stored = repository.get_background_job(job["id"])
    assert stored["worker_id"] == "worker-a"
    assert stored["lease_expires_at"] == expired_at.isoformat()


def test_background_job_heartbeat_rejects_running_job_without_owner(repository) -> None:
    now = datetime.now(UTC)
    job = repository.create_background_job(
        "refresh",
        {},
        status="running",
        heartbeat_at=now.isoformat(),
        lease_expires_at=(now + timedelta(minutes=5)).isoformat(),
    )

    heartbeat = repository.heartbeat_background_job(
        job["id"], "worker-a", lease_seconds=120, now=now + timedelta(seconds=30)
    )

    assert heartbeat is None
    stored = repository.get_background_job(job["id"])
    assert stored["worker_id"] is None
    assert stored["heartbeat_at"] == now.isoformat()


@pytest.mark.parametrize("terminal_status", ["completed", "failed", "interrupted"])
def test_claim_background_job_rejects_terminal_job(
    repository, terminal_status: str
) -> None:
    now = datetime.now(UTC)
    job = repository.create_background_job("refresh", {}, status=terminal_status)

    claimed = repository.claim_background_job(
        job["id"], "worker-a", lease_seconds=120, now=now
    )

    assert claimed is None
    assert repository.get_background_job(job["id"])["status"] == terminal_status


def test_claim_background_job_rejects_running_job_without_expired_lease(
    repository,
) -> None:
    now = datetime.now(UTC)
    job = repository.create_background_job(
        "refresh", {}, status="running", worker_id="worker-a"
    )

    claimed = repository.claim_background_job(
        job["id"], "worker-b", lease_seconds=120, now=now
    )

    assert claimed is None
    assert repository.get_background_job(job["id"])["worker_id"] == "worker-a"


def test_update_background_job_cannot_change_queued_job_to_running(repository) -> None:
    job = repository.create_background_job("refresh", {})

    updated = repository.update_background_job(job["id"], status="running")

    assert updated is None
    stored = repository.get_background_job(job["id"])
    assert stored["status"] == "queued"
    assert stored["started_at"] is None


@pytest.mark.parametrize("terminal_status", ["completed", "failed", "interrupted"])
def test_update_background_job_terminal_status_is_immutable(
    repository, terminal_status: str
) -> None:
    different_terminal = {
        "completed": "failed",
        "failed": "interrupted",
        "interrupted": "completed",
    }[terminal_status]
    job = repository.create_background_job("refresh", {}, status=terminal_status)

    for requested_status in ("queued", "running", different_terminal):
        updated = repository.update_background_job(
            job["id"], status=requested_status
        )
        assert updated is None
        assert repository.get_background_job(job["id"])["status"] == terminal_status

    same_status = repository.update_background_job(
        job["id"], status=terminal_status, error="same terminal update"
    )
    assert same_status is None
    stored = repository.get_background_job(job["id"])
    assert stored["status"] == terminal_status
    assert stored["error"] is None


@pytest.mark.parametrize("terminal_status", ["completed", "failed", "interrupted"])
def test_update_running_background_job_terminal_transition_requires_owner(
    repository, terminal_status: str
) -> None:
    now = datetime.now(UTC)
    job = repository.create_background_job(
        "refresh",
        {},
        status="running",
        worker_id="worker-a",
        heartbeat_at=now.isoformat(),
        lease_expires_at=(now + timedelta(minutes=5)).isoformat(),
    )

    assert repository.update_background_job(job["id"], status=terminal_status) is None
    assert (
        repository.update_background_job(
            job["id"], status=terminal_status, worker_id="worker-b"
        )
        is None
    )
    assert repository.get_background_job(job["id"])["status"] == "running"

    updated = repository.update_background_job(
        job["id"], status=terminal_status, worker_id="worker-a"
    )
    assert updated["status"] == terminal_status
    assert updated["worker_id"] == "worker-a"


def test_write_llm_call_rejects_moving_existing_call_to_another_run(
    repository,
) -> None:
    from app.schemas import LlmCallTrace

    conversation = repository.create_conversation("owner-1")
    original_run = repository.create_query_run(conversation["id"], "original query")
    other_run = repository.create_query_run(conversation["id"], "other query")
    original_call = LlmCallTrace(
        id="owned-call",
        query_run_id=original_run["id"],
        model="original-model",
        purpose="answer",
        status="completed",
        response={"answer": "original response"},
    )
    repository.write_llm_call(original_run["id"], original_call)

    moved_call = original_call.model_copy(
        update={
            "query_run_id": other_run["id"],
            "model": "moved-model",
            "response": {"answer": "moved response"},
        }
    )
    with pytest.raises(ValueError, match="owned-call"):
        repository.write_llm_call(other_run["id"], moved_call)

    stored = repository.get_llm_call("owned-call")
    assert stored["query_run_id"] == original_run["id"]
    assert stored["model"] == "original-model"
    assert stored["response"] == {"answer": "original response"}
    assert [item["id"] for item in repository.list_llm_calls(original_run["id"])] == [
        "owned-call"
    ]
    assert repository.list_llm_calls(other_run["id"]) == []


def test_write_llm_call_updates_existing_call_within_same_run(repository) -> None:
    from app.schemas import LlmCallTrace

    conversation = repository.create_conversation("owner-1")
    query_run = repository.create_query_run(conversation["id"], "query")
    call = LlmCallTrace(
        id="same-call",
        query_run_id=query_run["id"],
        model="test-model",
        purpose="answer",
        status="running",
        response={"answer": "old response"},
    )
    first = repository.write_llm_call(query_run["id"], call)

    updated = repository.write_llm_call(
        query_run["id"],
        call.model_copy(
            update={
                "status": "completed",
                "response_tokens": 20,
                "response": {"answer": "new response"},
            }
        ),
    )

    assert updated["query_run_id"] == query_run["id"]
    assert updated["status"] == "completed"
    assert updated["response_tokens"] == 20
    assert updated["response"] == {"answer": "new response"}
    assert updated["created_at"] == first["created_at"]


def test_expired_background_job_owner_cannot_complete_job(repository) -> None:
    now = datetime.now(UTC)
    job = repository.create_background_job(
        "refresh",
        {},
        status="running",
        worker_id="worker-a",
        heartbeat_at=(now - timedelta(minutes=5)).isoformat(),
        lease_expires_at=(now - timedelta(seconds=1)).isoformat(),
    )

    updated = repository.update_background_job(
        job["id"],
        status="completed",
        result={"worker": "a"},
        worker_id="worker-a",
        now=now,
    )

    assert updated is None
    stored = repository.get_background_job(job["id"])
    assert stored["status"] == "running"
    assert stored["result"] is None
    assert stored["completed_at"] is None


def test_old_worker_cannot_overwrite_result_after_new_worker_completes(repository) -> None:
    now = datetime.now(UTC)
    job = repository.create_background_job(
        "refresh",
        {},
        status="running",
        worker_id="worker-a",
        heartbeat_at=(now - timedelta(minutes=5)).isoformat(),
        lease_expires_at=(now - timedelta(seconds=1)).isoformat(),
    )
    claimed = repository.claim_background_job(
        job["id"], "worker-b", lease_seconds=120, now=now
    )
    assert claimed["worker_id"] == "worker-b"
    completed = repository.update_background_job(
        job["id"],
        status="completed",
        result={"worker": "b"},
        worker_id="worker-b",
        now=now + timedelta(seconds=10),
    )
    assert completed["status"] == "completed"

    overwritten = repository.update_background_job(
        job["id"],
        status="failed",
        result={"worker": "a"},
        error="stale worker",
        worker_id="worker-a",
        now=now + timedelta(seconds=20),
    )

    assert overwritten is None
    stored = repository.get_background_job(job["id"])
    assert stored["status"] == "completed"
    assert stored["result"] == {"worker": "b"}
    assert stored["error"] is None


def test_terminal_background_job_result_cannot_be_modified(repository) -> None:
    now = datetime.now(UTC)
    job = repository.create_background_job(
        "refresh",
        {},
        status="running",
        worker_id="worker-a",
        heartbeat_at=now.isoformat(),
        lease_expires_at=(now + timedelta(minutes=5)).isoformat(),
    )
    completed = repository.update_background_job(
        job["id"],
        status="completed",
        result={"version": 1},
        worker_id="worker-a",
        now=now + timedelta(seconds=10),
    )
    assert completed["result"] == {"version": 1}

    repeated = repository.update_background_job(
        job["id"],
        status="completed",
        result={"version": 2},
        error="replacement",
        worker_id="worker-a",
        now=now + timedelta(seconds=20),
    )

    assert repeated is None
    stored = repository.get_background_job(job["id"])
    assert stored["status"] == "completed"
    assert stored["result"] == {"version": 1}
    assert stored["error"] is None


def test_running_background_job_field_update_requires_active_owner(repository) -> None:
    now = datetime.now(UTC)
    job = repository.create_background_job(
        "refresh",
        {},
        status="running",
        worker_id="worker-a",
        heartbeat_at=now.isoformat(),
        lease_expires_at=(now + timedelta(minutes=5)).isoformat(),
    )
    update_time = now + timedelta(seconds=30)

    assert (
        repository.update_background_job(
            job["id"], result={"step": 1}, now=update_time
        )
        is None
    )
    assert (
        repository.update_background_job(
            job["id"], result={"step": 1}, worker_id="worker-b", now=update_time
        )
        is None
    )
    updated = repository.update_background_job(
        job["id"], result={"step": 1}, worker_id="worker-a", now=update_time
    )

    assert updated["status"] == "running"
    assert updated["result"] == {"step": 1}


@pytest.mark.parametrize("field", ["result", "error"])
def test_queued_background_job_rejects_result_fields(repository, field: str) -> None:
    job = repository.create_background_job("refresh", {})
    kwargs = {field: {"queued": True} if field == "result" else "queued error"}

    updated = repository.update_background_job(job["id"], **kwargs)

    assert updated is None
    stored = repository.get_background_job(job["id"])
    assert stored["result"] is None
    assert stored["error"] is None
