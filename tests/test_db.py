"""Tests for the idempotent Supabase write layer."""

from __future__ import annotations

import psycopg2
import pytest
from app.config import AppConfig
from app.data_pipeline import db


class RecordingCursor:
    def __init__(self, rows: list[tuple[object, ...]] | None = None) -> None:
        self.rows = rows or []
        self.executed: list[tuple[str, object]] = []
        self.closed = False

    def execute(self, statement: str, params: object = None) -> None:
        self.executed.append((statement, params))

    def fetchall(self) -> list[tuple[object, ...]]:
        return list(self.rows)

    def close(self) -> None:
        self.closed = True


class RecordingConnection:
    def __init__(self, rows: list[tuple[object, ...]] | None = None) -> None:
        self.cursor_instance = RecordingCursor(rows)
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self) -> RecordingCursor:
        return self.cursor_instance

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


def _config() -> AppConfig:
    return AppConfig.from_mapping(
        {
            "SUPABASE_DB_URL": "postgresql://db.example",
            "SUPABASE_DB_PASSWORD": "db-password",
        }
    )


def _capture_batches(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, object, int]]:
    batches: list[tuple[str, object, int]] = []

    def fake_execute_values(cursor, statement, rows, page_size):  # type: ignore[no-untyped-def]
        batches.append((statement, rows, page_size))

    monkeypatch.setattr(db, "execute_values", fake_execute_values)
    return batches


def test_connect_requires_database_url() -> None:
    with pytest.raises(ValueError, match="SUPABASE_DB_URL"):
        db.connect(AppConfig.from_mapping({}))


def test_connect_passes_password_separately(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_connect(dsn: str, **kwargs: object) -> RecordingConnection:
        captured["dsn"] = dsn
        captured.update(kwargs)
        return RecordingConnection()

    monkeypatch.setattr(db.psycopg2, "connect", fake_connect)

    db.connect(_config())

    assert captured["dsn"] == "postgresql://db.example"
    assert captured["password"] == "db-password"
    assert captured["connect_timeout"] == db.CONNECT_TIMEOUT


def test_transaction_commits_on_success() -> None:
    connection = RecordingConnection()

    with db.transaction(connection):
        pass

    assert connection.commits == 1
    assert connection.rollbacks == 0


def test_transaction_rolls_back_and_reraises() -> None:
    connection = RecordingConnection()

    with pytest.raises(RuntimeError, match="boom"), db.transaction(connection):
        raise RuntimeError("boom")

    assert connection.rollbacks == 1
    assert connection.commits == 0


def test_transaction_does_not_close_the_connection() -> None:
    connection = RecordingConnection()

    with db.transaction(connection):
        pass

    assert connection.closed is False


def test_quote_rejects_identifier_with_quote_character() -> None:
    with pytest.raises(ValueError, match="Identifiant SQL invalide"):
        db.quote('name"; DROP TABLE results; --')


def test_quote_rejects_uppercase_and_leading_digit() -> None:
    for invalid in ("Name", "1name", "na-me", "na me", ""):
        with pytest.raises(ValueError, match="Identifiant SQL invalide"):
            db.quote(invalid)


def test_build_upsert_statement_uses_conflict_target() -> None:
    statement = db.build_upsert_statement(
        table="drivers",
        columns=("source_driver_id", "name", "code"),
        conflict=("source_driver_id",),
        update_columns=("name", "code"),
    )

    assert statement == (
        'INSERT INTO "drivers" ("source_driver_id", "name", "code") VALUES %s '
        'ON CONFLICT ("source_driver_id") DO UPDATE SET '
        '"name" = EXCLUDED."name", "code" = EXCLUDED."code"'
    )


def test_build_upsert_statement_supports_composite_conflict() -> None:
    statement = db.build_upsert_statement(
        table="results",
        columns=("season", "session_type", "race_id", "driver_id", "points"),
        conflict=("season", "session_type", "race_id", "driver_id"),
        update_columns=("points",),
    )

    assert 'ON CONFLICT ("season", "session_type", "race_id", "driver_id")' in statement
    assert '"points" = EXCLUDED."points"' in statement


def test_build_upsert_statement_rejects_empty_update_set() -> None:
    with pytest.raises(ValueError, match="aucun effet"):
        db.build_upsert_statement(
            table="seasons",
            columns=("season",),
            conflict=("season",),
            update_columns=(),
        )


def test_upsert_skips_empty_rows_without_executing(monkeypatch: pytest.MonkeyPatch) -> None:
    batches = _capture_batches(monkeypatch)
    connection = RecordingConnection()

    written = db.upsert(
        connection,
        table="seasons",
        columns=("season", "label"),
        rows=[],
        conflict=("season",),
    )

    assert written == 0
    assert batches == []
    assert connection.cursor_instance.executed == []


def test_upsert_writes_rows_and_closes_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    batches = _capture_batches(monkeypatch)
    connection = RecordingConnection()
    rows = [("hamilton", "Lewis Hamilton", "HAM"), ("verstappen", "Max Verstappen", "VER")]

    written = db.upsert(
        connection,
        table="drivers",
        columns=("source_driver_id", "name", "code"),
        rows=rows,
        conflict=("source_driver_id",),
        update_columns=("name", "code"),
    )

    assert written == 2
    assert len(batches) == 1
    statement, forwarded, page_size = batches[0]
    assert 'ON CONFLICT ("source_driver_id")' in statement
    assert forwarded is rows
    assert page_size == db.DEFAULT_PAGE_SIZE
    assert connection.cursor_instance.closed is True


def test_upsert_defaults_to_updating_every_non_key_column(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batches = _capture_batches(monkeypatch)

    db.upsert(
        RecordingConnection(),
        table="results",
        columns=("season", "session_type", "race_id", "driver_id", "points"),
        rows=[(2023, "R", 1, 7, 25)],
        conflict=("season", "session_type", "race_id", "driver_id"),
    )

    statement = batches[0][0]
    assert '"points" = EXCLUDED."points"' in statement
    assert '"driver_id" = EXCLUDED."driver_id"' not in statement
    assert '"season" = EXCLUDED."season"' not in statement


def test_upsert_rejects_conflict_column_absent_from_insert() -> None:
    with pytest.raises(ValueError, match="source_driver_id"):
        db.upsert(
            RecordingConnection(),
            table="drivers",
            columns=("name", "code"),
            rows=[("Lewis Hamilton", "HAM")],
            conflict=("source_driver_id",),
        )


def test_upsert_rejects_injected_table_name(monkeypatch: pytest.MonkeyPatch) -> None:
    batches = _capture_batches(monkeypatch)

    with pytest.raises(ValueError, match="Identifiant SQL invalide"):
        db.upsert(
            RecordingConnection(),
            table="drivers; DROP TABLE results",
            columns=("name", "code"),
            rows=[("Lewis Hamilton", "HAM")],
            conflict=("name",),
            update_columns=("code",),
        )

    assert batches == []


def test_upsert_closes_cursor_even_when_execute_values_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(cursor, statement, rows, page_size):  # type: ignore[no-untyped-def]
        raise psycopg2.DataError("invalid input syntax")

    monkeypatch.setattr(db, "execute_values", explode)
    connection = RecordingConnection()

    with pytest.raises(psycopg2.DataError):
        db.upsert(
            connection,
            table="seasons",
            columns=("season", "label"),
            rows=[(2023, "2023")],
            conflict=("season",),
            update_columns=("label",),
        )

    assert connection.cursor_instance.closed is True


def test_fetch_all_returns_rows_and_closes_cursor() -> None:
    connection = RecordingConnection([(1, "a"), (2, "b")])

    rows = db.fetch_all(connection, "SELECT id, name FROM drivers")

    assert rows == [(1, "a"), (2, "b")]
    assert connection.cursor_instance.executed[0][0] == "SELECT id, name FROM drivers"
    assert connection.cursor_instance.closed is True


def test_fetch_all_passes_params_through() -> None:
    connection = RecordingConnection()

    db.fetch_all(connection, "SELECT 1 WHERE season = %s", (2023,))

    assert connection.cursor_instance.executed[0][1] == (2023,)


def test_fetch_one_returns_first_row() -> None:
    assert db.fetch_one(RecordingConnection([(7, "HAM")]), "SELECT 1") == (7, "HAM")


def test_fetch_one_returns_none_when_empty() -> None:
    assert db.fetch_one(RecordingConnection([]), "SELECT 1") is None
