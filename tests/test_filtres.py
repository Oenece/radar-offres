"""Tests des règles de tri et de la mise en forme (veille.py, partie 1 et outils).

Les filtres sont testés avec profil.exemple.toml : lieux autour de Lyon, remote en
Europe, thèmes data / analytics.
"""

import unittest

from outils import offre, profil_exemple

import veille


class Lieu(unittest.TestCase):
    p = profil_exemple()

    def accepte(self, lieu):
        return veille.lieu_accepte(lieu, self.p)

    def test_une_ville_du_profil(self):
        self.assertTrue(self.accepte("Lyon, Auvergne-Rhône-Alpes, France"))
        self.assertTrue(self.accepte("VILLEURBANNE"))

    def test_une_autre_ville(self):
        self.assertFalse(self.accepte("Paris, France"))

    def test_un_seul_lieu_suffit(self):
        self.assertTrue(self.accepte("Paris / Lyon"))

    def test_le_pays_seul_est_accepte_mais_pas_avec_une_autre_ville(self):
        self.assertTrue(self.accepte("France"))
        self.assertFalse(self.accepte("Bordeaux, France"))

    def test_remote_vers_une_zone_acceptee(self):
        self.assertTrue(self.accepte("Remote - Europe"))
        self.assertTrue(self.accepte("EMEA (remote)"))

    def test_remote_vers_une_autre_zone(self):
        self.assertFalse(self.accepte("Remote, US"))
        self.assertFalse(self.accepte("Berlin (remote)"))

    def test_remote_sans_pays(self):
        self.assertTrue(self.accepte("Remote"))
        self.assertTrue(self.accepte("Fully remote"))

    def test_lieu_vide(self):
        self.assertFalse(self.accepte(""))


class Theme(unittest.TestCase):
    p = profil_exemple()

    def accepte(self, titre, description=""):
        return veille.theme_accepte(titre, description, self.p)

    def test_un_theme_dans_le_titre(self):
        self.assertTrue(self.accepte("Senior Data Analyst"))
        self.assertTrue(self.accepte("Marketing Analytics Lead"))

    def test_une_exclusion_l_emporte_sur_le_theme(self):
        self.assertFalse(self.accepte("Sales Data Analyst"))
        self.assertFalse(self.accepte("Data Analyst Intern"))

    def test_un_ingenieur_doit_etre_tourne_vers_le_metier(self):
        self.assertFalse(self.accepte("Software Engineer"))
        self.assertTrue(self.accepte("Analytics Engineer"))

    def test_un_ingenieur_avec_une_description_du_metier_reste_ecarte(self):
        self.assertFalse(self.accepte("Backend Developer", "AI, SQL, dashboards, BigQuery"))

    def test_sans_theme_la_description_doit_parler_d_ia_et_du_metier(self):
        description = "You will use AI to build dashboards on top of our SQL warehouse."
        self.assertTrue(self.accepte("Chef de projet", description))

    def test_un_seul_mot_du_metier_ne_suffit_pas(self):
        self.assertFalse(self.accepte("Chef de projet", "You will use AI and SQL."))

    def test_le_metier_sans_ia_ne_suffit_pas(self):
        self.assertFalse(self.accepte("Chef de projet", "SQL, dashboards and BigQuery."))


class Lecture(unittest.TestCase):
    p = profil_exemple()

    def test_colle_et_coince(self):
        o = offre(description="Strong SQL skills. Spark is a plus.")
        colle, coince = veille.lecture(o, self.p)
        self.assertEqual([r["tag"] for r in colle], ["SQL"])
        self.assertEqual([r["tag"] for r in coince], ["Big data"])

    def test_un_lien_ne_compte_pas(self):
        o = offre(titre="Analyste", description="Voir https://exemple.fr/sql-et-python")
        self.assertEqual(veille.lecture(o, self.p), ([], []))

    def test_annees_au_dessus_de_l_alerte(self):
        o = offre(description="10+ years of experience in analytics.")
        _, coince = veille.lecture(o, self.p)
        self.assertEqual(coince, [{"tag": "10 ans",
                                   "texte": "10 ans d'expérience demandés (tu en as 4)"}])

    def test_annees_sous_l_alerte(self):
        o = offre(description="3 years of experience.")
        self.assertEqual(veille.lecture(o, self.p)[1], [])

    def test_salaire_bas(self):
        _, coince = veille.lecture(offre(salaire_max=35000), self.p)
        self.assertEqual(coince, [{"tag": "Salaire bas", "texte": "salaire sous la cible de 45 à 55 k€"}])

    def test_salaire_bas_dans_une_autre_devise_ignore(self):
        self.assertEqual(veille.lecture(offre(salaire_max=35000, devise="USD"), self.p)[1], [])

    def test_salaire_bas_dans_la_devise_du_profil(self):
        p = dict(self.p, profil=dict(self.p["profil"], devise="GBP"))
        _, coince = veille.lecture(offre(salaire_max=35000, devise="GBP"), p)
        self.assertEqual(coince[0]["texte"], "salaire sous la cible de 45 à 55 k£")

    def test_quatre_raisons_au_plus(self):
        o = offre(description="SQL dashboards A/B test python " * 3)
        p = dict(self.p, colle=self.p["colle"] + [{"motif": "test", "tag": "Cinquième", "texte": "…"}])
        self.assertEqual(len(veille.lecture(o, p)[0]), 4)


class Outils(unittest.TestCase):

    def test_annees_demandees(self):
        self.assertEqual(veille.annees_demandees("3 to 5 years, ideally 7 ans"), 7)
        self.assertIsNone(veille.annees_demandees("since 1998, 50 years of history"))
        self.assertIsNone(veille.annees_demandees("no number here"))

    def test_salaire_dans_le_texte(self):
        self.assertEqual(veille.salaire_dans_le_texte("entre 50 à 65 k€ selon profil"), (50000, 65000))
        self.assertEqual(veille.salaire_dans_le_texte("50 000 € - 65 000 €"), (50000, 65000))
        self.assertEqual(veille.salaire_dans_le_texte("salaire attractif"), (None, None))

    def test_fourchette(self):
        self.assertEqual(veille.fourchette(60000, 100000), "60 à 100 k€")
        self.assertEqual(veille.fourchette(None, 50000, "USD"), "50 k$")
        self.assertEqual(veille.fourchette(55000, 55000), "55 k€")
        self.assertEqual(veille.fourchette(40000, None), "")
        self.assertEqual(veille.fourchette(90000, 120000, "CHF"), "90 à 120 k CHF")
        self.assertEqual(veille.fourchette(None, 500000, "SEK"), "500 kSEK")

    def test_sans_html(self):
        self.assertEqual(veille.sans_html("&lt;p&gt;Data &amp;amp; IA&lt;/p&gt;"), "Data & IA")
        self.assertEqual(veille.sans_html("<ul><li>un</li>\n<li>deux</li></ul>"), "un deux")
        self.assertEqual(veille.sans_html(None), "")

    def test_jour_iso(self):
        self.assertEqual(veille.jour_iso("2026-10-21T08:30:00.000Z"), "2026-10-21")
        self.assertEqual(veille.jour_iso(1792540800000), "2026-10-21")  # Lever : millisecondes
        self.assertEqual(veille.jour_iso("Wed, 21 Oct 2026 08:30:00 +0200"), "2026-10-21")  # Teamtailor
        self.assertEqual(veille.jour_iso("hier"), "")
        self.assertEqual(veille.jour_iso(None), "")

    def test_mode_lisible(self):
        self.assertEqual(veille.mode_lisible("Hybrid"), "hybride")
        self.assertEqual(veille.mode_lisible("On-Site"), "sur site")
        self.assertEqual(veille.mode_lisible("fully"), "remote")
        self.assertEqual(veille.mode_lisible(None), "")

    def test_extrait_saute_la_presentation_de_l_entreprise(self):
        description = ("We are a fast-growing company with offices in many cities. " * 3 +
                       "What you'll do: build dashboards for the marketing team. " + "More details. " * 30)
        texte = veille.extrait(description, longueur=60)
        self.assertTrue(texte.startswith("What you'll do"), texte)
        self.assertTrue(texte.endswith(" …"))

    def test_extrait_court_reste_entier(self):
        self.assertEqual(veille.extrait("Un poste court."), "Un poste court.")


if __name__ == "__main__":
    unittest.main()
