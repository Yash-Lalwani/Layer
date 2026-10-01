from typing import Any

from fastapi import Request
from mcp.client.session import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

from layer_api.config import Settings


class EngineError(Exception):
    pass


class EngineClient:
    def __init__(self, settings: Settings):
        self.url = settings.rag_engine_url
        self.api_key = settings.rag_engine_api_key

    async def _call(self, tool: str, arguments: dict[str, Any] | None = None, *, authenticated: bool = True) -> dict:
        if authenticated and not self.api_key:
            raise EngineError("RAG_ENGINE_API_KEY is not configured")
        headers = {"Authorization": f"Bearer {self.api_key}"} if authenticated else {}
        try:
            async with create_mcp_http_client(headers=headers) as http:
                async with streamable_http_client(self.url, http_client=http) as streams:
                    async with ClientSession(streams[0], streams[1]) as session:
                        await session.initialize()
                        result = await session.call_tool(tool, arguments or {})
            if result.is_error:
                message = result.content[0].text if result.content else f"{tool} failed"
                raise EngineError(message)
            if result.structured_content is None:
                raise EngineError(f"{tool} returned no structured result")
            return result.structured_content
        except EngineError:
            raise
        except Exception as exc:
            raise EngineError(f"RAG-Engine {tool} failed: {exc}") from exc

    async def health(self) -> dict:
        return await self._call("health", authenticated=False)

    async def create_collection(self, collection_id: str, name: str) -> dict:
        return await self._call("create_collection", {"collection_id": collection_id, "name": name})

    async def delete_collection(self, collection_id: str) -> dict:
        return await self._call("delete_collection", {"collection_id": collection_id})

    async def ingest_document(self, collection_id: str, content_base64: str, filename: str, doc_id: str, metadata: dict) -> dict:
        return await self._call("ingest_document", {"collection_id": collection_id, "content_base64": content_base64, "filename": filename, "doc_id": doc_id, "metadata": metadata})

    async def delete_document(self, collection_id: str, doc_id: str) -> dict:
        return await self._call("delete_document", {"collection_id": collection_id, "doc_id": doc_id})

    async def list_documents(self, collection_id: str) -> dict:
        return await self._call("list_documents", {"collection_id": collection_id})


def get_engine_client(request: Request) -> EngineClient:
    return request.app.state.engine_client
