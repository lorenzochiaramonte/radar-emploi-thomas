# Radar emploi — Thomas Chiaramonte 🚛

Agent automatique qui scanne les offres d'emploi tous les matins à 7h sur le bassin de Lorette (42420), filtre selon le profil, dédoublonne, génère un texte de candidature personnalisé pour les meilleures offres, et pousse le tout sur Telegram + Email + une page web persistante.

**Stack** : Python + GitHub Actions (gratuit, zéro serveur à gérer).
**Sources** : API France Travail (officielle, gratuite) + Indeed (RSS).
**IA** : API Claude Haiku (~0,15€/mois pour la génération des candidatures).
**Cible** : cariste CACES 3, préparateur de commandes, magasinier, manutentionnaire, opérateur de production agroalimentaire.
**Rayon** : 25 km autour de Lorette.

---

## 🎯 Ce que tu vas obtenir chaque matin à 7h

**Sur Telegram** (pour Thomas) — 1 message d'intro + 1 message par offre, avec :
- Le titre, l'entreprise, la ville, la distance, le score
- Le lien direct vers la plateforme pour postuler
- **Le texte de candidature pré-écrit, prêt à copier-coller**

**Par email** (pour toi) — digest détaillé pour pouvoir trier qualité avant que Thomas le voie.

**Sur une page web** (`https://<ton-user>.github.io/radar-emploi-thomas/`) — vue persistante 24/7 avec filtres, statut "Intéressé / Postulé", bouton copier-coller pour la candidature.

---

## 🚀 Setup en 30 minutes (pas-à-pas)

### Étape 1 — Créer le dépôt GitHub

1. Compte sur https://github.com/signup (si tu n'en as pas, gratuit)
2. `+` → `New repository`
3. Nom : `radar-emploi-thomas`
4. **Coche "Public"** (obligatoire si tu veux GitHub Pages gratuit) ou Private (mais alors GitHub Pages payant)
5. `Create repository`

### Étape 2 — Uploader les fichiers

Sur la page de ton dépôt :
1. Clique `uploading an existing file`
2. Glisse-dépose : `radar.py`, `candidature_generator.py`, `telegram_client.py`, `web_dashboard.py`, `requirements.txt`, `.gitignore`, `README.md`
3. Pour le workflow : `Add file` → `Create new file` → tape `.github/workflows/radar.yml` → colle le contenu
4. `Commit changes`

### Étape 3 — Identifiants France Travail (10 min)

1. Va sur https://francetravail.io/data/api
2. Inscription, puis "Mes applications" → "Créer une application"
3. Choisis l'API **"Offres d'emploi v2"**
4. Note le **client_id** et le **client_secret**

### Étape 4 — Mot de passe d'application Gmail (5 min)

1. https://myaccount.google.com/security
2. Active la validation en deux étapes si pas déjà fait
3. https://myaccount.google.com/apppasswords
4. Crée un mot de passe nommé "Radar emploi"
5. Note le code de 16 caractères

### Étape 5 — Clé API Anthropic pour les candidatures (5 min)

1. https://console.anthropic.com/
2. Crée un compte (gratuit, ~5$ de crédit offert)
3. `Settings` → `API Keys` → `Create Key`
4. Note la clé (commence par `sk-ant-`)

> Coût réel attendu : **~0,15€/mois** pour 5 candidatures générées par jour.
> Tu peux mettre une limite mensuelle dans la console (ex : 2$/mois) pour la sécurité.

### Étape 6 — Bot Telegram (10 min)

1. Sur Telegram, cherche **@BotFather** et envoie `/newbot`
2. Donne un nom (ex : `RadarEmploiThomas`) et un username (ex : `radar_thomas_bot`)
3. BotFather te donne un **token** (forme : `123456:ABC-DEF...`) — note-le
4. Demande à Thomas d'ouvrir le bot et de taper `/start` (ou n'importe quel message)
5. **Récupérer le chat_id de Thomas** : ouvre le terminal et lance :
   ```
   curl "https://api.telegram.org/bot<TON_TOKEN>/getUpdates"
   ```
   Cherche `"chat":{"id":123456789` — c'est le chat_id (un nombre).
   Alternative : utilise `python telegram_client.py <TON_TOKEN>` qui le fait pour toi.

### Étape 7 — Configurer les secrets GitHub

Sur ton dépôt GitHub : `Settings` → `Secrets and variables` → `Actions` → `New repository secret`. Crée :

| Nom | Valeur |
|---|---|
| `FT_CLIENT_ID` | client_id France Travail |
| `FT_CLIENT_SECRET` | client_secret France Travail |
| `SMTP_USER` | ton adresse Gmail |
| `SMTP_PASSWORD` | mot de passe d'application Gmail (16 caractères) |
| `EMAIL_DESTINATAIRE` | ton adresse mail (où tu reçois le digest) |
| `ANTHROPIC_API_KEY` | ta clé API Claude (`sk-ant-...`) |
| `TELEGRAM_BOT_TOKEN` | token du bot Telegram |
| `TELEGRAM_CHAT_ID` | chat_id de Thomas |

### Étape 8 — Activer GitHub Pages

1. `Settings` → `Pages`
2. Source : `GitHub Actions` (PAS "Deploy from a branch")
3. Sauve

Ensuite ajoute une **variable** (pas un secret) avec l'URL Pages :
1. `Settings` → `Secrets and variables` → `Actions` → onglet **Variables** → `New repository variable`
2. Nom : `PAGES_URL`
3. Valeur : `https://<ton-username>.github.io/radar-emploi-thomas/`

### Étape 9 — Lancer le premier run

1. Onglet `Actions`
2. Workflow `radar-emploi-quotidien` à gauche
3. `Run workflow` → `Run workflow`
4. Attends 2-3 minutes
5. Si tout est vert : Thomas reçoit ses messages sur Telegram, toi un email, et la page web devient accessible 🎉

À partir de demain matin, ça tourne tout seul à 7h.

---

## ⚙️ Personnalisation rapide

Toutes les options sont en haut de `radar.py` :

```python
LORETTE_LAT = 45.5236
LORETTE_LON = 4.6736
RAYON_KM = 25                # Rayon de recherche

CODES_ROME = ["N1103", ...]  # Métiers ciblés (référentiel France Travail)

MOTS_CLES_POSITIFS = {       # Bonus de score
    "caces 3": 3, ...
}

MOTS_CLES_NEGATIFS = {       # Malus de score (à éviter)
    "caces 5 obligatoire": -3, ...
}

SCORE_MIN = 2                # Seuil pour apparaître dans le digest
```

Pour le ton ou le format des candidatures, c'est dans `candidature_generator.py` → `PROMPT_SYSTEME`.

---

## 🐛 Diagnostiquer un problème

| Symptôme | Cause probable | Solution |
|---|---|---|
| Pas d'email reçu | Mot de passe d'application Gmail invalide | Recrée-en un, vérifie `SMTP_PASSWORD` |
| Telegram silencieux | Token ou chat_id invalide | Re-vérifier `TELEGRAM_BOT_TOKEN` et `TELEGRAM_CHAT_ID` |
| `France Travail HTTP 401` | Identifiants invalides ou expirés | Vérifier `FT_CLIENT_ID/SECRET` |
| `Anthropic 401` | Clé API invalide | Régénérer une clé sur console.anthropic.com |
| Toujours les mêmes offres | Historique foireux | Supprimer `data/historique.json` du dépôt |
| Trop d'offres / pas assez | Score mal calibré | Ajuster `SCORE_MIN` ou les listes de mots-clés |
| GitHub Pages 404 | Source mal configurée | Settings → Pages → source = "GitHub Actions" |

Pour les logs détaillés : `Actions` → run en cours → étape `Exécuter le radar`.

---

## 💰 Coûts mensuels estimés

| Poste | Coût |
|---|---|
| GitHub Actions (tier gratuit) | 0 € |
| GitHub Pages | 0 € |
| API France Travail | 0 € |
| API Indeed (RSS) | 0 € |
| API Anthropic Claude (5 candidatures × 30 jours) | ~0,15 € |
| Bot Telegram | 0 € |
| SMTP Gmail | 0 € |
| **Total** | **~0,15 €/mois** |

---

## 🛣️ Évolutions possibles

- Scraping direct des sites d'agences locales (Adecco, Manpower, Proman...)
- Bot Telegram interactif avec callbacks (nécessite un serveur 24/7)
- Suivi automatique des candidatures envoyées (statut, relances J+7)
- Intégration LinkedIn / Welcome to the Jungle / HelloWork
- Dashboard avec stats temporelles (volume marché, métiers porteurs)

---

## 🔒 Sécurité

- Tous les identifiants sont dans GitHub Secrets, jamais en clair dans le code
- Le CV de Thomas n'est pas stocké en clair, juste résumé dans `candidature_generator.py`
- Aucune donnée perso d'autres candidats n'est collectée
- Le dashboard web n'expose que des offres publiques

---

## 📞 Support

Si quelque chose coince, garde l'erreur exacte (capture des logs GitHub Actions) sous le coude pour qu'on debug.
