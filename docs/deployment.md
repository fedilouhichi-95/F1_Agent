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
transaction et affiche un message de succès ou une erreur sans secret. Avant la
première application, vérifier que le projet Supabase ne contient pas déjà des
données qui nécessitent une migration de réparation.

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