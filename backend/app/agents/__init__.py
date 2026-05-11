"""Agent package and registry bootstrap."""

from app.agents.account_ops_agent import AccountOpsAgent
from app.agents.audit_agent import AuditAgent
from app.agents.content_writer_agent import ContentWriterAgent
from app.agents.hot_topic_agent import HotTopicAgent
from app.agents.profile_agent import ProfileAgent
from app.agents.registry import agent_registry
from app.agents.rewrite_agent import RewriteAgent
from app.agents.post_process_agent import PostProcessAgent
from app.agents.topic_planner_agent import TopicPlannerAgent

agent_registry.register(ProfileAgent())
agent_registry.register(HotTopicAgent())
agent_registry.register(TopicPlannerAgent())
agent_registry.register(ContentWriterAgent())
agent_registry.register(RewriteAgent())
agent_registry.register(PostProcessAgent())
agent_registry.register(AuditAgent())
agent_registry.register(AccountOpsAgent())

__all__ = [
    "agent_registry",
    "ProfileAgent",
    "HotTopicAgent",
    "TopicPlannerAgent",
    "ContentWriterAgent",
    "RewriteAgent",
    "PostProcessAgent",
    "AuditAgent",
    "AccountOpsAgent",
]
