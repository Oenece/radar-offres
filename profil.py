"""Lecture du profil de recherche (profil.toml).

Le profil dit ce que la veille garde (lieux, thèmes, exclusions), comment elle lit
une offre (règles « colle » et « coince », cible salariale, expérience) et où sont
les fichiers de la personne (employeurs.csv, dossier des données).

Le code ne contient aucun critère : tout vient d'ici. Pour commencer, copier
profil.exemple.toml en profil.toml et l'adapter.
"""

import re
import tomllib
from pathlib import Path

# Les clés sans lesquelles la veille ne sait pas trier.
OBLIGATOIRES = {
    "profil": ["salaire_cible", "salaire_bas", "annees_experience", "annees_alerte"],
    "lieux": ["acceptes", "exacts", "remote_zones"],
    "themes": ["titre", "ingenieur", "ingenieur_ok", "ia", "metier", "metier_minimum", "exclus_titre"],
}


class ProfilInvalide(Exception):
    """Le profil manque, ne se lit pas, ou une clé est absente ou fausse."""


def charger(chemin):
    """Lit profil.toml et rend un dictionnaire prêt à l'emploi.

    Les chemins de [fichiers] sont résolus par rapport au dossier du profil, et
    chaque motif est compilé une fois pour signaler tout de suite une regex fausse.
    """
    chemin = Path(chemin).resolve()
    if not chemin.exists():
        raise ProfilInvalide(f"Pas de profil à {chemin}. Copier profil.exemple.toml en profil.toml, "
                             "puis l'adapter.")
    try:
        p = tomllib.loads(chemin.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as erreur:
        raise ProfilInvalide(f"{chemin.name} ne se lit pas : {erreur}") from None

    for section, cles in OBLIGATOIRES.items():
        manquantes = [c for c in cles if c not in p.get(section, {})]
        if manquantes:
            raise ProfilInvalide(f"{chemin.name}, section [{section}] : il manque {', '.join(manquantes)}.")
    p.setdefault("colle", [])
    p.setdefault("coince", [])
    p.setdefault("a_la_main", {}).setdefault("recherches_apec", [])

    # Les salaires du profil sont dans cette devise ; une offre dans une autre devise
    # affiche son salaire, mais il n'est comparé ni à la cible ni au seuil bas.
    p["profil"]["devise"] = p["profil"].get("devise", "EUR").upper()
    mini, maxi = p["profil"]["salaire_cible"]
    if not mini <= maxi:
        raise ProfilInvalide(f"{chemin.name} : salaire_cible doit aller du plus bas au plus haut.")

    motifs = list(p["themes"]["titre"]) + p["themes"]["ingenieur_ok"] + p["themes"]["ia"]
    motifs += p["themes"]["metier"] + p["themes"]["exclus_titre"] + [p["themes"]["ingenieur"]]
    motifs += [r["motif"] for r in p["colle"] + p["coince"]]
    for motif in motifs:
        try:
            re.compile(motif)
        except re.error as erreur:
            raise ProfilInvalide(f"{chemin.name} : motif « {motif} » invalide ({erreur}).") from None

    fichiers = p.get("fichiers", {})
    p["chemin_employeurs"] = chemin.parent / fichiers.get("employeurs", "employeurs.csv")
    p["dossier_donnees"] = chemin.parent / fichiers.get("donnees", "donnees")
    return p
