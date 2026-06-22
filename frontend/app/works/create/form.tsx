"use client";

import { useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { Agent } from "@/lib/api";

export function CreateWorkForm({ agents, preselected }: { agents: Agent[]; preselected?: string }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"single" | "group" | "swarm">("single");
  const [selected, setSelected] = useState<string[]>(preselected ? [preselected] : []);

  const visibleAgents = useMemo(() => agents, [agents]);

  function toggle(id: string) {
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  }

  const onSubmit = (formData: FormData) => {
    startTransition(async () => {
      setError(null);
      if (selected.length === 0) {
        setError("Mindestens einen Agenten auswählen.");
        return;
      }
      if (mode === "single" && selected.length !== 1) {
        setError("Single-Mode braucht genau einen Agenten.");
        return;
      }
      const payload = {
        title: formData.get("title"),
        goal: formData.get("goal"),
        expected_outcome: formData.get("expected_outcome"),
        initial_message: formData.get("initial_message") || formData.get("goal"),
        mode,
        visibility: formData.get("visibility") || "private",
        max_turns: Number(formData.get("max_turns") || 12),
        agents: selected.map((id) => ({ agent_id: id }))
      };
      const res = await fetch("/api/proxy/works", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        setError(await res.text());
        return;
      }
      const work = await res.json();
      router.push(`/works/${work.id}`);
    });
  };

  return (
    <form action={onSubmit} className="grid gap-6 md:grid-cols-[2fr,1fr]">
      <div className="space-y-4">
        <Field label="Titel" name="title" required />
        <Field label="Ziel" name="goal" textarea required />
        <Field label="Erwartetes Ergebnis" name="expected_outcome" textarea />
        <Field label="Initiale Nachricht (sonst = Ziel)" name="initial_message" textarea />
        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <label className="text-sm font-medium">Modus</label>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as typeof mode)}
              className="mt-1 block h-10 w-full rounded-md border bg-background px-3 text-sm"
            >
              <option value="single">single (1 Agent)</option>
              <option value="group">group (SelectorGroupChat)</option>
              <option value="swarm">swarm (Handoffs)</option>
            </select>
          </div>
          <div>
            <label className="text-sm font-medium">Sichtbarkeit</label>
            <select
              name="visibility"
              className="mt-1 block h-10 w-full rounded-md border bg-background px-3 text-sm"
            >
              <option value="private">privat</option>
              <option value="unlisted">unlisted</option>
              <option value="public">öffentlich</option>
            </select>
          </div>
          <Field label="Max Turns" name="max_turns" type="number" defaultValue="12" />
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" disabled={pending}>
          {pending ? "Lege an…" : "Work erstellen"}
        </Button>
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold">Agenten ({selected.length})</h3>
        <div className="max-h-[600px] space-y-2 overflow-y-auto">
          {visibleAgents.map((a) => (
            <label
              key={a.id}
              className={
                "flex cursor-pointer items-start gap-2 rounded border p-2 text-sm " +
                (selected.includes(a.id) ? "border-primary bg-primary/5" : "")
              }
            >
              <input
                type="checkbox"
                checked={selected.includes(a.id)}
                onChange={() => toggle(a.id)}
                className="mt-1"
              />
              <div>
                <div className="font-medium">{a.name}</div>
                <div className="text-xs text-muted-foreground">{a.role || a.domain || a.model}</div>
              </div>
            </label>
          ))}
        </div>
      </div>
    </form>
  );
}

function Field({
  label,
  textarea,
  ...props
}: { label: string; textarea?: boolean } & React.InputHTMLAttributes<HTMLInputElement> &
  React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <div>
      <label className="text-sm font-medium">{label}</label>
      <div className="mt-1">{textarea ? <Textarea {...props} /> : <Input {...props} />}</div>
    </div>
  );
}
