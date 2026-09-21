# Déploiement — flux Colab → GitHub → Streamlit Community Cloud

## Prérequis (une seule fois, hors décompte des 16 semaines)

| Service | Compte | Clés nécessaires |
|---|---|---|
| Groq | console.groq.com | `GROQ_API_KEY` |
| Qdrant Cloud | cloud.qdrant.io | `QDRANT_URL`, `QDRANT_API_KEY` |
| Supabase | supabase.com | `SUPABASE_URL`, `SUPABASE_ANON_KEY` |
| DagsHub | dagshub.com | `MLFLOW_TRACKING_*` (credentials MLflow) |
| GitHub | existing | dépôt privé `F1_Agent` |
| Streamlit Cloud | share.streamlit.io | lié au repo GitHub |

En dev : toutes les clés dans les Secrets Colab ; en prod : secrets de l'app
Streamlit Cloud (même noms que `.env.example`).

## Workflow quotidien

1. Ouvrir une session Colab, monter Drive, cloner le repo.
2. Travailler dans les notebooks d'expérimentation ou importer `app/`.
3. Lancer lint + tests : `ruff check .` puis `python -m pytest`.
4. **Committer AVANT de fermer la session** (Colab n'est pas fiable).
5. Pousser sur GitHub : la CI (`ci.yml`) vérifie lint + tests à chaque push.

## CD automatique

- Le push sur `main` déclenche le redéploiement Streamlit Cloud (app
  connectée au repo, zéro étape manuelle).
- Les PR vers `main` passent le portail de qualité (`eval.yml`) : évaluation
  RAGAS + exactitude chiffrée. Fusion bloquée si les seuils régressent.

## Rajout ultérieur (bonus CV, sans impact déploiement)

Dockerfiles par composant, documentés mais non utilisés : l'app reste
hébergée par Streamlit Cloud.