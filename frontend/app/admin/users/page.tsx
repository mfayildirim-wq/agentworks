import { AdminUsersPanel } from "@/app/profile/admin-users-panel";

export const dynamic = "force-dynamic";

export default function AdminUsersPage() {
  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="mb-4 text-2xl font-bold">Nutzer-Rollen (GOA)</h1>
      <AdminUsersPanel />
    </main>
  );
}
