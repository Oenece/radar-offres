"""Tests du score d'adéquation (score.py).

Lancer depuis la racine du dépôt :  python -m unittest discover tests
"""

import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.dont_write_bytecode = True
import profil  # noqa: E402
import score  # noqa: E402


def profil_test(**score_reglages):
    """Un petit profil complet, avec des réglages de score choisis par le test."""
    return {
        "profil": {"salaire_cible": [50000, 60000], "salaire_bas": 40000, "devise": "EUR",
                   "annees_experience": 4, "annees_alerte": 7},
        "themes": {"titre": [r"\bdata\b"]},
        "colle": [{"motif": "sql", "tag": "SQL", "texte": "…", "poids": 15},
                  {"motif": "python", "tag": "Python", "texte": "…"}],
        "coince": [{"motif": "phd", "tag": "Doctorat", "texte": "…", "poids": -20},
                   {"motif": "spark", "tag": "Big data", "texte": "…"}],
        "score": score_reglages,
    }


def offre(**champs):
    base = {"titre": "Chargé de mission", "colle": [], "coince": [], "salaire_min": None,
            "salaire_max": None, "devise": "EUR", "mode": "", "lieu": "Lyon"}
    base.update(champs)
    return base


def raison(tag):
    return {"tag": tag, "texte": "…"}


class Score(unittest.TestCase):

    def test_une_offre_sans_rien_vaut_la_base(self):
        note = score.noter(offre(), profil_test())
        self.assertEqual(note["score"], score.DEFAUTS["base"])
        self.assertEqual(note["detail"], [])

    def test_le_poids_de_la_regle_prime_sur_le_defaut(self):
        note = score.noter(offre(colle=[raison("SQL"), raison("Python")]), profil_test())
        self.assertEqual(dict(note["detail"]), {"SQL": 15, "Python": score.DEFAUTS["colle_defaut"]})

    def test_une_raison_coince_retire_des_points(self):
        note = score.noter(offre(coince=[raison("Doctorat"), raison("Big data")]), profil_test(base=50))
        self.assertEqual(note["score"], 50 - 20 + score.DEFAUTS["coince_defaut"])

    def test_le_titre_dans_les_themes_compte(self):
        note = score.noter(offre(titre="Data Analyst"), profil_test(base=50, titre=12))
        self.assertEqual(note["score"], 62)

    def test_les_annees_en_trop_comptent_a_l_annee_pres(self):
        # 10 ans demandés pour 4 d'expérience : 6 ans en trop, -3 chacun.
        note = score.noter(offre(coince=[raison("10 ans")]), profil_test(base=50))
        self.assertEqual(note["score"], 50 - 18)

    def test_salaire_dans_la_cible(self):
        note = score.noter(offre(salaire_min=52000, salaire_max=58000), profil_test(base=50))
        self.assertEqual(note["score"], 50 + score.DEFAUTS["salaire_cible"])

    def test_salaire_bas_compte_une_seule_fois(self):
        # lecture() ajoute déjà « Salaire bas » dans coince : il ne doit pas compter deux fois.
        note = score.noter(offre(salaire_max=35000, coince=[raison("Salaire bas")]), profil_test(base=50))
        self.assertEqual(note["score"], 50 + score.DEFAUTS["salaire_bas"])

    def test_salaire_hors_euros_ignore(self):
        note = score.noter(offre(salaire_max=90000, devise="USD"), profil_test(base=50))
        self.assertEqual(note["score"], 50)

    def test_salaire_compare_dans_la_devise_du_profil(self):
        p = profil_test(base=50)
        p["profil"]["devise"] = "GBP"
        self.assertEqual(score.noter(offre(salaire_max=58000, devise="GBP"), p)["score"], 60)
        self.assertEqual(score.noter(offre(salaire_max=58000, devise="EUR"), p)["score"], 50)

    def test_remote_ou_hybride(self):
        self.assertEqual(score.noter(offre(mode="hybride"), profil_test(base=50))["score"], 55)
        self.assertEqual(score.noter(offre(lieu="Paris (remote)"), profil_test(base=50))["score"], 55)

    def test_le_score_reste_entre_0_et_100(self):
        self.assertEqual(score.noter(offre(), profil_test(base=150))["score"], 100)
        self.assertEqual(score.noter(offre(), profil_test(base=-30))["score"], 0)

    def test_les_seuils_de_rarete(self):
        r = score.reglages(profil_test())
        attendu = {0: "commune", 39: "commune", 40: "peu_commune", 60: "rare", 75: "epique",
                   89: "epique", 90: "legendaire", 100: "legendaire"}
        for valeur, rarete in attendu.items():
            self.assertEqual(score.rarete(valeur, r), rarete, valeur)

    def test_un_seuil_du_profil_remplace_seulement_le_sien(self):
        r = score.reglages(profil_test(seuils={"legendaire": 95}))
        self.assertEqual(score.rarete(92, r), "epique")
        self.assertEqual(score.rarete(60, r), "rare")

    def test_aucun_quota_de_rarete(self):
        # Une série d'offres moyennes ne fabrique pas de légendaire : la rareté ne dépend que du score.
        notes = [score.noter(offre(colle=[raison("Python")]), profil_test()) for _ in range(50)]
        self.assertTrue(all(n["rarete"] == notes[0]["rarete"] for n in notes))

    def test_le_profil_exemple_se_note(self):
        p = profil.charger(RACINE / "tests" / "profil_test.toml")
        note = score.noter(offre(titre="Data Analyst", colle=[raison("SQL")], mode="remote"), p)
        self.assertEqual(note["score"], 40 + 10 + 15 + 5)
        self.assertEqual(note["rarete"], "rare")


if __name__ == "__main__":
    unittest.main()
