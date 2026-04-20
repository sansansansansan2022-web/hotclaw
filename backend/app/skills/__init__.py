"""Skills package.

【技能层】
Skill 是被 Agent 调用的工具能力，不参与工作流编排。
"""

from app.skills.base import BaseSkill, SkillResult
from app.skills.registry import skill_registry

# 注册所有 Skill
from app.skills.hot_topic_fetch_skill import HotTopicFetchSkill, hot_topic_fetch_skill
from app.skills.profile_parse_skill import ProfileParseSkill, profile_parse_skill
from app.skills.review_rewrite_skills import (
    RewriteSkill,
    StructureReviewSkill,
    StyleReviewSkill,
    rewrite_skill,
    structure_review_skill,
    style_review_skill,
)
from app.skills.structured_writing_skills import (
    OutlineGenerateSkill,
    SectionDraftSkill,
    outline_generate_skill,
    section_draft_skill,
)
from app.skills.title_generate_skill import TitleGenerateSkill, title_generate_skill
from app.skills.external.github_project_curator_skill import GitHubProjectCuratorSkill
from app.skills.external.scholar_paper_search_skill import ScholarPaperSearchSkill

skill_registry.register(HotTopicFetchSkill())
skill_registry.register(ProfileParseSkill())
skill_registry.register(OutlineGenerateSkill())
skill_registry.register(SectionDraftSkill())
skill_registry.register(StyleReviewSkill())
skill_registry.register(StructureReviewSkill())
skill_registry.register(RewriteSkill())
skill_registry.register(TitleGenerateSkill())
skill_registry.register(GitHubProjectCuratorSkill())
skill_registry.register(ScholarPaperSearchSkill())

__all__ = [
    "BaseSkill",
    "SkillResult",
    "skill_registry",
    "HotTopicFetchSkill",
    "hot_topic_fetch_skill",
    "ProfileParseSkill",
    "profile_parse_skill",
    "OutlineGenerateSkill",
    "outline_generate_skill",
    "SectionDraftSkill",
    "section_draft_skill",
    "StyleReviewSkill",
    "style_review_skill",
    "StructureReviewSkill",
    "structure_review_skill",
    "RewriteSkill",
    "rewrite_skill",
    "TitleGenerateSkill",
    "title_generate_skill",
    "GitHubProjectCuratorSkill",
    "ScholarPaperSearchSkill",
]
