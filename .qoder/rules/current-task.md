# 当前任务

## 任务目标

**打通 HotClaw 6 个智能体的 LLM 调用链路**

## 当前状态

| Agent | 状态 | 说明 |
|-------|------|------|
| profile_agent | ✅ 已修复 | 直接调用 litellm，使用 dashscope provider |
| hot_topic_agent | ❌ Mock | 需要改成真实 LLM 调用 |
| topic_planner_agent | ❌ Mock | 需要改成真实 LLM 调用 |
| title_generator_agent | ❌ Mock | 需要改成真实 LLM 调用 |
| content_writer_agent | ❌ Mock | 需要改成真实 LLM 调用 |
| audit_agent | ❌ Mock | 需要改成真实 LLM 调用 |

## 修改规范

参考 `profile_agent.py` 的实现方式，每个 Agent 需要修改以下内容：

### 1. 导入语句

```python
import json
import litellm
from app.agents.base import BaseAgent, AgentResult
from app.core.config import settings
```

### 2. execute 方法中的 LLM 调用

```python
# 阿里云 dashscope 需要用 dashscope 前缀
model = settings.llm_model_name
if not model.startswith("dashscope/"):
    model = f"dashscope/{model}"

response = await litellm.acompletion(
    model=model,
    api_key=settings.llm_api_key,
    base_url=settings.llm_api_base_url,
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ],
    timeout=settings.llm_timeout,
    custom_llm_provider="dashscope",
)
content = response.choices[0].message.content
```

### 3. 保留内容

- 保留原有的 `default_system_prompt`
- 保留原有的 `_parse_json` 方法（如果有）
- 保留原有的 `fallback` 方法

## 具体任务（按顺序执行）

### 任务 1：hot_topic_agent.py

- 删除 `asyncio.sleep(1.5)` Mock 代码
- 添加真实 LLM 调用，根据 profile 生成热点分析
- 构建 user_prompt 包含 profile 数据

### 任务 2：topic_planner_agent.py

- 删除 `asyncio.sleep(1.2)` Mock 代码
- 添加真实 LLM 调用，根据 profile 和 hot_topics 生成选题
- 构建 user_prompt 包含 profile 和热点数据

### 任务 3：title_generator_agent.py

- 删除 `asyncio.sleep(1.0)` Mock 代码
- 添加真实 LLM 调用，根据 profile 和 topics 生成标题
- 构建 user_prompt 包含 profile 和选题数据

### 任务 4：content_writer_agent.py

- 删除 `asyncio.sleep(2.0)` Mock 代码和 Mock 文章
- 添加真实 LLM 调用，根据所有上下文生成完整文章
- 构建 user_prompt 包含 profile、topics、titles、hot_topics

### 任务 5：audit_agent.py

- 删除 `asyncio.sleep(0.8)` Mock 代码
- 添加真实 LLM 调用，对标题和正文进行审核
- 构建 user_prompt 包含 titles 和 content

## 完成后

1. 在 `RESULT.md` 中记录每个文件的修改内容
2. 运行测试验证每个 Agent 能正常调用 LLM
3. 运行完整 workflow 测试

## 注意事项

- 每个文件单独修改，不要一次改太多
- 修改后立即测试
- 如果 LLM 返回格式不对，使用 fallback 返回
