"""Command line orchestration of the F1 ingestion.

Run it with ``python -m app.data_pipeline.ingest <commande>``. Every write goes
through :mod:`app.data_pipeline.db`, so each subcommand is idempotent and can be
replayed safely after an interruption.

``--dry-run`` fetches and parses without opening a database connection at all,
which makes it the safe way to explore a season before writing anything.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass

import psycopg2
from psycopg2.extensions import connection

from app.config import AppConfig
from app.data_pipeline import db
from app.data_pipeline.errors import (
    describe_connection_failure,
    describe_failure,
    missing_configuration,
)
from app.data_pipeline.jolpica import (
    ConstructorRow,
    DriverRow,
    JolpicaClient,
    RaceRow,
    StagedResult,
    StagedStanding,
    build_season,
    parse_constructors,
    parse_driver_standings,
    parse_drivers,
    parse_qualifying_results,
    parse_race_results,
    parse_races,
    parse_sprint_results,
)
from app.data_pipeline.resolve import (
    load_references,
    resolve_results,
    resolve_standings,
)

RACE_COLUMNS = (
    "season",
    "round_number",
    "race_key",
    "name",
    "circuit_name",
    "race_date",
    "url",
)
DRIVER_COLUMNS = ("source_driver_id", "name", "code", "nationality")
CONSTRUCTOR_COLUMNS = ("source_constructor_id", "name", "code", "nationality")
SEASON_COLUMNS = ("season", "label", "start_date")
RESULT_COLUMNS = (
    "season",
    "session_type",
    "race_id",
    "driver_id",
    "constructor_id",
    "driver_number",
    "grid_position",
    "finish_position",
    "points",
    "laps",
    "status",
    "fastest_lap_rank",
    "q1_ms",
    "q2_ms",
    "q3_ms",
)
STANDING_COLUMNS = (
    "season",
    "race_id",
    "driver_id",
    "constructor_id",
    "driver_number",
    "position",
    "points",
    "wins",
)

MINIMUM_SEASON = 1950


@dataclass(frozen=True)
class SeasonCounts:
    """How many rows each table holds for one season."""

    rows: tuple[tuple[str, int], ...]

    def render(self) -> str:
        return "\n".join(f"  {table:<14} {count:>7}" for table, count in self.rows)


def parse_seasons(raw: str) -> list[int]:
    """Read the ``INGEST_SEASONS`` format, rejecting anything the schema refuses."""
    seasons: list[int] = []
    for chunk in raw.split(","):
        token = chunk.strip()
        if not token:
            continue
        try:
            season = int(token)
        except ValueError as exc:
            raise ValueError(f"Saison invalide : {token!r}") from exc
        if season < MINIMUM_SEASON:
            raise ValueError(
                f"Saison {season} antérieure à {MINIMUM_SEASON}, refusée par le schéma"
            )
        seasons.append(season)
    if not seasons:
        raise missing_configuration("INGEST_SEASONS")
    return seasons


def fetch_metadata(client: JolpicaClient, season: int) -> dict[str, list[object]]:
    """Fetch and parse every metadata table for one season."""
    races: list[RaceRow] = parse_races(client.season_races(season))
    if not races:
        raise ValueError(f"Aucun grand prix trouvé pour la saison {season}.")
    drivers: list[DriverRow] = parse_drivers(client.season_drivers(season))
    constructors: list[ConstructorRow] = parse_constructors(client.season_constructors(season))
    return {
        "seasons": [tuple(build_season(season, races))],
        "drivers": [tuple(row) for row in drivers],
        "constructors": [tuple(row) for row in constructors],
        "races": [tuple(row) for row in races],
    }


def write_metadata(
    active: connection,
    tables: dict[str, list[object]],
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    """Persist metadata in foreign key order, in a single transaction."""
    plan = (
        ("seasons", SEASON_COLUMNS, ("season",)),
        ("drivers", DRIVER_COLUMNS, ("source_driver_id",)),
        ("constructors", CONSTRUCTOR_COLUMNS, ("source_constructor_id",)),
        ("races", RACE_COLUMNS, ("season", "round_number")),
    )
    written: dict[str, int] = {}
    for table, columns, conflict in plan:
        rows = tables[table]
        written[table] = len(rows) if dry_run else 0
        if dry_run:
            continue
        with db.transaction(active):
            written[table] = db.upsert(
                active,
                table=table,
                columns=columns,
                rows=rows,
                conflict=conflict,
            )
    return written


def ingest_season_metadata(
    client: JolpicaClient,
    season: int,
    active: connection | None = None,
) -> dict[str, int]:
    """Fetch, parse and optionally persist one season of metadata."""
    tables = fetch_metadata(client, season)
    if active is None:
        return {table: len(rows) for table, rows in tables.items()}
    return write_metadata(active, tables)


def fetch_results(
    client: JolpicaClient,
    season: int,
    rounds: Sequence[int],
    sessions: Sequence[str],
) -> list[StagedResult]:
    """Fetch results for the requested rounds and session types.

    Round-scoped requests are used on purpose: each answer holds at most twenty
    drivers, so no pagination is needed and one failing round only affects
    itself.
    """
    staged: list[StagedResult] = []
    parsers = {
        "R": (client.round_results, parse_race_results),
        "S": (client.round_sprint, parse_sprint_results),
        "Q": (client.round_qualifying, parse_qualifying_results),
    }
    for round_number in rounds:
        for session_type in sessions:
            fetch, parse = parsers[session_type]
            staged.extend(parse(fetch(season, round_number)))
    return staged


def fetch_standings(
    client: JolpicaClient, season: int, rounds: Sequence[int]
) -> list[StagedStanding]:
    """Fetch the cumulative driver standings after each round.

    The season-level endpoint only exposes the final table, so the progression
    has to be requested round by round.
    """
    staged: list[StagedStanding] = []
    for round_number in rounds:
        staged.extend(parse_driver_standings(client.round_driver_standings(season, round_number)))
    return staged


def count_rows(active: connection, season: int) -> SeasonCounts:
    """Report the current population of the pipeline tables for a season."""
    queries = (
        ("seasons", "SELECT count(*) FROM seasons WHERE season = %s", True),
        ("drivers", "SELECT count(*) FROM drivers", False),
        ("constructors", "SELECT count(*) FROM constructors", False),
        ("races", "SELECT count(*) FROM races WHERE season = %s", True),
    )
    rows: list[tuple[str, int]] = []
    for table, statement, filtered in queries:
        params = (season,) if filtered else ()
        found = db.fetch_one(active, statement, params)
        rows.append((table, int(found[0]) if found else 0))
    return SeasonCounts(rows=tuple(rows))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.data_pipeline.ingest",
        description="Ingestion des données F1 vers Supabase.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    metadata = subcommands.add_parser("metadata", help="Saisons, pilotes, écuries et calendrier.")
    metadata.add_argument("--season", action="append", help="Saison à ingérer (répétable).")
    metadata.add_argument(
        "--dry-run",
        action="store_true",
        help="Récupère et analyse sans ouvrir de connexion.",
    )

    results = subcommands.add_parser(
        "results", help="Classifications course, sprint et qualifications, plus les classements."
    )
    results.add_argument("--season", action="append", help="Saison à ingérer (répétable).")
    results.add_argument(
        "--session",
        default="RS",
        help="Types de session à ingérer : R, S, Q (défaut RS).",
    )
    results.add_argument(
        "--round",
        action="append",
        type=int,
        help="Limiter à ces rounds (répétable, défaut : tous).",
    )
    results.add_argument(
        "--skip-standings",
        action="store_true",
        help="Ne pas ingérer les classements cumulés.",
    )
    results.add_argument(
        "--dry-run",
        action="store_true",
        help="Récupère et analyse sans ouvrir de connexion.",
    )

    status = subcommands.add_parser("status", help="État de la base pour une saison.")
    status.add_argument("--season", action="append", help="Saison à inspecter (répétable).")
    return parser


def _sessions(raw: str) -> list[str]:
    """Validate the --session selector against what the schema accepts.

    Accepts both the compact form used by the default (``RSQ``) and the
    human-readable one the help text suggests (``R, S, Q``).
    """
    tokens: list[str] = []
    for chunk in raw.replace(",", " ").split():
        tokens.extend(character.upper() for character in chunk)
    unknown = [token for token in tokens if token not in ("R", "S", "Q")]
    if unknown:
        raise ValueError(f"Type de session inconnu : {', '.join(unknown)}")
    if not tokens:
        raise ValueError("Aucun type de session demandé.")
    return list(dict.fromkeys(tokens))


def _rounds_of(client: JolpicaClient, season: int) -> list[int]:
    rounds = [row.round_number for row in parse_races(client.season_races(season))]
    if not rounds:
        raise ValueError(f"Aucun grand prix trouvé pour la saison {season}.")
    return sorted(rounds)


def _seasons_from(args: argparse.Namespace, config: AppConfig) -> list[int]:
    raw = ",".join(args.season) if args.season else config.ingest_seasons
    return parse_seasons(raw)


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    config = AppConfig.from_env()
    args = _build_parser().parse_args(argv)

    try:
        seasons = _seasons_from(args, config)
    except ValueError as exc:
        print(f"Configuration invalide : {exc}", file=sys.stderr)
        return 2

    client = JolpicaClient(config.jolpica_base_url)

    if args.command == "status":
        try:
            active = db.connect(config)
        except (ValueError, psycopg2.Error) as exc:
            print(f"Connexion impossible : {describe_connection_failure(exc)}", file=sys.stderr)
            return 1
        try:
            for season in seasons:
                print(f"Saison {season} :")
                print(count_rows(active, season).render())
        finally:
            active.close()
        return 0

    if args.command == "results":
        return _run_results(config, client, args, seasons)

    try:
        for season in seasons:
            if args.dry_run:
                written = ingest_season_metadata(client, season)
                print(f"Saison {season} (simulation) :")
            else:
                active = db.connect(config)
                try:
                    written = ingest_season_metadata(client, season, active)
                finally:
                    active.close()
                print(f"Saison {season} :")
            for table, count in written.items():
                print(f"  {table:<14} {count:>7}")
    except (ValueError, psycopg2.Error, LookupError) as exc:
        print(f"Ingestion interrompue : {describe_failure(exc)}", file=sys.stderr)
        return 1
    return 0


def _run_results(
    config: AppConfig,
    client: JolpicaClient,
    args: argparse.Namespace,
    seasons: Sequence[int],
) -> int:
    """Fetch, resolve and optionally write results and standings."""
    try:
        sessions = _sessions(args.session)
    except ValueError as exc:
        print(f"Configuration invalide : {exc}", file=sys.stderr)
        return 2

    active: connection | None = None
    try:
        if not args.dry_run:
            active = db.connect(config)

        for season in seasons:
            rounds = args.round or _rounds_of(client, season)
            staged = fetch_results(client, season, rounds, sessions)
            written: dict[str, int] = {}

            if active is None:
                by_session: dict[str, int] = {}
                for item in staged:
                    by_session[item.session_type] = by_session.get(item.session_type, 0) + 1
                written = {
                    "results": len(staged),
                    **{f"  dont {key}": value for key, value in sorted(by_session.items())},
                }
            else:
                references = load_references(active, season)
                resolution = resolve_results(staged, references)
                rows = resolution.raise_if_incomplete("results")
                with db.transaction(active):
                    written["results"] = db.upsert(
                        active,
                        table="results",
                        columns=RESULT_COLUMNS,
                        rows=rows,
                        conflict=("season", "session_type", "race_id", "driver_id"),
                    )

            if not args.skip_standings:
                standings = fetch_standings(client, season, rounds)
                if active is None:
                    written["standings"] = len(standings)
                else:
                    references = load_references(active, season)
                    standing_rows = resolve_standings(standings, references)
                    rows = standing_rows.raise_if_incomplete("standings")
                    with db.transaction(active):
                        written["standings"] = db.upsert(
                            active,
                            table="standings",
                            columns=STANDING_COLUMNS,
                            rows=rows,
                            conflict=("season", "race_id", "driver_id"),
                        )

            label = f"Saison {season}" + (" (simulation)" if active is None else "")
            print(f"{label} :")
            for table, count in written.items():
                print(f"  {table:<14} {count:>7}")
    except (ValueError, psycopg2.Error, LookupError) as exc:
        print(f"Ingestion interrompue : {describe_failure(exc)}", file=sys.stderr)
        return 1
    finally:
        if active is not None:
            active.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
