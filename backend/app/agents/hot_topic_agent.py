"""Hot topic agent: analyzes hot topics relevant to the account profile.

Calls LLM to fetch and analyze hot topics based on account profile.
"""

import json
import litellm
from app.agents.base import BaseAgent, AgentResult
from app.core.config import settings


class HotTopicAgent(BaseAgent):
    agent_id = "hot_topic_agent"
    name = "热点分析智能体"
    description = "从多个来源抓取并分析与账号领域相关的热点"

    default_system_prompt = """\
你是一位精通中文互联网生态的热点分析师，能够从海量信息中筛选出与特定账号领域高度相关的热点话题。

## 任务
根据账号画像（profile），从百度热搜、微博热搜、知乎热榜、36氪等平台筛选与账号领域相关的热点话题。

## 输入
- profile (object): 账号画像数据，包含 domain、subdomain、target_audience、tone 等字段

## 输出要求
必须输出 JSON 对象，包含：
- hot_topics (array): 5-8 条热点，每条包含：
  - title (string): 热点标题
  - source (string): 来源平台（百度热搜/微博热搜/知乎热榜/36氪/抖音等）
  - heat_score (int): 热度评分 0-100
  - summary (string): 热点摘要，50字以内
  - relevance_score (float): 与账号领域的相关度 0-1

## 约束
- 只选择与账号领域确实相关的热点，relevance_score 低于 0.5 的不要纳入
- 按 heat_score * relevance_score 降序排列
- 热点来源需多样化，不要全部来自同一平台
- 摘要需客观精炼，不加主观判断"""

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        profile = input_data.get("profile", {})
        system_prompt = context.get("system_prompt") or self.default_system_prompt
        user_prompt = self._build_user_prompt(profile)

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

            # 解析 JSON
            data = self._parse_json(content)
            return self._success(data)

        except json.JSONDecodeError as e:
            return self._failure(code="JSON_PARSE_ERROR", message=f"JSON 解析失败: {str(e)}")
        except Exception as e:
            return self._failure(code="LLM_ERROR", message=str(e))

    def _build_user_prompt(self, profile: dict) -> str:
        """构建用户提示词"""
        domain = profile.get("domain", "未知")
        subdomain = profile.get("subdomain", "")
        target_audience = profile.get("target_audience", {})
        keywords = profile.get("keywords", [])

        prompt_parts = [
            f"请分析与我账号领域相关的热点话题。",
            f"",
            f"## 账号信息",
            f"- 主领域: {domain}",
            f"- 细分领域: {subdomain}",
            f"- 目标人群: {target_audience.get('occupation', '通用')}",
            f"- 年龄段: {target_audience.get('age_range', '未知')}",
        ]

        if keywords:
            prompt_parts.append(f"- 关键词: {', '.join(keywords)}")

        prompt_parts.append("")
        prompt_parts.append("请输出与该领域相关的热点话题分析。")

        return "\n".join(prompt_parts)

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
        return self._success({"hot_topics": []})
