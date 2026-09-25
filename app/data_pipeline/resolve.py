"""Resolve Jolpica slugs into Supabase identifiers.

Jolpica identifies drivers and constructors with slugs (``max_verstappen``,
``red_bull``) while the schema stores generated ``BIGINT`` identities. Every
fact row therefore has to be reconciled against what the metadata stage already
wrote.

The guiding rule is that **nothing is dropped silently**. A slug with no
matching row is collected and returned, so the caller can abort with a list
instead of quietly ingesting a season that is missing somebody.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from psycopg2.extensions import connection

from app.data_pipeline import db
from app.data_pipeline.jolpica import StagedResult, StagedStanding


@dataclass(frozen=True)
class References:
    """Everything the fact tables need in order to be inserted."""

    driver_ids: Mapping[str, int] = field(default_factory=dict)
    constructor_ids: Mapping[str, int] = field(default_factory=dict)
    race_ids: Mapping[int, int] = field(default_factory=dict)

    def driver(self, slug: str) -> int | None:
        return self.driver_ids.get(slug)

    def constructor(self, slug: str | None) -> int | None:
        return self.constructor_ids.get(slug) if slug else None

    def race(self, season: int, round_number: int) -> int | None:
        return self.race_ids.get(round_number)


@dataclass(frozen=True)
class Resolution:
    """Rows ready to insert, plus whatever could not be reconciled."""

    rows: list[tuple[object, ...]] = field(default_factory=list)
    unresolved: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return not self.unresolved

    def raise_if_incomplete(self, table: str) -> list[tuple[object, ...]]:
        """Return the rows, or explain precisely which references are missing."""
        if self.unresolved:
            listed = ", ".join(self.unresolved)
            raise LookupError(
                f"{table} : {len(self.unresolved)} référence(s) non résolue(s) "
                f"après ingestion des métadonnées ({listed}). Lance d'abord "
                f"`python -m app.data_pipeline.ingest metadata`."
            )
        return self.rows


def load_references(active: connection, season: int) -> References:
    """Read back the identities written by the metadata stage."""
    drivers = db.fetch_all(active, "SELECT source_driver_id, driver_id FROM drivers")
    constructors = db.fetch_all(
        active, "SELECT source_constructor_id, constructor_id FROM constructors"
    )
    races = db.fetch_all(
        active, "SELECT round_number, race_id FROM races WHERE season = %s", (season,)
    )
    return References(
        driver_ids={row[0]: int(row[1]) for row in drivers if row[0] is not None},
        constructor_ids={row[0]: int(row[1]) for row in constructors if row[0] is not None},
        race_ids={int(row[0]): int(row[1]) for row in races},
    )


def resolve_results(staged: Sequence[StagedResult], references: References) -> Resolution:
    """Map staged result lines onto the ``results`` column order."""
    rows: list[tuple[object, ...]] = []
    missing: set[str] = set()
    for item in staged:
        driver_id = references.driver(item.driver_slug)
        race_id = references.race(item.season, item.round_number)
        if driver_id is None:
            missing.add(f"driver:{item.driver_slug}")
        if race_id is None:
            missing.add(f"race:{item.season}/{item.round_number}")
        if driver_id is None or race_id is None:
            continue
        rows.append(
            (
                item.season,
                item.session_type,
                race_id,
                driver_id,
                references.constructor(item.constructor_slug),
                item.driver_number,
                item.grid_position,
                item.finish_position,
                item.points if item.points is not None else 0,
                item.laps,
                item.status,
                item.fastest_lap_rank,
                item.q1_ms,
                item.q2_ms,
                item.q3_ms,
            )
        )
    return Resolution(rows=rows, unresolved=tuple(sorted(missing)))


def resolve_standings(staged: Sequence[StagedStanding], references: References) -> Resolution:
    """Map staged standings onto the ``standings`` column order."""
    rows: list[tuple[object, ...]] = []
    missing: set[str] = set()
    for item in staged:
        driver_id = references.driver(item.driver_slug)
        race_id = references.race(item.season, item.round_number)
        if driver_id is None:
            missing.add(f"driver:{item.driver_slug}")
        if race_id is None:
            missing.add(f"race:{item.season}/{item.round_number}")
        if driver_id is None or race_id is None:
            continue
        rows.append(
            (
                item.season,
                race_id,
                driver_id,
                references.constructor(item.constructor_slug),
                item.driver_number,
                item.position,
                item.points,
                item.wins,
            )
        )
    return Resolution(rows=rows, unresolved=tuple(sorted(missing)))
