"""Mock audit agent: reviews content for risks and compliance."""

import asyncio
from app.agents.base import BaseAgent, AgentResult


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
        await asyncio.sleep(0.8)

        data = {
            "passed": True,
            "risk_level": "low",
            "issues": [],
            "overall_comment": "内容整体合规，未发现敏感词或违规内容。文章结构完整，论述合理。",
        }
        return self._success(data)

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        return self._success({
            "passed": False,
            "risk_level": "unknown",
            "issues": [{"type": "system", "description": "审核服务异常，请人工复核", "severity": "medium"}],
            "overall_comment": "审核服务降级，建议人工复核后发布。",
        })
