# PitStop Assistant — notebooks Colab

Expérimentation uniquement. Le code applicatif déployé vit dans `app/`
et les notebooks n'en contiennent que des démonstrations.

- `00_setup.ipynb` — connexions cloud "hello world" (Groq, Qdrant, Supabase)
- `01_ingestion_resultats.ipynb` — Jolpica-F1 → Supabase (saison 2023)
- `02_ingestion_telemetrie.ipynb` — FastF1 → Supabase (laps, pit stops, pneus)
- `03_ingestion_textuelle.ipynb` — Wikipedia + PDF FIA → chunks
- `04_embeddings_qdrant.ipynb` — embeddings BGE-small → Qdrant Cloud
- `05_dev_orchestrateur.ipynb` — prototype graphe LangGraph
- `06_dev_agents.ipynb` — tests des agents spécialisés

Rappels Colab : stocker les clés dans les Secrets Colab (jamais en dur),
monter Google Drive pour le cache FastF1, committer avant de fermer la session.