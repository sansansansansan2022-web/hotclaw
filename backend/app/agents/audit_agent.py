"""Audit agent: reviews content for risks and evidence grounding."""

# ============================================================================
# 审核 Agent (Audit Agent)
# ============================================================================
# 职责说明：
# - 审核生成的文章内容
# - 检查引用真实性（论文、项目名等是否有证据支撑）
# - 检查夸大宣传（如"顶会"、"最火"等是否合理）
# - 检查内容合规性和语气适当性
# - 评估风险等级并提供改进建议
#
# 协作关系：
# - 输入：标题 (TitleGeneratorAgent)、内容 (ContentWriterAgent)、证据
# - 输出：审核结果（通过/不通过、风险等级、问题列表）
# - 是内容发布的最后一道质量关卡
# ============================================================================

from __future__ import annotations

import json
import re

import litellm

from app.agents.base import AgentResult, BaseAgent
from app.core.config import settings


class AuditAgent(BaseAgent):
    """审核 Agent - 审核内容质量、合规性和引用真实性。

    核心职责：
    1. 检查文章引用的论文/项目是否在证据列表中
    2. 检查夸大宣传语是否合理
    3. 检查内容风格与账号定位的匹配度
    4. 评估整体风险等级（low/medium/high）
    5. 提供问题清单和改进建议

    特点：
    - 启发式检查 + LLM 审查双重保障
    - 风险等级基于问题严重程度自动判定
    - 高严重度问题直接导致不通过
    - 平衡合规性和可读性
    """

    # Agent 唯一标识符
    agent_id = "audit_agent"
    name = "Audit Agent"
    description = "Audit generated content for compliance risks and unsupported evidence claims."

    # 输入数据结构定义
    # titles: 标题候选列表
    # content: 文章内容
    # profile: 账号画像
    # account_context: 账号上下文
    # selected_evidence: 选中的证据
    # citation_guardrails: 引用规范
    input_schema = {
        "type": "object",
        "properties": {
            "titles": {"type": "object"},
            "content": {"type": "object"},
            "profile": {"type": "object"},
            "account_context": {"type": "object"},
            "selected_evidence": {"type": "array"},
            "citation_guardrails": {"type": "object"},
        },
        "required": ["titles", "content", "profile"],
    }

    # 输出数据结构定义
    # passed: 是否通过审核
    # risk_level: 风险等级（low/medium/high）
    # rewrite_required: 是否需要重写
    # publish_decision: pass/rewrite/blocker
    # issues: 问题列表
    # overall_comment: 整体评语
    output_schema = {
        "type": "object",
        "properties": {
            "passed": {"type": "boolean"},
            "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
            "rewrite_required": {"type": "boolean"},
            "publish_decision": {"type": "string", "enum": ["pass", "rewrite", "blocker"]},
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "description": {"type": "string"},
                        "severity": {"type": "string"},
                        "location": {"type": "string"},
                    },
                },
            },
            "overall_comment": {"type": "string"},
        },
    }

    # 该 Agent 不使用任何 Skill
    supported_skills = []

    # 默认系统提示词
    default_system_prompt = """You are a content audit specialist.

Review the generated article and return strict JSON with:
- passed
- risk_level
- issues
- overall_comment

Rules:
- Flag unsupported paper titles or repository names that do not exist in the evidence list.
- Flag claims like 顶会, 顶刊, 高水平, 爆火, state-of-the-art, best, first if the evidence does not support them.
- Balance compliance and readability, but do not let unsupported claims pass.
"""

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        """执行内容审核。

        主要步骤：
        1. 提取输入数据
        2. 执行启发式证据核查
        3. 调用 LLM 进行深度审核
        4. 合并启发式问题和 LLM 问题
        5. 计算风险等级和通过状态

        Args:
            input_data: 包含标题、内容、证据等的输入数据
            context: 执行上下文

        Returns:
            AgentResult: 包含审核结果、问题列表、风险等级
        """
        profile = input_data.get("profile", {})
        titles_data = input_data.get("titles", {})
        content_data = input_data.get("content", {})
        selected_evidence = input_data.get("selected_evidence") or []
        citation_guardrails = input_data.get("citation_guardrails") or {}
        system_prompt = context.get("system_prompt") or self.default_system_prompt

        # 构建审核提示词
        user_prompt = self._build_user_prompt(
            profile=profile,
            titles_data=titles_data,
            content_data=content_data,
            selected_evidence=selected_evidence,
            citation_guardrails=citation_guardrails,
        )

        # 步骤1: 执行启发式证据核查
        # 检查文章中引用的仓库名和论文名是否在证据中
        heuristic_issues = self._detect_grounding_issues(
            content_data,
            selected_evidence,
            citation_guardrails=citation_guardrails,
        )

        try:
            # 步骤2: 调用 LLM 进行深度审核
            response = await self.run_litellm_completion(
                context=context,
                completion_callable=litellm.acompletion,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                timeout=settings.llm_timeout,
            )
            content = response.choices[0].message.content
            data = self._parse_json(content)

            # 步骤3: 合并问题列表
            issues = data.get("issues") if isinstance(data.get("issues"), list) else []
            issues.extend(heuristic_issues)
            data["issues"] = issues

            # 步骤4: 计算风险等级
            data["risk_level"] = self._derive_risk_level(issues)

            # 步骤5: 确定通过状态（高严重度问题导致不通过）
            data["passed"] = not any(issue.get("severity") == "high" for issue in issues)
            data["rewrite_required"] = (not data["passed"]) and data["risk_level"] != "high"
            data["publish_decision"] = (
                "pass"
                if data["passed"]
                else ("blocker" if data["risk_level"] == "high" else "rewrite")
            )

            # 如果有启发式检查发现的问题，在评语中说明
            if heuristic_issues:
                prefix = "Heuristic grounding checks found additional evidence issues. "
                data["overall_comment"] = prefix + str(data.get("overall_comment") or "").strip()

            return self._attach_runtime_trace(self._success(data), context)

        except json.JSONDecodeError as exc:
            # JSON 解析失败时使用启发式检查结果作为降级
            return self._attach_runtime_trace(
                self._success(self._fallback_audit(heuristic_issues, f"Failed to parse audit JSON: {exc}")),
                context,
                fallback_used=True,
            )
        except Exception as exc:
            # 其他异常时也使用启发式检查结果
            return self._attach_runtime_trace(
                self._success(self._fallback_audit(heuristic_issues, str(exc))),
                context,
                fallback_used=True,
            )

    def _build_user_prompt(
        self,
        *,
        profile: dict,
        titles_data: dict,
        content_data: dict,
        selected_evidence: list[dict],
        citation_guardrails: dict[str, bool],
    ) -> str:
        """构建审核提示词。

        整合账号信息、标题、证据和文章内容，
        生成完整的审核指令。

        Args:
            profile: 账号画像
            titles_data: 标题列表
            content_data: 文章内容
            selected_evidence: 选中的证据
            citation_guardrails: 引用规范

        Returns:
            str: 完整的用户提示词
        """
        tone = profile.get("tone", "neutral")
        domain = profile.get("domain", "unknown")
        title_list = titles_data.get("titles", []) if isinstance(titles_data, dict) else []
        content_md = content_data.get("content_markdown", "") if isinstance(content_data, dict) else ""

        # 截取文章预览（最多 5000 字符）
        content_preview = content_md[:5000] + "..." if len(content_md) > 5000 else content_md
        prompt_parts = [
            "Audit the following article.",
            "",
            "ACCOUNT",
            json.dumps({"domain": domain, "tone": tone}, ensure_ascii=False, indent=2),
            "",
            "TITLE CANDIDATES",
            json.dumps(title_list[:4], ensure_ascii=False, indent=2),
            "",
            "SELECTED EVIDENCE",
            json.dumps(selected_evidence[:12], ensure_ascii=False, indent=2),
            "",
            "CITATION GUARDRAILS",
            json.dumps(citation_guardrails, ensure_ascii=False, indent=2),
            "",
            "ARTICLE",
            content_preview,
            "",
            "REQUIREMENTS",
            "- Output strict JSON only.",
            "- Check compliance, exaggeration, tone fit, and unsupported evidence claims.",
        ]
        return "\n".join(prompt_parts)

    def _detect_grounding_issues(
        self,
        content_data: dict,
        selected_evidence: list[dict],
        *,
        citation_guardrails: dict[str, bool] | None = None,
    ) -> list[dict]:
        """启发式证据核查。

        使用正则表达式检测文章中引用的：
        1. GitHub 仓库名（格式：owner/repo）
        2. 论文/书名（用书名号或引号包裹）
        3. 夸大宣传语（顶会、顶刊、SOTA 等）

        Args:
            content_data: 文章内容
            selected_evidence: 选中的证据列表

        Returns:
            list[dict]: 发现的问题列表
        """
        content_md = str((content_data or {}).get("content_markdown") or "")

        # 提取证据中的论文标题集合
        evidence_titles = {
            self._normalize_name(item.get("title"))
            for item in selected_evidence
            if isinstance(item, dict) and self._normalize_name(item.get("title"))
        }

        # 提取证据中的 GitHub 仓库名集合
        evidence_repo_names: set[str] = set()
        for item in selected_evidence:
            if not isinstance(item, dict) or not str(item.get("source_type") or "").startswith("github"):
                continue
            for candidate in self._repo_name_candidates(item):
                normalized = self._normalize_name(candidate)
                if normalized:
                    evidence_repo_names.add(normalized)

        issues: list[dict] = []

        # 检查 GitHub 仓库引用
        # 匹配格式：owner/repo 或 owner/repo-name
        guardrails = citation_guardrails if isinstance(citation_guardrails, dict) else {}
        if guardrails.get("must_ground_repo_names_in_evidence", True):
            repo_mentions = {
                self._normalize_name(match)
                for match in self._extract_repo_mentions(content_md)
                if self._normalize_name(match)
            }
            for repo_name in sorted(repo_mentions):
                # 如果引用的仓库不在证据中，记录问题
                if repo_name not in evidence_repo_names:
                    issues.append(
                        {
                            "type": "unsupported_repo_reference",
                            "description": f"Repository name '{repo_name}' does not appear in selected evidence.",
                            "severity": "medium",
                            "location": "content",
                        }
                    )

        # 检查论文/书名引用
        # 匹配书名号《》或引号""包裹的文本
        title_mentions = {
            self._normalize_name(match)
            for match in re.findall(r"[《""]([^》""]{8,120})[》""]", content_md)
            if self._normalize_name(match)
        }
        for title in sorted(title_mentions):
            # 如果引用的标题不在证据中且不是仓库名，记录问题
            if title not in evidence_titles and "/" not in title:
                issues.append(
                    {
                        "type": "unsupported_paper_reference",
                        "description": f"Quoted title '{title}' does not appear in selected evidence.",
                        "severity": "medium",
                        "location": "content",
                    }
                )

        # 检查夸大宣传语
        # 匹配：顶会、顶刊、高水平、爆火、SOTA、最强、第一等
        if re.search(r"顶会|顶刊|高水平|爆火|state[- ]of[- ]the[- ]art|SOTA|最强|第一", content_md, re.IGNORECASE):
            # 检查是否有权威证据支持
            strong_authority = any(
                isinstance(item, dict) and float(item.get("authority_score") or 0.0) >= 0.85
                for item in selected_evidence
            )
            if not strong_authority:
                issues.append(
                    {
                        "type": "unsupported_hype_claim",
                        "description": "The article uses strong authority or hype claims without strong evidence support.",
                        "severity": "medium",
                        "location": "content",
                    }
                )
        return issues

    def _extract_repo_mentions(self, content_md: str) -> list[str]:
        """Extract explicit ASCII GitHub-style owner/repo mentions.

        Do not use ``\\w`` here: in Python it also matches CJK characters, which
        turns phrases like ``api/sdk的能力`` into fake repository references.
        """

        repo_pattern = re.compile(
            r"(?<![A-Za-z0-9_.-])"
            r"([A-Za-z0-9][A-Za-z0-9_.-]{0,38}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99})"
            r"(?=$|[\s,.;:!?，。；：！？、）)\]}>\"'`])"
        )
        return [match.group(1) for match in repo_pattern.finditer(content_md or "")]

    def _repo_name_candidates(self, item: dict[str, object]) -> list[str]:
        candidates: list[str] = []
        for key in ("source_id", "repo_name", "repository_name", "full_name", "name"):
            value = item.get(key)
            if isinstance(value, str) and "/" in value:
                candidates.append(value)
        for key in ("source_url", "url", "html_url"):
            value = item.get(key)
            if not isinstance(value, str):
                continue
            match = re.search(r"github\.com/([^/\s]+/[^/\s?#]+)", value, flags=re.IGNORECASE)
            if match:
                candidates.append(match.group(1))
        payload = item.get("source_payload") or item.get("source_payload_json")
        if isinstance(payload, dict):
            for key in ("full_name", "repo_name", "repository_name"):
                value = payload.get(key)
                if isinstance(value, str) and "/" in value:
                    candidates.append(value)
        return candidates

    def _fallback_audit(self, heuristic_issues: list[dict], error_message: str) -> dict:
        """审核失败时的降级处理。

        当 LLM 审核不可用时，
        使用启发式检查结果作为审核结论。

        Args:
            heuristic_issues: 启发式检查发现的问题
            error_message: 错误消息

        Returns:
            dict: 基于启发式检查的审核结果
        """
        issues = list(heuristic_issues)
        # 添加系统错误问题
        if error_message:
            issues.append(
                {
                    "type": "audit_runtime_error",
                    "description": f"Audit model failed: {error_message}",
                    "severity": "medium",
                    "location": "system",
                }
            )
        # 计算风险等级
        risk_level = self._derive_risk_level(issues)
        return {
            "passed": not any(issue.get("severity") == "high" for issue in issues),
            "risk_level": risk_level,
            "rewrite_required": risk_level != "high" and bool(issues),
            "publish_decision": "blocker" if risk_level == "high" else ("rewrite" if issues else "pass"),
            "issues": issues,
            "overall_comment": "Audit fell back to deterministic grounding checks.",
        }

    def _derive_risk_level(self, issues: list[dict]) -> str:
        """根据问题严重程度计算风险等级。

        - 包含 high 级别问题 → high
        - 包含 medium 级别问题 → medium
        - 只有 low 或无问题 → low

        Args:
            issues: 问题列表

        Returns:
            str: 风险等级（low/medium/high）
        """
        severities = {str(item.get("severity") or "").lower() for item in issues if isinstance(item, dict)}
        if "high" in severities:
            return "high"
        if "medium" in severities:
            return "medium"
        return "low"

    def _normalize_name(self, value: object) -> str:
        """标准化名称用于比较。

        - 转换为小写
        - 去除多余空白

        Args:
            value: 原始值

        Returns:
            str: 标准化后的名称
        """
        raw = str(value or "").strip().lower()
        return re.sub(r"\s+", " ", raw)

    def _parse_json(self, content: str) -> dict:
        """解析 LLM 返回的 JSON 内容。

        处理可能包含 markdown 代码块的格式。

        Args:
            content: LLM 返回的原始文本

        Returns:
            dict: 解析后的数据字典
        """
        text = content.strip()
        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
        return json.loads(text)

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        """完全失败时的降级处理。

        执行纯启发式检查作为最终审核。

        Args:
            error: 发生的异常
            input_data: 原始输入数据

        Returns:
            AgentResult: 基于启发式检查的审核结果
        """
        # 执行启发式证据核查
        heuristic_issues = self._detect_grounding_issues(
            input_data.get("content") or {},
            input_data.get("selected_evidence") or [],
            citation_guardrails=input_data.get("citation_guardrails") or {},
        )
        result = self._success(self._fallback_audit(heuristic_issues, str(error)))
        result.runtime_trace = {
            "provider": None,
            "model": None,
            "latency_seconds": None,
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "retry_count": 0,
            "fallback_used": True,
            "error_class": self._classify_llm_error(error),
            "error_message": str(error),
        }
        return result
