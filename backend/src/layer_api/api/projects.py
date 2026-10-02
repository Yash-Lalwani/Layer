from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from layer_api.auth.dependencies import get_current_user
from layer_api.db import ChatSession, Project, ProjectSource, User, get_session
from layer_api.integrations.engine_client import EngineClient, get_engine_client
from layer_api.memory.store import list_facts, namespace
from layer_api.schemas import ApiError, ProjectCreateIn, ProjectOut, ProjectPatchIn


router = APIRouter(prefix="/projects", tags=["projects"])


def project_out(project: Project, sources: list[str] | None = None) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        name=project.name,
        description=project.description,
        is_demo=project.is_demo,
        connected_sources=sources or [],
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


async def owned_project(session: AsyncSession, project_id: str, user_id: str) -> Project:
    project = await session.scalar(select(Project).where(Project.id == project_id, Project.user_id == user_id))
    if project is None:
        raise ApiError(404, "not_found", "Project not found")
    return project


async def connected_sources(session: AsyncSession, project_id: str) -> list[str]:
    result = await session.scalars(
        select(ProjectSource.source_type).where(
            ProjectSource.project_id == project_id, ProjectSource.status == "connected"
        )
    )
    return list(result)


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    projects = (await session.scalars(
        select(Project).where(Project.user_id == user.id).order_by(Project.created_at.desc())
    )).all()
    return [project_out(project, await connected_sources(session, project.id)) for project in projects]


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    body: ProjectCreateIn,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    engine: Annotated[EngineClient, Depends(get_engine_client)],
):
    if user.is_guest:
        raise ApiError(403, "forbidden", "Demo projects cannot be changed")
    project_id = str(uuid4())
    collection_id = f"layer-{project_id}"
    await engine.create_collection(collection_id, body.name)
    project = Project(
        id=project_id,
        user_id=user.id,
        name=body.name,
        description=body.description,
        collection_id=collection_id,
    )
    session.add(project)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        await engine.delete_collection(collection_id)
        raise
    return project_out(project)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    project = await owned_project(session, project_id, user.id)
    return project_out(project, await connected_sources(session, project.id))


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: str,
    body: ProjectPatchIn,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    project = await owned_project(session, project_id, user.id)
    if user.is_guest or project.is_demo:
        raise ApiError(403, "forbidden", "Demo projects cannot be changed")
    if "name" in body.model_fields_set:
        if body.name is None:
            raise ApiError(422, "validation_error", "Project name is required")
        project.name = body.name
    if "description" in body.model_fields_set:
        project.description = body.description
    await session.commit()
    return project_out(project, await connected_sources(session, project.id))


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    engine: Annotated[EngineClient, Depends(get_engine_client)],
):
    project = await owned_project(session, project_id, user.id)
    if user.is_guest:
        raise ApiError(403, "forbidden", "Demo projects cannot be changed")
    if not project.is_demo:
        await engine.delete_collection(project.collection_id)
    chat_ids = (await session.scalars(select(ChatSession.id).where(ChatSession.project_id == project_id))).all()
    for chat_id in chat_ids:
        await request.app.state.checkpointer.adelete_thread(chat_id)
    for fact in await list_facts(request.app.state.memory_store, project_id):
        await request.app.state.memory_store.adelete(namespace(project_id), fact["id"])
    await session.delete(project)
    await session.commit()
    return {"ok": True}
