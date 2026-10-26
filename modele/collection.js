/* La logique des cartes, sans affichage : quelles offres forment un booster, ce qui
   attend dans la pochette, ce qui entre dans l'album, et les étapes d'une candidature.
   Testée par tests/js/collection.test.js (node --test tests/js). */
var Collection = (function () {
  "use strict";

  var TAILLE_BOOSTER = 5;

  // Les étapes d'une candidature, dans l'ordre : la carte change d'aspect à chacune.
  var ETAPES = ["postule", "relance", "entretien", "offre"];
  var LIBELLES_ETAPES = { postule: "Postulé", relance: "Relancé", entretien: "Entretien", offre: "Offre reçue" };

  function aujourdhui() { return new Date().toISOString().slice(0, 10); }

  // Une carte peut sortir d'un booster si elle n'a jamais été vue : pas encore ouverte,
  // sans statut (retenue, postulé, écartée), encore en ligne, et lue par un flux (pas une page maison).
  function aOuvrir(o, suivi, ouvertes) {
    return !o.page && !o.retiree && !ouvertes[o.cle] && !(suivi[o.cle] || {}).statut;
  }

  // Les boosters prêts (des paquets de 5, les plus anciennes cartes d'abord) et la pochette :
  // ce qui reste, moins de 5 cartes, attend les prochaines offres. Aucun quota de rareté :
  // un booster sans carte rare est normal. Dans un booster, la carte la plus rare sort en dernier.
  function boosters(offres, suivi, ouvertes, taille) {
    taille = taille || TAILLE_BOOSTER;
    var candidates = offres.filter(function (o) { return aOuvrir(o, suivi, ouvertes); })
      .sort(function (a, b) { return (a.vu_le || "").localeCompare(b.vu_le || "") || a.cle.localeCompare(b.cle); });
    var prets = [];
    for (var i = 0; i + taille <= candidates.length; i += taille) {
      prets.push(candidates.slice(i, i + taille).sort(function (a, b) { return a.score - b.score; }));
    }
    return { prets: prets, pochette: candidates.slice(prets.length * taille), taille: taille };
  }

  // Ouvrir un booster marque ses cartes comme vues : elles restent dans la liste des offres,
  // mais n'entrent dans l'album qu'au clic sur « J'ai postulé ».
  function ouvrir(booster, ouvertes, le) {
    booster.forEach(function (o) { ouvertes[o.cle] = le || aujourdhui(); });
    return ouvertes;
  }

  // Poser une candidature : la fiche de suivi reçoit le statut « postule » et son historique.
  function postuler(fiche, le, note) {
    fiche = fiche || {};
    le = le || aujourdhui();
    fiche.statut = "postule";
    fiche.candidature = { etape: "postule", le: le, historique: [{ etape: "postule", le: le }] };
    if (note) fiche.note = note;
    fiche.maj = le;
    return fiche;
  }

  // Passer à l'étape suivante (postulé → relancé → entretien → offre). Rend false à la dernière.
  function avancer(fiche, le) {
    var c = fiche && fiche.candidature;
    if (!c) return false;
    var i = ETAPES.indexOf(c.etape);
    if (i < 0 || i === ETAPES.length - 1) return false;
    le = le || aujourdhui();
    c.etape = ETAPES[i + 1];
    c.historique.push({ etape: c.etape, le: le });
    fiche.maj = le;
    return true;
  }

  // Revenir à l'étape d'avant (un clic de trop). À la première étape, rien ne change.
  function reculer(fiche) {
    var c = fiche && fiche.candidature;
    if (!c || c.historique.length < 2) return false;
    c.historique.pop();
    c.etape = c.historique[c.historique.length - 1].etape;
    return true;
  }

  // L'album : seulement les offres où l'on a postulé, les plus récentes candidatures d'abord.
  function album(offres, suivi) {
    return offres.filter(function (o) { return (suivi[o.cle] || {}).candidature; })
      .sort(function (a, b) { return suivi[b.cle].candidature.le.localeCompare(suivi[a.cle].candidature.le) || b.score - a.score; });
  }

  // Les compteurs de l'album : combien de cartes ont atteint chaque étape.
  function bilan(offres, suivi) {
    var compte = { total: 0, postule: 0, relance: 0, entretien: 0, offre: 0 };
    album(offres, suivi).forEach(function (o) {
      var rang = ETAPES.indexOf(suivi[o.cle].candidature.etape);
      compte.total += 1;
      for (var i = 0; i <= rang; i++) compte[ETAPES[i]] += 1;
    });
    return compte;
  }

  return { TAILLE_BOOSTER: TAILLE_BOOSTER, ETAPES: ETAPES, LIBELLES_ETAPES: LIBELLES_ETAPES,
           aOuvrir: aOuvrir, boosters: boosters, ouvrir: ouvrir, postuler: postuler, avancer: avancer,
           reculer: reculer, album: album, bilan: bilan };
})();
if (typeof module !== "undefined") module.exports = Collection;
