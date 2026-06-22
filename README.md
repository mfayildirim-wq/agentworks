# AgentWorks

AgentWorks is a self‑hostable platform for **AI agents as living web apps**. A user
picks an *agent template* (a system prompt + model + HTML output design), creates an
*instance* of it, and works with that instance in a chat while a living HTML result
("canvas") is generated next to the conversation. Templates can be shared on a built‑in
marketplace; usage is billed per LLM call from a wallet.

It is bilingual (English / German, switchable per user) and ships ready to run with
Docker Compose.

---

## Core concepts

- **Agent template** – a reusable definition: system prompt (what the agent does),
  model, HTML output design, category, optional custom `/` commands and scheduled
  tasks. Visibility: `private`, `draft`, `friends` (any user) or `public` / `unlisted`
  (admin‑approved).
- **Instance** – a dialog agent created from a template. Left: chat. Right: the living
  HTML result, updated as you talk. Outputs can be placed as a new tab, a linked list,
  appended sections, or by overwriting (configurable per template and per run).
- **Marketplace** – browse public templates, search, filter by category, rate.
- **Master page** – a per‑user dashboard of all instance results (view‑only or edit),
  publicly shareable under `/m/<user-id>` (only public/unlisted instances are shown).
- **Wallet & billing** – each run is charged LLM cost × 1.30 (25 % platform margin +
  5 % credited to the template creator). New users get a small welcome credit. The
  **system admin** (first user to log in) can grant credit to any user without payment.
- **Scheduled tasks** – an instance can run on a schedule (hourly/daily/weekly) and
  notify via email/Telegram.

## Architecture

| Path | What |
|------|------|
| `backend/` | FastAPI + SQLAlchemy (async) + Alembic + Postgres (pgvector). API, services, DB models, migrations, template seeds. Background jobs via Dramatiq. |
| `agent-runtime/` | The agent execution layer (AutoGen‑based model clients, goal/loop executors). |
| `frontend/` | Next.js 14 + React + Tailwind. Marketplace, master page, instance work‑view, profile/admin, i18n. |
| `infra/` | Docker Compose (prod + dev), nginx‑proxy vhost config, SearXNG, `.env.example`. |
| `docs/` | Architecture & subsystem notes. |
| `scripts/` | Helper scripts. |

## Setup on a fresh server

Prerequisites: Docker + Docker Compose.

```bash
# 1) Configure environment (placeholders → real values)
cp infra/.env.example infra/.env
#    Generate the two required secrets:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # → AGENT_SECRET_KEY
openssl rand -hex 32                                                                          # → NEXTAUTH_SECRET
#    Fill in at least: POSTGRES_*, AGENT_SECRET_KEY, NEXTAUTH_SECRET, and one LLM key
#    (ANTHROPIC_API_KEY / OPENAI_API_KEY / DEEPSEEK_API_KEY). Google OAuth is needed for login.

# 2) Start everything (Alembic migrations run automatically on backend start)
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env up -d --build

# 3) Log in once via the web UI — the FIRST user becomes the system admin.

# 4) Seed the public agent templates (English) — owner = system admin:
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env exec backend \
  python -m scripts.seed_alltag_templates
#    Optional extra templates:
#    python -m scripts.seed_github_mcp | seed_gmail_template | seed_google_calendar_template |
#    seed_website_builder_template | seed_wordpress_template | seed_mcp_demo_template
```

No instances or user accounts ship with the repo — the database schema is created by the
Alembic migrations, and only the (English) agent templates are seeded.

For local development there is `infra/docker-compose.yml`. Backend tests run with
`pytest` (against an isolated `*_test` database); the frontend builds with `npm run build`.

## Run without Docker

Docker Compose is the recommended path, but every component is a plain process and can
run on bare metal. You need to provide the same services yourself:

**Prerequisites**
- PostgreSQL **with the `pgvector` extension** (run once: `CREATE EXTENSION vector;`)
- Redis
- Python 3.12+, Node.js 20+
- An Ollama server only if you want local models (optional)

**Backend** (`backend/`)
```bash
python -m venv .venv && . .venv/bin/activate
pip install -e .                        # installs from pyproject.toml
export DATABASE_URL="postgresql+asyncpg://USER:PASS@localhost:5432/agentworks"
export REDIS_URL="redis://localhost:6379/0"
export AGENT_SECRET_KEY="$(python -c 'from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())')"
export ANTHROPIC_API_KEY="sk-ant-..."   # or OPENAI_/DEEPSEEK_ key
alembic upgrade head                    # create/upgrade the schema
uvicorn app.main:app --host 0.0.0.0 --port 8000
# In two more terminals (same env):
dramatiq app.workers                    # background jobs (runs, scheduling)
python -m app.cron_runner                # scheduler tick loop
```

**Frontend** (`frontend/`)
```bash
npm install
export NEXTAUTH_SECRET="$(openssl rand -hex 32)"
export NEXTAUTH_URL="http://localhost:3000"
export BACKEND_URL="http://localhost:8000"      # where the API runs
# Google OAuth env (GOOGLE_CLIENT_ID/SECRET) is required for login.
npm run build && npm start                      # or: npm run dev
```

**Seed templates** (after logging in once → first user becomes system admin):
```bash
cd backend && python -m scripts.seed_alltag_templates
```

All configuration is read from environment variables (see `backend/app/core/settings.py`
and `infra/.env.example`); there is no hard dependency on Docker.

## For AI agents / LLMs

- The product domain lives in `backend/app/services/` (templates, artifacts = instances,
  billing, roles, output placement, canvas rendering) and `backend/app/api/`.
- An **instance** is an `Artifact`; its rendered result is the current `ArtifactVersion`.
- The agent run loop is in `agent-runtime/`; model clients are selected by the model name.
- UI strings are translated via `frontend/lib/i18n/` (`dict.ts` + `useI18n`).

## License

Apache License 2.0 — see [LICENSE](./LICENSE).
