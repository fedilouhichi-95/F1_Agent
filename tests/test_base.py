"""Tests du contrat d'agent (hors réseau)."""

from __future__ import annotations

from app.agents.base import AgentResult, BaseAgent


class EchoAgent(BaseAgent):
    """Stub: renvoie la question telle quelle."""

    name = "echo"

    def run(self, question: str) -> AgentResult:
        return AgentResult(content=question)


def test_agent_returns_result() -> None:
    agent = EchoAgent()
    result = agent.run("Qui a gagné à Monaco ?")
    assert agent.name == "echo"
    assert result.content == "Qui a gagné à Monaco ?"
    assert result.sources == []
    assert result.metadata == {}


def test_agent_result_is_immutable() -> None:
    result = AgentResult(content="ok")
    assert isinstance(result.metadata, dict)
    assert isinstance(result.sources, list)
