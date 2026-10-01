# Layer backend

Layer uses Clerk to sign in registered users. The backend verifies each Clerk session token and maps its Clerk user ID to a stable Layer UUID. Project and Composio ownership use the Layer UUID.

## Local Clerk setup

1. Use the same Clerk Development application configured in `frontend/.env.local`.
2. Put its `CLERK_SECRET_KEY` in the ignored `backend/.env`. Set `FRONTEND_URL=http://localhost:3000`. Generate a separate random `OAUTH_STATE_SECRET` for Composio callback state.
3. Optionally copy the **PEM JWT public key** from Clerk Dashboard → API Keys → Show JWT public key into `CLERK_JWT_KEY`. Encode line breaks as `\n` in `.env`. With this key, token verification is local. Without it, the Clerk SDK obtains the verification key from Clerk using the secret key.
4. For an existing local Postgres database, run `docker compose exec -T postgres psql -U layer -d layer -v ON_ERROR_STOP=1 < migrations/001_clerk_user_id.sql` once. The migration adds `clerk_user_id` and removes the unused password hash column. The local database had no users when this migration was prepared.

## Run and check

```bash
uv sync
docker compose up -d postgres
uv run pytest
uv run uvicorn layer_api.main:app --reload --port 8080
```

In another terminal, run the frontend on port 3000. Sign up through Clerk and verify your email. `GET /auth/me` then creates a Layer user with its own UUID. The old `/auth/register` and `/auth/login` endpoints are gone. The backend accepts Clerk session tokens from the frontend origin only.

RAG-Engine must also be running at `RAG_ENGINE_URL` before creating a project. For the local setup, start its Postgres and Qdrant services, then run `uv run python -m rag_engine.mcp_server` from the separate `Rag-Engine` repository. Layer creates the project's RAG collection when you click **New project**.
