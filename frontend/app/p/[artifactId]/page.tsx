import { notFound } from "next/navigation";

export const dynamic = "force-dynamic";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

export default async function PublicArtifactPage({
  params
}: {
  params: { artifactId: string };
}) {
  let html: string | null = null;
  try {
    const res = await fetch(`${BACKEND}/p/${params.artifactId}`, {
      cache: "no-store"
    });
    if (res.ok) html = await res.text();
  } catch {
    html = null; // Backend nicht erreichbar / Timeout → saubere 404 statt Crash-Seite
  }
  if (html === null) notFound();
  return (
    <iframe
      title="Geteilte Seite"
      srcDoc={html}
      sandbox=""
      style={{ position: "fixed", inset: 0, width: "100%", height: "100%", border: "none" }}
    />
  );
}
