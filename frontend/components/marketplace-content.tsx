import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { api, type PublicTemplate } from "@/lib/api";
import { MarketplaceList } from "@/components/marketplace-list";

/**
 * Marktplatz-Inhalt (Server-Component): öffentliche Vorlagen + ob eingeloggt → an die
 * Filter-Liste. Wird unter `/marktplatz` und auf `/` (ausgeloggt) gerendert. Ohne
 * Überschrift — die Filter-Leiste ist der Einstieg.
 */
export async function MarketplaceContent() {
  let templates: PublicTemplate[] = [];
  try {
    templates = await api.templates.listPublic();
  } catch {
    templates = [];
  }
  const session = await getServerSession(authOptions);
  return <MarketplaceList templates={templates} loggedIn={!!session} />;
}
