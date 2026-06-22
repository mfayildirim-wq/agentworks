"use client";

import { SessionProvider } from "next-auth/react";
import type { ReactNode } from "react";
import { LanguageProvider } from "@/lib/i18n/provider";
import type { Lang } from "@/lib/i18n/dict";

export function Providers({
  children,
  initialLang = "de"
}: {
  children: ReactNode;
  initialLang?: Lang;
}) {
  return (
    <SessionProvider>
      <LanguageProvider initialLang={initialLang}>{children}</LanguageProvider>
    </SessionProvider>
  );
}
