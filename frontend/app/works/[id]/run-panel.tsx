"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatCost } from "@/lib/utils";

type RunStatus = "pending" | "running" | "completed" | "failed";

interface Run {
  id: string;
  work_id: string;
  status: RunStatus;
  total_tokens_in: number;
  total_tokens_out: number;
  total_cost: number;
  result: {
    final_message?: string;
    artifact?: string;
    output_type?: string;
    stop_reason?: string;
    iterations?: number;
  } | null;
  error: string | null;
}

interface StreamEvent {
  type: string;
  agent_name?: string;
  content?: string;
  tokens_in?: number;
  tokens_out?: number;
  cost_usd?: number;
}

interface Message {
  id: string;
  agent_name: string;
  content: string;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
}

export function RunPanel({ workId, initialMode }: { workId: string; initialMode: string }) {
  const [run, setRun] = useState<Run | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [starting, setStarting] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);

  const closeStream = useCallback(() => {
    sourceRef.current?.close();
    sourceRef.current = null;
  }, []);

  useEffect(() => () => closeStream(), [closeStream]);

  async function startRun() {
    setStarting(true);
    setMessages([]);
    const res = await fetch(`/api/proxy/works/${workId}/runs`, { method: "POST" });
    setStarting(false);
    if (!res.ok) return;
    const newRun: Run = await res.json();
    setRun(newRun);
    listen(newRun.id);
  }

  function listen(runId: string) {
    closeStream();
    const url = `/api/proxy/works/${workId}/runs/${runId}/stream`;
    const es = new EventSource(url);
    sourceRef.current = es;
    es.onmessage = (ev) => {
      try {
        const data: StreamEvent = JSON.parse(ev.data);
        if (data.type === "agent_message" && data.content) {
          setMessages((m) => [
            ...m,
            {
              id: `${m.length}`,
              agent_name: data.agent_name ?? "agent",
              content: data.content!,
              tokens_in: data.tokens_in ?? 0,
              tokens_out: data.tokens_out ?? 0,
              cost_usd: data.cost_usd ?? 0
            }
          ]);
        }
        if (data.type === "run_completed" || data.type === "error") {
          es.close();
          refreshRun(runId);
        }
      } catch {}
    };
    es.onerror = () => {
      es.close();
      pollUntilDone(runId);
    };
  }

  async function refreshRun(runId: string) {
    const r = await fetch(`/api/proxy/works/${workId}/runs/${runId}`, { cache: "no-store" });
    if (r.ok) setRun(await r.json());
    const m = await fetch(`/api/proxy/works/${workId}/runs/${runId}/messages`, { cache: "no-store" });
    if (m.ok) {
      const rows = await m.json();
      setMessages(
        rows.map((x: Message) => ({
          id: x.id,
          agent_name: x.agent_name,
          content: x.content,
          tokens_in: x.tokens_in,
          tokens_out: x.tokens_out,
          cost_usd: x.cost_usd
        }))
      );
    }
  }

  async function pollUntilDone(runId: string) {
    for (let i = 0; i < 120; i++) {
      await new Promise((r) => setTimeout(r, 2000));
      const r = await fetch(`/api/proxy/works/${workId}/runs/${runId}`, { cache: "no-store" });
      if (r.ok) {
        const data: Run = await r.json();
        setRun(data);
        if (data.status === "completed" || data.status === "failed") {
          refreshRun(runId);
          return;
        }
      }
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Ausführung</CardTitle>
        <div className="flex items-center gap-2">
          {run && <Badge>{run.status}</Badge>}
          <Button onClick={startRun} disabled={starting || run?.status === "running"}>
            {run?.status === "running" ? "läuft…" : starting ? "starte…" : "Run starten"}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground">Modus: {initialMode}</p>

        {messages.length === 0 && (
          <p className="text-sm text-muted-foreground">Noch keine Nachrichten.</p>
        )}
        <div className="space-y-2">
          {messages.map((m) => (
            <div key={m.id} className="rounded border p-3">
              <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
                <span className="font-medium text-foreground">{m.agent_name}</span>
                <span>
                  in {m.tokens_in} · out {m.tokens_out} · {formatCost(m.cost_usd)}
                </span>
              </div>
              <pre className="whitespace-pre-wrap text-sm">{m.content}</pre>
            </div>
          ))}
        </div>

        {run && run.status === "completed" && (
          <div className="rounded border border-green-500 bg-green-50 p-3 text-sm dark:bg-green-900/20">
            <div className="mb-2 font-semibold">Endergebnis</div>
            {run.result?.artifact && run.result.output_type === "html" ? (
              <div className="space-y-2">
                <div className="text-xs text-muted-foreground">
                  Artefakt · {run.result.iterations ?? 0} Iteration(en) · Stop:{" "}
                  {run.result.stop_reason ?? "—"}
                </div>
                <iframe
                  title="Artefakt-Vorschau"
                  srcDoc={run.result.artifact}
                  className="h-96 w-full rounded border bg-white"
                  sandbox=""
                />
              </div>
            ) : (
              <pre className="whitespace-pre-wrap">
                {run.result?.artifact ?? run.result?.final_message ?? ""}
              </pre>
            )}
            <div className="mt-2 text-xs text-muted-foreground">
              Tokens: {run.total_tokens_in} / {run.total_tokens_out} · Kosten {formatCost(run.total_cost)}
            </div>
          </div>
        )}
        {run && run.status === "failed" && (
          <div className="rounded border border-destructive bg-destructive/10 p-3 text-sm">
            Fehler: {run.error}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
