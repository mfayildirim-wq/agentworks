# Architecture

## Überblick

```
              ┌──────────────────────────────┐
              │      Next.js Frontend        │
              │  (App Router, Tailwind,      │
              │   shadcn/ui, NextAuth Google)│
              └──────────────┬───────────────┘
                             │ REST + SSE (JWT von NextAuth)
              ┌──────────────▼───────────────┐
              │       FastAPI Backend        │
              │   Auth · Agents · Works ·    │
              │   Marketplace · Logs · SSE   │
              └─────┬───────────────┬────────┘
                    │ in-process    │ enqueue
                    │               │
        ┌───────────▼──┐    ┌───────▼────────┐
        │ PostgreSQL   │    │     Redis      │
        │ + pgvector   │    │  (Queue + SSE) │
        └──────────────┘    └───────┬────────┘
                                    │ dequeue
                            ┌───────▼────────┐
                            │   Dramatiq     │
                            │   Worker(s)    │
                            │  → AutoGen     │
                            └────────────────┘
```

## Schichten

### Frontend (`frontend/`)

- Next.js 14 App Router, TypeScript strict.
- NextAuth mit Google Provider, JWT-Session.
- API-Client (`lib/api.ts`) hängt automatisch `Authorization: Bearer <id_token>` an.
- shadcn/ui für Komponenten; Tailwind für Styling.

### Backend (`backend/`)

- FastAPI, alle Routen async, SQLAlchemy 2.0 mit `asyncpg`-Treiber.
- Auth-Middleware validiert Google ID-Token via `google-auth`; legt User lazy an.
- Drei Routergruppen: `/auth`, `/agents`, `/works`. SSE unter `/works/{id}/runs/{run_id}/stream`.
- Dramatiq mit Redis-Broker für asynchrone Work-Runs.

### Agent-Runtime (`agent-runtime/`)

- Eigenes Python-Paket, vom Backend importiert.
- Kern-Interface `AgentExecutor` mit Methoden `prepare()`, `run()`, `stream()`.
- Implementierungen: `EchoExecutor` (Phase 0), `AutoGenSingleExecutor` (Phase 1), `AutoGenGroupExecutor` (Phase 2), `AutoGenSwarmExecutor` (Phase 2), `AutoGenGraphFlowExecutor` (Phase 3).
- Callbacks pumpen Messages/Events → Redis Pub/Sub-Channel `runs:{run_id}` → SSE.

### Datenbank

PostgreSQL 16 + pgvector. Schema siehe [`DATABASE_SCHEMA.md`](DATABASE_SCHEMA.md). Migrationen via Alembic.

### Observability

OpenTelemetry-Init im Backend (no-op Default; per ENV auf OTLP-Exporter umstellbar). Strukturiertes Logging über `structlog`. Trace-/Span-Felder in `logs.payload_jsonb`.

## Datenflüsse

### Work erstellen + starten

1. `POST /works` → DB-Eintrag, Kosten-Schätzung zurück.
2. `POST /works/{id}/runs` → Dramatiq-Message `execute_run(run_id)` enqueued.
3. Worker lädt Work + alle `work_agents` + aktuelle `agent_versions`.
4. Worker erzeugt passenden `AgentExecutor`.
5. Executor läuft, pusht jede Message via Callback an `MessageBus`.
6. `MessageBus` schreibt in `messages`/`logs` und published nach Redis-Channel.
7. SSE-Endpoint subscribed Channel + filtert authentifiziert.
8. Bei Abschluss `work_runs.status = completed`.

### Kosten

`tokens_in * model.input_price + tokens_out * model.output_price` pro Message; Aggregat in `work_runs.total_cost`. Modellpreise in `backend/app/core/pricing.py` als Konstanten.
