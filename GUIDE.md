# Guide : adapter radar-offres à ta recherche

Tout se règle dans deux fichiers, sans toucher au code :

- **`employeurs.csv`** : chez qui chercher ;
- **`profil.toml`** : quoi garder, et comment noter.

Et une commande pour vérifier chaque réglage tout de suite : **`python essai.py`**.
Elle lit les flux, applique ton profil et te dit, offre par offre, *pourquoi* elle est gardée ou
écartée. Elle ne modifie aucun fichier : lance-la autant que tu veux.

---

## 0. Démarrer en 5 minutes

```bash
cp profil.exemple.toml profil.toml          # le profil d'exemple : marketing d'acquisition à Paris
cp employeurs.exemple.csv employeurs.csv    # 13 employeurs d'exemple
python essai.py                             # ce que l'exemple garde, et pourquoi
```

Ensuite, refais les sections 1 à 4 avec tes propres choix, en relançant `python essai.py` après
chaque changement. Quand le résultat te plaît : `python veille.py`.

---

## 1. Brancher un employeur

**Étape 1.** Ouvre la page « carrières » ou « jobs » de l'entreprise, puis clique sur une offre.
Regarde l'adresse dans la barre du navigateur.

**Étape 2.** Donne cette adresse à l'outil d'essai :

```bash
python essai.py --url https://jobs.lever.co/acme
```

Il reconnaît l'outil de recrutement, lit le flux, montre ce que ton profil garderait, et te donne
la ligne à coller :

```
Ligne à coller dans employeurs.csv (nom et famille à ton choix) :
  Nom,famille,lever,acme,
```

**Étape 3.** Colle la ligne dans `employeurs.csv` en remplaçant `Nom` et `famille`
(la famille sert à regrouper les employeurs dans le tableau : « agence », « SaaS »…) :

```csv
Acme,SaaS,lever,acme,
```

### Les adresses reconnues

| Si l'adresse ressemble à… | ATS | Identifiant |
|---|---|---|
| `jobs.ashbyhq.com/acme` | `ashby` | `acme` |
| `jobs.lever.co/acme` | `lever` | `acme` |
| `boards.greenhouse.io/acme` ou `job-boards.greenhouse.io/acme` | `greenhouse` | `acme` |
| `jobs.smartrecruiters.com/Acme1` | `smartrecruiters` | `Acme1` (majuscules comprises) |
| `acme.teamtailor.com` | `teamtailor` | `acme` |

### L'adresse n'est pas reconnue ?

Beaucoup d'entreprises affichent leurs offres sur leur propre site, mais les font tourner sur un
de ces outils. Pour le savoir :

- clique sur **« Postuler »** : l'adresse du formulaire révèle souvent l'outil ;
- ou fais un clic droit > **« Afficher le code source »**, puis cherche (Ctrl+F) `ashby`, `lever`,
  `greenhouse`, `smartrecruiters` ou `teamtailor`. L'identifiant suit le nom de l'outil dans
  l'adresse trouvée.

Sinon, deux solutions de repli :

| Cas | Ligne à écrire | Ce que fait la veille |
|---|---|---|
| La page liste des liens vers chaque offre (`/carrieres/chef-de-projet`…) | `Acme,agence,page,https://acme.fr/carrieres,` | signale chaque nouveau lien, à lire à la main |
| Rien de lisible | `Acme,agence,manuel,https://acme.fr/carrieres,à regarder le lundi` | rappelle l'adresse dans « À regarder à la main » |

---

## 2. Choisir les lieux

Section `[lieux]` de `profil.toml`. Une offre est gardée si **un seul** de ses lieux passe.

```toml
[lieux]
acceptes = ['paris', 'île-de-france', 'lyon']        # un de ces mots dans le lieu suffit
exacts = ['remote france', 'france (remote)']        # lieux acceptés seulement écrits tels quels
remote_zones = ['france', 'europe', 'emea']           # télétravail accepté vers ces zones
```

| Tu veux… | Écris |
|---|---|
| ajouter une ville | ajoute-la dans `acceptes` : `'bordeaux'` |
| le télétravail depuis la France seulement | `remote_zones = ['france']` |
| aucun télétravail | `remote_zones = []` et retire les lignes « remote » de `exacts` |

⚠️ **Piège** : ne mets pas `'france'` dans `exacts`. Beaucoup d'offres listent leurs villes puis
« France » (« Madrid / France ») : ce « France » final ferait passer des postes à l'étranger.

---

## 3. Choisir les postes

Section `[themes]`. Une offre passe ces filtres dans cet ordre :

```
titre exclu ?  ──oui──►  écartée
     │ non
poste d'ingénieur sans mot de ingenieur_ok ?  ──oui──►  écartée
     │ non
un thème dans le titre ?  ──oui──►  gardée
     │ non
la description contient un mot « ia » ET assez de mots « metier » ?  ──oui──►  gardée
     │ non
écartée
```

| Clé | Rôle | Exemple |
|---|---|---|
| `titre` | les mots du titre qui gardent l'offre | `'\bseo\b'`, `'growth (marketing\|manager)'` |
| `exclus_titre` | les mots du titre qui l'écartent, quoi qu'il arrive | `'\bsales\b'`, `'internship'` |
| `ingenieur` / `ingenieur_ok` | un poste d'ingénieur ne passe que si son titre contient aussi un mot de `ingenieur_ok` | `ingenieur_ok = ['seo', 'marketing']` garde « SEO Engineer », écarte « Data Engineer » |
| `ia`, `metier`, `metier_minimum` | le repli quand le titre ne dit rien : la description doit parler d'IA et du métier | `metier_minimum = 2` |

### Trop d'offres, ou pas assez ?

Lance `python essai.py --ecartees`. Chaque offre affiche sa raison :

```
   ✓  Senior Product Manager - Growth     lieu « paris » ; titre « growth »        ← un mot trop large
   ✗  Paid Media Manager                  aucun thème dans le titre, …             ← un mot qui manque
```

| Symptôme | Remède |
|---|---|
| un mot attrape des postes hors sujet (« growth » attrape « Product Manager Growth ») | précise-le : `'growth (marketing\|marketer\|manager)'`, ou exclus l'autre métier : `'product manager'` dans `exclus_titre` |
| un poste pertinent est écarté | ajoute un mot de son titre dans `titre` |
| des postes d'ingénieur passent | retire le mot trop général de `ingenieur_ok` |
| le repli par la description ramène n'importe quoi | retire de `metier` les mots trop courants, ou monte `metier_minimum` |

Pour essayer un titre sans attendre une vraie offre :

```bash
python essai.py --titre "Consultant SEA Senior" --lieu Paris --description "Google Ads, GA4"
```

### Les motifs en 6 règles

Les mots de `profil.toml` sont des expressions régulières, cherchées en minuscules. Six règles
suffisent :

| Écriture | Sens | Trouve |
|---|---|---|
| `seo` | le texte, n'importe où | « SEO », « seoul » ⚠️ |
| `\bseo\b` | le mot entier | « SEO », pas « seoul » |
| `sea\|sem` | l'un ou l'autre | « SEA », « SEM » |
| `growth (manager\|marketer)` | un groupe d'alternatives | « growth manager », « growth marketer » |
| `analyste?` | la lettre d'avant est facultative | « analyst », « analyste » |
| `r[ée]f[ée]rencement` | une lettre parmi plusieurs | avec ou sans accents |

Écris les motifs entre apostrophes simples : `'\bseo\b'`. Un motif mal écrit est signalé au
lancement, avec son nom.

---

## 4. Écrire tes arguments

Les blocs `[[colle]]` et `[[coince]]` lisent chaque fiche : quand le motif apparaît, la phrase
s'affiche dans le tableau et le poids s'ajoute au score.

```toml
[[colle]]
motif = 'google ads|\bsea\b|paid search'
tag = 'SEA'                                          # l'étiquette courte du tableau
texte = 'campagnes Google Ads pilotées de bout en bout'  # ton argument, en une phrase
poids = 15                                           # facultatif : +10 par défaut

[[coince]]
motif = 'salesforce|hubspot'
tag = 'CRM'
texte = 'outil CRM pas encore pratiqué'
poids = -5                                           # facultatif : -8 par défaut
```

Écris un `[[colle]]` par compétence que tu veux mettre en avant, et un `[[coince]]` par écart
que tu devras préparer avant de postuler. Ajoute autant de blocs que tu veux.

---

## 5. Régler le score et la rareté

Chaque offre gardée reçoit un score de 0 à 100. Ce score donne sa rareté, de « commune » à
« légendaire » : il mesure à quel point l'offre **te correspond**, pas sa rareté sur le marché.

```
base (40)
 + 10   le titre touche un de tes thèmes
 + poids de chaque « colle » trouvé
 + poids de chaque « coince » trouvé (négatif)
 + 10   la fourchette affichée atteint ta cible     − 15  elle est sous salaire_bas
 −  3   par année demandée au-delà de ton expérience
 +  5   remote ou hybride
```

| Score | Rareté |
|---|---|
| 90 et plus | légendaire |
| 75 à 89 | épique |
| 60 à 74 | rare |
| 40 à 59 | peu commune |
| moins de 40 | commune |

**Pour calibrer** : lance `python essai.py` et regarde les scores des offres que tu connais.

- Une offre excellente n'est que « rare » ? Monte le `poids` de ce qui la fait coller.
- Une offre médiocre est « épique » ? Cherche le `colle` trop fréquent et baisse son poids.
- Tout est trop haut ou trop bas ? Change `base` dans `[score]`.

Il n'y a aucun quota : une semaine sans légendaire est une semaine normale.

---

### Les boosters

La rareté du score décide de l'aspect des cartes dans les boosters : une carte légendaire est
une offre qui te correspond presque parfaitement. Pour changer la taille d'un booster (5 cartes
par défaut), modifie `TAILLE_BOOSTER` au début de `modele/collection.js`, puis relance
`python tableau.py`.

## 6. Recevoir les meilleures offres par e-mail

```toml
[alerte]
rarete_min = 'epique'    # commune, peu_commune, rare, epique ou legendaire
```

`python alerte.py` affiche l'e-mail qui partirait, sans l'envoyer. L'envoi automatique chaque
matin est expliqué dans le [README](README.md#automatiser-avec-github-actions).

---

## 7. Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| `flux illisible : HTTP Error 404` | mauvais identifiant, ou l'entreprise a changé d'outil | refais l'étape 1 de la section 1 |
| un employeur rend « 0 offres » | le board existe mais il est vide, ou c'est le mauvais | vérifie la page carrière dans le navigateur |
| `Profil : … il manque …` | une clé obligatoire a été effacée | reprends-la dans `profil.exemple.toml` |
| `Profil : motif « … » invalide` | une parenthèse ou un crochet non fermé | corrige le motif cité |
| « Rien de nouveau. » | tout a déjà été vu | normal ; `python veille.py --tout` ressort tout sans rien modifier |
| un salaire n'est pas comparé à ta cible | il est dans une autre devise que celle du profil | normal : la veille ne convertit pas les devises |
