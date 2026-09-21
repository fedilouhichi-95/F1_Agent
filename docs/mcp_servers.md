# Serveurs MCP — PitStop Assistant

Trois serveurs MCP (Model Context Protocol) qui exposent les capacités du
projet sous forme de tools. Communication en **stdio**, lancés en
sous-processus par l'application (fonctionne en dev Colab comme en prod
Streamlit Cloud). Les serveurs n'importent jamais `streamlit`.

| Serveur | Tools (à venir) | Source de données |
|---|---|---|
| `f1_stats_server` | requêtage résultats, classements, drivers | Supabase |
| `f1_telemetry_server` | laps, pit stops, stratégies pneus | Supabase (données FastF1) |
| `f1_knowledge_server` | recherche sémantique de documents | Qdrant Cloud |

## Lancement en test

```bash
python -m app.mcp_servers.f1_stats_server        # stdio, prêt pour un client MCP
```

## Schémas des tools

Documentation complète des tools exposés (noms, entrées, sorties) ajoutée à
la Phase 4 du projet (Semaines 9-10 de la roadmap).