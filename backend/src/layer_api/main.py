import logging
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.exceptions import HTTPException as StarletteHTTPException

from layer_api.api import auth, chats, health, projects, sources
from layer_api.agent.graph import build_graph
from layer_api.config import Settings
from layer_api.demo.guests import cleanup_expired_guests
from layer_api.db import Base
from layer_api.integrations.engine_client import EngineClient, EngineError
from layer_api.integrations.composio_client import ComposioClient, ComposioError
from layer_api.schemas import ApiError


logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, engine_client: EngineClient | None = None, composio_client: ComposioClient | None = None, small_model=None, strong_model=None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database = create_async_engine(settings.sqlalchemy_url)
        app.state.session_factory = async_sessionmaker(database, expire_on_commit=False)
        app.state.engine_client = engine_client or EngineClient(settings)
        app.state.composio_client = composio_client or ComposioClient(settings)
        async with database.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with AsyncExitStack() as stack:
            if settings.database_url.startswith("sqlite"):
                from langgraph.checkpoint.memory import InMemorySaver
                from langgraph.store.memory import InMemoryStore
                checkpointer = InMemorySaver()
                store = InMemoryStore()
            else:
                from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
                from langgraph.store.postgres.aio import AsyncPostgresStore
                checkpointer = await stack.enter_async_context(AsyncPostgresSaver.from_conn_string(settings.database_url))
                await checkpointer.setup()
                store = await stack.enter_async_context(AsyncPostgresStore.from_conn_string(settings.database_url))
                await store.setup()
            app.state.checkpointer = checkpointer
            app.state.memory_store = store
            app.state.agent_graph = build_graph(settings, app.state.engine_client, app.state.composio_client, checkpointer, small_model, strong_model, store=store)
            await cleanup_expired_guests(app.state.session_factory, checkpointer, store)
            yield
        await database.dispose()

    app = FastAPI(title="Layer API", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, error: ApiError):
        return JSONResponse(status_code=error.status_code, content={"error": {"code": error.code, "message": error.message}})

    @app.exception_handler(EngineError)
    async def engine_error_handler(request: Request, error: EngineError):
        logger.warning("RAG-Engine error: %s", error)
        return JSONResponse(status_code=503, content={"error": {"code": "server_error", "message": str(error)}})

    @app.exception_handler(ComposioError)
    async def composio_error_handler(request: Request, error: ComposioError):
        logger.warning("Composio error: %s", error)
        return JSONResponse(status_code=503, content={"error": {"code": "server_error", "message": str(error)}})

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, error: RequestValidationError):
        message = error.errors()[0]["msg"] if error.errors() else "Invalid request"
        return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": message}})

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, error: StarletteHTTPException):
        code = "not_found" if error.status_code == 404 else "server_error"
        return JSONResponse(status_code=error.status_code, content={"error": {"code": code, "message": str(error.detail)}})

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, error: Exception):
        logger.exception("Unhandled API error", exc_info=error)
        return JSONResponse(status_code=500, content={"error": {"code": "server_error", "message": "Internal server error"}})

    app.include_router(auth.router)
    app.include_router(projects.router)
    app.include_router(sources.router)
    app.include_router(chats.router)
    app.include_router(health.router)
    return app


app = create_app()
