"""Base class for all skills.

Per NOTICE.md section 6:
- Skill is a tool capability called by Agents
- Not a workflow node, does not participate in orchestration
- Only does tool-type processing
- Output should be stable and reusable
"""

from abc import ABC, abstractmethod
from app.core.logger import get_logger

logger = get_logger(__name__)


class BaseSkill(ABC):
    """Abstract base class for all skills."""

    skill_id: str = ""
    name: str = ""
    description: str = ""

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    @abstractmethod
    async def execute(self, input_data: dict) -> dict:
        """Execute the skill.

        Args:
            input_data: Structured input for this skill.

        Returns:
            Structured output dict.
        """
        ...
