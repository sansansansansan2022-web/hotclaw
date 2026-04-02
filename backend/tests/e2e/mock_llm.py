"""Mock LLM responses for E2E testing.

【E2E 测试 Mock】
提供确定性的 LLM 响应，确保测试结果可重复、稳定。
"""

import json
from typing import Any


# =============================================================================
# Mock LLM Response Structures
# =============================================================================

def get_mock_profile_response(positioning: str) -> dict:
    """Mock response for ProfileAgent."""
    return {
        "domain": "职场成长",
        "subdomain": "互联网职场",
        "target_audience": {
            "age_range": "25-35",
            "occupation": "互联网从业者",
            "interests": ["职业发展", "技能提升", "职场人际"]
        },
        "tone": "专业温暖",
        "content_style": "干货型",
        "keywords": ["职场", "成长", "互联网", "技能", "晋升"],
        "positioning_raw": positioning
    }


def get_mock_hot_topics_response(profile: dict) -> dict:
    """Mock response for HotTopicAgent."""
    return {
        "topics": [
            {
                "rank": 1,
                "topic": "AI时代职场人的核心竞争力",
                "热度指数": 95,
                "related_keywords": ["AI", "职场", "竞争力"],
                "source": "微博热搜"
            },
            {
                "rank": 2,
                "topic": "远程办公对团队协作的影响",
                "热度指数": 85,
                "related_keywords": ["远程办公", "团队协作"],
                "source": "知乎热榜"
            },
            {
                "rank": 3,
                "topic": "2024年程序员就业趋势分析",
                "热度指数": 80,
                "related_keywords": ["程序员", "就业", "趋势"],
                "source": "脉脉"
            }
        ],
        "summary": f"针对{profile.get('domain', '职场')}领域的3个热点话题"
    }


def get_mock_topics_response(profile: dict, hot_topics: dict) -> dict:
    """Mock response for TopicPlannerAgent."""
    topics = hot_topics.get("topics", [])
    selected = topics[0] if topics else {}

    return {
        "selected_topic": selected.get("topic", "职场成长主题"),
        "topic_reason": f"这个话题契合{profile.get('domain')}领域，目标受众关注度高",
        "content_angle": "从实用角度出发，提供可操作的建议",
        "target_word_count": 2000,
        "outline": {
            "开头": "以一个职场故事引入话题",
            "主体": [
                "第一点：核心观点阐述",
                "第二点：具体案例分析",
                "第三点：实操方法论"
            ],
            "结尾": "总结要点，呼吁行动"
        },
        "candidates": [
            selected.get("topic", "职场成长主题"),
            f"如何在{profile.get('subdomain')}中脱颖而出",
            f"{profile.get('target_audience', {}).get('occupation', '职场人')}的成长指南"
        ]
    }


def get_mock_titles_response(profile: dict, topics: dict) -> dict:
    """Mock response for TitleGeneratorAgent."""
    selected_topic = topics.get("selected_topic", "职场成长")

    return {
        "selected_title": f"深度好文 | {selected_topic}的底层逻辑",
        "candidates": [
            f"深度好文 | {selected_topic}的底层逻辑",
            f"一篇讲透{selected_topic}的万字长文",
            f"{profile.get('target_audience', {}).get('occupation', '职场人')}必看：{selected_topic}",
            f"关于{selected_topic}，我想说几句真心话",
            f"别再踩坑了！{selected_topic}的正确姿势"
        ],
        "title_analysis": {
            "selected": "使用了专业感+好奇心的组合，适合职场读者"
        }
    }


def get_mock_content_response(profile: dict, topics: dict, titles: dict, hot_topics: dict) -> dict:
    """Mock response for ContentWriterAgent."""
    selected_title = titles.get("selected_title", "职场成长主题")
    selected_topic = topics.get("selected_topic", "职场成长")

    content = f"""# {selected_title}

## 引言

在当今快速变化的职场环境中，我们每个人都面临着前所未有的挑战和机遇。

## 正文

### 一、为什么这个问题值得关注

{selected_topic}是当前{profile.get('domain')}领域最受关注的话题之一。根据行业报告数据显示，越来越多{profile.get('target_audience', {}).get('occupation', '从业者')}开始重视这一领域的发展。

### 二、核心观点分析

**观点一：建立正确的认知框架**

很多人在职业发展过程中，往往忽略了最基本的原则。只有建立起正确的认知框架，才能在复杂的职场环境中做出正确决策。

**观点二：注重实践与方法论**

理论知识固然重要，但更重要的是将知识转化为实际行动。本文中介绍的方法论都是经过实践验证的。

### 三、具体行动建议

1. **持续学习**：保持好奇心，不断更新知识结构
2. **建立人脉**：主动拓展职场关系网络
3. **总结复盘**：定期回顾自己的成长轨迹

## 结语

希望这篇文章能帮助大家更好地理解{selected_topic}。记住，职场成长是一个持续的过程，需要我们保持耐心和毅力。

---

*本文由 HotClaw AI 内容创作平台生成*
"""

    return {
        "content_markdown": content,
        "content_html": f"<h1>{selected_title}</h1><p>内容已生成...</p>",
        "summary": f"探讨{selected_topic}的核心逻辑，为{profile.get('target_audience', {}).get('occupation')}提供实用建议",
        "word_count": 800,
        "tags": [profile.get("domain"), "职场成长", "实用建议"],
        "structure": ["引言", "正文", "结语"],
        "reading_time_minutes": 4
    }


def get_mock_audit_response(titles: dict, content: dict, profile: dict) -> dict:
    """Mock response for AuditAgent."""
    return {
        "passed": True,
        "risk_level": "low",
        "overall_comment": "内容质量良好，符合账号定位，建议发布",
        "issues": [],
        "suggestions": [
            "可以考虑增加一些互动性问题引导读者评论",
            "配图建议使用与主题相关的职场场景图片"
        ],
        "score": 85
    }


# =============================================================================
# Mock LLM Response Router
# =============================================================================

def get_mock_llm_response(agent_id: str, messages: list, **kwargs) -> dict:
    """
    Router that returns appropriate mock response based on agent_id.

    Args:
        agent_id: The agent identifier (e.g., "dashscope/qwen-turbo")
        messages: List of messages sent to LLM

        Returns:
            Mock response object (compatible with litellm response format)
    """
    # Extract the last user message for context
    user_message = ""
    system_message = ""
    for msg in messages:
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
        elif msg.get("role") == "system":
            system_message = msg.get("content", "")

    # Determine which agent is calling based on system prompt keywords
    if "账号定位" in system_message or "positioning" in user_message.lower():
        # Profile Agent
        positioning = user_message.replace("解析以下账号定位：", "").strip()
        data = get_mock_profile_response(positioning)
        content = json.dumps(data, ensure_ascii=False)
    elif "热点" in system_message or "hot_topic" in system_message.lower():
        # Hot Topic Agent - needs profile context
        data = get_mock_hot_topics_response({})
        content = json.dumps(data, ensure_ascii=False)
    elif "选题" in system_message or "topic" in system_message.lower():
        # Topic Planner Agent
        data = get_mock_topics_response({}, {})
        content = json.dumps(data, ensure_ascii=False)
    elif "标题" in system_message or "title" in system_message.lower():
        # Title Generator Agent
        data = get_mock_titles_response({}, {})
        content = json.dumps(data, ensure_ascii=False)
    elif "正文" in system_message or "content" in system_message.lower() or "文章" in system_message:
        # Content Writer Agent
        data = get_mock_content_response({}, {}, {}, {})
        content = json.dumps(data, ensure_ascii=False)
    elif "审核" in system_message or "audit" in system_message.lower():
        # Audit Agent
        data = get_mock_audit_response({}, {}, {})
        content = json.dumps(data, ensure_ascii=False)
    else:
        # Default fallback
        data = {"result": "mock_response", "input": user_message[:100]}
        content = json.dumps(data, ensure_ascii=False)

    # Return mock response object (compatible with litellm)
    return MockLLMResponse(content)


class MockLLMResponse:
    """Mock litellm completion response."""

    def __init__(self, content: str):
        self.choices = [MockChoice(content)]
        self.usage = MockUsage()


class MockChoice:
    def __init__(self, content: str):
        self.message = MockMessage(content)


class MockMessage:
    def __init__(self, content: str):
        self.content = content


class MockUsage:
    def __init__(self):
        self.prompt_tokens = 100
        self.completion_tokens = 200
        self.total_tokens = 300
