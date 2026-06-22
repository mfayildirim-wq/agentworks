import { petiteVueSource } from "./petite-vue-src";

// Minimales Tab-CSS — das Design-CSS aus html_templates kennt .tabbar i.d.R. nicht.
const TAB_CSS = `.tabbar{display:flex;flex-wrap:wrap;gap:.25rem;margin-bottom:1rem}
.tabbar button{padding:.4rem .8rem;border:1px solid #ddd;background:#f7f7f7;cursor:pointer;border-radius:.375rem}
.tabbar button.active{background:#111;color:#fff;font-weight:600}`;

/**
 * Baut das vollstaendige, ISOLIERTE iFrame-Dokument fuer einen Canvas-Slot.
 * petite-vue wird inline eingebettet (keine externen Skripte/CDN).
 * Der Parent fuettert Slot-Daten via postMessage({ type: "render", data: {...} }).
 */
export function buildSlotIframeDoc(css: string, template: string): string {
  // </script> im petite-vue-Quelltext neutralisieren, damit es das <script> nicht schliesst.
  const pv = petiteVueSource().replace(/<\/script/gi, "<\\/script");
  // 'unsafe-eval' ist nötig, weil petite-vue Template-Ausdrücke via `new Function` auswertet.
  // Unbedenklich hier: der iFrame ist sandboxed (allow-scripts, KEIN same-origin) + `connect-src 'none'`
  // → der eval ist eingesperrt, kein Cookie/Session/Netz-Zugriff.
  return `<!doctype html><html><head>
<meta charset="utf-8">
<base target="_blank">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline' 'unsafe-eval'; img-src https: data:">
<style>${css}\n${TAB_CSS}</style>
</head><body>
<div id="app">${template}</div>
<script>${pv}</script>
<script>
(function(){
  var scope = PetiteVue.reactive({ slots: [], layout: "sections", active: 0 });
  PetiteVue.createApp(scope).mount("#app");
  window.addEventListener("message", function(e){
    var d = e.data;
    if (d && d.type === "render" && d.data) {
      scope.slots = Array.isArray(d.data.slots) ? d.data.slots : [];
      scope.layout = d.data.layout || "sections";
      scope.active = 0;
    }
  });
  document.addEventListener("click", function(e){
    var t = e.target;
    var el = t && t.closest ? t.closest("[data-action]") : null;
    if (el) { e.preventDefault(); parent.postMessage({ type: "action", prompt: el.getAttribute("data-action") || "" }, "*"); }
  });
  parent.postMessage({ type: "ready" }, "*");
})();
</script>
</body></html>`;
}
