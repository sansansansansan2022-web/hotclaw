"""Profile agent: parses account positioning into structured profile.

Calls LLM to analyze account positioning and return structured JSON.
"""

import json
import litellm
from app.agents.base import BaseAgent, AgentResult
from app.core.config import settings


class ProfileAgent(BaseAgent):
    agent_id = "profile_agent"
    name = "账号定位解析智能体"
    description = "将用户的账号定位描述解析为结构化画像"

    default_system_prompt = """\
你是一位专业的自媒体账号定位分析师，擅长将模糊的自然语言描述转化为精确的结构化画像。

## 任务
根据用户提供的账号定位描述（positioning 字段），解析并输出该账号的结构化画像。

## 输入
- positioning: 用户的自然语言定位描述，例如"关注职场成长的公众号，目标读者25-35岁互联网从业者"

## 输出要求
必须输出严格的 JSON 对象，包含以下字段：
- domain (string): 账号主领域，如"职场成长"、"健康养生"、"美食探店"
- subdomain (string): 细分领域，如"互联网职场"、"中医养生"
- target_audience (object):
  - age_range (string): 目标年龄段，如"25-35"
  - occupation (string): 目标职业，如"互联网从业者"
  - interests (array[string]): 核心兴趣标签，3-5个
- tone (string): 内容调性，如"专业温暖"、"轻松幽默"、"严肃权威"
- content_style (string): 内容风格，如"干货型"、"故事型"、"观点型"
- keywords (array[string]): 账号核心关键词，5-8个

## 约束
- 只基于用户输入进行推断，不臆造无关信息
- 用户未明确提及的字段，根据上下文合理推断并标注
- 输出必须为合法 JSON，不要包含注释或多余文本"""

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        positioning = input_data.get("positioning", "")
        system_prompt = context.get("system_prompt") or self.default_system_prompt
        user_prompt = f"解析以下账号定位：{positioning}"

        try:
            # 阿里云 dashscope 需要用 dashscope 前缀
            model = settings.llm_model_name
            if not model.startswith("dashscope/"):
                model = f"dashscope/{model}"

            response = await litellm.acompletion(
                model=model,
                api_key=settings.llm_api_key,
                base_url=settings.llm_api_base_url,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                timeout=settings.llm_timeout,
                custom_llm_provider="dashscope",
            )
            content = response.choices[0].message.content

            # 解析 JSON，处理 markdown 代码块
            data = self._parse_json(content)
            # 确保原始输入被保留
            data["positioning_raw"] = positioning

            return self._success(data)

        except json.JSONDecodeError as e:
            return self._failure(code="JSON_PARSE_ERROR", message=f"JSON 解析失败: {str(e)}")
        except Exception as e:
            return self._failure(code="LLM_ERROR", message=str(e))

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
        return self._success({
            "domain": "泛资讯",
            "subdomain": "综合",
            "target_audience": {"age_range": "18-45", "occupation": "通用", "interests": []},
            "tone": "中性",
            "content_style": "信息型",
            "keywords": [],
            "positioning_raw": input_data.get("positioning", ""),
        })
