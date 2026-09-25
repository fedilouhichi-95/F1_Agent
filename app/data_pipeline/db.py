"""Idempotent Supabase write layer for the data pipeline.

Design notes:

- Writes go through raw ``psycopg2``: the ingestion needs real transactions and
  fast batched inserts. Reads from the app and the MCP servers go through
  ``supabase-py`` over HTTP with the anon key and RLS, which is a separate path.
- Every write is an upsert keyed on a natural unique key, so re-running the
  ingestion converges instead of duplicating rows.
- Values are always passed as query parameters, never interpolated. Identifiers
  are validated against a strict pattern and double-quoted, so they cannot carry
  user input. Building the statement as a plain string (rather than via
  ``psycopg2.sql``) keeps it a pure, testable function: ``sql.Identifier`` can
  only render against a live connection.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from contextlib import contextmanager

import psycopg2
from psycopg2.extensions import connection
from psycopg2.extras import execute_values

from app.config import AppConfig
from app.data_pipeline.errors import missing_configuration

DEFAULT_PAGE_SIZE = 1000
CONNECT_TIMEOUT = 30

_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


def quote(name: str) -> str:
    """Validate a SQL identifier and return it double-quoted.

    The pattern admits only lowercase letters, digits and underscores, so the
    value can never contain a quote, a space or a statement separator.
    """
    if not _IDENTIFIER.match(name):
        raise ValueError(f"Identifiant SQL invalide : {name!r}")
    return f'"{name}"'


def connect(config: AppConfig) -> connection:
    """Open an ingestion connection using the service role credentials."""
    if not config.supabase_db_url:
        raise missing_configuration("SUPABASE_DB_URL")
    return psycopg2.connect(
        config.supabase_db_url,
        password=config.supabase_db_password,
        connect_timeout=CONNECT_TIMEOUT,
    )


@contextmanager
def transaction(active: connection) -> Iterator[None]:
    """Commit on success, roll back on any error. Never closes the connection."""
    try:
        yield
        active.commit()
    except Exception:
        active.rollback()
        raise


def build_upsert_statement(
    *,
    table: str,
    columns: Sequence[str],
    conflict: Sequence[str],
    update_columns: Sequence[str],
) -> str:
    """Render an ``INSERT ... ON CONFLICT ... DO UPDATE`` statement."""
    inserted = ", ".join(quote(name) for name in columns)
    keys = ", ".join(quote(name) for name in conflict)
    assignments = ", ".join(f"{quote(name)} = EXCLUDED.{quote(name)}" for name in update_columns)
    if not assignments:
        raise ValueError("Un upsert sans colonne à mettre à jour n'a aucun effet")
    return (
        f"INSERT INTO {quote(table)} ({inserted}) VALUES %s "
        f"ON CONFLICT ({keys}) DO UPDATE SET {assignments}"
    )


def upsert(
    active: connection,
    *,
    table: str,
    columns: Sequence[str],
    rows: Sequence[Sequence[object]],
    conflict: Sequence[str],
    update_columns: Sequence[str] | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> int:
    """Insert rows, updating the non-key columns on conflict. Returns row count.

    ``conflict`` must name a real unique index or constraint, and is a subset of
    ``columns``. Generated identity columns stay out of ``columns`` so that
    PostgreSQL allocates them.
    """
    if not rows:
        return 0

    missing = set(conflict) - set(columns)
    if missing:
        raise ValueError(f"Colonnes de conflit absentes de l'insertion : {sorted(missing)}")

    targets = [name for name in columns]
    if update_columns is None:
        update_columns = [name for name in targets if name not in set(conflict)]

    statement = build_upsert_statement(
        table=table,
        columns=targets,
        conflict=conflict,
        update_columns=update_columns,
    )
    cursor = active.cursor()
    try:
        execute_values(cursor, statement, rows, page_size=page_size)
    finally:
        cursor.close()
    return len(rows)


def fetch_all(
    active: connection,
    statement: str,
    params: Sequence[object] = (),
) -> list[tuple[object, ...]]:
    """Run a read query and return every row."""
    cursor = active.cursor()
    try:
        cursor.execute(statement, params)
        return cursor.fetchall()
    finally:
        cursor.close()


def fetch_one(
    active: connection,
    statement: str,
    params: Sequence[object] = (),
) -> tuple[object, ...] | None:
    """Run a read query and return its first row, or None."""
    rows = fetch_all(active, statement, params)
    return rows[0] if rows else None
