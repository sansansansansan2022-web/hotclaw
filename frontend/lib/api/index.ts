import type {
  AccountCreateData,
  AccountMemoryActionResponse,
  AccountMemoryListResponse,
  AccountCreateRequest,
  AccountDetail,
  AutomationPlan,
  CreateAutomationPlanRequest,
  CreateReferenceSourceRequest,
  ComposePreviewResponse,
  ComposeSelectionSessionBundle,
  ExistingAccountAnalysisRequest,
  ExistingAccountAnalysisResponse,
  AccountListResponse,
  AccountRunData,
  AccountStyleProfileActionResponse,
  AccountStyleProfileResponse,
  ApiOriginDebugInfo,
  ApiOriginSource,
  AppLocale,
  AccountSummary,
  RecommendationBucketedResponse,
  RecommendationSelectResponse,
  ReferenceSource,
  ReferenceSourceListResponse,
  SyncReferenceSourceResponse,
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
  TaskArtifact,
  TaskArtifactListResponse,
  TaskEffectiveInputResponse,
  TaskListResponse,
  TaskNodeListResponse,
  UpdateAutomationPlanRequest,
  UpdateReferenceSourceRequest,
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

const LOCAL_DEV_API_ORIGIN = "http://127.0.0.1:8000";

interface LLMProviderTemplate {
  provider_id: string;
  name: string;
  description: string;
  base_url: string;
  default_model: string;
  supported_models: string[];
}

interface LLMProviderCreateRequest {
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
  extra_config?: Record<string, unknown> | null;
}

interface LLMProviderUpdateRequest {
  name?: string;
  description?: string;
  api_key?: string;
  base_url?: string;
  default_model?: string;
  supported_models?: string[];
  is_enabled?: boolean;
  is_default?: boolean;
  timeout?: number;
  extra_config?: Record<string, unknown> | null;
  status?: string;
}

interface LLMProviderTestRequest {
  provider_id: string;
  api_key?: string;
  base_url?: string;
  model?: string;
}

interface LLMProviderTestResponse {
  success: boolean;
  latency_ms?: number;
  response_preview?: string;
  error_message?: string;
}

export const LLM_PROVIDER_TEMPLATES: LLMProviderTemplate[] = [
  {
    provider_id: "dashscope",
    name: "DashScope",
    description: "Alibaba DashScope compatible endpoint for Qwen models.",
    base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    default_model: "qwen-turbo",
    supported_models: ["qwen-turbo", "qwen-plus", "qwen-max"],
  },
  {
    provider_id: "openai",
    name: "OpenAI",
    description: "OpenAI API for GPT models.",
    base_url: "https://api.openai.com/v1",
    default_model: "gpt-4o-mini",
    supported_models: ["gpt-4o-mini", "gpt-4.1-mini", "gpt-4.1"],
  },
  {
    provider_id: "deepseek",
    name: "DeepSeek",
    description: "DeepSeek compatible chat completion endpoint.",
    base_url: "https://api.deepseek.com/v1",
    default_model: "deepseek-chat",
    supported_models: ["deepseek-chat", "deepseek-reasoner"],
  },
  {
    provider_id: "compatible",
    name: "Compatible API",
    description: "OpenAI-compatible self-hosted or third-party endpoint.",
    base_url: "http://localhost:8000/v1",
    default_model: "custom-model",
    supported_models: ["custom-model"],
  },
];

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

const devLoggedApiOrigins = new Set<string>();

function normalizeOrigin(origin?: string): string | null {
  if (!origin) return null;
  return origin.replace(/\/$/, "");
}

function getRelativeApiOrigin(): string {
  return process.env.NODE_ENV === "production" ? "" : LOCAL_DEV_API_ORIGIN;
}

function getEnvelopeErrorMessage<T>(envelope: ApiEnvelope<T>): string {
  const dataMessage =
    envelope.data && typeof envelope.data === "object" && "message" in envelope.data
      ? (envelope.data as { message?: unknown }).message
      : undefined;

  if (typeof dataMessage === "string" && dataMessage.trim()) {
    return dataMessage;
  }

  if (typeof envelope.message === "string" && envelope.message.trim()) {
    return envelope.message;
  }

  return "Request failed";
}

function formatErrorDetail(detail: unknown): string | undefined {
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === "string" && item.trim()) {
          return item;
        }

        if (item && typeof item === "object") {
          const record = item as Record<string, unknown>;
          const location = Array.isArray(record.loc)
            ? record.loc
                .map((part) => String(part).trim())
                .filter(Boolean)
                .join(".")
            : "";
          const message =
            (typeof record.msg === "string" && record.msg.trim() && record.msg) ||
            (typeof record.message === "string" && record.message.trim() && record.message) ||
            "";
          if (!message) {
            return "";
          }
          return location ? `${location}: ${message}` : message;
        }

        return "";
      })
      .filter(Boolean);

    return messages.length ? messages.join("; ") : undefined;
  }

  if (detail && typeof detail === "object") {
    const record = detail as Record<string, unknown>;
    const message =
      (typeof record.message === "string" && record.message.trim() && record.message) ||
      (typeof record.detail === "string" && record.detail.trim() && record.detail) ||
      (typeof record.error === "string" && record.error.trim() && record.error) ||
      undefined;
    if (message) {
      return message;
    }

    try {
      return JSON.stringify(detail);
    } catch {
      return undefined;
    }
  }

  return undefined;
}

function resolveApiOrigin(): ApiOriginDebugInfo {
  const runtimeOrigin =
    typeof window !== "undefined"
      ? normalizeOrigin((window as Window & { __HOTCLAW_API_ORIGIN__?: string }).__HOTCLAW_API_ORIGIN__)
      : null;
  if (runtimeOrigin) {
    return { origin: runtimeOrigin, source: "runtime" };
  }

  const envOrigin =
    normalizeOrigin(process.env.NEXT_PUBLIC_HOTCLAW_API_ORIGIN) ??
    normalizeOrigin(process.env.HOTCLAW_API_ORIGIN);
  if (envOrigin) {
    return { origin: envOrigin, source: "env" };
  }

  return {
    origin: getRelativeApiOrigin(),
    source: "relative",
  };
}

function logApiOriginOnce(info: ApiOriginDebugInfo): void {
  if (process.env.NODE_ENV === "production" || typeof window === "undefined") {
    return;
  }

  const label = info.origin || "/api";
  const key = `${info.source}:${label}`;
  if (devLoggedApiOrigins.has(key)) {
    return;
  }

  devLoggedApiOrigins.add(key);
  console.info("[HotClaw][api-origin]", { origin: label, source: info.source });

  if (info.source === "relative") {
    if (info.origin) {
      console.warn(
        `[HotClaw][api-origin] NEXT_PUBLIC_HOTCLAW_API_ORIGIN is unset. Falling back to direct dev API origin ${info.origin}.`,
      );
    } else {
      console.warn("[HotClaw][api-origin] NEXT_PUBLIC_HOTCLAW_API_ORIGIN is unset. Falling back to same-origin /api proxy.");
    }
  }
}

export function getApiOriginDebugInfo(): ApiOriginDebugInfo {
  const info = resolveApiOrigin();
  logApiOriginOnce(info);
  return info;
}

function buildUrl(path: string, root: ApiRoot = "v1"): string {
  const info = getApiOriginDebugInfo();
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const basePath = root === "raw" ? "" : "/api/v1";
  return `${info.origin}${basePath}${normalizedPath}`;
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
        ? (body as { detail?: unknown }).detail
        : undefined;
    const formattedDetail = formatErrorDetail(detail);
    const message =
      formattedDetail ||
      (body && typeof body === "object" && "message" in body
        ? String((body as { message?: string }).message ?? "Request failed")
        : response.statusText || "Request failed");
    throw new ApiError(message, response.status, undefined, detail);
  }

  if (body && typeof body === "object" && "code" in body) {
    const envelope = body as ApiEnvelope<T>;
    if (envelope.code !== 0) {
      throw new ApiError(getEnvelopeErrorMessage(envelope), response.status, envelope.code, envelope.details);
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

export async function listTasks(page = 1, pageSize = 20, status?: string, accountId?: string): Promise<TaskListResponse> {
  return request<TaskListResponse>(`/tasks${toQuery({ page, page_size: pageSize, status, account_id: accountId })}`);
}

export async function listAccountTasks(accountId: string, page = 1, pageSize = 20, status?: string): Promise<TaskListResponse> {
  return listTasks(page, pageSize, status, accountId);
}

export async function getTaskDetail(taskId: string): Promise<TaskDetail> {
  return request<TaskDetail>(`/tasks/${taskId}`);
}

export async function getTaskNodes(taskId: string): Promise<TaskNodeListResponse> {
  return request<TaskNodeListResponse>(`/tasks/${taskId}/nodes`);
}

export async function getTaskArtifacts(taskId: string): Promise<TaskArtifactListResponse> {
  return request<TaskArtifactListResponse>(`/tasks/${taskId}/artifacts`);
}

export async function getTaskArtifact(taskId: string, artifactKey: string): Promise<TaskArtifact> {
  return request<TaskArtifact>(`/tasks/${taskId}/artifacts/${artifactKey}`);
}

export async function getTaskEffectiveInput(taskId: string): Promise<TaskEffectiveInputResponse> {
  return request<TaskEffectiveInputResponse>(`/tasks/${taskId}/effective-input`);
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

export async function analyzeExistingAccount(
  data: ExistingAccountAnalysisRequest,
): Promise<ExistingAccountAnalysisResponse> {
  return request<ExistingAccountAnalysisResponse>("/account-onboarding/analyze-existing", {
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

export async function listAccountMemories(
  accountId: string,
  params?: { query?: string; page?: number; page_size?: number },
): Promise<AccountMemoryListResponse> {
  return request<AccountMemoryListResponse>(
    `/accounts/${accountId}/article-memories${toQuery({
      query: params?.query,
      page: params?.page,
      page_size: params?.page_size,
    })}`,
  );
}

export async function searchAccountMemories(accountId: string, query: string): Promise<AccountMemoryListResponse> {
  return listAccountMemories(accountId, { query });
}

export async function rebuildAccountMemories(accountId: string): Promise<AccountMemoryActionResponse> {
  return request<AccountMemoryActionResponse>(`/accounts/${accountId}/article-memories/rebuild`, {
    method: "POST",
  });
}

export async function syncAccountMemories(accountId: string): Promise<AccountMemoryActionResponse> {
  return request<AccountMemoryActionResponse>(`/accounts/${accountId}/article-memories/sync`, {
    method: "POST",
  });
}

export async function getAccountStyleProfile(accountId: string): Promise<AccountStyleProfileResponse> {
  return request<AccountStyleProfileResponse>(`/accounts/${accountId}/style-profile`);
}

export async function rebuildAccountStyleProfile(accountId: string): Promise<AccountStyleProfileActionResponse> {
  return request<AccountStyleProfileActionResponse>(`/accounts/${accountId}/style-profile/rebuild`, {
    method: "POST",
  });
}

export async function updateAccount(accountId: string, data: AccountUpdateRequest): Promise<AccountSummary> {
  return request<AccountSummary>(`/accounts/${accountId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function listReferenceSources(accountId: string): Promise<ReferenceSourceListResponse> {
  return request<ReferenceSourceListResponse>(`/accounts/${accountId}/reference-sources`);
}

export async function createSelectionSession(
  accountId: string,
  data?: {
    creation_note?: string;
    preferred_lane?: string;
    title_direction?: string;
    reference_source_ids?: number[];
  },
): Promise<ComposeSelectionSessionBundle> {
  return request<ComposeSelectionSessionBundle>(`/accounts/${accountId}/selection-sessions`, {
    method: "POST",
    body: JSON.stringify(data ?? {}),
  });
}

export async function getSelectionSession(
  accountId: string,
  sessionId: string,
): Promise<ComposeSelectionSessionBundle> {
  return request<ComposeSelectionSessionBundle>(`/accounts/${accountId}/selection-sessions/${sessionId}`);
}

export async function getRecommendations(
  accountId: string,
  params?: {
    source_type?: string;
    sort_by?: "relevance" | "freshness";
    status?: string;
    min_count?: 5 | 8 | 10;
  },
): Promise<RecommendationBucketedResponse> {
  return request<RecommendationBucketedResponse>(
    `/accounts/${accountId}/recommendations${toQuery({
      source_type: params?.source_type,
      sort_by: params?.sort_by,
      status: params?.status,
      min_count: params?.min_count,
    })}`,
  );
}

export async function refreshRecommendations(
  accountId: string,
  params?: { min_count?: 5 | 8 | 10 },
): Promise<RecommendationBucketedResponse> {
  return request<RecommendationBucketedResponse>(
    `/accounts/${accountId}/recommendations/refresh${toQuery({ min_count: params?.min_count })}`,
    {
      method: "POST",
    },
  );
}

export async function selectRecommendations(
  accountId: string,
  data: {
    recommendation_ids: string[];
    action: "use_for_creation" | "save_as_reference" | "dismiss" | "remove_from_creation";
    selection_session_id?: string;
  },
): Promise<RecommendationSelectResponse> {
  return request<RecommendationSelectResponse>(`/accounts/${accountId}/recommendations/select`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function selectReferenceSourcesForSession(
  accountId: string,
  sessionId: string,
  data: { reference_source_ids: number[] },
): Promise<ComposeSelectionSessionBundle> {
  return request<ComposeSelectionSessionBundle>(
    `/accounts/${accountId}/selection-sessions/${sessionId}/reference-sources/select`,
    {
      method: "POST",
      body: JSON.stringify(data),
    },
  );
}

export async function confirmSelectionSources(
  accountId: string,
  sessionId: string,
  data?: { confirmed?: boolean },
): Promise<ComposeSelectionSessionBundle> {
  return request<ComposeSelectionSessionBundle>(
    `/accounts/${accountId}/selection-sessions/${sessionId}/confirm-sources`,
    {
      method: "POST",
      body: JSON.stringify(data ?? { confirmed: true }),
    },
  );
}

export async function confirmSelectionOutline(
  accountId: string,
  sessionId: string,
  data: {
    preview_version: number;
    approved_outline_seed: Record<string, unknown>;
  },
): Promise<ComposeSelectionSessionBundle["selection_session"]> {
  return request<ComposeSelectionSessionBundle["selection_session"]>(
    `/accounts/${accountId}/selection-sessions/${sessionId}/confirm-outline`,
    {
      method: "POST",
      body: JSON.stringify(data),
    },
  );
}

export async function buildComposePreview(
  accountId: string,
  data: {
    selection_session_id: string;
    creation_note?: string;
    preferred_lane?: string;
    title_direction?: string;
    preview_payload?: Record<string, unknown>;
  },
): Promise<ComposePreviewResponse> {
  return request<ComposePreviewResponse>(`/accounts/${accountId}/compose-preview`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function submitSelectionSession(
  accountId: string,
  sessionId: string,
  data?: {
    creation_note?: string;
    preferred_lane?: string;
    title_direction?: string;
    preview_payload?: Record<string, unknown>;
  },
): Promise<AccountRunData> {
  return request<AccountRunData>(`/accounts/${accountId}/selection-sessions/${sessionId}/submit`, {
    method: "POST",
    body: JSON.stringify(data ?? {}),
  });
}

export async function getAutomationPlan(accountId: string): Promise<AutomationPlan> {
  return request<AutomationPlan>(`/accounts/${accountId}/automation-plan`);
}

export async function createAutomationPlan(
  accountId: string,
  data: CreateAutomationPlanRequest,
): Promise<AutomationPlan> {
  return request<AutomationPlan>(`/accounts/${accountId}/automation-plan`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateAutomationPlan(
  accountId: string,
  data: UpdateAutomationPlanRequest,
): Promise<AutomationPlan> {
  return request<AutomationPlan>(`/accounts/${accountId}/automation-plan`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function createReferenceSource(
  accountId: string,
  data: CreateReferenceSourceRequest,
): Promise<ReferenceSource> {
  return request<ReferenceSource>(`/accounts/${accountId}/reference-sources`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateReferenceSource(
  accountId: string,
  sourceId: number,
  data: UpdateReferenceSourceRequest,
): Promise<ReferenceSource> {
  return request<ReferenceSource>(`/accounts/${accountId}/reference-sources/${sourceId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function syncReferenceSource(
  accountId: string,
  sourceId: number,
): Promise<SyncReferenceSourceResponse> {
  return request<SyncReferenceSourceResponse>(`/accounts/${accountId}/reference-sources/${sourceId}/sync`, {
    method: "POST",
  });
}

export async function runAccount(accountId: string): Promise<AccountRunData> {
  if (process.env.NODE_ENV !== "production" && typeof window !== "undefined") {
    console.info("[HotClaw][account-run]", {
      accountId,
      endpoint: buildUrl(`/accounts/${accountId}/run`),
    });
  }
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

export async function createAccountWeChatConfig(
  accountId: string,
  data: Omit<WeChatConfigCreate, "account_id">,
): Promise<WeChatConfigSummary> {
  return request<WeChatConfigSummary>(`/accounts/${accountId}/wechat-config`, {
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

export async function testAccountWeChatConfig(accountId: string): Promise<WeChatTestConnectionResponse> {
  return request<WeChatTestConnectionResponse>(`/accounts/${accountId}/wechat-config/test`, {
    method: "POST",
  });
}

export async function listLLMProviders(): Promise<LLMProviderInfo[]> {
  return request<LLMProviderInfo[]>("/llm-providers");
}

export async function createLLMProvider(data: LLMProviderCreateRequest): Promise<LLMProviderInfo> {
  return request<LLMProviderInfo>("/llm-providers", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateLLMProvider(
  providerId: string,
  data: LLMProviderUpdateRequest,
): Promise<LLMProviderInfo> {
  return request<LLMProviderInfo>(`/llm-providers/${providerId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteLLMProvider(providerId: string): Promise<void> {
  await request(`/llm-providers/${providerId}`, {
    method: "DELETE",
  });
}

export async function testLLMProvider(data: LLMProviderTestRequest): Promise<LLMProviderTestResponse> {
  return request<LLMProviderTestResponse>("/llm-providers/test", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function setDefaultLLMProvider(providerId: string): Promise<{ provider_id: string; message: string }> {
  return request<{ provider_id: string; message: string }>(`/llm-providers/active/default/${providerId}`, {
    method: "POST",
  });
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

export interface AgentCreateRequest {
  agent_id: string;
  name?: string;
  description?: string;
  prompt_template?: string;
  model_config_data?: Record<string, unknown>;
  retry_config?: Record<string, unknown>;
}

export interface AgentCreateResponse {
  agent_id: string;
  name: string;
  description: string | null;
  prompt_template: string | null;
  model_config_data: Record<string, unknown> | null;
  retry_config: Record<string, unknown> | null;
  created_at: string | null;
}

export async function createAgent(
  config: AgentCreateRequest,
): Promise<AgentCreateResponse> {
  return request<AgentCreateResponse>("/agents", {
    method: "POST",
    body: JSON.stringify(config),
  });
}

export async function deleteAgentConfig(
  agentId: string,
): Promise<{ agent_id: string; deleted: boolean }> {
  return request<{ agent_id: string; deleted: boolean }>(`/agents/${agentId}/config`, {
    method: "DELETE",
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

export type { AgentInfo, LLMProviderInfo, PaginationMeta, SkillInfo };
