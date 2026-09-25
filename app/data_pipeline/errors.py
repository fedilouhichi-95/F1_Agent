"""Shared error reporting for the data pipeline.

Connection failures are the most common way this pipeline breaks, and the
original cause is what tells you how to fix it. These helpers keep that cause
visible while guaranteeing that no credential ever reaches a log or a CI output.
"""

from __future__ import annotations

import re

_DSN_PATTERN = re.compile(r"postgres(?:ql)?://\S+", re.IGNORECASE)
_PASSWORD_PATTERN = re.compile(r"\b(password|passfile|pwd)\s*=\s*\S+", re.IGNORECASE)

REDACTED = "<url redacted>"
CONNECTION_HINT = (
    "Vérifie que SUPABASE_DB_URL utilise la chaîne du Session pooler, copiée depuis "
    "Project Settings > Database > Connect. L'hôte aws-N.pooler.supabase.com ne se "
    "déduit pas de la région, et la connexion directe est IPv6-only."
)


def describe_failure(exc: Exception) -> str:
    """Summarise a failure, keeping the cause but hiding credentials."""
    detail = " ".join(str(exc).split())
    detail = _DSN_PATTERN.sub(REDACTED, detail)
    return _PASSWORD_PATTERN.sub(r"\1=<redacted>", detail)


def describe_connection_failure(exc: Exception) -> str:
    """Same as :func:`describe_failure`, plus the pooler hint.

    Only for failures that actually reach PostgreSQL: appending the hint to an
    unrelated error (a mistyped season, say) sends the reader after the wrong
    setting.
    """
    return f"{describe_failure(exc)} — {CONNECTION_HINT}"


def missing_configuration(*names: str) -> ValueError:
    """Build the error raised when required environment variables are absent."""
    return ValueError(f"Configuration incomplète : {', '.join(names)} manquante(s).")
