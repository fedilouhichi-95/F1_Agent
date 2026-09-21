"""Configuration applicative centralisée (variables d'environnement).

Lecture unique, sans effet de bord réseau. Un `.env` local est chargé si
présent ; en production ce sont les secrets Streamlit Cloud, en dev les
Secrets Colab — les noms de variables sont identiques partout.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_QDRANT_COLLECTION = "pitstop_docs"
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_FASTF1_CACHE_DIR = "/content/drive/MyDrive/f1_cache"


def _env(name: str, default: str = "") -> str:
    """Read an environment variable, falling back to a default value."""
    return os.getenv(name, default).strip()


@dataclass(frozen=True)
class AppConfig:
    """App metadata and service credentials, immutable once built."""

    groq_api_key: str = field(default="")
    groq_model: str = field(default=DEFAULT_GROQ_MODEL)
    qdrant_url: str = field(default="")
    qdrant_api_key: str = field(default="")
    qdrant_collection_name: str = field(default=DEFAULT_QDRANT_COLLECTION)
    supabase_url: str = field(default="")
    supabase_anon_key: str = field(default="")
    embedding_model: str = field(default=DEFAULT_EMBEDDING_MODEL)
    fastf1_cache_dir: str = field(default=DEFAULT_FASTF1_CACHE_DIR)
    mlflow_tracking_uri: str = field(default="")
    mlflow_tracking_username: str = field(default="")
    mlflow_tracking_password: str = field(default="")

    @classmethod
    def from_env(cls) -> AppConfig:
        """Build the configuration from the current environment variables."""
        return cls(
            groq_api_key=_env("GROQ_API_KEY"),
            groq_model=_env("GROQ_MODEL", DEFAULT_GROQ_MODEL),
            qdrant_url=_env("QDRANT_URL"),
            qdrant_api_key=_env("QDRANT_API_KEY"),
            qdrant_collection_name=_env("QDRANT_COLLECTION_NAME", DEFAULT_QDRANT_COLLECTION),
            supabase_url=_env("SUPABASE_URL"),
            supabase_anon_key=_env("SUPABASE_ANON_KEY"),
            embedding_model=_env("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
            fastf1_cache_dir=_env("FASTF1_CACHE_DIR", DEFAULT_FASTF1_CACHE_DIR),
            mlflow_tracking_uri=_env("MLFLOW_TRACKING_URI"),
            mlflow_tracking_username=_env("MLFLOW_TRACKING_USERNAME"),
            mlflow_tracking_password=_env("MLFLOW_TRACKING_PASSWORD"),
        )
