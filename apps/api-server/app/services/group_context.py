from __future__ import annotations

import asyncio
import inspect
import re
from typing import Any

from fastapi import HTTPException, Request


GROUP_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$")


def validate_group_id(value: str) -> str:
    normalized = value.strip()
    if not GROUP_ID_PATTERN.fullmatch(normalized):
        raise HTTPException(
            status_code=422,
            detail="group_id 只能包含字母、数字、下划线和短横线，长度 2-64",
        )
    return normalized


def request_group_id(request: Request, group_id: str | None = None) -> str:
    if group_id is not None and group_id.strip():
        return validate_group_id(group_id)
    header_value = request.headers.get("X-Graph-Group")
    if header_value:
        return validate_group_id(header_value)
    return request.app.state.settings.group_id


async def list_existing_groups(driver: Any, default_group_id: str) -> list[str]:
    query = """
    CALL {
      MATCH (n:Entity) WHERE n.group_id IS NOT NULL RETURN n.group_id AS group_id
      UNION
      MATCH (n:Episodic) WHERE n.group_id IS NOT NULL RETURN n.group_id AS group_id
      UNION
      MATCH (n:Saga) WHERE n.group_id IS NOT NULL RETURN n.group_id AS group_id
      UNION
      MATCH (n:Community) WHERE n.group_id IS NOT NULL RETURN n.group_id AS group_id
    }
    RETURN DISTINCT group_id ORDER BY group_id
    """

    def run() -> Any:
        return driver.execute_query(query, routing_="r")

    response = await asyncio.to_thread(run)
    if inspect.isawaitable(response):
        response = await response
    records = response[0] if isinstance(response, tuple) else response.records
    groups = [str(record["group_id"]) for record in records if record.get("group_id")]
    if default_group_id not in groups:
        groups.insert(0, default_group_id)
    return groups
