"""Tests for shared pipeline error reporting."""

from __future__ import annotations

import psycopg2
from app.data_pipeline.errors import (
    CONNECTION_HINT,
    REDACTED,
    describe_failure,
    missing_configuration,
)


def test_describe_failure_keeps_postgres_reason() -> None:
    error = psycopg2.OperationalError(
        'connection to server at "aws-0-eu-west-1.pooler.supabase.com" (10.0.0.1), '
        "port 5432 failed: FATAL: (ENOTFOUND) tenant/user "
        "postgres.wsmohvwhcovsylwpivzl not found"
    )

    message = describe_failure(error)

    assert "tenant/user postgres.wsmohvwhcovsylwpivzl not found" in message
    assert "Session pooler" in message


def test_describe_failure_redacts_connection_string() -> None:
    error = psycopg2.OperationalError(
        "could not connect: dsn postgresql://postgres:wip-secret@db.example:5432/postgres"
    )

    message = describe_failure(error)

    assert "wip-secret" not in message
    assert REDACTED in message


def test_describe_failure_redacts_password_parameter() -> None:
    error = psycopg2.OperationalError("connection failed password=hunter2 host=db.example")

    message = describe_failure(error)

    assert "hunter2" not in message
    assert "Session pooler" in message


def test_describe_failure_collapses_whitespace() -> None:
    error = psycopg2.OperationalError("FATAL:\n   too   many\n connections")

    message = describe_failure(error)

    assert "FATAL: too many connections" in message


def test_missing_configuration_names_every_variable() -> None:
    error = missing_configuration("SUPABASE_DB_URL", "SUPABASE_DB_PASSWORD")

    assert "SUPABASE_DB_URL" in str(error)
    assert "SUPABASE_DB_PASSWORD" in str(error)


def test_describe_failure_never_raises_on_empty_message() -> None:
    assert describe_failure(ValueError()) == f" — {CONNECTION_HINT}"
