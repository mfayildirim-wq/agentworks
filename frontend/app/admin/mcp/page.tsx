"use client";

import { useCallback, useEffect, useState } from "react";

type Mcp = {
  server_id: string; name: string; description: string;
  transport: string; url: string; requires_credential: boolean; enabled: boolean;
  auth_header: string; auth_value_template: string; secret_label: string;
};

const EMPTY: Mcp = {
  server_id: "", name: "", description: "",
  transport: "streamable_http", url: "", requires_credential: false, enabled: true,
  auth_header: "Authorization", auth_value_template: "Bearer {secret}", secret_label: "Token / API-Key"
};

export default function AdminMcpPage() {
  const [rows, setRows] = useState<Mcp[]>([]);
  const [form, setForm] = useState<Mcp>(EMPTY);
  const [editing, setEditing] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    const res = await fetch("/api/proxy/mcp-servers", { cache: "no-store" });
    if (res.ok) setRows(await res.json());
  }, []);
  useEffect(() => { void load(); }, [load]);

  async function save() {
    const isEdit = editing !== null;
    const url = isEdit ? `/api/proxy/mcp-servers/${editing}` : "/api/proxy/mcp-servers";
    const res = await fetch(url, {
      method: isEdit ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form)
    });
    if (res.ok) { setMsg("Gespeichert ✅"); setForm(EMPTY); setEditing(null); void load(); }
    else setMsg((await res.text()) || "Fehler");
  }

  async function toggle(s: Mcp) {
    const res = await fetch(`/api/proxy/mcp-servers/${s.server_id}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: !s.enabled })
    });
    if (res.ok) void load();
    else setMsg("Änderung fehlgeschlagen");
  }

  async function remove(id: string) {
    if (!window.confirm(`MCP-Server „${id}" wirklich löschen?`)) return;
    const res = await fetch(`/api/proxy/mcp-servers/${id}`, { method: "DELETE" });
    if (res.ok) { setMsg(`„${id}" gelöscht`); void load(); }
    else setMsg("Löschen fehlgeschlagen");
  }

  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="mb-4 text-2xl font-bold">MCP-Server (Admin)</h1>
      {msg && <p className="mb-2 text-sm text-gray-600">{msg}</p>}

      <table className="mb-6 w-full text-sm">
        <thead>
          <tr className="border-b text-left text-gray-500">
            <th className="py-1">Name</th><th>server_id</th><th>Transport</th>
            <th>URL</th><th>Login?</th><th>Aktiv</th><th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.server_id} className="border-b">
              <td className="py-1">{s.name}</td>
              <td className="font-mono text-xs">{s.server_id}</td>
              <td>{s.transport}</td>
              <td className="max-w-[16rem] truncate font-mono text-xs">{s.url}</td>
              <td>{s.requires_credential ? "ja" : "nein"}</td>
              <td>
                <button className="underline" onClick={() => toggle(s)}>
                  {s.enabled ? "aktiv" : "aus"}
                </button>
              </td>
              <td className="space-x-2 text-right">
                <button className="underline" onClick={() => { setForm({ ...s, auth_header: s.auth_header ?? "Authorization", auth_value_template: s.auth_value_template ?? "Bearer {secret}", secret_label: s.secret_label ?? "Token / API-Key" }); setEditing(s.server_id); }}>Bearbeiten</button>
                <button className="text-red-600 underline" onClick={() => remove(s.server_id)}>Löschen</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="max-w-lg space-y-2 rounded border p-3">
        <h2 className="font-semibold">{editing ? `Bearbeiten: ${editing}` : "Neuen MCP-Server anlegen"}</h2>
        {!editing && (
          <input className="w-full rounded border px-2 py-1" placeholder="server_id (Slug, z.B. wetter)"
            value={form.server_id} onChange={(e) => setForm({ ...form, server_id: e.target.value })} />
        )}
        <input className="w-full rounded border px-2 py-1" placeholder="Name"
          value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <input className="w-full rounded border px-2 py-1" placeholder="Beschreibung"
          value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        <select className="w-full rounded border px-2 py-1" value={form.transport}
          onChange={(e) => setForm({ ...form, transport: e.target.value })}>
          <option value="streamable_http">streamable_http</option>
          <option value="sse">sse</option>
        </select>
        <input className="w-full rounded border px-2 py-1" placeholder="URL (z.B. http://server:8080/mcp)"
          value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={form.requires_credential}
            onChange={(e) => setForm({ ...form, requires_credential: e.target.checked })} />
          braucht Login (credential)
        </label>
        {form.requires_credential && (
          <>
            <input className="w-full rounded border px-2 py-1" placeholder="Auth-Header"
              value={form.auth_header} onChange={(e) => setForm({ ...form, auth_header: e.target.value })} />
            <input className="w-full rounded border px-2 py-1" placeholder="Wert-Template (muss {secret} enthalten)"
              value={form.auth_value_template} onChange={(e) => setForm({ ...form, auth_value_template: e.target.value })} />
            <input className="w-full rounded border px-2 py-1" placeholder="Token-Label (Nutzer-Formular)"
              value={form.secret_label} onChange={(e) => setForm({ ...form, secret_label: e.target.value })} />
          </>
        )}
        <div className="flex gap-2">
          <button className="rounded bg-black px-3 py-1.5 text-white" onClick={save}>Speichern</button>
          {editing && <button className="rounded border px-3 py-1.5" onClick={() => { setForm(EMPTY); setEditing(null); }}>Abbrechen</button>}
        </div>
      </div>
    </main>
  );
}
