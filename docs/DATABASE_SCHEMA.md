# Database Schema

Postgres 16 + pgvector. Async via `asyncpg`. Migrations via Alembic (`backend/alembic/versions/`).

## Kerntabellen

```
users (id, google_sub*, email*, name, avatar_url, created_at)

agents (id, owner_id→users, name, description, role, domain, avatar_url,
        visibility, price_per_run, current_version_id→agent_versions, created_at, updated_at)

agent_versions (id, agent_id→agents, version, system_prompt, model, temperature,
                tools jsonb, config jsonb, created_at)

agent_skills (id, agent_id→agents, skill)  UNIQUE(agent_id, skill)

works (id, owner_id→users, title, goal, expected_outcome, initial_message,
       mode, visibility, max_turns, max_tokens, workflow_graph jsonb,
       created_at, updated_at)

work_agents (id, work_id→works, agent_id→agents, agent_version_id→agent_versions,
             role_in_work, handoff_targets jsonb[str], order_idx)
             UNIQUE(work_id, agent_id)

work_runs (id, work_id→works, status, started_at, finished_at,
           total_tokens_in, total_tokens_out, total_cost, result jsonb, error)

messages (id, run_id→work_runs, agent_id→agents NULLABLE, agent_name, role,
          content, tokens_in, tokens_out, cost_usd, ts)

logs (id, run_id→work_runs, level, type, payload jsonb, ts)

ratings (id, agent_id→agents, user_id→users, stars, comment, created_at)
        UNIQUE(agent_id, user_id)
```

## Phase-3-Tabellen

```
rag_documents (id, agent_id→agents, title, chunk, embedding vector(1024), created_at)

memory_entries (id, agent_id→agents, user_id→users, key, value, updated_at)

cron_jobs (id, owner_id→users, work_id→works, cron_expr, enabled,
           last_run_at, max_cost_usd, created_at)
```

## Konventionen

- UUIDs überall als Primärschlüssel, `gen_random_uuid()` via `uuid_generate_v4()` / SQLAlchemy default.
- Zeitstempel `timestamptz`, server default `now()`.
- Enums Postgres-nativ (`visibility`, `run_status`, `run_mode`).
- Cascade-Delete für owner_id-/parent-Beziehungen, damit Lösch-Flows einfach bleiben.
- JSONB für strukturierte, aber querbare Daten (`tools`, `handoff_targets`, `workflow_graph`, `logs.payload`).
- pgvector für Embeddings; Dim 1024 (Voyage-3 Default). Fallback `JSON`, falls Extension fehlt.

## Migrations

Initialer Sprung: `0001_initial.py` legt alles an, inkl. `vector(1024)`-Spalte und Enums.
Künftige Spaltenänderungen als separate Revisionen — niemals 0001 editieren.
