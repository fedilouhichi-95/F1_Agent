"""Tests for slug-to-id resolution (no network, no database)."""

from __future__ import annotations

import pytest
from app.data_pipeline import resolve
from app.data_pipeline.jolpica import StagedResult, StagedStanding

REFERENCES = resolve.References(
    driver_ids={"max_verstappen": 1, "perez": 2, "albon": 3},
    constructor_ids={"red_bull": 10, "mercedes": 11},
    race_ids={1: 100, 2: 200},
)


def _result(**overrides: object) -> StagedResult:
    base = {
        "season": 2023,
        "round_number": 1,
        "session_type": "R",
        "driver_slug": "max_verstappen",
        "constructor_slug": "red_bull",
        "driver_number": 1,
        "grid_position": 2,
        "finish_position": 1,
        "points": 25.0,
        "laps": 57,
        "status": "Finished",
        "fastest_lap_rank": 6,
        "q1_ms": None,
        "q2_ms": None,
        "q3_ms": None,
    }
    base.update(overrides)
    return StagedResult(**base)  # type: ignore[arg-type]


def _standing(**overrides: object) -> StagedStanding:
    base = {
        "season": 2023,
        "round_number": 1,
        "driver_slug": "max_verstappen",
        "constructor_slug": "red_bull",
        "driver_number": 1,
        "position": 1,
        "points": 25.0,
        "wins": 1,
    }
    base.update(overrides)
    return StagedStanding(**base)  # type: ignore[arg-type]


def test_load_references_indexes_every_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    queries: list[tuple[str, object]] = []

    def fake_fetch_all(_active, statement, params=()):  # type: ignore[no-untyped-def]
        queries.append((statement, params))
        if "FROM races" in statement:
            return [(1, 100), (2, 200)]
        if "FROM drivers" in statement:
            return [("max_verstappen", 1), (None, 9)]
        return [("red_bull", 10), (None, 9)]

    monkeypatch.setattr(resolve.db, "fetch_all", fake_fetch_all)

    references = resolve.load_references(object(), 2023)  # type: ignore[arg-type]

    assert references.driver_ids == {"max_verstappen": 1}
    assert references.constructor_ids == {"red_bull": 10}
    assert references.race_ids == {1: 100, 2: 200}
    assert ("SELECT round_number, race_id FROM races WHERE season = %s", (2023,)) in queries


def test_resolve_results_substitutes_every_identifier() -> None:
    outcome = resolve.resolve_results([_result()], REFERENCES)

    assert outcome.complete is True
    assert outcome.rows == [
        (2023, "R", 100, 1, 10, 1, 2, 1, 25.0, 57, "Finished", 6, None, None, None)
    ]


def test_resolve_results_keeps_missing_qualifying_times_as_null() -> None:
    outcome = resolve.resolve_results([_result(session_type="Q", q3_ms=89708)], REFERENCES)

    assert outcome.rows[0][12:] == (None, None, 89708)


def test_resolve_results_defaults_absent_points_to_zero() -> None:
    outcome = resolve.resolve_results([_result(points=None)], REFERENCES)

    assert outcome.rows[0][8] == 0


def test_resolve_results_reports_an_unknown_driver() -> None:
    outcome = resolve.resolve_results([_result(driver_slug="inconnu")], REFERENCES)

    assert outcome.complete is False
    assert outcome.unresolved == ("driver:inconnu",)
    assert outcome.rows == []


def test_resolve_results_reports_an_unknown_round() -> None:
    outcome = resolve.resolve_results([_result(round_number=99)], REFERENCES)

    assert outcome.unresolved == ("race:2023/99",)


def test_resolve_results_reports_every_problem_once() -> None:
    staged = [
        _result(driver_slug="inconnu"),
        _result(driver_slug="autre_inconnu"),
        _result(driver_slug="inconnu"),
    ]

    outcome = resolve.resolve_results(staged, REFERENCES)

    assert outcome.unresolved == ("driver:autre_inconnu", "driver:inconnu")


def test_resolve_results_keeps_the_rows_it_can_resolve() -> None:
    staged = [_result(), _result(driver_slug="inconnu")]

    outcome = resolve.resolve_results(staged, REFERENCES)

    assert len(outcome.rows) == 1
    assert outcome.complete is False


def test_resolve_results_treats_a_null_constructor_as_null_id() -> None:
    outcome = resolve.resolve_results([_result(constructor_slug=None)], REFERENCES)

    assert outcome.rows[0][4] is None
    assert outcome.complete is True


def test_resolve_standings_substitutes_every_identifier() -> None:
    outcome = resolve.resolve_standings([_standing()], REFERENCES)

    assert outcome.rows == [(2023, 100, 1, 10, 1, 1, 25.0, 1)]


def test_resolve_standings_reports_an_unknown_driver() -> None:
    outcome = resolve.resolve_standings([_standing(driver_slug="inconnu")], REFERENCES)

    assert outcome.unresolved == ("driver:inconnu",)
    assert outcome.rows == []


def test_raise_if_incomplete_names_the_missing_references() -> None:
    outcome = resolve.resolve_results([_result(driver_slug="inconnu")], REFERENCES)

    with pytest.raises(LookupError) as excinfo:
        outcome.raise_if_incomplete("results")

    message = str(excinfo.value)
    assert "driver:inconnu" in message
    assert "metadata" in message


def test_raise_if_incomplete_returns_rows_when_nothing_is_missing() -> None:
    outcome = resolve.resolve_results([_result()], REFERENCES)

    assert outcome.raise_if_incomplete("results") == outcome.rows


def test_empty_staged_input_resolves_to_nothing() -> None:
    assert resolve.resolve_results([], REFERENCES).rows == []
    assert resolve.resolve_standings([], REFERENCES).rows == []


def test_references_return_none_for_unknown_keys() -> None:
    assert REFERENCES.driver("absent") is None
    assert REFERENCES.constructor("absent") is None
    assert REFERENCES.constructor(None) is None
    assert REFERENCES.race(2023, 42) is None
