# Layer

Layer is a project assistant in the spirit of NotebookLM. A user creates projects, connects Google Drive, Gmail, Jira and Notion to each project, and chats with an agent that answers from those sources with verified citations. It is built by Yash as a personal, learning-focused resume project.

Layer uses **RAG-Engine** (Yash's separate repository) as its retrieval engine over MCP.

**The build spec is `LAYER_APP_PLAN.md`.** Before starting or continuing a phase, read the plan's section for that phase and every section it references. This file holds the rules that apply to every phase.

---

## Ground Rules (follow always)

These rules come from Yash. They matter more than anything else, including the plan.

**Why they exist.** Yash must be able to explain every part of this project in an interview. The more complex the code, the harder that becomes. It is not a startup product and does not need to be 110% production-perfect. It will be deployed so recruiters can try it, not to serve real customers at scale.

**The rule in one line: build every planned feature properly, and implement it at learning level with no extra machinery just to make it perfect.**

1. **Build the planned features.** Query decomposition, MCP tool use (RAG-Engine and Composio), cited answers with citation verification, streaming, short-term and long-term memory, human-in-the-loop memory approval, guardrails, tracing, evaluation, and demo mode. Do not cut a feature to make the job easier.
2. **Make them work properly.** Every feature must actually work correctly and be tested.
3. **Implement at learning level.** One clear, correct implementation per concept. No extra abstraction layers, plugin systems, generic frameworks, retry/backoff machinery, job queues, multi-tenant scaling, or clever optimizations that exist only to make it production-grade. If a simple version works correctly, use it.
4. **Ask before removing or replacing.** If something in the plan seems redundant, broken by design, or harder than it should be, **stop, explain it to Yash, and wait for his decision.**
5. **Do not add features that are not in the plan.** If you think something is missing, mention it in your phase summary as a suggestion. Do not build it.
6. **Code style.** Simple, readable code. Small functions and components with clear names. Type hints in Python, TypeScript types in the frontend. Short docstrings only where they add real information. No excessive comments, no Javadoc-style comment blocks, no commented-out code.
7. **Use libraries for plumbing, write the concepts yourself.** FastAPI, Postgres, LangGraph, langmem, Composio, the MCP client, LangSmith and Next.js handle infrastructure. The agent concepts (planning, routing, evidence handling, citations, memory logic, guardrail logic) are Yash's own readable code, because those are what he will be asked about.
8. **The home page design is fixed.** The existing home page in `frontend/` must look exactly the same. Only fix bugs, wire up its buttons, and integrate it. Never restyle it.

## How to work

- Work **one phase at a time**, in the order given in the plan (Section 12). Do not start the next phase until Yash says so.
- At the start of a phase, present your plan for it and wait for approval before changing files.
- At the end of each phase: run the tests, then give Yash a short summary covering what was built, what changed, how to try it (commands), any decisions you made, any suggestions, and a suggested commit message.
- **Never run `git commit` or `git push`.** Yash does all commits himself.
- Read existing code before changing it.
- Verify library and service APIs against the installed versions and current docs (LangGraph, langmem, Composio, the MCP Python SDK, LangSmith, Next.js). Do not rely on memory for signatures. The plan (Section 14) lists what to check.
- Keep dependencies minimal. When adding one, say why in the phase summary.
- Secrets only in `.env` files. Never commit keys.
- When the plan and this file seem to conflict, follow this file and point out the conflict to Yash.

## Key decisions (do not change without asking Yash)

- **Repository:** `frontend/` (Next.js, TypeScript, Tailwind) and `backend/` (FastAPI, LangGraph, Python 3.12, uv).
- **Authentication:** Clerk for registered users. Layer keeps its UUID user IDs for project ownership and Composio connections. Clerk Billing is not part of the build.
- **RAG-Engine:** called over MCP with the `layer` API key. Layer never reimplements retrieval, reranking or citation verification.
- **Integrations:** Composio with its managed OAuth apps, for Drive, Gmail, Jira and Notion.
- **Data access:** Drive is ingested into RAG-Engine (only when the user clicks Sync). Gmail, Jira and Notion are fetched live at question time.
- **Answers:** streamed (live step updates plus answer text), then replaced by the verified final answer.
- **Human-in-the-loop:** approval before saving any long-term memory fact. Sending a new message skips a pending approval.
- **Demo mode:** "Try the demo" creates a temporary guest with their own copy of a pre-connected demo project. Guests can chat and approve memory, cannot connect or change sources, get 7 questions, and expire after 24 hours.
- **Guardrails in Layer:** auth, per-user rate limit, input validation with injection patterns, spotlighting, PII redaction. No llm-guard models in Layer (RAG-Engine already runs them).
- **Styling:** the home page stays as is (light). The Layer Workspace uses a dark theme: dark gray, not pure black.
- **Tracing:** LangSmith. If its keys are missing, tracing is off and nothing breaks.
- **Deployment:** frontend on Vercel at `layer.yashlalwani.info`, backend on Railway at `api.layer.yashlalwani.info`, RAG-Engine at `rag.yashlalwani.info`.

## Commands (once the project is set up)

```bash
# backend
cd backend
uv sync
docker compose up -d postgres              # local Postgres for Layer
uv run pytest
uv run uvicorn layer_api.main:app --reload --port 8080
uv run python eval/run_eval.py

# frontend
cd frontend
npm install
npm run dev
```

RAG-Engine runs separately from its own repository (locally at `http://localhost:8000`).

Update this section if the actual commands differ.
