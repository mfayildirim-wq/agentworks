// Lädt das Avatar-Set (DiceBear "avataaars") als feste SVGs nach public/avatars.
// Die committeten SVGs sind danach die Quelle der Wahrheit — zur Laufzeit besteht
// KEIN Bezug zu DiceBear. Re-runnable; überschreibt vorhandene Dateien.
//
//   node scripts/fetch-avatars.mjs
//
// AVATAR_COUNT muss mit lib/icons.ts und dem Backend (app/services/agents.py)
// übereinstimmen.
import { mkdir, writeFile, readdir, rm } from "node:fs/promises";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const AVATAR_COUNT = 30;
const STYLE = "avataaars";
const OUT = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "avatars");

const pad = (n) => String(n).padStart(2, "0");

async function main() {
  await mkdir(OUT, { recursive: true });

  // Altbestand (z.B. Berufs-Emoji-Set) entfernen, damit nur das neue Set existiert.
  for (const f of await readdir(OUT)) {
    if (f.endsWith(".svg") && !/^avatar-\d{2}\.svg$/.test(f)) {
      await rm(join(OUT, f));
    }
  }

  for (let i = 1; i <= AVATAR_COUNT; i++) {
    const seed = `agent-${pad(i)}`;
    const url = `https://api.dicebear.com/9.x/${STYLE}/svg?seed=${encodeURIComponent(seed)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`${url} → HTTP ${res.status}`);
    const svg = await res.text();
    await writeFile(join(OUT, `avatar-${pad(i)}.svg`), svg, "utf8");
    console.log(`✓ avatar-${pad(i)}.svg`);
  }
  console.log(`Fertig: ${AVATAR_COUNT} Avatare in public/avatars/`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
