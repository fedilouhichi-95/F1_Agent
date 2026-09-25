"""Tests for the ingestion CLI orchestration (no network, no database)."""

from __future__ import annotations

import psycopg2
import pytest
from app.config import AppConfig
from app.data_pipeline import ingest
from app.data_pipeline import resolve as ingest_resolve

RACES_PAYLOAD = {
    "MRData": {
        "RaceTable": {
            "Races": [
                {
                    "season": "2023",
                    "round": "1",
                    "raceName": "Bahrain Grand Prix",
                    "Circuit": {"circuitId": "bahrain", "circuitName": "Bahrain International"},
                    "date": "2023-03-05",
                },
                {
                    "season": "2023",
                    "round": "2",
                    "raceName": "Saudi Arabian Grand Prix",
                    "Circuit": {"circuitId": "jeddah", "circuitName": "Jeddah Corniche"},
                    "date": "2023-03-19",
                },
            ]
        }
    }
}

DRIVERS_PAYLOAD = {
    "MRData": {
        "DriverTable": {
            "Drivers": [
                {
                    "driverId": "albon",
                    "givenName": "Alexander",
                    "familyName": "Albon",
                    "code": "ALB",
                    "nationality": "Thai",
                },
                {
                    "driverId": "verstappen",
                    "givenName": "Max",
                    "familyName": "Verstappen",
                    "code": "VER",
                    "nationality": "Dutch",
                },
            ]
        }
    }
}

CONSTRUCTORS_PAYLOAD = {
    "MRData": {
        "ConstructorTable": {
            "Constructors": [
                {"constructorId": "alfa", "name": "Alfa Romeo", "nationality": "Swiss"}
            ]
        }
    }
}

EMPTY_PAYLOAD = {"MRData": {"series": "f1"}}


class FakeJolpica:
    def __init__(self, base_url: str = "", **kwargs: object) -> None:
        self.base_url = base_url
        self.kwargs = kwargs
        self.calls: list[str] = []

    def season_races(self, season: int) -> dict:
        self.calls.append(f"races:{season}")
        return RACES_PAYLOAD

    def season_drivers(self, season: int) -> dict:
        self.calls.append(f"drivers:{season}")
        return DRIVERS_PAYLOAD

    def season_constructors(self, season: int) -> dict:
        self.calls.append(f"constructors:{season}")
        return CONSTRUCTORS_PAYLOAD


class FakeCursor:
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


class FakeConnection:
    def __init__(self, rows: list[tuple[object, ...]] | None = None) -> None:
        self.cursor_instance = FakeCursor(rows or [(7,)])
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self) -> FakeCursor:
        return self.cursor_instance

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


def _record_upserts(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []

    def fake_upsert(
        _active: object,
        *,
        table: str,
        columns: object,
        rows: object,
        conflict: object,
        **_kwargs: object,
    ) -> int:
        calls.append(
            {
                "table": table,
                "columns": tuple(columns),
                "rows": rows,
                "conflict": tuple(conflict),
            }
        )
        return len(rows)

    monkeypatch.setattr(ingest.db, "upsert", fake_upsert)
    return calls


def _patch_client(
    monkeypatch: pytest.MonkeyPatch, factory: type[FakeJolpica] = FakeJolpica
) -> None:
    monkeypatch.setattr(ingest, "JolpicaClient", factory)


def test_parse_seasons_reads_a_comma_list() -> None:
    assert ingest.parse_seasons("2019, 2020 ,2023") == [2019, 2020, 2023]


def test_parse_seasons_rejects_non_numeric() -> None:
    with pytest.raises(ValueError, match="Saison invalide"):
        ingest.parse_seasons("2023,dernier")


def test_parse_seasons_rejects_year_the_schema_would_refuse() -> None:
    with pytest.raises(ValueError, match="antérieure"):
        ingest.parse_seasons("1949")


def test_parse_seasons_reports_missing_setting() -> None:
    with pytest.raises(ValueError, match="INGEST_SEASONS"):
        ingest.parse_seasons("  ,  ")


def test_fetch_metadata_parses_every_table() -> None:
    client = FakeJolpica()

    tables = ingest.fetch_metadata(client, 2023)

    assert set(tables) == {"seasons", "drivers", "constructors", "races"}
    assert len(tables["races"]) == 2
    assert len(tables["drivers"]) == 2
    assert len(tables["constructors"]) == 1
    assert client.calls == ["races:2023", "drivers:2023", "constructors:2023"]


def test_fetch_metadata_builds_the_season_from_the_first_race() -> None:
    tables = ingest.fetch_metadata(FakeJolpica(), 2023)

    assert tables["seasons"][0][0] == 2023
    assert str(tables["seasons"][0][2]) == "2023-03-05"


def test_fetch_metadata_refuses_an_empty_calendar() -> None:
    class EmptyCalendar(FakeJolpica):
        def season_races(self, season: int) -> dict:
            return EMPTY_PAYLOAD

    with pytest.raises(ValueError, match="Aucun grand prix"):
        ingest.fetch_metadata(EmptyCalendar(), 2023)


def test_write_metadata_respects_foreign_key_order(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _record_upserts(monkeypatch)
    tables = ingest.fetch_metadata(FakeJolpica(), 2023)

    ingest.write_metadata(FakeConnection(), tables)

    assert [call["table"] for call in calls] == [
        "seasons",
        "drivers",
        "constructors",
        "races",
    ]


def test_write_metadata_targets_the_source_slug_as_conflict_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _record_upserts(monkeypatch)
    tables = ingest.fetch_metadata(FakeJolpica(), 2023)

    ingest.write_metadata(FakeConnection(), tables)

    by_table = {call["table"]: call for call in calls}
    assert by_table["drivers"]["conflict"] == ("source_driver_id",)
    assert by_table["constructors"]["conflict"] == ("source_constructor_id",)
    assert by_table["races"]["conflict"] == ("season", "round_number")
    assert by_table["races"]["columns"] == ingest.RACE_COLUMNS


def test_write_metadata_uses_one_transaction_per_table(monkeypatch: pytest.MonkeyPatch) -> None:
    _record_upserts(monkeypatch)
    connection = FakeConnection()
    tables = ingest.fetch_metadata(FakeJolpica(), 2023)

    ingest.write_metadata(connection, tables)

    assert connection.commits == 4
    assert connection.rollbacks == 0


def test_write_metadata_rolls_back_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeConnection()
    tables = ingest.fetch_metadata(FakeJolpica(), 2023)

    def explode(*_args: object, **_kwargs: object) -> int:
        raise psycopg2.DataError("violation de contrainte")

    monkeypatch.setattr(ingest.db, "upsert", explode)

    with pytest.raises(psycopg2.DataError):
        ingest.write_metadata(connection, tables)

    assert connection.rollbacks == 1
    assert connection.commits == 0


def test_write_metadata_dry_run_never_touches_the_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _record_upserts(monkeypatch)
    connection = FakeConnection()
    tables = ingest.fetch_metadata(FakeJolpica(), 2023)

    written = ingest.write_metadata(connection, tables, dry_run=True)

    assert calls == []
    assert connection.commits == 0
    assert written == {"seasons": 1, "drivers": 2, "constructors": 1, "races": 2}


def test_ingest_without_connection_only_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _record_upserts(monkeypatch)

    written = ingest.ingest_season_metadata(FakeJolpica(), 2023)

    assert calls == []
    assert written == {"seasons": 1, "drivers": 2, "constructors": 1, "races": 2}


def test_count_rows_filters_only_tables_that_carry_a_season(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[str, object]] = []

    def fake_fetch_all(_active: object, statement: str, params: object = ()) -> list:
        seen.append((statement, params))
        return [(5,)]

    monkeypatch.setattr(ingest.db, "fetch_all", fake_fetch_all)

    counts = dict(ingest.count_rows(FakeConnection(), 2023).rows)

    assert counts == {"seasons": 5, "drivers": 5, "constructors": 5, "races": 5}
    assert ("SELECT count(*) FROM drivers", ()) in seen
    assert ("SELECT count(*) FROM races WHERE season = %s", (2023,)) in seen


def test_count_rows_handles_a_table_that_is_still_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ingest.db, "fetch_all", lambda *_a, **_k: [])

    counts = dict(ingest.count_rows(FakeConnection(), 2023).rows)

    assert set(counts.values()) == {0}


def test_count_rows_renders_a_table() -> None:
    counts = ingest.SeasonCounts(rows=(("races", 22), ("drivers", 20)))

    assert counts.render() == "  races               22\n  drivers             20"


def test_main_status_connects_and_prints(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    connection = FakeConnection()
    monkeypatch.setattr(ingest.db, "connect", lambda _config: connection)
    _patch_client(monkeypatch)
    monkeypatch.setattr(ingest, "count_rows", lambda _c, _s: ingest.SeasonCounts((("races", 22),)))

    code = ingest.main(["status", "--season", "2023"])

    assert code == 0
    assert "Saison 2023" in capsys.readouterr().out
    assert connection.closed is True


def test_main_status_reports_a_connection_failure_without_leaking(
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    secret = "wip-secret"

    def refuse(_config: AppConfig) -> object:
        raise psycopg2.OperationalError(f"password authentication failed, password={secret}")

    monkeypatch.setattr(ingest.db, "connect", refuse)
    _patch_client(monkeypatch)

    code = ingest.main(["status", "--season", "2023"])

    captured = capsys.readouterr()
    assert code == 1
    assert "Connexion impossible" in captured.err
    assert secret not in captured.err


def test_main_metadata_dry_run_does_not_connect(
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    def refuse(_config: AppConfig) -> object:
        raise AssertionError("aucune connexion ne doit être ouverte en simulation")

    monkeypatch.setattr(ingest.db, "connect", refuse)
    _patch_client(monkeypatch)

    code = ingest.main(["metadata", "--season", "2023", "--dry-run"])

    assert code == 0
    out = capsys.readouterr().out
    assert "simulation" in out
    assert "races" in out


def test_main_metadata_writes_and_closes_the_connection(
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    connection = FakeConnection()
    monkeypatch.setattr(ingest.db, "connect", lambda _config: connection)
    _patch_client(monkeypatch)
    _record_upserts(monkeypatch)

    code = ingest.main(["metadata", "--season", "2023"])

    assert code == 0
    assert connection.closed is True
    assert "Saison 2023" in capsys.readouterr().out


def test_main_rejects_an_invalid_season(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(monkeypatch)

    code = ingest.main(["metadata", "--season", "pas-une-saison"])

    assert code == 2


def test_main_falls_back_to_configured_seasons(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeConnection()
    monkeypatch.setattr(ingest.db, "connect", lambda _config: connection)
    _patch_client(monkeypatch)
    _record_upserts(monkeypatch)
    monkeypatch.setenv("INGEST_SEASONS", "2022,2023")

    assert ingest.main(["metadata"]) == 0
    assert connection.commits == 8


RESULTS_PAYLOAD = {
    "MRData": {
        "RaceTable": {
            "Races": [
                {
                    "season": "2023",
                    "round": "1",
                    "raceName": "Bahrain Grand Prix",
                    "Results": [
                        {
                            "number": "1",
                            "position": "1",
                            "points": "25",
                            "grid": "1",
                            "laps": "57",
                            "status": "Finished",
                            "Driver": {
                                "driverId": "max_verstappen",
                                "permanentNumber": "3",
                                "code": "VER",
                            },
                            "Constructor": {"constructorId": "red_bull", "name": "Red Bull"},
                            "FastestLap": {"rank": "6", "lap": "44"},
                        }
                    ],
                    "SprintResults": [],
                    "QualifyingResults": [],
                }
            ]
        }
    }
}

STANDINGS_LIST_PAYLOAD = {
    "MRData": {
        "StandingsTable": {
            "StandingsLists": [
                {
                    "season": "2023",
                    "round": "1",
                    "DriverStandings": [
                        {
                            "position": "1",
                            "points": "25",
                            "wins": "1",
                            "Driver": {
                                "driverId": "max_verstappen",
                                "permanentNumber": "3",
                                "code": "VER",
                            },
                            "Constructors": [{"constructorId": "red_bull", "name": "Red Bull"}],
                        }
                    ],
                }
            ]
        }
    }
}


class ResultsJolpica(FakeJolpica):
    def round_results(self, season: int, round_number: int) -> dict:
        self.calls.append(f"results:{season}/{round_number}")
        return RESULTS_PAYLOAD

    def round_sprint(self, season: int, round_number: int) -> dict:
        self.calls.append(f"sprint:{season}/{round_number}")
        return RESULTS_PAYLOAD

    def round_qualifying(self, season: int, round_number: int) -> dict:
        self.calls.append(f"qualifying:{season}/{round_number}")
        return RESULTS_PAYLOAD

    def round_driver_standings(self, season: int, round_number: int) -> dict:
        self.calls.append(f"standings:{season}/{round_number}")
        return STANDINGS_LIST_PAYLOAD


def test_sessions_normalises_and_deduplicates() -> None:
    assert ingest._sessions("rsq") == ["R", "S", "Q"]
    assert ingest._sessions(" R , R ") == ["R"]


def test_sessions_rejects_an_unknown_letter() -> None:
    with pytest.raises(ValueError, match="inconnu"):
        ingest._sessions("RX")


def test_sessions_rejects_an_empty_selection() -> None:
    with pytest.raises(ValueError, match="Aucun type"):
        ingest._sessions(" , ")


def test_fetch_results_only_requests_the_selected_sessions() -> None:
    client = ResultsJolpica()

    staged = ingest.fetch_results(client, 2023, [1], ["R"])

    assert [item.session_type for item in staged] == ["R"]
    assert client.calls == ["results:2023/1"]


def test_fetch_standings_asks_for_every_round() -> None:
    client = ResultsJolpica()

    staged = ingest.fetch_standings(client, 2023, [1, 2, 3])

    assert len(staged) == 3
    assert client.calls == ["standings:2023/1", "standings:2023/2", "standings:2023/3"]


def test_main_results_dry_run_never_connects(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    def refuse(_config: AppConfig) -> object:
        raise AssertionError("aucune connexion ne doit être ouverte en simulation")

    monkeypatch.setattr(ingest.db, "connect", refuse)
    _patch_client(monkeypatch, ResultsJolpica)

    code = ingest.main(
        ["results", "--season", "2023", "--round", "1", "--session", "R", "--dry-run"]
    )

    assert code == 0
    out = capsys.readouterr().out
    assert "simulation" in out
    assert "results" in out
    assert "dont R" in out


def test_main_results_dry_run_can_skip_standings(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(ingest.db, "connect", lambda _config: FakeConnection())
    _patch_client(monkeypatch, ResultsJolpica)

    code = ingest.main(
        ["results", "--season", "2023", "--round", "1", "--skip-standings", "--dry-run"]
    )

    assert code == 0
    assert "standings" not in capsys.readouterr().out


def test_main_results_writes_when_references_resolve(
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    connection = FakeConnection()
    calls = _record_upserts(monkeypatch)
    monkeypatch.setattr(ingest.db, "connect", lambda _config: connection)
    monkeypatch.setattr(
        ingest,
        "load_references",
        lambda _c, _s: ingest_resolve.References(
            driver_ids={"max_verstappen": 1},
            constructor_ids={"red_bull": 10},
            race_ids={1: 100},
        ),
    )
    _patch_client(monkeypatch, ResultsJolpica)

    code = ingest.main(["results", "--season", "2023", "--round", "1", "--session", "R"])

    assert code == 0
    assert [call["table"] for call in calls] == ["results", "standings"]
    assert calls[0]["conflict"] == ("season", "session_type", "race_id", "driver_id")
    assert calls[0]["rows"][0][:5] == (2023, "R", 100, 1, 10)
    assert connection.closed is True
    assert "Saison 2023" in capsys.readouterr().out


def test_main_results_aborts_and_names_the_missing_references(
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    _record_upserts(monkeypatch)
    monkeypatch.setattr(ingest.db, "connect", lambda _config: FakeConnection())
    monkeypatch.setattr(
        ingest,
        "load_references",
        lambda _c, _s: ingest_resolve.References(driver_ids={}, race_ids={}),
    )
    _patch_client(monkeypatch, ResultsJolpica)

    code = ingest.main(["results", "--season", "2023", "--round", "1", "--session", "R"])

    captured = capsys.readouterr()
    assert code == 1
    assert "driver:max_verstappen" in captured.err
    assert "race:2023/1" in captured.err
    assert "Ingestion interrompue" in captured.err


def test_main_results_rejects_an_unknown_session(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(monkeypatch, ResultsJolpica)

    code = ingest.main(["results", "--season", "2023", "--session", "X"])

    assert code == 2


def test_sessions_accepts_the_comma_separated_form() -> None:
    assert ingest._sessions("R, S, Q") == ["R", "S", "Q"]
    assert ingest._sessions("r,s") == ["R", "S"]
