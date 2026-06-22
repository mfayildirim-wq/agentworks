# Workflow Engine

## Datenmodell

Nicht eigene `workflow_nodes`/`workflow_edges`-Tabellen (zu schwergewichtig für eine
1:1-Beziehung), sondern:

- `works.workflow_graph` jsonb: `{nodes: [{id, x, y}], edges: [{source, target}]}`
- `work_agents.handoff_targets` jsonb (Array von Agent-IDs als Strings)

Beim Speichern via `PUT /works/{id}/workflow` werden beide Felder konsistent gehalten:
Edges → `handoff_targets` projiziert; `mode = graph`.

## Editor (Frontend)

`/workflows/[id]` rendert React Flow. Agenten = Nodes, Edges per Drag-Connect. Save
schreibt zurück, fitView ist Default.

## Runtime

Mode `graph` triggert `AutoGenGraphFlowExecutor` (`autogen_agentchat.teams.GraphFlow` +
`DiGraphBuilder`). Knotenreihenfolge ergibt sich aus den Edges.

## Validierung (geplant, Phase 3.1)

- Pflicht: mindestens ein Start-Node (kein eingehender Edge).
- Optional: Ende (kein ausgehender Edge) — sonst läuft GraphFlow bis `max_turns`.
- Keine Self-Loops in v1. Schleifen erst später, wenn explizit gewünscht.
