import asyncio
import sys
sys.path.insert(0, '.')

from app.agents.profile_agent import ProfileAgent

async def test():
    print("Testing ProfileAgent...")
    agent = ProfileAgent()
    result = await agent.execute(
        {'positioning': '美食探店公众号'},
        {}
    )
    print('Success:', result.is_success)
    if result.data:
        print('Domain:', result.data.get('domain'))
        print('Subdomain:', result.data.get('subdomain'))
        print('Tone:', result.data.get('tone'))
    else:
        print('Error:', result.error)

asyncio.run(test())
