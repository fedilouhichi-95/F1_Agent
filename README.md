# PitStop Assistant

Assistant IA multi-agents pour la Formule 1 — combine RAG et 6 agents
spécialisés (LangGraph) pour répondre à des questions statistiques,
stratégiques et réglementaires sur la saison 2023. 100 % cloud gratuit :
Groq (LLM), Qdrant Cloud (RAG), Supabase (données), Streamlit Community
Cloud (déploiement), Google Colab (développement).

> Projet de fin d'études — Ingénierie Informatique.

## Installation

```bash
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env        # puis remplir avec tes clés (Groq, Qdrant, Supabase)
```

## Utilisation

```bash
python -m app               # diagnostic de configuration (smoke test)
python -m pytest            # tests unitaires (mocks, hors réseau)
python -m pytest -m eval    # quality gate (RAGAS + exactitude chiffrée)
ruff check .                # lint
streamlit run app/streamlit_app.py   # app en local / Colab
```

## Structure

```
app/               code de production (agents, MCP, pipeline, RAG, monitoring)
notebooks/         expérimentations Colab (numérotées, rien de critique ici)
tests/             tests unitaires + evaluation/quality gate
docs/              documentation (architecture, MCP, déploiement)
.github/workflows/ CI (lint+tests) et Eval (quality gate RAGAS)
SPEC.md            objectif, stack, features, hors-périmètre
```

## Architecture et flux

```
Question → Streamlit → Orchestrateur (LangGraph)
  → Stats (Supabase) | Stratégie (données FastF1) | Contexte (Qdrant)
  → Synthèse (Groq) → Vérificateur → réponse + sources + traces + log
```

Voir `SPEC.md` pour le périmètre complet et `docs/` pour l'architecture.

## Roadmap

Voir `SPEC.md` (features numérotées) et `PROGRESS.md` (suivi d'avancement).
Plan détaillé sur 16 semaines dans `docs/plan_pfe.md`.