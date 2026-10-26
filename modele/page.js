/* Tableau de la veille d'offres : rendu, filtres, tri, suivi.
   Les données arrivent dans <script id="donnees"> (écrites par tableau.py).
   Le suivi (statut et note par offre) et les derniers filtres restent dans le
   localStorage de ce navigateur ; la page marche aussi sans. */
(function () {
  "use strict";

  var D = JSON.parse(document.getElementById("donnees").textContent);
  var CIBLE_MIN = D.cible[0], CIBLE_MAX = D.cible[1];  // la cible salariale, lue dans le profil
  var CIBLE_TEXTE = D.cible_texte, DEVISE = D.devise;  // « 45 à 55 k€ », « EUR »
  // La jauge de salaire va de la moitié du bas de la cible au double du haut, en dizaines de milliers.
  var ECHELLE_MIN = Math.floor(CIBLE_MIN / 2 / 10000) * 10000;
  var ECHELLE_MAX = Math.ceil(CIBLE_MAX * 2 / 10000) * 10000;
  var CLE_SUIVI = "veille-offres-suivi", CLE_FILTRES = "veille-offres-filtres";

  // ---------------------------------------------------------------- outils
  function $(id) { return document.getElementById(id); }
  function esc(t) {
    return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function sansAccents(t) { return (t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); }
  function lire(cle, defaut) {
    try { var v = localStorage.getItem(cle); return v ? JSON.parse(v) : defaut; } catch (e) { return defaut; }
  }
  function ecrire(cle, valeur) { try { localStorage.setItem(cle, JSON.stringify(valeur)); } catch (e) { /* rien */ } }

  var mois = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short", year: "numeric" });
  var moisLong = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long", year: "numeric" });
  function enDate(iso) { var p = (iso || "").split("-"); return p.length === 3 ? new Date(+p[0], p[1] - 1, +p[2]) : null; }
  function dateCourte(iso) { var d = enDate(iso); return d ? mois.format(d) : ""; }
  function dateLongue(iso) { var d = enDate(iso); return d ? moisLong.format(d) : ""; }
  function jours(iso) {
    var d = enDate(iso); if (!d) return null;
    var auj = new Date(); auj.setHours(0, 0, 0, 0);
    return Math.round((auj - d) / 86400000);
  }
  function relatif(iso) {
    var j = jours(iso);
    if (j === null) return "date inconnue";
    if (j <= 0) return "aujourd'hui";
    if (j === 1) return "hier";
    if (j < 7) return "il y a " + j + " j";
    if (j < 60) return "il y a " + Math.round(j / 7) + " sem.";
    if (j < 730) return "il y a " + Math.round(j / 30) + " mois";
    return "il y a " + Math.round(j / 365) + " ans";
  }
  function initiales(nom) {
    var mots = nom.replace(/[^\p{L}\p{N} ]/gu, " ").trim().split(/\s+/);
    return (mots.length > 1 ? mots[0][0] + mots[1][0] : nom.slice(0, 2)).toUpperCase();
  }
  function nombre(n) { return new Intl.NumberFormat("fr-FR").format(n); }
  var NOMS_ATS = { ashby: "Ashby", lever: "Lever", greenhouse: "Greenhouse", smartrecruiters: "SmartRecruiters",
                   teamtailor: "Teamtailor", page: "page carrière" };

  // ------------------------------------------------------------ les offres
  var passages = D.passages || [];
  var dernier = passages.length ? passages[passages.length - 1].date
    : D.offres.reduce(function (m, o) { return o.vu_le > m ? o.vu_le : m; }, "");
  var plusieursPassages = new Set(passages.map(function (p) { return p.date; })).size > 1;

  var offres = D.offres.map(function (o) {
    var lieux = Array.from(new Set((o.lieu || "").split(" / ").filter(Boolean)));
    var memeDevise = (o.devise || "EUR") === DEVISE;
    var bas = o.salaire_min || o.salaire_max;
    o.lieux = lieux;
    o.ref = o.publiee_le || o.vu_le;
    o.colle = o.colle || []; o.coince = o.coince || [];
    o.score = o.page ? -1 : o.score;   // calculé par score.py ; une page maison n'a pas de score
    o.retiree = !!(o.en_ligne_le && dernier && o.en_ligne_le < dernier);
    o.comparable = memeDevise && !!o.salaire_max;   // un salaire qu'on peut placer face à la cible
    o.cible = o.comparable && o.salaire_max >= CIBLE_MIN && bas <= CIBLE_MAX;
    o.souple = /remote|hybride/.test(o.mode || "") || /remote|hybrid/i.test(o.lieu || "");
    o.texte = sansAccents([o.employeur, o.titre, o.lieu, o.equipe, o.famille, o.contrat, o.extrait,
      o.colle.map(function (r) { return r.tag; }).join(" "), o.coince.map(function (r) { return r.tag; }).join(" ")].join(" "));
    return o;
  });

  var suivi = lire(CLE_SUIVI, {});
  function statut(o) { return (suivi[o.cle] || {}).statut || ""; }

  // ------------------------------------------------------------ les filtres
  var filtres = Object.assign({ periode: "tout", suivi: "a-trier", tri: "adequation", famille: "",
    salaire: false, cible: false, souple: false, retirees: false }, lire(CLE_FILTRES, {}));
  var employeurChoisi = "";
  var recherche = "";

  function garde(o) {
    var s = statut(o);
    if (filtres.suivi === "a-trier" && s) return false;
    if (filtres.suivi === "retenue" && s !== "retenue") return false;
    if (filtres.suivi === "postule" && s !== "postule") return false;
    if (filtres.suivi === "ecartee" && s !== "ecartee") return false;
    if (filtres.periode === "passage" && o.vu_le !== dernier) return false;
    if (filtres.periode === "30" && !(jours(o.ref) <= 30)) return false;
    if (filtres.famille && o.famille !== filtres.famille) return false;
    if (filtres.salaire && !o.salaire_max) return false;
    if (filtres.cible && !o.cible) return false;
    if (filtres.souple && !o.souple) return false;
    if (!filtres.retirees && o.retiree && s !== "postule") return false;
    if (employeurChoisi && o.employeur !== employeurChoisi) return false;
    if (recherche) {
      var mots = sansAccents(recherche).split(/\s+/).filter(Boolean);
      for (var i = 0; i < mots.length; i++) if (o.texte.indexOf(mots[i]) < 0) return false;
    }
    return true;
  }

  var TRIS = {
    adequation: function (a, b) { return b.score - a.score || b.colle.length - a.colle.length || (b.ref || "").localeCompare(a.ref || ""); },
    publication: function (a, b) { return (b.ref || "").localeCompare(a.ref || ""); },
    salaire: function (a, b) { return (b.comparable ? b.salaire_max : -1) - (a.comparable ? a.salaire_max : -1) || (b.salaire_max || 0) - (a.salaire_max || 0); },
    employeur: function (a, b) { return a.employeur.localeCompare(b.employeur, "fr") || a.titre.localeCompare(b.titre, "fr"); }
  };

  // ------------------------------------------------------------ le rendu
  var LIBELLES = { retenue: "Retenue", postule: "Postulé", ecartee: "Écartée" };
  var RARETES = { legendaire: "Légendaire", epique: "Épique", rare: "Rare", peu_commune: "Peu commune", commune: "Commune" };

  function jauge(o) {
    if (!o.comparable) return "";
    function pos(v) { return Math.max(0, Math.min(100, (v - ECHELLE_MIN) / (ECHELLE_MAX - ECHELLE_MIN) * 100)); }
    var bas = o.salaire_min || o.salaire_max;
    var g = pos(bas), d = pos(o.salaire_max);
    if (d - g < 3) { g = Math.max(0, Math.min(g, 97)); d = g + 3; }   // une fourchette étroite reste visible
    var milieuCible = (pos(CIBLE_MIN) + pos(CIBLE_MAX)) / 2;
    return '<div class="jauge" title="Fourchette affichée face à ta cible de ' + CIBLE_TEXTE + '">' +
      '<span class="plage" style="left:' + g + '%;width:' + (d - g) + '%"></span>' +
      '<span class="cible" style="left:' + pos(CIBLE_MIN) + '%;width:' + (pos(CIBLE_MAX) - pos(CIBLE_MIN)) + '%"></span></div>' +
      '<div class="jauge-legende"><span>' + Math.round(ECHELLE_MIN / 1000) + ' k</span><span class="repere" style="left:' + milieuCible + '%">cible</span><span>' + Math.round(ECHELLE_MAX / 1000) + " k</span></div>";
  }

  function ligne(o) {
    var s = statut(o), note = (suivi[o.cle] || {}).note || "";
    var lieu = o.lieux.slice(0, 3).join(", ") + (o.lieux.length > 3 ? " +" + (o.lieux.length - 3) : "");
    var meta = [lieu, o.contrat, o.mode, o.equipe].filter(Boolean).map(function (m) { return "<span>" + esc(m) + "</span>"; }).join("");
    var tags = o.page ? '<span class="tag coince">page maison, à lire à la main</span>'
      : o.colle.map(function (r) { return '<span class="tag colle">' + esc(r.tag) + "</span>"; }).join("") +
        o.coince.map(function (r) { return '<span class="tag coince">' + esc(r.tag) + "</span>"; }).join("");
    var chip = (s ? '<span class="statut">' + LIBELLES[s] + "</span>" : "") +
               (o.retiree ? '<span class="statut retiree">retirée du site</span>' : "");
    var liste = function (rs, classe) {
      return rs.length ? "<ul>" + rs.map(function (r) { return "<li>" + esc(r.texte) + "</li>"; }).join("") + "</ul>"
        : '<p class="rien">Rien de repéré dans la fiche.</p>';
    };
    var dates = [o.publiee_le ? "publiée le " + dateLongue(o.publiee_le) : "date de publication non donnée",
      "vue par la veille le " + dateLongue(o.vu_le),
      o.retiree ? "plus en ligne depuis le " + dateLongue(o.en_ligne_le) : "encore en ligne le " + dateLongue(o.en_ligne_le || o.vu_le),
      "source " + (NOMS_ATS[o.ats] || o.ats || "")].join(" · ");
    var boutons = ["retenue", "postule", "ecartee", ""].map(function (v) {
      var lib = v ? (v === "retenue" ? "Retenir" : v === "postule" ? "Postulé" : "Écarter") : "À trier";
      return '<button type="button" data-statut="' + v + '"' + (s === v ? ' class="actif" aria-pressed="true"' : ' aria-pressed="false"') + ">" + lib + "</button>";
    }).join("");

    return '<li class="offre' + (o.retiree ? " retiree" : "") + (s === "ecartee" ? " ecartee" : "") +
      '" tabindex="0" data-cle="' + esc(o.cle) + '">' +
      '<div class="quand"><span class="relatif">' + relatif(o.ref) + '</span><span class="absolu">' + esc(dateCourte(o.ref)) + "</span>" +
        (plusieursPassages && o.vu_le === dernier ? '<span class="neuf">nouvelle</span>' : "") + "</div>" +
      '<div class="mono" aria-hidden="true">' + esc(initiales(o.employeur)) + "</div>" +
      '<div class="corps"><div class="qui"><b>' + esc(o.employeur) + "</b> · " + esc(o.famille) + "</div>" +
        '<h3 class="poste">' + esc(o.titre) + chip + "</h3>" +
        '<div class="meta">' + meta + "</div>" +
        '<div class="tags">' + (o.page ? "" : '<span class="rarete r-' + esc(o.rarete) + '" title="Score d’adéquation à ton profil">' +
          RARETES[o.rarete] + " · " + o.score + "</span>") + tags + "</div></div>" +
      '<div class="paie">' + (o.salaire ? '<div class="montant">' + esc(o.salaire.replace(" à ", "–")) + "</div>" +
          (o.comparable ? "" : '<span class="devise">autre devise</span>') : '<div class="montant absent">salaire non affiché</div>') +
        jauge(o) + "</div>" +
      '<div class="detail">' +
        (o.page ? "" : '<div class="raisons"><div class="colle"><h3>Ce qui colle</h3>' + liste(o.colle) +
          '</div><div class="coince"><h3>Ce qui coince</h3>' + liste(o.coince) + "</div></div>") +
        (o.page ? "" : '<div class="pourquoi"><h3>Pourquoi ' + o.score + " sur 100</h3><ul>" +
          (o.score_detail || []).map(function (d) {
            return '<li><span>' + esc(d[0]) + '</span><b class="' + (d[1] > 0 ? "plus" : "moins") + '">' + (d[1] > 0 ? "+" : "−") + Math.abs(d[1]) + "</b></li>";
          }).join("") + "</ul></div>") +
        (o.extrait ? '<p class="extrait">' + esc(o.extrait) + "</p>" : "") +
        '<p class="dates">' + esc(dates) + "</p>" +
        '<div class="actions-offre"><a class="bouton reduit" href="' + esc(o.lien) + '" target="_blank" rel="noopener noreferrer">Ouvrir l\'offre ↗</a>' +
          '<div class="segment suivi-offre" role="group" aria-label="Suivi de l\'offre">' + boutons + "</div></div>" +
        '<textarea class="champ note-perso" placeholder="Note pour toi : contact, date de relance, ce que tu as envoyé…">' + esc(note) + "</textarea>" +
      "</div></li>";
  }

  var ouverte = null;

  function rendre() {
    var vues = offres.filter(garde).sort(TRIS[filtres.tri] || TRIS.adequation);
    $("liste").innerHTML = vues.map(ligne).join("");
    $("vide").hidden = vues.length > 0;
    var c = vues.length + (vues.length > 1 ? " offres" : " offre");
    $("compte").innerHTML = esc(c) + (employeurChoisi ? ' · <button class="lien plein" id="sans-employeur" type="button">' + esc(employeurChoisi) + " ✕</button>" : "");
    if (ouverte) {
      var li = $("liste").querySelector('[data-cle="' + CSS.escape(ouverte) + '"]');
      if (li) li.classList.add("ouverte"); else ouverte = null;
    }
    chiffres();
    document.dispatchEvent(new Event("veille:rendu"));   // les cartes se mettent à jour (cartes.js)
  }

  function chiffres() {
    var enLigne = offres.filter(function (o) { return !o.retiree; });
    var aTrier = enLigne.filter(function (o) { return !statut(o); }).length;
    var avecSalaire = enLigne.filter(function (o) { return o.salaire_max; });
    var dansLaDevise = avecSalaire.filter(function (o) { return o.comparable; }).length;
    var cible = enLigne.filter(function (o) { return o.cible; }).length;
    $("chiffres").innerHTML =
      '<div class="chiffre-hero moyen"><div class="valeur">' + nombre(aTrier) + '</div><div class="legende">offres à trier</div><div class="contexte">sur ' + nombre(enLigne.length) + " encore en ligne</div></div>" +
      '<div class="chiffre-hero moyen"><div class="valeur">' + nombre(avecSalaire.length) + '</div><div class="legende">affichent un salaire</div><div class="contexte">dont ' + nombre(dansLaDevise) + " en " + esc(DEVISE) + "</div></div>" +
      '<div class="chiffre-hero moyen"><div class="valeur degrade-texte">' + nombre(cible) + '</div><div class="legende">' + (cible > 1 ? "recoupent" : "recoupe") + ' ' + CIBLE_TEXTE + '</div><div class="contexte">fourchette affichée qui touche ta cible</div></div>';
  }

  function entete() {
    var p = passages[passages.length - 1];
    var nouvelles = p ? p.nouvelles : offres.length;
    var heure = p && p.heure ? " à " + p.heure.replace(":", " h ") : "";
    $("tete-date").textContent = dernier ? "Passage du " + dateLongue(dernier) + heure : "Aucun passage";
    var enLigne = offres.filter(function (o) { return !o.retiree; }).length;
    $("tete-titre").textContent = plusieursPassages
      ? (nouvelles ? nouvelles + (nouvelles > 1 ? " offres nouvelles" : " offre nouvelle") + " cette semaine, " + enLigne + " en ligne."
                   : "Rien de nouveau cette semaine. " + enLigne + " offres en ligne.")
      : enLigne + " offres retenues au premier passage.";
    var lus = p ? p.employeurs_lus : 0, suivis = D.employeurs.length;
    $("tete-sous").textContent = lus + " employeurs lus par leur flux public sur " + suivis +
      " suivis. Hors LinkedIn, Indeed et Glassdoor ; rien n'est envoyé nulle part.";
  }

  function manuels() {
    var p = passages[passages.length - 1] || { manuels: [] };
    var apec = '<div class="tuile"><p class="t-label">APEC</p><p class="t-tuile-copie">Recherche protégée par un captcha. Trois requêtes à lancer toi-même.</p><div class="liens">' +
      D.apec.map(function (q) {
        return '<a class="lien externe" target="_blank" rel="noopener noreferrer" href="https://www.apec.fr/candidat/recherche-emploi.html/emploi?motsCles=' + encodeURIComponent(q) + '">' + esc(q) + "</a>";
      }).join("") + "</div></div>";
    $("manuels").innerHTML = apec + (p.manuels || []).map(function (m) {
      return '<div class="tuile"><p class="t-label">' + esc(m.employeur) + '</p><p class="t-tuile-copie">' + esc(m.note.charAt(0).toUpperCase() + m.note.slice(1)) + '.</p>' +
        '<div class="liens"><a class="lien externe" target="_blank" rel="noopener noreferrer" href="' + esc(m.lien) + '">Ouvrir la page</a></div></div>';
    }).join("");
  }

  function employeurs() {
    var compte = {};
    offres.forEach(function (o) { if (!o.retiree) compte[o.employeur] = (compte[o.employeur] || 0) + 1; });
    var parFamille = {};
    D.employeurs.forEach(function (e) { (parFamille[e.famille] = parFamille[e.famille] || []).push(e); });
    var noms = Object.keys(parFamille);
    $("suivis-titre").textContent = D.employeurs.length + " employeurs suivis, en " + noms.length + " familles.";
    $("familles").innerHTML = noms.map(function (f) {
      return '<div class="famille"><h3>' + esc(f) + '</h3><div class="noms">' + parFamille[f].map(function (e) {
        var manuel = e.ats === "manuel";
        return '<button type="button" class="nom-employeur' + (manuel ? " manuel" : "") + '" data-employeur="' + esc(e.nom) + '">' +
          esc(e.nom) + '<span class="n">' + (manuel ? "" : (compte[e.nom] || 0)) + "</span></button>";
      }).join("") + "</div></div>";
    }).join("");
    var sel = $("f-famille");
    noms.sort(function (a, b) { return a.localeCompare(b, "fr"); }).forEach(function (f) {
      var opt = document.createElement("option"); opt.value = f; opt.textContent = f.charAt(0).toUpperCase() + f.slice(1); sel.appendChild(opt);
    });
  }

  function historique() {
    $("passages-titre").textContent = passages.length + (passages.length > 1 ? " passages" : " passage") + " depuis le " + dateLongue(passages.length ? passages[0].date : dernier) + ".";
    $("passages-lignes").innerHTML = passages.slice().reverse().map(function (p) {
      var err = (p.erreurs || []).map(function (e) { return e.employeur; }).join(", ") || "aucune";
      return "<tr><td>" + esc(dateLongue(p.date)) + "</td><td>" + esc(p.heure || "") + '</td><td class="nombre">' + p.nouvelles +
        '</td><td class="nombre">' + p.employeurs_lus + "</td><td>" + esc(err) + "</td></tr>";
    }).join("");
    $("pied").textContent = "Fichier refait le " + dateLongue(D.genere_le.slice(0, 10)) + " à " + D.genere_le.slice(11).replace(":", " h ") +
      ". Les statuts et les notes restent dans ce navigateur : ils ne partent nulle part.";
  }

  // ------------------------------------------------------------ le suivi
  function poserStatut(cle, valeur) {
    var f = suivi[cle] || {};
    if (valeur === "postule" && !f.candidature) {
      f = Collection.postuler(f);   // « Postulé » fait entrer la carte dans l'album
    } else if (valeur !== "postule" && f.candidature && f.candidature.historique.length < 2) {
      delete f.candidature;         // un clic de trop sur « Postulé », rattrapé avant toute relance
    }
    if (valeur) f.statut = valeur; else delete f.statut;
    f.maj = new Date().toISOString().slice(0, 10);
    enregistrer(cle, f);
  }
  // Range une fiche de suivi (statut, note, candidature) ; une fiche vide disparaît.
  function enregistrer(cle, f) {
    if (!f.statut && !f.note && !f.candidature) delete suivi[cle]; else suivi[cle] = f;
    ecrire(CLE_SUIVI, suivi);
  }

  // ------------------------------------------------------------ les contrôles
  function synchroniserControles() {
    [["f-periode", filtres.periode], ["f-suivi", filtres.suivi]].forEach(function (x) {
      $(x[0]).querySelectorAll("button").forEach(function (b) {
        var actif = b.value === x[1]; b.classList.toggle("actif", actif); b.setAttribute("aria-pressed", actif ? "true" : "false");
      });
    });
    $("f-famille").value = filtres.famille; $("f-tri").value = filtres.tri;
    ["salaire", "cible", "souple", "retirees"].forEach(function (k) { $("f-" + k).checked = !!filtres[k]; });
  }
  function changer(k, v) { filtres[k] = v; ecrire(CLE_FILTRES, filtres); rendre(); }

  $("f-periode").addEventListener("segment", function (e) { changer("periode", e.detail); });
  $("f-suivi").addEventListener("segment", function (e) { changer("suivi", e.detail); });
  $("f-famille").addEventListener("change", function (e) { changer("famille", e.target.value); });
  $("f-tri").addEventListener("change", function (e) { changer("tri", e.target.value); });
  ["salaire", "cible", "souple", "retirees"].forEach(function (k) {
    $("f-" + k).addEventListener("change", function (e) { changer(k, e.target.checked); });
  });
  var minuterie;
  $("recherche").addEventListener("input", function (e) {
    clearTimeout(minuterie); minuterie = setTimeout(function () { recherche = e.target.value.trim(); rendre(); }, 120);
  });
  $("raz").addEventListener("click", function () {
    filtres = { periode: "tout", suivi: "toutes", tri: filtres.tri, famille: "", salaire: false, cible: false, souple: false, retirees: true };
    employeurChoisi = ""; recherche = ""; $("recherche").value = "";
    ecrire(CLE_FILTRES, filtres); synchroniserControles(); rendre();
  });
  $("compte").addEventListener("click", function (e) {
    if (e.target.id === "sans-employeur") { employeurChoisi = ""; rendre(); }
  });
  $("familles").addEventListener("click", function (e) {
    var b = e.target.closest(".nom-employeur"); if (!b) return;
    employeurChoisi = b.dataset.employeur;
    filtres.suivi = "toutes"; filtres.periode = "tout"; filtres.famille = "";
    synchroniserControles(); rendre();
    $("offres").scrollIntoView({ behavior: "smooth" });
  });

  // Ouvrir, fermer, changer le statut, écrire une note
  var liste = $("liste");
  function basculer(li) {
    var deja = li.classList.contains("ouverte");
    liste.querySelectorAll(".offre.ouverte").forEach(function (x) { x.classList.remove("ouverte"); });
    if (!deja) { li.classList.add("ouverte"); ouverte = li.dataset.cle; } else ouverte = null;
  }
  liste.addEventListener("click", function (e) {
    var li = e.target.closest(".offre"); if (!li) return;
    var b = e.target.closest("[data-statut]");
    if (b) { poserStatut(li.dataset.cle, b.dataset.statut); rendre(); return; }
    if (e.target.closest("a, textarea, button")) return;
    if (e.target.closest(".detail") && li.classList.contains("ouverte")) return;
    basculer(li);
  });
  liste.addEventListener("input", function (e) {
    if (!e.target.classList.contains("note-perso")) return;
    var cle = e.target.closest(".offre").dataset.cle, f = suivi[cle] || {};
    f.note = e.target.value; f.maj = new Date().toISOString().slice(0, 10);
    enregistrer(cle, f);
  });

  // Clavier
  document.addEventListener("keydown", function (e) {
    var dansChamp = /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName);
    if (e.key === "/" && !dansChamp) { e.preventDefault(); $("recherche").focus(); return; }
    if (e.key === "Escape" && dansChamp) { document.activeElement.blur(); return; }
    if (dansChamp || e.metaKey || e.ctrlKey || e.altKey) return;
    var lignes = Array.from(liste.querySelectorAll(".offre"));
    var li = document.activeElement.closest && document.activeElement.closest(".offre");
    var i = lignes.indexOf(li);
    if (e.key === "j" || e.key === "k") {
      e.preventDefault();
      var cible = lignes[Math.max(0, Math.min(lignes.length - 1, i + (e.key === "j" ? 1 : -1)))] || lignes[0];
      if (cible) { cible.focus(); cible.scrollIntoView({ block: "nearest" }); }
      return;
    }
    if (!li) return;
    if (e.key === "Enter") { e.preventDefault(); basculer(li); }
    if (e.key === "o") { var a = li.querySelector("a.bouton"); if (a) window.open(a.href, "_blank", "noopener"); }
    var touches = { r: "retenue", p: "postule", x: "ecartee", u: "" };
    if (e.key in touches) {
      var cle = li.dataset.cle;
      poserStatut(cle, touches[e.key]); rendre();
      var suivante = liste.querySelector('[data-cle="' + CSS.escape(cle) + '"]') || liste.querySelectorAll(".offre")[Math.min(i, liste.children.length - 1)];
      if (suivante) suivante.focus();
    }
  });

  // La barre de filtres prend un filet quand elle colle sous la nav
  var barre = $("barre");
  window.addEventListener("scroll", function () { barre.classList.toggle("collee", barre.getBoundingClientRect().top <= 53); }, { passive: true });

  // Ce que cartes.js partage avec la liste : les offres, le suivi et de quoi le modifier.
  window.Veille = {
    offres: offres, suivi: suivi, lire: lire, ecrire: ecrire, enregistrer: enregistrer, poserStatut: poserStatut,
    rendre: rendre, esc: esc, initiales: initiales, dateCourte: dateCourte, dateLongue: dateLongue,
    RARETES: RARETES, NOMS_ATS: NOMS_ATS
  };

  $("f-cible-texte").textContent = CIBLE_TEXTE;
  entete(); manuels(); employeurs(); historique(); synchroniserControles(); rendre();
})();
