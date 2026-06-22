# Security

## Auth

Single-Source-of-Truth: Google ID-Token. NextAuth signiert die Session, gibt das
ID-Token an Server-Components/Proxy weiter; das Backend verifiziert per
`google-auth` (Audience = `GOOGLE_CLIENT_ID`, falls gesetzt).

`AUTH_DISABLED_FOR_TESTS=1` aktiviert einen festen `test-user` (nur lokal/CI).

## Mandantentrennung

- Jede private Ressource hat `owner_id`.
- Lese-/Schreib-Zugriff prüft entweder `owner_id == current_user.id` ODER
  `visibility == public`.
- Zentrale Stellen: `services/agents.py`, `services/works.py`, `api/ratings.py`,
  `api/workflows.py`, `api/cron_jobs.py`, `api/rag.py`.

Vor jedem neuen Endpoint: Sichtbarkeits-Check explizit als ersten Schritt im Handler.

## Tool-Use

Phase 1 ohne Tools. Ab Phase 2 nur kuratierte Whitelist (`agent_versions.tools` ⊆ erlaubte
Tool-Namen). Niemals freie Code-Ausführung freischalten.

## SSE

Verbinden mit gültiger Session erforderlich. Channel-Subscription erfolgt server-side,
Client erhält reine Event-Daten — keine direkten Redis-Credentials.

## Data Retention

Aktuell keine automatische Löschung. Bei Wachstum: TTL/Partitionierung für `messages`/`logs`
(z.B. 90 Tage Default).

## DSGVO / Datenexport

- `users.email` ist personenbezogen.
- `messages.content` kann Nutzerdaten enthalten.
- Export/Erase-API: außerhalb dieses Plans (Phase 4 zusammen mit Billing).
