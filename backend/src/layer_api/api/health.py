from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from layer_api.db import get_session
from layer_api.integrations.engine_client import EngineClient, get_engine_client
from layer_api.schemas import ApiError


router = APIRouter(tags=["health"])


@router.get("/health")
async def health(
    session: Annotated[AsyncSession, Depends(get_session)],
    engine: Annotated[EngineClient, Depends(get_engine_client)],
):
    await session.execute(text("SELECT 1"))
    engine_status = await engine.health()
    if engine_status.get("status") != "ok":
        raise ApiError(503, "server_error", "RAG-Engine is not healthy")
    return {"status": "ok"}

