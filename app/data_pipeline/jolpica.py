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


class StagedResult(NamedTuple):
    """A result line still keyed by Jolpica slugs, before resolution to ids."""

    season: int
    round_number: int
    session_type: str
    driver_slug: str
    constructor_slug: str | None
    driver_number: int | None
    grid_position: int | None
    finish_position: int | None
    points: float | None
    laps: int | None
    status: str | None
    fastest_lap_rank: int | None
    q1_ms: int | None
    q2_ms: int | None
    q3_ms: int | None


class StagedStanding(NamedTuple):
    season: int
    round_number: int
    driver_slug: str
    constructor_slug: str | None
    driver_number: int | None
    position: int
    points: float
    wins: int


RACE = "R"
SPRINT = "S"
QUALIFYING = "Q"


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


def _mapping_list(value: object) -> list[Mapping[str, Any]]:
    """Keep only the mapping entries of a list field."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _rounds(
    payload: Mapping[str, Any], list_key: str
) -> list[tuple[int, int, list[Mapping[str, Any]]]]:
    """Return ``(season, round, entries)`` for each race carrying ``list_key``.

    Round-scoped endpoints nest their result list inside ``RaceTable.Races``,
    and the round number lives on that race, not on the result itself.
    """
    rounds: list[tuple[int, int, list[Mapping[str, Any]]]] = []
    for race in _rows(payload, "RaceTable", "Races"):
        season = _int(_text(race, "season"))
        round_number = _int(_text(race, "round"))
        if season is None or round_number is None:
            continue
        rounds.append((season, round_number, _mapping_list(race.get(list_key))))
    return rounds


def parse_time_ms(raw: str | None) -> int | None:
    """Convert a Jolpica duration such as ``1:29.708`` into milliseconds.

    Accepts ``M:SS``, ``M:SS.m`` and ``M:SS.mmm``; anything else yields None
    rather than a wrong number.
    """
    if not raw:
        return None
    parts = raw.strip().split(":")
    if len(parts) not in (2, 3):
        return None
    tail = parts[-1]
    head = parts[:-1]
    if not tail:
        return None
    whole, dot, fraction = tail.partition(".")
    if dot and not whole:
        return None
    fraction = (fraction + "000")[:3]
    try:
        seconds = int(whole)
        if len(head) == 1:
            minutes = int(head[0])
        else:
            minutes = 60 * int(head[0]) + int(head[1])
        milliseconds = int(fraction) if dot else 0
    except ValueError:
        return None
    if seconds < 0 or minutes < 0:
        return None
    return (minutes * 60 + seconds) * 1000 + milliseconds


def _fastest_lap_rank(entry: Mapping[str, Any]) -> int | None:
    """Read the fastest-lap rank, tolerating both API shapes.

    Current responses carry a single ``FastestLap`` object; older ones expose a
    ``FastestLaps`` array. Handling only one form would silently drop the rank
    on the other.
    """
    plural = entry.get("FastestLaps")
    if isinstance(plural, list):
        candidates = _mapping_list(plural)
        first = candidates[0] if candidates else None
    elif isinstance(plural, Mapping):
        first = plural
    else:
        single = entry.get("FastestLap")
        first = single if isinstance(single, Mapping) else None
    if first is None:
        return None
    return _int(_text(first, "rank"))


def _result_entries(
    entries: Sequence[Mapping[str, Any]],
    season: int,
    round_number: int,
    session_type: str,
) -> list[StagedResult]:
    rows: list[StagedResult] = []
    for entry in entries:
        driver = entry.get("Driver")
        if not isinstance(driver, Mapping):
            continue
        slug = _text(driver, "driverId")
        if not slug:
            continue
        constructor = entry.get("Constructor")
        constructor_slug = (
            _text(constructor, "constructorId") if isinstance(constructor, Mapping) else None
        )
        points = _text(entry, "points")
        rows.append(
            StagedResult(
                season=season,
                round_number=round_number,
                session_type=session_type,
                driver_slug=slug,
                constructor_slug=constructor_slug,
                driver_number=_int(_text(entry, "number")),
                grid_position=_int(_text(entry, "grid")),
                finish_position=_int(_text(entry, "position")),
                points=float(points) if points and _is_number(points) else None,
                laps=_int(_text(entry, "laps")),
                status=_text(entry, "status"),
                fastest_lap_rank=_fastest_lap_rank(entry),
                q1_ms=None,
                q2_ms=None,
                q3_ms=None,
            )
        )
    return rows


def _is_number(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True


def _parse_results(
    payload: Mapping[str, Any], list_key: str, session_type: str
) -> list[StagedResult]:
    rows: list[StagedResult] = []
    for season, round_number, entries in _rounds(payload, list_key):
        rows.extend(_result_entries(entries, season, round_number, session_type))
    return rows


def parse_race_results(payload: Mapping[str, Any]) -> list[StagedResult]:
    """Extract the Grand Prix classification (``session_type`` ``R``)."""
    return _parse_results(payload, "Results", RACE)


def parse_sprint_results(payload: Mapping[str, Any]) -> list[StagedResult]:
    """Extract the sprint classification (``session_type`` ``S``)."""
    return _parse_results(payload, "SprintResults", SPRINT)


def parse_qualifying_results(payload: Mapping[str, Any]) -> list[StagedResult]:
    """Extract qualifying (``session_type`` ``Q``).

    The API sends no ``grid``, ``laps``, ``status`` or points for qualifying,
    so those stay None rather than being faked. The three Q times are the whole
    value of the row and are converted to milliseconds.
    """
    rows: list[StagedResult] = []
    for season, round_number, entries in _rounds(payload, "QualifyingResults"):
        by_slug = {}
        for entry in entries:
            driver = entry.get("Driver")
            if isinstance(driver, Mapping):
                slug = _text(driver, "driverId")
                if slug:
                    by_slug[slug] = entry
        for staged in _result_entries(entries, season, round_number, QUALIFYING):
            source = by_slug.get(staged.driver_slug, {})
            rows.append(
                staged._replace(
                    q1_ms=parse_time_ms(_text(source, "Q1")),
                    q2_ms=parse_time_ms(_text(source, "Q2")),
                    q3_ms=parse_time_ms(_text(source, "Q3")),
                )
            )
    return rows


def parse_driver_standings(payload: Mapping[str, Any]) -> list[StagedStanding]:
    """Extract cumulative driver standings, one line per round.

    ``Constructors`` is a list, because a driver can change team mid-season.
    The last entry is kept: it is the team the driver was racing for at the end
    of that round.
    """
    rows: list[StagedStanding] = []
    for standings_list in _rows(payload, "StandingsTable", "StandingsLists"):
        season = _int(_text(standings_list, "season"))
        round_number = _int(_text(standings_list, "round"))
        if season is None or round_number is None:
            continue
        for entry in _mapping_list(standings_list.get("DriverStandings")):
            driver = entry.get("Driver")
            if not isinstance(driver, Mapping):
                continue
            slug = _text(driver, "driverId")
            position = _int(_text(entry, "position"))
            if not slug or position is None:
                continue
            constructors = _mapping_list(entry.get("Constructors"))
            constructor_slug = _text(constructors[-1], "constructorId") if constructors else None
            points = _text(entry, "points")
            rows.append(
                StagedStanding(
                    season=season,
                    round_number=round_number,
                    driver_slug=slug,
                    constructor_slug=constructor_slug,
                    driver_number=_int(_text(driver, "permanentNumber")),
                    position=position,
                    points=float(points) if points and _is_number(points) else 0.0,
                    wins=_int(_text(entry, "wins")) or 0,
                )
            )
    return rows


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
        """Return the **final** championship table only.

        Jolpica's season-level standings endpoint answers with one entry per
        driver for the last round, not the per-round history. Use
        :meth:`round_driver_standings` for the full progression.
        """
        return self.get(f"{season}/driverstandings/")

    def round_driver_standings(self, season: int, round_number: int) -> Mapping[str, Any]:
        """Return the cumulative standings as they stood after a round."""
        return self.get(f"{season}/{round_number}/driverstandings/")
