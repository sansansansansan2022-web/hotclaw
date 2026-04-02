"""Test script to verify the full agent workflow chain.

Usage:
    python scripts/test_workflow.py
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import and register agents (simulating FastAPI startup)
from app.agents.profile_agent import ProfileAgent
from app.agents.hot_topic_agent import HotTopicAgent
from app.agents.topic_planner_agent import TopicPlannerAgent
from app.agents.title_generator_agent import TitleGeneratorAgent
from app.agents.content_writer_agent import ContentWriterAgent
from app.agents.audit_agent import AuditAgent
from app.agents.registry import agent_registry
from app.orchestrator.engine import DEFAULT_WORKFLOW_NODES


def _register_agents():
    """Register all agents (simulating FastAPI startup)."""
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


def print_info(text: str) -> None:
    print(f"  [INFO] {text}")


def main():
    # Register agents first
    _register_agents()

    print_header("HotClaw Agent Workflow Chain Verification")

    # 1. Check all agents are registered
    print_header("Step 1: Check Agent Registry")
    expected_agents = [
        "profile_agent",
        "hot_topic_agent",
        "topic_planner_agent",
        "title_generator_agent",
        "content_writer_agent",
        "audit_agent",
    ]

    all_agents = agent_registry.list_all()
    agent_ids = [a.agent_id for a in all_agents]

    for agent_id in expected_agents:
        if agent_id in agent_ids:
            agent = agent_registry.get(agent_id)
            print_success(f"{agent_id} registered: {agent.name}")
        else:
            print_error(f"{agent_id} NOT found in registry!")

    print(f"\n  Total agents registered: {len(all_agents)}")

    # 2. Check workflow nodes
    print_header("Step 2: Check Workflow Nodes")
    print(f"  Total nodes defined: {len(DEFAULT_WORKFLOW_NODES)}")

    for i, node in enumerate(DEFAULT_WORKFLOW_NODES):
        node_id = node["node_id"]
        agent_id = node["agent_id"]
        input_keys = list(node["input_mapping"].keys())
        output_key = node["output_key"]
        required = node.get("required", True)

        status = "required" if required else "optional"
        in_registered = agent_id in agent_ids
        icon = "[OK]" if in_registered else "[!!]"
        print(f"  {icon} {i+1}. {node_id}")
        print(f"      Agent: {agent_id}")
        print(f"      Input: {input_keys}")
        print(f"      Output: {output_key}")
        print(f"      Status: {status}")

    # 3. Check data flow
    print_header("Step 3: Verify Data Flow")

    # Build data dependency graph
    data_produced = set()  # Keys produced by nodes
    data_consumed = set()  # Keys consumed by nodes

    for node in DEFAULT_WORKFLOW_NODES:
        output_key = node["output_key"]
        data_produced.add(output_key)

        for input_key in node["input_mapping"].keys():
            data_consumed.add(input_key)

    # Input is the external data
    external_inputs = data_consumed - data_produced

    print(f"  External inputs: {external_inputs}")
    print(f"  Internal data flow: {data_produced & data_consumed}")
    print(f"  Final outputs: {data_produced}")

    # 4. Check workflow order
    print_header("Step 4: Verify Workflow Order")

    # Profile -> HotTopics -> Topics -> Titles -> Content -> Audit
    expected_order = [
        ("profile_agent", "profile"),
        ("hot_topic_agent", "hot_topics"),
        ("topic_planner_agent", "topics"),
        ("title_generator_agent", "titles"),
        ("content_writer_agent", "content"),
        ("audit_agent", "audit_result"),
    ]

    order_ok = True
    for i, (node, expected_output) in enumerate(expected_order):
        node_def = DEFAULT_WORKFLOW_NODES[i]
        if node_def["agent_id"] != node or node_def["output_key"] != expected_output:
            print_error(f"Node {i+1} mismatch: expected {node}/{expected_output}, got {node_def['agent_id']}/{node_def['output_key']}")
            order_ok = False

    if order_ok:
        print_success("Workflow order is correct!")

    # 5. Summary
    print_header("Summary")

    issues = []

    if len(all_agents) != 6:
        issues.append(f"Expected 6 agents, got {len(all_agents)}")

    for agent_id in expected_agents:
        if agent_id not in agent_ids:
            issues.append(f"Missing agent: {agent_id}")

    if len(DEFAULT_WORKFLOW_NODES) != 6:
        issues.append(f"Expected 6 workflow nodes, got {len(DEFAULT_WORKFLOW_NODES)}")

    if not order_ok:
        issues.append("Workflow order is incorrect")

    if issues:
        print_error("Issues found:")
        for issue in issues:
            print(f"  - {issue}")
        print("\n  Workflow chain verification FAILED!")
        return 1
    else:
        print_success("All checks passed!")
        print_success("Agent workflow chain is ready!")
        print("\n  Workflow chain visualization:")
        print("  " + " -> ".join([n["output_key"] for n in DEFAULT_WORKFLOW_NODES]))
        print("\n  Full data flow:")
        print(f"  positioning -> {DEFAULT_WORKFLOW_NODES[0]['output_key']}")
        for i in range(len(DEFAULT_WORKFLOW_NODES) - 1):
            curr = DEFAULT_WORKFLOW_NODES[i]
            next_node = DEFAULT_WORKFLOW_NODES[i + 1]
            inputs = list(next_node["input_mapping"].keys())
            print(f"  {curr['output_key']} -> {next_node['output_key']} (with {inputs})")
        print("\n  Workflow chain verification PASSED!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
