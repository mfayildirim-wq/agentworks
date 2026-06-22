export interface AvatarIcon {
  key: string;
  label: string;
}

// Muss mit scripts/fetch-avatars.mjs und dem Backend (app/services/agents.py)
// übereinstimmen.
export const AVATAR_COUNT = 30;

const pad = (n: number) => String(n).padStart(2, "0");

export const AVATAR_ICONS: AvatarIcon[] = Array.from({ length: AVATAR_COUNT }, (_, i) => ({
  key: `avatar-${pad(i + 1)}`,
  label: `Avatar ${i + 1}`
}));

export function randomAvatar(): string {
  return `preset:avatar-${pad(Math.floor(Math.random() * AVATAR_COUNT) + 1)}`;
}

export function resolveAvatar(avatarUrl: string | null | undefined): string | null {
  if (!avatarUrl) return null;
  if (avatarUrl.startsWith("preset:")) return `/avatars/${avatarUrl.slice(7)}.svg`;
  return avatarUrl; // /media/...
}

/** Deterministischer Farbton (0–359) aus einem String — stabil, wirkt zufällig. */
export function hueFromString(seed: string): number {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) % 360;
  return h;
}

/**
 * Monogramm-Fallback, wenn kein Bild/Emoji gesetzt ist: erster Großbuchstabe des
 * Namens auf einem deterministisch aus dem Namen gefärbten Kreis.
 */
export function monogram(name: string): { letter: string; color: string } {
  const letter = (name.trim()[0] ?? "?").toUpperCase();
  return { letter, color: `hsl(${hueFromString(name)}, 65%, 55%)` };
}
