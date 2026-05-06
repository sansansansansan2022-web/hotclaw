"""Base class for all skills.

Per NOTICE.md section 6:
- Skill is a tool capability called by Agents
- Not a workflow node, does not participate in orchestration
- Only does tool-type processing
- Output should be stable and reusable

Skill Contract 要求：
1. 每个 Skill 必须定义 input_schema 和 output_schema
2. 每个 Skill 的 execute() 必须返回 SkillResult 结构
3. Skill 不直接写主业务状态
4. Skill 可被注册、查询、复用
"""

from abc import ABC, abstractmethod
from typing import Any
from app.core.logger import get_logger

logger = get_logger(__name__)


class SkillResult:
    """
    Standardized skill execution result.

    【技能执行结果】
    所有 Skill 必须返回 SkillResult，实现统一的成功/失败处理。

    Attributes:
        status: 结果状态 ("success" | "failed")
        skill_id: 技能 ID
        data: 成功时的结构化输出数据
        error: 失败时的错误信息 {code, message}
    """

    def __init__(
        self,
        status: str,
        skill_id: str,
        data: dict | None = None,
        error: dict | None = None,
    ):
        self.status = status
        self.skill_id = skill_id
        self.data = data
        self.error = error

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "status": self.status,
            "skill_id": self.skill_id,
            "data": self.data,
            "error": self.error,
        }

    @property
    def is_success(self) -> bool:
        """判断是否成功执行。"""
        return self.status == "success"

    @classmethod
    def success(cls, skill_id: str, data: dict) -> "SkillResult":
        """构建成功结果。"""
        return cls(status="success", skill_id=skill_id, data=data)

    @classmethod
    def failure(cls, skill_id: str, code: str, message: str) -> "SkillResult":
        """构建失败结果。"""
        return cls(
            status="failed",
            skill_id=skill_id,
            error={"code": code, "message": message}
        )


class BaseSkill(ABC):
    """
    Abstract base class for all skills.

    【技能抽象基类】
    所有具体技能都继承此类。

    Skill Contract 要求：
    1. skill_id: 唯一标识
    2. name: 中文显示名称
    3. description: 职能描述
    4. input_schema: 输入 JSON Schema
    5. output_schema: 输出 JSON Schema
    6. execute(): 核心执行逻辑

    Skill 设计原则：
    1. 不参与工作流编排
    2. 只能被 Agent 调用
    3. 不直接写主业务状态
    4. 输出必须结构化
    """

    # 类属性：子类必须定义
    skill_id: str = ""
    name: str = ""
    description: str = ""

    # Skill Contract
    input_schema: dict = {}
    output_schema: dict = {}

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    @abstractmethod
    async def execute(self, input_data: dict) -> dict:
        """
        Execute the skill.

        Args:
            input_data: Structured input for this skill.

        Returns:
            dict: 包含 status/skill_id/data/error 的结构
        """
        ...

    def get_input_schema(self) -> dict:
        """获取输入 Schema。"""
        return self.input_schema

    def get_output_schema(self) -> dict:
        """获取输出 Schema。"""
        return self.output_schema

    def get_contract(self) -> dict:
        """获取完整的 Skill Contract 描述。"""
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }
