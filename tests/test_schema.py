"""Contract tests for the Supabase schema file."""

from __future__ import annotations

import re
from pathlib import Path

SCHEMA_PATH = Path(__file__).parents[1] / "app" / "data_pipeline" / "schema.sql"
TABLE_PATTERN = re.compile(r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\n\);", re.DOTALL)


def _schema_text() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


def _table_blocks() -> dict[str, str]:
    return {name: body for name, body in TABLE_PATTERN.findall(_schema_text())}


def test_schema_declares_all_expected_tables() -> None:
    expected = {
        "seasons",
        "drivers",
        "constructors",
        "races",
        "results",
        "standings",
        "laps",
        "pit_stops",
        "tire_stints",
        "logs",
    }
    assert expected <= _table_blocks().keys()


def test_fact_tables_carry_season_and_race_constraints() -> None:
    blocks = _table_blocks()
    for table in ("results", "standings", "laps", "pit_stops", "tire_stints"):
        body = blocks[table]
        assert "season" in body
        assert "FOREIGN KEY (race_id, season)" in body
        assert "UNIQUE" in body
    assert "REFERENCES seasons" in blocks["races"]
    assert "UNIQUE" in blocks["races"]


def test_identity_tables_do_not_duplicate_seasons() -> None:
    blocks = _table_blocks()
    assert "season" not in blocks["drivers"]
    assert "season" not in blocks["constructors"]
    assert "logs" in blocks


def test_schema_enables_rls_and_protects_logs() -> None:
    schema = _schema_text()
    assert schema.count("ENABLE ROW LEVEL SECURITY") == 10
    assert schema.count("CREATE POLICY") == 9
    assert "REVOKE ALL ON TABLE public.logs FROM anon, authenticated;" in schema
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE" in schema


def test_schema_is_idempotent_and_contains_no_secrets() -> None:
    schema = _schema_text()
    assert schema.count("CREATE TABLE IF NOT EXISTS") == 10
    assert schema.count("CREATE INDEX IF NOT EXISTS") >= 8
    assert schema.count("DROP POLICY IF EXISTS") == 9
    assert "gsk_" not in schema
    assert "PRIVATE KEY" not in schema
    assert "eyJ" not in schema
