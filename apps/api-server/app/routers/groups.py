from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas import GroupSummary
from app.services.group_context import list_existing_groups


router = APIRouter(prefix="/api/v1/groups", tags=["group"])


@router.get("", response_model=list[GroupSummary])
async def groups(request: Request) -> list[GroupSummary]:
    default_group = request.app.state.settings.group_id
    graph_service = request.app.state.graph_service_by_group.get(default_group)
    if graph_service is None:
        from app.services.graph import Neo4jGraphService

        graph_service = Neo4jGraphService.from_settings(request.app.state.settings)
        request.app.state.graph_service_by_group[default_group] = graph_service
    group_ids = await list_existing_groups(graph_service.driver, default_group)
    return [
        GroupSummary(id=item, label=item, is_default=item == default_group)
        for item in group_ids
    ]
