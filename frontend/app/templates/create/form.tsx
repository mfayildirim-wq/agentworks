"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { Agent, TemplateInputField } from "@/lib/api";

// uid: stabiler React-Key pro Zeile, damit Entfernen aus der Mitte nicht Fokus/Werte
// der nachfolgenden Felder verliert. Wird vor dem Absenden entfernt.
type FieldDraft = TemplateInputField & { uid: string };

// Eigene „/"-Funktion (def:) eines Templates.
type CommandDraft = { uid: string; key: string; label: string; instruction: string; mode: string };

const COMMAND_MODES = [
  ["hinzufuegen", "Neuer Tab"],
  ["liste", "Liste"],
  ["oben", "Oben anfügen"],
  ["unten", "Unten anfügen"],
  ["ueberarbeiten", "Überarbeiten"],
  ["ueberschreiben", "Überschreiben"]
] as const;

export function CreateTemplateForm({ agents }: { agents: Agent[] }) {
  const router = useRouter();
  const noAgents = agents.length === 0;
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("");
  const [visibility, setVisibility] = useState("public");
  const [outputType, setOutputType] = useState("html");
  const [defaultOutputMode, setDefaultOutputMode] = useState("hinzufuegen");
  const [agentId, setAgentId] = useState(agents[0]?.id ?? "");
  const [promptTemplate, setPromptTemplate] = useState("");
  const [fields, setFields] = useState<FieldDraft[]>([]);
  const [commands, setCommands] = useState<CommandDraft[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const uidCounter = useRef(0);

  function addField() {
    const uid = `f${uidCounter.current++}`;
    setFields((f) => [
      ...f,
      { uid, key: "", label: "", type: "string", required: false, options: null }
    ]);
  }
  function updateField(uid: string, patch: Partial<FieldDraft>) {
    setFields((f) => f.map((x) => (x.uid === uid ? { ...x, ...patch } : x)));
  }
  function removeField(uid: string) {
    setFields((f) => f.filter((x) => x.uid !== uid));
  }

  function addCommand() {
    const uid = `c${uidCounter.current++}`;
    setCommands((c) => [...c, { uid, key: "", label: "", instruction: "", mode: "hinzufuegen" }]);
  }
  function updateCommand(uid: string, patch: Partial<CommandDraft>) {
    setCommands((c) => c.map((x) => (x.uid === uid ? { ...x, ...patch } : x)));
  }
  function removeCommand(uid: string) {
    setCommands((c) => c.filter((x) => x.uid !== uid));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const inputSchema: TemplateInputField[] = fields.map((f) => ({
        key: f.key,
        label: f.label,
        type: f.type,
        required: f.required,
        options: f.type === "select" ? f.options ?? [] : null
      }));
      const body = {
        title,
        description,
        category,
        visibility,
        output_type: outputType,
        mode: "single",
        input_schema: inputSchema,
        config: {
          agent_ids: agentId ? [agentId] : [],
          prompt_template: promptTemplate,
          default_output_mode: defaultOutputMode,
          commands: commands
            .filter((c) => c.key.trim() && c.label.trim() && c.instruction.trim())
            .map((c) => ({
              key: c.key.trim(),
              label: c.label.trim(),
              instruction: c.instruction.trim(),
              mode: c.mode
            }))
        }
      };
      const res = await fetch(`/api/proxy/templates`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      if (!res.ok) {
        setError((await res.text()) || "Fehler");
        return;
      }
      const data = (await res.json()) as { id: string };
      router.push(`/templates/${data.id}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="max-w-2xl space-y-4">
      <input
        className="w-full rounded border px-2 py-1"
        placeholder="Titel (z.B. Reiseplaner)"
        required
        value={title}
        onChange={(e) => setTitle(e.target.value)}
      />
      <textarea
        className="w-full rounded border px-2 py-1"
        placeholder="Beschreibung"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />
      <div className="grid grid-cols-2 gap-3">
        <input
          className="rounded border px-2 py-1"
          placeholder="Kategorie (z.B. travel)"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        />
        <select
          className="rounded border px-2 py-1"
          value={visibility}
          onChange={(e) => setVisibility(e.target.value)}
        >
          <option value="public">öffentlich</option>
          <option value="unlisted">per Link</option>
          <option value="private">privat</option>
        </select>
        <select
          className="rounded border px-2 py-1"
          value={outputType}
          onChange={(e) => setOutputType(e.target.value)}
        >
          <option value="html">HTML</option>
          <option value="markdown">Markdown</option>
          <option value="json">JSON</option>
        </select>
        <select
          className="rounded border px-2 py-1"
          value={agentId}
          onChange={(e) => setAgentId(e.target.value)}
        >
          {agents.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
      </div>
      <textarea
        className="h-28 w-full rounded border px-2 py-1 font-mono text-sm"
        placeholder="Prompt-Template, z.B. Plane eine Reise nach {{destination}} für {{days}} Tage."
        value={promptTemplate}
        onChange={(e) => setPromptTemplate(e.target.value)}
      />

      <div>
        <label className="mb-1 block text-sm font-medium">Ausgabe pro Lauf</label>
        <select
          className="w-full rounded border px-2 py-1"
          value={defaultOutputMode}
          onChange={(e) => setDefaultOutputMode(e.target.value)}
        >
          <option value="hinzufuegen">Neuer Tab pro Lauf (Standard)</option>
          <option value="liste">Liste — verlinktes Verzeichnis, neue oben (z.B. Rezepte)</option>
          <option value="oben">Oben anfügen (neuer Abschnitt oben)</option>
          <option value="unten">Unten anfügen (neuer Abschnitt unten)</option>
          <option value="ueberarbeiten">Gleiches Ergebnis überarbeiten (z.B. Reiseplaner)</option>
          <option value="ueberschreiben">Immer überschreiben</option>
        </select>
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <span className="font-medium">Eingabefelder</span>
          <button type="button" onClick={addField} className="text-sm text-blue-600">
            + Feld
          </button>
        </div>
        {fields.map((f) => (
          <div key={f.uid} className="mb-2">
            <div className="grid grid-cols-12 gap-2">
              <input
                className="col-span-3 rounded border px-2 py-1"
                placeholder="key"
                value={f.key}
                onChange={(e) => updateField(f.uid, { key: e.target.value })}
              />
              <input
                className="col-span-4 rounded border px-2 py-1"
                placeholder="Label"
                value={f.label}
                onChange={(e) => updateField(f.uid, { label: e.target.value })}
              />
              <select
                className="col-span-2 rounded border px-2 py-1"
                value={f.type}
                onChange={(e) =>
                  updateField(f.uid, { type: e.target.value as TemplateInputField["type"] })
                }
              >
                <option value="string">Text</option>
                <option value="number">Zahl</option>
                <option value="select">Auswahl</option>
                <option value="boolean">Ja/Nein</option>
              </select>
              <label className="col-span-2 flex items-center gap-1 text-sm">
                <input
                  type="checkbox"
                  checked={f.required}
                  onChange={(e) => updateField(f.uid, { required: e.target.checked })}
                />
                Pflicht
              </label>
              <button
                type="button"
                onClick={() => removeField(f.uid)}
                className="col-span-1 text-red-500"
              >
                ✕
              </button>
            </div>
            {f.type === "select" && (
              <input
                className="mt-1 w-full rounded border px-2 py-1 text-sm"
                placeholder="Optionen, kommagetrennt (z.B. entspannt, aktiv, kulturell)"
                value={(f.options ?? []).join(", ")}
                onChange={(e) =>
                  updateField(f.uid, {
                    options: e.target.value
                      .split(",")
                      .map((o) => o.trim())
                      .filter(Boolean)
                  })
                }
              />
            )}
          </div>
        ))}
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <span className="font-medium">Eigene Funktionen (def:)</span>
          <button type="button" onClick={addCommand} className="text-sm text-blue-600">
            + Funktion
          </button>
        </div>
        {commands.map((c) => (
          <div key={c.uid} className="mb-3 space-y-2 rounded border p-2">
            <div className="grid grid-cols-12 gap-2">
              <input
                className="col-span-4 rounded border px-2 py-1"
                placeholder="z.B. neuesziel"
                value={c.key}
                onChange={(e) => updateCommand(c.uid, { key: e.target.value })}
              />
              <input
                className="col-span-5 rounded border px-2 py-1"
                placeholder="Label (Menütext)"
                value={c.label}
                onChange={(e) => updateCommand(c.uid, { label: e.target.value })}
              />
              <select
                className="col-span-2 rounded border px-2 py-1"
                value={c.mode}
                onChange={(e) => updateCommand(c.uid, { mode: e.target.value })}
              >
                {COMMAND_MODES.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => removeCommand(c.uid)}
                className="col-span-1 text-red-500"
                title="Entfernen"
              >
                ✕
              </button>
            </div>
            <textarea
              className="h-16 w-full rounded border px-2 py-1 text-sm"
              placeholder="Anweisung an den Agenten (Platzhalter {input} optional)"
              value={c.instruction}
              onChange={(e) => updateCommand(c.uid, { instruction: e.target.value })}
            />
          </div>
        ))}
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {noAgents && (
        <p className="text-sm text-amber-600">
          Du hast noch keinen Agenten. Lege zuerst einen Agenten an, bevor du ein Template
          erstellst.
        </p>
      )}
      <button
        type="submit"
        disabled={busy || noAgents}
        className="rounded bg-black px-4 py-2 text-sm text-white disabled:opacity-50"
      >
        {busy ? "Speichere…" : "Template anlegen"}
      </button>
    </form>
  );
}
