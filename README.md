# radar-offres

**Une veille d'offres d'emploi qui lit directement les sites carrière des employeurs, garde ce qui
correspond à ton profil, et note chaque offre selon à quel point elle te correspond.**

Python 3.11+, aucune dépendance, aucun compte, aucune donnée envoyée.

[![Tests](https://github.com/Oenece/radar-offres/actions/workflows/tests.yml/badge.svg)](https://github.com/Oenece/radar-offres/actions/workflows/tests.yml)
**Démo en ligne**, mise à jour chaque matin avec le profil d'exemple : [oenece.github.io/radar-offres](https://oenece.github.io/radar-offres/)

---

## Le problème

Chercher un poste précis (par exemple « consultant SEA à Paris », « data marketing à Lyon ») sur
les grands sites d'emploi, c'est :

- **du bruit** : des centaines d'annonces sponsorisées, en double ou hors sujet ;
- **du retard** : beaucoup d'offres paraissent d'abord sur le site carrière de l'employeur ;
- **des angles morts** : les entreprises qui t'intéressent vraiment ne publient pas toutes partout ;
- **aucune aide pour trier** : savoir si une offre te correspond demande de lire chaque fiche.

Or la plupart des entreprises tech publient leurs offres avec un ATS (Ashby, Lever, Greenhouse,
SmartRecruiters, Teamtailor), et ces outils exposent une **API publique** : la liste complète des
postes, à jour, en JSON ou en RSS.

## Ce que fait radar-offres

1. **Lit** les flux publics d'une liste d'employeurs que tu choisis (`employeurs.csv`).
2. **Filtre** les postes selon ton profil : lieux, télétravail, thèmes du titre, exclusions.
3. **Lit chaque fiche** et en tire ce qui colle à ton parcours et ce qui coince (outil jamais
   pratiqué, années d'expérience demandées, salaire sous ta cible…).
4. **Note** chaque offre de 0 à 100 selon son adéquation à ton profil, avec le détail des points.
   La note donne une rareté, de « commune » à « légendaire » : une offre rare est une offre
   qui te correspond, pas une offre difficile à trouver.
5. **Se souvient** de ce qui a déjà été vu : un second passage ne ressort que les nouveautés.
6. **Produit** un compte rendu Markdown du jour et une page HTML, en un seul fichier qui s'ouvre
   sans serveur : les nouvelles offres arrivent en **boosters de cartes** à ouvrir, et chaque
   candidature entre dans un **album** où tu la suis jusqu'à l'offre.

```
employeurs.csv ──► lecteurs ATS ──► offre normalisée ──► filtre lieu ──► filtre thème
                   (Ashby, Lever,                                              │
                    Greenhouse…)                                               ▼
tableau.html ◄── vus.json ◄── dédoublonnage ◄── score d'adéquation ◄── colle / coince
offres-JJ.md                                                            salaire, extrait
```

## Démarrage

```bash
git clone https://github.com/Oenece/radar-offres.git
cd radar-offres
cp profil.exemple.toml profil.toml
cp employeurs.exemple.csv employeurs.csv
python essai.py      # ce que le profil garde ou écarte, et pourquoi (ne modifie rien)
python veille.py     # le passage : écrit les nouveautés et le tableau
```

Le profil d'exemple cherche du marketing d'acquisition (SEA, SEO, GEO, paid social) à Paris ou à
Lyon, chez 13 employeurs d'exemple. Le premier passage écrit dans `donnees/` :

| Fichier | Contenu |
|---|---|
| `offres-AAAA-MM-JJ.md` | les nouveautés du jour, par famille d'employeur, avec leur score |
| `tableau.html` | la vue filtrable de toutes les offres gardées |
| `vus.json` | la mémoire de la veille (ce qui a déjà été vu, et jusqu'à quand c'était en ligne) |
| `passages.json` | l'historique des passages, avec les sources en erreur |

Options :

```bash
python veille.py --profil ailleurs/profil.toml   # un profil rangé ailleurs
python veille.py --tout                          # ressort tout, sans toucher à vus.json
python veille.py --sans-detail                   # ne lit pas le détail SmartRecruiters (plus rapide)
python tableau.py                                # refait seulement tableau.html
```

Tes fichiers (`profil.toml`, `employeurs.csv`, `donnees/`) sont ignorés par git : tu peux garder
le code à jour sans jamais publier ta recherche.

## Adapter à ta recherche

**→ [GUIDE.md](GUIDE.md)** explique tout pas à pas : brancher un employeur, choisir les lieux et
les postes, écrire tes arguments, régler le score. Tout se règle dans `profil.toml` et
`employeurs.csv` ; le code ne contient aucun critère.

| Section de `profil.toml` | Ce qu'elle décide |
|---|---|
| `[profil]` | ta devise, ta cible salariale, le seuil de salaire bas, tes années d'expérience |
| `[lieux]` | les villes acceptées, les lieux exacts, les zones de télétravail |
| `[themes]` | les mots du titre qui gardent ou écartent une offre, les postes d'ingénieur, le repli sur la description |
| `[[colle]]` / `[[coince]]` | tes arguments et tes écarts, cherchés dans chaque fiche, avec leur poids |
| `[score]` | la base, les poids par défaut et les seuils de rareté |
| `[alerte]` | la rareté à partir de laquelle une offre déclenche un e-mail |
| `[a_la_main]` | les recherches à faire toi-même sur les sites protégés (APEC) |
| `[fichiers]` | où sont ta liste d'employeurs et ton dossier de données |

`python essai.py` vérifie chaque réglage tout de suite, offre par offre :

```
Younited (lever, younited) : 7 offres, 2 gardée(s)
   ✓  Growth Marketing Manager (F/H)   67 rare   lieu « paris » ; titre « growth (marketing|marketer|manager) »
   ✓  Global Traffic Manager (F/H)     60 rare   lieu « paris » ; titre « traffic|trafic »
```

Le score d'adéquation part de 40 et ajoute ou retire des points selon ce qui colle ou coince, le
titre, le salaire, l'expérience demandée et le télétravail. Il donne la rareté : peu commune à
partir de 40, rare à 60, épique à 75, légendaire à 90, sans aucun quota. Le détail et la méthode
pour le calibrer sont dans le [guide](GUIDE.md#5-régler-le-score-et-la-rareté).

## Les boosters et l'album

Le but n'est pas de jouer : c'est de donner envie d'ouvrir les offres et de postuler.

- **Un booster** réunit 5 nouvelles offres. Tant qu'il y en a moins, elles attendent dans une
  pochette (« 3 / 5 cartes »). Sans quota de rareté : un booster sans carte rare est normal.
- **À l'ouverture**, les cartes se retournent une à une, la plus rare en dernier. Chaque carte
  montre ce qui colle, ce qui coince, le détail de son score et le lien vers l'offre.
- **L'album** ne reçoit une carte que si tu cliques sur « J'ai postulé » (avec la date et une note).
  Tu la fais ensuite avancer : relancé, entretien, offre reçue. Son aspect change à chaque étape,
  et elle est marquée « clôturée » quand l'offre disparaît du site.
- Une carte ouverte mais pas postulée reste dans la liste des offres, avec ses filtres.

Tout reste dans le navigateur (localStorage) : rien n'est envoyé, et sur la démo en ligne chaque
visiteur a sa propre collection.

## Recevoir une alerte par e-mail

`alerte.py` envoie les offres du dernier passage qui atteignent la rareté choisie dans le profil
(`[alerte] rarete_min`, « epique » par défaut). Sans offre à ce niveau, rien ne part.

```bash
python alerte.py                # affiche l'e-mail, n'envoie rien
python alerte.py --envoyer      # envoie par SMTP
```

Le serveur et le compte se lisent dans des variables d'environnement, jamais dans un fichier :
`SMTP_HOTE`, `SMTP_PORT` (587 par défaut, 465 pour SSL direct), `SMTP_UTILISATEUR`,
`SMTP_MOT_DE_PASSE`, `ALERTE_A` (destinataire) et, si besoin, `ALERTE_DE` (expéditeur).
N'importe quel service SMTP convient : un mot de passe d'application Gmail, ou un service
d'envoi avec une offre gratuite (Brevo, par exemple).

## Automatiser avec GitHub Actions

Le dépôt fournit deux workflows :

| Workflow | Ce qu'il fait |
|---|---|
| `tests.yml` | lance les tests à chaque envoi de code, en Python 3.11 et 3.13 |
| `demo.yml` | chaque matin, une veille avec le profil d'exemple, publiée sur GitHub Pages |

Pour ta propre veille, garde tes critères hors du dépôt public : crée un **dépôt privé** qui
contient seulement `profil.toml`, `employeurs.csv` et `donnees/`, avec ce workflow dans
`.github/workflows/veille.yml` :

```yaml
name: Veille
on:
  schedule:
    - cron: "30 5 * * *"     # chaque matin (heure UTC)
  workflow_dispatch:
permissions:
  contents: write
jobs:
  veille:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/checkout@v4
        with:
          repository: Oenece/radar-offres   # ou ta copie
          path: radar
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: python radar/veille.py --profil profil.toml
      - name: Commiter les données
        run: |
          git config user.name "radar-offres"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add donnees
          git diff --cached --quiet || (git commit -m "Veille du $(date +%F)" && git push)
      - run: python radar/alerte.py --profil profil.toml --envoyer
        env:
          SMTP_HOTE: ${{ secrets.SMTP_HOTE }}
          SMTP_PORT: ${{ secrets.SMTP_PORT }}
          SMTP_UTILISATEUR: ${{ secrets.SMTP_UTILISATEUR }}
          SMTP_MOT_DE_PASSE: ${{ secrets.SMTP_MOT_DE_PASSE }}
          ALERTE_A: ${{ secrets.ALERTE_A }}
          ALERTE_DE: ${{ secrets.ALERTE_DE }}   # l'expéditeur vérifié chez ton service d'envoi
```

Les secrets se créent dans *Settings > Secrets and variables > Actions* du dépôt privé.
Un passage dure une à deux minutes : l'offre gratuite d'Actions (2 000 minutes par mois pour
un dépôt privé) suffit largement.

Bon à savoir : GitHub met en pause les workflows planifiés d'un dépôt public sans activité depuis
60 jours, et prévient par e-mail ; un clic dans l'onglet Actions les relance.

## Ajouter un employeur

Donne l'adresse de sa page carrière à l'outil d'essai : il reconnaît l'outil de recrutement
(Ashby, Lever, Greenhouse, SmartRecruiters, Teamtailor), montre ce que ton profil garderait et te
donne la ligne à coller dans `employeurs.csv`.

```bash
python essai.py --url https://jobs.lever.co/acme
```

Les cas particuliers (adresse non reconnue, page maison, pas de flux) sont dans le
[guide](GUIDE.md#1-brancher-un-employeur). Une source en panne n'arrête pas le passage : elle est
notée dans `passages.json` et dans le compte rendu.

## Tests

```bash
python -m unittest discover tests     # le Python, sans réseau
node --test "tests/js/*.test.js"      # la logique des boosters et de l'album
```

Les tests tournent sans réseau : les lecteurs reçoivent de fausses réponses écrites sur le modèle
de chaque API, et un passage complet tourne dans un dossier temporaire avec un faux ATS. Ils
couvrent les filtres, la lecture des fiches, le score, l'outil d'essai, l'alerte, la lecture du
profil et ses erreurs. Ils utilisent un profil fixe (`tests/profil_test.toml`) : tu peux modifier
`profil.exemple.toml` sans les casser.

## Limites et bon usage

- **Seulement des requêtes GET** sur des API et des pages publiques, avec un `User-Agent` qui dit
  qui lit. Un passage par jour suffit largement ; inutile de lancer la veille en boucle.
- **Pas de LinkedIn, d'Indeed ni de Glassdoor**, dont les conditions d'utilisation interdisent la
  collecte automatique. L'APEC est protégée par un captcha : la veille rappelle les recherches à
  faire à la main au lieu de le contourner.
- **La lecture des fiches repose sur des motifs** : elle repère des mots, elle ne comprend pas
  l'offre. « Ce qui colle » et « ce qui coince » sont des pistes à relire sur l'offre.
- Les API des ATS peuvent changer ; un lecteur cassé se voit tout de suite dans les sources en erreur.

## Organisation du code

| Fichier | Rôle |
|---|---|
| `veille.py` | le passage : lecteurs ATS, filtres, lecture des fiches, mémoire, compte rendu |
| `profil.py` | lecture et vérification de `profil.toml` |
| `score.py` | le score d'adéquation et la rareté |
| `essai.py` | ce que le profil garde ou écarte, et pourquoi ; reconnaît l'ATS d'une adresse |
| `alerte.py` | l'e-mail des meilleures offres du dernier passage |
| `salaire.py` | la mise en forme des fourchettes de salaire (« 60 à 100 k€ ») |
| `tableau.py` | assemble `tableau.html` (modèle, styles, script et données en un seul fichier) |
| `modele/` | le squelette HTML, les styles et les scripts de la page |
| `modele/collection.js` | la logique des cartes : boosters, pochette, album, étapes de candidature |
| `modele/cartes.js` | l'affichage des cartes : étagère, ouverture d'un booster, album |
| `tests/` | les tests, sans réseau (Python, et JavaScript dans `tests/js`) |

## Licence

MIT : voir [LICENSE](LICENSE).
