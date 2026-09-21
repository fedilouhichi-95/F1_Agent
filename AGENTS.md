# AGENTS — PitStop Assistant

Guide de travail pour toute session sur ce projet (humain ou IA).

## Conventions de code

- Python 3.12, typage strict : annotations de type sur toutes les signatures publiques.
- Style : **ruff** (lint + format). Commande de vérification : `ruff check .` — viser zéro violation.
- Noms en anglais dans le code (variables, modules) ; interface utilisateur et documentation en français.
- Chaque agent = un module dans `app/agents/` avec une classe ou un ensemble de fonctions pures (LLM injecté).
- Les serveurs MCP ne dépendent pas de Streamlit : ils ne doivent jamais importer `streamlit`.
- Pas de secrets en dur dans le code, les notebooks, les prompts ou les commits — toujours via `.env` (local), Secrets Colab (dev) ou secrets Streamlit (prod).
- Les notebooks Colab (`notebooks/`) sont des outils d'expérimentation : le code applicatif déployé vit dans `app/`.
- Config applicative centralisée dans `app/config.py` (lecture des variables d'environnement).

## Style de commits (conventional commits)

- Format : `type(scope): résumé` — impératif, ≤ 72 caractères. Types : `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `perf`, `ci`, `build`.
- Exemples :
  - `feat(agents): add strategy agent with pit-stop analysis`
  - `fix(context): correct Qdrant payload metadata keys`
  - `chore: initial project scaffold`
- Commits **atomiques** : une logique par commit, staging précis (`git add -p`).
- Jamais de commit contenant fichiers générés, secrets ou changements non liés.
- Toujours committer en fin de session Colab (Colab n'est pas un stockage fiable).

## Commandes

Toutes s'exécutent dans une session Colab après clonage du repo, et localement si besoin.

```bash
pip install -r requirements.txt        # dépendances (versions épinglées)
ruff check .                           # lint
ruff format .                          # formatage automatique
python -m pytest                       # tests unitaires (mocks, pas d'appels réseaux)
python -m pytest -m eval               # évaluation RAGAS + exactitude chiffrée (quality gate)
streamlit run app/streamlit_app.py     # app en local/Colab pour test
python -m app.mcp_servers.f1_stats_server   # tester un serveur MCP en stdio
```

## Interdictions

- ❌ Aucune nouvelle dépendance sans validation de l'utilisateur (pas de `pip install` ajouté au
  `requirements.txt` sans demande préalable).
- ❌ Aucun secret (clé API, mot de passe, token) dans un fichier versionné, un prompt, un log ou un notebook.
- ❌ Aucune migration/manipulation manuelle des tables Supabase sans passer par le code du pipeline.
- ❌ Ne jamais modifier `SPEC.md` / `AGENTS.md` sans accord explicite.
- ❌ Pas de `reset --hard` / force-push / rebase sur des branches partagées sans validation.

## Zones sensibles

- `requirements.txt` : versions épinglées, à mettre à jour avec précaution (compatibilité Colab + Streamlit Cloud).
- `.env.example` / `.streamlit/secrets.toml` : ne contenir que des valeurs d'exemple/vides, jamais de vraies clés.
- `.github/workflows/` : la CI consomme les secrets du repo (Groq, Qdrant, Supabase) — ne pas logguer ces valeurs dans les steps.
- Collection Qdrant Cloud et tables Supabase : données de travail versionnées via DVC (remote Google Drive), pas dans le repo git.