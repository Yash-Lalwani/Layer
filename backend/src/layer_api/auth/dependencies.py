from datetime import timezone
from typing import Annotated

import jwt

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from layer_api.auth.clerk import clerk_profile, verify_session
from layer_api.db import User, get_session, now
from layer_api.schemas import ApiError


async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    settings = request.app.state.settings
    bearer = request.headers.get("authorization", "")
    token = bearer[7:] if bearer.lower().startswith("bearer ") else ""
    if token and settings.demo_token_secret:
        try:
            claims = jwt.decode(token, settings.demo_token_secret, algorithms=["HS256"],
                                audience="layer-api", issuer="layer-demo")
        except jwt.InvalidTokenError:
            claims = None
        if claims is not None:
            guest = await session.get(User, claims.get("sub", ""))
            expires_at = guest.expires_at if guest else None
            if expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if not guest or not guest.is_guest or not expires_at or expires_at <= now():
                raise ApiError(401, "unauthorized", "Demo session expired")
            return guest
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
