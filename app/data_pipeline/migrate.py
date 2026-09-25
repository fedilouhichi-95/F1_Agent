"""Apply the Supabase schema through the project's migration runner."""

from __future__ import annotations

import re
from pathlib import Path

import psycopg2

from app.config import AppConfig

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

_DSN_PATTERN = re.compile(r"postgres(?:ql)?://\S+", re.IGNORECASE)
_REDACTED = "<url redacted>"
_CONNECTION_HINT = (
    "Vérifie que SUPABASE_DB_URL utilise la chaîne du Session pooler, copiée depuis "
    "Project Settings > Database > Connect. L'hôte aws-N.pooler.supabase.com ne se "
    "déduit pas de la région, et la connexion directe est IPv6-only."
)


def describe_failure(exc: Exception) -> str:
    """Summarise a migration failure, keeping the cause but hiding credentials."""
    detail = _DSN_PATTERN.sub(_REDACTED, " ".join(str(exc).split()))
    return f"{detail} — {_CONNECTION_HINT}"


def apply_schema(config: AppConfig, schema_path: Path = SCHEMA_PATH) -> None:
    """Apply the schema in a single transaction using the service role connection."""
    if not config.supabase_db_url:
        raise ValueError("SUPABASE_DB_URL is required to apply the schema")

    schema_sql = schema_path.read_text(encoding="utf-8")
    connection = psycopg2.connect(
        config.supabase_db_url,
        password=config.supabase_db_password,
    )
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(schema_sql)
        finally:
            cursor.close()
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> None:
    """Apply the schema using environment configuration."""
    try:
        apply_schema(AppConfig.from_env())
    except (ValueError, psycopg2.Error) as exc:
        raise SystemExit(f"Migration impossible : {describe_failure(exc)}") from exc
    print("Schéma Supabase appliqué avec succès.")


if __name__ == "__main__":
    main()
