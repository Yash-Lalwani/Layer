from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from layer_api.auth.security import read_token
from layer_api.db import User, get_session
from layer_api.schemas import ApiError


bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    user_id = read_token(credentials.credentials, request.app.state.settings.jwt_secret) if credentials else None
    user = await session.get(User, user_id) if user_id else None
    if user is None:
        raise ApiError(401, "unauthorized", "Please log in")
    return user

