"""Skills package.

【技能层】
Skill 是被 Agent 调用的工具能力，不参与工作流编排。
"""

from app.skills.base import BaseSkill, SkillResult
from app.skills.registry import skill_registry

# 注册所有 Skill
from app.skills.hot_topic_fetch_skill import HotTopicFetchSkill, hot_topic_fetch_skill
from app.skills.external.github_project_curator_skill import GitHubProjectCuratorSkill
from app.skills.external.scholar_paper_search_skill import ScholarPaperSearchSkill

skill_registry.register(HotTopicFetchSkill())
skill_registry.register(GitHubProjectCuratorSkill())
skill_registry.register(ScholarPaperSearchSkill())

__all__ = [
    "BaseSkill",
    "SkillResult",
    "skill_registry",
    "HotTopicFetchSkill",
    "hot_topic_fetch_skill",
    "GitHubProjectCuratorSkill",
    "ScholarPaperSearchSkill",
]
