"use client";

import Link from "next/link";
import { Pencil } from "lucide-react";

/**
 * Bleistift-Overlay in einer Vorlagen-Karte (die Karte selbst ist ein Link zur
 * Instanz-Seite). Eigener Anchor zur Bearbeiten-Seite, liegt mit z-index ÜBER der
 * Karte und stoppt das Klick-Bubbling, damit nicht der Karten-Link auslöst.
 */
export function TemplateEditButton({ templateId }: { templateId: string }) {
  return (
    <Link
      href={`/agent-templates/${templateId}/edit`}
      onClick={(e) => e.stopPropagation()}
      title="Vorlage bearbeiten"
      aria-label="Vorlage bearbeiten"
      className="relative z-10 flex h-7 w-7 items-center justify-center rounded-full border bg-white text-gray-700 shadow-sm transition hover:bg-muted"
    >
      <Pencil size={14} />
    </Link>
  );
}
