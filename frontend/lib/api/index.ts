import type {
  AccountCreateData,
  AccountCreateRequest,
  AccountDetail,
  AccountListResponse,
  AccountRunData,
  AppLocale,
  AccountSummary,
  AccountUpdateRequest,
  AgentInfo,
  DraftConfirmData,
  DraftDetail,
  DraftDiscardData,
  DraftListResponse,
  DraftRejectData,
  DraftRerunData,
  LLMProviderInfo,
  PaginationMeta,
  PublishRecord,
  PublishRecordListResponse,
  RefreshStatusResponse,
  SkillInfo,
  SystemConfigMap,
  SystemConfigValue,
  TaskCreateData,
  TaskDetail,
  TaskListResponse,
  TaskNodeListResponse,
  WeChatConfigCreate,
  WeChatConfigDetail,
  WeChatConfigSummary,
  WeChatConfigUpdate,
  WeChatPublishResult,
  WeChatPublishStatus,
  WeChatTestConnectionRequest,
  WeChatTestConnectionResponse,
} from "@/types";

type ApiRoot = "v1" | "raw";

interface ApiEnvelope<T> {
  code: number;
  message?: string;
  data: T;
  details?: Record<string, unknown> | null;
}

export class ApiError extends Error {
  status: number;
  code?: number;
  details?: unknown;

  constructor(message: string, status: number, code?: number, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function normalizeOrigin(origin?: string): string | null {
  if (!origin) return null;
  return origin.replace(/\/$/, "");
}

function getApiOrigin(): string {
  const envOrigin =
    normalizeOrigin(process.env.NEXT_PUBLIC_HOTCLAW_API_ORIGIN) ??
    normalizeOrigin(process.env.HOTCLAW_API_ORIGIN);
  if (envOrigin) return envOrigin;
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "http://127.0.0.1:8000";
}

function buildUrl(path: string, root: ApiRoot = "v1"): string {
  const base = root === "raw" ? getApiOrigin() : `${getApiOrigin()}/api/v1`;
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}

function repairText(value: string): string {
  if (!value || /[\u3400-\u9fff]/.test(value) || !/[\u0080-\u00ff]/.test(value)) {
    return value;
  }

  try {
    const bytes = Uint8Array.from(Array.from(value, (character) => character.charCodeAt(0) & 0xff));
    const repaired = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    if (repaired === value || /[\uFFFD]/.test(repaired)) {
      return value;
    }
    return /[\u3400-\u9fff]/.test(repaired) || /[^\u0000-\u007f]/.test(repaired) ? repaired : value;
  } catch {
    return value;
  }
}

function normalizePayload<T>(value: T): T {
  if (typeof value === "string") {
    return repairText(value) as T;
  }

  if (Array.isArray(value)) {
    return value.map((item) => normalizePayload(item)) as T;
  }

  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, item]) => [key, normalizePayload(item)]),
    ) as T;
  }

  return value;
}

async function parseBody<T>(response: Response): Promise<T | ApiEnvelope<T> | null> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return null;
  }
  return response.json() as Promise<T | ApiEnvelope<T>>;
}

async function request<T>(path: string, init?: RequestInit, root: ApiRoot = "v1"): Promise<T> {
  const response = await fetch(buildUrl(path, root), {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  const body = await parseBody<T>(response);

  if (!response.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body
        ? (body as { detail?: string }).detail
        : undefined;
    const message =
      detail ||
      (body && typeof body === "object" && "message" in body
        ? String((body as { message?: string }).message ?? "Request failed")
        : response.statusText || "Request failed");
    throw new ApiError(message, response.status);
  }

  if (body && typeof body === "object" && "code" in body) {
    const envelope = body as ApiEnvelope<T>;
    if (envelope.code !== 0) {
      throw new ApiError(envelope.message || "Request failed", response.status, envelope.code, envelope.details);
    }
    return normalizePayload(envelope.data);
  }

  return normalizePayload((body as T) ?? ({} as T));
}

function toQuery(params: Record<string, string | number | undefined | null>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  }
  const text = query.toString();
  return text ? `?${text}` : "";
}

export function getTaskStreamUrl(taskId: string): string {
  return buildUrl(`/tasks/${taskId}/stream`);
}

export async function createTask(positioning: string, workflowId = "default_pipeline"): Promise<TaskCreateData> {
  return request<TaskCreateData>("/tasks", {
    method: "POST",
    body: JSON.stringify({ positioning, workflow_id: workflowId }),
  });
}

export async function listTasks(page = 1, pageSize = 20, status?: string): Promise<TaskListResponse> {
  return request<TaskListResponse>(`/tasks${toQuery({ page, page_size: pageSize, status })}`);
}

export async function getTaskDetail(taskId: string): Promise<TaskDetail> {
  return request<TaskDetail>(`/tasks/${taskId}`);
}

export async function getTaskNodes(taskId: string): Promise<TaskNodeListResponse> {
  return request<TaskNodeListResponse>(`/tasks/${taskId}/nodes`);
}

export async function rerunTask(taskId: string): Promise<TaskCreateData> {
  return request<TaskCreateData>(`/tasks/${taskId}/rerun`, { method: "POST" });
}

export async function createAccount(data: AccountCreateRequest): Promise<AccountCreateData> {
  return request<AccountCreateData>("/accounts", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listAccounts(page = 1, pageSize = 20): Promise<AccountListResponse> {
  return request<AccountListResponse>(`/accounts${toQuery({ page, page_size: pageSize })}`);
}

export async function getAccount(accountId: string): Promise<AccountDetail> {
  return request<AccountDetail>(`/accounts/${accountId}`);
}

export async function updateAccount(accountId: string, data: AccountUpdateRequest): Promise<AccountSummary> {
  return request<AccountSummary>(`/accounts/${accountId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function runAccount(accountId: string): Promise<AccountRunData> {
  return request<AccountRunData>(`/accounts/${accountId}/run`, { method: "POST" });
}

export async function enableAccount(accountId: string): Promise<AccountSummary> {
  return request<AccountSummary>(`/accounts/${accountId}/enable`, { method: "POST" });
}

export async function disableAccount(accountId: string): Promise<AccountSummary> {
  return request<AccountSummary>(`/accounts/${accountId}/disable`, { method: "POST" });
}

export async function listDrafts(
  page = 1,
  pageSize = 20,
  filters?: { draft_status?: string; publish_status?: string; account_id?: string },
): Promise<DraftListResponse> {
  return request<DraftListResponse>(
    `/drafts${toQuery({
      page,
      page_size: pageSize,
      draft_status: filters?.draft_status,
      publish_status: filters?.publish_status,
      account_id: filters?.account_id,
    })}`,
  );
}

export async function getDraft(draftId: number): Promise<DraftDetail> {
  return request<DraftDetail>(`/drafts/${draftId}`);
}

export async function getPendingDraftCount(accountId?: string): Promise<{ count: number; account_id?: string | null }> {
  try {
    return await request<{ count: number; account_id?: string | null }>(`/drafts/pending-count${toQuery({ account_id: accountId })}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 422) {
      const fallback = await listDrafts(1, 1, { account_id: accountId, draft_status: "pending_review" });
      return {
        count: fallback.pagination.total ?? fallback.drafts.length,
        account_id: accountId ?? null,
      };
    }

    throw error;
  }
}

export async function confirmPublishDraft(draftId: number): Promise<DraftConfirmData> {
  return request<DraftConfirmData>(`/drafts/${draftId}/confirm-publish`, { method: "POST" });
}

export async function discardDraft(draftId: number): Promise<DraftDiscardData> {
  return request<DraftDiscardData>(`/drafts/${draftId}/discard`, { method: "POST" });
}

export async function rejectDraft(draftId: number): Promise<DraftRejectData> {
  return request<DraftRejectData>(`/drafts/${draftId}/reject`, { method: "POST" });
}

export async function rerunFromDraft(draftId: number): Promise<DraftRerunData> {
  return request<DraftRerunData>(`/drafts/${draftId}/rerun`, { method: "POST" });
}

export async function publishDraftToWeChat(draftId: number): Promise<WeChatPublishResult> {
  return request<WeChatPublishResult>(`/drafts/${draftId}/publish-to-wechat`, { method: "POST" });
}

export async function retryPublishDraft(draftId: number): Promise<WeChatPublishResult> {
  return request<WeChatPublishResult>(`/drafts/${draftId}/retry-publish`, { method: "POST" });
}

export async function getDraftWeChatStatus(draftId: number): Promise<WeChatPublishStatus> {
  return request<WeChatPublishStatus>(`/drafts/${draftId}/wechat-status`);
}

export async function getDraftPublishRecords(draftId: number): Promise<PublishRecordListResponse> {
  return request<PublishRecordListResponse>(`/drafts/${draftId}/publish-records`);
}

export async function getPublishRecord(recordId: number): Promise<PublishRecord> {
  return request<PublishRecord>(`/wechat/publish-records/${recordId}`);
}

export async function refreshPublishStatus(recordId: number): Promise<RefreshStatusResponse> {
  return request<RefreshStatusResponse>(`/wechat/publish-records/${recordId}/refresh-status`, {
    method: "POST",
  });
}

export async function getWeChatConfig(accountId: string): Promise<WeChatConfigDetail> {
  return request<WeChatConfigDetail>(`/wechat/config/${accountId}`);
}

export async function createWeChatConfig(data: WeChatConfigCreate): Promise<WeChatConfigSummary> {
  return request<WeChatConfigSummary>("/wechat/config", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateWeChatConfig(accountId: string, data: WeChatConfigUpdate): Promise<WeChatConfigSummary> {
  return request<WeChatConfigSummary>(`/wechat/config/${accountId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function testWeChatConnection(data: WeChatTestConnectionRequest): Promise<WeChatTestConnectionResponse> {
  return request<WeChatTestConnectionResponse>("/wechat/test-connection", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listLLMProviders(): Promise<LLMProviderInfo[]> {
  return request<LLMProviderInfo[]>("/llm-providers");
}

export async function listAgents(): Promise<{ agents: AgentInfo[] }> {
  return request<{ agents: AgentInfo[] }>("/agents");
}

export async function getAgent(agentId: string): Promise<AgentInfo> {
  return request<AgentInfo>(`/agents/${agentId}`);
}

export async function updateAgentConfig(
  agentId: string,
  config: {
    model_config_data?: Record<string, unknown>;
    prompt_template?: string;
    retry_config?: Record<string, unknown>;
  },
): Promise<{ agent_id: string; updated_fields: string[] }> {
  return request<{ agent_id: string; updated_fields: string[] }>(`/agents/${agentId}/config`, {
    method: "PUT",
    body: JSON.stringify(config),
  });
}

export async function listSkills(): Promise<{ skills: SkillInfo[] }> {
  return request<{ skills: SkillInfo[] }>("/skills");
}

export async function getAllSystemConfigs(): Promise<SystemConfigMap> {
  return request<SystemConfigMap>("/system-configs/all", undefined, "raw");
}

export async function getSystemConfigValue(key: string, defaultValue?: string): Promise<SystemConfigValue> {
  const result = await request<{ key: string; value: SystemConfigValue }>(
    `/system-configs/${key}/value${toQuery({ default: defaultValue })}`,
    undefined,
    "raw",
  );
  return result.value;
}

export async function upsertSystemConfig(
  key: string,
  value: string,
  valueType: "string" | "number" | "boolean" | "json" = "string",
): Promise<void> {
  try {
    await request(`/system-configs/${key}`, {
      method: "PUT",
      body: JSON.stringify({ value, value_type: valueType }),
    }, "raw");
    return;
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 404) {
      throw error;
    }
  }

  await request("/system-configs", {
    method: "POST",
    body: JSON.stringify({
      key,
      value,
      value_type: valueType,
      category: "app",
      description: "Global console language",
      is_sensitive: false,
    }),
  }, "raw");
}

export async function updateGlobalLanguage(locale: AppLocale): Promise<void> {
  await upsertSystemConfig("ui_language", locale, "string");
}

export type { PaginationMeta };
