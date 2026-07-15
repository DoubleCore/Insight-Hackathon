from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from pydantic import BaseModel

from app.schemas import LlmCallTrace, QueryTrace, RetrievalCandidate, RetrievalSlice


SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conversations_owner
    ON conversations(owner_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id, created_at);

CREATE TABLE IF NOT EXISTS query_runs (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    query_text TEXT NOT NULL,
    status TEXT NOT NULL,
    answer TEXT,
    error TEXT,
    stages_json TEXT NOT NULL DEFAULT '[]',
    trace_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_query_runs_created ON query_runs(created_at DESC);

CREATE TABLE IF NOT EXISTS retrieval_slices (
    id TEXT PRIMARY KEY,
    query_run_id TEXT NOT NULL REFERENCES query_runs(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    algorithm TEXT NOT NULL,
    query_text TEXT NOT NULL,
    status TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_retrieval_slices_run
    ON retrieval_slices(query_run_id, created_at);

CREATE TABLE IF NOT EXISTS retrieval_candidates (
    id TEXT PRIMARY KEY,
    slice_id TEXT NOT NULL REFERENCES retrieval_slices(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    score REAL NOT NULL,
    algorithm TEXT NOT NULL,
    evidence_level TEXT,
    confidence REAL,
    valid_from TEXT,
    valid_to TEXT,
    verification_status TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_retrieval_candidates_slice
    ON retrieval_candidates(slice_id, score DESC);

CREATE TABLE IF NOT EXISTS llm_calls (
    id TEXT PRIMARY KEY,
    query_run_id TEXT NOT NULL REFERENCES query_runs(id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    purpose TEXT NOT NULL,
    status TEXT NOT NULL,
    request_tokens INTEGER,
    response_tokens INTEGER,
    latency_ms REAL,
    request_json TEXT NOT NULL DEFAULT '{}',
    response_json TEXT NOT NULL DEFAULT '{}',
    error TEXT,
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_llm_calls_run ON llm_calls(query_run_id, created_at);

CREATE TABLE IF NOT EXISTS background_jobs (
    id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    result_json TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    worker_id TEXT,
    heartbeat_at TEXT,
    lease_expires_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_background_jobs_status
    ON background_jobs(status, updated_at DESC);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _identifier() -> str:
    return str(uuid4())


def _payload(value: BaseModel | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return dict(value)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    result = dict(row)
    if "query_text" in result:
        result["query"] = result.pop("query_text")
    for column in list(result):
        if column.endswith("_json"):
            decoded_name = column.removesuffix("_json")
            raw = result.pop(column)
            result[decoded_name] = json.loads(raw) if raw is not None else None
    return result


_CANDIDATE_METADATA_FIELDS = {
    "uuid",
    "algorithms",
    "object_type",
    "rank",
    "selected",
    "evidence_ids",
    "source",
    "target",
    "relation",
    "data_as_of",
    "last_verified_at",
    "needs_refresh_after",
    "current_validity",
    "requires_internal_validation",
    "claim_nature",
    "rerank_score",
    "rerank_fallback_reason",
}


def _candidate_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    result = _row(row)
    if result is None:
        return None
    metadata = result.get("metadata") or {}
    for field in _CANDIDATE_METADATA_FIELDS:
        if field in metadata:
            result[field] = metadata[field]
    return result


class Repository:
    def __init__(self, database_path: str | Path):
        if str(database_path) == ":memory:":
            raise ValueError("Repository 不支持 :memory:，请使用临时文件数据库")
        self.database_path = Path(database_path)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA synchronous = NORMAL")
            connection.execute("PRAGMA busy_timeout = 10000")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    _connect = connection

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
            connection.executescript(SCHEMA)
            existing_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(background_jobs)")
            }
            for column in ("worker_id", "heartbeat_at", "lease_expires_at"):
                if column not in existing_columns:
                    connection.execute(f"ALTER TABLE background_jobs ADD COLUMN {column} TEXT")
            query_run_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(query_runs)")
            }
            if "trace_id" not in query_run_columns:
                connection.execute("ALTER TABLE query_runs ADD COLUMN trace_id TEXT")

    def create_conversation(self, owner_id: str, title: str | None = None) -> dict[str, Any]:
        conversation_id = _identifier()
        timestamp = _now()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO conversations (id, owner_id, title, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (conversation_id, owner_id, title, timestamp, timestamp),
            )
        return self.get_conversation(conversation_id)

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            return _row(
                connection.execute(
                    "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
                ).fetchone()
            )

    def list_conversations(self, owner_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM conversations WHERE owner_id = ? ORDER BY updated_at DESC",
                (owner_id,),
            ).fetchall()
        return [_row(item) for item in rows]  # type: ignore[misc]

    def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        message_id = _identifier()
        timestamp = _now()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO messages "
                "(id, conversation_id, role, content, metadata_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (message_id, conversation_id, role, content, _json(metadata or {}), timestamp),
            )
            connection.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (timestamp, conversation_id),
            )
        return self.get_message(message_id)

    def get_message(self, message_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            return _row(
                connection.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
            )

    def list_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at, rowid",
                (conversation_id,),
            ).fetchall()
        return [_row(item) for item in rows]  # type: ignore[misc]

    def create_query_run(
        self,
        conversation_id: str,
        query: str,
        *,
        status: str = "queued",
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        query_run_id = _identifier()
        timestamp = _now()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO query_runs "
                "(id, conversation_id, query_text, status, stages_json, trace_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, '[]', ?, ?, ?)",
                (
                    query_run_id,
                    conversation_id,
                    query,
                    status,
                    trace_id,
                    timestamp,
                    timestamp,
                ),
            )
        return self.get_query_run(query_run_id)

    def get_query_run(self, query_run_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            return _row(
                connection.execute(
                    "SELECT * FROM query_runs WHERE id = ?", (query_run_id,)
                ).fetchone()
            )

    def update_query_run(
        self,
        query_run_id: str,
        *,
        status: str | None = None,
        answer: str | None = None,
        error: str | None = None,
        stages: list[Mapping[str, Any]] | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any] | None:
        values: dict[str, Any] = {"updated_at": _now()}
        if status is not None:
            values["status"] = status
        if answer is not None:
            values["answer"] = answer
        if error is not None:
            values["error"] = error
        if stages is not None:
            values["stages_json"] = _json(stages)
        if trace_id is not None:
            values["trace_id"] = trace_id
        assignments = ", ".join(f"{column} = ?" for column in values)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE query_runs SET {assignments} WHERE id = ?",
                (*values.values(), query_run_id),
            )
        return self.get_query_run(query_run_id)

    def list_query_runs(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM query_runs ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row(item) for item in rows]  # type: ignore[misc]

    def recover_interrupted_query_runs(self) -> int:
        timestamp = _now()
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE query_runs SET status = 'interrupted', updated_at = ?, "
                "error = COALESCE(error, '服务重启，问答请求已中断') "
                "WHERE status IN ('queued', 'running')",
                (timestamp,),
            )
        return cursor.rowcount

    def write_retrieval_slice(
        self, query_run_id: str, retrieval_slice: BaseModel | Mapping[str, Any]
    ) -> dict[str, Any]:
        data = _payload(retrieval_slice)
        slice_id = data.get("id") or _identifier()
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO retrieval_slices "
                "(id, query_run_id, name, algorithm, query_text, status, metadata_json, "
                "started_at, completed_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET "
                "name = excluded.name, algorithm = excluded.algorithm, "
                "query_text = excluded.query_text, "
                "status = excluded.status, metadata_json = excluded.metadata_json, "
                "started_at = excluded.started_at, completed_at = excluded.completed_at "
                "WHERE retrieval_slices.query_run_id = excluded.query_run_id",
                (
                    slice_id,
                    query_run_id,
                    data["name"],
                    data["algorithm"],
                    data["query"],
                    data.get("status", "completed"),
                    _json(data.get("metadata", {})),
                    data.get("started_at"),
                    data.get("completed_at"),
                    _now(),
                ),
            )
            if cursor.rowcount == 0:
                raise ValueError(
                    f"retrieval slice {slice_id} belongs to another query run"
                )
            candidates = data.get("candidates", [])
            candidate_ids = [candidate["id"] for candidate in candidates]
            if candidate_ids:
                placeholders = ", ".join("?" for _ in candidate_ids)
                connection.execute(
                    f"DELETE FROM retrieval_candidates WHERE slice_id = ? "
                    f"AND id NOT IN ({placeholders})",
                    (slice_id, *candidate_ids),
                )
            else:
                connection.execute(
                    "DELETE FROM retrieval_candidates WHERE slice_id = ?", (slice_id,)
                )
            for candidate in candidates:
                self._upsert_retrieval_candidate(connection, slice_id, candidate)
        return self.get_retrieval_slice(slice_id)

    def get_retrieval_slice(self, slice_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            return _row(
                connection.execute(
                    "SELECT * FROM retrieval_slices WHERE id = ?", (slice_id,)
                ).fetchone()
            )

    def list_retrieval_slices(self, query_run_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM retrieval_slices WHERE query_run_id = ? ORDER BY created_at, rowid",
                (query_run_id,),
            ).fetchall()
        return [_row(item) for item in rows]  # type: ignore[misc]

    def write_retrieval_candidate(
        self, slice_id: str, candidate: BaseModel | Mapping[str, Any]
    ) -> dict[str, Any]:
        data = _payload(candidate)
        candidate_id = data.get("id") or _identifier()
        with self._connect() as connection:
            self._upsert_retrieval_candidate(
                connection, slice_id, {**data, "id": candidate_id}
            )
        return self.get_retrieval_candidate(candidate_id)

    def _upsert_retrieval_candidate(
        self, connection: sqlite3.Connection, slice_id: str, data: Mapping[str, Any]
    ) -> None:
        cursor = connection.execute(
            "INSERT INTO retrieval_candidates "
            "(id, slice_id, title, content, score, algorithm, evidence_level, confidence, "
            "valid_from, valid_to, verification_status, metadata_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "title = excluded.title, content = excluded.content, score = excluded.score, "
            "algorithm = excluded.algorithm, "
            "evidence_level = excluded.evidence_level, confidence = excluded.confidence, "
            "valid_from = excluded.valid_from, valid_to = excluded.valid_to, "
            "verification_status = excluded.verification_status, "
            "metadata_json = excluded.metadata_json "
            "WHERE retrieval_candidates.slice_id = excluded.slice_id",
            (
                data["id"],
                slice_id,
                data["title"],
                data["content"],
                data["score"],
                data["algorithm"],
                data.get("evidence_level"),
                data.get("confidence"),
                data.get("valid_from"),
                data.get("valid_to"),
                data.get("verification_status"),
                _json(data.get("metadata", {})),
                _now(),
            ),
        )
        if cursor.rowcount == 0:
            raise ValueError(
                f"retrieval candidate {data['id']} belongs to another retrieval slice"
            )

    def get_retrieval_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            return _candidate_row(
                connection.execute(
                    "SELECT * FROM retrieval_candidates WHERE id = ?", (candidate_id,)
                ).fetchone()
            )

    def list_retrieval_candidates(self, slice_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM retrieval_candidates WHERE slice_id = ? ORDER BY score DESC, rowid",
                (slice_id,),
            ).fetchall()
        return [_candidate_row(item) for item in rows]  # type: ignore[misc]

    def write_llm_call(
        self, query_run_id: str, llm_call: BaseModel | Mapping[str, Any]
    ) -> dict[str, Any]:
        data = _payload(llm_call)
        call_id = data.get("id") or _identifier()
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO llm_calls "
                "(id, query_run_id, model, purpose, status, request_tokens, response_tokens, "
                "latency_ms, request_json, response_json, error, started_at, completed_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET model = excluded.model, "
                "purpose = excluded.purpose, status = excluded.status, "
                "request_tokens = excluded.request_tokens, "
                "response_tokens = excluded.response_tokens, latency_ms = excluded.latency_ms, "
                "request_json = excluded.request_json, response_json = excluded.response_json, "
                "error = excluded.error, started_at = excluded.started_at, "
                "completed_at = excluded.completed_at "
                "WHERE llm_calls.query_run_id = excluded.query_run_id",
                (
                    call_id,
                    query_run_id,
                    data["model"],
                    data["purpose"],
                    data["status"],
                    data.get("request_tokens"),
                    data.get("response_tokens"),
                    data.get("latency_ms"),
                    _json(data.get("request", {})),
                    _json(data.get("response", {})),
                    data.get("error"),
                    data.get("started_at"),
                    data.get("completed_at"),
                    _now(),
                ),
            )
        if cursor.rowcount == 0:
            raise ValueError(f"llm call {call_id} belongs to another query run")
        return self.get_llm_call(call_id)

    def get_llm_call(self, call_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            return _row(
                connection.execute("SELECT * FROM llm_calls WHERE id = ?", (call_id,)).fetchone()
            )

    def list_llm_calls(self, query_run_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM llm_calls WHERE query_run_id = ? ORDER BY created_at, rowid",
                (query_run_id,),
            ).fetchall()
        return [_row(item) for item in rows]  # type: ignore[misc]

    def get_query_trace(self, query_run_id: str) -> QueryTrace | None:
        query_run = self.get_query_run(query_run_id)
        if query_run is None:
            return None
        if "stages" not in query_run or query_run["stages"] is None:
            raise ValueError("查询运行缺少阶段数据")

        retrieval_slices: list[RetrievalSlice] = []
        for stored_slice in self.list_retrieval_slices(query_run_id):
            candidates = [
                RetrievalCandidate.model_validate(candidate)
                for candidate in self.list_retrieval_candidates(stored_slice["id"])
            ]
            retrieval_slices.append(
                RetrievalSlice.model_validate({**stored_slice, "candidates": candidates})
            )
        llm_calls = [
            LlmCallTrace.model_validate(call) for call in self.list_llm_calls(query_run_id)
        ]
        return QueryTrace.model_validate(
            {
                **query_run,
                "stages": query_run["stages"],
                "retrieval_slices": retrieval_slices,
                "llm_calls": llm_calls,
            }
        )

    def create_background_job(
        self,
        job_type: str,
        payload: Mapping[str, Any],
        *,
        status: str = "queued",
        worker_id: str | None = None,
        heartbeat_at: str | None = None,
        lease_expires_at: str | None = None,
    ) -> dict[str, Any]:
        job_id = _identifier()
        timestamp = _now()
        started_at = timestamp if status == "running" else None
        completed_at = timestamp if status in {"completed", "failed", "interrupted"} else None
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO background_jobs "
                "(id, job_type, status, payload_json, created_at, updated_at, started_at, "
                "completed_at, worker_id, heartbeat_at, lease_expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job_id,
                    job_type,
                    status,
                    _json(payload),
                    timestamp,
                    timestamp,
                    started_at,
                    completed_at,
                    worker_id,
                    heartbeat_at,
                    lease_expires_at,
                ),
            )
        return self.get_background_job(job_id)

    def get_background_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            return _row(
                connection.execute(
                    "SELECT * FROM background_jobs WHERE id = ?", (job_id,)
                ).fetchone()
            )

    def update_background_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        result: Mapping[str, Any] | None = None,
        error: str | None = None,
        worker_id: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        timestamp = (now or datetime.now(UTC)).isoformat()
        values: dict[str, Any] = {"updated_at": timestamp}
        terminal_statuses = {"completed", "failed", "interrupted"}
        if status is not None:
            values["status"] = status
            if status in terminal_statuses:
                values["completed_at"] = timestamp
        if result is not None:
            values["result_json"] = _json(result)
        if error is not None:
            values["error"] = error

        eligibility: list[str] = []
        eligibility_parameters: list[Any] = []
        if status is None or status == "running" or status in terminal_statuses:
            eligibility.append(
                "(status = 'running' AND worker_id = ? AND lease_expires_at > ?)"
            )
            eligibility_parameters.extend((worker_id, timestamp))
        queued_update_is_harmless = (
            status in {None, "queued"} and result is None and error is None
        )
        if queued_update_is_harmless:
            eligibility.append("status = 'queued'")
        if not eligibility:
            return None

        assignments = ", ".join(f"{column} = ?" for column in values)
        eligibility_clause = " OR ".join(eligibility)
        with self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE background_jobs SET {assignments} "
                f"WHERE id = ? AND ({eligibility_clause})",
                (*values.values(), job_id, *eligibility_parameters),
            )
        if cursor.rowcount == 0:
            return None
        return self.get_background_job(job_id)

    def list_background_jobs(self, *, status: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM background_jobs"
        parameters: tuple[Any, ...] = ()
        if status is not None:
            sql += " WHERE status = ?"
            parameters = (status,)
        sql += " ORDER BY updated_at DESC, rowid DESC"
        with self._connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [_row(item) for item in rows]  # type: ignore[misc]

    def claim_background_job(
        self,
        job_id: str,
        worker_id: str,
        *,
        lease_seconds: int,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        if lease_seconds <= 0:
            raise ValueError("任务租约时长必须大于零")
        heartbeat = now or datetime.now(UTC)
        heartbeat_at = heartbeat.isoformat()
        lease_expires_at = (heartbeat + timedelta(seconds=lease_seconds)).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE background_jobs SET status = 'running', worker_id = ?, "
                "heartbeat_at = ?, lease_expires_at = ?, updated_at = ?, "
                "started_at = COALESCE(started_at, ?) "
                "WHERE id = ? AND (status = 'queued' OR "
                "(status = 'running' AND "
                "lease_expires_at <= ?))",
                (
                    worker_id,
                    heartbeat_at,
                    lease_expires_at,
                    heartbeat_at,
                    heartbeat_at,
                    job_id,
                    heartbeat_at,
                ),
            )
        if cursor.rowcount == 0:
            return None
        return self.get_background_job(job_id)

    def heartbeat_background_job(
        self,
        job_id: str,
        worker_id: str,
        *,
        lease_seconds: int,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        if lease_seconds <= 0:
            raise ValueError("任务租约时长必须大于零")
        heartbeat = now or datetime.now(UTC)
        heartbeat_at = heartbeat.isoformat()
        lease_expires_at = (heartbeat + timedelta(seconds=lease_seconds)).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE background_jobs SET status = 'running', worker_id = ?, "
                "heartbeat_at = ?, lease_expires_at = ?, updated_at = ?, "
                "started_at = COALESCE(started_at, ?) "
                "WHERE id = ? AND status = 'running' AND worker_id = ? "
                "AND lease_expires_at > ?",
                (
                    worker_id,
                    heartbeat_at,
                    lease_expires_at,
                    heartbeat_at,
                    heartbeat_at,
                    job_id,
                    worker_id,
                    heartbeat_at,
                ),
            )
        if cursor.rowcount == 0:
            return None
        return self.get_background_job(job_id)

    def recover_interrupted_jobs(
        self,
        *,
        now: datetime | None = None,
        include_active: bool = False,
        include_queued: bool = True,
    ) -> int:
        timestamp = (now or datetime.now(UTC)).isoformat()
        status_filter = (
            "status IN ('queued', 'running')"
            if include_queued
            else "status = 'running'"
        )
        lease_filter = "" if include_active else (
            "AND (lease_expires_at IS NULL OR lease_expires_at <= ?)"
        )
        parameters: tuple[str, ...] = (
            (timestamp, timestamp)
            if include_active
            else (timestamp, timestamp, timestamp)
        )
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE background_jobs "
                "SET status = 'interrupted', updated_at = ?, completed_at = ?, "
                "error = COALESCE(error, '服务重启，任务已中断') "
                f"WHERE {status_filter} "
                f"{lease_filter}",
                parameters,
            )
        return cursor.rowcount
