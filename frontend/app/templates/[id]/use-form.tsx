"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Template } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";

export function UseTemplateForm({ template }: { template: Template }) {
  const { t } = useI18n();
  const router = useRouter();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      // Instanz anlegen — nur Name (label), Ausgabe vom Agenten erzeugt. KEINE Chat-Nachricht
      // vorab: die Instanz-Seite startet den Agenten beim Öffnen selbst (POST .../start).
      const res = await fetch(`/api/proxy/templates/${template.id}/instantiate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ inputs: { label: name.trim() }, output_template: "agent" })
      });
      if (!res.ok) {
        setError((await res.text()) || t("tpl.error"));
        return;
      }
      const data = (await res.json()) as { work_id: string; artifact_id: string | null };
      router.push(data.artifact_id ? `/artifacts/${data.artifact_id}` : `/works/${data.work_id}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <label className="mb-1 block text-sm font-medium">
          {t("tpl.name")}<span className="text-red-500"> *</span>
        </label>
        <input
          className="w-full rounded border px-2 py-1"
          placeholder={t("tpl.namePlaceholder")}
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <p className="mt-1 text-sm text-gray-500">
          {t("tpl.nameHint")}
        </p>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      <button
        type="submit"
        disabled={busy || !name.trim()}
        className="rounded bg-black px-4 py-2 text-sm text-white disabled:opacity-50"
      >
        {busy ? t("tpl.starting") : t("tpl.start")}
      </button>
    </form>
  );
}
