// Tests de la logique des cartes (modele/collection.js). Lancer : node --test tests/js
const { test } = require("node:test");
const assert = require("node:assert/strict");
const C = require("../../modele/collection.js");

function offre(cle, score, vu_le = "2026-10-20", champs = {}) {
  return { cle, score, vu_le, rarete: "rare", ...champs };
}

test("cinq cartes font un booster, le reste attend dans la pochette", () => {
  const offres = [1, 2, 3, 4, 5, 6, 7].map((i) => offre("o" + i, i * 10));
  const r = C.boosters(offres, {}, {});
  assert.equal(r.prets.length, 1);
  assert.equal(r.prets[0].length, 5);
  assert.deepEqual(r.pochette.map((o) => o.cle), ["o6", "o7"]);
});

test("moins de cinq cartes : aucun booster, tout attend", () => {
  const r = C.boosters([offre("a", 90), offre("b", 95)], {}, {});
  assert.equal(r.prets.length, 0);
  assert.equal(r.pochette.length, 2);
});

test("douze cartes : deux boosters et deux en attente", () => {
  const offres = Array.from({ length: 12 }, (_, i) => offre("o" + String(i).padStart(2, "0"), 50));
  const r = C.boosters(offres, {}, {});
  assert.equal(r.prets.length, 2);
  assert.equal(r.pochette.length, 2);
});

test("les plus anciennes cartes partent d'abord, la plus rare sort en dernier", () => {
  const offres = [
    offre("neuve", 99, "2026-10-25"),
    offre("a", 80, "2026-10-01"), offre("b", 20, "2026-10-01"), offre("c", 60, "2026-10-02"),
    offre("d", 40, "2026-10-03"), offre("e", 95, "2026-10-04"),
  ];
  const r = C.boosters(offres, {}, {});
  assert.deepEqual(r.prets[0].map((o) => o.cle), ["b", "d", "c", "a", "e"]);
  assert.deepEqual(r.pochette.map((o) => o.cle), ["neuve"]);
});

test("aucun quota : un booster sans carte rare reste un booster", () => {
  const offres = Array.from({ length: 5 }, (_, i) => offre("o" + i, 30, "2026-10-20", { rarete: "commune" }));
  assert.equal(C.boosters(offres, {}, {}).prets.length, 1);
});

test("ne sortent pas des boosters : les cartes ouvertes, suivies, retirées ou de page maison", () => {
  const offres = [
    offre("ouverte", 50), offre("suivie", 50), offre("retiree", 50, "2026-10-20", { retiree: true }),
    offre("page", 50, "2026-10-20", { page: true }), offre("libre", 50),
  ];
  const r = C.boosters(offres, { suivie: { statut: "ecartee" } }, { ouverte: "2026-10-21" });
  assert.deepEqual(r.pochette.map((o) => o.cle), ["libre"]);
});

test("ouvrir un booster marque ses cartes comme vues", () => {
  const offres = [1, 2, 3, 4, 5].map((i) => offre("o" + i, 50));
  const ouvertes = {};
  C.ouvrir(C.boosters(offres, {}, ouvertes).prets[0], ouvertes, "2026-10-26");
  assert.equal(Object.keys(ouvertes).length, 5);
  assert.equal(C.boosters(offres, {}, ouvertes).prets.length, 0);
});

test("seul « J'ai postulé » fait entrer une carte dans l'album", () => {
  const offres = [offre("vue", 90), offre("retenue", 90), offre("postulee", 50)];
  const suivi = { retenue: { statut: "retenue" }, postulee: C.postuler({}, "2026-10-26", "via le site") };
  assert.deepEqual(C.album(offres, suivi).map((o) => o.cle), ["postulee"]);
  assert.equal(suivi.postulee.statut, "postule");
  assert.equal(suivi.postulee.note, "via le site");
});

test("les étapes avancent dans l'ordre puis s'arrêtent à l'offre", () => {
  const fiche = C.postuler({}, "2026-10-01");
  assert.ok(C.avancer(fiche, "2026-10-08"));
  assert.ok(C.avancer(fiche, "2026-10-15"));
  assert.ok(C.avancer(fiche, "2026-10-20"));
  assert.equal(fiche.candidature.etape, "offre");
  assert.equal(C.avancer(fiche, "2026-10-21"), false);
  assert.deepEqual(fiche.candidature.historique.map((h) => h.etape), C.ETAPES);
});

test("reculer annule la dernière étape, pas la candidature", () => {
  const fiche = C.postuler({}, "2026-10-01");
  C.avancer(fiche, "2026-10-08");
  assert.ok(C.reculer(fiche));
  assert.equal(fiche.candidature.etape, "postule");
  assert.equal(C.reculer(fiche), false);
});

test("le bilan compte les cartes qui ont atteint chaque étape", () => {
  const offres = [offre("a", 50), offre("b", 50), offre("c", 50)];
  const suivi = { a: C.postuler({}, "2026-10-01"), b: C.postuler({}, "2026-10-02"), c: C.postuler({}, "2026-10-03") };
  C.avancer(suivi.b); C.avancer(suivi.c); C.avancer(suivi.c);
  assert.deepEqual(C.bilan(offres, suivi), { total: 3, postule: 3, relance: 2, entretien: 1, offre: 0 });
});
