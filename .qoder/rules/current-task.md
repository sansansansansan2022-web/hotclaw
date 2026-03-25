# 当前任务

## 状态：待执行

## 任务：创建 LLM 调用层

### 具体要求

在 `backend/app/core/` 目录下创建 `llm.py` 文件，实现 LLM 调用封装。

### 功能规格

```python
# backend/app/core/llm.py

class LLMClient:
    """LLM 调用客户端"""
    
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: dict | None = None,  # {"type": "json_object"}
    ) -> LLMResponse:
        """
        调用 LLM 并返回响应
        
        Returns:
            LLMResponse:
                - content: str (响应内容)
                - prompt_tokens: int
                - completion_tokens: int
                - model: str
        """
        pass
```

### 配置要求

从 `app.core.config.settings` 读取：
- `llm_model`: 模型名称
- `llm_api_base`: API 地址（可选）
- `llm_api_key`: API Key
- `llm_timeout`: 超时时间

### 错误处理

- 超时：抛出 `LLMTimeoutError`
- API 错误：抛出 `LLMAPIError`
- JSON 解析失败：抛出 `LLMResponseError`

### 日志要求

每次调用记录：
- model
- prompt_tokens
- completion_tokens
- elapsed_seconds
- trace_id

### 依赖

使用 `openai` SDK（已在项目中），支持 OpenAI 兼容 API。

### 完成标准

1. 文件创建成功
2. 类型注解完整
3. 错误处理完善
4. 有基础单元测试（可选 mock）

---

**完成后请报告结果，等待下一个任务。**