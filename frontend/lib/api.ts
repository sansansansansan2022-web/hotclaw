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
  AccountCreateRequest,
  AccountUpdateRequest,
  AccountSummary,
  AccountDetail,
  AccountCreateData,
  AccountRunData,
  AccountListResponse,
  DraftSummary,
  DraftDetail,
  DraftListResponse,
  DraftConfirmData,
  DraftDiscardData,
  DraftRejectData,
  DraftRerunData,
  WeChatPublishStatus,
  WeChatPublishResult,
  PublishRecord,
  PublishRecordListResponse,
  RefreshStatusResponse,
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
// 统一响应格式（部分API使用）
interface UnifiedResponse<T> {
  code: number;
  message?: string;
  data: T;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await res.json();
  
  // 兼容两种响应格式：
  // 1. 统一格式: {code: 0, data: {...}} (部分API使用)
  // 2. 直接数据: {accounts: [...], pagination: {...}} (部分API直接返回)
  if ("code" in body) {
    // 统一格式响应
    if (body.code !== 0) {
      throw new Error(body.message || "request failed");
    }
    return body.data;
  } else {
    // 直接返回数据（无需包装）
    return body as T;
  }
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
  pageSize = 20,
  status?: string
): Promise<{ tasks: TaskSummary[]; pagination: { page: number; page_size: number; total: number } }> {
  const qs = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (status) qs.set("status", status);
  return request(`/tasks?${qs}`);
}

/** 重跑任务 */
export async function rerunTask(taskId: string): Promise<TaskCreateData> {
  return request<TaskCreateData>(`/tasks/${taskId}/rerun`, {
    method: "POST",
  });
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
 * 解决：在浏览器端直接连接后端端口 8000，
 * 绕过 Next.js 代理，直接接收 SSE 流。
 *
 * 为什么不用生产环境问题？
 * 生产环境用 Nginx 等反向代理，默认支持 SSE 流式响应。
 */
export function getTaskStreamUrl(taskId: string): string {
  // SSR 时（服务端渲染）返回相对路径
  if (typeof window !== "undefined") {
    return `http://${window.location.hostname}:8000${BASE}/tasks/${taskId}/stream`;
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

// =============================================================================
// Account 相关 API
// =============================================================================

/**
 * createAccount - 创建新账号
 *
 * 调用后端 API: POST /api/v1/accounts
 *
 * 参数:
 * - data: AccountCreateRequest (包含 name, positioning 等必填字段)
 *
 * 返回:
 * - AccountCreateData (包含 account_id, name, is_active, operation_mode)
 *
 * 调用方:
 * - frontend/app/accounts/new/page.tsx (新建账号页)
 */
export async function createAccount(data: AccountCreateRequest): Promise<AccountCreateData> {
  return request<AccountCreateData>("/accounts", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/**
 * listAccounts - 获取账号列表（分页）
 *
 * 调用后端 API: GET /api/v1/accounts
 *
 * 参数:
 * - page: 页码（默认 1）
 * - pageSize: 每页数量（默认 20）
 *
 * 返回:
 * - AccountListResponse (包含 accounts 列表和 pagination 信息)
 *
 * 调用方:
 * - frontend/app/accounts/page.tsx (账号列表页)
 */
export async function listAccounts(
  page = 1,
  pageSize = 20
): Promise<AccountListResponse> {
  const qs = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  return request<AccountListResponse>(`/accounts?${qs}`);
}

/**
 * getAccount - 获取账号详情
 *
 * 调用后端 API: GET /api/v1/accounts/{accountId}
 *
 * 参数:
 * - accountId: 账号 ID
 *
 * 返回:
 * - AccountDetail (包含完整账号信息和 recent_tasks)
 *
 * 调用方:
 * - frontend/app/accounts/[id]/page.tsx (账号详情页)
 * - frontend/app/accounts/[id]/edit/page.tsx (编辑页加载数据)
 */
export async function getAccount(accountId: string): Promise<AccountDetail> {
  return request<AccountDetail>(`/accounts/${accountId}`);
}

/**
 * updateAccount - 更新账号
 *
 * 调用后端 API: PATCH /api/v1/accounts/{accountId}
 *
 * 参数:
 * - accountId: 账号 ID
 * - data: AccountUpdateRequest (部分更新，只更新提供的字段)
 *
 * 返回:
 * - AccountSummary (更新后的账号摘要)
 *
 * 调用方:
 * - frontend/app/accounts/[id]/edit/page.tsx (编辑页保存)
 */
export async function updateAccount(
  accountId: string,
  data: AccountUpdateRequest
): Promise<AccountSummary> {
  return request<AccountSummary>(`/accounts/${accountId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

/**
 * runAccount - 手动触发账号运行
 *
 * 调用后端 API: POST /api/v1/accounts/{accountId}/run
 *
 * 【与 Scheduler 的区别】
 * - 手动触发: allow_auto=False，强制创建新任务
 * - 自动触发: allow_auto=True，由 Scheduler 调用
 *
 * 参数:
 * - accountId: 账号 ID
 *
 * 返回:
 * - AccountRunData (包含 account_id, task_id, status, operation_mode)
 *
 * 调用方:
 * - frontend/app/accounts/page.tsx (列表页运行按钮)
 * - frontend/app/accounts/[id]/page.tsx (详情页运行按钮)
 *
 * 异常:
 * - 409 Conflict: 已有运行中的任务
 * - 400 Bad Request: 账号已禁用或 positioning 为空
 */
export async function runAccount(accountId: string): Promise<AccountRunData> {
  return request<AccountRunData>(`/accounts/${accountId}/run`, {
    method: "POST",
  });
}

/**
 * enableAccount - 启用账号
 *
 * 调用后端 API: POST /api/v1/accounts/{accountId}/enable
 *
 * 启用后账号可以被 Scheduler 扫描到（如果 auto_run_enabled=True）。
 *
 * 参数:
 * - accountId: 账号 ID
 *
 * 返回:
 * - AccountSummary (更新后的账号摘要)
 *
 * 调用方:
 * - frontend/app/accounts/[id]/page.tsx (详情页启用按钮)
 */
export async function enableAccount(accountId: string): Promise<AccountSummary> {
  return request<AccountSummary>(`/accounts/${accountId}/enable`, {
    method: "POST",
  });
}

/**
 * disableAccount - 禁用账号
 *
 * 调用后端 API: POST /api/v1/accounts/{accountId}/disable
 *
 * 禁用后账号不会被 Scheduler 扫描到，不会出现在定时任务中。
 *
 * 参数:
 * - accountId: 账号 ID
 *
 * 返回:
 * - AccountSummary (更新后的账号摘要)
 *
 * 调用方:
 * - frontend/app/accounts/[id]/page.tsx (详情页禁用按钮)
 */
export async function disableAccount(accountId: string): Promise<AccountSummary> {
  return request<AccountSummary>(`/accounts/${accountId}/disable`, {
    method: "POST",
  });
}

// =============================================================================
// Draft 草稿箱相关 API
// =============================================================================

/** 草稿列表（分页） */
export async function listDrafts(
  page = 1,
  pageSize = 20,
  filters?: { draft_status?: string; publish_status?: string; account_id?: string }
): Promise<DraftListResponse> {
  const qs = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (filters?.draft_status) qs.set("draft_status", filters.draft_status);
  if (filters?.publish_status) qs.set("publish_status", filters.publish_status);
  if (filters?.account_id) qs.set("account_id", filters.account_id);
  return request<DraftListResponse>(`/drafts?${qs}`);
}

/** 获取待确认草稿数量 */
export async function getPendingDraftCount(accountId?: string): Promise<{ count: number }> {
  const qs = accountId ? `?account_id=${accountId}` : "";
  return request<{ count: number }>(`/drafts/pending-count${qs}`);
}

/** 获取草稿详情 */
export async function getDraft(draftId: number): Promise<DraftDetail> {
  return request<DraftDetail>(`/drafts/${draftId}`);
}

/** 确认发布草稿 */
export async function confirmPublishDraft(draftId: number): Promise<DraftConfirmData> {
  return request<DraftConfirmData>(`/drafts/${draftId}/confirm-publish`, {
    method: "POST",
  });
}

/** 废弃草稿 */
export async function discardDraft(draftId: number): Promise<DraftDiscardData> {
  return request<DraftDiscardData>(`/drafts/${draftId}/discard`, {
    method: "POST",
  });
}

/** 拒绝草稿 */
export async function rejectDraft(draftId: number): Promise<DraftRejectData> {
  return request<DraftRejectData>(`/drafts/${draftId}/reject`, {
    method: "POST",
  });
}

/** 从草稿重跑 */
export async function rerunFromDraft(draftId: number): Promise<DraftRerunData> {
  return request<DraftRerunData>(`/drafts/${draftId}/rerun`, {
    method: "POST",
  });
}

// =============================================================================
// WeChat 相关 API
// =============================================================================

import type {
  WeChatConfigSummary,
  WeChatConfigCreate,
  WeChatConfigUpdate,
  WeChatTestConnectionRequest,
  WeChatTestConnectionResponse,
} from "@/types";

/** 获取账号的微信配置 */
export async function getWeChatConfig(accountId: string): Promise<WeChatConfigSummary> {
  return request<WeChatConfigSummary>(`/wechat/config/${accountId}`);
}

/** 创建微信配置 */
export async function createWeChatConfig(data: WeChatConfigCreate): Promise<{
  account_id: string;
  app_id_masked: string;
  has_app_secret: boolean;
  is_enabled: boolean;
}> {
  return request(`/wechat/config`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/** 更新微信配置 */
export async function updateWeChatConfig(
  accountId: string,
  data: WeChatConfigUpdate
): Promise<{
  account_id: string;
  app_id_masked: string;
  has_app_secret: boolean;
  is_enabled: boolean;
}> {
  return request(`/wechat/config/${accountId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

/** 测试微信连接 */
export async function testWeChatConnection(
  data: WeChatTestConnectionRequest
): Promise<WeChatTestConnectionResponse> {
  return request<WeChatTestConnectionResponse>("/wechat/test-connection", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/** 发布草稿到微信 */
export async function publishDraftToWeChat(
  draftId: number
): Promise<WeChatPublishResult> {
  return request<WeChatPublishResult>(`/drafts/${draftId}/publish-to-wechat`, {
    method: "POST",
  });
}

/** 获取草稿的微信发布状态 */
export async function getDraftWeChatStatus(
  draftId: number
): Promise<WeChatPublishStatus> {
  return request<WeChatPublishStatus>(`/drafts/${draftId}/wechat-status`);
}

/** 获取草稿的所有发布记录 */
export async function getDraftPublishRecords(
  draftId: number
): Promise<PublishRecordListResponse> {
  return request<PublishRecordListResponse>(`/drafts/${draftId}/publish-records`);
}

/** 重试发布草稿到微信 */
export async function retryPublishDraft(
  draftId: number
): Promise<WeChatPublishResult> {
  return request<WeChatPublishResult>(`/drafts/${draftId}/retry-publish`, {
    method: "POST",
  });
}

/** 获取单个发布记录 */
export async function getPublishRecord(
  recordId: number
): Promise<PublishRecord> {
  return request<PublishRecord>(`/wechat/publish-records/${recordId}`);
}

/** 刷新发布状态 */
export async function refreshPublishStatus(
  recordId: number
): Promise<RefreshStatusResponse> {
  return request<RefreshStatusResponse>(`/wechat/publish-records/${recordId}/refresh-status`, {
    method: "POST",
  });
}
