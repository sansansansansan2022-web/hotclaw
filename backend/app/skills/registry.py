"""Skill registry: manages all registered skill instances."""

from app.skills.base import BaseSkill
from app.core.exceptions import SkillNotFoundError
from app.core.logger import get_logger

logger = get_logger(__name__)


class SkillRegistry:
    """Central registry for all skills."""

    def __init__(self) -> None:
        self._skills: dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        if skill.skill_id in self._skills:
            logger.warning("skill_already_registered", skill_id=skill.skill_id)
        self._skills[skill.skill_id] = skill
        logger.info("skill_registered", skill_id=skill.skill_id, name=skill.name)

    def get(self, skill_id: str) -> BaseSkill:
        skill = self._skills.get(skill_id)
        if skill is None:
            raise SkillNotFoundError(skill_id)
        return skill

    def list_all(self) -> list[BaseSkill]:
        return list(self._skills.values())

    def has(self, skill_id: str) -> bool:
        return skill_id in self._skills


# Singleton instance
skill_registry = SkillRegistry()
