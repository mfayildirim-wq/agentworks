import { ModerationPanel } from "@/app/profile/moderation-panel";

export const dynamic = "force-dynamic";

export default function AdminPublicationsPage() {
  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="mb-4 text-2xl font-bold">Veröffentlichungs-Moderation</h1>
      <ModerationPanel />
    </main>
  );
}
