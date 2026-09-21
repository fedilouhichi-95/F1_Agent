"""Fixtures pytest partagées."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force un environnement vierge pour éviter toute fuite de secrets en test."""
    for variable in (
        "GROQ_API_KEY",
        "QDRANT_URL",
        "QDRANT_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY",
    ):
        monkeypatch.delenv(variable, raising=False)
