"""Jolpica-F1 client and pure payload parsers for the ingestion.

Jolpica is the free successor to the retired Ergast API. Every endpoint returns
the same ``MRData`` envelope, but each one exposes a differently named result
list: ``Races``, ``Drivers``, ``Constructors``, ``Results``, ``SprintResults``,
``QualifyingResults``. The parsers below are deliberately separate functions
rather than one parameterised helper, so a schema change on one endpoint cannot
silently corrupt another.

Two facts about this API shape the whole design:

- it returns **XML by default**, so ``format=json`` must always be requested;
- it caps ``limit`` at 100, and identifiers (``driverId``, ``constructorId``)
  are slugs, not integers.

The parsers are pure functions over already-decoded JSON, so they are testable
without a network. Only :class:`JolpicaClient` performs I/O.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from datetime import date
from typing import Any, NamedTuple, Protocol

import requests

from app.data_pipeline.errors import describe_failure

PAGE_SIZE = 100
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF = 0.5
REQUEST_TIMEOUT = 30


class HttpSession(Protocol):
    """The subset of ``requests.Session`` this module relies on."""

    def get(self, url: str, **kwargs: object) -> Any: ...


class JolpicaError(RuntimeError):
    """Raised when Jolpica answers with an unusable envelope."""


class RaceRow(NamedTuple):
    season: int
    round_number: int
    race_key: str
    name: str
    circuit_name: str | None
    race_date: date | None
    url: str | None


class SeasonRow(NamedTuple):
    season: int
    label: str
    start_date: date | None


class DriverRow(NamedTuple):
    source_driver_id: str
    name: str
    code: str | None
    nationality: str | None


class ConstructorRow(NamedTuple):
    source_constructor_id: str
    name: str
    code: str | None
    nationality: str | None


def _envelope(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return the ``MRData`` mapping, or explain what came back instead."""
    if not isinstance(payload, Mapping):
        raise JolpicaError(f"Réponse JSON inattendue : {type(payload).__name__}")
    data = payload.get("MRData")
    if not isinstance(data, Mapping):
        raise JolpicaError("Réponse Jolpica sans enveloppe MRData")
    return data


def _rows(payload: Mapping[str, Any], table_key: str, list_key: str) -> list[Mapping[str, Any]]:
    """Return the mapping list at ``MRData.<table_key>.<list_key>``.

    Both keys are passed explicitly: the list name cannot be derived from the
    table name, since ``RaceTable`` holds ``Races`` but a results list may be
    called ``Results``, ``SprintResults`` or ``QualifyingResults``.
    """
    table = _envelope(payload).get(table_key)
    if not isinstance(table, Mapping):
        return []
    rows = table.get(list_key)
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, Mapping)]


def _text(entry: Mapping[str, Any], *keys: str) -> str | None:
    """Read the first present, non-empty string among ``keys``."""
    for key in keys:
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _int(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _full_name(person: Mapping[str, Any]) -> str | None:
    given = _text(person, "givenName")
    family = _text(person, "familyName")
    if given and family:
        return f"{given} {family}"
    return given or family


def parse_races(payload: Mapping[str, Any]) -> list[RaceRow]:
    """Extract the season calendar.

    ``race_key`` combines the circuit identifier with the round because a single
    circuit can host two Grands Prix in one season (2020 ran the Styrian GP
    twice), and the schema requires ``(season, race_key)`` to stay unique.
    """
    rows: list[RaceRow] = []
    for race in _rows(payload, "RaceTable", "Races"):
        if not isinstance(race, Mapping):
            continue
        season = _int(_text(race, "season"))
        round_number = _int(_text(race, "round"))
        name = _text(race, "raceName")
        if season is None or round_number is None or not name:
            continue
        circuit = race.get("Circuit")
        circuit = circuit if isinstance(circuit, Mapping) else {}
        circuit_id = _text(circuit, "circuitId") or "unknown"
        rows.append(
            RaceRow(
                season=season,
                round_number=round_number,
                race_key=f"{circuit_id}-{round_number}",
                name=name,
                circuit_name=_text(circuit, "circuitName"),
                race_date=_iso_date(_text(race, "date")),
                url=_text(race, "url"),
            )
        )
    return rows


def parse_drivers(payload: Mapping[str, Any]) -> list[DriverRow]:
    """Extract drivers, keyed by their Jolpica slug.

    ``code`` is genuinely absent for some entries (reserve drivers), so every
    field is read defensively.
    """
    rows: list[DriverRow] = []
    for driver in _rows(payload, "DriverTable", "Drivers"):
        if not isinstance(driver, Mapping):
            continue
        slug = _text(driver, "driverId")
        name = _full_name(driver)
        if not slug or not name:
            continue
        rows.append(
            DriverRow(
                source_driver_id=slug,
                name=name,
                code=_text(driver, "code"),
                nationality=_text(driver, "nationality"),
            )
        )
    return rows


def parse_constructors(payload: Mapping[str, Any]) -> list[ConstructorRow]:
    """Extract constructors.

    Jolpica exposes no three-letter code for constructors, so ``code`` stays
    NULL rather than being invented from the name.
    """
    rows: list[ConstructorRow] = []
    for constructor in _rows(payload, "ConstructorTable", "Constructors"):
        if not isinstance(constructor, Mapping):
            continue
        slug = _text(constructor, "constructorId")
        name = _text(constructor, "name")
        if not slug or not name:
            continue
        rows.append(
            ConstructorRow(
                source_constructor_id=slug,
                name=name,
                code=None,
                nationality=_text(constructor, "nationality"),
            )
        )
    return rows


def build_season(season: int, races: Sequence[RaceRow]) -> SeasonRow:
    """Derive the season dimension row, using the first race date as a start."""
    dates = [race.race_date for race in races if race.race_date is not None]
    return SeasonRow(season=season, label=str(season), start_date=min(dates) if dates else None)


class JolpicaClient:
    """Thin JSON client over the Jolpica endpoints the pipeline needs."""

    def __init__(
        self,
        base_url: str,
        session: HttpSession | None = None,
        *,
        retries: int = DEFAULT_RETRIES,
        backoff: float = DEFAULT_BACKOFF,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._session = session if session is not None else requests.Session()
        self._retries = retries
        self._backoff = backoff
        self._sleep = sleep

    def get(self, path: str, **params: str) -> Mapping[str, Any]:
        """Fetch one JSON document, retrying transient transport failures.

        The decoded document is returned as-is. Envelope validation belongs to
        the parsers, because each one knows which table it needs.
        """
        url = f"{self._base_url}/{path.lstrip('/')}"
        query = {"format": "json", "limit": str(PAGE_SIZE), **params}
        last: Exception | None = None
        for attempt in range(1, self._retries + 1):
            try:
                response = self._session.get(url, params=query, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
            except requests.HTTPError as exc:
                # A status error is deterministic: retrying it wastes a round trip.
                raise JolpicaError(f"Jolpica a refusé {url} : {exc}") from exc
            except requests.RequestException as exc:
                last = exc
                if attempt == self._retries:
                    break
                self._sleep(self._backoff * attempt)
                continue

            try:
                payload = response.json()
            except ValueError as exc:
                raise JolpicaError(f"Réponse Jolpica illisible depuis {url} : {exc}") from exc
            if not isinstance(payload, Mapping):
                raise JolpicaError(f"Réponse Jolpica illisible depuis {url} : pas un objet JSON")
            return payload

        raise JolpicaError(
            f"Échec de l'appel Jolpica à {url} après {self._retries} tentatives "
            f"({describe_failure(last)})"
        ) from last

    def season_races(self, season: int) -> Mapping[str, Any]:
        return self.get(f"{season}/races/")

    def season_drivers(self, season: int) -> Mapping[str, Any]:
        return self.get(f"{season}/drivers/")

    def season_constructors(self, season: int) -> Mapping[str, Any]:
        return self.get(f"{season}/constructors/")

    def round_results(self, season: int, round_number: int) -> Mapping[str, Any]:
        return self.get(f"{season}/{round_number}/results/")

    def round_sprint(self, season: int, round_number: int) -> Mapping[str, Any]:
        return self.get(f"{season}/{round_number}/sprint/")

    def round_qualifying(self, season: int, round_number: int) -> Mapping[str, Any]:
        return self.get(f"{season}/{round_number}/qualifying/")

    def season_driver_standings(self, season: int) -> Mapping[str, Any]:
        return self.get(f"{season}/driverstandings/")
