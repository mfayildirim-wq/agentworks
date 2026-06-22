import { notFound } from "next/navigation";
import { api, type MasterPage } from "@/lib/api";
import { MasterView } from "@/components/master-view";

export const dynamic = "force-dynamic";

/**
 * Öffentliche Master-Seite eines Nutzers unter `/m/<userId>`.
 * Zeigt nur die öffentlich/ungelistet gestellten Instanzen; 404 wenn nicht gefunden.
 */
export default async function PublicMasterPage({
  params
}: {
  params: { userId: string };
}) {
  let master: MasterPage | null = null;
  try {
    master = await api.master(params.userId);
  } catch {
    notFound();
  }
  if (!master) notFound();

  return (
    <MasterView
      instances={master.instances}
      isOwner={false}
      ownerName={master.owner_name}
      ownerId={master.owner_id}
    />
  );
}
