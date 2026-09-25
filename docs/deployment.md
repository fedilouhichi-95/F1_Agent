# Déploiement — flux Colab → GitHub → Streamlit Community Cloud

## Prérequis (une seule fois, hors décompte des 16 semaines)

| Service | Compte | Clés nécessaires |
|---|---|---|
| Groq | console.groq.com | `GROQ_API_KEY` |
| Qdrant Cloud | cloud.qdrant.io | `QDRANT_URL`, `QDRANT_API_KEY` |
| Supabase | supabase.com | `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_DB_URL`, `SUPABASE_DB_PASSWORD` |
| DagsHub | dagshub.com | `MLFLOW_TRACKING_*` (credentials MLflow) |
| GitHub | existing | dépôt public `F1_Agent` |
| Streamlit Cloud | share.streamlit.io | lié au repo GitHub |

En dev : toutes les clés dans les Secrets Colab ; en prod : secrets de l'app
Streamlit Cloud (mêmes noms que `.env.example`).

## Secrets Streamlit

En local, `AppConfig` lit le `.env` ou `.streamlit/secrets.toml`. Sur Streamlit
Community Cloud, saisir les mêmes noms de variables dans **Settings → Secrets**.
Les secrets sont transmis à la configuration sans être importés par
`app/config.py` et ne sont jamais affichés dans l'interface.

Ne jamais coller une valeur réelle dans `.streamlit/secrets.toml.example`,
`.env.example` ou un notebook.

## Migration Supabase

La migration doit être exécutée par le code du projet, jamais en collant le DDL
dans l'éditeur SQL. Après avoir configuré `SUPABASE_DB_URL` et
`SUPABASE_DB_PASSWORD` dans Colab ou les secrets GitHub :

```bash
python -m app.data_pipeline.migrate
```

Le runner lit `app/data_pipeline/schema.sql`, applique le DDL dans une
transaction et affiche un message de succès ou l'erreur PostgreSQL réelle, sans
jamais exposer le mot de passe. Le schéma est idempotent : le relancer ne duplique
rien. Avant la première application, vérifier que le projet Supabase ne contient
pas déjà des données qui nécessitent une migration de réparation.

## Choisir la bonne chaîne de connexion

Depuis Colab, seule la chaîne du **Session pooler** fonctionne.

| Méthode | Hôte | IP | Verdict |
|---|---|---|---|
| Session pooler | `aws-N-REGION.pooler.supabase.com:5432` | IPv4 | ✅ à utiliser |
| Transaction pooler | `aws-N-REGION.pooler.supabase.com:6543` | IPv4 | ❌ ne supporte ni les transactions multi-instructions, ni le DDL |
| Connexion directe | `db.REF.supabase.co:5432` | IPv6 | ❌ les VM Colab n'ont pas d'IPv6 |

**L'hôte doit être copié, jamais composé.** Le `N` de `aws-N-REGION` est un index
de cluster propre à la région : il ne se déduit pas du nom de la région. Un hôte
composé à la main est résolu par le DNS mais pointe vers un cluster qui ne connaît
pas le projet.

Source : Project Settings → Database → **Connect** (bouton en haut de la page) →
onglet Session pooler.

L'identifiant est `postgres.REF` pour le pooler, mais seulement `postgres` pour la
connexion directe. Le mot de passe se transmet séparément via `SUPABASE_DB_PASSWORD`
et n'a pas besoin d'être encodé dans l'URL.

## Diagnostic de connexion

Si la migration échoue, le message contient la cause PostgreSQL. Correspondance :

| Message | Cause | Correction |
|---|---|---|
| `tenant/user postgres.REF not found` | Hôte composé à la main, ou mauvaise région | Copier l'hôte depuis le panneau Connect |
| `password authentication failed` | Mot de passe obsolète | Project Settings → Database → Reset password, puis mettre à jour `.env` |
| `could not translate host name` | Hôte mal saisi | Recontrôler la chaîne |
| `timeout expired` | Connexion directe en IPv6 | Basculer sur le Session pooler |
| `no pg_hba.conf entry` | Adresse IP non autorisée | Vérifier les règles réseau du projet |

En Colab, une variable déjà lue dans la session n'est pas écrasée par un
`load_dotenv()` ultérieur : un diagnostic de connexion doit utiliser
`load_dotenv(override=True)`. Le runner, lui, démarre un processus neuf et relit
`.env` proprement.

## Workflow quotidien

1. Ouvrir une session Colab, monter Drive, cloner le repo.
2. Travailler dans les notebooks d'expérimentation ou importer `app/`.
3. Lancer les vérifications : `ruff check .`, `ruff format --check .` puis `python -m pytest -m "not eval"`.
4. **Committer AVANT de fermer la session** (Colab n'est pas fiable).
5. Pousser sur GitHub : la CI (`ci.yml`) vérifie lint, format et tests à chaque push.

## CD automatique

- Le push sur `main` peut déclencher le redéploiement Streamlit Cloud lorsque
  l’application est connectée au dépôt.
- Les PR vers `main` déclenchent `eval.yml`. Pour le moment, ce workflow
  vérifie seulement la structure du corpus ; les métriques RAGAS, l’exactitude
  et les seuils restent à implémenter dans l’issue #14.

## Rajout ultérieur (bonus CV, sans impact déploiement)

Dockerfiles par composant, documentés mais non utilisés : l'app reste
hébergée par Streamlit Cloud.