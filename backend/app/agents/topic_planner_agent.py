"""Mock topic planner agent: generates candidate topics from profile and hot topics."""

import asyncio
from app.agents.base import BaseAgent, AgentResult


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
        await asyncio.sleep(1.2)

        data = {
            "topics": [
                {
                    "title": "AI工具正在淘汰这5类职场技能，你中了几个？",
                    "angle": "从AI工具普及的角度切入，分析哪些技能正在被替代",
                    "hook": "恐惧+自检",
                    "target_emotion": "焦虑感",
                    "estimated_appeal": 0.92,
                    "reasoning": "AI话题热度高，结合职场定位，恐惧驱动型标题点击率高",
                },
                {
                    "title": "35岁转型不是终点：3个成功案例告诉你真相",
                    "angle": "正面案例解读，消解年龄焦虑",
                    "hook": "案例+希望",
                    "target_emotion": "希望感",
                    "estimated_appeal": 0.88,
                    "reasoning": "35岁话题持续热门，正面解读差异化，目标受众年龄匹配",
                },
                {
                    "title": "春招季：互联网人跳槽前必须想清楚的3件事",
                    "angle": "从春招热点切入，给出实用建议",
                    "hook": "时效+实用",
                    "target_emotion": "理性决策",
                    "estimated_appeal": 0.85,
                    "reasoning": "春招时效性强，实用型内容转发率高",
                },
            ]
        }
        return self._success(data)

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
