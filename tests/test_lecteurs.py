"""Tests des lecteurs d'ATS, sans réseau.

Chaque test remplace veille.telecharger par une fausse réponse, écrite à la main
sur le modèle de l'API publique (seuls les champs que le lecteur lit). On vérifie
que chaque ATS rend la même forme d'offre (voir offre_vide).
"""

import json
import unittest
from unittest import mock

import outils  # noqa: F401  (chemin du dépôt)
import veille

CHAMPS = {"id", "titre", "lien", "lieu", "description", "salaire_min", "salaire_max", "devise",
          "publiee_le", "contrat", "mode", "equipe"}


def reponses(par_url):
    """Un faux telecharger : la réponse dont le morceau d'URL apparaît dans l'URL demandée."""
    def telecharger(url):
        for morceau, contenu in par_url.items():
            if morceau in url:
                return contenu if isinstance(contenu, str) else json.dumps(contenu)
        raise AssertionError(f"URL inattendue : {url}")
    return mock.patch.object(veille, "telecharger", side_effect=telecharger)


class Lecteurs(unittest.TestCase):

    def verifier_forme(self, offres):
        self.assertTrue(offres)
        for o in offres:
            self.assertLessEqual(CHAMPS, set(o), o)

    def test_ashby(self):
        api = {"jobs": [{
            "id": "a1", "title": "Data Analyst", "jobUrl": "https://jobs.ashbyhq.com/acme/a1",
            "location": "Lyon", "secondaryLocations": [{"location": "Paris"}], "isRemote": True,
            "descriptionPlain": "SQL", "publishedAt": "2026-10-20T09:00:00Z",
            "employmentType": "FullTime", "workplaceType": "Hybrid", "team": "Data",
            "compensation": {"summaryComponents": [
                {"compensationType": "Equity", "maxValue": 1},
                {"compensationType": "Salary", "minValue": 45000, "maxValue": 55000, "currencyCode": "EUR"}]},
        }]}
        with reponses({"api.ashbyhq.com/posting-api/job-board/acme": api}):
            offres = list(veille.lire_ashby("acme"))
        self.verifier_forme(offres)
        o = offres[0]
        self.assertEqual(o["lieu"], "Lyon (remote) / Paris (remote)")
        self.assertEqual((o["contrat"], o["mode"], o["equipe"]), ("Full Time", "hybride", "Data"))
        self.assertEqual((o["salaire_min"], o["salaire_max"]), (45000, 55000))
        self.assertEqual(o["publiee_le"], "2026-10-20")

    def test_lever(self):
        api = [{
            "id": "l1", "text": "Analytics Engineer", "hostedUrl": "https://jobs.lever.co/acme/l1",
            "categories": {"allLocations": ["Lyon", "Remote"], "commitment": "CDI", "team": "Data"},
            "workplaceType": "onsite", "descriptionPlain": "Intro.", "additionalPlain": "Fin.",
            "lists": [{"text": "Missions", "content": "<li>dbt</li><li>SQL</li>"}],
            "createdAt": 1792540800000,
            "salaryRange": {"min": 50000, "max": 60000, "currency": "EUR", "interval": "per-year-salary"},
        }]
        with reponses({"api.lever.co/v0/postings/acme": api}):
            o = list(veille.lire_lever("acme"))[0]
        self.verifier_forme([o])
        self.assertEqual(o["lieu"], "Lyon / Remote")
        self.assertIn("Missions dbt SQL", o["description"])
        self.assertEqual((o["mode"], o["publiee_le"], o["salaire_max"]), ("sur site", "2026-10-21", 60000))

    def test_lever_ignore_un_salaire_horaire(self):
        api = [{"id": "l2", "text": "Analyste", "hostedUrl": "https://x", "categories": {},
                "salaryRange": {"min": 20, "max": 30, "currency": "EUR", "interval": "per-hour-wage"}}]
        with reponses({"api.lever.co": api}):
            self.assertIsNone(list(veille.lire_lever("acme"))[0]["salaire_max"])

    def test_greenhouse(self):
        api = {"jobs": [{
            "id": 42, "title": "Data Analyst", "absolute_url": "https://boards.greenhouse.io/acme/jobs/42",
            "location": {"name": "Lyon"}, "offices": [{"name": "Lyon Office", "location": "Lyon, France"}],
            "content": "&lt;p&gt;SQL &amp;amp; Python&lt;/p&gt;", "first_published": "2026-10-19T10:00:00Z",
            "departments": [{"name": "Marketing"}],
        }]}
        with reponses({"boards-api.greenhouse.io/v1/boards/acme/jobs": api}):
            o = list(veille.lire_greenhouse("acme"))[0]
        self.verifier_forme([o])
        self.assertEqual((o["id"], o["description"], o["equipe"]), ("42", "SQL & Python", "Marketing"))
        self.assertEqual(o["lieu"], "Lyon / Lyon, France")

    def test_smartrecruiters_lit_toutes_les_pages(self):
        def page(debut, nombre):
            return {"totalFound": 150, "content": [
                {"id": str(i), "name": f"Analyste {i}", "ref": f"https://api.smartrecruiters.com/v1/companies/acme/postings/{i}",
                 "location": {"fullLocation": "Lyon, France", "remote": i == 0, "hybrid": i == 1},
                 "releasedDate": "2026-10-18T00:00:00.000Z", "typeOfEmployment": {"label": "CDI"},
                 "function": {"label": "Data"}} for i in range(debut, debut + nombre)]}
        with reponses({"offset=0": page(0, 100), "offset=100": page(100, 50)}):
            offres = list(veille.lire_smartrecruiters("acme"))
        self.verifier_forme(offres)
        self.assertEqual(len(offres), 150)
        self.assertEqual((offres[0]["lieu"], offres[0]["mode"]), ("Lyon, France / remote", "remote"))
        self.assertEqual(offres[1]["mode"], "hybride")

    def test_smartrecruiters_detail_met_le_poste_avant_l_entreprise(self):
        detail = {"postingUrl": "https://jobs.smartrecruiters.com/acme/7", "jobAd": {"sections": {
            "companyDescription": {"text": "<p>Acme</p>"}, "jobDescription": {"text": "<p>Le poste</p>"},
            "qualifications": {"text": "SQL"}}}}
        o = {"detail": "https://api.smartrecruiters.com/x/7", "lien": "ancien"}
        with reponses({"/x/7": detail}):
            veille.detail_smartrecruiters(o)
        self.assertEqual(o["description"], "Le poste SQL  Acme")
        self.assertEqual(o["lien"], "https://jobs.smartrecruiters.com/acme/7")

    def test_teamtailor(self):
        rss = """<?xml version="1.0"?>
<rss xmlns:tt="https://teamtailor.com/locations"><channel><item>
  <title>Data Analyst</title><link>https://acme.teamtailor.com/jobs/1</link><guid>tt-1</guid>
  <description>&lt;p&gt;SQL&lt;/p&gt;</description><pubDate>Wed, 21 Oct 2026 08:30:00 +0200</pubDate>
  <remoteStatus>hybrid</remoteStatus><tt:department>Data</tt:department>
  <tt:locations><tt:location><tt:city>Lyon</tt:city><tt:country>France</tt:country></tt:location></tt:locations>
</item></channel></rss>"""
        with reponses({"acme.teamtailor.com/jobs.rss": rss}):
            o = list(veille.lire_teamtailor("acme"))[0]
        self.verifier_forme([o])
        self.assertEqual((o["lieu"], o["mode"], o["equipe"]), ("Lyon / France", "hybride", "Data"))
        self.assertEqual((o["description"], o["publiee_le"]), ("SQL", "2026-10-21"))

    def test_page_maison_garde_les_sous_pages_une_fois(self):
        page = ('<a href="/carrieres/analyste-data">A</a> <a href="/carrieres/analyste-data#postuler">B</a>'
                '<a href="/carrieres">tout</a> <a href="/blog/article">blog</a>'
                '<a href="https://exemple.fr/carrieres/chef-de-projet/">C</a>')
        with reponses({"exemple.fr/carrieres": page}):
            offres = list(veille.lire_page("https://exemple.fr/carrieres"))
        self.assertEqual([o["lien"] for o in offres], ["https://exemple.fr/carrieres/analyste-data",
                                                       "https://exemple.fr/carrieres/chef-de-projet"])
        self.assertEqual(offres[0]["titre"], "Analyste data")
        self.assertTrue(all(o["page"] for o in offres))


if __name__ == "__main__":
    unittest.main()
