"""
Agent registry: manages all registered agent instances.

【智能体注册表】
实现插件化架构：新增智能体只需继承 BaseAgent 并注册，
即可被编排引擎自动发现和使用。

设计模式：注册表模式（Registry Pattern）
- 类似 Django 的 ADMIN 和 Flask 的 extensions
- 新增智能体无需修改编排引擎代码

面试点：
- 注册表模式实现插件化
- 单例模式
- 全局注册 vs 延迟注册
"""

from app.agents.base import BaseAgent
from app.core.exceptions import AgentNotFoundError
from app.core.logger import get_logger

logger = get_logger(__name__)


class AgentRegistry:
    """
    Central registry for all agents. Agents are registered by agent_id.

    【智能体注册表】
    维护 agent_id → BaseAgent 实例 的映射。

    注册流程：
    1. 在 agents/__init__.py 中 import 所有智能体类
    2. 调用 agent_registry.register(ProfileAgent())
    3. 编排引擎通过 agent_registry.get(agent_id) 获取实例

    为什么用实例而不是类？
    实例可以包含配置状态（self.config），
    允许不同任务使用不同配置的同一智能体。
    """

    def __init__(self) -> None:
        # agent_id → 智能体实例
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """
        Register an agent instance.

        【注册方法】
        通常在应用启动时（main.py startup 事件）调用，
        将所有智能体注册到全局注册表。

        如果重复注册同一 agent_id，记录警告但不覆盖。
        """
        if agent.agent_id in self._agents:
            logger.warning("agent_already_registered", agent_id=agent.agent_id)
        self._agents[agent.agent_id] = agent
        logger.info("agent_registered", agent_id=agent.agent_id, name=agent.name)

    def get(self, agent_id: str) -> BaseAgent:
        """
        Get an agent by ID.

        【获取方法】编排引擎调用此方法获取智能体实例

        Raises:
            AgentNotFoundError: agent_id 不存在时抛出
        """
        agent = self._agents.get(agent_id)
        if agent is None:
            raise AgentNotFoundError(agent_id)
        return agent

    def list_all(self) -> list[BaseAgent]:
        """Return all registered agents."""
        return list(self._agents.values())

    def has(self, agent_id: str) -> bool:
        """检查智能体是否已注册。"""
        return agent_id in self._agents


# 【单例模式】全局注册表实例
# 整个应用共享同一个注册表
agent_registry = AgentRegistry()
