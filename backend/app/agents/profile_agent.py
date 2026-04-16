"""Profile agent: parses account positioning into a structured profile."""

# ============================================================================
# 账号画像 Agent (Profile Agent)
# ============================================================================
# 职责说明：
# - 将用户输入的账号定位描述（自然语言）解析为结构化的账号画像
# - 提取领域、子领域、目标受众、内容风格、关键词等信息
# - 决定内容来源偏好（学术论文、GitHub、微信搜索等）
#
# 协作关系：
# - 输入：positioning（账号定位描述）
# - 输出：结构化画像数据
# - 被 TopicPlannerAgent、HotTopicAgent 等后续 Agent 使用
# ============================================================================

from __future__ import annotations

import json

import litellm

from app.agents.base import AgentResult, BaseAgent
from app.core.config import settings


class ProfileAgent(BaseAgent):
    """账号画像 Agent - 将自然语言账号定位转换为结构化画像。

    核心职责：
    1. 解析账号定位描述，提取领域和子领域
    2. 分析目标受众特征（年龄段、职业、兴趣）
    3. 确定内容风格和语气
    4. 提取关键词用于内容匹配
    5. 判断内容来源偏好（scholar/github/wechat/web_search）
    6. 决定研究和开源内容的处理模式

    适用场景：
    - 新账号初始化时生成基础画像
    - 账号定位调整后更新画像
    - 为后续内容生成提供上下文
    """

    # Agent 唯一标识符
    agent_id = "profile_agent"
    name = "Profile Agent"
    description = "Parse account positioning into a structured content profile."

    # 输入数据结构定义
    # positioning: 自然语言账号定位描述
    # account_context: 可选的账号上下文信息
    input_schema = {
        "type": "object",
        "properties": {
            "positioning": {"type": "string", "description": "Natural language account positioning"},
            "account_context": {"type": "object", "description": "Optional account context"},
        },
        "required": ["positioning"],
    }

    # 输出数据结构定义
    # 包含领域、受众、内容风格、来源偏好等完整画像信息
    output_schema = {
        "type": "object",
        "properties": {
            "domain": {"type": "string"},
            "subdomain": {"type": "string"},
            "target_audience": {
                "type": "object",
                "properties": {
                    "age_range": {"type": "string"},
                    "occupation": {"type": "string"},
                    "interests": {"type": "array", "items": {"type": "string"}},
                },
            },
            "tone": {"type": "string"},
            "content_style": {"type": "string"},
            "keywords": {"type": "array", "items": {"type": "string"}},
            "source_preferences": {"type": "array", "items": {"type": "string"}},
            "research_mode": {"type": "string"},
            "open_source_mode": {"type": "string"},
            "positioning_raw": {"type": "string"},
        },
    }

    # 该 Agent 不使用任何 Skill
    supported_skills = []

    # 默认系统提示词，指导 LLM 如何解析账号定位
    default_system_prompt = """You are a profile analyst for a content operations system.

Read the account positioning and return strict JSON only.

Required fields:
- domain
- subdomain
- target_audience { age_range, occupation, interests }
- tone
- content_style
- keywords
- source_preferences: choose from scholar, github, wechat, web_search
- research_mode: choose disabled, enabled, research_first
- open_source_mode: choose disabled, enabled, open_source_first

Rules:
- Infer only what is reasonably supported by the positioning text.
- If the account clearly focuses on research, papers, methods, or academic interpretation, include scholar and set research_mode accordingly.
- If the account clearly focuses on developers, tools, GitHub, open source, or engineering trends, include github and set open_source_mode accordingly.
"""

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        """执行账号画像解析。

        主要步骤：
        1. 提取账号定位描述
        2. 调用 LLM 进行结构化解析
        3. 规范化来源偏好和研究模式
        4. 返回完整画像数据

        Args:
            input_data: 包含 positioning 的输入数据
            context: 执行上下文（包含 system_prompt 等）

        Returns:
            AgentResult: 包含结构化画像或错误信息
        """
        # 获取账号定位描述
        positioning = input_data.get("positioning", "")
        # 获取自定义系统提示词（可选）
        system_prompt = context.get("system_prompt") or self.default_system_prompt
        # 构建用户提示词
        user_prompt = f"Parse this account positioning into the required JSON contract:\n{positioning}"

        try:
            # 调用 LLM 进行解析
            response = await self.run_litellm_completion(
                context=context,
                completion_callable=litellm.acompletion,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                timeout=settings.llm_timeout,
            )
            content = response.choices[0].message.content
            # 解析 LLM 返回的 JSON
            data = self._parse_json(content)
            # 保留原始定位描述
            data["positioning_raw"] = positioning
            # 规范化来源偏好
            data["source_preferences"] = self._normalize_source_preferences(data.get("source_preferences"))
            # 规范化研究模式
            data["research_mode"] = self._normalize_research_mode(data.get("research_mode"), data["source_preferences"])
            # 规范化开源模式
            data["open_source_mode"] = self._normalize_open_source_mode(
                data.get("open_source_mode"),
                data["source_preferences"],
            )
            return self._attach_runtime_trace(self._success(data), context)

        except json.JSONDecodeError as exc:
            return self._attach_runtime_trace(
                self._failure(code="JSON_PARSE_ERROR", message=f"Failed to parse profile JSON: {exc}"),
                context,
            )
        except Exception as exc:
            return self._attach_runtime_trace(self._failure(code="LLM_ERROR", message=str(exc)), context)

    def _parse_json(self, content: str) -> dict:
        """解析 LLM 返回的 JSON 内容。

        处理可能包含 markdown 代码块的格式：
        - 去掉 ```json 前缀和 ``` 后缀
        - 解析为 Python dict

        Args:
            content: LLM 返回的原始文本

        Returns:
            dict: 解析后的数据字典
        """
        text = content.strip()
        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
        return json.loads(text)

    def _normalize_source_preferences(self, value: object) -> list[str]:
        """规范化来源偏好列表。

        确保返回的来源类型是有效的：
        - scholar: 学术论文
        - github: GitHub 项目
        - wechat: 微信公众号
        - web_search: 网页搜索

        同时进行去重处理。

        Args:
            value: LLM 返回的来源偏好（可能是字符串列表或其他格式）

        Returns:
            list[str]: 规范化后的来源偏好列表
        """
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            clean = str(item).strip().lower()
            # 只保留有效来源类型
            if clean not in {"scholar", "github", "wechat", "web_search"}:
                continue
            # 去重
            if clean in seen:
                continue
            seen.add(clean)
            normalized.append(clean)
        return normalized

    def _normalize_research_mode(self, value: object, source_preferences: list[str]) -> str:
        """规范化研究模式设置。

        研究模式决定如何处理学术论文类内容：
        - disabled: 不启用学术内容
        - enabled: 启用学术内容
        - research_first: 优先使用学术内容

        如果 LLM 返回值无效，则根据来源偏好推断。

        Args:
            value: LLM 返回的研究模式值
            source_preferences: 来源偏好列表

        Returns:
            str: 规范化后的研究模式
        """
        clean = str(value or "").strip().lower()
        if clean in {"disabled", "enabled", "research_first"}:
            return clean
        # 如果包含 scholar 来源，则启用研究模式
        return "enabled" if "scholar" in source_preferences else "disabled"

    def _normalize_open_source_mode(self, value: object, source_preferences: list[str]) -> str:
        """规范化开源模式设置。

        开源模式决定如何处理 GitHub/开源项目类内容：
        - disabled: 不启用开源内容
        - enabled: 启用开源内容
        - open_source_first: 优先使用开源内容

        如果 LLM 返回值无效，则根据来源偏好推断。

        Args:
            value: LLM 返回的开源模式值
            source_preferences: 来源偏好列表

        Returns:
            str: 规范化后的开源模式
        """
        clean = str(value or "").strip().lower()
        if clean in {"disabled", "enabled", "open_source_first"}:
            return clean
        # 如果包含 github 来源，则启用开源模式
        return "enabled" if "github" in source_preferences else "disabled"

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        """LLM 调用失败时的降级处理。

        基于账号定位描述中的关键词进行简单推断：
        - 包含"论文"、"学术"等词 → 添加 scholar 来源
        - 包含"github"、"开源"、"开发者"等词 → 添加 github 来源

        Args:
            error: 发生的异常
            input_data: 原始输入数据

        Returns:
            AgentResult: 基于关键词推断的简化画像
        """
        positioning = str(input_data.get("positioning") or "")
        lower = positioning.lower()
        source_preferences: list[str] = []

        # 检测学术关键词
        if any(token in lower for token in ("论文", "学术", "research", "paper", "arxiv", "benchmark")):
            source_preferences.append("scholar")
        # 检测开源/开发者关键词
        if any(token in lower for token in ("github", "开源", "developer", "repo", "项目", "工具")):
            source_preferences.append("github")

        return self._success(
            {
                "domain": "general",
                "subdomain": "general",
                "target_audience": {"age_range": "18-45", "occupation": "general", "interests": []},
                "tone": "neutral",
                "content_style": "analysis",
                "keywords": [],
                "source_preferences": source_preferences,
                "research_mode": "enabled" if "scholar" in source_preferences else "disabled",
                "open_source_mode": "enabled" if "github" in source_preferences else "disabled",
                "positioning_raw": positioning,
            }
        )
