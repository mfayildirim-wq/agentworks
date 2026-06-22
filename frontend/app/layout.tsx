import type { Metadata } from "next";
import { cookies } from "next/headers";
import "./globals.css";
import { Providers } from "@/components/providers";
import { SiteHeader } from "@/components/site-header";
import type { Lang } from "@/lib/i18n/dict";

export const metadata: Metadata = {
  title: "AgentWorks",
  description: "Agenten-Marktplatz & Multi-Agent-Workflows"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const cookieLang = cookies().get("aw_lang")?.value;
  const lang: Lang = cookieLang === "en" ? "en" : "de";
  return (
    <html lang={lang}>
      <body>
        <Providers initialLang={lang}>
          <SiteHeader />
          <main className="container py-6">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
