"""Mock hot topic agent: analyzes hot topics relevant to the account profile."""

import asyncio
from app.agents.base import BaseAgent, AgentResult


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
        await asyncio.sleep(1.5)

        data = {
            "hot_topics": [
                {
                    "title": "2026年互联网行业春招趋势分析",
                    "source": "百度热搜",
                    "heat_score": 95,
                    "summary": "今年春招岗位结构变化明显，AI相关岗位增长超200%",
                    "relevance_score": 0.92,
                },
                {
                    "title": "远程办公三年后：企业与员工的新博弈",
                    "source": "微博热搜",
                    "heat_score": 88,
                    "summary": "越来越多企业要求回到办公室，员工如何应对",
                    "relevance_score": 0.85,
                },
                {
                    "title": "35岁程序员转型成功案例引发热议",
                    "source": "知乎热榜",
                    "heat_score": 82,
                    "summary": "前大厂技术负责人分享转型产品经理的经验",
                    "relevance_score": 0.90,
                },
                {
                    "title": "AI工具如何改变职场工作流",
                    "source": "36氪",
                    "heat_score": 78,
                    "summary": "调研显示60%职场人已在日常工作中使用AI工具",
                    "relevance_score": 0.88,
                },
                {
                    "title": "年轻人对加班文化的集体反思",
                    "source": "微博热搜",
                    "heat_score": 75,
                    "summary": "多个社交平台出现反内卷讨论",
                    "relevance_score": 0.80,
                },
            ]
        }
        return self._success(data)

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        return self._success({"hot_topics": []})
