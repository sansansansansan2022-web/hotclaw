import asyncio
import litellm
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)
print(f'[配置] 已加载 .env 文件: {env_path}')

async def test():
    # DeepSeek API 配置
    api_key = os.getenv('DEEPSEEK_API_KEY', '')
    base_url = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
    model = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
    
    print(f'[配置] DEEPSEEK_API_KEY: {api_key[:10]}...' if api_key else '[配置] DEEPSEEK_API_KEY: 未设置')
    print(f'[配置] DEEPSEEK_BASE_URL: {base_url}')
    print(f'[配置] DEEPSEEK_MODEL: {model}')
    
    if not api_key:
        print('[错误] No DEEPSEEK_API_KEY found')
        return

    print(f"\n测试 DeepSeek API...")
    try:
        # DeepSeek 需要使用 provider/model 格式
        full_model = f"deepseek/{model}"
        print(f'[调用] model={full_model}')
        
        r = await litellm.acompletion(
            model=full_model,
            messages=[{'role': 'user', 'content': '你好，请用一句话介绍自己'}],
            api_key=api_key,
            base_url=base_url,
            timeout=30
        )
        print(f'\n[成功] 模型: {model}')
        print(f'[响应] {r.choices[0].message.content}')
    except Exception as e:
        print(f'\n[错误] {type(e).__name__}: {str(e)[:200]}')

asyncio.run(test())
