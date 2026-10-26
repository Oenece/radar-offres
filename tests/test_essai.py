"""Tests de l'outil d'essai (essai.py) et des raisons données par les filtres."""

import contextlib
import io
import unittest
from unittest import mock

from outils import PROFIL_EXEMPLE, offre, profil_test

import essai
import profil
import veille


class Adresses(unittest.TestCase):

    def test_les_cinq_ats(self):
        attendu = {
            "https://jobs.ashbyhq.com/acme": ("ashby", "acme"),
            "https://jobs.ashbyhq.com/acme/1234-abcd?src=x": ("ashby", "acme"),
            "https://jobs.lever.co/acme/": ("lever", "acme"),
            "https://boards.greenhouse.io/acme/jobs/42": ("greenhouse", "acme"),
            "https://job-boards.eu.greenhouse.io/acme": ("greenhouse", "acme"),
            "https://jobs.smartrecruiters.com/Acme1/744000": ("smartrecruiters", "Acme1"),
            "https://careers.smartrecruiters.com/Acme1": ("smartrecruiters", "Acme1"),
            "https://acme-france.teamtailor.com/jobs": ("teamtailor", "acme-france"),
        }
        for url, resultat in attendu.items():
            self.assertEqual(essai.deviner_ats(url), resultat, url)

    def test_adresse_inconnue(self):
        self.assertIsNone(essai.deviner_ats("https://www.acme.fr/carrieres"))


class Raisons(unittest.TestCase):
    p = profil_test()

    def test_raisons_du_lieu(self):
        self.assertEqual(veille.pourquoi_lieu("Lyon, France", self.p), (True, "lieu « lyon »"))
        self.assertEqual(veille.pourquoi_lieu("Remote - Europe", self.p), (True, "remote vers « europe »"))
        self.assertEqual(veille.pourquoi_lieu("Berlin", self.p), (False, "lieu hors profil (« Berlin »)"))

    def test_raisons_du_theme(self):
        self.assertEqual(veille.pourquoi_theme("Sales Data Analyst", "", self.p), (False, r"titre exclu par « \bsales\b »"))
        self.assertEqual(veille.pourquoi_theme("Backend Engineer", "", self.p),
                         (False, "poste d'ingénieur sans mot de ingenieur_ok"))
        self.assertEqual(veille.pourquoi_theme("Senior Data Analyst", "", self.p), (True, r"titre « \bdata\b »"))
        garde, raison = veille.pourquoi_theme("Chef de projet", "AI, SQL and dashboards", self.p)
        self.assertTrue(garde)
        self.assertIn("2 mots du métier", raison)

    def test_juger_suit_l_ordre_du_passage(self):
        self.assertEqual(essai.juger(offre(lieu="Paris"), self.p)[0], False)
        garde, raison = essai.juger(offre(titre="Data Analyst", lieu="Lyon"), self.p)
        self.assertTrue(garde)
        self.assertEqual(raison, r"lieu « lyon » ; titre « \bdata\b »")


class Commande(unittest.TestCase):

    def lancer(self, *arguments):
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            essai.main(essai.options(["--profil", str(PROFIL_EXEMPLE), *arguments]))
        return sortie.getvalue()

    def test_une_offre_inventee(self):
        texte = self.lancer("--titre", "Consultant SEA", "--lieu", "Paris", "--description", "Google Ads")
        self.assertIn("✓ gardée", texte)
        self.assertIn("+15  SEA", texte)

    def test_une_url_lit_le_flux_et_donne_la_ligne(self):
        offres = [veille.offre_vide(id="1", titre="SEO Manager", lien="https://x", lieu="Paris")]
        with mock.patch.dict(veille.LECTEURS, {"lever": lambda _: iter(offres)}):
            texte = self.lancer("--url", "https://jobs.lever.co/acme")
        self.assertIn("1 offres, 1 gardée(s)", texte)
        self.assertIn("Nom,famille,lever,acme,", texte)


class ProfilExemple(unittest.TestCase):
    """Le profil à copier doit rester valide et garder ce qu'il annonce."""

    def test_il_se_charge(self):
        p = profil.charger(PROFIL_EXEMPLE)
        self.assertEqual(p["profil"]["devise"], "EUR")

    def test_il_garde_le_marketing_d_acquisition(self):
        p = profil.charger(PROFIL_EXEMPLE)
        for titre in ("Consultant SEA", "SEO & GEO Manager", "Growth Marketing Manager", "Paid Social Lead"):
            self.assertTrue(essai.juger(offre(titre=titre, lieu="Paris"), p)[0], titre)
        for titre in ("Senior Product Manager - Growth", "Data Engineer (Growth Team)", "Sales Manager"):
            self.assertFalse(essai.juger(offre(titre=titre, lieu="Paris"), p)[0], titre)
        # « France » seul ne suffit pas : beaucoup d'offres listent leurs villes puis « France ».
        self.assertFalse(essai.juger(offre(titre="Consultant SEO", lieu="Madrid / France"), p)[0])


if __name__ == "__main__":
    unittest.main()
