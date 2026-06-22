# Marketplace

## Quellen

- `GET /agents` mit Filterparametern:
  - `q` — Volltext (case-insensitive auf `name`/`description`).
  - `skill` — exakter Match gegen `agent_skills.skill`.
  - `domain` — exakter Match.
  - `model` — filtert auf aktuelle `agent_versions.model`.
  - `mine` — nur eigene.
- Default-Sichtbarkeit: alle `public` + eigene.

## Ranking (Phase 2)

Default: `created_at DESC`. Erweiterungspfade:

- Bewertungsdurchschnitt × Anzahl (Bayesian Average).
- Anzahl erfolgreicher Runs (aus `work_runs`).
- Empfehlungen für eingeloggten User (z.B. zuletzt genutzte Skills).

In Phase 1–2 keine Ranking-Magie; erst wenn echte Nutzungsdaten vorliegen.

## UI

Marktplatz unter `/`. Karten via `components/agent-card.tsx`. Filter via einfache
`<form action="/" method="get">` → Server-Side-Render im App-Router.
