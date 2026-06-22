# Logging & Observability

## Strukturierte Logs

`structlog` (siehe `app/core/logging.py`) → JSON-Logs auf stdout. Konfig per
`LOG_LEVEL` (Default `INFO`).

Pflichtfelder: `event` (string), `run_id` / `work_id` / `agent_id` wo zutreffend.

## Pro-Run-Tabellen

| Tabelle | Inhalt |
| --- | --- |
| `messages` | Sichtbare Chat-Nachrichten (Frontend rendert daraus die Run-Ansicht). |
| `logs` | Alle Events (auch nicht-Chat: `tool_call`, `handoff`, `error`, `token_usage`). |

Beide Tabellen sind per `run_id` indexiert.

## SSE-Streaming

`event_bus.publish` schreibt jede `RunEvent` auf Redis-Channel `runs:<run_id>`.
`event_bus.subscribe_stream` (FastAPI `StreamingResponse`) liefert SSE-Frames
an authentifizierte Clients und beendet sich bei `run_completed`/`error`.

## OpenTelemetry

Default no-op. Einschalten:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318 \
OTEL_SERVICE_NAME=agentworks-backend \
uvicorn app.main:app
```

FastAPI-Routen + SQLAlchemy werden via `opentelemetry-instrumentation-*` automatisch
getraced (zukünftige Erweiterung — initial sind die Pakete nur installiert, nicht aktiv).

## Kosten

`work_runs.total_cost` ist der Aggregat-Wert, der aus den Token-Zählungen der
Executors berechnet wird. UI zeigt ihn am Ende des Runs unter „Endergebnis".
