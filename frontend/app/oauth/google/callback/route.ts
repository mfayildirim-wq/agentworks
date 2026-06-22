import { NextRequest, NextResponse } from "next/server";

// Google OAuth callback landing route.
//
// Warum eine eigene Route statt /api/proxy/...?
// Der generische Proxy (app/api/proxy/[...path]/route.ts) folgt dem 302 des Backends
// server-seitig (fetch default redirect:"follow") und reicht nur den Content-Type, nicht
// den Location-Header weiter — der Browser bleibt also auf der Callback-URL hängen.
// Diese dünne Route ruft das Backend mit redirect:"manual" auf und leitet den Browser
// selbst auf die vom Backend gelieferte Ziel-URL (/artifacts/{id}) weiter.
const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const code = url.searchParams.get("code") ?? "";
  const state = url.searchParams.get("state") ?? "";

  const res = await fetch(
    `${BACKEND}/oauth/google/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`,
    { method: "GET", redirect: "manual", cache: "no-store" },
  );

  // Backend antwortet mit 302 + Location auf /artifacts/{id}; diese Ziel-URL übernehmen.
  const location = res.headers.get("location");
  if (location) return NextResponse.redirect(location);

  // Fehler (z.B. 400 ungültiger state) → zurück zur Startseite.
  return NextResponse.redirect(new URL("/", req.url));
}
