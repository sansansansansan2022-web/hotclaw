/** API client for HotClaw backend. */

import type {
  ApiResponse,
  TaskCreateRequest,
  TaskCreateData,
  TaskDetail,
  NodeRun,
  TaskSummary,
} from "@/types";

const BASE = "/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body: ApiResponse<T> = await res.json();
  if (body.code !== 0) {
    throw new Error(body.message || "request failed");
  }
  return body.data;
}

export async function createTask(positioning: string): Promise<TaskCreateData> {
  return request<TaskCreateData>("/tasks", {
    method: "POST",
    body: JSON.stringify({ positioning } satisfies TaskCreateRequest),
  });
}

export async function getTaskDetail(taskId: string): Promise<TaskDetail> {
  return request<TaskDetail>(`/tasks/${taskId}`);
}

export async function getTaskNodes(taskId: string): Promise<{ nodes: NodeRun[] }> {
  return request<{ nodes: NodeRun[] }>(`/tasks/${taskId}/nodes`);
}

export async function listTasks(
  page = 1,
  pageSize = 20
): Promise<{ tasks: TaskSummary[]; pagination: { page: number; page_size: number; total: number } }> {
  return request(`/tasks?page=${page}&page_size=${pageSize}`);
}

export function getTaskStreamUrl(taskId: string): string {
  return `${BASE}/tasks/${taskId}/stream`;
}

// --- Agents ---

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

export async function listAgents(): Promise<{ agents: AgentInfo[] }> {
  return request<{ agents: AgentInfo[] }>("/agents");
}

export async function getAgent(agentId: string): Promise<AgentInfo> {
  return request<AgentInfo>(`/agents/${agentId}`);
}

export async function updateAgentConfig(
  agentId: string,
  config: { model_config_data?: Record<string, unknown>; prompt_template?: string; retry_config?: Record<string, unknown> }
): Promise<{ agent_id: string; updated_fields: string[] }> {
  return request(`/agents/${agentId}/config`, {
    method: "PUT",
    body: JSON.stringify(config),
  });
}

// --- Skills ---

export interface SkillInfo {
  skill_id: string;
  name: string;
  description: string;
  version: string;
  config_data: Record<string, unknown> | null;
  status: string;
}

export async function listSkills(): Promise<{ skills: SkillInfo[] }> {
  return request<{ skills: SkillInfo[] }>("/skills");
}

export async function updateSkillConfig(
  skillId: string,
  config: { config_data: Record<string, unknown> }
): Promise<{ skill_id: string; updated: boolean }> {
  return request(`/skills/${skillId}/config`, {
    method: "PUT",
    body: JSON.stringify(config),
  });
}

// --- LLM Providers ---

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

export async function listLLMProviders(): Promise<LLMProviderInfo[]> {
  return request<LLMProviderInfo[]>("/llm-providers");
}

export async function getLLMProvider(providerId: string): Promise<LLMProviderInfo> {
  return request<LLMProviderInfo>(`/llm-providers/${providerId}`);
}

export async function createLLMProvider(
  data: LLMProviderCreate
): Promise<LLMProviderInfo> {
  return request("/llm-providers", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateLLMProvider(
  providerId: string,
  data: LLMProviderUpdate
): Promise<LLMProviderInfo> {
  return request(`/llm-providers/${providerId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteLLMProvider(providerId: string): Promise<void> {
  await request(`/llm-providers/${providerId}`, {
    method: "DELETE",
  });
}

export async function testLLMProvider(
  data: LLMProviderTestRequest
): Promise<LLMProviderTestResponse> {
  return request("/llm-providers/test", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getDefaultLLMProvider(): Promise<{
  provider_id: string | null;
  name?: string;
  default_model?: string;
  message?: string;
}> {
  return request("/llm-providers/active/default");
}

export async function setDefaultLLMProvider(
  providerId: string
): Promise<{ provider_id: string; message: string }> {
  return request(`/llm-providers/active/default/${providerId}`, {
    method: "POST",
  });
}

// 预定义的 Provider 模板
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
