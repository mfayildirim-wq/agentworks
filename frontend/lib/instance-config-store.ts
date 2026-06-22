import type { ReactNode } from "react";

/**
 * Winziger Modul-Store für die Einstellungs-Sektionen der gerade offenen Instanz
 * (Work-View). Die Work-View schiebt ihre zwei Konfig-Knoten (Instanz-Konfig +
 * Template) hier hinein; das Nav-Dropdown „Agent-UI-Einstellungen" liest sie via
 * `useSyncExternalStore` und rendert sie als zwei aufklappbare Popups. Kein
 * Prop-Durchreichen, kein Endlos-Render. `null`, wenn keine Instanz offen ist.
 */
export type InstanceConfig = {
  instanz: ReactNode | null;
  template: ReactNode | null;
  externalUrl: string | null;
};

let value: InstanceConfig | null = null;
const listeners = new Set<() => void>();

export const instanceConfigStore = {
  set(node: InstanceConfig | null) {
    value = node;
    listeners.forEach((cb) => cb());
  },
  subscribe(cb: () => void): () => void {
    listeners.add(cb);
    return () => listeners.delete(cb);
  },
  getSnapshot(): InstanceConfig | null {
    return value;
  },
  getServerSnapshot(): InstanceConfig | null {
    return null;
  }
};
