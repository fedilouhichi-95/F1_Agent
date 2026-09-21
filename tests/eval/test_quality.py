"""Quality gate — squelette à compléter à la Phase 6 de la SPEC.

Le job CI `eval.yml` lance ce module (`pytest -m eval`). Tant que le
jeu de référence est vide, seul un test structurel s'exécute (aucun
appel réseau, aucun secret requis) pour garder le workflow vert.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

EVAL_DIR = Path(__file__).parent


@pytest.mark.eval
def test_reference_questions_file_is_valid_json() -> None:
    """Le jeu de référence doit rester un JSON valide et listable."""
    with (EVAL_DIR / "questions.json").open(encoding="utf-8") as handle:
        payload = json.load(handle)
    assert isinstance(payload["questions"], list)
    assert payload["reference_date"] == "2023"
