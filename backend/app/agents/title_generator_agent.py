"""Title generator agent: generates candidate titles for each topic.

Calls LLM to generate and score title proposals.
"""

import json
import litellm
from app.agents.base import BaseAgent, AgentResult
from app.core.config import settings


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
        profile = input_data.get("profile", {})
        topics = input_data.get("topics", {})
        topic_list = topics.get("topics", []) if isinstance(topics, dict) else []
        system_prompt = context.get("system_prompt") or self.default_system_prompt
        user_prompt = self._build_user_prompt(profile, topic_list)

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

    def _build_user_prompt(self, profile: dict, topic_list: list) -> str:
        """构建用户提示词"""
        tone = profile.get("tone", "中性")
        domain = profile.get("domain", "未知")

        prompt_parts = [
            "请为以下选题生成 4-6 个候选标题。",
            "",
            "## 账号信息",
            f"- 主领域: {domain}",
            f"- 内容调性: {tone}",
        ]

        if topic_list:
            # 选择吸引力最高的选题
            sorted_topics = sorted(topic_list, key=lambda x: x.get("estimated_appeal", 0), reverse=True)
            prompt_parts.append("")
            prompt_parts.append("## 候选选题（按吸引力降序）")
            for i, topic in enumerate(sorted_topics[:3], 1):
                title = topic.get("title", "")
                appeal = topic.get("estimated_appeal", 0)
                hook = topic.get("hook", "")
                prompt_parts.append(f"{i}. {title} (预估吸引力: {appeal:.2f}, 钩子类型: {hook})")

        prompt_parts.append("")
        prompt_parts.append("请输出标题方案。")

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
        topics = input_data.get("topics", {})
        topic_list = topics.get("topics", []) if isinstance(topics, dict) else []
        title = topic_list[0]["title"] if topic_list else "默认标题"
        return self._success({
            "selected_topic": title,
            "titles": [{"text": title, "style": "default", "score": 5.0, "reasoning": "降级：直接使用选题标题"}],
        })
