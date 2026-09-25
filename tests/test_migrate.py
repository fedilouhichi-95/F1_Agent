"""Tests for the Supabase schema migration runner."""

from __future__ import annotations

import app.data_pipeline.migrate as migrate
import psycopg2
import pytest
from app.config import AppConfig
from app.data_pipeline.migrate import _REDACTED


class FakeCursor:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.executed: str | None = None
        self.closed = False

    def execute(self, statement: str) -> None:
        self.executed = statement
        if self.error is not None:
            raise self.error

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self, error: Exception | None = None) -> None:
        self.cursor_instance = FakeCursor(error)
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self) -> FakeCursor:
        return self.cursor_instance

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


def test_apply_schema_commits_successfully(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeConnection()
    monkeypatch.setattr(migrate.psycopg2, "connect", lambda *_args, **_kwargs: connection)
    config = AppConfig.from_mapping(
        {
            "SUPABASE_DB_URL": "postgresql://db.example",
            "SUPABASE_DB_PASSWORD": "db-password",
        }
    )

    migrate.apply_schema(config)

    assert "CREATE TABLE IF NOT EXISTS" in (connection.cursor_instance.executed or "")
    assert connection.committed is True
    assert connection.closed is True
    assert connection.rolled_back is False


def test_apply_schema_rolls_back_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeConnection(RuntimeError("schema failure"))
    monkeypatch.setattr(migrate.psycopg2, "connect", lambda *_args, **_kwargs: connection)
    config = AppConfig.from_mapping(
        {
            "SUPABASE_DB_URL": "postgresql://db.example",
            "SUPABASE_DB_PASSWORD": "db-password",
        }
    )

    with pytest.raises(RuntimeError, match="schema failure"):
        migrate.apply_schema(config)

    assert connection.rolled_back is True
    assert connection.closed is True
    assert connection.committed is False


def test_apply_schema_requires_database_url() -> None:
    with pytest.raises(ValueError, match="SUPABASE_DB_URL"):
        migrate.apply_schema(AppConfig.from_mapping({}))


def test_describe_failure_keeps_postgres_reason() -> None:
    error = psycopg2.OperationalError(
        'connection to server at "aws-0-eu-west-1.pooler.supabase.com" (10.0.0.1), '
        "port 5432 failed: FATAL: (ENOTFOUND) tenant/user "
        "postgres.wsmohvwhcovsylwpivzl not found"
    )

    message = migrate.describe_failure(error)

    assert "tenant/user postgres.wsmohvwhcovsylwpivzl not found" in message
    assert "Session pooler" in message


def test_describe_failure_redacts_connection_string() -> None:
    error = psycopg2.OperationalError(
        "could not connect: dsn postgresql://postgres:wip-secret@db.example:5432/postgres"
    )

    message = migrate.describe_failure(error)

    assert "wip-secret" not in message
    assert _REDACTED in message


def test_main_exits_with_diagnostic(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(_config: AppConfig) -> None:
        raise psycopg2.OperationalError(
            "FATAL: tenant/user postgres.wsmohvwhcovsylwpivzl not found"
        )

    monkeypatch.setattr(migrate, "apply_schema", explode)

    with pytest.raises(SystemExit) as excinfo:
        migrate.main()

    assert "tenant/user postgres.wsmohvwhcovsylwpivzl not found" in str(excinfo.value)
    assert "wip-secret" not in str(excinfo.value)
