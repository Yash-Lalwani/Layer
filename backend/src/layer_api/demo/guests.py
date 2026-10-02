from datetime import timedelta

import jwt
from sqlalchemy import delete, select

from layer_api.db import ChatSession, DriveFile, Message, Project, ProjectSource, User, now
from layer_api.memory.store import list_facts, namespace
from layer_api.schemas import ApiError


async def cleanup_expired_guests(session_factory, checkpointer, store) -> None:
    async with session_factory() as db:
        guests = (await db.scalars(select(User).where(User.is_guest.is_(True), User.expires_at <= now()))).all()
        for guest in guests:
            projects = (await db.scalars(select(Project).where(Project.user_id == guest.id))).all()
            for project in projects:
                chats = (await db.scalars(select(ChatSession).where(ChatSession.project_id == project.id))).all()
                for chat in chats:
                    await checkpointer.adelete_thread(chat.id)
                    await db.execute(delete(Message).where(Message.chat_id == chat.id))
                await db.execute(delete(ChatSession).where(ChatSession.project_id == project.id))
                for fact in await list_facts(store, project.id):
                    await store.adelete(namespace(project.id), fact["id"])
                await db.execute(delete(DriveFile).where(DriveFile.project_id == project.id))
                await db.execute(delete(ProjectSource).where(ProjectSource.project_id == project.id))
                await db.delete(project)
            await db.delete(guest)
        await db.commit()


async def create_guest(db, settings) -> tuple[User, Project, str]:
    result = await db.execute(select(Project).join(User, Project.user_id == User.id).where(
        Project.collection_id == settings.demo_collection_id,
        Project.is_demo.is_(True), User.is_guest.is_(False)))
    template = result.scalar_one_or_none()
    if template is None:
        raise ApiError(503, "server_error", "The demo project is not ready")
    sources = (await db.scalars(select(ProjectSource).where(ProjectSource.project_id == template.id,
                                                           ProjectSource.status == "connected"))).all()
    if {source.source_type for source in sources} != {"drive", "gmail", "jira", "notion"}:
        raise ApiError(503, "server_error", "The demo sources are not ready")

    expires_at = now() + timedelta(hours=settings.demo_guest_ttl_hours)
    guest = User(name="Demo Guest", email=None, is_guest=True, questions_used=0, expires_at=expires_at)
    db.add(guest)
    await db.flush()
    project = Project(user_id=guest.id, name=template.name, description=template.description,
                      collection_id=template.collection_id, is_demo=True)
    db.add(project)
    await db.flush()
    db.add_all(ProjectSource(project_id=project.id, source_type=row.source_type, status=row.status,
                             account_label=row.account_label, config=dict(row.config or {}),
                             composio_account_id=row.composio_account_id, last_synced_at=row.last_synced_at)
               for row in sources)
    files = (await db.scalars(select(DriveFile).where(DriveFile.project_id == template.id))).all()
    db.add_all(DriveFile(project_id=project.id, drive_file_id=file.drive_file_id, name=file.name,
                         mime_type=file.mime_type, web_url=file.web_url, modified_time=file.modified_time,
                         status=file.status, error=file.error, ingested_at=file.ingested_at) for file in files)
    await db.commit()
    token = jwt.encode({"sub": guest.id, "iss": "layer-demo", "aud": "layer-api", "iat": now(),
                        "exp": expires_at}, settings.demo_token_secret, algorithm="HS256")
    return guest, project, token
