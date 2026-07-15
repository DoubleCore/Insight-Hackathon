from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import re

from fastapi import APIRouter, Request

from app.schemas import (
    IndustrySearchHit,
    IndustryPendingEpisodeRequest,
    IndustryPendingEpisodeResult,
    IndustrySearchRequest,
    IndustrySearchResult,
)
from app.services.group_context import request_group_id
from app.services.web_search import WebSearchHit


router = APIRouter(prefix="/api/v1/industry-search", tags=["industry-search"])


@router.post("", response_model=IndustrySearchResult)
async def industry_search(
    payload: IndustrySearchRequest, request: Request
) -> IndustrySearchResult:
    group_id = _resolve_target_group(request, payload)
    query = _build_query(
        payload.industry_name,
        payload.include_digital_china,
        payload.search_depth,
        payload.relation_types,
    )
    service = request.app.state.web_search_service
    max_results = _depth_max_results(payload.search_depth, payload.max_results)
    hits = await service.search(
        query, providers=payload.providers, max_results=max_results
    )
    return IndustrySearchResult(
        group_id=group_id,
        industry_name=payload.industry_name,
        query=query,
        target_mode=payload.target_mode,
        search_depth=payload.search_depth,
        relation_types=payload.relation_types,
        include_digital_china=payload.include_digital_china,
        manual_review_required=payload.manual_review_required,
        ingestion_status="待人工审核" if payload.manual_review_required else "草稿未入库",
        hits=[IndustrySearchHit(**asdict(hit)) for hit in hits],
        draft_episode_body=_build_draft(
            payload.industry_name,
            group_id,
            hits,
            payload.include_digital_china,
            payload.search_depth,
            payload.relation_types,
            payload.manual_review_required,
        ),
    )


@router.post("/pending-episode", response_model=IndustryPendingEpisodeResult)
async def create_pending_episode(
    payload: IndustryPendingEpisodeRequest,
) -> IndustryPendingEpisodeResult:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    now_text = now.isoformat().replace("+00:00", "Z")
    safe_industry = payload.industry_name.strip()
    safe_group = payload.group_id.strip()
    timestamp = now.strftime("%Y%m%d%H%M%S")
    episode_body = _build_pending_episode_body(payload)
    episode = {
        "episode_id": f"industry_extension::{safe_group}::{_slug(safe_industry)}::{timestamp}",
        "episode_name": f"{safe_industry}-公开资料扩展草稿",
        "episode_body": episode_body,
        "source": "text",
        "source_description": "产业扩展公开搜索草稿 / 待人工审核",
        "reference_time": now_text,
        "group_id": safe_group,
        "saga": "Layer 2 资料证据层 / 产业扩展公开搜索草稿",
        "legacy_saga_key": "industry_extension_draft",
        "saga_key": "layer2_industry_extension_draft",
        "saga_name": "Layer 2 资料证据层 / 产业扩展公开搜索草稿",
        "layer_id": 2,
        "layer_name": "资料证据层",
        "fact_set_name": "产业扩展公开搜索草稿",
        "fact_set_type": "public_search_draft",
        "fact_set_description": "由产业扩展页面生成的公开资料草稿，需人工审核后才能入库。",
        "display_name": "Layer 2 资料证据层 / 产业扩展公开搜索草稿",
        "claim_nature": "public_search_draft",
        "requires_internal_validation": True,
        "ingestion_status": "pending_ingest",
    }
    return IndustryPendingEpisodeResult(episode=episode)


def _resolve_target_group(request: Request, payload: IndustrySearchRequest) -> str:
    if payload.target_mode == "new_group":
        return request_group_id(request, payload.new_group_id)
    return request_group_id(request, payload.group_id)


def _depth_max_results(search_depth: str, requested: int) -> int:
    defaults = {"quick": 5, "standard": 8, "deep": 15}
    return min(max(requested, defaults.get(search_depth, 8)), 20)


def _build_query(
    industry_name: str,
    include_digital_china: bool,
    search_depth: str,
    relation_types: list[str],
) -> str:
    relation_words = " ".join(relation_types)
    base = f"{industry_name} 产业链 L4 细分环节 产品 服务 企业 {relation_words} 公开资料 证据"
    if search_depth == "standard":
        base += " 龙头企业 上下游 供应链 客户 伙伴 新闻 公告 招投标"
    elif search_depth == "deep":
        base += " 龙头企业 上下游 供应链 客户 伙伴 新闻 公告 招投标 年报 官网 解决方案 生态合作"
    if include_digital_china:
        base += " 神州数码 客户 合作伙伴 公开关系"
    return base[:380]


def _build_draft(
    industry_name: str,
    group_id: str,
    hits: list[WebSearchHit],
    include_digital_china: bool,
    search_depth: str,
    relation_types: list[str],
    manual_review_required: bool,
) -> str:
    source_lines = "\n".join(
        f"- [{hit.title}]({hit.url})：{hit.content[:180]}" for hit in hits
    )
    digital_china_line = (
        "需要判断企业与神州数码的公开关系状态、证据 ID、是否需要内部验证。"
        if include_digital_china
        else "本次不判断神州数码关系。"
    )
    review_line = (
        "本次结果仅作为草稿，必须人工审核后才允许进入正式图谱。"
        if manual_review_required
        else "本次结果仍未自动入库，可后续手动确认后写入。"
    )
    return f"""产业名称：{industry_name}
目标 group：{group_id}
搜索深度：{search_depth}
关注关系：{"、".join(relation_types) if relation_types else "未指定"}
入库口径：{review_line}

目标结构：
- L4 细分产业链节点
- 产品/服务
- 生产、采购、销售、使用这些产品/服务的企业主体
- 企业之间的{"、".join(relation_types) if relation_types else "交易、合作、股权、竞争、渠道"}关系
- {digital_china_line}

公开资料来源：
{source_lines if source_lines else "- 未检索到可用公开资料"}
"""


def _build_pending_episode_body(payload: IndustryPendingEpisodeRequest) -> str:
    hit_lines = "\n".join(
        f"- 来源：{hit.title or hit.url}\n  URL：{hit.url}\n  摘要：{hit.content[:240]}"
        for hit in payload.hits
    )
    return f"""{payload.draft_episode_body.strip()}

质量治理字段：
- 判断性质：公开搜索草稿
- claim_nature：public_search_draft
- 置信度：medium-low
- 当前有效性：待人工审核
- 是否需要内部验证：true
- 是否分析神州数码关系：{"true" if payload.include_digital_china else "false"}
- 人工审核要求：{"待人工审核" if payload.manual_review_required else "可人工复核后入库"}
- 搜索深度：{payload.search_depth}
- 关系类型：{"、".join(payload.relation_types) if payload.relation_types else "未指定"}
- 搜索 query：{payload.query}

待审核公开来源：
{hit_lines if hit_lines else "- 未提供公开来源"}
"""


def _slug(value: str) -> str:
    normalized = re.sub(r"\s+", "_", value.strip())
    return re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]", "", normalized) or "industry"
