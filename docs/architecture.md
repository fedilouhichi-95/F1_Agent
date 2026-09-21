# Architecture — PitStop Assistant

## Vue d'ensemble

App IA full-stack 100 % cloud gratuit. Le développement et l'expérimentation
ont lieu dans Google Colab ; le code de production vit sur GitHub et est
déployé en continu sur Streamlit Community Cloud.

```
        DÉVELOPPEMENT (Google Colab)          PRODUCTION (Streamlit Cloud)
   ┌───────────────────────┐            ┌──────────────────────────────┐
   │ Notebooks ingestion,   │  git push  │  App Streamlit (chat)        │
   │ tests agents, éval     │───────────▶│  LangGraph (6 agents)        │
   │ RAGAS                  │ GitHub     │  Serveurs MCP (stdio)        │
   └──────────┬────────────┘     ▲      └──────┬────────┬──────────┬───┘
              │ DVC (remote Drive)│ CI/CD      │        │          │
              ▼                ┌───┴──┐        ▼        ▼          ▼
   DagsHub (MLflow tracking)   │ GitHub│   Groq     Qdrant     Supabase
   Google Drive (gros fichiers)│Actions│   (LLM)    (RAG)      (données+logs)
                               └───────┘
```

## Composants

| Composant | Rôle | Où il tourne |
|---|---|---|
| `app/agents/` | 6 agents + graphe LangGraph | Colab (dev) / Streamlit Cloud (prod) |
| `app/mcp_servers/` | 3 serveurs MCP stdio | sous-processus lancés par l'app |
| `app/data_pipeline/` | ingestion Jolpica-F1 + FastF1 → Supabase | Colab |
| `app/rag/` | chunking, embeddings, recherche Qdrant | Colab (indexation) + prod (query) |
| `app/monitoring/` | logs de requêtes → Supabase | Streamlit Cloud |
| `app/config.py` | lecture centralisée de l'environnement | partout |

## Modèle de données

- **Supabase** : `drivers`, `constructors`, `races`, `results`, `standings`,
  `laps`, `pit_stops`, `tire_stints`, `logs`. Toutes les tables factuelles
  portent une colonne `season` (multi-saison). DDL dans
  `app/data_pipeline/schema.sql`.
- **Qdrant Cloud** : collection `pitstop_docs` — chunks textuels (Wikipedia +
  PDF FIA) vectorisés en BGE-small, avec métadonnées (source, sujet, chunk).

## Flux de données

```
Question utilisateur
  → Orchestrateur (LangGraph, classification Groq)
  → Stats (SQL Supabase) | Stratégie (données FastF1) | Contexte (Qdrant)
  → Synthèse (Groq) → Vérificateur (recoupe les chiffres vs Supabase)
  → réponse + sources + traces d'agents + ligne dans la table logs
```

## Décisions structurantes

- Aucun secret dans le code : `.env` (local), Secrets Colab (dev), secrets
  Streamlit Cloud (prod) — mêmes noms de variables.
- Les serveurs MCP n'importent jamais `streamlit` (indépendants du runtime UI).
- Les notebooks sont des outils ; le code déployé vit toujours dans `app/`.