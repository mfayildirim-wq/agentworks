import { getServerSession } from "next-auth";
import { NextRequest, NextResponse } from "next/server";
import { authOptions } from "@/lib/auth";

// Google-OAuth-Start.
//
// Warum eine eigene Route statt /api/proxy/...?
// Der generische Proxy folgt dem 302 des Backends server-seitig (fetch default
// redirect:"follow") und reicht den Location-Header NICHT weiter — der Browser landet
// also nie bei Google. Diese Route ruft das Backend mit redirect:"manual" auf (mit dem
// Bearer des eingeloggten Nutzers, da /start owner-geschützt ist) und leitet den Browser
// selbst auf die Google-Consent-URL weiter.
const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const artifactId = url.searchParams.get("artifact_id") ?? "";
  const kind = url.searchParams.get("kind") ?? "google_calendar";
  const session = await getServerSession(authOptions);
  const idToken = (session as { idToken?: string } | null)?.idToken;
  if (!idToken) return NextResponse.redirect(new URL("/", req.url));

  const res = await fetch(
    `${BACKEND}/oauth/google/start?artifact_id=${encodeURIComponent(artifactId)}&kind=${encodeURIComponent(kind)}`,
    {
      method: "GET",
      redirect: "manual",
      cache: "no-store",
      headers: { Authorization: `Bearer ${idToken}` },
    },
  );

  // Backend antwortet mit 302 + Location auf die Google-Consent-URL; diese übernehmen.
  const location = res.headers.get("location");
  if (location) return NextResponse.redirect(location);
  // Nicht-Besitzer/Fehler (404/403) → zurück zur Instanz bzw. Startseite.
  return NextResponse.redirect(new URL(artifactId ? `/artifacts/${artifactId}` : "/", req.url));
}
