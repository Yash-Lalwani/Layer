import logging
import time
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from layer_api.agent.citations import VerificationUnavailable
from layer_api.agent.streaming import sse
from layer_api.api.projects import owned_project
from layer_api.auth.dependencies import get_current_user
from layer_api.db import ChatSession, Message, Project, ProjectSource, User, get_session, now
from layer_api.memory.store import list_facts, namespace
from layer_api.schemas import ApiError, ChatMessageIn, ChatTitleIn, MemoryApprovalIn


router = APIRouter(tags=["chats"])
logger = logging.getLogger(__name__)


def chat_out(chat: ChatSession) -> dict:
    return {"id": chat.id, "project_id": chat.project_id, "title": chat.title,
            "created_at": chat.created_at, "updated_at": chat.updated_at}


def message_out(message: Message) -> dict:
    return {"id": message.id, "chat_id": message.chat_id, "role": message.role,
            "content": message.content, "answer": message.answer,
            "memory_decision": message.memory_decision, "created_at": message.created_at}


async def owned_chat(db: AsyncSession, chat_id: str, user_id: str) -> tuple[ChatSession, Project]:
    result = await db.execute(select(ChatSession, Project).join(Project, ChatSession.project_id == Project.id).where(
        ChatSession.id == chat_id, Project.user_id == user_id))
    row = result.first()
    if row is None:
        raise ApiError(404, "not_found", "Chat not found")
    return row


def configured(row: ProjectSource) -> bool:
    if row.status != "connected" or not row.composio_account_id or row.config is None:
        return False
    config = row.config
    if row.source_type == "drive":
        return bool(config.get("file_ids") or config.get("folder_ids"))
    if row.source_type == "jira":
        return bool(config.get("project_key"))
    if row.source_type == "notion":
        return bool(config.get("page_ids") or config.get("database_ids"))
    return row.source_type == "gmail"


@router.get("/projects/{project_id}/chats")
async def list_chats(project_id: str, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_session)]):
    await owned_project(db, project_id, user.id)
    chats = (await db.scalars(select(ChatSession).where(ChatSession.project_id == project_id).order_by(ChatSession.updated_at.desc()))).all()
    return [chat_out(chat) for chat in chats]


@router.post("/projects/{project_id}/chats", status_code=201)
async def create_chat(project_id: str, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_session)]):
    await owned_project(db, project_id, user.id)
    chat = ChatSession(project_id=project_id, title="New chat")
    db.add(chat)
    await db.commit()
    return chat_out(chat)


@router.patch("/chats/{chat_id}")
async def rename_chat(chat_id: str, body: ChatTitleIn, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_session)]):
    chat, _ = await owned_chat(db, chat_id, user.id)
    chat.title = body.title
    await db.commit()
    return chat_out(chat)


@router.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str, request: Request, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_session)]):
    chat, _ = await owned_chat(db, chat_id, user.id)
    await request.app.state.checkpointer.adelete_thread(chat.id)
    await db.delete(chat)
    await db.commit()
    return {"ok": True}


@router.get("/chats/{chat_id}/messages")
async def list_messages(chat_id: str, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_session)]):
    await owned_chat(db, chat_id, user.id)
    messages = (await db.scalars(select(Message).where(Message.chat_id == chat_id).order_by(Message.created_at, Message.id))).all()
    return [message_out(message) for message in messages]


@router.get("/projects/{project_id}/memory")
async def project_memory(project_id: str, request: Request, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_session)]):
    await owned_project(db, project_id, user.id)
    return await list_facts(request.app.state.memory_store, project_id)


@router.delete("/projects/{project_id}/memory/{fact_id}")
async def delete_memory(project_id: str, fact_id: str, request: Request, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_session)]):
    await owned_project(db, project_id, user.id)
    facts = await list_facts(request.app.state.memory_store, project_id)
    if not any(fact["id"] == fact_id for fact in facts):
        raise ApiError(404, "not_found", "Memory fact not found")
    await request.app.state.memory_store.adelete(namespace(project_id), fact_id)
    return {"ok": True}


async def pending_assistant(db: AsyncSession, chat_id: str) -> Message | None:
    messages = (await db.scalars(select(Message).where(Message.chat_id == chat_id, Message.role == "assistant")
                                 .order_by(Message.created_at.desc(), Message.id.desc()))).all()
    return next((message for message in messages if message.answer and message.answer.get("pending_memory")), None)


@router.post("/chats/{chat_id}/memory-approval")
async def memory_approval(chat_id: str, body: MemoryApprovalIn, request: Request, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_session)]):
    await owned_chat(db, chat_id, user.id)
    message = await pending_assistant(db, chat_id)
    graph = request.app.state.agent_graph
    config = {"configurable": {"thread_id": chat_id}}
    snapshot = await graph.aget_state(config)
    if not message or message.answer["pending_memory"]["approval_id"] != body.approval_id or "approve_memory" not in snapshot.next:
        raise ApiError(409, "conflict", "Memory approval is no longer pending")
    if body.decision == "approved" and not body.facts:
        raise ApiError(422, "validation_error", "Choose at least one fact to save")
    if body.decision == "approved":
        original = message.answer["pending_memory"]["facts"]
        if len(body.facts) > len(original):
            raise ApiError(422, "validation_error", "Too many facts")
    await graph.ainvoke(Command(resume={"decision": body.decision, "facts": body.facts if body.decision == "approved" else []}), config=config)
    message.memory_decision = body.decision
    message.answer = {**message.answer, "pending_memory": None}
    await db.commit()
    return message_out(message)


@router.post("/chats/{chat_id}/messages/stream")
async def stream_message(chat_id: str, body: ChatMessageIn, request: Request, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_session)]):
    chat, project = await owned_chat(db, chat_id, user.id)
    questions_left = None
    if user.is_guest:
        limit = request.app.state.settings.demo_questions_per_guest
        used = await db.scalar(update(User).where(User.id == user.id, User.questions_used < limit)
                               .values(questions_used=User.questions_used + 1).returning(User.questions_used))
        if used is None:
            raise ApiError(429, "demo_limit_reached", "The demo's 7 questions are used. Sign up to keep exploring.")
        questions_left = limit - used
        await db.commit()
    rows = (await db.scalars(select(ProjectSource).where(ProjectSource.project_id == project.id))).all()
    allowed = {row.source_type: row for row in rows if configured(row)}
    graph = request.app.state.agent_graph
    config = {"configurable": {"thread_id": chat_id}}
    snapshot = await graph.aget_state(config) if hasattr(graph, "aget_state") else None
    if snapshot and "approve_memory" in snapshot.next:
        await graph.ainvoke(Command(resume={"decision": "skipped", "facts": []}), config=config)
        old = await pending_assistant(db, chat_id)
        if old:
            old.memory_decision = "skipped"
            old.answer = {**old.answer, "pending_memory": None}
            await db.commit()
    inputs = {
        "messages": [HumanMessage(content=body.content)], "user_id": user.id, "chat_id": chat_id,
        "composio_user_id": "demo" if user.is_guest else user.id,
        "project_id": project.id, "collection_id": project.collection_id,
        "question": body.content, "started_at": time.perf_counter(),
        "source_configs": {name: row.config for name, row in allowed.items()},
        "source_accounts": {name: row.composio_account_id for name, row in allowed.items()},
    }

    async def events():
        answer = None
        try:
            async for part in graph.astream(inputs, config=config,
                                            stream_mode=["custom", "messages", "updates"], version="v2"):
                if part["type"] == "custom" and "step" in part["data"]:
                    yield sse("step", part["data"])
                elif part["type"] == "messages":
                    token, metadata = part["data"]
                    if metadata.get("langgraph_node") == "synthesize" and isinstance(token.content, str) and token.content:
                        yield sse("token", {"text": token.content})
                elif part["type"] == "updates" and "guard_output" in part["data"]:
                    answer = part["data"]["guard_output"]["answer_payload"]
            if answer is None:
                raise RuntimeError("The agent did not produce a final answer")
            snapshot = await graph.aget_state(config) if hasattr(graph, "aget_state") else None
            if snapshot and "approve_memory" in snapshot.next:
                answer = {**answer, "pending_memory": {
                    "approval_id": snapshot.values["memory_approval_id"],
                    "facts": snapshot.values["memory_candidates"],
                }}
            async with request.app.state.session_factory() as save_db:
                saved_chat, _ = await owned_chat(save_db, chat_id, user.id)
                user_message = Message(chat_id=chat_id, role="user", content=body.content)
                assistant_message = Message(chat_id=chat_id, role="assistant", content=answer["text"], answer=answer)
                save_db.add_all([user_message, assistant_message])
                if saved_chat.title == "New chat":
                    saved_chat.title = body.content[:80]
                saved_chat.updated_at = now()
                await save_db.commit()
                await save_db.refresh(user_message)
                await save_db.refresh(assistant_message)
                yield sse("final", {"user_message": message_out(user_message), "assistant_message": message_out(assistant_message), "questions_left": questions_left})
        except VerificationUnavailable as exc:
            yield sse("error", {"code": "verification_failed", "message": str(exc)})
        except ApiError as exc:
            yield sse("error", {"code": exc.code, "message": exc.message})
        except Exception:
            logger.exception("Chat stream failed")
            yield sse("error", {"code": "server_error", "message": "The answer could not be completed. Please try again."})

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
