"""Le score d'adéquation d'une offre, de 0 à 100, et sa rareté.

Le score dit à quel point l'offre colle au profil, pas à quel point elle est rare
sur le marché. Il part d'une base et ajoute ou retire des points :
    - chaque raison « colle » trouvée (poids de la règle, sinon colle_defaut) ;
    - chaque raison « coince » trouvée (poids de la règle, sinon coince_defaut) ;
    - le titre qui touche un thème du profil (titre) ;
    - le salaire affiché face à la cible (salaire_cible, salaire_bas), dans la devise du profil ;
    - les années demandées au-delà de ton expérience (par_annee_en_trop) ;
    - le télétravail ou l'hybride (mode_souple).
Le total est borné entre 0 et 100, puis classé par les seuils de rareté.

Tout se calcule à partir des champs gardés dans vus.json : le tableau peut donc
renoter toutes les offres quand le profil change, sans relire les flux.
Les poids et les seuils se règlent dans la section [score] du profil ; ce qui
manque prend la valeur de DEFAUTS.
"""

import re

DEFAUTS = {
    "base": 40,
    "colle_defaut": 10,
    "coince_defaut": -8,
    "titre": 10,
    "salaire_cible": 10,
    "salaire_bas": -15,
    "par_annee_en_trop": -3,
    "mode_souple": 5,
    "seuils": {"peu_commune": 40, "rare": 60, "epique": 75, "legendaire": 90},
}

# Du plus haut au plus bas : la première rareté dont le seuil est atteint l'emporte.
RARETES = ["legendaire", "epique", "rare", "peu_commune"]
LIBELLES = {"legendaire": "légendaire", "epique": "épique", "rare": "rare",
            "peu_commune": "peu commune", "commune": "commune"}


def reglages(p):
    """Les réglages du score : ceux du profil, complétés par DEFAUTS."""
    r = {**DEFAUTS, **p.get("score", {})}
    r["seuils"] = {**DEFAUTS["seuils"], **p.get("score", {}).get("seuils", {})}
    return r


def rarete(score, r):
    """La rareté (identifiant sans accent) que le score atteint."""
    for cle in RARETES:
        if score >= r["seuils"][cle]:
            return cle
    return "commune"


def noter(offre, p):
    """Le score de l'offre, sa rareté, et le détail des points (libellé, points).

    offre : une fiche avec titre, colle, coince, salaire_min, salaire_max, devise, mode.
    """
    r = reglages(p)
    poids_colle = {regle["tag"]: regle.get("poids", r["colle_defaut"]) for regle in p["colle"]}
    poids_coince = {regle["tag"]: regle.get("poids", r["coince_defaut"]) for regle in p["coince"]}
    perso = p["profil"]
    detail = []

    if any(re.search(m, (offre.get("titre") or "").lower()) for m in p["themes"]["titre"]):
        detail.append(("titre dans tes thèmes", r["titre"]))

    for raison in offre.get("colle") or []:
        detail.append((raison["tag"], poids_colle.get(raison["tag"], r["colle_defaut"])))

    for raison in offre.get("coince") or []:
        tag = raison["tag"]
        annees = re.fullmatch(r"(\d+) ans", tag)
        if annees:  # ajouté par lecture() : compté plus bas, à l'année près
            en_trop = int(annees.group(1)) - perso["annees_experience"]
            detail.append((f"{tag} demandés", round(en_trop * r["par_annee_en_trop"])))
        elif tag != "Salaire bas":  # ajouté par lecture() : compté avec le salaire
            detail.append((tag, poids_coince.get(tag, r["coince_defaut"])))

    maxi = offre.get("salaire_max")
    if maxi and (offre.get("devise") or "EUR") == perso["devise"]:  # une autre devise ne se compare pas
        bas = perso["salaire_cible"][0]
        if maxi < perso["salaire_bas"]:
            detail.append(("salaire sous ta cible", r["salaire_bas"]))
        elif maxi >= bas:  # la fourchette atteint au moins le bas de la cible
            detail.append(("salaire dans ta cible ou au-dessus", r["salaire_cible"]))

    mode, lieu = offre.get("mode") or "", (offre.get("lieu") or "").lower()
    if mode in ("remote", "hybride") or "remote" in lieu:
        detail.append(("remote ou hybride", r["mode_souple"]))

    total = r["base"] + sum(points for _, points in detail)
    score = max(0, min(100, round(total)))
    return {"score": score, "rarete": rarete(score, r), "detail": [d for d in detail if d[1]]}
