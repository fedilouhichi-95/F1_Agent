# PROJECT_MAP

> Cartographie établie le 25 septembre 2026 à partir de la révision `038eeec`, sur la branche `docs/improve-readme`.
> Ce document décrit l’état observé du dépôt, et non la roadmap prévue par `SPEC.md`.

## 1. Vue d’ensemble

PitStop Assistant est actuellement un scaffold Python minimal. L’interface Streamlit affiche uniquement l’état de configuration ; aucune question utilisateur n’est traitée et aucun service cloud n’est contacté.

| Élément | Observation |
|---|---|
| État fonctionnel | Configuration, smoke test CLI, vue d’état Streamlit, contrat abstrait d’agent et DDL partiel |
| Version applicative | `0.1.0` dans `app/__init__.py` |
| Branche analysée | `docs/improve-readme` |
| Révision analysée | `038eeec` (`docs :modification readme`) |
| Taille suivie | 33 fichiers Git |
| Code Python | 14 fichiers, 271 lignes : 169 dans `app/`, 102 dans `tests/` |
| Tests | 6 fonctions de test : 5 unitaires et 1 test structurel d’évaluation |
| Notebooks | 0 fichier `.ipynb` ; seul `notebooks/README.md` est présent |
| Dépendances | Manifestes runtime et développement présents, mais la plupart des bibliothèques métier ne sont pas importées |
| État Git au début du scan | Branche propre, aucun fichier non suivi |

### Stack déclarée et intégration réelle

| Composant | Déclaré dans | Utilisation observée |
|---|---|---|
| Python 3.12 | `pyproject.toml`, CI, documentation | Cible de compilation et version CI ; validée par configuration |
| Streamlit | `requirements.txt` | Importé par `app/streamlit_app.py` pour afficher trois statuts |
| `python-dotenv` | `requirements.txt` | Importé par `app/config.py` pour charger un fichier `.env` |
| Groq, LangGraph, LangChain | `requirements.txt` | Aucun import ni client ; le flux d’agents n’existe pas |
| Qdrant, sentence-transformers | `requirements.txt` | Aucun import ; aucun chunk, embedding ou recherche |
| Supabase, `psycopg2` | `requirements.txt` | Aucun import ; aucun accès ou ingestion |
| FastF1, Requests, NumPy, pandas | `requirements.txt` | Aucun import ; aucun pipeline télémétrie |
| Plotly | `requirements.txt` | Aucun import ; aucun dashboard de monitoring |
| pytest, Ruff | `requirements-dev.txt`, CI | Tests et lint sont configurés, mais les outils n’étaient pas installés dans l’environnement d’audit |
| RAGAS, MLflow, DVC, pdfplumber | `requirements-dev.txt` | Dépendances déclarées, sans code d’intégration |
| GitHub Actions | `.github/workflows/` | Workflows CI et eval présents, avec les limites décrites dans `DOC_DRIFT.md` |

## 2. Arborescence réelle

```text
app/
├── __init__.py                 # métadonnées et version
├── __main__.py                 # smoke test CLI
├── config.py                   # lecture centralisée des variables d’environnement
├── streamlit_app.py            # vue Streamlit minimale
├── agents/
│   ├── __init__.py             # exports du contrat de base
│   └── base.py                 # AgentResult, BaseAgent, factory non implémentée
├── data_pipeline/
│   ├── __init__.py             # package vide
│   └── schema.sql              # une seule table drivers
├── mcp_servers/__init__.py     # package vide
├── monitoring/__init__.py      # package vide
└── rag/__init__.py             # package vide
```

Autres zones :

- `tests/` contient les fixtures, deux tests du contrat/configuration et le squelette d’évaluation.
- `docs/` contient l’architecture, le déploiement, les serveurs MCP et la roadmap PFE.
- `notebooks/README.md` décrit sept notebooks qui ne sont pas présents.
- `.github/workflows/` contient `ci.yml` et `eval.yml`.
- Aucun `Dockerfile`, manifeste DVC, script d’ingestion, `graph.py` ou client MCP n’est présent.

## 3. Architecture effectivement implémentée

### 3.1 Composants et responsabilités

| Fichier ou package | Responsabilité réelle | Dépendances |
|---|---|---|
| `app/config.py` | Charger un `.env`, lire les variables et construire un dataclass `AppConfig` gelé | `os`, `dataclasses`, `python-dotenv` |
| `app/__main__.py` | Afficher la version, la version Python et un compteur de services apparemment configurés | `app.config` |
| `app/streamlit_app.py` | Configurer la page Streamlit et afficher l’état Groq/Qdrant/Supabase | `streamlit`, `app.config` |
| `app/agents/base.py` | Définir `AgentResult`, le contrat abstrait `BaseAgent.run` et une factory qui lève une exception | `abc`, `dataclasses` |
| `app/agents/__init__.py` | Réexporter `AgentResult` et `BaseAgent` | `app.agents.base` |
| `app/rag/` | Décrire textuellement un futur module RAG ; aucune fonction | aucune |
| `app/data_pipeline/` | Décrire textuellement un futur pipeline ; aucune ingestion | aucune |
| `app/monitoring/` | Décrire textuellement un futur monitoring ; aucune fonction | aucune |
| `app/mcp_servers/` | Décrire textuellement les serveurs MCP ; aucun serveur | aucune |
| `tests/` | Vérifier le contrat de base, les valeurs par défaut de configuration et la structure JSON | `pytest` |
| `.github/workflows/ci.yml` | Installer les dépendances, lancer Ruff et les tests hors `eval` | GitHub Actions |
| `.github/workflows/eval.yml` | Installer les dépendances et lancer le test marqué `eval` sur les PR vers `main` | GitHub Actions et secrets partiels |

### 3.2 Graphe de dépendances runtime

```text
Fichier .env ou environnement du processus
                │
                ▼
       load_dotenv() / os.getenv
                │
                ▼
             AppConfig
             ┌──┴───────────────┐
             ▼                  ▼
      app.__main__      app.streamlit_app
             │                  │
       texte CLI          statuts Streamlit

AgentResult / BaseAgent ◄── test EchoAgent
questions.json ────────────► test structurel eval
```

Aucun chemin ne va vers Groq, Supabase, Qdrant, FastF1, LangGraph, MLflow, DVC ou un serveur MCP.

## 4. Flux de données principal

### 4.1 Flux réel

1. Le processus démarre via `python -m app` ou `streamlit run app/streamlit_app.py`.
2. `app.config` charge éventuellement un `.env` et construit `AppConfig`.
3. Le smoke test compte trois clés et affiche un rapport textuel.
4. L’application Streamlit affiche trois lignes d’état de connexion.
5. Le programme se termine ou attend le prochain cycle Streamlit.

Il n’existe pas de flux de question, de recherche documentaire, de requête SQL, de génération de réponse, de vérification, d’écriture de log ou de retour utilisateur.

### 4.2 Flux documenté mais non implémenté

```text
Question
  → Streamlit
  → Orchestrateur LangGraph
  → Stats Supabase | Stratégie FastF1 | Contexte Qdrant
  → Synthèse Groq
  → Vérificateur
  → réponse, sources, traces et log Supabase
```

Ce flux est une cible de `SPEC.md` et de `docs/architecture.md`, pas un chemin exécutable dans le code actuel.

## 5. Points d’entrée et commandes réelles

| Commande | État | Comportement observé ou limite |
|---|---|---|
| `pip install -r requirements.txt -r requirements-dev.txt` | Documentée | Installation prévue ; non exécutée pendant l’audit |
| `python -m app` | Point d’entrée existant | Le point d’entrée affiche version, Python et `Services configurés`; dans l’environnement d’audit, `python` n’était pas disponible et l’essai avec `python3` a échoué à l’import de `python-dotenv` avant la logique applicative |
| `streamlit run app/streamlit_app.py` | Point d’entrée existant | Affiche seulement l’état des connexions ; aucun chat |
| `python -m pytest` | Commande documentée | Six tests sont présents ; dépendances non installées dans l’environnement d’audit |
| `python -m pytest -m eval` | Commande partiellement fonctionnelle | Un seul test vérifie la structure JSON ; aucun appel RAGAS, aucun calcul d’exactitude et aucun seuil |
| `ruff check .` | Configurée | `pyproject.toml` sélectionne `E`, `F`, `I`, `UP` et `B`; Ruff n’était pas installé pendant l’audit, résultat non rejoué |
| `ruff format .` | Documentée dans `AGENTS.md` | Ruff est configuré, mais la CI ne vérifie pas le formatage |
| `python -m app.mcp_servers.f1_stats_server` | Cassée | Le module `f1_stats_server.py` n’existe pas ; aucun module MCP ne peut être lancé |
| `python -m app.mcp_servers.f1_telemetry_server` | Absente | Aucun fichier serveur |
| `python -m app.mcp_servers.f1_knowledge_server` | Absente | Aucun fichier serveur |
| Commande d’ingestion, graphe ou tracking | Absente | Aucun runner pour Jolpica-F1, FastF1, LangGraph, DVC ou MLflow n’est exposé |

## 6. Modèle de données observé

`app/data_pipeline/schema.sql` ne crée que `drivers` :

- `driver_id` est la clé primaire et se référence lui-même ;
- `season` est une colonne obligatoire ;
- `name` est obligatoire ;
- `code`, `number` et `nationality` sont facultatifs.

Les tables suivantes, promises dans `SPEC.md` et `docs/architecture.md`, n’existent pas dans le DDL : `races`, `results`, `constructors`, `standings`, `laps`, `pit_stops`, `tire_stints` et `logs`.

Le DDL ne définit pas non plus de stratégie d’identité pour les identifiants, de contraintes entre tables, de politiques RLS, de grants ou de migration versionnée. La clé primaire `driver_id`, seule et sans dimension saisonnière dans la clé, ne permet pas de représenter plusieurs lignes saisonnières du même driver avec le même identifiant.

## 7. Conventions réelles

### 7.1 Conventions observées

- Les modules Python utilisent `from __future__ import annotations`.
- Les fonctions publiques inspectées portent des annotations de type.
- Les structures de configuration et de résultat utilisent des dataclasses.
- `AppConfig` et `AgentResult` sont déclarés `frozen=True`, mais `AgentResult` contient des listes et dictionnaires mutables.
- Les identifiants de code sont en anglais ; les textes d’interface et la documentation sont principalement en français, avec quelques docstrings de fonctions en anglais.
- Les tests sont courts, sans accès réseau, et utilisent un stub local `EchoAgent`.
- Les dépendances métier sont regroupées dans les manifestes, mais aucune convention d’injection réelle n’est encore observable pour un LLM.
- Les commits sont rares : le scaffold initial est suivi d’un commit documentaire.

### 7.2 Écarts avec `AGENTS.md`

- Le contrat décrit l’injection d’un LLM à l’instanciation, mais `BaseAgent` ne définit aucun constructeur ni paramètre LLM.
- La règle « un module par agent » n’est pas encore appliquée à six agents, car aucun agent spécialisé n’existe.
- La commande MCP documentée ne peut pas fonctionner.
- La commande d’installation indiquée dans `AGENTS.md` n’installe que `requirements.txt`, alors que Ruff et pytest sont dans `requirements-dev.txt`.
- La CI lance `ruff check`, mais pas `ruff format --check`.
- Le dernier commit `docs :modification readme` ne respecte pas le format `type(scope): résumé` annoncé.

## 8. Couverture des tests

| Test | Couverture réelle | Couverture absente |
|---|---|---|
| `tests/test_base.py` | Contrat `AgentResult`, implémentation d’un agent echo | Agents réels, injection LLM, sources, metadata, traces |
| `tests/test_config.py` | Valeurs par défaut, lecture de deux variables, gel du dataclass | Secrets Streamlit, DB, MLflow, validation des URLs, isolation complète |
| `tests/eval/test_quality.py` | JSON valide, présence d’une liste et date de référence | RAGAS, exactitude chiffrée, seuil, régression, MLflow, données réelles |
| `conftest.py` | Suppression de cinq variables de service avant chaque test | Nettoyage des autres variables et comportement de l’évaluation réseau |

La suite ne contient aucun test d’UI, d’entrée CLI, de SQL, de client cloud, de MCP, de pipeline, de RAG ou d’intégration entre agents.

## 9. Zones sensibles et dette technique

1. **Secrets de production** : `AppConfig` ne lit que l’environnement ; aucun chemin `st.secrets` n’est implémenté.
2. **Base de données** : le DDL est un embryon et ne fournit ni RLS ni migration exécutable.
3. **Quality gate** : un JSON vide produit un workflow vert et ne mesure aucune qualité.
4. **Surface de code** : les dépendances cloud sont déclarées en masse alors que les clients et pipelines sont absents.
5. **État des tests** : les tests sont des tests de scaffold et ne vérifient pas les critères d’acceptation.
6. **Documentation** : README, architecture et spécification décrivent une cible comme si elle était disponible ; `PROGRESS.md` est le document qui reflète le mieux l’état réel.
7. **Notebooks** : sept fichiers sont annoncés dans `notebooks/README.md`, mais aucun n’est versionné.
8. **Opérations** : DVC, MLflow, CD Streamlit et provisionnement Supabase ne sont pas matérialisés dans le dépôt.

## 10. Éléments non vérifiables depuis le dépôt

Les services distants et la configuration d’hébergement ne sont pas versionnés. Il est donc impossible de confirmer localement l’état de Supabase, Qdrant, DagsHub, MLflow, des secrets, de la liaison Streamlit Community Cloud, de la protection de la branche `main` ou du comportement réel du CD. Les notebooks décrits ne sont pas présents non plus.

## 11. Verdict de cartographie

Le dépôt est un **scaffold initial cohérent et volontairement minimal**, mais il n’est pas encore une implémentation de la plateforme décrite par `README.md`, `SPEC.md` et `docs/architecture.md`. La prochaine étape technique prioritaire est de choisir explicitement le statut de la documentation : roadmap non implémentée, ou implémentation progressive avec des indicateurs d’état vérifiables.
