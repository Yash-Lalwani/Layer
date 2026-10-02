from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message


class UserOut(BaseModel):
    id: str
    name: str
    email: str | None
    is_guest: bool
    questions_left: int | None
    created_at: datetime


class ProjectCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Project name is required")
        return value


class ProjectPatchIn(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Project name is required")
        return value


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str | None
    is_demo: bool
    connected_sources: list[str]
    created_at: datetime
    updated_at: datetime


class ChatMessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def clean_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Enter a question")
        return value


class ChatTitleIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Title is required")
        return value


class MemoryApprovalIn(BaseModel):
    approval_id: str
    decision: Literal["approved", "rejected"]
    facts: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("facts")
    @classmethod
    def clean_facts(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip() and len(value.strip()) <= 500]


def user_out(user) -> UserOut:
    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        is_guest=user.is_guest,
        questions_left=7 - user.questions_used if user.is_guest else None,
        created_at=user.created_at,
    )
