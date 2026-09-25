"""Configuration applicative centralisée (variables d'environnement).

Lecture unique, sans effet de bord réseau. Un `.env` local est chargé si
présent ; en production ce sont les secrets Streamlit Cloud, en dev les
Secrets Colab — les noms de variables sont identiques partout.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_QDRANT_COLLECTION = "pitstop_docs"
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_FASTF1_CACHE_DIR = "/content/drive/MyDrive/f1_cache"


def _clean(value: object) -> str | None:
    """Normalize a configuration value and treat blank values as missing."""
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _value(name: str, default: str, source: Mapping[str, object]) -> str:
    """Read a value from an explicit source, then the environment, then defaults."""
    return _clean(source.get(name)) or _clean(os.getenv(name)) or default


@dataclass(frozen=True)
class AppConfig:
    """App metadata and service credentials, immutable once built."""

    groq_api_key: str = field(default="", repr=False)
    groq_model: str = field(default=DEFAULT_GROQ_MODEL)
    qdrant_url: str = field(default="")
    qdrant_api_key: str = field(default="", repr=False)
    qdrant_collection_name: str = field(default=DEFAULT_QDRANT_COLLECTION)
    supabase_url: str = field(default="")
    supabase_anon_key: str = field(default="", repr=False)
    supabase_db_url: str = field(default="", repr=False)
    supabase_db_password: str = field(default="", repr=False)
    embedding_model: str = field(default=DEFAULT_EMBEDDING_MODEL)
    fastf1_cache_dir: str = field(default=DEFAULT_FASTF1_CACHE_DIR)
    mlflow_tracking_uri: str = field(default="")
    mlflow_tracking_username: str = field(default="")
    mlflow_tracking_password: str = field(default="", repr=False)

    @classmethod
    def from_env(cls, *, overrides: Mapping[str, object] | None = None) -> AppConfig:
        """Build configuration from optional overrides and environment variables."""
        return cls.from_mapping(overrides or {})

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> AppConfig:
        """Build configuration with an explicit source taking precedence over the environment."""
        return cls(
            groq_api_key=_value("GROQ_API_KEY", "", values),
            groq_model=_value("GROQ_MODEL", DEFAULT_GROQ_MODEL, values),
            qdrant_url=_value("QDRANT_URL", "", values),
            qdrant_api_key=_value("QDRANT_API_KEY", "", values),
            qdrant_collection_name=_value(
                "QDRANT_COLLECTION_NAME", DEFAULT_QDRANT_COLLECTION, values
            ),
            supabase_url=_value("SUPABASE_URL", "", values),
            supabase_anon_key=_value("SUPABASE_ANON_KEY", "", values),
            supabase_db_url=_value("SUPABASE_DB_URL", "", values),
            supabase_db_password=_value("SUPABASE_DB_PASSWORD", "", values),
            embedding_model=_value("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL, values),
            fastf1_cache_dir=_value("FASTF1_CACHE_DIR", DEFAULT_FASTF1_CACHE_DIR, values),
            mlflow_tracking_uri=_value("MLFLOW_TRACKING_URI", "", values),
            mlflow_tracking_username=_value("MLFLOW_TRACKING_USERNAME", "", values),
            mlflow_tracking_password=_value("MLFLOW_TRACKING_PASSWORD", "", values),
        )
