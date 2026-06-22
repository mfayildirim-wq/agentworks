"use client";

import { useState } from "react";
import type { Profile } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";

export function ProfileForm({ initial }: { initial: Profile }) {
  const { t } = useI18n();
  const [name, setName] = useState(initial.name);
  const [notifyEmail, setNotifyEmail] = useState(initial.notify_email);
  const [notifyTelegram, setNotifyTelegram] = useState(initial.notify_telegram);
  const [telegramConnected, setTelegramConnected] = useState(initial.telegram_connected);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function connectTelegram() {
    setMsg(null);
    const res = await fetch("/api/proxy/profile/telegram/link-token", { method: "POST" });
    if (!res.ok) {
      setMsg(t("profile.telegramLinkFailed"));
      return;
    }
    const { token, bot_username } = (await res.json()) as { token: string; bot_username: string };
    if (!bot_username) {
      setMsg(t("profile.telegramNotConfigured"));
      return;
    }
    window.open(`https://t.me/${bot_username}?start=${token}`, "_blank", "noopener");
    setMsg(t("profile.telegramStartHint"));
  }

  async function disconnectTelegram() {
    const res = await fetch("/api/proxy/profile/telegram", { method: "DELETE" });
    if (res.ok) {
      setTelegramConnected(false);
      setMsg(t("profile.telegramDisconnected"));
    }
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    const body: Record<string, unknown> = {
      name,
      notify_email: notifyEmail,
      notify_telegram: notifyTelegram
    };
    try {
      const res = await fetch("/api/proxy/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      if (!res.ok) {
        setMsg((await res.text()) || t("profile.saveFailed"));
        return;
      }
      (await res.json()) as Profile;
      setMsg(t("profile.saved"));
    } catch {
      setMsg(t("profile.networkError"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={save} className="max-w-xl space-y-5">
      <div>
        <div className="text-sm text-muted-foreground">{t("profile.email")}</div>
        <div className="font-medium">{initial.email}</div>
      </div>

      <label className="block text-sm">
        {t("profile.name")}
        <input
          className="mt-1 w-full rounded border px-3 py-2"
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={busy}
        />
      </label>

      <div className="rounded-lg border p-4">
        <h2 className="mb-1 font-semibold">{t("profile.notifications")}</h2>
        <p className="mb-3 text-xs text-muted-foreground">
          {t("profile.notificationsHint")}
        </p>

        <div className="mb-3 flex items-center justify-between gap-2">
          <div className="text-sm">
            {t("profile.telegram")}{" "}
            {telegramConnected ? (
              <span className="text-xs text-green-700">● {t("profile.connected")}</span>
            ) : (
              <span className="text-xs text-muted-foreground">● {t("profile.notConnected")}</span>
            )}
          </div>
          {telegramConnected ? (
            <button
              type="button"
              onClick={disconnectTelegram}
              className="rounded border px-3 py-1 text-sm hover:bg-muted"
            >
              {t("profile.disconnect")}
            </button>
          ) : (
            <button
              type="button"
              onClick={connectTelegram}
              className="rounded border px-3 py-1 text-sm hover:bg-muted"
            >
              {t("profile.connect")}
            </button>
          )}
        </div>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={notifyEmail}
            onChange={(e) => setNotifyEmail(e.target.checked)}
            disabled={busy}
          />
          {t("profile.emailNotifications")} ({initial.email})
        </label>
        <label className="mt-2 flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={notifyTelegram}
            onChange={(e) => setNotifyTelegram(e.target.checked)}
            disabled={busy}
          />
          {t("profile.telegramNotifications")}
        </label>
      </div>

      {msg && <p className="text-sm text-muted-foreground">{msg}</p>}

      <button
        type="submit"
        disabled={busy}
        className="rounded bg-black px-4 py-2 text-sm text-white disabled:opacity-50"
      >
        {busy ? t("profile.saving") : t("common.save")}
      </button>
    </form>
  );
}
