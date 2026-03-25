"""Mock title generator agent: generates candidate titles for each topic."""

import asyncio
from app.agents.base import BaseAgent, AgentResult


class TitleGeneratorAgent(BaseAgent):
    agent_id = "title_generator_agent"
    name = "标题生成智能体"
    description = "为选题生成多个候选标题并评分"

    default_system_prompt = """\
你是一位精通微信公众号爆款标题的写作专家，深谙读者点击心理和平台推荐机制。

## 任务
为估计吸引力最高的候选选题生成 4-6 个风格各异的候选标题，并给出评分和理由。

## 输入
- profile (object): 账号画像数据
- topics (object): 候选选题列表（选择 estimated_appeal 最高的选题）

## 输出要求
必须输出 JSON 对象，包含：
- selected_topic (string): 选中的选题标题
- titles (array): 4-6 个候选标题，每个包含：
  - text (string): 标题文本，长度 15-30 字
  - style (string): 标题风格类型（悬念型/数字型/故事型/反问型/警告型/实用型）
  - score (float): 标题评分 1-10
  - reasoning (string): 评分理由，说明该标题的吸引力所在

## 约束
- 标题必须符合账号调性（profile.tone），不要过度标题党
- 长度控制在 15-30 个中文字符
- 风格需多样化，至少覆盖 3 种不同类型
- 不使用误导性、虚假性标题
- 按 score 降序排列
- 评分标准：好奇心激发度(30%)、与内容匹配度(25%)、情绪驱动力(25%)、可信度(20%)"""

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        await asyncio.sleep(1.0)

        topics = input_data.get("topics", {})
        topic_list = topics.get("topics", []) if isinstance(topics, dict) else []
        first_topic_title = topic_list[0]["title"] if topic_list else "默认选题"

        data = {
            "selected_topic": first_topic_title,
            "titles": [
                {
                    "text": "AI工具正在淘汰这5类职场技能，你中了几个？",
                    "style": "恐惧驱动型",
                    "score": 8.5,
                    "reasoning": "数字+自检式提问，激发好奇心和焦虑感",
                },
                {
                    "text": "别再埋头苦干了！2026年这些技能已经不值钱",
                    "style": "警告型",
                    "score": 8.2,
                    "reasoning": "否定式开头+时间限定，制造紧迫感",
                },
                {
                    "text": "同事偷偷用AI后，我才发现自己落后了3年",
                    "style": "故事型",
                    "score": 7.8,
                    "reasoning": "第一人称叙事，制造差距感",
                },
                {
                    "text": "ChatGPT能做的事，你还在手动做？职场人必看",
                    "style": "实用提醒型",
                    "score": 7.5,
                    "reasoning": "具体工具名+反问，直接且实用",
                },
            ],
        }
        return self._success(data)

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        topics = input_data.get("topics", {})
        topic_list = topics.get("topics", []) if isinstance(topics, dict) else []
        title = topic_list[0]["title"] if topic_list else "默认标题"
        return self._success({
            "selected_topic": title,
            "titles": [{"text": title, "style": "default", "score": 5.0, "reasoning": "降级：直接使用选题标题"}],
        })
