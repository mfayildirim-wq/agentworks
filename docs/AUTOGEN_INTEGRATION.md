# AutoGen Integration

## Adapter-Schicht

Das Backend kennt **nur** das eigene Interface in `agent_runtime/executor.py`:

```python
class AgentExecutor(ABC):
    async def run(self, work: WorkSpec, ctx: ExecutorContext) -> ExecutorResult: ...
```

AutoGen wird ausschließlich in `agent_runtime/executors/autogen_*.py` importiert.

## Modi → Executors

| `WorkSpec.mode` | Executor | AutoGen-Baustein |
| --- | --- | --- |
| `single` | `AutoGenSingleExecutor` | `AssistantAgent.on_messages` |
| `group` | `AutoGenGroupExecutor` | `SelectorGroupChat.run_stream` |
| `swarm` | `AutoGenSwarmExecutor` | `Swarm.run_stream` mit `handoffs` |
| `graph` | `AutoGenGraphFlowExecutor` | `GraphFlow` + `DiGraphBuilder` |

Auswahl via `agent_runtime.executors.factory.create_executor(mode)`.

## Modell-Client

`AnthropicChatCompletionClient` aus `autogen-ext[anthropic]`. API-Key kommt aus
`ExecutorContext.api_key` → liest `settings.anthropic_api_key`.

## Events

Jeder Executor pumpt `RunEvent`s an `ctx.on_event`. Diese werden vom Worker in `event_bus`
persistiert (DB) und per Redis-Pub/Sub für SSE veröffentlicht.

Event-Typen:

- `run_started` / `run_completed` / `error`
- `agent_message` (Inhalt, Tokens, Kosten)
- `tool_call` / `tool_result` (Phase 2+)
- `handoff` (Swarm)
- `token_usage` (Aggregat am Ende)

## Kostenberechnung

`agent_runtime/pricing.py` enthält USD/1M-Token-Preise. Pro Message
`cost(model, tokens_in, tokens_out)`; Aggregat in `work_runs.total_cost`.

## Versionsbindung

`AutoGen` ist API-aktiv. Pin in `pyproject.toml`. Beim Update:

1. Versions-Pin lockern, neu installieren.
2. Smoke-Test der vier Executors gegen Echo + ein Live-Modell.
3. Falls Breaking: nur den entsprechenden Adapter anpassen — das Backend bleibt unberührt.
