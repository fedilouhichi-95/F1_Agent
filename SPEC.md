# SPEC — PitStop Assistant

## Objectif

Assistant IA multi-agents pour la Formule 1 qui répond en langage naturel à des questions
statistiques, stratégiques et réglementaires (saison F1 2023) en combinant RAG textuel et
6 agents spécialisés (LangGraph). Développé et déployé sur une stack **100 % gratuite** :
aucune exécution locale (tout se passe dans Google Colab + services cloud).

## Stack validée

- **Langage** : Python 3.12
- **Orchestration agents** : LangGraph + Groq (API gratuite, Llama 3.1/3.3)
- **RAG** : sentence-transformers (BGE-small) + base vectorielle **Qdrant Cloud**
- **Données structurées F1** : **Supabase** (PostgreSQL hébergé) — données Jolpica-F1 + FastF1
- **Interface** : **Streamlit Community Cloud** (déploiement permanent)
- **MLOps** : DVC (remote Google Drive) + MLflow (DagsHub) + GitHub Actions (CI/CD)
- **Garantie de qualité** : pytest (mocks) + évaluation RAGAS avec portail de qualité chiffré
- Versions épinglées dans `requirements.txt`

## Features priorisées (v1)

1. **Ingestion données structurées F1 2023** — résultats, qualifs, classements (Jolpica-F1)
   et données FastF1 (laps, pit stops, pneus) vers Supabase.
   *Acceptation* : tables `races`, `results`, `drivers`, `constructors`, `standings`,
   `laps`, `pit_stops`, `tire_stints` peuplées et interrogeables ; schéma *multi-saison*
   (colonne `season`).
2. **Pipeline RAG textuel** — pages Wikipedia (pilotes, écuries, circuits, saison) + PDF
   réglementaires FIA → chunking → embeddings → collection Qdrant Cloud.
   *Acceptation* : collection peuplée avec métadonnées, requête de similarité fonctionnelle
   depuis Colab, run tracké sur DagsHub (MLflow).
3. **6 agents LangGraph** — Orchestrateur (routing), Stats (SQL Supabase), Stratégie
   (analyse FastF1), Contexte (RAG Qdrant), Synthèse (réponse finale Groq),
   Vérificateur (recoupement des chiffres vs Supabase).
   *Acceptation* : pipeline de bout en bout répond exactement, chiffres vérifiés, traces
   par agent disponibles.
4. **3 serveurs MCP** — `f1_stats`, `f1_telemetry`, `f1_knowledge` (stdio, sous-processus).
   *Acceptation* : chaque serveur testable via `python -m`, avec client MCP simple.
5. **Tests + CI/CD** — pytest unitaires (mocks Groq/Qdrant/Supabase) + lint ruff ;
   job GitHub Actions à chaque push.
   *Acceptation* : CI verte à chaque push sur toutes branches.
6. **Évaluation continue (quality gate)** — jeu de 20-30 questions de référence avec
   chiffres vérifiés + métriques RAGAS ; portail bloquant à chaque PR vers `main`.
   *Acceptation* : fusion bloquée si les seuils régressent ; runs loggés MLflow.
7. **App Streamlit finale** — chat, sources affichées (structuré vs extrait), traces
   multi-agents, feedback utilisateur, onglet Monitoring (latence, catégories, feedback)
   alimenté par table `logs` Supabase.
   *Acceptation* : app publique déployée en permanence, CD auto sur push `main`.

## Hors périmètre v1

- Prédiction de résultats par ML
- Authentification / login
- Ingestion de plusieurs saisons (ingestion = 2023 uniquement, schéma déjà multi-saison)
- Prometheus / Grafana (monitoring = dashboard Streamlit + table `logs`)
- Déploiement Docker réel (les Dockerfiles sont un bonus CV uniquement)
- Expérimentation longue d'embeddings (un modèle retenu : BGE-small)

## Contraintes

- Zéro exécution locale : dev dans Google Colab, secrets via Secrets Colab / secrets Streamlit
- Coût : strictement 0 €/mois (quotas gratuits Groq, Qdrant Cloud, Supabase, DagsHub)
- Deadline : 16 semaines (PFE), livrable démo via URL publique