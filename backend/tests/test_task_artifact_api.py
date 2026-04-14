from __future__ import annotations

from app.models.tables import AccountModel, TaskModel, TaskNodeRunModel


async def test_task_artifacts_and_effective_input_contract(client, db_session):
    account = AccountModel(
        id="acct_task_artifacts",
        name="Task Artifact Account",
        positioning="A technology account focused on AI tooling, developer workflow, and product judgment.",
        operation_mode="manual",
        auto_run_enabled=False,
        auto_publish_enabled=False,
        is_active=True,
    )
    task = TaskModel(
        id="task_artifact_contract",
        account_id=account.id,
        workflow_id="default_pipeline",
        status="completed",
        input_data={
            "positioning": account.positioning,
            "selection_session_id": "css_artifact_demo",
            "selected_recommendations": [
                {
                    "id": "rec_1",
                    "title": "OpenCLI: AI agent in the terminal",
                }
            ],
            "selected_reference_sources": [
                {
                    "id": 7,
                    "name": "OpenAI Blog",
                }
            ],
            "compose_preview": {
                "selection_session": {"id": "css_artifact_demo"},
                "outline_preview": {"summary": "Explain why terminal agents now matter."},
            },
            "query_plan": {
                "lane": {"id": "ai_tools", "label": "AI Tools"},
                "primary_queries": ["OpenCLI AI agent terminal"],
                "selected_topic": "Why terminal AI agents finally matter",
                "selected_title": "Why terminal AI agents finally matter",
            },
            "reference_digest": {
                "summary": "Use GitHub evidence plus account references.",
                "preferred_source_names": ["GitHub", "OpenAI Blog"],
            },
            "outline_seed": {
                "summary": "Explain why terminal agents now matter.",
                "sections": [
                    {
                        "section_id": "s1",
                        "heading": "Why now",
                        "purpose": "Frame the shift.",
                        "key_points": ["Adoption is now real."],
                        "evidence_refs": ["rec_1"],
                    }
                ],
            },
            "creation_note": "Focus on operator workflow and adoption boundary.",
            "selected_evidence": [
                {"id": "rec_1", "title": "OpenCLI: AI agent in the terminal"}
            ],
            "external_evidence": {
                "selected_evidence": [
                    {"id": "rec_1", "title": "OpenCLI: AI agent in the terminal"}
                ]
            },
        },
        result_data={
            "profile": {
                "positioning_raw": account.positioning,
                "domain": "technology",
                "target_audience": {"occupation": "developers"},
            },
            "query_plan": {
                "lane": {
                    "id": "ai_tools",
                    "label": "AI Tools",
                    "reason": "Matches the account's strongest lane.",
                },
                "primary_queries": ["OpenCLI AI agent terminal"],
                "selected_topic": "Why terminal AI agents finally matter",
                "selected_title": "Why terminal AI agents finally matter",
            },
            "source_candidates": [
                {
                    "source_id": "rec_1",
                    "source_title": "OpenCLI: AI agent in the terminal",
                    "source_type": "github_repo",
                    "source_name": "GitHub",
                    "fit_score": 0.88,
                }
            ],
            "reference_digest": {
                "summary": "Use GitHub evidence plus account references.",
                "style_takeaways": ["Lead with judgment"],
                "preferred_source_names": ["GitHub", "OpenAI Blog"],
            },
            "selected_evidence": [
                {"id": "rec_1", "title": "OpenCLI: AI agent in the terminal"}
            ],
            "hot_topics": {"hot_topics": [{"title": "OpenCLI"}]},
            "topics": {
                "topics": [
                    {
                        "title": "Why terminal AI agents finally matter",
                        "angle": "workflow",
                    }
                ]
            },
            "titles": {
                "selected_topic": "Why terminal AI agents finally matter",
                "selected_title": "Why terminal AI agents finally matter",
                "titles": [{"text": "Why terminal AI agents finally matter"}],
            },
            "outline_plan": {
                "summary": "Explain why terminal agents now matter.",
                "sections": [
                    {
                        "section_id": "s1",
                        "heading": "Why now",
                        "purpose": "Frame the shift.",
                        "key_points": ["Adoption is now real."],
                        "evidence_refs": ["rec_1"],
                    }
                ],
            },
            "section_drafts": [
                {
                    "section_id": "s1",
                    "heading": "Why now",
                    "summary": "Terminal agents finally feel usable.",
                    "content_markdown": "Draft content",
                }
            ],
            "content": {
                "selected_title": "Why terminal AI agents finally matter",
                "summary": "Explain the workflow shift.",
                "content_markdown": "Final assembled article",
            },
            "review_results": [
                {
                    "reviewer": "style_reviewer",
                    "summary": "Strong voice alignment.",
                    "issues": [],
                }
            ],
            "style_review": {
                "reviewer": "style_reviewer",
                "summary": "Strong voice alignment.",
                "issues": [],
            },
            "structure_review": {
                "reviewer": "structure_reviewer",
                "summary": "Structure is coherent.",
                "issues": [],
            },
            "rewrite_result": {
                "used_rewrite": True,
                "revised_content_markdown": "Rewritten final article",
            },
            "audit_result": {
                "passed": True,
                "risk_level": "low",
                "issues": [],
                "overall_comment": "Grounded in evidence.",
            },
            "evaluation": {
                "final_score": 0.91,
                "summary": "Strong final draft.",
            },
        },
    )
    db_session.add_all(
        [
            account,
            task,
            TaskNodeRunModel(
                task_id=task.id,
                node_id="profile_parsing",
                agent_id="profile_agent",
                status="completed",
                output_data={"profile": {"domain": "technology"}},
            ),
            TaskNodeRunModel(
                task_id=task.id,
                node_id="hot_topic_analysis",
                agent_id="hot_topic_agent",
                status="completed",
                output_data={
                    "query_plan": task.result_data["query_plan"],
                    "source_candidates": task.result_data["source_candidates"],
                },
            ),
            TaskNodeRunModel(
                task_id=task.id,
                node_id="topic_planning",
                agent_id="topic_planner_agent",
                status="completed",
                output_data=task.result_data["topics"],
            ),
            TaskNodeRunModel(
                task_id=task.id,
                node_id="title_generation",
                agent_id="title_generator_agent",
                status="completed",
                output_data=task.result_data["titles"],
            ),
            TaskNodeRunModel(
                task_id=task.id,
                node_id="outline_planner",
                agent_id="outline_planner_agent",
                status="completed",
                output_data=task.result_data["outline_plan"],
            ),
            TaskNodeRunModel(
                task_id=task.id,
                node_id="section_writer",
                agent_id="section_writer_agent",
                status="completed",
                output_data={"section_drafts": task.result_data["section_drafts"]},
            ),
            TaskNodeRunModel(
                task_id=task.id,
                node_id="article_assembly",
                agent_id="article_assembler_agent",
                status="completed",
                output_data=task.result_data["content"],
            ),
            TaskNodeRunModel(
                task_id=task.id,
                node_id="style_reviewer",
                agent_id="style_reviewer_agent",
                status="completed",
                output_data=task.result_data["style_review"],
            ),
            TaskNodeRunModel(
                task_id=task.id,
                node_id="structure_reviewer",
                agent_id="structure_reviewer_agent",
                status="completed",
                output_data=task.result_data["structure_review"],
            ),
            TaskNodeRunModel(
                task_id=task.id,
                node_id="rewrite_agent",
                agent_id="rewrite_agent",
                status="completed",
                output_data=task.result_data["rewrite_result"],
            ),
            TaskNodeRunModel(
                task_id=task.id,
                node_id="audit",
                agent_id="audit_agent",
                status="completed",
                output_data=task.result_data["audit_result"],
            ),
        ]
    )
    await db_session.commit()

    artifacts_response = await client.get(f"/api/v1/tasks/{task.id}/artifacts")
    assert artifacts_response.status_code == 200, artifacts_response.text
    artifacts_payload = artifacts_response.json()
    assert artifacts_payload["code"] == 0
    artifacts = {
        item["artifact_key"]: item
        for item in artifacts_payload["data"]["artifacts"]
    }
    assert "evidence_bundle" in artifacts
    assert "assembled_article" in artifacts
    assert artifacts["evidence_bundle"]["display_payload"]["query_plan"]["lane"]["label"] == "AI Tools"
    assert artifacts["assembled_article"]["display_payload"]["content"]["content_markdown"] == "Final assembled article"
    assert artifacts["review_summary"]["status"] == "available"

    outline_response = await client.get(f"/api/v1/tasks/{task.id}/artifacts/outline_preview")
    assert outline_response.status_code == 200, outline_response.text
    outline_payload = outline_response.json()
    assert outline_payload["code"] == 0
    assert outline_payload["data"]["artifact_key"] == "outline_preview"
    assert outline_payload["data"]["display_payload"]["outline_plan"]["summary"] == "Explain why terminal agents now matter."

    effective_input_response = await client.get(f"/api/v1/tasks/{task.id}/effective-input")
    assert effective_input_response.status_code == 200, effective_input_response.text
    effective_input_payload = effective_input_response.json()
    assert effective_input_payload["code"] == 0
    assert effective_input_payload["data"]["selection_session_id"] == "css_artifact_demo"
    assert effective_input_payload["data"]["query_plan"]["lane"]["label"] == "AI Tools"
    assert len(effective_input_payload["data"]["selected_recommendations"]) == 1
    assert effective_input_payload["data"]["outline_seed"]["summary"] == "Explain why terminal agents now matter."
