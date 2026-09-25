"""Fixtures pytest partagées."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force un environnement vierge pour éviter toute fuite de secrets en test."""
    for variable in (
        "GROQ_API_KEY",
        "GROQ_MODEL",
        "QDRANT_URL",
        "QDRANT_API_KEY",
        "QDRANT_COLLECTION_NAME",
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY",
        "EMBEDDING_MODEL",
        "FASTF1_CACHE_DIR",
        "MLFLOW_TRACKING_URI",
        "MLFLOW_TRACKING_USERNAME",
        "MLFLOW_TRACKING_PASSWORD",
    ):
        monkeypatch.delenv(variable, raising=False)
