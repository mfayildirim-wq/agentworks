"use client";

import { useEffect, useState } from "react";
import type { Profile } from "@/lib/api";
import { ProfileForm } from "./form";
import { WalletPanel } from "./wallet-panel";
import { FriendsPanel } from "./friends-panel";
import { UsageByInstance } from "./usage-by-instance";
import { ModerationPanel } from "./moderation-panel";
import { AdminUsersPanel } from "./admin-users-panel";
import { SystemKeysPanel } from "./system-keys-panel";
import { SystemPricesPanel } from "./system-prices-panel";
import { SystemBillingPanel } from "./system-billing-panel";
import { SystemUsersPanel } from "./system-users-panel";
import { useI18n } from "@/lib/i18n/provider";

type Tab = "profil" | "kosten" | "freunde" | "moderation" | "admin" | "system";

export function ProfileHub({ initial }: { initial: Profile | null }) {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("profil");

  // Rollen einmalig laden, um Moderation (Admin) / Admin (GOA) Tabs zu zeigen.
  const [isAdmin, setIsAdmin] = useState(false);
  const [isGoa, setIsGoa] = useState(false);
  useEffect(() => {
    let active = true;
    void fetch("/api/proxy/users/me", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((me: { is_admin?: boolean; is_goa?: boolean } | null) => {
        if (active) {
          setIsAdmin(Boolean(me?.is_admin));
          setIsGoa(Boolean(me?.is_goa));
        }
      })
      .catch(() => {
        /* im Zweifel keine Admin-Tabs */
      });
    return () => {
      active = false;
    };
  }, []);

  const tabs: { id: Tab; label: string; show: boolean }[] = [
    { id: "profil", label: t("ptab.profile"), show: true },
    { id: "kosten", label: t("ptab.costs"), show: true },
    { id: "freunde", label: t("ptab.friends"), show: true },
    { id: "moderation", label: t("ptab.moderation"), show: isAdmin },
    { id: "admin", label: t("ptab.admin"), show: isGoa },
    { id: "system", label: t("ptab.system"), show: isGoa }
  ];

  const pill = (active: boolean) =>
    `rounded-full px-4 py-1.5 text-sm transition ${
      active
        ? "bg-black text-white"
        : "border text-muted-foreground hover:bg-muted"
    }`;

  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold">Profil</h1>

      <div className="mb-6 flex flex-wrap gap-2">
        {tabs
          .filter((t) => t.show)
          .map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={pill(tab === t.id)}
            >
              {t.label}
            </button>
          ))}
      </div>

      {tab === "profil" &&
        (initial ? (
          <ProfileForm initial={initial} />
        ) : (
          <p className="text-sm text-muted-foreground">
            Profil konnte nicht geladen werden.
          </p>
        ))}

      {tab === "kosten" && (
        <>
          <WalletPanel />
          <UsageByInstance />
        </>
      )}

      {tab === "freunde" && <FriendsPanel />}

      {tab === "moderation" && isAdmin && <ModerationPanel />}

      {tab === "admin" && isGoa && <AdminUsersPanel />}

      {tab === "system" && isGoa && (
        <div className="space-y-6">
          <SystemKeysPanel />
          <SystemPricesPanel />
          <SystemBillingPanel />
          <SystemUsersPanel />
        </div>
      )}
    </div>
  );
}
