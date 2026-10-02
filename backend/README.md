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

RAG-Engine must be reachable at `RAG_ENGINE_URL` before creating a project. The deployed endpoint is `https://rag.yashlalwani.info/mcp`; put its Layer-scoped bearer key in `RAG_ENGINE_API_KEY` in the ignored `backend/.env`. Never put that key in the frontend. Layer creates the project's RAG collection when you click **New project**. For a local RAG-Engine, run `docker compose up -d qdrant postgres` and then `uv run python -m rag_engine.mcp_server` from the separate `RAG-Engine` repository. That repository's `docker-compose.override.yml` maps the original `rag-engine_qdrant_data` and `rag-engine_postgres_data` volumes into the healthy `rag-engine-local` Compose project. Keep that file and those volumes to retain the local data.

Layer uses the Python MCP client with bearer authentication and a 90-second HTTP timeout for the deployed Engine. Project creation and Drive Sync use `create_collection`, `list_documents`, and `ingest_document`; chat uses `search`, `rerank`, and `verify_citations`. Deletion uses the matching document or collection delete tool. Layer's project ownership and source selections are checked before these calls. The Engine's `ask` and `approve_sql` tools are reserved for a future project-scoped SQL source; Layer does not expose the Engine's unrelated SQL database. That future flow should show the proposed SQL and explanation in the chat, save its `query_id` against the Layer user, project, and chat, and call `approve_sql` only after that same user approves or rejects it.

## Phase 3 chat

Put `OPENAI_API_KEY` in the ignored `backend/.env` locally. The plan's `LLM_MODEL_SMALL=gpt-4o-mini` handles question decomposition; `LLM_MODEL_STRONG=gpt-4o` writes the draft answer. Never commit the key. Run `uv sync` after pulling this phase's dependencies.

Chat uses LangGraph's Postgres checkpointer in the Layer database and creates its checkpoint tables at backend startup. Start RAG-Engine before asking questions. Only sources connected and configured for the chosen project are searched. Drive must be synced first. The browser receives a provisional draft, then a checked final answer; a citation-verification failure produces an error instead of saving the draft.

Drive sync marks `.sql` and `.sh` files as failed because RAG-Engine cannot parse those formats; other files in the selected folder continue syncing.

## Project memory

The backend creates LangGraph's Postgres Store tables at startup. After a verified answer, the small model proposes up to three durable facts. A fact is saved only after the user approves it in the chat card. Editing changes what is saved, rejecting saves nothing, and sending another message skips the pending proposal. The Memory tab lists and deletes facts for the current project. Facts are scoped to that project's UUID and are included when planning later chats.

## Phoenix guest demo

`demo_data/` contains 10 Drive documents, 20 email drafts, 15 Jira issues, and 4 Notion pages. Review them before loading anything. The email set includes one deliberate prompt-injection test message for the later guardrail phase.

1. Use **dedicated demo accounts**, separate from personal accounts. The existing Phoenix Google test account can serve as the Drive and Gmail demo identity, provided the demo project selects only fabricated Phoenix content. Upload `demo_data/drive/` to a `Phoenix Demo` Drive folder; create a Jira project with key `PHX`; prepare a Notion parent page shared with the demo connection.
2. From `backend/`, run `uv run python scripts/setup_demo_project.py connect drive`, then `connect gmail`, `connect jira`, and `connect notion`, **one at a time**. Open each printed managed OAuth link and complete consent before starting the next. Put the returned account IDs in the corresponding `DEMO_*_ACCOUNT_ID` entries of the ignored `backend/.env`. A new `connect` command gives a fresh link if one expires.
3. Set `DEMO_DRIVE_FOLDER_IDS` (and optionally `DEMO_DRIVE_FILE_IDS`), `DEMO_NOTION_PAGE_IDS` (and optionally `DEMO_NOTION_DATABASE_IDS`), `DEMO_GMAIL_LABEL=phoenix`, and `DEMO_JIRA_PROJECT_KEY=PHX` in `backend/.env`. Set `DEMO_TOKEN_SECRET` to a random secret. Configure a working RAG endpoint and its Layer bearer key in the same ignored file.
4. Run `uv run python scripts/create_demo_drafts.py` to preview the synthetic email count, then `uv run python scripts/create_demo_drafts.py --create` to create the missing drafts under the `phoenix` label. No email is sent. The demo Gmail scope uses `label:phoenix in:drafts`, so other mail in the same account is excluded. Run `uv run python scripts/create_demo_jira_issues.py` to preview the Jira count, then add `--create` to create missing `PHX` issues from the CSV. The script labels them `phoenix-demo`; the demo JQL requires that label, excluding unrelated issues in `PHX`. Jira assigns its own issue keys. The CSV's fictional owners and original statuses are recorded in descriptions; supported `In Progress` and `Done` statuses are also applied to the Jira workflow. Run `uv run python scripts/create_demo_notion_pages.py <parent-page-id> --create` to create the four fabricated child pages, then set `DEMO_NOTION_PAGE_IDS` to the four printed child IDs. Uploading Markdown files as attachments does not create readable Notion page content.
5. Run `uv run python scripts/setup_demo_project.py setup`. It validates all four demo accounts, creates the shared `layer-demo-phoenix` RAG collection and internal template project, and syncs only the chosen Drive files. Once sync reports available documents, **Try the demo** creates a 24-hour guest copy with separate chats and memory, read-only sources, and seven questions. The shared collection is never deleted during guest cleanup.

The backend demo token is separate from Clerk and is stored by the frontend as a short-lived cookie. Only the backend verifies it. No Composio or RAG keys go to the browser. Browser acceptance testing can be done after the dedicated demo accounts are loaded.
