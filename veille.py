"""Veille hebdomadaire d'offres d'emploi, hors LinkedIn.

Lit les flux publics des employeurs listés dans employeurs.csv (Ashby, Lever,
Greenhouse, SmartRecruiters, Teamtailor, ou une page carrière simple), garde
les postes qui correspondent au profil (lieux, thèmes, exclusions), et écrit les
nouveautés dans offres-AAAA-MM-JJ.md.

Tous les critères viennent de profil.toml (voir profil.py et profil.exemple.toml) :
le code ne contient que la logique.

Ce qui a déjà été vu est noté dans vus.json : un second passage ne ressort rien.
Chaque passage refait aussi tableau.html (vue filtrable, voir tableau.py).

Lancer :  python veille.py --profil chemin/vers/profil.toml
Options : --tout         ignore vus.json pour ce passage (ne le modifie pas)
          --sans-detail  ne lit pas le détail des offres SmartRecruiters (plus rapide)

Aucune connexion à un compte, rien n'est envoyé : le script ne fait que des GET
sur des pages et API publiques.
"""

import argparse
import csv
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

DOSSIER = Path(__file__).resolve().parent
sys.path.insert(0, str(DOSSIER))  # profil.py et tableau.py sont à côté (python -I ne l'ajoute pas)
sys.dont_write_bytecode = True    # pas de dossier __pycache__ à côté du code
import profil as module_profil  # noqa: E402
import score  # noqa: E402
from salaire import fourchette  # noqa: E402

ENTETES = {"User-Agent": "radar-offres/0.1 (lecture des offres publiques)"}


# ---------------------------------------------------------------------------
# 1. Les règles de tri (les listes viennent du profil, noté p)
# ---------------------------------------------------------------------------

def trouve(motifs, texte):
    """Le premier motif (expression régulière) qui apparaît dans le texte, ou None."""
    return next((m for m in motifs if re.search(m, texte)), None)


def cherche(motifs, texte):
    """Vrai si un des motifs apparaît dans le texte."""
    return trouve(motifs, texte) is not None


def pourquoi_lieu(lieu, p):
    """(gardé ?, raison) : un lieu du profil, un lieu exact, ou remote vers une zone acceptée.

    Le lieu peut lister plusieurs endroits séparés par « / » : un seul suffit.
    """
    lieux = p["lieux"]
    for morceau in lieu.lower().split(" / "):
        morceau = morceau.strip()
        ville = next((m for m in lieux["acceptes"] if m in morceau), None)
        if ville:
            return True, f"lieu « {ville} »"
        if morceau in lieux["exacts"]:
            return True, f"lieu exact « {morceau} »"
        # Remote : gardé s'il vise une zone acceptée, ou s'il ne nomme aucun pays.
        if "remote" in morceau or "télétravail" in morceau or "anywhere" in morceau:
            zone = next((m for m in lieux["remote_zones"] if m in morceau), None)
            if zone:
                return True, f"remote vers « {zone} »"
            if morceau in ("remote", "fully remote", "télétravail", "anywhere"):
                return True, "remote sans pays"
    return False, f"lieu hors profil (« {lieu or 'non précisé'} »)"


def lieu_accepte(lieu, p):
    return pourquoi_lieu(lieu, p)[0]


def pourquoi_theme(titre, description, p):
    """(gardé ?, raison) : le titre touche un thème, ou la description parle d'IA et du métier.

    Les postes d'ingénieur ne passent que si le titre les tourne vers le métier
    (themes.ingenieur_ok). Sans thème dans le titre, il faut un mot d'IA et au moins
    themes.metier_minimum mots du métier dans la description.
    """
    t = p["themes"]
    titre = titre.lower()
    exclu = trouve(t["exclus_titre"], titre)
    if exclu:
        return False, f"titre exclu par « {exclu} »"
    if re.search(t["ingenieur"], titre) and not cherche(t["ingenieur_ok"], titre):
        return False, "poste d'ingénieur sans mot de ingenieur_ok"
    theme = trouve(t["titre"], titre)
    if theme:
        return True, f"titre « {theme} »"
    texte = description.lower()
    mots_metier = [m for m in t["metier"] if re.search(m, texte)]
    ia = trouve(t["ia"], texte)
    if ia and len(mots_metier) >= t["metier_minimum"]:
        return True, f"description : « {ia} » et {len(mots_metier)} mots du métier"
    return False, "aucun thème dans le titre, description insuffisante"


def theme_accepte(titre, description, p):
    return pourquoi_theme(titre, description, p)[0]


def annees_demandees(texte):
    """Le plus grand nombre d'années d'expérience demandé, ou None."""
    trouves = re.findall(r"(\d{1,2})\s*\+?\s*(?:years|ans|année)", texte)
    nombres = [int(n) for n in trouves if 1 <= int(n) <= 15]
    return max(nombres) if nombres else None


def lecture(offre, p):
    """Les raisons « colle » et « coince » de l'offre, d'après les règles du profil."""
    texte = (offre["titre"] + " " + offre["description"]).lower()
    texte = re.sub(r"https?://\S+", " ", texte)  # un lien YouTube ne dit rien du poste
    colle = [{"tag": r["tag"], "texte": r["texte"]} for r in p["colle"] if re.search(r["motif"], texte)]
    coince = [{"tag": r["tag"], "texte": r["texte"]} for r in p["coince"] if re.search(r["motif"], texte)]
    perso = p["profil"]
    ans = annees_demandees(texte)
    if ans and ans >= perso["annees_alerte"]:
        experience = f"{perso['annees_experience']:g}".replace(".", ",")
        coince.append({"tag": f"{ans} ans", "texte": f"{ans} ans d'expérience demandés (tu en as {experience})"})
    maxi = offre.get("salaire_max")
    if maxi and offre.get("devise", "EUR") == perso["devise"] and maxi < perso["salaire_bas"]:
        cible = fourchette(*perso["salaire_cible"], perso["devise"])
        coince.append({"tag": "Salaire bas", "texte": f"salaire sous la cible de {cible}"})
    # On garde les quatre premières raisons de chaque côté pour rester lisible.
    return colle[:4], coince[:4]


# ---------------------------------------------------------------------------
# 2. La lecture des flux, un lecteur par ATS
# ---------------------------------------------------------------------------

def telecharger(url):
    """GET simple, renvoie le texte de la réponse."""
    requete = urllib.request.Request(url, headers=ENTETES)
    for essai in (1, 2):  # un second essai si le serveur est lent
        try:
            with urllib.request.urlopen(requete, timeout=60) as reponse:
                return reponse.read().decode("utf-8", errors="replace")
        except TimeoutError:
            if essai == 2:
                raise


def sans_html(texte):
    """Retire les balises et décode les entités (&amp; etc.)."""
    texte = html.unescape(texte or "")
    texte = re.sub(r"<[^>]+>", " ", texte)
    return re.sub(r"\s+", " ", html.unescape(texte)).strip()


def salaire_dans_le_texte(texte):
    """Repère une fourchette du type « 50 à 65 k€ » ou « 50 000 € - 65 000 € »."""
    # L'unité du premier nombre est facultative : « 50 à 65 k€ » la donne une seule fois.
    m = re.search(r"(\d{2,3})\s?(?:k|K|000)?\s?€?\s?(?:-|à|to|–)\s?(\d{2,3})\s?(?:k|K|000)\s?€", texte)
    if m:
        return int(m.group(1)) * 1000, int(m.group(2)) * 1000
    return None, None


# Les mots qui ouvrent la partie « le poste » d'une fiche, après la présentation de l'entreprise.
DEBUT_POSTE = [r"what you'?ll do", r"your mission", r"the role", r"about the role", r"the job",
               r"responsibilities", r"vos missions", r"votre mission", r"le poste",
               r"description du poste", r"vous serez", r"in this role", r"what you will do"]


def extrait(description, longueur=900):
    """Le début de la partie « poste » de la fiche, sans la présentation de l'entreprise."""
    texte = re.sub(r"https?://\S+", "", description or "")
    texte = re.sub(r"\s+", " ", texte).strip()
    bas = texte.lower()
    positions = [m.start() for motif in DEBUT_POSTE for m in [re.search(motif, bas)] if m]
    if positions and min(positions) < len(texte) - 200:
        # On repart du début de la phrase qui contient le mot, pas du mot lui-même.
        debut = max(bas.rfind(". ", 0, min(positions)), bas.rfind(": ", 0, min(positions)))
        texte = texte[debut + 2 if debut >= 0 else 0:]
    if len(texte) <= longueur:
        return texte
    return texte[:longueur].rsplit(" ", 1)[0] + " …"  # on coupe entre deux mots


def jour_iso(valeur):
    """Ramène une date d'ATS (ISO, millisecondes, RFC 822) au format AAAA-MM-JJ."""
    if not valeur:
        return ""
    if isinstance(valeur, (int, float)):  # Lever : millisecondes depuis 1970
        return datetime.fromtimestamp(valeur / 1000, tz=timezone.utc).date().isoformat()
    if re.match(r"\d{4}-\d{2}-\d{2}", valeur):
        return valeur[:10]
    try:
        return parsedate_to_datetime(valeur).date().isoformat()  # Teamtailor
    except (TypeError, ValueError):
        return ""


# Le mode de travail, écrit pareil quel que soit l'ATS.
MODES = {"remote": "remote", "fully": "remote", "hybrid": "hybride", "onsite": "sur site",
         "on-site": "sur site", "office": "sur site"}


def mode_lisible(valeur):
    return MODES.get((valeur or "").lower().replace(" ", ""), "")


def offre_vide(**champs):
    """Une offre avec tous ses champs, pour que chaque lecteur rende la même forme."""
    base = {"description": "", "salaire_min": None, "salaire_max": None, "devise": "EUR",
            "publiee_le": "", "contrat": "", "mode": "", "equipe": ""}
    base.update(champs)
    return base


def lire_ashby(ident):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{ident}?includeCompensation=true"
    for job in json.loads(telecharger(url))["jobs"]:
        lieux = [job.get("location") or ""]
        lieux += [s.get("location", "") for s in job.get("secondaryLocations") or []]
        # Le drapeau remote se colle au lieu (« Seoul (remote) ») : il ne vaut pas partout.
        if job.get("isRemote"):
            lieux = [f"{l} (remote)" for l in lieux]
        offre = offre_vide(id=job["id"], titre=job["title"], lien=job["jobUrl"],
                           lieu=" / ".join(l for l in lieux if l),
                           description=job.get("descriptionPlain") or "",
                           publiee_le=jour_iso(job.get("publishedAt")),
                           contrat=re.sub(r"(?<!^)([A-Z])", r" \1", job.get("employmentType") or ""),
                           mode=mode_lisible(job.get("workplaceType")),
                           equipe=job.get("team") or job.get("department") or "")
        for c in (job.get("compensation") or {}).get("summaryComponents") or []:
            if c.get("compensationType") == "Salary" and c.get("maxValue"):
                offre["salaire_min"], offre["salaire_max"] = c.get("minValue"), c["maxValue"]
                offre["devise"] = c.get("currencyCode") or "EUR"
        yield offre


def lire_lever(ident):
    url = f"https://api.lever.co/v0/postings/{ident}?mode=json"
    for job in json.loads(telecharger(url)):
        cat = job.get("categories") or {}
        lieux = cat.get("allLocations") or [cat.get("location") or ""]
        if job.get("workplaceType") == "remote":
            lieux = [f"{l} (remote)" for l in lieux]
        description = job.get("descriptionPlain", "") + " " + job.get("additionalPlain", "")
        for liste in job.get("lists") or []:
            description += " " + liste.get("text", "") + " " + sans_html(liste.get("content", ""))
        offre = offre_vide(id=job["id"], titre=job["text"], lien=job["hostedUrl"],
                           lieu=" / ".join(l for l in lieux if l), description=description,
                           publiee_le=jour_iso(job.get("createdAt")),
                           contrat=cat.get("commitment") or "",
                           mode=mode_lisible(job.get("workplaceType")),
                           equipe=cat.get("team") or cat.get("department") or "")
        fourch = job.get("salaryRange") or {}
        if fourch.get("max") and "year" in (fourch.get("interval") or "year"):
            offre["salaire_min"], offre["salaire_max"] = fourch.get("min"), fourch["max"]
            offre["devise"] = fourch.get("currency") or "EUR"
        yield offre


def lire_greenhouse(ident):
    url = f"https://boards-api.greenhouse.io/v1/boards/{ident}/jobs?content=true"
    for job in json.loads(telecharger(url))["jobs"]:
        lieux = [(job.get("location") or {}).get("name", "")]
        lieux += [o.get("location") or o.get("name") or "" for o in job.get("offices") or []]
        departements = job.get("departments") or [{}]
        yield offre_vide(id=str(job["id"]), titre=job["title"], lien=job["absolute_url"],
                         lieu=" / ".join(l for l in lieux if l),
                         description=sans_html(job.get("content", "")),
                         publiee_le=jour_iso(job.get("first_published") or job.get("updated_at")),
                         equipe=departements[0].get("name") or "")


def lire_smartrecruiters(ident):
    debut, total = 0, 1
    while debut < total:
        url = f"https://api.smartrecruiters.com/v1/companies/{ident}/postings?limit=100&offset={debut}"
        page = json.loads(telecharger(url))
        total = page["totalFound"]
        debut += 100
        for job in page["content"]:
            loc = job.get("location") or {}
            lieu = loc.get("fullLocation") or loc.get("city") or ""
            # Le drapeau remote se colle au lieu, comme pour les autres ATS : « Tokyo (remote) »
            # ne doit pas passer pour un « remote » sans pays.
            if loc.get("remote"):
                lieu = f"{lieu} (remote)" if lieu else "remote"
            mode = "remote" if loc.get("remote") else "hybride" if loc.get("hybrid") else ""
            yield offre_vide(id=job["id"], titre=job["name"], lieu=lieu, mode=mode,
                             lien=f"https://jobs.smartrecruiters.com/{ident}/{job['id']}",
                             publiee_le=jour_iso(job.get("releasedDate")),
                             contrat=(job.get("typeOfEmployment") or {}).get("label", ""),
                             equipe=(job.get("function") or {}).get("label", ""),
                             detail=job["ref"])


def detail_smartrecruiters(offre):
    """La liste SmartRecruiters n'a pas la description : on la lit à part."""
    detail = json.loads(telecharger(offre["detail"]))
    sections = (detail.get("jobAd") or {}).get("sections") or {}
    # Le poste d'abord, la présentation de l'entreprise à la fin (l'extrait lit le début).
    ordre = ["jobDescription", "qualifications", "additionalInformation", "companyDescription"]
    offre["description"] = " ".join(sans_html((sections.get(n) or {}).get("text", "")) for n in ordre)
    offre["lien"] = detail.get("postingUrl") or offre["lien"]


def lire_teamtailor(ident):
    ns = "{https://teamtailor.com/locations}"
    racine = ET.fromstring(telecharger(f"https://{ident}.teamtailor.com/jobs.rss"))
    for item in racine.iter("item"):
        lieux = [e.text or "" for e in item.iter(ns + "city")]
        lieux += [e.text or "" for e in item.iter(ns + "country")]
        statut = item.findtext("remoteStatus") or ""
        if statut in ("fully", "remote"):
            lieux = [f"{l} (remote)" for l in lieux] or ["remote"]
        yield offre_vide(id=item.findtext("guid"), titre=item.findtext("title") or "",
                         lien=item.findtext("link") or "", lieu=" / ".join(l for l in lieux if l),
                         description=sans_html(item.findtext("description")),
                         publiee_le=jour_iso(item.findtext("pubDate")),
                         mode=mode_lisible(statut), equipe=item.findtext(ns + "department") or "")


def lire_page(url):
    """Page carrière maison : on relève les liens vers des sous-pages d'offre.

    Pas de description ni de lieu fiables : chaque nouveau lien sort tel quel,
    marqué « page maison », et se lit à la main.
    """
    chemin = urlparse(url).path.rstrip("/")
    vus = set()
    for lien in re.findall(r'href="([^"]+)"', telecharger(url)):
        complet = urljoin(url, lien).split("#")[0].rstrip("/")
        if urlparse(complet).path.startswith(chemin + "/") and complet not in vus:
            vus.add(complet)
            titre = complet.rsplit("/", 1)[-1].replace("-", " ").capitalize()
            yield offre_vide(id=complet, titre=titre, lien=complet, lieu="page maison", page=True)


LECTEURS = {"ashby": lire_ashby, "lever": lire_lever, "greenhouse": lire_greenhouse,
            "smartrecruiters": lire_smartrecruiters, "teamtailor": lire_teamtailor,
            "page": lire_page}


# ---------------------------------------------------------------------------
# 3. Le passage : lire, filtrer, comparer à vus.json, écrire
# ---------------------------------------------------------------------------

# Ce que vus.json garde de chaque offre : de quoi refaire le tableau sans relire les flux.
CHAMPS_GARDES = ["employeur", "famille", "ats", "titre", "lien", "lieu", "salaire",
                 "salaire_min", "salaire_max", "devise", "publiee_le", "contrat", "mode",
                 "equipe", "colle", "coince", "extrait", "page"]


def passage(p, tout=False, avec_detail=True):
    dossier = p["dossier_donnees"]
    dossier.mkdir(parents=True, exist_ok=True)
    fichier_vus = dossier / "vus.json"
    with p["chemin_employeurs"].open(encoding="utf-8") as f:
        employeurs = list(csv.DictReader(f))
    vus = json.loads(fichier_vus.read_text(encoding="utf-8")) if fichier_vus.exists() else {}
    aujourd_hui = date.today().isoformat()
    exclus_titre = p["themes"]["exclus_titre"]

    nouvelles, doublons, erreurs, manuels = [], [], [], []
    titres_du_jour = set()
    lus = 0
    for emp in employeurs:
        ats = emp["ats"]
        if ats == "manuel":
            manuels.append(emp)
            continue
        print(f"  {emp['nom']:<16} ({ats})", end=" ", flush=True)
        try:
            gardees = 0
            for offre in LECTEURS[ats](emp["identifiant"]):
                cle = f"{ats}:{emp['identifiant']}:{offre['id']}"
                if cle in vus:
                    vus[cle]["en_ligne_le"] = aujourd_hui  # toujours publiée
                    if not tout:
                        continue
                if not offre.get("page") and not lieu_accepte(offre["lieu"], p):
                    continue
                # SmartRecruiters : on ne lit le détail que si le titre n'est pas déjà écarté.
                if offre.get("detail") and avec_detail and not cherche(exclus_titre, offre["titre"].lower()):
                    detail_smartrecruiters(offre)
                if not offre.get("page") and not theme_accepte(offre["titre"], offre["description"], p):
                    continue
                if not offre["salaire_max"]:
                    offre["salaire_min"], offre["salaire_max"] = salaire_dans_le_texte(offre["description"])
                offre["salaire"] = fourchette(offre["salaire_min"], offre["salaire_max"], offre["devise"])
                offre["employeur"], offre["famille"], offre["cle"] = emp["nom"], emp["famille"], cle
                offre["ats"] = ats
                offre["colle"], offre["coince"] = lecture(offre, p)
                offre["extrait"] = extrait(offre["description"])
                # Même poste publié dans plusieurs villes : une seule ligne, les autres notées vues.
                titre_court = (emp["nom"], offre["titre"].strip().lower())
                if titre_court in titres_du_jour:
                    doublons.append(offre)
                    continue
                titres_du_jour.add(titre_court)
                nouvelles.append(offre)
                gardees += 1
            lus += 1
            print(f"-> {gardees} nouvelle(s)")
        except Exception as erreur:  # une source en panne ne bloque pas les autres
            print(f"-> erreur : {erreur}")
            erreurs.append((emp["nom"], str(erreur)[:120]))

    if not nouvelles:
        print("\nRien de nouveau.")
    else:
        ecrire_sortie(nouvelles, erreurs, manuels, aujourd_hui, p)

    # On ne met vus.json à jour qu'en passage normal.
    if not tout:
        for offre in nouvelles:
            fiche = {champ: offre.get(champ) for champ in CHAMPS_GARDES}
            fiche.update(vu_le=aujourd_hui, en_ligne_le=aujourd_hui)
            vus[offre["cle"]] = fiche
        for offre in doublons:
            vus[offre["cle"]] = {"vu_le": aujourd_hui, "en_ligne_le": aujourd_hui,
                                 "employeur": offre["employeur"], "titre": offre["titre"],
                                 "lien": offre["lien"], "doublon": True}
        fichier_vus.write_text(json.dumps(vus, ensure_ascii=False, indent=1), encoding="utf-8")
        noter_passage(dossier / "passages.json", aujourd_hui, len(nouvelles), lus, erreurs, manuels)

    # Le tableau se refait à chaque passage, même sans nouveauté (les « en ligne » bougent).
    import tableau
    tableau.ecrire_tableau(p)
    return nouvelles


def noter_passage(fichier, jour, nb_nouvelles, lus, erreurs, manuels):
    """Ajoute le passage du jour à passages.json (historique lu par le tableau)."""
    historique = json.loads(fichier.read_text(encoding="utf-8")) if fichier.exists() else []
    historique.append({"date": jour, "heure": datetime.now().strftime("%H:%M"),
                       "nouvelles": nb_nouvelles, "employeurs_lus": lus,
                       "erreurs": [{"employeur": n, "message": m} for n, m in erreurs],
                       "manuels": [{"employeur": e["nom"], "lien": e["identifiant"], "note": e["note"]}
                                   for e in manuels]})
    fichier.write_text(json.dumps(historique, ensure_ascii=False, indent=1), encoding="utf-8")


def ecrire_sortie(nouvelles, erreurs, manuels, jour, p):
    """Écrit (ou complète, si un passage a déjà eu lieu aujourd'hui) offres-JOUR.md."""
    sortie = p["dossier_donnees"] / f"offres-{jour}.md"
    lignes = []
    if not sortie.exists():
        lignes += [f"# Veille d'offres, {jour}", "",
                   "Sortie de `veille.py` : seulement ce qui n'avait pas encore été vu. "
                   "Les lignes « colle » et « coince » sont des motifs repérés dans la fiche, "
                   "à relire sur l'offre. Vue filtrable : `tableau.html`.", ""]
    else:
        lignes += ["", "## Passage complémentaire", ""]

    # Par famille d'employeur, les offres au meilleur score d'adéquation d'abord.
    for o in nouvelles:
        o["adequation"] = None if o.get("page") else score.noter(o, p)
    nouvelles.sort(key=lambda o: (o["famille"], -(o["adequation"] or {"score": -1})["score"]))

    famille = None
    for o in nouvelles:
        if o["famille"] != famille:
            famille = o["famille"]
            lignes += ["", f"## {famille[0].upper() + famille[1:]}", ""]
        salaire = o["salaire"] or "non affiché"
        lieux = list(dict.fromkeys(o["lieu"].split(" / ")))  # sans les doublons, dans l'ordre
        lieu = " / ".join(lieux[:4]) + (" …" if len(lieux) > 4 else "")
        publiee = f" ; publiée le {o['publiee_le']}" if o["publiee_le"] else ""
        note = f" ; score {o['adequation']['score']} ({score.LIBELLES[o['adequation']['rarete']]})" if o["adequation"] else ""
        lignes.append(f"- **{o['employeur']}**, [{o['titre'].strip()}]({o['lien']}) ; {lieu} ; {salaire}{publiee}{note}")
        if o.get("page"):
            lignes.append("  - page maison : lire l'offre à la main")
        else:
            lignes.append("  - colle : " + ("; ".join(r["texte"] for r in o["colle"]) or "rien de repéré"))
            lignes.append("  - coince : " + ("; ".join(r["texte"] for r in o["coince"]) or "rien de repéré"))

    lignes += ["", "## À regarder à la main", ""]
    recherches = p["a_la_main"]["recherches_apec"]
    if recherches:
        lignes.append("- APEC : la recherche est protégée par un captcha (DataDome), elle ne se lit pas "
                      "sans navigateur. Recherches à faire : "
                      + ", ".join(f"« {r} »" for r in recherches) + ".")
    for emp in manuels:
        lignes.append(f"- {emp['nom']} : {emp['identifiant']} ({emp['note']})")
    if erreurs:
        lignes += ["", "## Sources en erreur", ""]
        lignes += [f"- {nom} : {message}" for nom, message in erreurs]

    with sortie.open("a", encoding="utf-8") as f:
        f.write("\n".join(lignes) + "\n")
    print(f"\n{len(nouvelles)} offre(s) nouvelle(s) -> {sortie.name}")


def options(arguments=None):
    lecteur = argparse.ArgumentParser(description="Veille d'offres d'emploi sur les flux publics des ATS.")
    lecteur.add_argument("--profil", default="profil.toml",
                         help="le profil de recherche (par défaut : profil.toml dans le dossier courant)")
    lecteur.add_argument("--tout", action="store_true",
                         help="ignore vus.json pour ce passage (ne le modifie pas)")
    lecteur.add_argument("--sans-detail", action="store_true",
                         help="ne lit pas le détail des offres SmartRecruiters (plus rapide)")
    return lecteur.parse_args(arguments)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    args = options()
    try:
        profil = module_profil.charger(args.profil)
    except module_profil.ProfilInvalide as erreur:
        sys.exit(f"Profil : {erreur}")
    print("Veille d'offres :")
    passage(profil, tout=args.tout, avec_detail=not args.sans_detail)
