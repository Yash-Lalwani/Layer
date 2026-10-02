from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from layer_api.auth.dependencies import get_current_user
from layer_api.db import User, get_session
from layer_api.demo.guests import cleanup_expired_guests, create_guest
from layer_api.schemas import UserOut, user_out


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(get_current_user)]):
    return user_out(user)


@router.post("/demo", status_code=201)
async def demo(request: Request, db: Annotated[AsyncSession, Depends(get_session)]):
    settings = request.app.state.settings
    if not settings.demo_token_secret:
        from layer_api.schemas import ApiError
        raise ApiError(503, "server_error", "Demo is not configured")
    await cleanup_expired_guests(request.app.state.session_factory, request.app.state.checkpointer,
                                 request.app.state.memory_store)
    guest, project, token = await create_guest(db, settings)
    return {"token": token, "project_id": project.id, "questions_left": settings.demo_questions_per_guest}
