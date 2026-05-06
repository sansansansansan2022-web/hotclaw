"""End-to-end workflow test: simulates full agent chain execution.

Tests the actual input/output of each agent in the workflow.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Register agents
from app.agents.profile_agent import ProfileAgent
from app.agents.hot_topic_agent import HotTopicAgent
from app.agents.topic_planner_agent import TopicPlannerAgent
from app.agents.title_generator_agent import TitleGeneratorAgent
from app.agents.content_writer_agent import ContentWriterAgent
from app.agents.audit_agent import AuditAgent
from app.agents.registry import agent_registry
from app.orchestrator.workspace import Workspace


def _register_agents():
    """Register all agents."""
    agent_registry.register(ProfileAgent())
    agent_registry.register(HotTopicAgent())
    agent_registry.register(TopicPlannerAgent())
    agent_registry.register(TitleGeneratorAgent())
    agent_registry.register(ContentWriterAgent())
    agent_registry.register(AuditAgent())


def print_header(text: str) -> None:
    print(f"\n{'='*60}")
    print(f" {text}")
    print(f"{'='*60}")


def print_success(text: str) -> None:
    print(f"  [OK] {text}")


def print_error(text: str) -> None:
    print(f"  [FAIL] {text}")


def print_data(label: str, data: dict) -> None:
    """Print data structure with truncation."""
    print(f"\n  {label}:")
    if not data:
        print("    (empty)")
        return

    # Show keys
    print(f"    Keys: {list(data.keys())}")

    # Show first level values (truncated)
    for key, value in data.items():
        if isinstance(value, str):
            display = value[:50] + "..." if len(value) > 50 else value
        elif isinstance(value, list):
            display = f"list[{len(value)}]"
        elif isinstance(value, dict):
            display = f"dict[{list(value.keys())[:3]}...]"
        else:
            display = str(value)
        print(f"      {key}: {display}")


def check_agent_output(agent_name: str, output: dict, expected_keys: list) -> bool:
    """Check if agent output contains expected keys."""
    if not output:
        print_error(f"{agent_name}: output is empty!")
        return False

    missing_keys = [k for k in expected_keys if k not in output]
    if missing_keys:
        print_error(f"{agent_name}: missing keys: {missing_keys}")
        print_error(f"  Available keys: {list(output.keys())}")
        return False

    print_success(f"{agent_name}: output valid with keys {expected_keys}")
    return True


async def run_e2e_test():
    """Run end-to-end workflow test."""
    _register_agents()

    print_header("End-to-End Workflow Test")

    # Test input
    test_input = {
        "positioning": "关注职场成长的公众号，目标读者25-35岁互联网从业者"
    }

    print(f"\n  Test Input:")
    print(f"    positioning: {test_input['positioning']}")

    # Create workspace
    workspace = Workspace(task_id="test-task", input_data=test_input)

    # Workflow nodes definition (approximates DEFAULT_WORKFLOW_NODES; first node is ContextBuilder)
    workflow_nodes = [
        {
            "node_id": "context_building",
            "agent_id": "context_builder_agent",
            "output_key": "run_context",
            "input_mapping": {"positioning": "input.positioning", "account_id": "input.account_id"},
        },
        {
            "node_id": "hot_topic_analysis",
            "agent_id": "hot_topic_agent",
            "output_key": "hot_topics",
            "input_mapping": {"profile": "profile"},
        },
        {
            "node_id": "topic_planning",
            "agent_id": "topic_planner_agent",
            "output_key": "topics",
            "input_mapping": {
                "profile": "profile",
                "hot_topics": "hot_topics",
                "account_context": "account_context",
                "ops_context": "ops_context",
            },
        },
        {
            "node_id": "title_generation",
            "agent_id": "title_generator_agent",
            "output_key": "titles",
            "input_mapping": {
                "profile": "profile",
                "topics": "topics",
                "account_context": "account_context",
                "ops_context": "ops_context",
            },
        },
        {
            "node_id": "content_writing",
            "agent_id": "content_writer_agent",
            "output_key": "content",
            "input_mapping": {
                "profile": "profile",
                "topics": "topics",
                "titles": "titles",
                "hot_topics": "hot_topics",
                "account_context": "account_context",
                "ops_context": "ops_context",
            },
        },
        {
            "node_id": "audit",
            "agent_id": "audit_agent",
            "output_key": "audit_result",
            "input_mapping": {"titles": "titles", "content": "content", "profile": "profile"},
        },
    ]

    context = {}  # No custom prompts for testing

    # Execute each agent step by step
    results = {}
    all_passed = True

    for i, node in enumerate(workflow_nodes):
        node_id = node["node_id"]
        agent_id = node["agent_id"]
        output_key = node["output_key"]

        print_header(f"Step {i+1}: {node_id} ({agent_id})")

        # Extract input for this agent
        agent_input = workspace.extract_for_agent(node["input_mapping"])
        print_data("Agent Input", agent_input)

        # Get agent
        agent = agent_registry.get(agent_id)

        # Execute agent (skip hot_topic_agent's web search for unit test)
        if agent_id == "hot_topic_agent":
            # For unit test, use simplified input
            agent_input = {"profile": workspace.get("profile")}

        try:
            result = await agent.execute(agent_input, context)

            if result.is_success:
                print_success(f"Agent executed successfully")

                # Store output in workspace
                workspace.set(output_key, result.data)
                if node_id == "context_building":
                    payload = result.data or {}
                    workspace.set("profile", payload.get("effective_profile") or {})
                    if payload.get("account_context") is not None:
                        workspace.set("account_context", payload["account_context"])
                    if isinstance(payload.get("ops_context"), dict):
                        workspace.set("ops_context", payload["ops_context"])
                results[output_key] = result.data

                # Verify expected output keys
                expected_keys = get_expected_keys(agent_id)
                if not check_agent_output(agent_id, result.data, expected_keys):
                    all_passed = False

                print_data("Agent Output", result.data)
            else:
                print_error(f"Agent failed: {result.error}")
                all_passed = False
                break

        except Exception as e:
            print_error(f"Agent execution error: {str(e)}")
            all_passed = False
            break

    # Summary
    print_header("Test Summary")

    print("\n  Workflow Data Flow:")
    for key in ["profile", "hot_topics", "topics", "titles", "content", "audit_result"]:
        value = workspace.get(key)
        if value:
            status = "OK"
        else:
            status = "MISSING"
        print(f"    {key}: {status}")

    if all_passed:
        print_success("\nAll agents executed successfully!")
        print_success("Workflow chain is working correctly!")
        return 0
    else:
        print_error("\nSome agents failed!")
        return 1


def get_expected_keys(agent_id: str) -> list:
    """Return expected output keys for each agent."""
    expectations = {
        "context_builder_agent": ["effective_profile", "ops_context", "positioning"],
        "profile_agent": ["domain", "subdomain", "tone", "keywords"],
        "hot_topic_agent": ["hot_topics"],
        "topic_planner_agent": ["topics"],
        "title_generator_agent": ["titles", "selected_topic"],
        "content_writer_agent": ["content_markdown", "word_count", "structure"],
        "audit_agent": ["passed", "risk_level", "issues"],
    }
    return expectations.get(agent_id, [])


if __name__ == "__main__":
    exit_code = asyncio.run(run_e2e_test())
    sys.exit(exit_code)
