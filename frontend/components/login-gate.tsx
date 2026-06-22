"use client";

import { signIn, useSession } from "next-auth/react";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n/provider";
import type { ReactNode } from "react";

export function LoginGate({ children }: { children: ReactNode }) {
  const { status } = useSession();
  const { t } = useI18n();
  if (status === "loading") return <p>{t("login.loading")}</p>;
  if (status === "unauthenticated") {
    return (
      <div className="flex flex-col items-center gap-4 py-20">
        <h2 className="text-2xl font-semibold">{t("login.pleaseLogin")}</h2>
        <p className="text-muted-foreground">{t("login.usesGoogle")}</p>
        <Button onClick={() => signIn("google")}>{t("login.continueGoogle")}</Button>
      </div>
    );
  }
  return <>{children}</>;
}
