/**
 * API client for HotClaw backend.
 *
 * 【API 客户端】
 * 封装所有后端 API 调用，统一处理：
 * - 请求序列化/反序列化
 * - 错误处理（code !== 0 → throw Error）
 * - 路径前缀（/api/v1）
 * - SSE URL 生成（直连后端）
 *
 * 面试点：
 * - fetch API + async/await
 * - 统一错误处理
 * - SSR/CSR 环境判断
 * - SSE 直连绕过代理
 */

import type {
  ApiResponse,
  TaskCreateRequest,
  TaskCreateData,
  TaskDetail,
  NodeRun,
  TaskSummary,
} from "@/types";

// API 基础路径（通过 Next.js 代理）
const BASE = "/api/v1";

/**
 * request — 统一请求方法
 *
 * 所有 API 调用都通过此函数，自动：
 * 1. 拼接 BASE 路径
 * 2. 设置 Content-Type
 * 3. 解析响应 JSON
 * 4. 检查 code 字段（非 0 则抛出错误）
 */
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body: ApiResponse<T> = await res.json();
  // 后端返回 code !== 0 表示业务错误
  if (body.code !== 0) {
    throw new Error(body.message || "request failed");
  }
  return body.data;
}

// =============================================================================
// 任务相关 API
// =============================================================================

/** 创建任务 */
export async function createTask(positioning: string): Promise<TaskCreateData> {
  return request<TaskCreateData>("/tasks", {
    method: "POST",
    body: JSON.stringify({ positioning } satisfies TaskCreateRequest),
  });
}

/** 获取任务详情 */
export async function getTaskDetail(taskId: string): Promise<TaskDetail> {
  return request<TaskDetail>(`/tasks/${taskId}`);
}

/** 获取节点执行记录 */
export async function getTaskNodes(taskId: string): Promise<{ nodes: NodeRun[] }> {
  return request<{ nodes: NodeRun[] }>(`/tasks/${taskId}/nodes`);
}

/** 任务列表（分页） */
export async function listTasks(
  page = 1,
  pageSize = 20
): Promise<{ tasks: TaskSummary[]; pagination: { page: number; page_size: number; total: number } }> {
  return request(`/tasks?page=${page}&page_size=${pageSize}`);
}

/**
 * getTaskStreamUrl — SSE 流地址
 *
 * 【关键设计】SSE 必须直连后端，绕过 Next.js 开发服务器代理
 *
 * 问题：Next.js 开发服务器的代理默认会缓冲 HTTP 响应，
 * 直到完整响应后才发送给客户端。这会导致 SSE 的流式推送
 * 变成"一次性推送"，无法实现实时效果。
 *
 * 解决：在浏览器端直接连接后端端口 8002，
 * 绕过 Next.js 代理，直接接收 SSE 流。
 *
 * 为什么不用生产环境问题？
 * 生产环境用 Nginx 等反向代理，默认支持 SSE 流式响应。
 */
export function getTaskStreamUrl(taskId: string): string {
  // SSR 时（服务端渲染）返回相对路径
  if (typeof window !== "undefined") {
    return `http://${window.location.hostname}:8002${BASE}/tasks/${taskId}/stream`;
  }
  return `${BASE}/tasks/${taskId}/stream`;
}

// =============================================================================
// 智能体相关 API
// =============================================================================

export interface AgentInfo {
  agent_id: string;
  name: string;
  description: string;
  version: string;
  status: string;
  model_config_data?: Record<string, unknown> | null;
  prompt_template?: string | null;
  prompt_source?: string | null;
  default_system_prompt?: string | null;
  has_custom_prompt?: boolean;
  retry_config?: Record<string, unknown> | null;
}

/** 列出所有智能体 */
export async function listAgents(): Promise<{ agents: AgentInfo[] }> {
  return request<{ agents: AgentInfo[] }>("/agents");
}

/** 获取单个智能体详情 */
export async function getAgent(agentId: string): Promise<AgentInfo> {
  return request<AgentInfo>(`/agents/${agentId}`);
}

/** 更新智能体配置（Prompt / Model / Retry） */
export async function updateAgentConfig(
  agentId: string,
  config: {
    model_config_data?: Record<string, unknown>;
    prompt_template?: string;
    retry_config?: Record<string, unknown>;
  }
): Promise<{ agent_id: string; updated_fields: string[] }> {
  return request(`/agents/${agentId}/config`, {
    method: "PUT",
    body: JSON.stringify(config),
  });
}

// =============================================================================
// 技能相关 API
// =============================================================================

export interface SkillInfo {
  skill_id: string;
  name: string;
  description: string;
  version: string;
  config_data: Record<string, unknown> | null;
  status: string;
}

/** 列出所有技能 */
export async function listSkills(): Promise<{ skills: SkillInfo[] }> {
  return request<{ skills: SkillInfo[] }>("/skills");
}

/** 更新技能配置 */
export async function updateSkillConfig(
  skillId: string,
  config: { config_data: Record<string, unknown> }
): Promise<{ skill_id: string; updated: boolean }> {
  return request(`/skills/${skillId}/config`, {
    method: "PUT",
    body: JSON.stringify(config),
  });
}

// =============================================================================
// LLM Provider 相关 API
// =============================================================================

export interface LLMProviderInfo {
  provider_id: string;
  name: string;
  description: string | null;
  api_key: string | null;
  base_url: string | null;
  default_model: string | null;
  supported_models: string[] | null;
  is_enabled: boolean;
  is_default: boolean;
  timeout: number;
  extra_config: Record<string, unknown> | null;
  status: string;
  test_status: string | null;
  test_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface LLMProviderCreate {
  provider_id: string;
  name: string;
  description?: string;
  api_key?: string;
  base_url?: string;
  default_model?: string;
  supported_models?: string[];
  is_enabled?: boolean;
  is_default?: boolean;
  timeout?: number;
  extra_config?: Record<string, unknown>;
}

export interface LLMProviderUpdate {
  name?: string;
  description?: string;
  api_key?: string;
  base_url?: string;
  default_model?: string;
  supported_models?: string[];
  is_enabled?: boolean;
  is_default?: boolean;
  timeout?: number;
  extra_config?: Record<string, unknown>;
  status?: string;
}

export interface LLMProviderTestRequest {
  provider_id: string;
  api_key?: string;
  base_url?: string;
  model?: string;
}

export interface LLMProviderTestResponse {
  success: boolean;
  latency_ms?: number;
  response_preview?: string;
  error_message?: string;
}

/** 列出所有 LLM Provider */
export async function listLLMProviders(): Promise<LLMProviderInfo[]> {
  return request<LLMProviderInfo[]>("/llm-providers");
}

/** 获取单个 Provider */
export async function getLLMProvider(providerId: string): Promise<LLMProviderInfo> {
  return request<LLMProviderInfo>(`/llm-providers/${providerId}`);
}

/** 创建 Provider */
export async function createLLMProvider(
  data: LLMProviderCreate
): Promise<LLMProviderInfo> {
  return request("/llm-providers", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/** 更新 Provider */
export async function updateLLMProvider(
  providerId: string,
  data: LLMProviderUpdate
): Promise<LLMProviderInfo> {
  return request(`/llm-providers/${providerId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

/** 删除 Provider */
export async function deleteLLMProvider(providerId: string): Promise<void> {
  await request(`/llm-providers/${providerId}`, {
    method: "DELETE",
  });
}

/** 测试 Provider 连接 */
export async function testLLMProvider(
  data: LLMProviderTestRequest
): Promise<LLMProviderTestResponse> {
  return request("/llm-providers/test", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/** 获取当前默认 Provider */
export async function getDefaultLLMProvider(): Promise<{
  provider_id: string | null;
  name?: string;
  default_model?: string;
  message?: string;
}> {
  return request("/llm-providers/active/default");
}

/** 设置默认 Provider */
export async function setDefaultLLMProvider(
  providerId: string
): Promise<{ provider_id: string; message: string }> {
  return request(`/llm-providers/active/default/${providerId}`, {
    method: "POST",
  });
}

/**
 * 预定义的 Provider 模板
 * 用户创建 Provider 时可以直接选择模板，快速配置
 */
export const LLM_PROVIDER_TEMPLATES = [
  {
    provider_id: "openai",
    name: "OpenAI",
    description: "OpenAI GPT 系列模型 (GPT-4o, GPT-4o-mini, o1)",
    supported_models: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1", "o1-mini"],
    default_model: "gpt-4o-mini",
    base_url: "https://api.openai.com/v1",
  },
  {
    provider_id: "dashscope",
    name: "阿里云百炼 (Qwen)",
    description: "阿里云通义千问系列模型",
    supported_models: ["qwen-turbo", "qwen-plus", "qwen3.5-plus", "qwen-max", "qwen2.5-plus"],
    default_model: "qwen3.5-plus",
    base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1",
  },
  {
    provider_id: "deepseek",
    name: "DeepSeek",
    description: "DeepSeek V3 / DeepSeek R1 系列模型",
    supported_models: ["deepseek-chat", "deepseek-coder", "deepseek-reasoner"],
    default_model: "deepseek-chat",
    base_url: "https://api.deepseek.com",
  },
  {
    provider_id: "zhipu",
    name: "智谱 AI (GLM)",
    description: "智谱 GLM 系列大模型",
    supported_models: ["glm-4", "glm-4-flash", "glm-4-plus", "glm-3-turbo"],
    default_model: "glm-4",
    base_url: "https://open.bigmodel.cn/api/paas/v4",
  },
  {
    provider_id: "ollama",
    name: "Ollama (本地)",
    description: "Ollama 本地部署模型",
    supported_models: [],
    default_model: "",
    base_url: "http://localhost:11434/v1",
  },
  {
    provider_id: "vllm",
    name: "vLLM (本地)",
    description: "vLLM 本地部署模型",
    supported_models: [],
    default_model: "",
    base_url: "http://localhost:8000/v1",
  },
] as const;
