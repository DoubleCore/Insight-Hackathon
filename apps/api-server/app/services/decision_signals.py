from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import replace
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Literal

import httpx
from graphiti_core.edges import HasEpisodeEdge, NextEpisodeEdge
from graphiti_core.nodes import EpisodeType, EpisodicNode, SagaNode

from app.config import PROJECT_ROOT, Settings


logger = logging.getLogger(__name__)

DecisionSignalCategory = Literal[
    "policy", "technology", "industry_rule", "business_implication"
]
DecisionSignalSourceType = Literal["link", "document", "text"]

DECISION_SIGNAL_SAGA = "决策信号层"
MAX_CONTENT_CHARS = 12_000
MAX_PDF_PAGES = 12
EVIDENCE_EXCERPT_CHARS = 800
DEFAULT_EVIDENCE_DIR = PROJECT_ROOT / "data" / "evidence"
DECISION_SIGNAL_EVIDENCE_FILE = "decision_signals.jsonl"

CATEGORY_LABELS = {
    "policy": "政策风向",
    "technology": "技术趋势",
    "industry_rule": "行业规律",
    "business_implication": "企业战略含义",
}


def build_decision_signal_episode_body(
    *,
    title: str,
    category: str,
    source_type: str,
    content: str,
    source_url: str | None = None,
    keywords: str = "",
    industry_impact: str = "",
    dc_implication: str = "",
    notes: str = "",
    evidence_id: str | None = None,
) -> str:
    trimmed_content = content.strip()[:MAX_CONTENT_CHARS]
    return f"""资料类型：{CATEGORY_LABELS.get(category, category)}
标题：{title.strip()}
关键词：{keywords.strip()}
来源链接：{source_url or ""}
上传方式：{source_type}
证据ID：{evidence_id or ""}

核心内容：
{trimmed_content}

对产业链的可能影响：
{industry_impact.strip()}

对神州数码业务判断的可能影响：
{dc_implication.strip()}

备注：
{notes.strip()}
"""


def extract_text_from_upload(filename: str, payload: bytes) -> str:
    lower_name = filename.lower()
    if lower_name.endswith((".txt", ".md")):
        return payload.decode("utf-8", errors="ignore")
    if lower_name.endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(payload))
        pages = reader.pages[:MAX_PDF_PAGES]
        return "\n".join(page.extract_text() or "" for page in pages)
    raise ValueError("仅支持 .txt / .md / .pdf 文档")


async def fetch_link_text(url: str) -> str:
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
    return response.text[:MAX_CONTENT_CHARS]


def make_decision_signal_evidence_id(
    *, group_id: str, title: str, source_url: str | None, content: str
) -> str:
    digest = hashlib.sha1(
        "\n".join([group_id, title.strip(), source_url or "", content[:2000]]).encode("utf-8")
    ).hexdigest()[:10].upper()
    return f"DS-{datetime.now(UTC):%Y%m%d}-{digest}"


def write_decision_signal_evidence_record(
    *,
    evidence_id: str,
    group_id: str,
    title: str,
    category: str,
    source_type: str,
    content: str,
    episode_uuid: str,
    source_url: str | None = None,
    evidence_dir: Path | str | None = None,
) -> Path:
    target_dir = Path(evidence_dir or DEFAULT_EVIDENCE_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / DECISION_SIGNAL_EVIDENCE_FILE
    now = datetime.now(UTC).isoformat()
    source_grade = "B" if source_type == "link" and source_url else "B-"
    record = {
        "evidence_id": evidence_id,
        "source_title": title.strip(),
        "source_url_or_file": source_url or f"admin-upload:{episode_uuid}",
        "evidence_excerpt": content.strip()[:EVIDENCE_EXCERPT_CHARS],
        "source_grade": source_grade,
        "publish_date": None,
        "retrieved_at": now,
        "limitations": (
            "管理端决策资料上传；用于政策、技术趋势和经营判断背景，仍需结合原始来源人工复核。"
        ),
        "group_id": group_id,
        "category": category,
        "source_type": source_type,
        "episode_uuid": episode_uuid,
        "saga": DECISION_SIGNAL_SAGA,
    }
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    return target


async def _get_or_create_saga(
    driver: Any, *, group_id: str, created_at: datetime
) -> SagaNode:
    sagas = await SagaNode.get_by_group_ids(driver, [group_id])
    for saga in sagas:
        if saga.name == DECISION_SIGNAL_SAGA:
            return saga
    saga = SagaNode(name=DECISION_SIGNAL_SAGA, group_id=group_id, created_at=created_at)
    await saga.save(driver)
    return saga


async def _saga_last_episode_uuid(driver: Any, saga_uuid: str) -> str | None:
    records, _, _ = await driver.execute_query(
        """
        MATCH (s:Saga {uuid: $saga_uuid})-[:HAS_EPISODE]->(e:Episodic)
        RETURN e.uuid AS uuid, e.valid_at AS valid_at, e.created_at AS created_at
        ORDER BY e.valid_at DESC, e.created_at DESC
        LIMIT 1
        """,
        saga_uuid=saga_uuid,
        routing_="r",
    )
    return str(records[0]["uuid"]) if records else None


async def _save_episode_fallback(
    graphiti: Any,
    *,
    title: str,
    body: str,
    group_id: str,
    category: str,
    now: datetime,
    evidence_id: str,
) -> EpisodicNode:
    driver = graphiti.driver
    episode = EpisodicNode(
        name=title,
        group_id=group_id,
        labels=[],
        source=EpisodeType.text,
        content=body,
        source_description=f"{DECISION_SIGNAL_SAGA}/{CATEGORY_LABELS[category]}",
        created_at=now,
        valid_at=now,
        entity_edges=[],
        episode_metadata={
            "evidence_ids": [evidence_id],
            "category": category,
            "saga": DECISION_SIGNAL_SAGA,
            "fallback_ingest": True,
        },
    )
    await episode.save(driver)

    saga = await _get_or_create_saga(driver, group_id=group_id, created_at=now)
    previous_episode_uuid = await _saga_last_episode_uuid(driver, saga.uuid)
    if previous_episode_uuid is not None and previous_episode_uuid != episode.uuid:
        await NextEpisodeEdge(
            source_node_uuid=previous_episode_uuid,
            target_node_uuid=episode.uuid,
            group_id=group_id,
            created_at=now,
        ).save(driver)

    await HasEpisodeEdge(
        source_node_uuid=saga.uuid,
        target_node_uuid=episode.uuid,
        group_id=group_id,
        created_at=now,
    ).save(driver)
    if saga.first_episode_uuid is None or previous_episode_uuid is None:
        saga.first_episode_uuid = episode.uuid
    saga.last_episode_uuid = episode.uuid
    await saga.save(driver)
    return episode


async def import_decision_signal(
    *,
    settings: Settings,
    graphiti_factory: Any,
    group_id: str,
    title: str,
    category: DecisionSignalCategory,
    source_type: DecisionSignalSourceType,
    content: str,
    source_url: str | None = None,
    keywords: str = "",
    industry_impact: str = "",
    dc_implication: str = "",
    notes: str = "",
    evidence_dir: Path | str | None = None,
) -> dict[str, Any]:
    scoped_settings = replace(settings, group_id=group_id)
    graphiti = graphiti_factory(scoped_settings)
    now = datetime.now(UTC)
    evidence_id = make_decision_signal_evidence_id(
        group_id=group_id, title=title, source_url=source_url, content=content
    )
    body = build_decision_signal_episode_body(
        title=title,
        category=category,
        source_type=source_type,
        content=content,
        source_url=source_url,
        keywords=keywords,
        industry_impact=industry_impact,
        dc_implication=dc_implication,
        notes=notes,
        evidence_id=evidence_id,
    )
    fallback_reason: str | None = None
    try:
        try:
            result = await graphiti.add_episode(
                name=title,
                episode_body=body,
                source_description=f"{DECISION_SIGNAL_SAGA}/{CATEGORY_LABELS[category]}",
                reference_time=now,
                group_id=group_id,
                saga=DECISION_SIGNAL_SAGA,
            )
            episode_uuid = result.episode.uuid
        except Exception as exc:
            fallback_reason = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "Decision signal Graphiti extraction failed; saved raw episode fallback: %s",
                fallback_reason,
            )
            episode = await _save_episode_fallback(
                graphiti,
                title=title,
                body=body,
                group_id=group_id,
                category=category,
                now=now,
                evidence_id=evidence_id,
            )
            episode_uuid = episode.uuid

        write_decision_signal_evidence_record(
            evidence_id=evidence_id,
            group_id=group_id,
            title=title,
            category=category,
            source_type=source_type,
            content=content,
            episode_uuid=episode_uuid,
            source_url=source_url,
            evidence_dir=evidence_dir,
        )
        return {
            "group_id": group_id,
            "saga": DECISION_SIGNAL_SAGA,
            "evidence_id": evidence_id,
            "episode_uuid": episode_uuid,
            "title": title,
            "category": category,
            "source_type": source_type,
            "source_url": source_url,
            "content_preview": body[:500],
            "fallback_reason": fallback_reason,
        }
    finally:
        close = getattr(graphiti, "close", None)
        if close is not None:
            await close()
