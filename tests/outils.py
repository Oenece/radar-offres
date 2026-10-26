"""Ce que les tests partagent : le chemin du dépôt, le profil d'exemple, une offre type."""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.dont_write_bytecode = True

import profil  # noqa: E402

PROFIL_EXEMPLE = RACINE / "profil.exemple.toml"   # le profil à copier, qui peut évoluer
PROFIL_TEST = Path(__file__).resolve().parent / "profil_test.toml"   # le profil fixe des tests


def profil_test():
    """Le profil fixe des tests (data analyst à Lyon)."""
    return profil.charger(PROFIL_TEST)


def offre(**champs):
    """Une offre comme la rendent les lecteurs (voir offre_vide dans veille.py)."""
    base = {"id": "1", "titre": "Data Analyst", "lien": "https://exemple.fr/1", "lieu": "Lyon",
            "description": "", "salaire_min": None, "salaire_max": None, "devise": "EUR",
            "publiee_le": "", "contrat": "", "mode": "", "equipe": ""}
    base.update(champs)
    return base
