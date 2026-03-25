#!/usr/bin/env python3
"""DashScope 连通性诊断脚本。

在不走 workflow 的情况下单独测试模型调用，快速定位问题。

使用方法:
    cd backend
    python scripts/test_dashscope_connectivity.py

或直接运行:
    python -m scripts.test_dashscope_connectivity
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加载环境变量
from dotenv import load_dotenv

env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"[配置] 已加载 .env 文件: {env_path}")
else:
    print(f"[警告] .env 文件不存在: {env_path}")

# 导入 LLM 模块
from app.llm import (
    LLMGateway,
    LLMCallOptions,
    LLMCallMeta,
    LLMConfig,
    LLMTimeoutError,
    LLMAPIError,
)


# =============================================================================
# 诊断函数
# =============================================================================

def print_header(title: str) -> None:
    """打印诊断标题"""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")


def print_result(success: bool, title: str, details: str = "") -> None:
    """打印诊断结果"""
    status = "[OK]" if success else "[FAIL]"
    print(f"{status} {title}")
    if details:
        print(f"      {details}")


async def test_dns_resolution() -> bool:
    """测试 DNS 解析"""
    print_header("1. DNS 解析测试")

    try:
        import socket

        hostname = "dashscope.aliyuncs.com"
        start = time.time()
        ip = socket.gethostbyname(hostname)
        elapsed = (time.time() - start) * 1000

        print_result(True, f"DNS 解析成功: {hostname}", f"IP: {ip}, 耗时: {elapsed:.1f}ms")
        return True

    except socket.gaierror as e:
        print_result(False, f"DNS 解析失败", str(e))
        return False
    except Exception as e:
        print_result(False, f"DNS 解析异常", str(e))
        return False


async def test_tcp_connection() -> bool:
    """测试 TCP 连接"""
    print_header("2. TCP 连接测试")

    try:
        import socket

        hostname = "dashscope.aliyuncs.com"
        port = 443
        start = time.time()

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex((hostname, port))
        sock.close()

        elapsed = (time.time() - start) * 1000

        if result == 0:
            print_result(True, f"TCP 连接成功", f"{hostname}:{port}, 耗时: {elapsed:.1f}ms")
            return True
        else:
            print_result(False, f"TCP 连接失败", f"错误码: {result}")
            return False

    except socket.timeout:
        print_result(False, "TCP 连接超时", "10 秒超时")
        return False
    except Exception as e:
        print_result(False, "TCP 连接异常", str(e))
        return False


async def test_https_connection() -> bool:
    """测试 HTTPS 连接"""
    print_header("3. HTTPS API 连接测试")

    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("LLM_API_KEY")

    if not api_key:
        print_result(False, "API Key 未配置", "请在 .env 中设置 DASHSCOPE_API_KEY")
        return False

    try:
        import httpx

        base_url = os.getenv("DASHSCOPE_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1"

        start = time.time()
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{base_url}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            elapsed = (time.time() - start) * 1000

        if response.status_code == 200:
            print_result(True, "HTTPS 连接成功", f"状态码: {response.status_code}, 耗时: {elapsed:.1f}ms")

            # 尝试解析模型列表
            try:
                models = response.json()
                model_list = models.get("data", [])[:5]  # 只显示前5个
                print(f"      可用模型示例: {[m.get('id', 'unknown') for m in model_list]}")
            except:
                pass

            return True
        else:
            print_result(False, f"HTTPS 请求失败", f"状态码: {response.status_code}")
            try:
                error = response.json()
                print(f"      错误详情: {error}")
            except:
                pass
            return False

    except httpx.TimeoutException:
        print_result(False, "HTTPS 请求超时", "30 秒超时")
        return False
    except httpx.ConnectError as e:
        print_result(False, "HTTPS 连接错误", str(e))
        return False
    except Exception as e:
        print_result(False, "HTTPS 请求异常", str(e))
        return False


async def test_llm_call(model: str, provider: str = "dashscope") -> bool:
    """测试实际的 LLM 调用"""
    print_header(f"4. LLM 调用测试 (模型: {model})")

    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("LLM_API_KEY")

    if not api_key:
        print_result(False, "API Key 未配置", "跳过 LLM 调用测试")
        return False

    try:
        config = LLMConfig(
            dashscope_api_key=api_key,
            dashscope_base_url=os.getenv("DASHSCOPE_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1",
            dashscope_model=model,
            timeout=60,
        )

        gateway = LLMGateway(config=config)

        if not gateway.is_provider_available(provider):
            print_result(False, f"Provider 不可用", f"可用: {gateway.get_available_providers()}")
            return False

        meta = LLMCallMeta(agent_id="diagnostic_script", trace_id="diag_test")

        start = time.time()
        response = await gateway.complete(
            agent_id="diagnostic_script",
            prompt="请回复: OK",
            options=LLMCallOptions(
                system_prompt="你是一个简洁的助手，只需要回复 OK",
                temperature=0.1,
                max_tokens=10,
            ),
            provider=provider,
            trace_id="diagnostic",
        )
        elapsed = (time.time() - start) * 1000

        print_result(True, "LLM 调用成功", f"响应: {response.content[:50]}...")
        print(f"      模型: {response.model}")
        print(f"      耗时: {elapsed:.1f}ms")
        print(f"      Token: prompt={response.prompt_tokens}, completion={response.completion_tokens}")

        return True

    except LLMTimeoutError as e:
        print_result(False, "LLM 调用超时", f"{e.details.get('timeout_seconds')}秒超时")
        print(f"      实际耗时: {e.details.get('latency_ms')}ms")
        return False

    except LLMAPIError as e:
        print_result(False, "LLM API 错误", str(e))
        print(f"      状态码: {e.details.get('status_code')}")
        return False

    except Exception as e:
        print_result(False, "LLM 调用异常", str(e))
        return False


async def test_multiple_model_formats() -> None:
    """测试多种模型格式"""
    print_header("5. 多种模型格式测试")

    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("LLM_API_KEY")

    if not api_key:
        print("[跳过] API Key 未配置")
        return

    test_cases = [
        {"name": "qwen-turbo (快速)", "model": "qwen-turbo"},
        {"name": "qwen-plus (平衡)", "model": "qwen-plus"},
        {"name": "qwen3.5-plus (增强)", "model": "qwen3.5-plus"},
    ]

    results = []

    for tc in test_cases:
        print(f"\n测试: {tc['name']}")
        try:
            config = LLMConfig(
                dashscope_api_key=api_key,
                timeout=30,  # 较短超时用于测试
            )

            gateway = LLMGateway(config=config)

            start = time.time()
            response = await gateway.complete(
                agent_id="diagnostic",
                prompt="回复 OK",
                options=LLMCallOptions(
                    system_prompt="简洁回复 OK",
                    temperature=0.1,
                    max_tokens=5,
                ),
                provider="dashscope",
            )
            elapsed = (time.time() - start) * 1000

            print_result(True, tc["name"], f"耗时: {elapsed:.1f}ms, 响应: {response.content[:20]}")
            results.append({"name": tc["name"], "success": True, "latency": elapsed})

        except Exception as e:
            print_result(False, tc["name"], str(e)[:50])
            results.append({"name": tc["name"], "success": False, "error": str(e)})

        # 简短延迟避免限流
        await asyncio.sleep(1)

    # 总结
    print_header("5. 模型格式测试总结")
    success_count = sum(1 for r in results if r["success"])
    print(f"成功: {success_count}/{len(results)}")

    if success_count > 0:
        avg_latency = sum(r["latency"] for r in results if "latency" in r) / success_count
        print(f"平均耗时: {avg_latency:.1f}ms")


# =============================================================================
# 主函数
# =============================================================================

async def run_diagnostics() -> None:
    """运行所有诊断测试"""
    print("\n" + "=" * 60)
    print(" DashScope 连通性诊断")
    print("=" * 60)
    print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python: {sys.version.split()[0]}")

    # 检查 API Key
    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("LLM_API_KEY")
    if api_key:
        masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
        print(f"API Key: {masked_key}")
    else:
        print("API Key: [未设置]")

    # 网络层测试
    dns_ok = await test_dns_resolution()
    tcp_ok = await test_tcp_connection()
    https_ok = await test_https_connection()

    # LLM 调用测试（使用 qwen-turbo 作为快速测试）
    model = os.getenv("DASHSCOPE_MODEL") or "qwen-turbo"
    llm_ok = await test_llm_call(model)

    # 多种模型测试（仅当 LLM 调用成功时）
    if llm_ok:
        await test_multiple_model_formats()

    # 最终总结
    print_header("诊断总结")

    tests = [
        ("DNS 解析", dns_ok),
        ("TCP 连接", tcp_ok),
        ("HTTPS API", https_ok),
        ("LLM 调用", llm_ok),
    ]

    for name, ok in tests:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}")

    all_passed = all(ok for _, ok in tests)

    print("\n" + "-" * 60)
    if all_passed:
        print("结果: 所有测试通过 [OK]")
        print("建议: 如果仍有问题，检查:")
        print("  1. API Key 权限和配额")
        print("  2. 模型是否已开通（如 qwen3.5-plus）")
        print("  3. 账户余额")
    else:
        failed = [name for name, ok in tests if not ok]
        print(f"结果: {len(failed)} 项测试失败 [FAIL]")
        print(f"失败项: {', '.join(failed)}")
        print("\n排查建议:")
        print("  1. DNS 失败 -> 检查网络/防火墙/DNS 配置")
        print("  2. TCP 失败 -> 检查防火墙是否开放 443 端口")
        print("  3. HTTPS 失败 -> 检查代理设置或网络限制")
        print("  4. LLM 调用失败 -> 检查 API Key 有效性和模型权限")

    print("-" * 60)


def main() -> None:
    """主入口"""
    try:
        asyncio.run(run_diagnostics())
    except KeyboardInterrupt:
        print("\n\n[中断] 用户取消诊断")
        sys.exit(1)
    except Exception as e:
        print(f"\n[错误] 诊断过程异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
