/* Les cartes : l'étagère des boosters, leur ouverture, et l'album des candidatures.
   La logique (qui forme un booster, les étapes) est dans collection.js ; le suivi est
   celui de la liste (page.js, partagé par window.Veille). Ce qui a déjà été ouvert
   reste dans ce navigateur, sous la clé CLE_OUVERTES. */
(function () {
  "use strict";

  var V = window.Veille, C = Collection;
  var CLE_OUVERTES = "veille-offres-ouvertes";
  var ouvertes = V.lire(CLE_OUVERTES, {});
  var esc = V.esc;
  function $(id) { return document.getElementById(id); }
  var mouvementReduit = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ------------------------------------------------------------ une carte
  function carte(o, options) {
    options = options || {};
    var c = (V.suivi[o.cle] || {}).candidature;
    var etape = c ? " e-" + c.etape : "";
    // « Paris, France / Paris, Paris, France » → « Paris, France » : chaque morceau une seule fois.
    var morceaux = Array.from(new Set((o.lieu || "").split(/\s*[\/,;]\s*/).filter(Boolean)));
    var lieux = morceaux.slice(0, 2).join(", ") + (morceaux.length > 2 ? " +" + (morceaux.length - 2) : "");
    var tags = (o.colle || []).slice(0, 3).map(function (r) { return "<li>" + esc(r.tag) + "</li>"; }).join("");
    var face =
      '<div class="carte-face">' +
        '<div class="carte-tete"><span class="carte-rarete">' + esc(V.RARETES[o.rarete]) + "</span><b>" + o.score + "</b></div>" +
        '<div class="carte-mono" aria-hidden="true">' + esc(V.initiales(o.employeur)) + "</div>" +
        '<p class="carte-employeur">' + esc(o.employeur) + "</p>" +
        '<h3 class="carte-poste">' + esc(o.titre) + "</h3>" +
        '<p class="carte-lieu">' + esc([lieux, o.mode].filter(Boolean).join(" · ")) + "</p>" +
        '<p class="carte-salaire">' + esc(o.salaire || "salaire non affiché") + "</p>" +
        (tags ? '<ul class="carte-tags">' + tags + "</ul>" : "") +
        (c ? '<p class="carte-etape">' + esc(C.LIBELLES_ETAPES[c.etape]) + " · " + esc(V.dateCourte(c.le)) + "</p>" : "") +
        (o.retiree ? '<p class="carte-close">Offre clôturée</p>' : "") +
      "</div>";
    var dos = '<div class="carte-dos" aria-hidden="true"><span>radar</span><span>offres</span></div>';
    return '<button type="button" class="carte r-' + esc(o.rarete) + etape + (o.retiree ? " retiree" : "") +
      (options.retournee ? " retournee" : "") + (options.mini ? " mini" : "") + '" data-cle="' + esc(o.cle) + '"' +
      ' aria-label="' + esc(options.retournee === false ? "Carte cachée : la retourner" : o.titre + ", " + o.employeur + ", " + V.RARETES[o.rarete]) + '">' +
      '<span class="carte-interieur">' + dos + face + "</span></button>";
  }

  function trouver(cle) { return V.offres.filter(function (o) { return o.cle === cle; })[0]; }

  // ------------------------------------------------------------ l'étagère
  function periode(booster) {
    var dates = booster.map(function (o) { return o.vu_le; }).sort();
    var a = V.dateCourte(dates[0]), b = V.dateCourte(dates[dates.length - 1]);
    return a === b ? "offres du " + a : "offres du " + a + " au " + b;
  }

  function etagere() {
    var r = C.boosters(V.offres, V.suivi, ouvertes);
    var n = r.prets.length;
    $("boosters-titre").textContent = n ? n + (n > 1 ? " boosters à ouvrir." : " booster à ouvrir.") : "Aucun booster à ouvrir.";
    $("boosters-sous").textContent = "Chaque booster réunit " + r.taille + " nouvelles offres. Leur rareté dit à quel point " +
      "elles te correspondent : la plus rare sort en dernier. Une carte n'entre dans ton album que si tu postules.";

    var paquets = r.prets.slice(0, 8).map(function (b, i) {
      return '<button type="button" class="paquet" data-booster="' + i + '" style="--i:' + i + '">' +
        '<span class="paquet-brillance" aria-hidden="true"></span>' +
        '<span class="paquet-nom">radar<br>offres</span>' +
        '<span class="paquet-info"><b>' + r.taille + " cartes</b>" + esc(periode(b)) + "</span></button>";
    }).join("");
    var plus = n > 8 ? '<p class="etagere-plus">et ' + (n - 8) + " autres derrière.</p>" : "";

    var p = r.pochette.length;
    var fortes = r.pochette.filter(function (o) { return o.rarete === "epique" || o.rarete === "legendaire"; }).length;
    var pochette =
      '<div class="pochette">' +
        '<div class="pochette-cartes" aria-hidden="true">' + Array.from({ length: r.taille }, function (_, i) {
          return '<span class="' + (i < p ? "pleine" : "") + '"></span>'; }).join("") + "</div>" +
        '<p class="pochette-texte"><b>' + p + " / " + r.taille + "</b> cartes pour le prochain booster.</p>" +
        '<p class="pochette-note">' + (fortes
          ? "Dont " + fortes + (fortes > 1 ? " cartes épiques ou mieux, déjà visibles" : " carte épique ou mieux, déjà visible") + " dans la liste des offres : elles n'attendent pas."
          : "Il se forme dès que " + r.taille + " nouvelles offres sont arrivées.") + "</p>" +
      "</div>";
    var tout = n > 3 ? '<button type="button" class="lien plein vu-tout" id="vu-tout">J\'ai déjà vu ces offres : tout marquer comme ouvert</button>' : "";

    $("etagere").innerHTML = (n ? '<div class="paquets">' + paquets + "</div>" + plus : "") + pochette + tout;
    return r;
  }

  $("etagere").addEventListener("click", function (e) {
    var b = e.target.closest(".paquet");
    if (b) { ouvrirBooster(C.boosters(V.offres, V.suivi, ouvertes).prets[+b.dataset.booster]); return; }
    if (e.target.id === "vu-tout") {
      C.boosters(V.offres, V.suivi, ouvertes).prets.forEach(function (booster) { C.ouvrir(booster, ouvertes); });
      V.ecrire(CLE_OUVERTES, ouvertes); toutRendre();
    }
  });

  // ------------------------------------------------------------ l'ouverture
  var scene = $("scene"), detail = $("scene-detail"), fond = $("ouverture");
  var enCours = null, choisie = null, retourDuFocus = null;
  var visitees = {};   // les offres dont on a ouvert la page pendant ce booster : « J'ai postulé » s'y met en avant

  // Les deux gestes qui comptent, sous chaque carte retournée : lire l'offre, puis dire qu'on a postulé.
  function actionsCarte(o) {
    var voir = '<a class="mini-action voir" data-voir="' + esc(o.cle) + '" href="' + esc(o.lien) +
      '" target="_blank" rel="noopener noreferrer">Voir l\'offre ↗</a>';
    if ((V.suivi[o.cle] || {}).candidature) return voir + '<span class="mini-action fait">✓ Dans l\'album</span>';
    return voir + '<button type="button" class="mini-action postuler' + (visitees[o.cle] ? " a-faire" : "") +
      '" data-postuler="' + esc(o.cle) + '">J\'ai postulé</button>';
  }
  function majActions(cle) {
    var zone = scene.querySelector('.case-scene-actions[data-pour="' + CSS.escape(cle) + '"]');
    if (zone) zone.innerHTML = actionsCarte(trouver(cle));
  }

  function ouvrirBooster(booster) {
    if (!booster) return;
    enCours = booster; choisie = null; retourDuFocus = document.activeElement;
    $("scene-titre").textContent = "Booster · " + periode(booster);
    detail.innerHTML = "";
    scene.className = "scene";
    scene.innerHTML =
      '<button type="button" class="paquet grand" id="paquet-ouvert">' +
        '<span class="paquet-brillance" aria-hidden="true"></span>' +
        '<span class="paquet-nom">radar<br>offres</span>' +
        '<span class="paquet-info"><b>' + booster.length + " cartes</b>Touche pour ouvrir</span></button>";
    fond.hidden = false;
    document.body.classList.add("scene-ouverte");
    $("paquet-ouvert").focus();
  }

  function dechirer() {
    // Le booster est vu dès qu'on le déchire : recharger la page ne le refait pas apparaître.
    C.ouvrir(enCours, ouvertes); V.ecrire(CLE_OUVERTES, ouvertes);
    var paquet = $("paquet-ouvert");
    paquet.classList.add("dechire");
    setTimeout(distribuer, mouvementReduit ? 0 : 650);
  }

  function distribuer() {
    scene.className = "scene distribuee";
    scene.innerHTML = '<div class="main-cartes">' + enCours.map(function (o, i) {
      return '<div class="case-scene" style="--i:' + i + '">' + carte(o, { retournee: false }) +
        '<div class="case-scene-actions" data-pour="' + esc(o.cle) + '">' + actionsCarte(o) + "</div></div>";
    }).join("") + "</div>" +
      '<div class="scene-actions"><button type="button" class="bouton" id="tout-retourner">Tout retourner</button></div>';
    var premiere = scene.querySelector(".carte"); if (premiere) premiere.focus();
  }

  function retourner(bouton) {
    if (bouton.classList.contains("retournee")) { choisir(bouton.dataset.cle); return; }
    bouton.classList.add("retournee");
    bouton.parentNode.classList.add("visible");          // ses deux boutons apparaissent
    var o = trouver(bouton.dataset.cle);
    bouton.setAttribute("aria-label", o.titre + ", " + o.employeur + ", " + V.RARETES[o.rarete]);
    if (o.rarete === "legendaire" || o.rarete === "epique") {
      scene.classList.remove("eclat-epique", "eclat-legendaire");
      void scene.offsetWidth;                               // relance l'animation
      scene.classList.add("eclat-" + o.rarete);
    }
    choisir(o.cle);
    if (!scene.querySelector(".carte:not(.retournee)")) {
      var actions = scene.querySelector(".scene-actions");
      actions.innerHTML = '<button type="button" class="bouton" id="terminer">Ranger ce booster</button>';
    }
  }

  function toutRetourner() {
    var cachees = Array.prototype.slice.call(scene.querySelectorAll(".carte:not(.retournee)"));
    cachees.forEach(function (b, i) { setTimeout(function () { retourner(b); }, mouvementReduit ? 0 : i * 420); });
  }

  function choisir(cle) {
    choisie = cle;
    scene.querySelectorAll(".carte").forEach(function (b) { b.classList.toggle("choisie", b.dataset.cle === cle); });
    var o = trouver(cle), f = V.suivi[cle] || {};
    var liste = function (rs, vide) {
      return rs.length ? "<ul>" + rs.map(function (r) { return "<li>" + esc(r.texte) + "</li>"; }).join("") + "</ul>" : '<p class="rien">' + vide + "</p>";
    };
    var points = (o.score_detail || []).map(function (d) {
      return "<li><span>" + esc(d[0]) + '</span><b class="' + (d[1] > 0 ? "plus" : "moins") + '">' + (d[1] > 0 ? "+" : "−") + Math.abs(d[1]) + "</b></li>";
    }).join("");
    var statut = f.candidature ? '<span class="statut">Dans ton album</span>' : f.statut === "retenue" ? '<span class="statut">Retenue</span>'
      : f.statut === "ecartee" ? '<span class="statut retiree">Écartée</span>' : "";
    var astuce = f.candidature ? "Elle est dans ton album : fais-la avancer à chaque relance ou entretien."
      : visitees[cle] ? "Tu as postulé ? Range la carte dans ton album pour suivre ta candidature."
      : "Lis l'offre en entier, postule sur le site de l'employeur, puis reviens cliquer « J'ai postulé » : la carte rejoint ton album.";
    detail.innerHTML =
      '<div class="detail-carte r-' + esc(o.rarete) + '">' +
        '<p class="detail-qui"><b>' + esc(o.employeur) + "</b> · " + esc(o.famille || "") + "</p>" +
        "<h3>" + esc(o.titre) + statut + "</h3>" +
        '<div class="detail-principal">' +
          '<a class="bouton grand voir" data-voir="' + esc(cle) + '" href="' + esc(o.lien) + '" target="_blank" rel="noopener noreferrer">Voir l\'offre ↗</a>' +
          (f.candidature ? '<span class="bouton grand fait">✓ Dans ton album</span>'
            : '<button type="button" class="bouton grand postuler' + (visitees[cle] ? " a-faire" : "") + '" data-action="postuler">J\'ai postulé : ranger dans l\'album</button>') +
        "</div>" +
        '<p class="detail-astuce">' + esc(astuce) + "</p>" +
        '<div class="detail-colonnes">' +
          '<div><h4>Ce qui colle</h4>' + liste(o.colle || [], "Rien de repéré dans la fiche.") + "</div>" +
          '<div><h4>Ce qui coince</h4>' + liste(o.coince || [], "Rien de repéré dans la fiche.") + "</div>" +
          '<div class="pourquoi"><h4>Pourquoi ' + o.score + " sur 100</h4><ul>" + points + "</ul></div>" +
        "</div>" +
        (o.extrait ? '<p class="detail-extrait">' + esc(o.extrait) + "</p>" : "") +
        '<div class="detail-actions">' +
          '<span class="detail-actions-titre">Pas pour tout de suite ?</span>' +
          '<button type="button" class="bouton-secondaire reduit" data-action="retenue">Retenir pour plus tard</button>' +
          '<button type="button" class="bouton-secondaire reduit" data-action="ecartee">Écarter</button>' +
        "</div>" +
      "</div>";
  }

  function fermer() {
    fond.hidden = true;
    document.body.classList.remove("scene-ouverte");
    enCours = null;
    toutRendre();
    if (retourDuFocus && document.contains(retourDuFocus)) retourDuFocus.focus(); else $("boosters").scrollIntoView();
  }

  scene.addEventListener("click", function (e) {
    if (e.target.closest("#paquet-ouvert")) { dechirer(); return; }
    if (e.target.closest("#tout-retourner")) { toutRetourner(); return; }
    if (e.target.closest("#terminer")) { fermer(); return; }
    var voir = e.target.closest("[data-voir]");
    if (voir) { marquerVisitee(voir.dataset.voir); return; }   // le lien s'ouvre dans un autre onglet
    var p = e.target.closest("[data-postuler]");
    if (p) { choisir(p.dataset.postuler); demanderPostuler(p.dataset.postuler); return; }
    var b = e.target.closest(".carte"); if (b) retourner(b);
  });
  function marquerVisitee(cle) {
    visitees[cle] = true;
    setTimeout(function () { majActions(cle); if (choisie === cle) choisir(cle); }, 0);
  }
  detail.addEventListener("click", function (e) {
    var voir = e.target.closest("[data-voir]");
    if (voir) { marquerVisitee(voir.dataset.voir); return; }
    var b = e.target.closest("[data-action]"); if (!b || !choisie) return;
    if (b.dataset.action === "postuler") { demanderPostuler(choisie); return; }
    V.poserStatut(choisie, b.dataset.action); V.rendre(); choisir(choisie); majActions(choisie);
  });
  $("scene-fermer").addEventListener("click", fermer);
  document.addEventListener("keydown", function (e) {
    if (fond.hidden) return;
    if (e.key === "Escape" && !$("dialogue-postuler").open) { e.preventDefault(); fermer(); }
  });

  // ------------------------------------------------------------ « J'ai postulé »
  var dialogue = $("dialogue-postuler"), aPostuler = null;
  function demanderPostuler(cle) {
    var o = trouver(cle), f = V.suivi[cle] || {};
    aPostuler = cle;
    $("postuler-offre").textContent = o.titre + " · " + o.employeur;
    $("postuler-le").value = new Date().toISOString().slice(0, 10);
    $("postuler-note").value = f.note || "";
    dialogue.showModal();
  }
  dialogue.addEventListener("close", function () {
    if (dialogue.returnValue !== "ok" || !aPostuler) { aPostuler = null; return; }
    var f = C.postuler(V.suivi[aPostuler] || {}, $("postuler-le").value, $("postuler-note").value.trim());
    if (!f.note) delete f.note;
    V.enregistrer(aPostuler, f);
    var cle = aPostuler; aPostuler = null;
    V.rendre();
    if (!fond.hidden) {
      choisir(cle); majActions(cle);
      var b = scene.querySelector('.carte[data-cle="' + CSS.escape(cle) + '"]');
      if (b) { b.classList.add("rangee"); setTimeout(function () { b.classList.remove("rangee"); }, 900); }
    }
  });

  // ------------------------------------------------------------ l'album
  function album() {
    var cartes = C.album(V.offres, V.suivi), b = C.bilan(V.offres, V.suivi);
    $("album-titre").textContent = b.total ? b.total + (b.total > 1 ? " candidatures dans ton album." : " candidature dans ton album.")
      : "Ton album est vide.";
    $("album-sous").textContent = b.total
      ? "Fais avancer chaque carte : relance, entretien, offre. Une carte dont l'offre a disparu du site est marquée clôturée : c'est souvent le moment de relancer."
      : "Une carte entre ici quand tu postules : bouton « J'ai postulé » sous une carte d'un booster, ou dans la liste des offres.";
    $("album-bilan").innerHTML = b.total ? C.ETAPES.map(function (e) {
      return '<div class="bilan-etape e-' + e + '"><b>' + b[e] + "</b><span>" + esc(C.LIBELLES_ETAPES[e].toLowerCase()) + "</span></div>";
    }).join("") : "";
    $("album-cartes").innerHTML = cartes.map(function (o) {
      var c = V.suivi[o.cle].candidature, rang = C.ETAPES.indexOf(c.etape), suivante = C.ETAPES[rang + 1];
      return '<div class="case-album">' + carte(o, { retournee: true, mini: true }) +
        '<ol class="frise" aria-label="Étapes">' + C.ETAPES.map(function (e, i) {
          return '<li class="' + (i <= rang ? "faite" : "") + '" title="' + esc(C.LIBELLES_ETAPES[e]) + '"></li>'; }).join("") + "</ol>" +
        '<div class="case-actions">' +
          (suivante ? '<button type="button" class="bouton reduit" data-avancer="' + esc(o.cle) + '">' + esc(C.LIBELLES_ETAPES[suivante]) + "</button>" : "") +
          (c.historique.length > 1 ? '<button type="button" class="lien plein" data-reculer="' + esc(o.cle) + '" aria-label="Annuler la dernière étape">Annuler</button>' : "") +
        "</div></div>";
    }).join("");
  }

  $("album-cartes").addEventListener("click", function (e) {
    var a = e.target.closest("[data-avancer]"), r = e.target.closest("[data-reculer]");
    if (a || r) {
      var cle = (a || r).dataset[a ? "avancer" : "reculer"], f = V.suivi[cle];
      if (a) C.avancer(f); else C.reculer(f);
      V.enregistrer(cle, f); album();
      return;
    }
    var b = e.target.closest(".carte");
    if (b) { var o = trouver(b.dataset.cle); window.open(o.lien, "_blank", "noopener"); }
  });

  // ------------------------------------------------------------ ensemble
  function toutRendre() { etagere(); album(); }
  document.addEventListener("veille:rendu", function () { if (fond.hidden) toutRendre(); });
  toutRendre();
})();
