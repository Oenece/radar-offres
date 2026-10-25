"""Tests de la lecture du profil et d'un passage complet, dans un dossier temporaire.

Le passage tourne avec un faux ATS (aucun réseau) : on vérifie ce qu'il écrit
(vus.json, passages.json, offres-JJ.md, tableau.html) et qu'un second passage
ne ressort rien.
"""

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from outils import PROFIL_EXEMPLE, offre

import profil
import veille


class Dossier(unittest.TestCase):
    """Un dossier de travail temporaire, avec le profil d'exemple dedans."""

    def setUp(self):
        self.dossier = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dossier)
        self.profil = self.dossier / "profil.toml"
        shutil.copy(PROFIL_EXEMPLE, self.profil)

    def ecrire_profil(self, ancien, nouveau):
        texte = self.profil.read_text(encoding="utf-8")
        self.assertIn(ancien, texte)
        self.profil.write_text(texte.replace(ancien, nouveau, 1), encoding="utf-8")


class Profil(Dossier):

    def test_les_chemins_partent_du_dossier_du_profil(self):
        p = profil.charger(self.profil)
        self.assertEqual(p["chemin_employeurs"], self.dossier.resolve() / "employeurs.csv")
        self.assertEqual(p["dossier_donnees"], self.dossier.resolve() / "donnees")

    def test_devise_par_defaut_et_en_majuscules(self):
        self.ecrire_profil("devise = 'EUR'", "devise = 'gbp'")
        self.assertEqual(profil.charger(self.profil)["profil"]["devise"], "GBP")
        self.ecrire_profil("devise = 'gbp'", "")
        self.assertEqual(profil.charger(self.profil)["profil"]["devise"], "EUR")

    def test_profil_absent(self):
        with self.assertRaisesRegex(profil.ProfilInvalide, "profil.exemple.toml"):
            profil.charger(self.dossier / "absent.toml")

    def test_toml_illisible(self):
        self.profil.write_text("[profil\nsalaire = ", encoding="utf-8")
        with self.assertRaisesRegex(profil.ProfilInvalide, "ne se lit pas"):
            profil.charger(self.profil)

    def test_cle_manquante(self):
        self.ecrire_profil("salaire_bas = 40000", "")
        with self.assertRaisesRegex(profil.ProfilInvalide, r"\[profil\].*salaire_bas"):
            profil.charger(self.profil)

    def test_motif_invalide(self):
        self.ecrire_profil("'analytics',", "'analytics(',")
        with self.assertRaisesRegex(profil.ProfilInvalide, "analytics\\("):
            profil.charger(self.profil)

    def test_cible_a_l_envers(self):
        self.ecrire_profil("salaire_cible = [45000, 55000]", "salaire_cible = [55000, 45000]")
        with self.assertRaisesRegex(profil.ProfilInvalide, "salaire_cible"):
            profil.charger(self.profil)


class Passage(Dossier):

    def setUp(self):
        super().setUp()
        (self.dossier / "employeurs.csv").write_text(
            "nom,famille,ats,identifiant,note\n"
            "Acme,logiciel,faux,acme,\n"
            "Panne,logiciel,panne,panne,\n"
            "Sans flux,agence,manuel,https://exemple.fr,à la main\n", encoding="utf-8")
        self.offres = [
            offre(id="1", titre="Data Analyst", lieu="Lyon", description="SQL et dashboards",
                  salaire_min=48000, salaire_max=52000),
            offre(id="2", titre="Data Analyst", lieu="Villeurbanne"),        # même poste, autre ville
            offre(id="3", titre="Data Analyst", lieu="Paris"),               # hors zone
            offre(id="4", titre="Sales Manager", lieu="Lyon"),               # hors thème
            offre(id="5", titre="Analytics Lead", lieu="Remote - Europe"),
        ]

    def lancer(self, **options):
        def panne(_):
            raise TimeoutError("le serveur ne répond pas")
            yield  # noqa: F401  (en fait un générateur, comme les vrais lecteurs)
        lecteurs = {"faux": lambda _: iter([dict(o) for o in self.offres]), "panne": panne}
        sortie = io.StringIO()
        with mock.patch.dict(veille.LECTEURS, lecteurs), contextlib.redirect_stdout(sortie):
            nouvelles = veille.passage(profil.charger(self.profil), **options)
        return nouvelles, sortie.getvalue()

    def donnees(self, nom):
        return self.dossier / "donnees" / nom

    def test_premier_passage(self):
        nouvelles, _ = self.lancer()
        self.assertEqual([o["id"] for o in nouvelles], ["1", "5"])

        vus = json.loads(self.donnees("vus.json").read_text(encoding="utf-8"))
        self.assertEqual(set(vus), {"faux:acme:1", "faux:acme:2", "faux:acme:5"})
        self.assertTrue(vus["faux:acme:2"]["doublon"])
        self.assertEqual(vus["faux:acme:1"]["salaire"], "48 à 52 k€")

        passages = json.loads(self.donnees("passages.json").read_text(encoding="utf-8"))
        self.assertEqual(passages[-1]["nouvelles"], 2)
        self.assertEqual(passages[-1]["employeurs_lus"], 1)
        self.assertEqual(passages[-1]["erreurs"][0]["employeur"], "Panne")
        self.assertEqual(passages[-1]["manuels"][0]["employeur"], "Sans flux")

        md = self.donnees(f"offres-{date.today().isoformat()}.md").read_text(encoding="utf-8")
        self.assertIn("[Data Analyst](https://exemple.fr/1)", md)
        self.assertIn("score ", md)
        self.assertIn("## Sources en erreur", md)
        self.assertIn("- Sans flux : https://exemple.fr (à la main)", md)

        tableau = self.donnees("tableau.html").read_text(encoding="utf-8")
        self.assertIn('"rarete"', tableau)
        self.assertIn('"cible_texte": "45 à 55 k€"', tableau)
        self.assertNotIn("/*DONNEES*/", tableau)

    def test_un_second_passage_ne_ressort_rien(self):
        self.lancer()
        nouvelles, sortie = self.lancer()
        self.assertEqual(nouvelles, [])
        self.assertIn("Rien de nouveau", sortie)
        passages = json.loads(self.donnees("passages.json").read_text(encoding="utf-8"))
        self.assertEqual(len(passages), 2)

    def test_tout_ressort_tout_sans_toucher_aux_fichiers(self):
        self.lancer()
        vus_avant = self.donnees("vus.json").read_text(encoding="utf-8")
        nouvelles, _ = self.lancer(tout=True)
        self.assertEqual([o["id"] for o in nouvelles], ["1", "5"])
        self.assertEqual(self.donnees("vus.json").read_text(encoding="utf-8"), vus_avant)
        self.assertEqual(len(json.loads(self.donnees("passages.json").read_text(encoding="utf-8"))), 1)

    def test_une_offre_toujours_en_ligne_est_datee(self):
        self.lancer()
        vus = json.loads(self.donnees("vus.json").read_text(encoding="utf-8"))
        vus["faux:acme:1"]["en_ligne_le"] = "2000-01-01"
        self.donnees("vus.json").write_text(json.dumps(vus), encoding="utf-8")
        self.lancer()
        vus = json.loads(self.donnees("vus.json").read_text(encoding="utf-8"))
        self.assertEqual(vus["faux:acme:1"]["en_ligne_le"], date.today().isoformat())


if __name__ == "__main__":
    unittest.main()
