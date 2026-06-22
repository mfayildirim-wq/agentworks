"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { monogram, resolveAvatar } from "@/lib/icons";
import { CATEGORIES } from "@/lib/categories";

/** Auswählbarer Avatar-Stil (für das Generieren-Dropdown). */
type AvatarStyle = { id: string; label: string; group: string };

/**
 * Einheitliche „Agent-Vorlage"-Form für Anlegen UND Bearbeiten: Name, Beschreibung,
 * Prompt, Modell, Kosten, Kategorie, Sichtbarkeit, Bild. Ohne `templateId` legt sie
 * via POST /templates/agent-template an; mit `templateId` aktualisiert sie via
 * PUT /templates/agent-template/{id}.
 */
export type ModelOption = { value: string; label: string; group: string };

export type AgentTemplateInitial = {
  name: string;
  description: string;
  prompt: string;
  model: string;
  price: number;
  category: string;
  visibility: string;
  image_url: string;
  html_template_id: string;
  mcp_servers?: string[];
};

export function AgentTemplateForm({
  models,
  hasOwnKeys,
  templateId,
  initial
}: {
  models: ModelOption[];
  hasOwnKeys: boolean;
  templateId?: string;
  initial?: AgentTemplateInitial;
}) {
  const router = useRouter();
  const isEdit = Boolean(templateId);
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [avatarHint, setAvatarHint] = useState("");
  const [avatarStyle, setAvatarStyle] = useState("fotorealistisch");
  const [avatarStyles, setAvatarStyles] = useState<AvatarStyle[]>([]);
  const [showFree, setShowFree] = useState(false);
  const [freeAvatars, setFreeAvatars] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState({
    name: initial?.name ?? "",
    description: initial?.description ?? "",
    prompt: initial?.prompt ?? "",
    model: initial?.model ?? models[0]?.value ?? "qwen2.5:3b",
    price: initial?.price ?? 1.0,
    category: initial?.category ?? "",
    visibility: initial?.visibility ?? "private",
    image_url: initial?.image_url ?? "",
    // Design wird jetzt PRO INSTANZ gewählt (Instanz-Anlegen). Hier nur ein
    // gültiger Default, damit das Backend-Pflichtfeld erfüllt ist.
    html_template_id: initial?.html_template_id || "classic"
  });


  // Nur Admin/GOA dürfen öffentliche Vorlagen anlegen. Für normale User die
  // „Öffentlich"-Option ausblenden und die Sichtbarkeit auf „privat" erzwingen.
  // (Das Backend erzwingt dies ohnehin — hier nur UX.)
  const [isAdmin, setIsAdmin] = useState(false);
  useEffect(() => {
    let active = true;
    void fetch(`/api/proxy/users/me`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((me: { is_admin?: boolean } | null) => {
        if (!active) return;
        const admin = Boolean(me?.is_admin);
        setIsAdmin(admin);
        if (!admin && !["private", "draft", "friends"].includes(form.visibility))
          set("visibility", "private");
      })
      .catch(() => {
        /* im Zweifel kein Admin → Öffentlich bleibt ausgeblendet */
      });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auswählbare Avatar-Stile fürs Generieren-Dropdown laden.
  useEffect(() => {
    let active = true;
    void fetch(`/api/proxy/avatars/styles`)
      .then((r) => (r.ok ? r.json() : []))
      .then((data: AvatarStyle[]) => {
        if (active) setAvatarStyles(data);
      })
      .catch(() => {
        /* Dropdown bleibt leer; Default-Stil greift im Backend */
      });
    return () => {
      active = false;
    };
  }, []);

  function set<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim() || !form.prompt.trim()) {
      setError("Name und Prompt sind erforderlich.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const url = isEdit
        ? `/api/proxy/templates/agent-template/${templateId}`
        : `/api/proxy/templates/agent-template`;
      const res = await fetch(url, {
        method: isEdit ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: form.name,
          description: form.description,
          prompt: form.prompt,
          model: form.model,
          price: Number(form.price),
          category: form.category,
          visibility: form.visibility,
          image_url: form.image_url || null,
          html_template_id: form.html_template_id,
          mcp_servers: []
        })
      });
      if (!res.ok) {
        setError((await res.text()) || "Speichern fehlgeschlagen.");
        return;
      }
      const data = await res.json();
      router.push(`/templates/${data.id}`);
      router.refresh();
    } catch {
      setError("Netzwerkfehler — bitte erneut versuchen.");
    } finally {
      setBusy(false);
    }
  }

  async function generateAvatar() {
    if (!form.name.trim()) {
      setError("Bitte zuerst einen Namen eingeben.");
      return;
    }
    setGenerating(true);
    setError(null);
    try {
      const res = await fetch(`/api/proxy/avatars/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: form.name,
          description: form.description,
          prompt: form.prompt,
          hint: avatarHint,
          style: avatarStyle
        })
      });
      if (!res.ok) {
        setError((await res.text()) || "Avatar-Generierung fehlgeschlagen.");
        return;
      }
      const { url } = (await res.json()) as { url: string };
      set("image_url", url);
    } catch {
      setError("Avatar-Generierung fehlgeschlagen.");
    } finally {
      setGenerating(false);
    }
  }

  async function uploadImage(file: File) {
    setUploading(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`/api/proxy/media/upload`, { method: "POST", body: fd });
      if (!res.ok) {
        setError((await res.text()) || "Upload fehlgeschlagen.");
        return;
      }
      const { url } = (await res.json()) as { url: string };
      set("image_url", url);
    } catch {
      setError("Upload fehlgeschlagen.");
    } finally {
      setUploading(false);
    }
  }

  async function openFreeAvatars() {
    setShowFree(true);
    if (freeAvatars !== null) return; // einmal laden, gecacht
    try {
      const res = await fetch(`/api/proxy/media/free-avatars`, { cache: "no-store" });
      const d = (await res.json()) as { avatars?: string[] };
      setFreeAvatars(d.avatars ?? []);
    } catch {
      setFreeAvatars([]);
    }
  }

  return (
    <form onSubmit={submit} className="max-w-2xl space-y-4">
      <label className="block text-sm">
        Name
        <input
          className="mt-1 w-full rounded border px-3 py-2"
          placeholder="z.B. Reiseplaner"
          value={form.name}
          onChange={(e) => set("name", e.target.value)}
          disabled={busy}
        />
      </label>

      <label className="block text-sm">
        Kurzbeschreibung
        <input
          className="mt-1 w-full rounded border bg-muted px-3 py-2 text-muted-foreground"
          placeholder="Wird automatisch aus dem Prompt erzeugt"
          value={form.description}
          disabled
          readOnly
        />
        <span className="mt-1 block text-xs text-muted-foreground">
          Wird automatisch aus dem Prompt erzeugt (für Marktplatz & Routing).
        </span>
      </label>

      <label className="block text-sm">
        Prompt (definiert Verhalten, Fragen an den Nutzer und das Ergebnis)
        <textarea
          className="mt-1 w-full rounded border px-3 py-2 font-mono text-sm"
          rows={8}
          placeholder="Du bist ein Reiseplaner. Frage nach Ziel und Zeitraum und erstelle einen Reiseplan als HTML-Seite, Tag für Tag…"
          value={form.prompt}
          onChange={(e) => set("prompt", e.target.value)}
          disabled={busy}
        />
      </label>

      <p className="rounded border border-dashed border-gray-200 px-3 py-2 text-xs text-gray-500">
        Das Seiten-Design wird jetzt beim Anlegen einer Instanz gewählt
        (fertige Vorlage, vom Agent erzeugt oder Slot-Vorlage).
      </p>

      <div className="flex flex-wrap gap-4">
        <label className="block text-sm">
          Modell
          <select
            className="mt-1 w-72 rounded border px-3 py-2"
            value={form.model}
            onChange={(e) => set("model", e.target.value)}
            disabled={busy}
          >
            {Array.from(new Set(models.map((m) => m.group))).map((g) => (
              <optgroup key={g} label={g}>
                {models
                  .filter((m) => m.group === g)
                  .map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
              </optgroup>
            ))}
          </select>
          {!hasOwnKeys && (
            <p className="mt-1 text-xs text-gray-400">
              Eigene Modelle (Claude/OpenAI) erscheinen, sobald du im{" "}
              <a className="underline" href="/profile">
                Profil
              </a>{" "}
              einen API-Key hinterlegst.
            </p>
          )}
        </label>
        <label className="block text-sm">
          Kategorie
          <select
            required
            className="mt-1 w-48 rounded border px-3 py-2"
            value={form.category}
            onChange={(e) => set("category", e.target.value)}
            disabled={busy}
          >
            <option value="">— Kategorie wählen —</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          Sichtbarkeit
          <select
            className="mt-1 w-40 rounded border px-3 py-2"
            value={form.visibility}
            onChange={(e) => set("visibility", e.target.value)}
            disabled={busy}
          >
            {/* Nicht-Admins: nur „Privat" — das Backend erzwingt für sie ohnehin
                privat (auch bei „Per Link"/„Öffentlich"). */}
            {isAdmin && <option value="public">Öffentlich</option>}
            {isAdmin && <option value="unlisted">Per Link</option>}
            <option value="friends">Freunde</option>
            <option value="private">Privat</option>
            <option value="draft">Entwurf (nur ich)</option>
          </select>
        </label>
      </div>

      <div className="text-sm">
        Avatar
        <div className="mt-1 flex items-center gap-4">
          {/* Vorschau: Bild, Emoji (Alt-Vorlagen) oder Monogramm */}
          <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-lg border bg-muted">
            {form.image_url.startsWith("emoji:") ? (
              <span className="text-3xl">{form.image_url.slice("emoji:".length)}</span>
            ) : resolveAvatar(form.image_url) ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={resolveAvatar(form.image_url)!}
                alt="Avatar-Vorschau"
                className="h-full w-full object-cover"
              />
            ) : (
              <span
                className="flex h-full w-full items-center justify-center text-2xl font-semibold text-white"
                style={{ backgroundColor: monogram(form.name).color }}
              >
                {monogram(form.name).letter}
              </span>
            )}
          </div>

          <div className="flex flex-1 flex-col gap-2">
            {avatarStyles.length > 0 && (
              <select
                className="w-full rounded border px-3 py-2 text-sm"
                value={avatarStyle}
                onChange={(e) => setAvatarStyle(e.target.value)}
                disabled={busy || generating}
                aria-label="Avatar-Stil"
              >
                {Array.from(new Set(avatarStyles.map((s) => s.group))).map((g) => (
                  <optgroup key={g} label={g}>
                    {avatarStyles
                      .filter((s) => s.group === g)
                      .map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.label}
                        </option>
                      ))}
                  </optgroup>
                ))}
              </select>
            )}
            <input
              className="w-full rounded border px-3 py-2 text-sm"
              placeholder="Avatar-Beschreibung (optional), z.B. „freundlicher Roboter mit Landkarte und Koffer“"
              value={avatarHint}
              onChange={(e) => setAvatarHint(e.target.value)}
              maxLength={500}
              disabled={busy || generating}
            />
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => void generateAvatar()}
                disabled={busy || generating || uploading || !form.name.trim()}
                className="rounded border px-3 py-2 text-sm hover:bg-muted disabled:opacity-50"
              >
                {generating
                  ? "Generiert…"
                  : form.image_url
                    ? "🔁 Neu generieren"
                    : "✨ Mit KI generieren"}
              </button>
              <label className="cursor-pointer rounded border px-3 py-2 text-sm hover:bg-muted">
                {uploading ? "Lädt…" : "Bild hochladen"}
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp,image/svg+xml"
                  className="hidden"
                  disabled={busy || uploading || generating}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) void uploadImage(f);
                  }}
                />
              </label>
              <button
                type="button"
                onClick={() => void openFreeAvatars()}
                disabled={busy || uploading || generating}
                className="rounded border px-3 py-2 text-sm hover:bg-muted disabled:opacity-50"
              >
                🗂️ Freie Avatare
              </button>
            </div>

            {showFree && (
              <div className="rounded border p-2">
                <div className="mb-1 flex items-center justify-between text-xs text-gray-500">
                  <span>
                    Nicht zugeordnete Avatare{freeAvatars ? ` (${freeAvatars.length})` : " …"}
                  </span>
                  <button type="button" onClick={() => setShowFree(false)} aria-label="Schließen">
                    ✕
                  </button>
                </div>
                {freeAvatars === null ? (
                  <p className="text-xs text-gray-400">Lädt…</p>
                ) : freeAvatars.length === 0 ? (
                  <p className="text-xs text-gray-400">Keine freien Avatare im Ordner.</p>
                ) : (
                  <div className="grid max-h-48 grid-cols-6 gap-2 overflow-auto sm:grid-cols-8">
                    {freeAvatars.map((u) => (
                      <button
                        key={u}
                        type="button"
                        title="Diesen Avatar verwenden"
                        onClick={() => {
                          set("image_url", u);
                          setShowFree(false);
                        }}
                        className={`rounded border p-0.5 transition hover:border-primary ${
                          form.image_url === u ? "border-primary ring-2 ring-primary" : ""
                        }`}
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={resolveAvatar(u) ?? u} alt="" className="h-12 w-12 rounded object-cover" />
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
        <p className="mt-1 text-xs text-gray-400">
          Stil wählen; ohne Beschreibung wird der Avatar automatisch aus Name &amp; Beschreibung als
          Figur mit passendem Werkzeug erzeugt. Oder eigenes Bild hochladen (PNG/JPG/WebP/SVG, max. 2 MB).
        </p>
      </div>


      {error && <p className="text-sm text-red-600">{error}</p>}

      <button
        type="submit"
        disabled={busy}
        className="rounded bg-black px-4 py-2 text-sm text-white disabled:opacity-50"
      >
        {busy ? "Speichert…" : isEdit ? "Änderungen speichern" : "Agent-Vorlage erstellen"}
      </button>
    </form>
  );
}
