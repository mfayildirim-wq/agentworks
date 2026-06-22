import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { api, type MasterPage } from "@/lib/api";
import { MasterView } from "@/components/master-view";
import { MarketplaceContent } from "@/components/marketplace-content";

export const dynamic = "force-dynamic";

/**
 * Startseite:
 * - eingeloggt MIT Instanzen → eigene Master-Seite (alle eigenen Instanz-Ergebnisse),
 * - eingeloggt OHNE Instanzen (neue Nutzer) → Marktplatz (öffentliche Vorlagen entdecken),
 * - ausgeloggt (oder Fehler) → Marktplatz.
 */
export default async function HomePage() {
  const session = await getServerSession(authOptions);

  if (session) {
    let master: MasterPage | null = null;
    try {
      master = await api.master("me");
    } catch {
      master = null;
    }
    // Nur mit mindestens einer Instanz die Master-Seite zeigen; sonst Marktplatz.
    if (master && master.instances.length > 0) {
      return (
        <MasterView
          instances={master.instances}
          isOwner={master.is_owner}
          ownerName={master.owner_name}
          ownerId={master.owner_id}
        />
      );
    }
  }

  return <MarketplaceContent />;
}
