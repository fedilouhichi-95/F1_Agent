"""PitStop Assistant — point d'entrée Streamlit (interface de chat).

Version scaffold : affiche l'app et l'état des connexions configurées.
Les features de chat, sources, traces et monitoring arrivent aux phases
suivantes du projet (voir SPEC.md).
"""

from __future__ import annotations

import streamlit as st

from app.config import AppConfig

APP_TITLE = "PitStop Assistant"


def render() -> None:
    """Render the Streamlit application."""
    st.set_page_config(page_title=APP_TITLE, page_icon=":racing_car:")
    config = AppConfig.from_env()

    st.title(APP_TITLE)
    st.caption("Assistant IA multi-agents pour la Formule 1 — saison 2023.")

    services = {
        "Groq (LLM)": bool(config.groq_api_key),
        "Qdrant Cloud (RAG)": bool(config.qdrant_url and config.qdrant_api_key),
        "Supabase (données)": bool(config.supabase_url and config.supabase_anon_key),
    }

    st.subheader("État des connexions")
    for name, ready in services.items():
        status = "ok" if ready else "à configurer (secrets)"
        st.write(f"{name} : {status}")


if __name__ == "__main__":
    render()
