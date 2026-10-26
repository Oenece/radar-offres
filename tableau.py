"""Fabrique tableau.html : la vue filtrable de la veille d'offres.

Lit vus.json (les offres gardées) et passages.json (l'historique des passages)
dans le dossier des données du profil, et colle le tout dans un seul fichier HTML
qui s'ouvre sans serveur :
    modele/modele.html   le squelette de la page
    style/*.css          l'habillage Apple, le style maison, la grammaire Apple
    modele/page.css      ce qui est propre à ce tableau
    modele/page.js       le tri, les filtres, le suivi des offres

Le suivi (retenue, postulé, écartée, note) vit dans le navigateur (localStorage) :
il survit à chaque nouvelle génération du fichier, tant qu'on l'ouvre au même endroit.

Lancer seul :  python tableau.py --profil chemin/vers/profil.toml
(veille.py l'appelle déjà à chaque passage)
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent
STYLE = DOSSIER / "style"
MODELE = DOSSIER / "modele"
sys.path.insert(0, str(DOSSIER))
sys.dont_write_bytecode = True
import profil as module_profil  # noqa: E402
import score  # noqa: E402
from salaire import fourchette  # noqa: E402


def lire_json(chemin, defaut):
    return json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else defaut


def donnees(p):
    """Ce que la page reçoit : les offres, les passages, les employeurs suivis, la cible."""
    dossier = p["dossier_donnees"]
    vus = lire_json(dossier / "vus.json", {})
    # Les doublons (même poste dans une autre ville) ne sont là que pour vus.json.
    offres = [dict(fiche, cle=cle) for cle, fiche in vus.items() if not fiche.get("doublon")]
    # Le score se recalcule à chaque fois : un profil modifié renote toutes les offres.
    for o in offres:
        if not o.get("page"):
            note = score.noter(o, p)
            o.update(score=note["score"], rarete=note["rarete"], score_detail=note["detail"])
    with p["chemin_employeurs"].open(encoding="utf-8") as f:
        employeurs = [(e["nom"], e["famille"], e["ats"]) for e in csv.DictReader(f)]
    return {
        "genere_le": datetime.now().strftime("%Y-%m-%dT%H:%M"),
        "offres": offres,
        "passages": lire_json(dossier / "passages.json", []),
        "employeurs": [{"nom": n, "famille": f, "ats": a} for n, f, a in employeurs],
        "apec": p["a_la_main"]["recherches_apec"],
        "cible": p["profil"]["salaire_cible"],
        "cible_texte": fourchette(*p["profil"]["salaire_cible"], p["profil"]["devise"]),
        "devise": p["profil"]["devise"],
    }


def ecrire_tableau(p):
    feuilles = ["habillage-apple.css", "style-base.css", "grammaire-apple.css"]
    css = "\n".join((STYLE / f).read_text(encoding="utf-8") for f in feuilles)
    css += "\n" + "\n".join((MODELE / f).read_text(encoding="utf-8") for f in ("page.css", "cartes.css"))
    # collection.js (la logique des cartes) avant page.js (la liste), puis cartes.js (l'affichage).
    scripts = [STYLE / "grammaire-apple.js"] + [MODELE / f for f in ("collection.js", "page.js", "cartes.js")]
    js = "\n".join(f.read_text(encoding="utf-8") for f in scripts)
    # « </ » fermerait la balise <script> si un titre d'offre en contenait un.
    contenu = json.dumps(donnees(p), ensure_ascii=False).replace("</", "<\\/")

    page = (MODELE / "modele.html").read_text(encoding="utf-8")
    page = page.replace("/*CSS*/", css).replace("/*JS*/", js).replace("/*DONNEES*/", contenu)
    sortie = p["dossier_donnees"] / "tableau.html"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(page, encoding="utf-8")
    print(f"Tableau -> {sortie}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    lecteur = argparse.ArgumentParser(description="Refait tableau.html à partir des données de la veille.")
    lecteur.add_argument("--profil", default="profil.toml", help="le profil de recherche")
    args = lecteur.parse_args()
    try:
        ecrire_tableau(module_profil.charger(args.profil))
    except module_profil.ProfilInvalide as erreur:
        sys.exit(f"Profil : {erreur}")
