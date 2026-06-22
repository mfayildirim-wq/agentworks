// Petite-vue Templates fuer die 3 Canvas-Designs.
//
// Der iFrame-Boot-Script (slot-iframe.ts) stellt den Scope bereit:
//   slots:  Array<{ id: string; title: string; body: string }>  (vom Parent VORSORTIERT)
//   layout: "sections" | "tabs"
//   active: number  (aktiver Tab-Index)
//
// Die Klassennamen (hero/card/grid/tile ...) muessen EXAKT zu den Design-CSS
// aus html_templates passen, damit das vom Parent gelieferte CSS greift.

// Geteiltes TABS-Fragment: eine Tab-Leiste plus ein Panel fuer den aktiven Slot.
// Das .tabbar-CSS wird im iFrame-Builder angehaengt (Design-CSS kennt es i.d.R. nicht).
const TABS = `<div class="tabbar">
  <button v-for="(s,i) in slots" @click="active=i" :class="{active: active===i}">{{s.title}}</button>
</div>
<div v-html="slots[active] ? slots[active].body : ''"></div>`;

// Leerer Zustand (keine Slots).
const EMPTY = `<div v-if="!slots.length"><p style="color:#888">Noch keine Inhalte.</p></div>`;

// --- classic: schlichte Sections in <main> ---
const CLASSIC_SECTIONS = `<main v-if="slots.length && layout!=='tabs'">
  <section v-for="s in slots" :id="s.id">
    <h2>{{s.title}}</h2>
    <div v-html="s.body"></div>
  </section>
</main>`;

// --- magazine: Hero-Header + Karten ---
const MAGAZINE_SECTIONS = `<div v-if="slots.length && layout!=='tabs'">
  <header class="hero"><h1>Übersicht</h1></header>
  <main>
    <section class="card" v-for="s in slots">
      <h2>{{s.title}}</h2>
      <div v-html="s.body"></div>
    </section>
  </main>
</div>`;

// --- cards: Header + Kachel-Grid ---
const CARDS_SECTIONS = `<div v-if="slots.length && layout!=='tabs'">
  <header><h1>Übersicht</h1></header>
  <div class="grid">
    <article class="tile" v-for="s in slots">
      <h3>{{s.title}}</h3>
      <div v-html="s.body"></div>
    </article>
  </div>
</div>`;

function compose(sections: string): string {
  return `${EMPTY}
<div v-if="slots.length && layout==='tabs'">${TABS}</div>
${sections}`;
}

export const THEME_TEMPLATES: Record<string, string> = {
  classic: compose(CLASSIC_SECTIONS),
  magazine: compose(MAGAZINE_SECTIONS),
  cards: compose(CARDS_SECTIONS),
};

export function themeTemplate(designId: string): string {
  return THEME_TEMPLATES[designId] ?? THEME_TEMPLATES.classic;
}
