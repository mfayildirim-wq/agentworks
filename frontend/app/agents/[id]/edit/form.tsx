"use client";

import { useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { AvatarPicker } from "@/components/avatar-picker";
import { SkillInput } from "@/components/skill-input";
import type { Agent } from "@/lib/api";

export function EditAgentForm({ agent }: { agent: Agent }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const [role, setRole] = useState(agent.role);
  const [domain, setDomain] = useState(agent.domain);
  const [description, setDescription] = useState(agent.description);
  const [skills, setSkills] = useState<string[]>(agent.skills);
  const [avatar, setAvatar] = useState<string | null>(agent.avatar_url);
  const [visibility, setVisibility] = useState(agent.visibility);
  const [model, setModel] = useState(agent.model);
  const [provider, setProvider] = useState((agent as { provider?: string }).provider ?? "deepseek");
  const [models, setModels] = useState<{ value: string; label: string; group: string }[]>([]);
  const [price, setPrice] = useState(String(agent.price_per_run));

  useEffect(() => {
    fetch("/api/proxy/models", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : []))
      .then((ms: { value: string; label: string; group: string }[]) => setModels(ms))
      .catch(() => {});
  }, []);

  const submit = () => {
    startTransition(async () => {
      setError(null);
      const payload = {
        role,
        domain,
        description,
        skills,
        avatar_url: avatar,
        visibility,
        model,
        provider,
        price_per_run: Number(price || 0)
      };
      const res = await fetch(`/api/proxy/agents/${agent.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        setError(await res.text());
        return;
      }
      router.push(`/agents/${agent.id}`);
    });
  };

  return (
    <div className="grid max-w-2xl gap-5">
      <Labeled label="Avatar">
        <AvatarPicker value={avatar} onChange={setAvatar} name={agent.name} />
      </Labeled>
      <div className="grid gap-4 sm:grid-cols-2">
        <Labeled label="Rolle">
          <Input value={role} onChange={(e) => setRole(e.target.value)} />
        </Labeled>
        <Labeled label="Fachgebiet">
          <Input value={domain} onChange={(e) => setDomain(e.target.value)} />
        </Labeled>
      </div>
      <Labeled label="Beschreibung / Profil">
        <Textarea value={description} onChange={(e) => setDescription(e.target.value)} />
      </Labeled>
      <Labeled label="Fähigkeiten (Skills)">
        <SkillInput value={skills} onChange={setSkills} />
      </Labeled>
      <div className="grid gap-4 sm:grid-cols-3">
        <Labeled label="Modell">
          <select
            value={model}
            onChange={(e) => {
              const v = e.target.value;
              setModel(v);
              const m = models.find((x) => x.value === v);
              if (m) setProvider(m.group.toLowerCase());
            }}
            className="block h-10 w-full rounded-md border bg-background px-3 text-sm"
          >
            {!models.some((m) => m.value === model) && <option value={model}>{model}</option>}
            {models.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label} ({m.group})
              </option>
            ))}
          </select>
        </Labeled>
        <Labeled label="Preis/Run (USD)">
          <Input type="number" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} />
        </Labeled>
        <Labeled label="Sichtbarkeit">
          <select
            value={visibility}
            onChange={(e) => setVisibility(e.target.value as Agent["visibility"])}
            className="block h-10 w-full rounded-md border bg-background px-3 text-sm"
          >
            <option value="private">privat</option>
            <option value="unlisted">unlisted</option>
            <option value="public">öffentlich</option>
          </select>
        </Labeled>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div>
        <Button type="button" disabled={pending} onClick={submit}>
          {pending ? "Speichere…" : "Speichern"}
        </Button>
      </div>
    </div>
  );
}

function Labeled({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="text-sm font-medium">{label}</label>
      <div className="mt-1">{children}</div>
    </div>
  );
}
