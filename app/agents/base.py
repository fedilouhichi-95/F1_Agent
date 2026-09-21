"""Contrat commun des agents et structures de résultat."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentResult:
    """Réponse produite par un agent, avec ses sources traçables."""

    content: str
    sources: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


class BaseAgent(ABC):
    """Un agent transforme une question en AgentResult.

    Le LLM est injecté à l'instanciation de chaque agent spécialisé (jamais
    importé ni instancié ici) pour que les tests unitaires restent hors réseau.
    """

    name: str = "base"

    @abstractmethod
    def run(self, question: str) -> AgentResult:
        """Answer the given question."""


def echo_agent_factory() -> BaseAgent:
    """Agent minimal utilisable tant que les agents réels n'existent pas."""
    raise NotImplementedError("Les agents spécialisés arrivent à la Phase 3 du projet.")
