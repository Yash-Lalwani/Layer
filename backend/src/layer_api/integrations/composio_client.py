import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any

from composio import Composio, SESSION_PRESET_DIRECT_TOOLS
from fastapi import Request
from mcp.client.session import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

from layer_api.config import Settings


TOOLKITS = {"drive": "googledrive", "gmail": "gmail", "jira": "jira", "notion": "notion"}
TOOLS = {
    "drive": ["GOOGLEDRIVE_FIND_FILE", "GOOGLEDRIVE_GET_FILE_METADATA", "GOOGLEDRIVE_DOWNLOAD_FILE", "GOOGLEDRIVE_EXPORT_GOOGLE_WORKSPACE_FILE"],
    "gmail": ["GMAIL_LIST_LABELS", "GMAIL_FETCH_EMAILS", "GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID"],
    "jira": ["JIRA_GET_ALL_PROJECTS", "JIRA_SEARCH_FOR_ISSUES_USING_JQL_POST", "JIRA_GET_ISSUE"],
    "notion": ["NOTION_SEARCH_NOTION_PAGE", "NOTION_RETRIEVE_PAGE", "NOTION_GET_PAGE_MARKDOWN", "NOTION_FETCH_ALL_BLOCK_CONTENTS", "NOTION_FETCH_BLOCK_CONTENTS", "NOTION_QUERY_DATABASE"],
}


class ComposioError(Exception):
    pass


def composio_user_id(user_id: str) -> str:
    if user_id == "demo":
        return "layer-demo"
    if user_id == "demo-sender":
        return "layer-demo-sender"
    return f"layer-user-{user_id}"


def first_error(group: ExceptionGroup) -> Exception:
    error = group.exceptions[0]
    return first_error(error) if isinstance(error, ExceptionGroup) else error


class ComposioClient:
    def __init__(self, settings: Settings):
        self.client = Composio(api_key=settings.composio_api_key) if settings.composio_api_key else None

    def _client(self) -> Composio:
        if self.client is None:
            raise ComposioError("COMPOSIO_API_KEY is not configured")
        return self.client

    async def authorize(self, user_id: str, source_type: str, callback_url: str) -> tuple[str, str]:
        toolkit = TOOLKITS[source_type]

        def start():
            session = self._client().sessions.create(user_id=composio_user_id(user_id), toolkits=[toolkit], mcp=True)
            return session.authorize(toolkit, callback_url=callback_url)

        try:
            request = await asyncio.to_thread(start)
            return request.id, request.redirect_url
        except Exception as exc:
            raise ComposioError(f"Could not start {source_type} connection: {exc}") from exc

    async def account(self, account_id: str) -> dict[str, Any]:
        try:
            account = await asyncio.to_thread(self._client().connected_accounts.get, account_id)
            return account.model_dump(mode="json")
        except Exception as exc:
            raise ComposioError(f"Could not check connected account: {exc}") from exc

    @asynccontextmanager
    async def tools(self, user_id: str, source_type: str, account_id: str):
        toolkit = TOOLKITS[source_type]

        def make_session():
            return self._client().sessions.create(
                user_id=composio_user_id(user_id),
                toolkits=[toolkit],
                tools={toolkit: {"enable": TOOLS[source_type]}},
                connected_accounts={toolkit: account_id},
                session_preset=SESSION_PRESET_DIRECT_TOOLS,
                mcp=True,
            )

        try:
            session = await asyncio.to_thread(make_session)
        except Exception as exc:
            raise ComposioError(f"Could not open {source_type} tools: {exc}") from exc
        try:
            async with create_mcp_http_client(headers=session.mcp.headers) as http:
                async with streamable_http_client(session.mcp.url, http_client=http) as streams:
                    async with ClientSession(streams[0], streams[1]) as mcp:
                        await mcp.initialize()
                        yield ComposioToolSession(mcp)
        except ExceptionGroup as exc:
            error = first_error(exc)
            if isinstance(error, ComposioError):
                raise error from exc
            raise ComposioError(f"{source_type} tools failed: {error}") from exc


class ComposioToolSession:
    def __init__(self, session: ClientSession):
        self.session = session

    async def call(self, tool: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        result = await self.session.call_tool(tool, arguments or {})
        if not result.content or not hasattr(result.content[0], "text"):
            raise ComposioError(f"{tool} returned no data")
        try:
            payload = json.loads(result.content[0].text)
        except json.JSONDecodeError as exc:
            raise ComposioError(f"{tool} returned invalid data") from exc
        if result.is_error or not payload.get("successful", False):
            raise ComposioError(f"{tool} failed: {payload.get('error') or 'Unknown error'}")
        return payload.get("data") or {}


def get_composio_client(request: Request) -> ComposioClient:
    return request.app.state.composio_client
