"""Skill and agent registries."""
from typing import Any

from agentic_system.observability import get_logger
from agentic_system.runtime.agent import Agent
from agentic_system.runtime.contracts import ExecutionContext
from agentic_system.runtime.skill import Skill

logger = get_logger(__name__)


class SkillRegistry:
    """Registry for managing skills."""

    def __init__(self):
        """Initialize skill registry."""
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        """
        Register a skill.

        Args:
            skill: Skill instance to register
        """
        spec = skill.spec()
        key = f"{spec.name}@{spec.version}"
        self._skills[key] = skill
        logger.info(f"Skill registered: {key}")

    def get(self, name: str, version: str = "latest") -> Skill | None:
        """
        Get a skill by name and version.

        Args:
            name: Skill name
            version: Skill version (default: "latest")

        Returns:
            Skill instance or None if not found
        """
        if version == "latest":
            # Find latest version (simple implementation: return first match)
            for key, skill in self._skills.items():
                if key.startswith(f"{name}@"):
                    return skill
            return None

        key = f"{name}@{version}"
        return self._skills.get(key)

    def execute(
        self,
        name: str,
        input_data: dict[str, Any],
        context: ExecutionContext,
        version: str = "latest",
    ) -> dict[str, Any]:
        """
        Execute a skill by name.

        Args:
            name: Skill name
            input_data: Input data
            context: Execution context
            version: Skill version (default: "latest")

        Returns:
            Skill output

        Raises:
            ValueError: If skill not found
        """
        skill = self.get(name, version)
        if skill is None:
            raise ValueError(f"Skill not found: {name}@{version}")

        return skill.execute(input_data, context)

    def list_skills(self) -> list[str]:
        """
        List all registered skills.

        Returns:
            List of skill keys (name@version)
        """
        return list(self._skills.keys())


class AgentRegistry:
    """Registry for managing agents."""

    def __init__(self):
        """Initialize agent registry."""
        self._agents: dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        """
        Register an agent.

        Args:
            agent: Agent instance to register
        """
        spec = agent.spec()
        key = f"{spec.agent_id}@{spec.version}"
        self._agents[key] = agent
        logger.info(f"Agent registered: {key}")

    def get(self, agent_id: str, version: str = "latest") -> Agent | None:
        """
        Get an agent by ID and version.

        Args:
            agent_id: Agent ID
            version: Agent version (default: "latest")

        Returns:
            Agent instance or None if not found
        """
        if version == "latest":
            # Find latest version (simple implementation: return first match)
            for key, agent in self._agents.items():
                if key.startswith(f"{agent_id}@"):
                    return agent
            return None

        key = f"{agent_id}@{version}"
        return self._agents.get(key)

    def list_agents(self) -> list[str]:
        """
        List all registered agents.

        Returns:
            List of agent keys (agent_id@version)
        """
        return list(self._agents.keys())


# Global registries
_skill_registry: SkillRegistry | None = None
_agent_registry: AgentRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    """Get or create the global skill registry."""
    global _skill_registry
    if _skill_registry is None:
        _skill_registry = SkillRegistry()
    return _skill_registry


def get_agent_registry() -> AgentRegistry:
    """Get or create the global agent registry."""
    global _agent_registry
    if _agent_registry is None:
        _agent_registry = AgentRegistry()
    return _agent_registry
