# Agent Design

Ein **Agent** ist eine versionierte Konfiguration einer digitalen Arbeitskraft.

## Felder (Agent)

| Feld | Typ | Bedeutung |
| --- | --- | --- |
| `name` | string | Marketplace-Anzeigename. |
| `description` | text | Kurzprofil (Marketplace-Karte, Profilseite). |
| `role` | string | Funktion (z.B. „Research Analyst"). |
| `domain` | string | Fachgebiet als Filter-Tag. |
| `visibility` | enum | `private` · `unlisted` · `public`. |
| `price_per_run` | float | UI-Anzeige; keine echte Buchung in Phase 1–3. |
| `current_version_id` | uuid | Zeigt auf eine `agent_versions`-Zeile. |

## Felder (AgentVersion)

| Feld | Typ | Bedeutung |
| --- | --- | --- |
| `version` | int | Aufsteigende Versionsnummer pro Agent. |
| `system_prompt` | text | Vollständiger System-Prompt. |
| `model` | string | Anthropic-Modell-ID (z.B. `claude-sonnet-4-6`). |
| `temperature` | float | 0…2. |
| `tools` | jsonb | Whitelist von Tool-Namen (Phase 2). |
| `config` | jsonb | Reserve für künftige Felder. |

Edit am Agenten → neue Version. So bleibt jede frühere Work-Ausführung rekonstruierbar.

## Skills

`agent_skills(agent_id, skill)` — viele-zu-viele-Tags, dienen als Filter im Marketplace.

## Sichtbarkeit

- `private`: nur Owner.
- `unlisted`: per Link erreichbar, nicht im Marketplace.
- `public`: im Marketplace + öffentliche Works.

Auth-Check zentral in `app/services/agents.py`. Niemals direkt aus der Datenbank lesen, ohne den Filter zu durchlaufen.

## Beispiel: Business-Ideen-Agent

```json
{
  "name": "Business-Ideen-Agent",
  "domain": "business",
  "role": "Ideengeber",
  "system_prompt": "Du erzeugst 3 konkrete Geschäftsideen mit Zielgruppe, Pain-Point und MVP-Pfad.",
  "model": "claude-sonnet-4-6",
  "skills": ["ideation", "business", "strategy"],
  "visibility": "public",
  "price_per_run": 0.5
}
```
