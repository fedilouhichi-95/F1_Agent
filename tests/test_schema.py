"""Contract tests for the Supabase schema file."""

from __future__ import annotations

import re
from pathlib import Path

SCHEMA_PATH = Path(__file__).parents[1] / "app" / "data_pipeline" / "schema.sql"
TABLE_PATTERN = re.compile(r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\n\);", re.DOTALL)


def _schema_text() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


def _squeeze(text: str) -> str:
    """Collapse runs of spaces so assertions survive column alignment."""
    return " ".join(text.split())


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
    for table in ("results", "laps", "pit_stops", "tire_stints"):
        body = blocks[table]
        assert "season" in body
        assert "FOREIGN KEY (race_id, season)" in body
    assert "UNIQUE" in blocks["standings"]
    assert "REFERENCES seasons" in blocks["races"]
    assert "UNIQUE" in blocks["races"]


def test_identity_tables_do_not_duplicate_seasons() -> None:
    blocks = _table_blocks()
    assert "season" not in blocks["drivers"]
    assert "season" not in blocks["constructors"]
    assert "logs" in blocks


def test_identity_tables_expose_source_ids() -> None:
    blocks = _table_blocks()
    assert "source_driver_id" in blocks["drivers"]
    assert "source_constructor_id" in blocks["constructors"]
    assert "session_type" not in blocks["drivers"]
    assert "session_type" not in blocks["constructors"]


def test_session_aware_tables_declare_session_type() -> None:
    blocks = _table_blocks()
    for table in ("results", "laps", "pit_stops", "tire_stints"):
        assert "session_type TEXT NOT NULL DEFAULT 'R'" in _squeeze(blocks[table])
    assert "session_type" not in blocks["standings"]
    assert "session_type" not in blocks["races"]


def test_results_carry_qualifying_times() -> None:
    body = _table_blocks()["results"]
    for column in ("q1_ms", "q2_ms", "q3_ms"):
        assert column in body


def test_unique_keys_include_session_type() -> None:
    schema = _schema_text()
    expected = {
        "idx_results_session_driver_key": "ON results (season, session_type, race_id, driver_id)",
        "idx_laps_session_driver_lap_key": (
            "ON laps (season, session_type, race_id, driver_id, lap_number)"
        ),
        "idx_pit_stops_session_lap_stop_key": (
            "ON pit_stops (season, session_type, race_id, driver_id, lap_number, stop_number)"
        ),
        "idx_tire_stints_session_stint_key": (
            "ON tire_stints (season, session_type, race_id, driver_id, stint_number)"
        ),
    }
    for index_name, definition in expected.items():
        assert f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name}" in schema
        assert definition in schema


def test_evolution_block_retires_pre_session_type_keys() -> None:
    schema = _schema_text()
    retired = {
        "results": "results_race_driver_key",
        "laps": "laps_race_driver_lap_key",
        "pit_stops": "pit_stops_race_driver_lap_stop_key",
        "tire_stints": "tire_stints_race_driver_stint_key",
    }
    for table, constraint in retired.items():
        assert f"ALTER TABLE public.{table} DROP CONSTRAINT IF EXISTS {constraint};" in _squeeze(
            schema
        )
    for table in retired:
        assert (
            f"ADD CONSTRAINT {table}_session_type_check CHECK (session_type IN ('R','S','Q'))"
            in schema
        )


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
    assert "ADD COLUMN IF NOT EXISTS source_driver_id" in schema
    assert "ADD COLUMN IF NOT EXISTS session_type" in schema
    assert "gsk_" not in schema
    assert "PRIVATE KEY" not in schema
    assert "eyJ" not in schema
