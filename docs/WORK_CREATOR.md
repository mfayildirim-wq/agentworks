# Work Creator

## Was ist ein Work?

Eine nachvollziehbare Aufgabe mit mindestens einem Agenten, Ziel, Initial-Message, Modus
und Logging aller entstehenden Nachrichten.

## API-Flow

1. `POST /works` — legt `works` + `work_agents` an. Liefert `WorkOut` inkl. `estimated_cost_usd`.
2. `POST /works/{id}/runs` — erstellt `work_runs(status=pending)` und enqueued
   `execute_run(run_id)` an Dramatiq.
3. `GET /works/{id}/runs/{run_id}` — Polling-Endpoint (Phase-1-Fallback).
4. `GET /works/{id}/runs/{run_id}/messages` — alle bisherigen Messages.
5. `GET /works/{id}/runs/{run_id}/stream` — SSE (Phase 2). Closet bei `run_completed`/`error`.

## Modi

| Modus | Min Agenten | UI-Hinweis |
| --- | --- | --- |
| `single` | 1 | Schnelltest, klassischer Assistent. |
| `group` | 2+ | Moderierter Group-Chat (SelectorGroupChat). |
| `swarm` | 2+ | Handoffs zwischen Agenten — Edges via Workflow-Editor. |
| `graph` | 2+ | DAG-Ausführung — Edges im Workflow-Editor; Mode wird beim Speichern auf `graph` gesetzt. |

## Kostenschätzung

`agent_runtime.pricing.cost(model, 2_000, 1_000)` pro Agent, summiert. UI-only — kein Block bei Überschreitung. Harte Grenze: `Work.max_tokens` wird beim Executor noch nicht erzwungen (TODO Phase 4).

## „Work kopieren"

`POST /works/{id}/copy` erzeugt eine neue private Kopie mit Prefix `Copy: `. Praktisch
für öffentliche Works, die man als Vorlage nutzen will.
