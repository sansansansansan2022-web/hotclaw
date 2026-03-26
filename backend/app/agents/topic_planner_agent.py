"""Topic planner agent: generates candidate topics from profile and hot topics.

Calls LLM to create topic proposals based on account profile and hot topics.
"""

import json
import litellm
from app.agents.base import BaseAgent, AgentResult
from app.core.config import settings


class TopicPlannerAgent(BaseAgent):
    agent_id = "topic_planner_agent"
    name = "选题策划智能体"
    description = "根据账号画像和热点生成候选选题"

    default_system_prompt = """\
你是一位资深自媒体选题策划专家，擅长结合账号定位和热点趋势，策划出兼具传播力和用户价值的选题方案。

## 任务
综合账号画像和当前热点话题，策划 3-5 个有传播潜力的公众号选题。

## 输入
- profile (object): 账号画像数据
- hot_topics (object): 当前热点列表

## 输出要求
必须输出 JSON 对象，包含：
- topics (array): 3-5 个选题，每个包含：
  - title (string): 选题标题（即文章主题方向）
  - angle (string): 切入角度说明
  - hook (string): 吸引读者的钩子类型（如"恐惧+自检"、"案例+希望"、"时效+实用"）
  - target_emotion (string): 目标触发情绪（如焦虑感、希望感、好奇心）
  - estimated_appeal (float): 预估吸引力 0-1
  - reasoning (string): 选题理由，说明为什么这个选题适合该账号

## 约束
- 选题必须同时匹配账号调性（profile.tone）和目标受众（profile.target_audience）
- 每个选题的 hook 策略应不同，提供多样化选择
- 优先选择与高热度、高相关度热点关联的选题
- estimated_appeal 评分需基于热度、相关性、情绪驱动力综合判断
- 按 estimated_appeal 降序排列"""

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        profile = input_data.get("profile", {})
        hot_topics = input_data.get("hot_topics", {})
        system_prompt = context.get("system_prompt") or self.default_system_prompt
        user_prompt = self._build_user_prompt(profile, hot_topics)

        try:
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

    def _build_user_prompt(self, profile: dict, hot_topics: dict) -> str:
        """构建用户提示词"""
        domain = profile.get("domain", "未知")
        subdomain = profile.get("subdomain", "")
        tone = profile.get("tone", "中性")
        target_audience = profile.get("target_audience", {})
        keywords = profile.get("keywords", [])

        topics_list = hot_topics.get("hot_topics", []) if isinstance(hot_topics, dict) else []

        prompt_parts = [
            "请根据以下信息策划 3-5 个有传播潜力的选题。",
            "",
            "## 账号信息",
            f"- 主领域: {domain}",
            f"- 细分领域: {subdomain}",
            f"- 内容调性: {tone}",
            f"- 目标人群: {target_audience.get('occupation', '通用')}",
        ]

        if keywords:
            prompt_parts.append(f"- 关键词: {', '.join(keywords)}")

        if topics_list:
            prompt_parts.append("")
            prompt_parts.append("## 当前热点")
            for i, topic in enumerate(topics_list[:5], 1):
                title = topic.get("title", "")
                source = topic.get("source", "")
                heat = topic.get("heat_score", 0)
                relevance = topic.get("relevance_score", 0)
                prompt_parts.append(f"{i}. {title} (来源: {source}, 热度: {heat}, 相关度: {relevance})")

        prompt_parts.append("")
        prompt_parts.append("请输出选题策划方案。")

        return "\n".join(prompt_parts)

    def _parse_json(self, content: str) -> dict:
        """解析 LLM 返回的 JSON，处理 markdown 代码块"""
        content = content.strip()
        if content.startswith("```"):
            parts = content.split("```")
            if len(parts) >= 2:
                content = parts[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
        return json.loads(content)

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        # Use hot topics directly as topics
        hot_topics = input_data.get("hot_topics", {})
        topics_list = hot_topics.get("hot_topics", []) if isinstance(hot_topics, dict) else []
        fallback_topics = [
            {
                "title": t.get("title", ""),
                "angle": "直接引用热点",
                "hook": "热点",
                "target_emotion": "好奇",
                "estimated_appeal": 0.5,
                "reasoning": "降级策略：直接使用热点标题",
            }
            for t in topics_list[:3]
        ]
        return self._success({"topics": fallback_topics})
