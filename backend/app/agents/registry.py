"""Agent registry: manages all registered agent instances."""

from app.agents.base import BaseAgent
from app.core.exceptions import AgentNotFoundError
from app.core.logger import get_logger

logger = get_logger(__name__)


class AgentRegistry:
    """Central registry for all agents. Agents are registered by agent_id."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """Register an agent instance."""
        if agent.agent_id in self._agents:
            logger.warning("agent_already_registered", agent_id=agent.agent_id)
        self._agents[agent.agent_id] = agent
        logger.info("agent_registered", agent_id=agent.agent_id, name=agent.name)

    def get(self, agent_id: str) -> BaseAgent:
        """Get an agent by ID. Raises AgentNotFoundError if not found."""
        agent = self._agents.get(agent_id)
        if agent is None:
            raise AgentNotFoundError(agent_id)
        return agent

    def list_all(self) -> list[BaseAgent]:
        """Return all registered agents."""
        return list(self._agents.values())

    def has(self, agent_id: str) -> bool:
        return agent_id in self._agents


# Singleton instance
agent_registry = AgentRegistry()
