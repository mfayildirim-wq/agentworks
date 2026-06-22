"use client";

import { useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { AvatarPicker } from "@/components/avatar-picker";
import { SkillInput } from "@/components/skill-input";

export function CreateAgentForm() {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [domain, setDomain] = useState("");
  const [description, setDescription] = useState("");
  const [skills, setSkills] = useState<string[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [avatar, setAvatar] = useState<string | null>(null);
  const [visibility, setVisibility] = useState("private");
  const [provider, setProvider] = useState("deepseek");
  const [model, setModel] = useState("deepseek-chat");
  const [models, setModels] = useState<{ value: string; label: string; group: string }[]>([]);
  const [price, setPrice] = useState("0");
  const [cvBusy, setCvBusy] = useState(false);

  useEffect(() => {
    fetch("/api/proxy/models", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : []))
      .then((ms: { value: string; label: string; group: string }[]) => setModels(ms))
      .catch(() => {});
  }, []);

  const onCv = async (file: File) => {
    setCvBusy(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch("/api/proxy/agents/extract-profile", { method: "POST", body: fd });
      if (!res.ok) throw new Error(await res.text());
      const p = await res.json();
      if (p.role) setRole(p.role);
      if (p.domain) setDomain(p.domain);
      if (p.summary) setDescription(p.summary);
      if (p.name && !name) setName(p.name);
      if (Array.isArray(p.skills)) {
        setSuggestions(p.skills);
        setSkills((cur) => Array.from(new Set([...cur, ...p.skills])));
      }
    } catch (e) {
      setError("CV-Analyse fehlgeschlagen: " + (e as Error).message);
    } finally {
      setCvBusy(false);
    }
  };

  const submit = () => {
    startTransition(async () => {
      setError(null);
      const payload = {
        name,
        role,
        domain,
        description,
        skills,
        avatar_url: avatar,
        visibility,
        provider,
        model,
        price_per_run: Number(price || 0)
      };
      const res = await fetch("/api/proxy/agents", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        setError(await res.text());
        return;
      }
      const agent = await res.json();
      router.push(`/agents/${agent.id}`);
    });
  };

  return (
    <div className="grid max-w-2xl gap-5">
      <div>
        <label className="text-sm font-medium">Avatar</label>
        <div className="mt-1">
          <AvatarPicker value={avatar} onChange={setAvatar} name={name} />
        </div>
      </div>

      <div className="rounded-md border border-dashed p-4">
        <label className="cursor-pointer text-sm font-medium text-primary underline">
          {cvBusy ? "Analysiere…" : "Lebenslauf / Beraterprofil hochladen (PDF, DOCX, TXT)"}
          <input
            type="file"
            accept=".pdf,.docx,.txt,.md"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && onCv(e.target.files[0])}
          />
        </label>
        <p className="mt-1 text-xs text-muted-foreground">
          Das System erkennt Rolle, Fachgebiet und Fähigkeiten automatisch.
        </p>
      </div>

      <Labeled label="Name">
        <Input value={name} onChange={(e) => setName(e.target.value)} required />
      </Labeled>
      <div className="grid gap-4 sm:grid-cols-2">
        <Labeled label="Rolle">
          <Input value={role} onChange={(e) => setRole(e.target.value)} placeholder="z.B. Softwareentwickler" />
        </Labeled>
        <Labeled label="Fachgebiet">
          <Input value={domain} onChange={(e) => setDomain(e.target.value)} placeholder="z.B. software" />
        </Labeled>
      </div>
      <Labeled label="Beschreibung / Profil">
        <Textarea value={description} onChange={(e) => setDescription(e.target.value)} />
      </Labeled>

      <Labeled label="Fähigkeiten (Skills)">
        <SkillInput value={skills} onChange={setSkills} suggestions={suggestions} />
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
            {models.length === 0 && <option value={model}>{model}</option>}
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
            onChange={(e) => setVisibility(e.target.value)}
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
        <Button type="button" disabled={pending || !name} onClick={submit}>
          {pending ? "Speichere…" : "Agent anlegen"}
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
