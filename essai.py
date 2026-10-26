"""Essai : ce que ton profil garde ou écarte, et pourquoi. Ne modifie aucun fichier.

Pour régler profil.toml sans attendre le prochain passage, et pour vérifier un
nouvel employeur avant de l'ajouter à employeurs.csv.

    python essai.py                                   tous les employeurs de employeurs.csv
    python essai.py --employeur Shine                 un seul employeur de la liste
    python essai.py --url https://jobs.lever.co/acme  une page carrière : trouve l'ATS,
                                                      lit le flux, donne la ligne à coller
    python essai.py --ecartees                        affiche aussi les offres écartées
    python essai.py --titre "Consultant SEA" --lieu Paris     une offre inventée

Options communes : --profil chemin/vers/profil.toml
"""

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent
sys.path.insert(0, str(DOSSIER))
sys.dont_write_bytecode = True
import profil as module_profil  # noqa: E402
import score  # noqa: E402
import veille  # noqa: E402

# L'adresse d'une page carrière -> (ats, identifiant). L'identifiant est le premier groupe.
ADRESSES = [
    (r"jobs\.ashbyhq\.com/([^/?#]+)", "ashby"),
    (r"jobs\.lever\.co/([^/?#]+)", "lever"),
    (r"(?:job-)?boards(?:\.eu)?\.greenhouse\.io/([^/?#]+)", "greenhouse"),
    (r"(?:jobs|careers)\.smartrecruiters\.com/([^/?#]+)", "smartrecruiters"),
    (r"([a-z0-9-]+)\.teamtailor\.com", "teamtailor"),
]


def deviner_ats(url):
    """(ats, identifiant) d'après l'adresse de la page carrière, ou None."""
    for motif, ats in ADRESSES:
        m = re.search(motif, url, re.I)
        if m:
            return ats, m.group(1)
    return None


def juger(offre, p, avec_detail=True):
    """(gardée ?, raison) d'une offre, dans l'ordre exact du passage."""
    if offre.get("page"):
        return True, "page maison : à lire à la main"
    garde, raison = veille.pourquoi_lieu(offre["lieu"], p)
    if not garde:
        return False, raison
    if offre.get("detail") and avec_detail and not veille.cherche(p["themes"]["exclus_titre"], offre["titre"].lower()):
        veille.detail_smartrecruiters(offre)
    garde_theme, raison_theme = veille.pourquoi_theme(offre["titre"], offre["description"], p)
    return garde_theme, (raison + " ; " + raison_theme) if garde_theme else raison_theme


def noter(offre, p):
    """Le score, comme le tableau le calcule."""
    if not offre["salaire_max"]:
        offre["salaire_min"], offre["salaire_max"] = veille.salaire_dans_le_texte(offre["description"])
    offre["colle"], offre["coince"] = veille.lecture(offre, p)
    return score.noter(offre, p)


def essayer(nom, ats, identifiant, p, ecartees=False, avec_detail=True):
    """Lit un flux et affiche le verdict de chaque offre. Rend le compte des raisons d'écart."""
    try:
        offres = list(veille.LECTEURS[ats](identifiant))
    except Exception as erreur:
        print(f"\n{nom} ({ats}, {identifiant}) : flux illisible : {erreur}")
        return Counter()
    gardees, ecarts = [], Counter()
    for o in offres:
        garde, raison = juger(o, p, avec_detail)
        if garde:
            gardees.append((o, raison, None if o.get("page") else noter(o, p)))
        else:
            ecarts[raison.split(" (")[0].split(" «")[0]] += 1
            if ecartees:
                gardees.append((o, raison, False))
    retenues = sum(1 for _, _, n in gardees if n is not False)
    print(f"\n{nom} ({ats}, {identifiant}) : {len(offres)} offres, {retenues} gardée(s)")
    for o, raison, note in sorted(gardees, key=lambda x: -(x[2]["score"] if x[2] else -1)):
        if note is False:
            print(f"   ✗  {o['titre'][:60]:<60}  {raison}")
        elif note is None:
            print(f"   ✓  {o['titre'][:60]:<60}  {raison}")
        else:
            print(f"   ✓  {o['titre'][:60]:<60}  {note['score']:>3} {score.LIBELLES[note['rarete']]:<11}  {raison}")
    return ecarts


def options(arguments=None):
    lecteur = argparse.ArgumentParser(description="Ce que ton profil garde ou écarte, et pourquoi.")
    lecteur.add_argument("--profil", default="profil.toml", help="le profil de recherche")
    lecteur.add_argument("--employeur", help="un seul employeur de employeurs.csv (son nom)")
    lecteur.add_argument("--url", help="l'adresse d'une page carrière à essayer")
    lecteur.add_argument("--titre", help="essaie une offre inventée avec ce titre")
    lecteur.add_argument("--lieu", default="", help="le lieu de l'offre inventée")
    lecteur.add_argument("--description", default="", help="la description de l'offre inventée")
    lecteur.add_argument("--ecartees", action="store_true", help="affiche aussi les offres écartées")
    lecteur.add_argument("--sans-detail", action="store_true", help="ne lit pas le détail SmartRecruiters")
    return lecteur.parse_args(arguments)


def main(args):
    p = module_profil.charger(args.profil)
    avec_detail = not args.sans_detail

    if args.titre:
        o = veille.offre_vide(id="essai", titre=args.titre, lien="", lieu=args.lieu, description=args.description)
        garde, raison = juger(o, p)
        print(("✓ gardée" if garde else "✗ écartée") + f" : {raison}")
        if garde:
            note = noter(o, p)
            print(f"  score {note['score']} ({score.LIBELLES[note['rarete']]})")
            for libelle, points in note["detail"]:
                print(f"    {points:+4d}  {libelle}")
        return

    if args.url:
        trouve = deviner_ats(args.url)
        if not trouve:
            print("ATS non reconnu. Si la page liste des liens vers chaque offre, essaie la ligne :\n"
                  f"  Nom,famille,page,{args.url},\nsinon : Nom,famille,manuel,{args.url},note")
            return
        ats, identifiant = trouve
        essayer(args.url, ats, identifiant, p, args.ecartees, avec_detail)
        print(f"\nLigne à coller dans employeurs.csv (nom et famille à ton choix) :\n  Nom,famille,{ats},{identifiant},")
        return

    with p["chemin_employeurs"].open(encoding="utf-8") as f:
        employeurs = [e for e in csv.DictReader(f) if e["ats"] != "manuel"]
    if args.employeur:
        employeurs = [e for e in employeurs if e["nom"].lower() == args.employeur.lower()]
        if not employeurs:
            sys.exit(f"Pas d'employeur « {args.employeur} » dans {p['chemin_employeurs'].name}.")
    total = Counter()
    for e in employeurs:
        total += essayer(e["nom"], e["ats"], e["identifiant"], p, args.ecartees, avec_detail)
    if total:
        print("\nPourquoi les autres offres sont écartées :")
        for raison, nombre in total.most_common():
            print(f"  {nombre:>5}  {raison}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        main(options())
    except module_profil.ProfilInvalide as erreur:
        sys.exit(f"Profil : {erreur}")
