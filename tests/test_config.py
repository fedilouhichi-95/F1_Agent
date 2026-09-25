"""Tests de la configuration applicative (aucun appel réseau)."""

from __future__ import annotations

import pytest
from app.config import DEFAULT_EMBEDDING_MODEL, DEFAULT_GROQ_MODEL, AppConfig


def test_from_env_uses_defaults_when_empty() -> None:
    config = AppConfig.from_env()
    assert config.groq_api_key == ""
    assert config.qdrant_api_key == ""
    assert config.supabase_anon_key == ""
    assert config.supabase_db_url == ""
    assert config.supabase_db_password == ""
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


def test_from_mapping_reads_streamlit_secrets() -> None:
    config = AppConfig.from_mapping(
        {
            "GROQ_API_KEY": " groq-secret ",
            "GROQ_MODEL": "custom-model",
            "QDRANT_URL": "https://qdrant.example",
            "QDRANT_API_KEY": "qdrant-secret",
            "QDRANT_COLLECTION_NAME": "docs",
            "SUPABASE_URL": "https://supabase.example",
            "SUPABASE_ANON_KEY": "supabase-secret",
            "SUPABASE_DB_URL": "postgresql://db.example",
            "SUPABASE_DB_PASSWORD": "db-secret",
            "MLFLOW_TRACKING_PASSWORD": "mlflow-secret",
        }
    )

    assert config.groq_api_key == "groq-secret"
    assert config.groq_model == "custom-model"
    assert config.qdrant_url == "https://qdrant.example"
    assert config.qdrant_api_key == "qdrant-secret"
    assert config.qdrant_collection_name == "docs"
    assert config.supabase_url == "https://supabase.example"
    assert config.supabase_anon_key == "supabase-secret"
    assert config.supabase_db_url == "postgresql://db.example"
    assert config.supabase_db_password == "db-secret"
    assert config.mlflow_tracking_password == "mlflow-secret"


def test_mapping_overrides_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "environment-key")

    config = AppConfig.from_env(overrides={"GROQ_API_KEY": "streamlit-key"})

    assert config.groq_api_key == "streamlit-key"


def test_blank_mapping_value_falls_back_to_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "environment-key")

    config = AppConfig.from_env(overrides={"GROQ_API_KEY": "   "})

    assert config.groq_api_key == "environment-key"


def test_repr_hides_sensitive_values() -> None:
    config = AppConfig.from_mapping(
        {
            "GROQ_API_KEY": "groq-secret",
            "QDRANT_API_KEY": "qdrant-secret",
            "SUPABASE_ANON_KEY": "supabase-secret",
            "SUPABASE_DB_URL": "postgresql://db-secret",
            "SUPABASE_DB_PASSWORD": "db-secret",
            "MLFLOW_TRACKING_PASSWORD": "mlflow-secret",
        }
    )

    rendered = repr(config)

    assert "groq-secret" not in rendered
    assert "qdrant-secret" not in rendered
    assert "supabase-secret" not in rendered
    assert "db-secret" not in rendered
    assert "mlflow-secret" not in rendered
    assert "groq_api_key" not in rendered


def test_config_is_immutable() -> None:
    config = AppConfig.from_env()
    assert config.__dataclass_params__.frozen
