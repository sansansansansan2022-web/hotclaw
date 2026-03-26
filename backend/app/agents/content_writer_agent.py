"""Content writer agent: generates full article content.

Calls LLM to generate complete article based on topic, title, and hot topics.
"""

import json
import litellm
from app.agents.base import BaseAgent, AgentResult
from app.core.config import settings


class ContentWriterAgent(BaseAgent):
    agent_id = "content_writer_agent"
    name = "正文生成智能体"
    description = "根据选题、标题和热点素材生成完整公众号文章"

    default_system_prompt = """\
你是一位专业的微信公众号长文写手，能够根据选题和素材创作出兼具深度和可读性的高质量文章。

## 任务
根据选题、标题、热点素材和账号画像，生成一篇完整的微信公众号文章。

## 输入
- profile (object): 账号画像数据
- topics (object): 选题列表
- titles (object): 标题列表（使用得分最高的标题）
- hot_topics (object): 热点素材

## 输出要求
必须输出 JSON 对象，包含：
- content_markdown (string): 完整文章内容，Markdown 格式
- word_count (int): 文章总字数
- structure (object):
  - sections (array): 文章结构，每个 section 包含 heading 和 summary
- tags (array[string]): 文章标签，4-6个

## 文章结构要求
1. **引言**（100-200字）：用热点数据、个人经历或反常识观点切入，3句话内抓住读者
2. **正文**（1000-2000字）：分 3-5 个小节，每节有清晰的小标题，论据充实
3. **总结/行动建议**（200-300字）：给出明确的观点或可操作建议
4. **结尾**（50-100字）：引导关注、转发或互动

## 约束
- 总字数控制在 1500-3000 字
- 文风必须匹配 profile.tone（如"专业温暖"则避免过于学术化）
- 使用 Markdown 格式：# 大标题、## 小标题、> 引用、**加粗** 等
- 适当使用数据和案例增强说服力
- 段落简短（每段不超过 4 行），适合手机阅读
- 不编造虚假数据或不存在的研究"""

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        profile = input_data.get("profile", {})
        topics = input_data.get("topics", {})
        titles_data = input_data.get("titles", {})
        hot_topics = input_data.get("hot_topics", {})
        system_prompt = context.get("system_prompt") or self.default_system_prompt
        user_prompt = self._build_user_prompt(profile, topics, titles_data, hot_topics)

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

    def _build_user_prompt(self, profile: dict, topics: dict, titles_data: dict, hot_topics: dict) -> str:
        """构建用户提示词"""
        tone = profile.get("tone", "中性")
        domain = profile.get("domain", "未知")
        keywords = profile.get("keywords", [])

        topic_list = topics.get("topics", []) if isinstance(topics, dict) else []
        title_list = titles_data.get("titles", []) if isinstance(titles_data, dict) else []
        hot_list = hot_topics.get("hot_topics", []) if isinstance(hot_topics, dict) else []

        prompt_parts = [
            "请根据以下信息生成一篇完整的微信公众号文章。",
            "",
            "## 账号信息",
            f"- 主领域: {domain}",
            f"- 内容调性: {tone}",
        ]
        if keywords:
            prompt_parts.append(f"- 关键词: {', '.join(keywords)}")

        # 选题信息
        if topic_list:
            sorted_topics = sorted(topic_list, key=lambda x: x.get("estimated_appeal", 0), reverse=True)
            top_topic = sorted_topics[0] if sorted_topics else {}
            prompt_parts.append("")
            prompt_parts.append("## 选中选题")
            prompt_parts.append(f"- 标题: {top_topic.get('title', '')}")
            prompt_parts.append(f"- 切入角度: {top_topic.get('angle', '')}")
            prompt_parts.append(f"- 目标情绪: {top_topic.get('target_emotion', '')}")

        # 候选标题
        if title_list:
            prompt_parts.append("")
            prompt_parts.append("## 候选标题（使用得分最高的）")
            for t in title_list[:3]:
                prompt_parts.append(f"- [{t.get('score', 0):.1f}分] {t.get('text', '')}")

        # 热点素材
        if hot_list:
            prompt_parts.append("")
            prompt_parts.append("## 相关热点素材")
            for i, h in enumerate(hot_list[:3], 1):
                prompt_parts.append(f"{i}. {h.get('title', '')} ({h.get('source', '')})")

        prompt_parts.append("")
        prompt_parts.append("请输出完整的文章内容。")

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
        return self._success({
            "content_markdown": "# 文章生成失败\n\n正文生成过程中出现异常，请重试。",
            "word_count": 0,
            "structure": {"sections": []},
            "tags": [],
        })
