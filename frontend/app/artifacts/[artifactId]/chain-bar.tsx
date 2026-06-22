"use client";

import { useRef, useState } from "react";
import type { ArtifactView } from "@/lib/api";

type ListItem = { id: string; title: string };

/** Prefix-Helfer: zeigt nur Emoji-Avatare ("emoji:🤖") inline, sonst nichts (v1). */
function nodeLabel(n: { title: string; image_url?: string | null }): string {
  const img = n.image_url || "";
  if (img.startsWith("emoji:")) return `${img.slice("emoji:".length)} ${n.title}`;
  return n.title;
}

/**
 * Kette-Leiste: Brotkrümel der Kette (A → B → C), Auswahl des nächsten Schritts,
 * "Jetzt weiterleiten →" und Auto-Häkchen. Nur für den Eigentümer sichtbar.
 */
export function ChainBar({
  view,
  artifactId,
  onChanged
}: {
  view: ArtifactView;
  artifactId: string;
  onChanged: (patch: Partial<ArtifactView>) => void;
}) {
  const mounted = useRef(true);
  const [editing, setEditing] = useState(false);
  const [items, setItems] = useState<ListItem[] | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [err, setErr] = useState<string | null>(null);
  const [forwarded, setForwarded] = useState(false);

  const path = view.chain_path && view.chain_path.length > 0
    ? view.chain_path
    : [{ id: artifactId, title: view.title, image_url: view.image_url, is_self: true }];

  async function toggleEdit() {
    setErr(null);
    const next = !editing;
    setEditing(next);
    if (next && items === null) {
      const res = await fetch("/api/proxy/artifacts", { cache: "no-store" });
      if (res.ok && mounted.current) {
        const all = (await res.json()) as ListItem[];
        setItems(all.filter((i) => i.id !== artifactId));
      }
    }
  }

  async function setNext() {
    if (!selected) return;
    setErr(null);
    const res = await fetch(`/api/proxy/artifacts/${artifactId}/chain`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ next_artifact_id: selected, auto: view.chain_auto ?? false })
    });
    if (res.ok) {
      location.reload();
    } else if (res.status === 400) {
      const txt = (await res.text()).trim();
      setErr(txt || "Das ergäbe eine Schleife (Zyklus) – nicht möglich.");
    } else {
      setErr("Setzen fehlgeschlagen.");
    }
  }

  async function removeNext() {
    setErr(null);
    const res = await fetch(`/api/proxy/artifacts/${artifactId}/chain`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ next_artifact_id: null, auto: false })
    });
    if (res.ok) location.reload();
    else setErr("Entfernen fehlgeschlagen.");
  }

  async function forward() {
    setErr(null);
    const res = await fetch(`/api/proxy/artifacts/${artifactId}/forward`, { method: "POST" });
    if (res.ok) {
      if (mounted.current) {
        setForwarded(true);
        setTimeout(() => mounted.current && setForwarded(false), 3000);
      }
    } else {
      setErr((await res.text()).trim() || "Weiterleiten fehlgeschlagen.");
    }
  }

  async function toggleAuto(checked: boolean) {
    setErr(null);
    const res = await fetch(`/api/proxy/artifacts/${artifactId}/chain`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ next_artifact_id: view.chain_next_id, auto: checked })
    });
    if (res.ok && mounted.current) onChanged({ chain_auto: checked });
    else if (mounted.current) setErr("Speichern fehlgeschlagen.");
  }

  return (
    <div className="rounded-lg border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold">Kette</span>
        <span className="flex flex-wrap items-center gap-1 text-sm">
          {path.map((n, i) => (
            <span key={n.id} className="flex items-center gap-1">
              {i > 0 && <span className="text-gray-400">→</span>}
              {n.is_self ? (
                <span className="font-bold">{nodeLabel(n)}</span>
              ) : (
                <a href={`/artifacts/${n.id}`} className="underline">
                  {nodeLabel(n)}
                </a>
              )}
            </span>
          ))}
        </span>
        <button
          type="button"
          onClick={() => void toggleEdit()}
          className="rounded border px-2 py-0.5 text-xs hover:bg-muted"
        >
          {view.chain_next_id ? "Bearbeiten" : "⊕ nächster Agent"}
        </button>
        {view.chain_next_id && (
          <>
            <button
              type="button"
              onClick={() => void forward()}
              className="rounded bg-black px-3 py-1.5 text-sm text-white"
            >
              Jetzt weiterleiten →
            </button>
            <label className="flex items-center gap-1 text-xs text-gray-500">
              <input
                type="checkbox"
                checked={!!view.chain_auto}
                onChange={(e) => void toggleAuto(e.target.checked)}
              />
              automatisch bei neuem Stand
            </label>
          </>
        )}
      </div>

      <p className="mt-1 text-xs text-gray-500">
        Leite das Ergebnis dieser Instanz an einen nächsten Agenten weiter — manuell oder
        automatisch bei jedem neuen Stand.
      </p>

      {forwarded && view.chain_next_id && (
        <p className="mt-1 text-xs text-green-600">
          Weitergeleitet ✓{" "}
          <a href={`/artifacts/${view.chain_next_id}`} className="underline">
            zum nächsten Agenten
          </a>
        </p>
      )}

      {editing && (
        <div className="mt-2 flex flex-wrap items-center gap-2 border-t pt-2">
          {items === null ? (
            <span className="text-xs text-gray-400">Lädt…</span>
          ) : (
            <>
              <select
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
                className="rounded border px-2 py-1 text-sm"
              >
                <option value="">— Instanz wählen —</option>
                {items.map((i) => (
                  <option key={i.id} value={i.id}>
                    {i.title}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => void setNext()}
                disabled={!selected}
                className="rounded bg-black px-3 py-1.5 text-sm text-white disabled:opacity-50"
              >
                Setzen
              </button>
              {view.chain_next_id && (
                <button
                  type="button"
                  onClick={() => void removeNext()}
                  className="rounded border border-red-300 px-3 py-1.5 text-sm text-red-600"
                >
                  Entfernen
                </button>
              )}
            </>
          )}
        </div>
      )}

      {err && <p className="mt-1 text-xs text-red-600">{err}</p>}
    </div>
  );
}
