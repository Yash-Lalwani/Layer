from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from layer_api.auth.clerk import clerk_profile, verify_session
from layer_api.db import User, get_session
from layer_api.schemas import ApiError


async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    settings = request.app.state.settings
    clerk_user_id = verify_session(request, settings)
    user = await session.scalar(select(User).where(User.clerk_user_id == clerk_user_id))
    if user:
        return user

    name, email = await clerk_profile(clerk_user_id, settings)
    if await session.scalar(select(User).where(User.email == email)):
        raise ApiError(409, "conflict", "This email already belongs to a Layer account")

    user = User(name=name, email=email, clerk_user_id=clerk_user_id)
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = await session.scalar(select(User).where(User.clerk_user_id == clerk_user_id))
        if existing:
            return existing
        raise ApiError(409, "conflict", "This email already belongs to a Layer account") from None
    return user
