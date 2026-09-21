"""Tests de la configuration applicative (aucun appel réseau)."""

from __future__ import annotations

import pytest
from app.config import DEFAULT_EMBEDDING_MODEL, DEFAULT_GROQ_MODEL, AppConfig


def test_from_env_uses_defaults_when_empty() -> None:
    config = AppConfig.from_env()
    assert config.groq_api_key == ""
    assert config.qdrant_api_key == ""
    assert config.supabase_anon_key == ""
    assert config.qdrant_collection_name == "pitstop_docs"
    assert config.groq_model == DEFAULT_GROQ_MODEL
    assert config.embedding_model == DEFAULT_EMBEDDING_MODEL


def test_from_env_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("QDRANT_COLLECTION_NAME", "fixtures")
    config = AppConfig.from_env()
    assert config.groq_api_key == "test-key"
    assert config.qdrant_collection_name == "fixtures"
    assert config.qdrant_api_key == ""
    assert config.groq_model == DEFAULT_GROQ_MODEL


def test_config_is_immutable() -> None:
    config = AppConfig.from_env()
    assert config.__dataclass_params__.frozen
