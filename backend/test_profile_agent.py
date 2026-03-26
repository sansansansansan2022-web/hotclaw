"""测试完整的 profile_agent 调用"""
import asyncio
import sys
sys.path.insert(0, '.')

from app.agents.profile_agent import ProfileAgent
from app.agents.base import AgentResult

async def test():
    print("=== Testing ProfileAgent ===")
    agent = ProfileAgent()

    input_data = {"positioning": "美食探店公众号"}
    context = {}

    print(f"Input: {input_data}")
    print(f"Model: {agent.__class__.__name__}")

    try:
        result = await agent.execute(input_data, context)
        print(f"\nResult status: {result.status}")
        print(f"Result is_success: {result.is_success}")

        if result.data:
            print(f"\nData keys: {list(result.data.keys())}")
            print(f"Domain: {result.data.get('domain')}")
            print(f"Subdomain: {result.data.get('subdomain')}")
            print(f"Tone: {result.data.get('tone')}")
        else:
            print(f"\nError: {result.error}")

    except Exception as e:
        print(f"\nException: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
