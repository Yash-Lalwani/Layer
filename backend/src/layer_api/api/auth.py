from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from layer_api.auth.dependencies import get_current_user
from layer_api.auth.security import create_token, hash_password, verify_password
from layer_api.db import User, get_session
from layer_api.schemas import ApiError, AuthOut, LoginIn, RegisterIn, UserOut, user_out


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthOut)
async def register(body: RegisterIn, request: Request, session: Annotated[AsyncSession, Depends(get_session)]):
    email = str(body.email).lower()
    if await session.scalar(select(User).where(User.email == email)):
        raise ApiError(422, "validation_error", "Email is already registered")
    user = User(name=body.name, email=email, password_hash=hash_password(body.password))
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise ApiError(422, "validation_error", "Email is already registered") from None
    return AuthOut(token=create_token(user.id, request.app.state.settings.jwt_secret), user=user_out(user))


@router.post("/login", response_model=AuthOut)
async def login(body: LoginIn, request: Request, session: Annotated[AsyncSession, Depends(get_session)]):
    user = await session.scalar(select(User).where(User.email == str(body.email).lower()))
    if user is None or user.password_hash is None or not verify_password(body.password, user.password_hash):
        raise ApiError(401, "unauthorized", "Invalid email or password")
    return AuthOut(token=create_token(user.id, request.app.state.settings.jwt_secret), user=user_out(user))


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(get_current_user)]):
    return user_out(user)

