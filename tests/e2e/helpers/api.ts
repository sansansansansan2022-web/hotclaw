import type { APIRequestContext, APIResponse } from "@playwright/test";

type ApiEnvelope<T> = {
  code: number;
  message?: string;
  data: T;
  details?: unknown;
};

type ApiRoot = "api" | "raw";
type ConfigValueType = "string" | "number" | "boolean" | "json";

export interface AccountData {
  account_id: string;
  name: string;
  is_active: boolean;
  operation_mode: string;
}

export interface DraftSummaryData {
  id: number;
  task_id: string;
  account_id: string | null;
  title: string;
  draft_status: string;
  publish_status: string;
}

export interface DraftDetailData extends DraftSummaryData {
  publish_error_message?: string | null;
  confirmed_at?: string | null;
  confirmed_by?: string | null;
  published_at?: string | null;
}

export interface PublishRecordData {
  id: number;
  draft_id: number;
  account_id: string;
  task_id?: string | null;
  wechat_draft_id?: string | null;
  media_id?: string | null;
  publish_id?: string | null;
  article_id?: string | null;
  publish_status: string;
  source_mode: string;
  trigger_type: string;
  publish_attempt: number;
  retry_count: number;
  parent_record_id?: number | null;
  error_code?: string | null;
  error_message?: string | null;
  request_snapshot?: string | null;
  response_snapshot?: string | null;
  url?: string | null;
  created_at: string;
  updated_at?: string | null;
}

export interface TaskDetailData {
  task_id: string;
  account_id: string | null;
  account_name: string | null;
  status: string;
  workflow_id: string;
  error_message?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  elapsed_seconds?: number | null;
  total_tokens?: number | null;
  latest_draft?: {
    id: number;
    account_id: string | null;
    title: string;
    draft_status: string;
    publish_status: string;
    updated_at: string | null;
  } | null;
}

export interface DraftListResponseData {
  drafts: DraftSummaryData[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages?: number;
  };
}

export interface PublishRecordListData {
  draft_id: number;
  total: number;
  records: PublishRecordData[];
}

export class HotClawApi {
  readonly apiBaseURL: string;

  constructor(
    private readonly request: APIRequestContext,
    baseURL = process.env.E2E_API_BASE_URL ?? "http://127.0.0.1:8107",
  ) {
    this.apiBaseURL = baseURL.replace(/\/$/, "");
  }

  private buildUrl(path: string, root: ApiRoot): string {
    const normalized = path.startsWith("/") ? path : `/${path}`;
    return root === "api"
      ? `${this.apiBaseURL}/api/v1${normalized}`
      : `${this.apiBaseURL}${normalized}`;
  }

  private async readBody<T>(response: APIResponse): Promise<T> {
    const text = await response.text();
    const body = text ? JSON.parse(text) : null;

    if (!response.ok()) {
      const detail =
        typeof body?.detail === "string"
          ? body.detail
          : typeof body?.message === "string"
            ? body.message
            : response.statusText();
      throw new Error(`HTTP ${response.status()}: ${detail}`);
    }

    if (body && typeof body === "object" && "code" in body) {
      const envelope = body as ApiEnvelope<T>;
      if (envelope.code !== 0) {
        const dataError =
          envelope.data && typeof envelope.data === "object" && "error" in (envelope.data as Record<string, unknown>)
            ? String((envelope.data as Record<string, unknown>).error ?? envelope.message ?? "Request failed")
            : envelope.message ?? "Request failed";
        throw new Error(dataError);
      }
      return envelope.data;
    }

    return body as T;
  }

  private async get<T>(path: string, root: ApiRoot = "api"): Promise<T> {
    const response = await this.request.get(this.buildUrl(path, root));
    return this.readBody<T>(response);
  }

  private async post<T>(path: string, data?: unknown, root: ApiRoot = "api"): Promise<T> {
    const response = await this.request.post(this.buildUrl(path, root), { data });
    return this.readBody<T>(response);
  }

  async createAccount(overrides: Record<string, unknown> = {}): Promise<AccountData> {
    const suffix = `${Date.now()}-${Math.floor(Math.random() * 1000)}`;
    return this.post<AccountData>("/accounts", {
      name: `E2E Account ${suffix}`,
      positioning: `HotClaw E2E positioning ${suffix}`,
      operation_mode: "semi_auto",
      auto_run_enabled: false,
      auto_publish_enabled: false,
      is_active: true,
      ...overrides,
    });
  }

  async createWeChatConfig(accountId: string, overrides: Record<string, unknown> = {}): Promise<Record<string, unknown>> {
    return this.post<Record<string, unknown>>(`/accounts/${accountId}/wechat-config`, {
      app_id: "e2e-app-id",
      app_secret: "e2e-app-secret",
      default_author: "HotClaw E2E",
      default_thumb_media_id: "thumb-e2e-001",
      need_open_comment: true,
      only_fans_can_comment: false,
      is_enabled: true,
      ...overrides,
    });
  }

  async getTask(taskId: string): Promise<TaskDetailData> {
    return this.get<TaskDetailData>(`/tasks/${taskId}`);
  }

  async getDraft(draftId: number): Promise<DraftDetailData> {
    return this.get<DraftDetailData>(`/drafts/${draftId}`);
  }

  async listDrafts(filters: { accountId?: string; draftStatus?: string; publishStatus?: string } = {}): Promise<DraftListResponseData> {
    const params = new URLSearchParams();
    params.set("page", "1");
    params.set("page_size", "100");
    if (filters.accountId) params.set("account_id", filters.accountId);
    if (filters.draftStatus) params.set("draft_status", filters.draftStatus);
    if (filters.publishStatus) params.set("publish_status", filters.publishStatus);
    return this.get<DraftListResponseData>(`/drafts?${params.toString()}`);
  }

  async getDraftPublishRecords(draftId: number): Promise<PublishRecordListData> {
    return this.get<PublishRecordListData>(`/drafts/${draftId}/publish-records`);
  }

  async getLatestPublishRecordForDraft(draftId: number): Promise<PublishRecordData | null> {
    const payload = await this.getDraftPublishRecords(draftId);
    return payload.records[0] ?? null;
  }

  async getPublishRecord(recordId: number): Promise<PublishRecordData> {
    return this.get<PublishRecordData>(`/wechat/publish-records/${recordId}`);
  }

  async upsertSystemConfig(key: string, value: string, valueType: ConfigValueType = "string"): Promise<void> {
    const updateResponse = await this.request.put(this.buildUrl(`/system-configs/${key}`, "raw"), {
      data: { value, value_type: valueType },
    });

    if (updateResponse.status() === 404) {
      const createResponse = await this.request.post(this.buildUrl("/system-configs", "raw"), {
        data: {
          key,
          value,
          value_type: valueType,
          category: "app",
          description: "HotClaw E2E test config",
          is_sensitive: false,
        },
      });
      await this.readBody<Record<string, unknown>>(createResponse);
      return;
    }

    await this.readBody<Record<string, unknown>>(updateResponse);
  }

  async setE2EModes(options: {
    generationMode?: "real" | "fake_success" | "fake_failure";
    generationFailureMessage?: string;
    publishMode?: "real" | "fake_success" | "fake_failure";
    publishFailureMessage?: string;
  }): Promise<void> {
    if (options.generationMode) {
      await this.upsertSystemConfig("e2e_generation_mode", options.generationMode);
    }
    if (options.generationFailureMessage) {
      await this.upsertSystemConfig("e2e_generation_failure_message", options.generationFailureMessage);
    }
    if (options.publishMode) {
      await this.upsertSystemConfig("e2e_publish_mode", options.publishMode);
    }
    if (options.publishFailureMessage) {
      await this.upsertSystemConfig("e2e_publish_failure_message", options.publishFailureMessage);
    }
  }

  async resetE2EModes(): Promise<void> {
    await this.setE2EModes({
      generationMode: "real",
      generationFailureMessage: "E2E fake generation failure",
      publishMode: "real",
      publishFailureMessage: "E2E fake publish failure",
    });
  }
}
