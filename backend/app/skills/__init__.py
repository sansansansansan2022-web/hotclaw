"""Skills package.

【技能层】
Skill 是被 Agent 调用的工具能力，不参与工作流编排。
"""

from app.skills.base import BaseSkill, SkillResult
from app.skills.registry import skill_registry

# 注册所有 Skill
from app.skills.hot_topic_fetch_skill import HotTopicFetchSkill

skill_registry.register(HotTopicFetchSkill())

__all__ = [
    "BaseSkill",
    "SkillResult",
    "skill_registry",
    "HotTopicFetchSkill",
]
