"""Tests for the Jolpica client and its payload parsers.

The JSON fixtures below are copied from live API responses so that a change in
Jolpica's envelope breaks a test instead of corrupting an ingestion silently.
"""

from __future__ import annotations

import pytest
import requests
from app.data_pipeline import jolpica
from app.data_pipeline.jolpica import (
    JolpicaClient,
    JolpicaError,
    build_season,
    parse_constructors,
    parse_drivers,
    parse_races,
)

RACES_PAYLOAD = {
    "MRData": {
        "series": "f1",
        "total": "22",
        "RaceTable": {
            "season": "2023",
            "Races": [
                {
                    "season": "2023",
                    "round": "1",
                    "url": "https://en.wikipedia.org/wiki/2023_Bahrain_Grand_Prix",
                    "raceName": "Bahrain Grand Prix",
                    "Circuit": {
                        "circuitId": "bahrain",
                        "circuitName": "Bahrain International Circuit",
                        "Location": {"lat": "26.0325", "long": "50.5106"},
                    },
                    "date": "2023-03-05",
                    "time": "15:00:00Z",
                }
            ],
        },
    }
}

DRIVERS_PAYLOAD = {
    "MRData": {
        "DriverTable": {
            "season": "2023",
            "Drivers": [
                {
                    "driverId": "albon",
                    "permanentNumber": "23",
                    "code": "ALB",
                    "givenName": "Alexander",
                    "familyName": "Albon",
                    "nationality": "Thai",
                },
                {
                    "driverId": "paul_aron",
                    "givenName": "Paul",
                    "familyName": "Aron",
                },
            ],
        }
    }
}

CONSTRUCTORS_PAYLOAD = {
    "MRData": {
        "ConstructorTable": {
            "season": "2023",
            "Constructors": [
                {
                    "constructorId": "alfa",
                    "url": "https://en.wikipedia.org/wiki/Alfa_Romeo_in_Formula_One",
                    "name": "Alfa Romeo",
                    "nationality": "Swiss",
                }
            ],
        }
    }
}


class FakeResponse:
    def __init__(self, payload: object, status_error: Exception | None = None) -> None:
        self.payload = payload
        self.status_error = status_error

    def raise_for_status(self) -> None:
        if self.status_error is not None:
            raise self.status_error

    def json(self) -> object:
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class FakeSession:
    """Returns prepared items; plain mappings are wrapped as a 200 response."""

    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get(self, url: str, **kwargs: object) -> object:
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError("aucune réponse préparée")
        item = self.responses.pop(0)
        return FakeResponse(item) if isinstance(item, dict) else item


BASE_URL = "https://api.jolpi.ca/ergast/f1"


def _client(responses: list[object], **kwargs: int | float) -> tuple[JolpicaClient, FakeSession]:
    session = FakeSession(responses)
    client = JolpicaClient(BASE_URL, session, sleep=lambda _s: None, **kwargs)
    return client, session


def test_parse_races_extracts_calendar() -> None:
    rows = parse_races(RACES_PAYLOAD)

    assert len(rows) == 1
    assert rows[0].season == 2023
    assert rows[0].round_number == 1
    assert rows[0].race_key == "bahrain-1"
    assert rows[0].name == "Bahrain Grand Prix"
    assert rows[0].circuit_name == "Bahrain International Circuit"
    assert rows[0].race_date is not None and rows[0].race_date.isoformat() == "2023-03-05"
    assert rows[0].url is not None and "Bahrain" in rows[0].url


def test_parse_races_keeps_two_rounds_on_the_same_circuit_distinct() -> None:
    payload = {
        "MRData": {
            "RaceTable": {
                "Races": [
                    {
                        "season": "2020",
                        "round": "9",
                        "raceName": "Styrian Grand Prix",
                        "Circuit": {"circuitId": "red_bull_ring", "circuitName": "Red Bull Ring"},
                        "date": "2020-10-11",
                    },
                    {
                        "season": "2020",
                        "round": "10",
                        "raceName": "Styrian Grand Prix",
                        "Circuit": {"circuitId": "red_bull_ring", "circuitName": "Red Bull Ring"},
                        "date": "2020-10-18",
                    },
                ]
            }
        }
    }

    rows = parse_races(payload)

    assert [row.race_key for row in rows] == ["red_bull_ring-9", "red_bull_ring-10"]
    assert len({row.race_key for row in rows}) == 2


def test_parse_races_skips_incomplete_entries() -> None:
    payload = {
        "MRData": {
            "RaceTable": {
                "Races": [
                    {"season": "2023", "round": "1", "raceName": "Complete"},
                    {"season": "2023", "round": "not-a-number", "raceName": "Bad round"},
                    {"season": "2023", "round": "2"},
                    "pas un objet",
                ]
            }
        }
    }

    rows = parse_races(payload)

    assert [row.name for row in rows] == ["Complete"]


def test_parse_races_survives_missing_circuit() -> None:
    payload = {
        "MRData": {
            "RaceTable": {"Races": [{"season": "2023", "round": "1", "raceName": "Sans circuit"}]}
        }
    }

    rows = parse_races(payload)

    assert rows[0].race_key == "unknown-1"
    assert rows[0].circuit_name is None
    assert rows[0].race_date is None


def test_parse_drivers_builds_full_name_and_keeps_slug() -> None:
    rows = parse_drivers(DRIVERS_PAYLOAD)

    assert len(rows) == 2
    assert rows[0].source_driver_id == "albon"
    assert rows[0].name == "Alexander Albon"
    assert rows[0].code == "ALB"
    assert rows[0].nationality == "Thai"


def test_parse_drivers_tolerates_reserve_driver_without_code() -> None:
    rows = parse_drivers(DRIVERS_PAYLOAD)

    assert rows[1].source_driver_id == "paul_aron"
    assert rows[1].code is None
    assert rows[1].nationality is None


def test_parse_drivers_preserves_accents() -> None:
    payload = {
        "MRData": {
            "DriverTable": {
                "Drivers": [
                    {
                        "driverId": "perez",
                        "givenName": "Sergio",
                        "familyName": "Pérez",
                        "code": "PER",
                        "nationality": "Mexican",
                    }
                ]
            }
        }
    }

    assert parse_drivers(payload)[0].name == "Sergio Pérez"


def test_parse_constructors_leaves_code_null_because_api_omits_it() -> None:
    rows = parse_constructors(CONSTRUCTORS_PAYLOAD)

    assert rows[0].source_constructor_id == "alfa"
    assert rows[0].name == "Alfa Romeo"
    assert rows[0].code is None
    assert rows[0].nationality == "Swiss"


def test_parsers_return_empty_list_for_missing_table() -> None:
    empty = {"MRData": {"series": "f1"}}

    assert parse_races(empty) == []
    assert parse_drivers(empty) == []
    assert parse_constructors(empty) == []


def test_parsers_reject_payload_without_mrdata_envelope() -> None:
    for parse in (parse_races, parse_drivers, parse_constructors):
        with pytest.raises(JolpicaError, match="MRData"):
            parse({"unexpected": True})


def test_parsers_reject_non_mapping_payload() -> None:
    with pytest.raises(JolpicaError, match="inattendue"):
        parse_drivers(["pas", "un", "objet"])  # type: ignore[arg-type]


def test_build_season_uses_first_race_date() -> None:
    rows = parse_races(RACES_PAYLOAD)

    season = build_season(2023, rows)

    assert season.season == 2023
    assert season.label == "2023"
    assert season.start_date is not None and season.start_date.isoformat() == "2023-03-05"


def test_build_season_handles_empty_calendar() -> None:
    season = build_season(2023, [])

    assert season.start_date is None
    assert season.label == "2023"


def test_client_always_requests_json_and_raises_page_size() -> None:
    client, session = _client([{"MRData": {"RaceTable": {"Races": []}}}])

    client.season_races(2023)

    url, kwargs = session.calls[0]
    assert url == "https://api.jolpi.ca/ergast/f1/2023/races/"
    params = kwargs["params"]
    assert isinstance(params, dict)
    assert params["format"] == "json"
    assert params["limit"] == "100"


def test_client_sets_a_timeout() -> None:
    client, session = _client([{"MRData": {}}])

    client.season_drivers(2023)

    assert session.calls[0][1]["timeout"] == jolpica.REQUEST_TIMEOUT


def test_client_retries_transport_failure_then_succeeds() -> None:
    client, session = _client(
        [
            FakeResponse(None, requests.ConnectionError("réseau coupé")),
            {"MRData": {"DriverTable": {"Drivers": []}}},
        ]
    )

    payload = client.season_drivers(2023)

    assert payload["MRData"]["DriverTable"] == {"Drivers": []}  # type: ignore[index]
    assert len(session.calls) == 2


def test_client_raises_after_exhausting_retries() -> None:
    client, _ = _client(
        [FakeResponse(None, requests.ConnectionError("réseau coupé")) for _ in range(3)],
        retries=3,
    )

    with pytest.raises(JolpicaError, match="3 tentatives"):
        client.season_constructors(2023)


def test_client_does_not_retry_a_deterministic_status_error() -> None:
    session = FakeSession([FakeResponse(None, requests.HTTPError("404 Not Found"))])
    client = JolpicaClient(BASE_URL, session, sleep=lambda _s: None)

    with pytest.raises(JolpicaError, match="refusé"):
        client.season_races(2023)

    assert len(session.calls) == 1


def test_client_reports_unreadable_json() -> None:
    client, _ = _client([FakeResponse(ValueError("pas du JSON"))])

    with pytest.raises(JolpicaError, match="illisible"):
        client.season_races(2023)


def test_client_returns_the_document_so_parsers_validate_the_envelope() -> None:
    client, _ = _client([{"pas": "enveloppe"}])

    payload = client.season_races(2023)

    assert payload == {"pas": "enveloppe"}
    with pytest.raises(JolpicaError, match="MRData"):
        parse_races(payload)  # type: ignore[arg-type]


def test_client_does_not_leak_credentials_in_its_error() -> None:
    secret = "wip-secret"
    failure = requests.ConnectionError(f"postgresql://postgres:{secret}@db.example refused")
    client, _ = _client([FakeResponse(None, failure) for _ in range(3)], retries=3)

    with pytest.raises(JolpicaError) as excinfo:
        client.season_races(2023)

    assert secret not in str(excinfo.value)
