# Plan PFE — PitStop Assistant (16 semaines)

Roadmap détaillée conditionnée dans le brief initial, stockée ici pour
référence. Le suivi réel d'avancement vit dans `PROGRESS.md` (et le board
GitHub Projects).

## Setup (avant Semaine 1)

Comptes et secrets : Groq, Qdrant Cloud, Supabase, DagsHub, GitHub, Streamlit
Cloud + montage Google Drive + Secrets Colab. Voir `docs/deployment.md`.

## Phases

- **Phase 0 (S1)** Cadrage MVP, structure du repo, `requirements.txt`,
  "hello world" sur les 3 services cloud depuis Colab, board GitHub Projects.
- **Phase 1 (S2-S3)** Ingestion : `01` Jolpica-F1 → Supabase (races, results,
  drivers, constructors, standings), `02` FastF1 → Supabase (laps, pit_stops,
  tire_stints), cache FastF1 sur Drive, DVC (remote Drive).
- **Phase 2 (S4-S5)** RAG textuel : Wikipedia + PDF FIA → chunks (300-500
  tokens, overlap 50-100), embeddings GPU T4 (BGE-small) → Qdrant Cloud,
  run loggé MLflow/DagsHub, test de similarité.
- **Phase 3 (S6-S8)** Agents : prototype Orchestrateur (LangGraph, Groq),
  puis Stats, Stratégie, Contexte, Synthèse, Vérificateur dans `app/agents/`,
  assemblage du graphe complet dans `graph.py`.
- **Phase 4 (S9-S10)** Serveurs MCP : `f1_stats_server`, `f1_telemetry_server`,
  `f1_knowledge_server` (stdio), tests indépendants, doc des tools.
- **Phase 5 (S11-S13)** CI/CD + évaluation : tests pytest (mocks),
  `.github/workflows/ci.yml`, jeu de 20-30 questions de référence, job RAGAS +
  exactitude chiffrée dans `eval.yml` (bloquant pour main), table `logs`
  Supabase + onglet Monitoring dans l'app.
- **Phase 6 (S14-S15)** Application Streamlit : chat, sources, traces,
  feedback ; déploiement Streamlit Community Cloud (CD auto sur main) ;
  bonus CV : Dockerfiles (non utilisés en réel).
- **Phase 7 (S16)** Évaluation finale (50+ questions), README complet, rapport
  technique, slides, démo live (URL publique), description CV/LinkedIn.

## Garde-fous quotidiens

- Committer avant de fermer une session Colab.
- Gros fichiers (cache FastF1, chunks) sur Google Drive, jamais dans `/content/`.
- Clés API uniquement dans Secrets Colab / secrets Streamlit Cloud.
- Le code déployé vit dans `app/`, testable indépendamment des notebooks.
- Surveiller les quotas gratuits Groq (~requêtes/minute) et Qdrant (~1 Go).

## Valorisation CV

> Assistant IA multi-agents pour la Formule 1 — Plateforme MLOps cloud-native.
> RAG + 6 agents spécialisés (LangGraph) sur une architecture 100 % cloud
> gratuite (Groq, Qdrant Cloud, Supabase). 3 serveurs MCP réutilisables.
> Pipeline MLOps complet : DVC, MLflow (DagsHub), CI/CD avec quality gate RAGAS
> (GitHub Actions), déploiement continu Streamlit Cloud + monitoring intégré.