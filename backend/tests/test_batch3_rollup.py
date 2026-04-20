from app.agents.outline_planner_agent import OutlinePlannerAgent
from app.agents.rewrite_agent import RewriteAgent
from app.agents.section_writer_agent import SectionWriterAgent
from app.agents.structure_reviewer_agent import StructureReviewerAgent
from app.agents.style_reviewer_agent import StyleReviewerAgent


def test_batch3_agents_expose_skill_boundaries():
    assert OutlinePlannerAgent.supported_skills == ["outline_generate_skill"]
    assert SectionWriterAgent.supported_skills == ["section_draft_skill"]
    assert StyleReviewerAgent.supported_skills == ["style_review_skill"]
    assert StructureReviewerAgent.supported_skills == ["structure_review_skill"]
    assert RewriteAgent.supported_skills == ["rewrite_skill"]


def test_batch3_agents_keep_existing_ids():
    assert OutlinePlannerAgent.agent_id == "outline_planner_agent"
    assert SectionWriterAgent.agent_id == "section_writer_agent"
    assert StyleReviewerAgent.agent_id == "style_reviewer_agent"
    assert StructureReviewerAgent.agent_id == "structure_reviewer_agent"
    assert RewriteAgent.agent_id == "rewrite_agent"
