import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from layer_api.api.projects import owned_project
from layer_api.auth.dependencies import get_current_user
from layer_api.db import DriveFile, ProjectSource, User, get_session
from layer_api.integrations.composio_client import ComposioClient, TOOLKITS, composio_user_id, get_composio_client
from layer_api.integrations.drive import list_folder, metadata, selected_files
from layer_api.integrations.drive_sync import sync_drive
from layer_api.integrations.engine_client import EngineClient, get_engine_client
from layer_api.integrations.gmail import gmail_query, labels, preview
from layer_api.integrations.jira import projects as jira_projects
from layer_api.integrations.notion import search as notion_search
from layer_api.schemas import ApiError


router = APIRouter(tags=["sources"])
logger = logging.getLogger(__name__)
SourceType = Literal["drive", "gmail", "jira", "notion"]
SOURCE_TYPES = ("drive", "gmail", "jira", "notion")


class DriveConfig(BaseModel):
    file_ids: list[str] = Field(default_factory=list)
    folder_ids: list[str] = Field(default_factory=list)


class GmailConfig(BaseModel):
    labels: list[str] = Field(default_factory=list)
    senders: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    query: str = ""


class JiraConfig(BaseModel):
    project_key: str = Field(min_length=1)
    jql: str | None = None

    @field_validator("project_key")
    @classmethod
    def clean_project_key(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Choose a Jira project")
        return value


class NotionConfig(BaseModel):
    page_ids: list[str] = Field(default_factory=list)
    database_ids: list[str] = Field(default_factory=list)


def source_out(source_type: str, row: ProjectSource | None) -> dict:
    return {
        "type": source_type, "status": row.status if row else "not_connected",
        "account_label": row.account_label if row else None,
        "config": row.config if row else None,
        "last_synced_at": row.last_synced_at if row else None,
    }


async def source_row(db: AsyncSession, project_id: str, source_type: str) -> ProjectSource | None:
    return await db.scalar(select(ProjectSource).where(ProjectSource.project_id == project_id, ProjectSource.source_type == source_type))


async def source_context(db: AsyncSession, project_id: str, user: User, source_type: str, write: bool = False):
    project = await owned_project(db, project_id, user.id)
    if write and (user.is_guest or project.is_demo):
        raise ApiError(403, "forbidden", "Demo sources are read-only")
    row = await source_row(db, project_id, source_type)
    if not row or row.status != "connected" or not row.composio_account_id:
        raise ApiError(422, "validation_error", f"Connect {source_type} first")
    return project, row


@router.get("/projects/{project_id}/sources")
async def list_sources(project_id: str, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_session)]):
    await owned_project(db, project_id, user.id)
    rows = (await db.scalars(select(ProjectSource).where(ProjectSource.project_id == project_id))).all()
    by_type = {row.source_type: row for row in rows}
    return [source_out(kind, by_type.get(kind)) for kind in SOURCE_TYPES]


@router.post("/projects/{project_id}/sources/{source_type}/connect")
async def connect_source(project_id: str, source_type: SourceType, request: Request, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_session)], composio: Annotated[ComposioClient, Depends(get_composio_client)]):
    project = await owned_project(db, project_id, user.id)
    if user.is_guest or project.is_demo:
        raise ApiError(403, "forbidden", "Demo sources are read-only")
    state = jwt.encode({"sub": user.id, "project_id": project_id, "source_type": source_type, "exp": datetime.now(timezone.utc) + timedelta(minutes=15)}, request.app.state.settings.oauth_state_secret, algorithm="HS256")
    callback = str(request.url_for("integration_callback")) + f"?state={state}"
    account_id, redirect_url = await composio.authorize(user.id, source_type, callback)
    row = await source_row(db, project_id, source_type)
    if row is None:
        row = ProjectSource(project_id=project_id, source_type=source_type)
        db.add(row)
    row.composio_account_id = account_id
    row.status = "not_connected"
    await db.commit()
    return {"redirect_url": redirect_url}


@router.get("/integrations/callback", name="integration_callback")
async def integration_callback(state: str, request: Request, db: Annotated[AsyncSession, Depends(get_session)], composio: Annotated[ComposioClient, Depends(get_composio_client)]):
    frontend = request.app.state.settings.frontend_url.rstrip("/")
    try:
        claim = jwt.decode(state, request.app.state.settings.oauth_state_secret, algorithms=["HS256"])
        user_id, project_id, source_type = claim["sub"], claim["project_id"], claim["source_type"]
        if source_type not in SOURCE_TYPES:
            raise ValueError("Unknown source")
        await owned_project(db, project_id, user_id)
        row = await source_row(db, project_id, source_type)
        if row is None or not row.composio_account_id:
            raise ValueError("Connection was not started")
        account = await composio.account(row.composio_account_id)
        if account.get("status", "").upper() != "ACTIVE" or account.get("user_id") != composio_user_id(user_id) or (account.get("toolkit") or {}).get("slug") != TOOLKITS[source_type]:
            raise ValueError("Connection is not active for this user")
        data = account.get("data") or {}
        scopes = set(str(data.get("scope") or "").split())
        if source_type == "drive" and "https://www.googleapis.com/auth/drive" not in scopes:
            raise ValueError("Drive permission was not granted")
        if source_type == "gmail" and "https://mail.google.com/" not in scopes:
            raise ValueError("Gmail permission was not granted")
        row.status = "connected"
        row.account_label = data.get("displayName") or data.get("workspace_name") or source_type.title()
        row.config = row.config or {"file_ids": [], "folder_ids": []} if source_type == "drive" else row.config
        await db.commit()
        return RedirectResponse(f"{frontend}/workspace/{project_id}?connected={source_type}")
    except Exception as exc:
        logger.warning("Source connection callback failed: %s", exc)
        source_type = locals().get("source_type", "unknown")
        project_id = locals().get("project_id", "")
        return RedirectResponse(f"{frontend}/workspace/{project_id}?connect_error={source_type}")


@router.delete("/projects/{project_id}/sources/{source_type}")
async def disconnect_source(project_id: str, source_type: SourceType, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_session)], engine: Annotated[EngineClient, Depends(get_engine_client)]):
    project = await owned_project(db, project_id, user.id)
    if user.is_guest or project.is_demo:
        raise ApiError(403, "forbidden", "Demo sources are read-only")
    row = await source_row(db, project_id, source_type)
    if source_type == "drive":
        files = (await db.scalars(select(DriveFile).where(DriveFile.project_id == project_id))).all()
        for file in files:
            if file.ingested_at:
                await engine.delete_document(project.collection_id, f"drive:{file.drive_file_id}")
            await db.delete(file)
    if row:
        await db.delete(row)
    await db.commit()
    return {"ok": True}


@router.put("/projects/{project_id}/sources/{source_type}/config")
async def update_config(project_id: str, source_type: SourceType, body: dict, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_session)], composio: Annotated[ComposioClient, Depends(get_composio_client)], engine: Annotated[EngineClient, Depends(get_engine_client)]):
    project, row = await source_context(db, project_id, user, source_type, write=True)
    models = {"drive": DriveConfig, "gmail": GmailConfig, "jira": JiraConfig, "notion": NotionConfig}
    config = models[source_type].model_validate(body).model_dump()
    if source_type == "gmail":
        config["query"] = gmail_query({**config, "query": ""})
    if source_type == "drive":
        async with composio.tools(user.id, "drive", row.composio_account_id) as tools:
            selected = await selected_files(tools, config["file_ids"], config["folder_ids"])
        selected_ids = {item["id"] for item in selected}
        existing = (await db.scalars(select(DriveFile).where(DriveFile.project_id == project_id))).all()
        for file in existing:
            if file.drive_file_id not in selected_ids:
                if file.ingested_at:
                    await engine.delete_document(project.collection_id, f"drive:{file.drive_file_id}")
                await db.delete(file)
    row.config = config
    await db.commit()
    return source_out(source_type, row)


@router.get("/projects/{project_id}/sources/drive/browse")
async def browse_drive(project_id: str, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_session)], composio: Annotated[ComposioClient, Depends(get_composio_client)], folder_id: str | None = None):
    _, row = await source_context(db, project_id, user, "drive")
    async with composio.tools(user.id, "drive", row.composio_account_id) as tools:
        items = await list_folder(tools, folder_id)
        path = []
        current = folder_id
        while current and current != "root":
            info = await metadata(tools, current)
            path.insert(0, {"id": current, "name": info.get("name") or "Folder"})
            current = (info.get("parents") or [None])[0]
    return {"path": path, "items": items}


@router.get("/projects/{project_id}/sources/drive/files")
async def drive_files(project_id: str, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_session)]):
    await owned_project(db, project_id, user.id)
    rows = (await db.scalars(select(DriveFile).where(DriveFile.project_id == project_id).order_by(DriveFile.name))).all()
    return [{"id": row.drive_file_id, "name": row.name, "mime_type": row.mime_type, "web_url": row.web_url, "status": row.status, "error": row.error, "modified_time": row.modified_time, "ingested_at": row.ingested_at} for row in rows]


@router.post("/projects/{project_id}/sources/drive/sync")
async def start_drive_sync(project_id: str, background: BackgroundTasks, request: Request, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_session)], composio: Annotated[ComposioClient, Depends(get_composio_client)], engine: Annotated[EngineClient, Depends(get_engine_client)]):
    await source_context(db, project_id, user, "drive", write=True)
    background.add_task(sync_drive, request.app.state.session_factory, composio, engine, project_id, user.id)
    return {"started": True}


@router.delete("/projects/{project_id}/sources/drive/files/{file_id}")
async def remove_drive_file(project_id: str, file_id: str, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_session)], engine: Annotated[EngineClient, Depends(get_engine_client)], composio: Annotated[ComposioClient, Depends(get_composio_client)]):
    project, source = await source_context(db, project_id, user, "drive", write=True)
    config = source.config or {"file_ids": [], "folder_ids": []}
    if file_id not in config.get("file_ids", []):
        raise ApiError(422, "validation_error", "Remove its selected folder to exclude this file")
    config["file_ids"] = [item for item in config["file_ids"] if item != file_id]
    if config.get("folder_ids"):
        async with composio.tools(user.id, "drive", source.composio_account_id) as tools:
            remaining = await selected_files(tools, [], config["folder_ids"])
        if any(item["id"] == file_id for item in remaining):
            raise ApiError(422, "validation_error", "Remove its selected folder to exclude this file")
    source.config = dict(config)
    row = await db.scalar(select(DriveFile).where(DriveFile.project_id == project_id, DriveFile.drive_file_id == file_id))
    if row:
        if row.ingested_at:
            await engine.delete_document(project.collection_id, f"drive:{file_id}")
        await db.delete(row)
    await db.commit()
    return {"ok": True}


@router.get("/projects/{project_id}/sources/gmail/labels")
async def gmail_labels(project_id: str, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_session)], composio: Annotated[ComposioClient, Depends(get_composio_client)]):
    _, row = await source_context(db, project_id, user, "gmail")
    async with composio.tools(user.id, "gmail", row.composio_account_id) as tools:
        return await labels(tools)


@router.post("/projects/{project_id}/sources/gmail/preview")
async def gmail_preview(project_id: str, body: GmailConfig, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_session)], composio: Annotated[ComposioClient, Depends(get_composio_client)]):
    _, row = await source_context(db, project_id, user, "gmail")
    async with composio.tools(user.id, "gmail", row.composio_account_id) as tools:
        return await preview(tools, body.model_dump())


@router.get("/projects/{project_id}/sources/jira/projects")
async def list_jira_projects(project_id: str, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_session)], composio: Annotated[ComposioClient, Depends(get_composio_client)]):
    _, row = await source_context(db, project_id, user, "jira")
    async with composio.tools(user.id, "jira", row.composio_account_id) as tools:
        return await jira_projects(tools)


@router.get("/projects/{project_id}/sources/notion/search")
async def search_notion(project_id: str, q: str, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_session)], composio: Annotated[ComposioClient, Depends(get_composio_client)]):
    _, row = await source_context(db, project_id, user, "notion")
    async with composio.tools(user.id, "notion", row.composio_account_id) as tools:
        return await notion_search(tools, q)
