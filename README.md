# PitStop Assistant

Assistant IA multi-agents pour la Formule 1, prévu pour répondre à des questions statistiques, stratégiques et réglementaires sur la saison 2023.

> Projet de fin d'études — Ingénierie Informatique.

## État actuel

La version `0.1.0` est un **scaffold technique** : elle contient la configuration, un smoke test, une interface Streamlit d'état, un contrat d'agent et un schéma Supabase partiel. Le flux RAG, les six agents, l'ingestion, les serveurs MCP et le monitoring décrits dans `SPEC.md` restent des étapes de roadmap.

| Élément | État |
|---|---|
| Configuration et smoke test | Disponible |
| Interface Streamlit | Disponible, état des connexions uniquement |
| Tests unitaires | Disponible |
| RAG, ingestion et agents | À implémenter |
| Serveurs MCP et monitoring | À implémenter |
| Quality gate RAGAS | Squelette de validation structurelle |

La cartographie complète et les écarts documentaires sont disponibles dans [`PROJECT_MAP.md`](PROJECT_MAP.md) et [`DOC_DRIFT.md`](DOC_DRIFT.md).

## Installation

Prérequis : Python 3.12.

```bash
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
```

Renseigner les secrets dans `.env`, les Secrets Colab ou les secrets Streamlit Cloud. Ne jamais versionner un fichier `.env` rempli.

## Utilisation

```bash
python -m app                              # diagnostic de configuration
python -m pytest                           # tests unitaires hors réseau
python -m pytest -m eval                   # vérification structurelle du scaffold eval
ruff check .                               # lint
ruff format --check .                      # vérification du formatage
streamlit run app/streamlit_app.py         # interface Streamlit
```

Le marqueur `eval` ne lance pas encore RAGAS ni une évaluation d'exactitude : le corpus de référence et les métriques sont à compléter.

## Structure

```text
app/               configuration, point d'entrée et contrats
notebooks/         expérimentations Colab prévues par la roadmap
tests/             tests unitaires et squelette d'évaluation
docs/              architecture, déploiement, MCP et roadmap
.github/workflows/ CI lint/tests et workflow d'évaluation
SPEC.md            périmètre cible et critères d'acceptation
PROGRESS.md        suivi réel d'avancement
```

## Architecture cible

```text
Question → Streamlit → Orchestrateur (LangGraph)
  → Stats (Supabase) | Stratégie (FastF1) | Contexte (Qdrant)
  → Synthèse (Groq) → Vérificateur → réponse + sources + traces + log
```

Ce schéma décrit la cible de `SPEC.md` et `docs/architecture.md`, pas un flux déjà exécutable.

## Documentation

- [`SPEC.md`](SPEC.md) — périmètre et stack cibles.
- [`PROGRESS.md`](PROGRESS.md) — état réel et prochaines étapes.
- [`docs/architecture.md`](docs/architecture.md) — architecture cible.
- [`docs/deployment.md`](docs/deployment.md) — procédure de déploiement prévue.
- [`docs/mcp_servers.md`](docs/mcp_servers.md) — contrats MCP prévus.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — workflow de contribution.
- [`SECURITY.md`](SECURITY.md) — signalement de problèmes de sécurité.
- [`CHANGELOG.md`](CHANGELOG.md) — historique des versions.

## Roadmap

Le plan détaillé est maintenu dans [`docs/plan_pfe.md`](docs/plan_pfe.md). Les fonctionnalités non livrées sont identifiées dans [`PROGRESS.md`](PROGRESS.md) afin de distinguer la cible de l'état actuel.

## Licence

Ce projet est distribué sous la licence MIT. Voir [`LICENSE`](LICENSE).
