/* Grammaire Apple — le peu de JavaScript qu'elle demande.
   1. .apparait : apparition au défilement (opacité + 20 px), désactivée en
      ctx-presentation, en impression et si prefers-reduced-motion.
   2. .segment : un contrôle segmenté pose aria-pressed sur le bouton choisi et
      émet l'événement « segment » (detail = value du bouton) sur son conteneur.
   3. data-theme : [data-bascule-theme] alterne clair / sombre sur <html>.
   4. .nav-locale : le lien de la section visible porte .actif.
   5. ?planche=<id> : n'affiche que la section #<id>, sans nav, en-tête ni pied, en
      ctx-presentation — ce que capturer.py --planche <id> attend pour une slide 16:9. */
(function () {
  var doc = document.documentElement;
  var planche = new URLSearchParams(window.location.search).get("planche");
  if (planche && document.body) {
    document.body.className = "ctx-presentation planche-seule";
    document.querySelectorAll(".nav-locale, .entete, .pied, .note, section, .bloc").forEach(function (e) {
      if (e.id !== planche) e.style.display = "none";
    });
    var cible = document.getElementById(planche);
    if (cible) {
      cible.style.display = ""; cible.style.paddingTop = "24px"; cible.classList.add("visible");
      // le constat (h2) et l'eyebrow sont le titre de la slide : le PNG ne les porte pas
      cible.querySelectorAll("h2, .t-eyebrow, .t-headline").forEach(function (e) { e.style.display = "none"; });
    }
  }
  var reduit = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var presentation = !!planche || (document.body && document.body.classList.contains("ctx-presentation"));

  function apparitions() {
    var els = document.querySelectorAll(".apparait");
    if (!els.length) return;
    if (reduit || presentation || !("IntersectionObserver" in window)) {
      els.forEach(function (e) { e.classList.add("visible"); });
      return;
    }
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add("visible"); obs.unobserve(en.target); }
      });
    }, { rootMargin: "0px 0px -10% 0px", threshold: 0.1 });
    els.forEach(function (e) { obs.observe(e); });
  }

  function segments() {
    document.querySelectorAll(".segment").forEach(function (seg) {
      var boutons = seg.querySelectorAll("button");
      boutons.forEach(function (b) {
        if (!b.hasAttribute("aria-pressed")) b.setAttribute("aria-pressed", b.classList.contains("actif") ? "true" : "false");
        b.addEventListener("click", function () {
          boutons.forEach(function (x) { x.setAttribute("aria-pressed", "false"); x.classList.remove("actif"); });
          b.setAttribute("aria-pressed", "true"); b.classList.add("actif");
          seg.dispatchEvent(new CustomEvent("segment", { detail: b.value || b.textContent.trim(), bubbles: true }));
        });
      });
    });
  }

  function navActive() {
    var nav = document.querySelector(".nav-locale");
    if (!nav || !("IntersectionObserver" in window)) return;
    var liens = nav.querySelectorAll("a[href^='#']");
    var cibles = [];
    liens.forEach(function (a) { var el = document.getElementById(a.getAttribute("href").slice(1)); if (el) cibles.push([el, a]); });
    if (!cibles.length) return;
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        liens.forEach(function (a) { a.classList.remove("actif"); });
        cibles.forEach(function (c) { if (c[0] === en.target) c[1].classList.add("actif"); });
      });
    }, { rootMargin: "-30% 0px -60% 0px" });
    cibles.forEach(function (c) { obs.observe(c[0]); });
  }

  function theme() {
    document.querySelectorAll("[data-bascule-theme]").forEach(function (b) {
      b.addEventListener("click", function () {
        var sombre = doc.getAttribute("data-theme") === "dark" ||
          (!doc.hasAttribute("data-theme") && window.matchMedia("(prefers-color-scheme: dark)").matches);
        doc.setAttribute("data-theme", sombre ? "light" : "dark");
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { apparitions(); segments(); theme(); navActive(); });
  } else { apparitions(); segments(); theme(); navActive(); }
})();
