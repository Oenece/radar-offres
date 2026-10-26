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


# Les couleurs de rareté des cartes (modele/cartes.css), répétées ici : un e-mail n'a pas de feuille de style.
COULEURS = {"commune": "#8E8E93", "peu_commune": "#30A14E", "rare": "#2B6FD6",
            "epique": "#8A3FD1", "legendaire": "#C98A00"}
POLICE = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"


def lien_du_passage(env=os.environ):
    """La page du passage GitHub Actions (avec le tableau en pièce jointe), si l'alerte y tourne."""
    if env.get("GITHUB_RUN_ID") and env.get("GITHUB_REPOSITORY"):
        serveur = env.get("GITHUB_SERVER_URL", "https://github.com")
        return f"{serveur}/{env['GITHUB_REPOSITORY']}/actions/runs/{env['GITHUB_RUN_ID']}"
    return None


def pastilles(regles, fond, encre):
    """Les « colle » ou « coince » d'une offre, en petites étiquettes."""
    return "".join(
        f'<span style="display:inline-block;margin:0 6px 6px 0;padding:3px 10px;border-radius:999px;'
        f'background:{fond};color:{encre};font-size:12px;line-height:18px">{html.escape(r["tag"])}</span>'
        for r in regles)


def carte(o):
    """Une offre en carte : rareté et score, titre, employeur, étiquettes, bouton."""
    couleur = COULEURS[o["rarete"]]
    details = " · ".join(html.escape(x) for x in (o["employeur"], o.get("lieu"), o.get("salaire")) if x)
    etiquettes = pastilles(o.get("colle") or [], "#E8F5EC", "#1E7A3C") \
        + pastilles(o.get("coince") or [], "#FDF0E6", "#A85A12")
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 16px;'
        f'background:#FFFFFF;border:1px solid #E5E5EA;border-left:4px solid {couleur};border-radius:12px">'
        f'<tr><td style="padding:18px 20px">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:{couleur}">'
        f'{html.escape(score.LIBELLES[o["rarete"]])}</td>'
        f'<td align="right" style="font-size:22px;font-weight:700;color:{couleur}">{o["score"]}'
        f'<span style="font-size:12px;font-weight:400;color:#8E8E93"> / 100</span></td>'
        f'</tr></table>'
        f'<div style="margin:6px 0 4px;font-size:17px;font-weight:600;line-height:23px;color:#1D1D1F">'
        f'{html.escape(o["titre"])}</div>'
        f'<div style="margin:0 0 12px;font-size:14px;color:#6E6E73">{details}</div>'
        f'<div style="margin:0 0 8px">{etiquettes}</div>'
        f'<a href="{html.escape(o["lien"])}" style="display:inline-block;padding:9px 18px;border-radius:999px;'
        f'background:{couleur};color:#FFFFFF;font-size:14px;font-weight:600;text-decoration:none">Voir l\'offre</a>'
        f'</td></tr></table>')


def composer(offres, lien_tableau=None):
    """Le message : un texte brut et sa version HTML, une carte par offre."""
    nombre = f"{len(offres)} offre{'s' if len(offres) > 1 else ''}"
    meilleure = score.LIBELLES[offres[0]["rarete"]]
    message = EmailMessage()
    message["Subject"] = f"radar-offres : {nombre}, la meilleure {meilleure} ({offres[0]['score']})"

    texte = []
    for o in offres:
        rarete = score.LIBELLES[o["rarete"]]
        details = " · ".join(x for x in (o.get("lieu"), o.get("salaire")) if x)
        atouts = ", ".join(r["tag"] for r in o.get("colle") or [])
        texte += [f"{o['score']} ({rarete}) {o['employeur']} : {o['titre']}", f"  {details}",
                  f"  colle : {atouts or 'rien de repéré'}", f"  {o['lien']}", ""]
    if lien_tableau:
        texte.append(f"Le tableau complet : {lien_tableau}")
    message.set_content("\n".join(texte))

    pied = (f'<a href="{html.escape(lien_tableau)}" style="color:#2B6FD6;text-decoration:none">'
            f'Ouvrir le tableau complet</a> · ' if lien_tableau else "")
    message.add_alternative(
        f'<div style="margin:0;padding:24px 12px;background:#F5F5F7;font-family:{POLICE}">'
        f'<table role="presentation" align="center" width="100%" cellpadding="0" cellspacing="0" '
        f'style="max-width:560px;margin:0 auto">'
        f'<tr><td style="padding:0 4px 16px">'
        f'<div style="font-size:12px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;'
        f'color:#8E8E93">radar-offres</div>'
        f'<div style="margin-top:4px;font-size:24px;font-weight:700;line-height:30px;color:#1D1D1F">'
        f'{nombre[0].upper() + nombre[1:]} qui vous correspond{"ent" if len(offres) > 1 else ""}</div>'
        f'</td></tr>'
        f'<tr><td>{"".join(carte(o) for o in offres)}</td></tr>'
        f'<tr><td style="padding:4px 4px 0;font-size:12px;line-height:18px;color:#8E8E93">'
        f'{pied}Envoyé par la veille du matin. Le seuil se règle dans [alerte] de profil.toml.</td></tr>'
        f'</table></div>', subtype="html")
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
    message = composer(offres, lien_du_passage())
    if args.envoyer:
        envoyer(message)
        print(f"Alerte : {len(offres)} offre(s) envoyée(s).")
    else:
        print(message["Subject"], "\n")
        print(message.get_body(("plain",)).get_content())
