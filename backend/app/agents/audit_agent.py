"""Audit agent: reviews content for risks and compliance.

Calls LLM to audit article content for compliance and quality.
"""

import json
import litellm
from app.agents.base import BaseAgent, AgentResult
from app.core.config import settings


class AuditAgent(BaseAgent):
    agent_id = "audit_agent"
    name = "审核智能体"
    description = "对生成的文章进行风险检测和合规性审核"

    default_system_prompt = """\
你是一位内容合规审核专家，负责对自动生成的公众号文章进行全面的风险检测和质量评估。

## 任务
对生成的文章标题和正文进行合规性审核和质量评估。

## 输入
- titles (object): 候选标题列表
- content (object): 文章正文数据
- profile (object): 账号画像数据

## 输出要求
必须输出 JSON 对象，包含：
- passed (bool): 是否通过审核（true=可发布, false=需修改）
- risk_level (string): 风险等级 "low" / "medium" / "high"
- issues (array): 发现的问题列表，每个包含：
  - type (string): 问题类型（sensitive_word/political_risk/false_info/exaggeration/clickbait/tone_mismatch/quality）
  - description (string): 问题描述
  - severity (string): 严重程度 "low" / "medium" / "high"
  - location (string): 问题位置（如"标题"、"第2段"）
- overall_comment (string): 综合评价，100字以内

## 审核维度
1. **敏感词检测**：政治敏感、违禁词、低俗用语
2. **事实核查**：是否包含可验证的虚假数据或不存在的研究
3. **夸大宣传**：是否有绝对化用语（"最"、"第一"、"100%"等）
4. **标题党程度**：标题是否与正文内容严重不符
5. **调性匹配**：文章风格是否与账号定位(profile.tone)一致
6. **内容质量**：结构完整性、论述逻辑性、可读性

## 约束
- issues 数组为空时 passed 应为 true
- 存在任何 high severity 问题时 passed 必须为 false
- risk_level 取 issues 中最高 severity 等级
- 审核应客观公正，不过度严苛也不放过真正的问题"""

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        profile = input_data.get("profile", {})
        titles_data = input_data.get("titles", {})
        content_data = input_data.get("content", {})
        system_prompt = context.get("system_prompt") or self.default_system_prompt
        user_prompt = self._build_user_prompt(profile, titles_data, content_data)

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

    def _build_user_prompt(self, profile: dict, titles_data: dict, content_data: dict) -> str:
        """构建用户提示词"""
        tone = profile.get("tone", "中性")
        domain = profile.get("domain", "未知")
        title_list = titles_data.get("titles", []) if isinstance(titles_data, dict) else []
        content_md = content_data.get("content_markdown", "") if isinstance(content_data, dict) else ""

        prompt_parts = [
            "请对以下文章进行合规性审核和质量评估。",
            "",
            "## 账号信息",
            f"- 主领域: {domain}",
            f"- 内容调性: {tone}",
        ]

        # 标题信息
        if title_list:
            prompt_parts.append("")
            prompt_parts.append("## 候选标题")
            for t in title_list[:3]:
                prompt_parts.append(f"- {t.get('text', '')}")

        # 文章内容
        if content_md:
            # 限制内容长度，避免超出 token 限制
            content_preview = content_md[:3000] + "..." if len(content_md) > 3000 else content_md
            prompt_parts.append("")
            prompt_parts.append("## 文章正文")
            prompt_parts.append(content_preview)

        prompt_parts.append("")
        prompt_parts.append("请输出审核结果。")

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
            "passed": False,
            "risk_level": "unknown",
            "issues": [{"type": "system", "description": "审核服务异常，请人工复核", "severity": "medium"}],
            "overall_comment": "审核服务降级，建议人工复核后发布。",
        })
