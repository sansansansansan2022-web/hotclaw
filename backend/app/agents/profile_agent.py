"""Profile agent: parses account positioning into structured profile.

Calls LLM to analyze account positioning and return structured JSON.
"""

import json

from app.agents.base import BaseAgent, AgentResult
from app.llm import (
    LLMGateway,
    LLMCallOptions,
    LLMTimeoutError,
    LLMAPIError,
    LLMCallError,
)
from app.core.logger import get_logger

logger = get_logger(__name__)


class ProfileAgent(BaseAgent):
    agent_id = "profile_agent"
    name = "账号定位解析智能体"
    description = "将用户的账号定位描述解析为结构化画像"

    default_system_prompt = """\
你是一位专业的自媒体账号定位分析师，能够准确理解用户的定位描述，并将其转化为清晰、可操作的结构化画像。

## 任务
将用户提供的账号定位描述解析为标准化的账号画像。

## 输入
- positioning (string): 用户描述的账号定位，如"职场成长号，目标读者25-35岁互联网从业者"

## 输出要求
必须输出严格的 JSON 对象，包含以下字段：
- domain (string): 账号主领域，如"职场成长"、"美食探店"、"科技数码"等
- subdomain (string): 更细分的子领域，如"互联网职场"、"餐厅推荐"、"AI工具"等
- target_audience (object): 目标受众画像，包含：
  - age_range (string): 年龄范围，如"18-25"、"25-35"、"35-45"等
  - occupation (string): 职业/身份描述
  - interests (array[string]): 兴趣标签列表
- tone (string): 内容调性，如"专业温暖"、"轻松幽默"、"严肃深度"等
- content_style (string): 内容风格，如"干货型"、"故事型"、"资讯型"等
- keywords (array[string]): 内容关键词，5-10个

## 约束
- domain 必须是一个清晰的领域名称，不要过于笼统或宽泛
- subdomain 应体现账号的特色和差异化定位
- target_audience 的描述要具体，避免"所有人"这样的模糊表述
- keywords 应能准确反映内容主题
- 如果用户描述过于模糊，请基于常理推断合理画像"""

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        # 使用统一的 LLM Gateway
        self._llm_gateway = LLMGateway()

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        positioning = input_data.get("positioning", "")
        system_prompt = context.get("system_prompt") or self.default_system_prompt
        user_prompt = f"解析以下账号定位：{positioning}"

        try:
            # 通过 LLMGateway 调用，不暴露底层细节
            response = await self._llm_gateway.complete(
                agent_id=self.agent_id,
                prompt=user_prompt,
                options=LLMCallOptions(
                    system_prompt=system_prompt,
                    temperature=0.7,
                ),
                provider="dashscope",
            )

            content = response.content

            # 解析 JSON，处理 markdown 代码块
            data = self._parse_json(content)
            # 确保原始输入被保留
            data["positioning_raw"] = positioning

            logger.info(
                "profile_agent_success",
                positioning=positioning,
                model=response.model,
                latency_ms=response.latency_ms,
            )

            return self._success(data)

        except LLMTimeoutError as e:
            logger.error(
                "profile_agent_timeout",
                positioning=positioning,
                timeout=e.details.get("timeout_seconds"),
                latency_ms=e.details.get("latency_ms"),
            )
            return self._failure(
                code="LLM_TIMEOUT",
                message=f"LLM 调用超时: {e.message}",
            )

        except LLMAPIError as e:
            logger.error(
                "profile_agent_api_error",
                positioning=positioning,
                error=e.message,
                status_code=e.details.get("status_code"),
            )
            return self._failure(
                code="LLM_API_ERROR",
                message=f"LLM API 调用失败: {e.message}",
            )

        except json.JSONDecodeError as e:
            logger.error(
                "profile_agent_json_parse_error",
                positioning=positioning,
                error=str(e),
            )
            return self._failure(
                code="JSON_PARSE_ERROR",
                message=f"JSON 解析失败: {str(e)}",
            )

        except LLMCallError as e:
            logger.error(
                "profile_agent_llm_error",
                positioning=positioning,
                error_type=type(e).__name__,
                error=e.message,
            )
            return self._failure(
                code="LLM_ERROR",
                message=f"LLM 调用错误: {e.message}",
            )

        except Exception as e:
            logger.error(
                "profile_agent_unexpected_error",
                positioning=positioning,
                error_type=type(e).__name__,
                error=str(e),
                exc_info=True,
            )
            return self._failure(
                code="UNEXPECTED_ERROR",
                message=f"Unexpected error: {str(e)}",
            )

    def _parse_json(self, content: str) -> dict:
        """解析 LLM 返回的 JSON，处理 markdown 代码块"""
        content = content.strip()
        # 移除 markdown 代码块
        if content.startswith("```"):
            parts = content.split("```")
            if len(parts) >= 2:
                content = parts[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
        return json.loads(content)

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        """降级策略：返回默认泛化画像"""
        positioning = input_data.get("positioning", "")
        logger.warning(
            "profile_agent_fallback",
            positioning=positioning,
            error_type=type(error).__name__,
            error=str(error),
        )
        return self._success({
            "domain": "泛资讯",
            "subdomain": "综合",
            "target_audience": {
                "age_range": "18-45",
                "occupation": "通用",
                "interests": [],
            },
            "tone": "中性",
            "content_style": "资讯型",
            "keywords": [],
            "positioning_raw": positioning,
        })
