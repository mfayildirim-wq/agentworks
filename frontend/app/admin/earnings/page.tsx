import { CreatorEarningsPanel } from "./panel";

export const dynamic = "force-dynamic";

export default function AdminEarningsPage() {
  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="mb-1 text-2xl font-bold">Creator-Einnahmen</h1>
      <p className="mb-4 text-sm text-muted-foreground">
        Anteil der Agent-Ersteller (5 % der LLM-Kosten) je Vorlage.
      </p>
      <CreatorEarningsPanel />
    </main>
  );
}
