"""Tests de l'alerte e-mail : le choix des offres et le message, sans serveur SMTP."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from outils import PROFIL_TEST

import alerte
import profil


def fiche(titre, colle=(), vu_le="2026-10-25", **champs):
    base = {"employeur": "Acme", "titre": titre, "lien": "https://exemple.fr/" + titre.replace(" ", "-"),
            "lieu": "Lyon", "salaire": "", "salaire_max": None, "devise": "EUR", "mode": "",
            "colle": [{"tag": t, "texte": "…"} for t in colle], "coince": [], "vu_le": vu_le}
    base.update(champs)
    return base


class Alerte(unittest.TestCase):

    def setUp(self):
        self.dossier = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dossier)
        shutil.copy(PROFIL_TEST, self.dossier / "profil.toml")
        donnees = self.dossier / "donnees"
        donnees.mkdir()
        # Avec le profil d'exemple : base 40, titre +10, SQL +15, Dataviz +10, Python +10, remote +5.
        vus = {
            "a": fiche("Data Analyst", colle=["SQL", "Dataviz", "Python"], mode="remote"),   # 90 légendaire
            "b": fiche("Data Analyst Senior", colle=["SQL", "Dataviz"]),                    # 75 épique
            "c": fiche("Data Analyst Junior", colle=["SQL"]),                               # 65 rare
            "d": fiche("Data Lead", colle=["SQL", "Dataviz", "Python"], vu_le="2026-10-24"),  # passage d'avant
            "e": fiche("Data Analyst", doublon=True),
        }
        (donnees / "vus.json").write_text(json.dumps(vus), encoding="utf-8")
        (donnees / "passages.json").write_text(json.dumps([{"date": "2026-10-24"}, {"date": "2026-10-25"}]),
                                               encoding="utf-8")
        self.p = profil.charger(self.dossier / "profil.toml")

    def test_seulement_le_dernier_passage_et_le_niveau_demande(self):
        offres = alerte.offres_a_signaler(self.p)
        self.assertEqual([(o["cle"], o["rarete"]) for o in offres], [("a", "legendaire"), ("b", "epique")])

    def test_le_seuil_se_regle_dans_le_profil(self):
        self.p["alerte"] = {"rarete_min": "rare"}
        self.assertEqual(len(alerte.offres_a_signaler(self.p)), 3)
        self.p["alerte"] = {"rarete_min": "legendaire"}
        self.assertEqual(len(alerte.offres_a_signaler(self.p)), 1)

    def test_un_seuil_inconnu_est_signale(self):
        self.p["alerte"] = {"rarete_min": "mythique"}
        with self.assertRaises(profil.ProfilInvalide):
            alerte.offres_a_signaler(self.p)

    def test_sans_passage_rien(self):
        (self.dossier / "donnees" / "passages.json").unlink()
        self.assertEqual(alerte.offres_a_signaler(self.p), [])

    def test_le_message(self):
        message = alerte.composer(alerte.offres_a_signaler(self.p))
        self.assertEqual(message["Subject"], "radar-offres : 2 offres, la meilleure légendaire (90)")
        texte = message.get_body(("plain",)).get_content()
        self.assertIn("90 (légendaire) Acme : Data Analyst", texte)
        self.assertIn("https://exemple.fr/Data-Analyst", texte)
        page = message.get_body(("html",)).get_content()
        self.assertIn('<a href="https://exemple.fr/Data-Analyst" ', page)
        self.assertIn("#C98A00", page)              # la couleur de la rareté légendaire
        self.assertNotIn("tableau complet", page)   # pas de lien hors de GitHub Actions

    def test_le_lien_du_tableau_sur_github(self):
        env = {"GITHUB_RUN_ID": "42", "GITHUB_REPOSITORY": "moi/ma-veille", "GITHUB_SERVER_URL": "https://github.com"}
        lien = alerte.lien_du_passage(env)
        self.assertEqual(lien, "https://github.com/moi/ma-veille/actions/runs/42")
        self.assertIsNone(alerte.lien_du_passage({}))
        message = alerte.composer(alerte.offres_a_signaler(self.p), lien)
        self.assertIn(lien, message.get_body(("html",)).get_content())
        self.assertIn(lien, message.get_body(("plain",)).get_content())

    def test_envoi_smtp(self):
        message = alerte.composer(alerte.offres_a_signaler(self.p))
        env = {"SMTP_HOTE": "smtp.exemple.fr", "SMTP_UTILISATEUR": "moi@exemple.fr",
               "SMTP_MOT_DE_PASSE": "x", "ALERTE_A": "moi@exemple.fr"}
        with mock.patch("smtplib.SMTP") as smtp:
            alerte.envoyer(message, env)
        serveur = smtp.return_value
        smtp.assert_called_once_with("smtp.exemple.fr", 587, timeout=60)
        serveur.login.assert_called_once_with("moi@exemple.fr", "x")
        serveur.send_message.assert_called_once()
        self.assertEqual(message["To"], "moi@exemple.fr")

    def test_envoi_sans_reglages(self):
        with self.assertRaises(SystemExit):
            alerte.envoyer(alerte.composer(alerte.offres_a_signaler(self.p)), {})


if __name__ == "__main__":
    unittest.main()
