"""Mock content writer agent: generates full article content."""

import asyncio
from app.agents.base import BaseAgent, AgentResult


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
        await asyncio.sleep(2.0)

        titles_data = input_data.get("titles", {})
        title_list = titles_data.get("titles", []) if isinstance(titles_data, dict) else []
        chosen_title = title_list[0]["text"] if title_list else "AI工具正在淘汰这5类职场技能"

        content_md = f"""# {chosen_title}

> 这是一个关于职场技能迭代的深度思考。

## 引言

最近刷到一条热搜："60%的职场人已经在日常工作中使用AI工具。"

看到这个数字，我第一反应是：剩下的40%还好吗？

作为一个在互联网行业摸爬滚打多年的人，我想和大家聊聊，AI浪潮下，哪些技能正在贬值，而我们又该如何应对。

## 一、基础数据处理能力

曾几何时，"会做Excel"是职场硬通货。但现在，AI工具可以在几秒内完成过去需要半天的数据整理工作。

**不是说Excel没用了，而是"只会Excel"已经不够了。**

## 二、简单的信息搜集和整理

以前，能快速搜集行业信息、整理竞品资料的人很抢手。现在，AI可以在分钟级完成这些工作，而且覆盖面更广。

## 三、标准化文案撰写

通知、周报、常规营销文案……这些标准化写作正在被AI大幅替代。

## 四、基础翻译能力

AI翻译的质量已经能满足90%的日常需求。

## 五、简单的代码编写

GitHub Copilot等工具让"写CRUD"变成了AI的基本功。

## 那我们该怎么办？

别慌。被淘汰的是"技能"，不是"人"。

关键是要从"执行者"转变为"决策者"和"创意者"：

1. **培养判断力**——AI给你10个方案，你要能选出最好的那个
2. **提升提问能力**——会用AI工具的人，本质上是"会提问的人"
3. **深耕领域专业性**——AI是通才，人要做专家
4. **强化人际协作**——这是AI暂时替代不了的

## 最后

与其焦虑AI会不会替代你，不如想想：你能不能借助AI，变成一个更强的你？

**职场的终极竞争力，从来不是某个技能，而是持续学习和适应变化的能力。**

---

*关注我，一起在职场中持续成长。*
"""

        data = {
            "content_markdown": content_md,
            "word_count": len(content_md),
            "structure": {
                "sections": [
                    {"heading": "引言", "summary": "用数据和个人感受引入话题"},
                    {"heading": "五类正在贬值的技能", "summary": "逐一分析被AI替代的技能"},
                    {"heading": "应对策略", "summary": "给出4个转型建议"},
                    {"heading": "结尾", "summary": "正向激励收尾"},
                ]
            },
            "tags": ["职场", "AI", "技能", "成长"],
        }
        return self._success(data)

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        return self._success({
            "content_markdown": "# 文章生成失败\n\n正文生成过程中出现异常，请重试。",
            "word_count": 0,
            "structure": {"sections": []},
            "tags": [],
        })
