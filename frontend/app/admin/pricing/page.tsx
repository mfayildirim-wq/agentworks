import { PricingEditor } from "./editor";

export const dynamic = "force-dynamic";

export default function AdminPricingPage() {
  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="mb-4 text-2xl font-bold">Provider-Preise (Admin)</h1>
      <PricingEditor />
    </main>
  );
}
