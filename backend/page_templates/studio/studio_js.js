// optional progressive enhancement: sanftes Einblenden der Karten beim Laden.
document.addEventListener("DOMContentLoaded", function () {
  var cards = document.querySelectorAll(".card");
  cards.forEach(function (card, i) {
    card.style.opacity = "0";
    card.style.transform = "translateY(12px)";
    setTimeout(function () {
      card.style.transition = "opacity .4s ease, transform .4s ease";
      card.style.opacity = "1";
      card.style.transform = "translateY(0)";
    }, 80 * i);
  });
});
