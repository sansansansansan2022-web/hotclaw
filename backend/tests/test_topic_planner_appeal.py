from app.agents.topic_planner_agent import TopicPlannerAgent


def test_topic_planner_accepts_qualitative_llm_appeal():
    result = TopicPlannerAgent()._normalize_topics({
        "topics": [{"title": "Next topic", "estimated_appeal": "high"}]
    })

    assert result["topics"][0]["estimated_appeal"] == 0.8
    assert result["titles"]["selected_title"] == "Next topic"
