/** Shared type definitions for HotClaw frontend. */

// --- Agent / Task status ---

export type TaskStatus = "pending" | "running" | "completed" | "failed";
export type NodeStatus = "pending" | "running" | "completed" | "failed" | "skipped";

// --- API response ---

export interface ApiResponse<T = unknown> {
  code: number;
  message: string;
  data: T;
  details?: Record<string, unknown> | null;
}

// --- Task ---

export interface TaskCreateRequest {
  positioning: string;
  workflow_id?: string;
}

export interface TaskCreateData {
  task_id: string;
  status: TaskStatus;
  created_at: string;
  workflow_id: string;
}

export interface TaskDetail {
  task_id: string;
  status: TaskStatus;
  input_data: { positioning: string } | null;
  workflow_id: string;
  result_data: TaskResultData | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  elapsed_seconds: number | null;
  total_tokens: number | null;
}

// --- Task Result Data (from result_data snapshot) ---

export interface TaskResultData {
  input?: { positioning: string };
  profile?: AccountProfile;
  hot_topics?: { hot_topics: HotTopic[] };
  topics?: { topics: TopicCandidate[] };
  titles?: { selected_topic: string; titles: TitleCandidate[] };
  content?: ArticleContent;
  audit_result?: AuditResult;
  [key: string]: unknown;
}

export interface AccountProfile {
  domain: string;
  subdomain: string;
  target_audience: {
    age_range: string;
    occupation: string;
    interests: string[];
  };
  tone: string;
  content_style: string;
  keywords: string[];
  positioning_raw: string;
}

export interface HotTopic {
  title: string;
  source: string;
  heat_score: number;
  summary: string;
  relevance_score: number;
}

export interface TopicCandidate {
  title: string;
  angle: string;
  hook: string;
  target_emotion: string;
  estimated_appeal: number;
  reasoning: string;
}

export interface TitleCandidate {
  text: string;
  style: string;
  score: number;
  reasoning: string;
}

export interface ArticleContent {
  content_markdown: string;
  word_count: number;
  structure: {
    sections: { heading: string; summary: string }[];
  };
  tags: string[];
}

export interface NodeRun {
  node_id: string;
  agent_id: string;
  status: NodeStatus;
  input_data: Record<string, unknown> | null;
  output_data: Record<string, unknown> | null;
  started_at: string | null;
  completed_at: string | null;
  elapsed_seconds: number | null;
  degraded: boolean;
  error_message: string | null;
}

export interface TaskSummary {
  task_id: string;
  positioning_summary: string;
  status: TaskStatus;
  created_at: string;
  elapsed_seconds: number | null;
  error_message: string | null;
  audit_result: AuditResult | null;
}

export interface AuditResult {
  passed: boolean;
  risk_level: "low" | "medium" | "high" | "unknown";
  issues: AuditIssue[];
  overall_comment: string;
}

export interface AuditIssue {
  type: string;
  description: string;
  severity: "low" | "medium" | "high";
  location?: string;
}

// --- SSE events ---

export interface SSENodeStart {
  node_id: string;
  agent_id: string;
  name: string;
  index: number;
  total: number;
  started_at: string;
}

export interface SSENodeComplete {
  node_id: string;
  agent_id: string;
  name: string;
  elapsed_seconds: number;
  degraded: boolean;
  output_summary: string;
}

export interface SSENodeError {
  node_id: string;
  error: string;
}

export interface SSETaskComplete {
  task_id: string;
  elapsed_seconds: number;
}

// --- Agent characters ---

export interface AgentCharacter {
  agent_id: string;
  name: string;
  role: string;
  color: string;       // Primary pixel color
  accent: string;      // Secondary pixel color
  deskX: number;       // Position in office grid
  deskY: number;
  idleFrames: number;
}

// --- Dashboard ---

export interface DashboardStats {
  account_name: string;
  followers: number;
  total_reads: number;
  avg_reads: number;
  articles_count: number;
  weekly_growth: number;
}

// --- Account ---

export type OperationMode = "manual" | "semi_auto" | "full_auto";
export type PostingFrequency = "daily" | "weekly" | "biweekly" | "monthly";

export interface AccountCreateRequest {
  name: string;
  category?: string;
  positioning: string;
  audience?: string;
  tone_style?: string;
  posting_frequency?: PostingFrequency;
  posting_time?: string;
  content_strategy?: string;
  reference_accounts?: string;
  operation_mode?: OperationMode;
  auto_run_enabled?: boolean;
  auto_publish_enabled?: boolean;
  is_active?: boolean;
}

export interface AccountUpdateRequest {
  name?: string;
  category?: string;
  positioning?: string;
  audience?: string;
  tone_style?: string;
  posting_frequency?: PostingFrequency;
  posting_time?: string;
  content_strategy?: string;
  reference_accounts?: string;
  operation_mode?: OperationMode;
  auto_run_enabled?: boolean;
  auto_publish_enabled?: boolean;
  is_active?: boolean;
}

export interface AccountSummary {
  account_id: string;
  name: string;
  category: string | null;
  positioning: string;
  operation_mode: OperationMode;
  posting_frequency: PostingFrequency | null;
  auto_run_enabled: boolean;
  is_active: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  last_run_status: string | null;
  last_error_message: string | null;
  created_at: string;
}

export interface AccountTaskSummary {
  task_id: string;
  status: TaskStatus;
  created_at: string;
  elapsed_seconds: number | null;
}

export interface AccountDetail extends AccountSummary {
  audience: string | null;
  tone_style: string | null;
  posting_time: string | null;
  content_strategy: string | null;
  reference_accounts: string | null;
  auto_publish_enabled: boolean;
  updated_at: string;
  recent_tasks: AccountTaskSummary[];
}

export interface AccountCreateData {
  account_id: string;
  name: string;
  is_active: boolean;
  operation_mode: OperationMode;
}

export interface AccountRunData {
  account_id: string;
  task_id: string;
  status: TaskStatus;
  operation_mode: OperationMode;
}

export interface AccountListResponse {
  accounts: AccountSummary[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
}

// --- Draft ---

export type DraftStatus = "draft" | "pending_review" | "approved" | "rejected" | "discarded";
export type PublishStatus = "not_published" | "pending" | "publishing" | "published" | "failed" | "unknown";
export type SourceType = "manual_task" | "semi_auto_task";

export interface DraftSummary {
  id: number;
  task_id: string;
  account_id: string | null;
  title: string;
  selected_topic: string | null;
  draft_status: DraftStatus;
  publish_status: PublishStatus;
  publish_review_required: boolean;
  source_type: SourceType;
  word_count: number;
  created_at: string;
  updated_at: string;
}

export interface AuditResultInfo {
  passed: boolean;
  risk_level: string;
  overall_comment: string | null;
  issues: unknown[] | null;
}

export interface DraftDetail {
  id: number;
  task_id: string;
  account_id: string | null;
  account_name: string | null;
  title: string;
  title_candidates: unknown[] | null;
  selected_topic: string | null;
  summary: string | null;
  content_markdown: string;
  content_html: string | null;
  word_count: number;
  tags: string[] | null;
  draft_status: DraftStatus;
  publish_status: PublishStatus;
  publish_review_required: boolean;
  source_type: SourceType;
  confirmed_at: string | null;
  confirmed_by: string | null;
  published_at: string | null;
  publish_error_message: string | null;
  audit_result: AuditResultInfo | null;
  created_at: string;
  updated_at: string;
}

export interface DraftListResponse {
  drafts: DraftSummary[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
}

export interface DraftConfirmData {
  draft_id: number;
  draft_status: string;
  publish_status: string;
  confirmed_at: string;
}

export interface DraftDiscardData {
  draft_id: number;
  draft_status: string;
}

export interface DraftRejectData {
  draft_id: number;
  draft_status: string;
}

export interface DraftRerunData {
  draft_id: number;
  original_task_id: string;
  new_task_id: string;
  status: TaskStatus;
}

// --- WeChat Config ---

export interface WeChatConfigSummary {
  account_id: string;
  app_id_masked: string;
  has_app_secret: boolean;
  default_author: string | null;
  is_enabled: boolean;
  test_status: string | null;
  test_message: string | null;
  last_sync_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface WeChatConfigCreate {
  account_id: string;
  app_id: string;
  app_secret: string;
  default_author?: string;
  default_thumb_media_id?: string;
  need_open_comment?: boolean;
  only_fans_can_comment?: boolean;
  is_enabled?: boolean;
}

export interface WeChatConfigUpdate {
  app_id?: string;
  app_secret?: string;
  default_author?: string;
  default_thumb_media_id?: string;
  need_open_comment?: boolean;
  only_fans_can_comment?: boolean;
  is_enabled?: boolean;
}

export interface WeChatTestConnectionRequest {
  app_id: string;
  app_secret: string;
}

export interface WeChatTestConnectionResponse {
  success: boolean;
  message: string;
}

// --- WeChat Publish ---

export interface WeChatPublishStatus {
  has_record: boolean;
  record_id?: number;
  draft_id: number;
  wechat_draft_id?: string;
  media_id?: string;
  publish_id?: string;
  publish_status: "pending" | "publishing" | "published" | "failed" | "unknown";
  source_mode?: string;
  trigger_type?: string;
  publish_attempt?: number;
  retry_count?: number;
  error_code?: string;
  error_message?: string;
  url?: string;
  started_at?: string;
  finished_at?: string;
  published_at?: string;
  last_checked_at?: string;
  created_at?: string;
}

export interface WeChatPublishResult {
  draft_id: number;
  draft_status: string;
  publish_status: string;
  published_at: string | null;
  wechat_media_id?: string;
  wechat_publish_id?: string;
  error?: string;
}

// Publish Record
export interface PublishRecord {
  id: number;
  publish_status: string;
  source_mode: string;
  trigger_type: string;
  publish_attempt: number;
  retry_count: number;
  error_code?: string;
  error_message?: string;
  url?: string;
  started_at?: string;
  published_at?: string;
  finished_at?: string;
  created_at: string;
}

export interface PublishRecordListResponse {
  draft_id: number;
  total: number;
  records: PublishRecord[];
}

// Refresh Status Response
export interface RefreshStatusResponse {
  record_id: number;
  previous_status: string;
  new_status: string;
  synced_draft: boolean;
  message: string;
}
