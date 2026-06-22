// optional progressive enhancement: smooth-scroll fuer interne Anker.
document.addEventListener("click", function (e) {
  var a = e.target.closest && e.target.closest('a[href^="#"]');
  if (!a) return;
  var el = document.querySelector(a.getAttribute("href"));
  if (el) {
    e.preventDefault();
    el.scrollIntoView({ behavior: "smooth", block: "start" });
  }
});
