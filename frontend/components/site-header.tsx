"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X } from "lucide-react";
import { signIn, signOut, useSession } from "next-auth/react";
import { Button } from "@/components/ui/button";
import { AgentUiSettings } from "@/components/agent-ui-settings";
import { useI18n } from "@/lib/i18n/provider";

export function SiteHeader() {
  const { t } = useI18n();
  const { data: session, status } = useSession();
  const [open, setOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const user = status === "authenticated" ? session?.user : undefined;

  const close = () => setOpen(false);
  const pathname = usePathname();
  // Aktiver Menüpunkt: schwarzer Rahmen, damit man sieht, wo man ist.
  const navCls = (href: string) =>
    pathname === href
      ? "rounded border border-black px-2 py-0.5 font-medium text-foreground"
      : "hover:text-foreground";
  const mobileCls = (href: string) =>
    `rounded px-2 py-3 hover:bg-muted ${pathname === href ? "border border-black font-medium" : ""}`;

  const avatarLetter = (user?.name || user?.email || "?").slice(0, 1).toUpperCase();

  return (
    <header className="relative border-b">
      <div className="container flex h-14 items-center justify-between">
        <div className="flex items-center gap-6">
          <Link href="/" className="text-lg font-semibold" onClick={close}>
            AgentWorks
          </Link>
          {/* Desktop-Navigation */}
          <nav className="hidden items-center gap-4 text-sm text-muted-foreground md:flex">
            <Link href="/marktplatz" className={navCls("/marktplatz")}>{t("nav.marketplace")}</Link>
            <Link href="/works" className={navCls("/works")}>{t("nav.public")}</Link>
          </nav>
        </div>

        {/* Desktop: Konto rechts */}
        <div className="hidden items-center gap-3 text-sm md:flex">
          {user && <AgentUiSettings />}
          {user ? (
            <div className="relative">
              <button
                type="button"
                onClick={() => setMenuOpen((o) => !o)}
                className="flex h-8 w-8 items-center justify-center rounded-full bg-black text-xs font-semibold text-white"
                aria-label="Konto-Menü"
                aria-haspopup="menu"
                aria-expanded={menuOpen}
                title="Konto"
              >
                {avatarLetter}
              </button>
              {menuOpen && (
                <>
                  {/* Klick-außerhalb fängt den Klick und schließt das Menü. */}
                  <button
                    type="button"
                    aria-hidden="true"
                    tabIndex={-1}
                    onClick={() => setMenuOpen(false)}
                    className="fixed inset-0 z-10 cursor-default"
                  />
                  <div
                    role="menu"
                    className="absolute right-0 top-10 z-20 w-40 overflow-hidden rounded-md border bg-background shadow-md"
                  >
                    <Link
                      href="/profile"
                      role="menuitem"
                      onClick={() => setMenuOpen(false)}
                      className="block px-3 py-2 text-sm hover:bg-muted"
                    >
                      {t("nav.profile")}
                    </Link>
                    <button
                      type="button"
                      role="menuitem"
                      onClick={() => {
                        setMenuOpen(false);
                        signOut();
                      }}
                      className="block w-full px-3 py-2 text-left text-sm hover:bg-muted"
                    >
                      {t("nav.signout")}
                    </button>
                  </div>
                </>
              )}
            </div>
          ) : (
            <Button size="sm" onClick={() => signIn("google")}>
              {t("nav.login")}
            </Button>
          )}
        </div>

        {/* Mobile: Einstellungen + Hamburger */}
        <div className="flex items-center gap-2 md:hidden">
          {user && <AgentUiSettings />}
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            className="flex h-9 w-9 items-center justify-center rounded border"
            aria-label={open ? "Menü schließen" : "Menü öffnen"}
            aria-expanded={open}
            aria-controls="mobile-menu"
          >
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Mobile-Menü (Dropdown) */}
      {open && (
        <div
          id="mobile-menu"
          className="absolute inset-x-0 top-14 z-20 border-b bg-background shadow-md md:hidden"
        >
          <nav className="container flex flex-col py-2 text-sm">
            <Link href="/marktplatz" onClick={close} className={mobileCls("/marktplatz")}>
              {t("nav.marketplace")}
            </Link>
            <Link href="/works" onClick={close} className={mobileCls("/works")}>
              {t("nav.public")}
            </Link>
            <div className="my-1 border-t" />
            {user ? (
              <>
                <Link
                  href="/profile"
                  onClick={close}
                  className="rounded px-2 py-3 hover:bg-muted"
                >
                  {t("nav.profile")}
                </Link>
                <button
                  type="button"
                  onClick={() => {
                    close();
                    signOut();
                  }}
                  className="rounded px-2 py-3 text-left hover:bg-muted"
                >
                  {t("nav.signout")}
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={() => {
                  close();
                  signIn("google");
                }}
                className="rounded px-2 py-3 text-left hover:bg-muted"
              >
                {t("nav.login")}
              </button>
            )}
          </nav>
        </div>
      )}
    </header>
  );
}
