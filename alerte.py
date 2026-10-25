"""Alerte e-mail : les offres du dernier passage qui atteignent une rareté choisie.

Lit vus.json et passages.json dans le dossier des données du profil, garde les
offres vues au dernier passage dont la rareté atteint [alerte] rarete_min du profil
(« epique » par défaut), et les envoie dans un seul e-mail. Sans offre, rien ne part.

Lancer :  python alerte.py --profil profil.toml             (affiche l'e-mail, n'envoie rien)
          python alerte.py --profil profil.toml --envoyer   (envoie par SMTP)

L'envoi lit le serveur et le compte dans des variables d'environnement, jamais
dans un fichier du dépôt (sur GitHub : les secrets du dépôt) :
    SMTP_HOTE, SMTP_PORT (587 par défaut, 465 pour SSL direct),
    SMTP_UTILISATEUR, SMTP_MOT_DE_PASSE,
    ALERTE_A (le destinataire), ALERTE_DE (l'expéditeur, SMTP_UTILISATEUR par défaut).
"""

import argparse
import html
import json
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent
sys.path.insert(0, str(DOSSIER))
sys.dont_write_bytecode = True
import profil as module_profil  # noqa: E402
import score  # noqa: E402

# De la plus basse à la plus haute : sert à comparer deux raretés.
ORDRE = ["commune", "peu_commune", "rare", "epique", "legendaire"]


def offres_a_signaler(p):
    """Les offres du dernier passage dont la rareté atteint le seuil, la meilleure d'abord."""
    seuil = p.get("alerte", {}).get("rarete_min", "epique")
    if seuil not in ORDRE:
        raise module_profil.ProfilInvalide(f"[alerte] rarete_min doit valoir {', '.join(ORDRE)}.")
    dossier = p["dossier_donnees"]
    passages = json.loads((dossier / "passages.json").read_text(encoding="utf-8")) \
        if (dossier / "passages.json").exists() else []
    if not passages:
        return []
    jour = passages[-1]["date"]
    vus = json.loads((dossier / "vus.json").read_text(encoding="utf-8"))
    choisies = []
    for cle, fiche in vus.items():
        if fiche.get("vu_le") != jour or fiche.get("doublon") or fiche.get("page"):
            continue
        note = score.noter(fiche, p)
        if ORDRE.index(note["rarete"]) >= ORDRE.index(seuil):
            choisies.append(dict(fiche, cle=cle, **note))
    return sorted(choisies, key=lambda o: -o["score"])


def composer(offres):
    """Le message : un texte brut et sa version HTML, une offre par bloc."""
    nombre = f"{len(offres)} offre{'s' if len(offres) > 1 else ''}"
    meilleure = score.LIBELLES[offres[0]["rarete"]]
    message = EmailMessage()
    message["Subject"] = f"radar-offres : {nombre}, la meilleure {meilleure} ({offres[0]['score']})"

    texte, blocs = [], []
    for o in offres:
        rarete = score.LIBELLES[o["rarete"]]
        details = " · ".join(x for x in (o.get("lieu"), o.get("salaire")) if x)
        atouts = ", ".join(r["tag"] for r in o.get("colle") or [])
        texte += [f"{o['score']} ({rarete}) {o['employeur']} : {o['titre']}", f"  {details}",
                  f"  colle : {atouts or 'rien de repéré'}", f"  {o['lien']}", ""]
        blocs.append(
            f'<p style="margin:0 0 16px"><b>{o["score"]} · {html.escape(rarete)}</b> '
            f'{html.escape(o["employeur"])}<br>'
            f'<a href="{html.escape(o["lien"])}">{html.escape(o["titre"])}</a><br>'
            f'<span style="color:#666">{html.escape(details)}</span><br>'
            f'<span style="color:#2f8f4e">{html.escape(atouts)}</span></p>')
    message.set_content("\n".join(texte))
    message.add_alternative(f"<div style=\"font-family:sans-serif\">{''.join(blocs)}</div>", subtype="html")
    return message


def envoyer(message, env=os.environ):
    """Envoie le message par SMTP, avec les réglages des variables d'environnement."""
    manquantes = [v for v in ("SMTP_HOTE", "SMTP_UTILISATEUR", "SMTP_MOT_DE_PASSE", "ALERTE_A") if not env.get(v)]
    if manquantes:
        sys.exit(f"Alerte : variables manquantes : {', '.join(manquantes)}.")
    message["From"] = env.get("ALERTE_DE") or env["SMTP_UTILISATEUR"]
    message["To"] = env["ALERTE_A"]
    port = int(env.get("SMTP_PORT") or 587)
    contexte = ssl.create_default_context()
    if port == 465:
        serveur = smtplib.SMTP_SSL(env["SMTP_HOTE"], port, context=contexte, timeout=60)
    else:
        serveur = smtplib.SMTP(env["SMTP_HOTE"], port, timeout=60)
        serveur.starttls(context=contexte)
    with serveur:
        serveur.login(env["SMTP_UTILISATEUR"], env["SMTP_MOT_DE_PASSE"])
        serveur.send_message(message)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    lecteur = argparse.ArgumentParser(description="Envoie par e-mail les meilleures offres du dernier passage.")
    lecteur.add_argument("--profil", default="profil.toml", help="le profil de recherche")
    lecteur.add_argument("--envoyer", action="store_true", help="envoie vraiment (sinon affiche l'e-mail)")
    args = lecteur.parse_args()
    try:
        offres = offres_a_signaler(module_profil.charger(args.profil))
    except module_profil.ProfilInvalide as erreur:
        sys.exit(f"Profil : {erreur}")
    if not offres:
        print("Alerte : aucune offre au niveau demandé dans le dernier passage, rien à envoyer.")
        sys.exit(0)
    message = composer(offres)
    if args.envoyer:
        envoyer(message)
        print(f"Alerte : {len(offres)} offre(s) envoyée(s).")
    else:
        print(message["Subject"], "\n")
        print(message.get_body(("plain",)).get_content())
