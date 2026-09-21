# PROGRESS — PitStop Assistant

Mémoire de session. Toute nouvelle session relit `AGENTS.md`, `SPEC.md` puis
ce fichier pour retrouver le contexte instantanément.

## ✅ Fait

- [x] Brief validé (Phase 1-2) : app IA full-stack, stack Python 3.12, Supabase
      + Qdrant Cloud, aucun login, tests strict CI-gated, docs en français,
      nom produit « PitStop Assistant ».
- [x] Architecture validée (Phase 4) : arborescence `app/`, `tests/`,
      `notebooks/`, `docs/`, workflows GitHub Actions.
- [x] Scaffold fonctionnel (Phase 5) :
  - `SPEC.md`, `AGENTS.md`, `.env.example`, `.gitignore`
  - `requirements.txt` (runtime) + `requirements-dev.txt` (dev/CI), versions
    épinglées au 21/09/2026
  - `app/config.py` (config centralisée), `app/agents/base.py` (contrat agent),
    `app/streamlit_app.py` (app minimale), `python -m app` (smoke test)
  - Schéma Supabase amorcé : `app/data_pipeline/schema.sql`
  - Tests : `pytest` 6 verts, marker `-m eval` vert, `ruff check` 0 violation
  - Workflows : `ci.yml` (lint + tests), `eval.yml` (quality gate RAGAS)
  - Docs : architecture, déploiement, MCP (à compléter), plan PFE 16 semaines
- [x] Push initial sur GitHub privé (`chore: initial project scaffold`).

## 🔜 Reste à faire (features SPEC, par priorité)

1. **F1 (P1)** Ingestion données structurées 2023 : Jolpica-F1 → Supabase
   (`races`, `results`, `drivers`, `constructors`, `standings`) — schéma
   multi-saison à figer dans `schema.sql`.
2. **F2 (P1)** Ingestion FastF1 → Supabase (`laps`, `pit_stops`,
   `tire_stints`) + cache FastF1 sur Drive.
3. **F3 (P2)** Pipeline RAG textuel : Wikipedia + PDF FIA → chunking → BGE-small
   → collection Qdrant ; run tracké MLflow/DagsHub.
4. **F4 (P2)** Agents : Orchestrateur, Stats, Stratégie, Contexte, Synthèse,
   Vérificateur (dans `app/agents/`), graphe complet `graph.py`.
5. **F5 (P2)** Serveurs MCP : `f1_stats`, `f1_telemetry`, `f1_knowledge`.
6. **F6 (P3)** Jeu de 20-30 questions de référence + eval RAGAS réel dans
   `tests/eval/` (le fichier `questions.json` est encore vide).
7. **F7 (P3)** Table `logs` Supabase + onglet Monitoring (Plotly) dans l'app.
8. **F8 (P3)** UI chat complète (sources, traces, feedback) + connexion
   Streamlit app aux agents.
9. **F9 (P4)** Déploiement Streamlit Community Cloud + secrets.
10. **(P4)** Évaluation finale 50+ questions, README final, rapport, slides.

## 📌 Décisions importantes

- Zéro exécution locale : dev dans Colab, secrets en Secrets Colab / secrets
  Streamlit Cloud — mêmes noms de variables partout.
- `requirements.txt` = runtime (Colab + Streamlit Cloud) ; `requirements-dev.txt`
  = CI/outils (DVC, MLflow, RAGAS, ruff, pytest) pour garder l'app Streamlit
  Cloud légère.
- Schéma Supabase conçu multi-saison dès maintenant (colonne `season`), mais
  seule la saison 2023 est ingestée en v1.
- Dockerfiles = bonus CV uniquement, jamais utilisés pour le déploiement réel.
- Migrations/DDL Supabase : uniquement via `app/data_pipeline/schema.sql` et le
  code du pipeline (jamais de manipulation manuelle).

## 🚨 Actions requises hors code

- Ajouter les secrets du repo GitHub (Groq, MLflow/DagsHub) avant d'activer un
  vrai quality gate `eval.yml`.
- Comptes : Groq, Qdrant Cloud, Supabase, DagsHub, Streamlit Cloud (cf.
  `docs/deployment.md`).