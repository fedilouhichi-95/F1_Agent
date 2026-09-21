"""Smoke entrypoint: `python -m app` affiche l'état de configuration."""

from __future__ import annotations

import sys

from app import __version__
from app.config import AppConfig


def main() -> None:
    """Print a short configuration report, one call to the user question."""
    config = AppConfig.from_env()
    configured = sum(
        bool(value)
        for value in (config.groq_api_key, config.qdrant_api_key, config.supabase_anon_key)
    )
    print(f"PitStop Assistant v{__version__}")
    print(f"Python {sys.version.split()[0]}")
    print(f"Services configurés : {configured}/3 (Groq, Qdrant, Supabase)")


if __name__ == "__main__":
    main()
