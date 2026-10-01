from typing import Annotated

from fastapi import APIRouter, Depends

from layer_api.auth.dependencies import get_current_user
from layer_api.db import User
from layer_api.schemas import UserOut, user_out


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(get_current_user)]):
    return user_out(user)
