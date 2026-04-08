/** Shared type definitions for HotClaw frontend. */

export type ApiOriginSource = "runtime" | "env" | "relative";

export interface ApiOriginDebugInfo {
  origin: string;
  source: ApiOriginSource;
}

export type TaskStatus = "pending" | "running" | "completed" | "failed";
export type NodeStatus = "pending" | "running" | "completed" | "failed" | "skipped";
export type OperationMode = "manual" | "semi_auto" | "full_auto";
export type PostingFrequency = "daily" | "weekly" | "biweekly" | "monthly";
export type DraftStatus = "draft" | "pending_review" | "approved" | "rejected" | "discarded" | "published";
export type PublishStatus = "not_published" | "pending" | "publishing" | "published" | "failed" | "skipped" | "unknown";
export type SourceType = "manual_task" | "semi_auto_task";
export type ToastTone = "brand" | "success" | "warning" | "danger" | "info";

export interface ApiResponse<T = unknown> {
  code: number;
  message: string;
  data: T;
  details?: Record<string, unknown> | null;
}

export interface PaginationMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages?: number;
}

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
  account_id: string | null;
  account_name: string | null;
  status: TaskStatus;
  input_data: { positioning?: string; [key: string]: unknown } | null;
  workflow_id: string;
  result_data: TaskResultData | null;
  error_message?: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  elapsed_seconds: number | null;
  total_tokens: number | null;
}

export interface TaskProgressData {
  total_nodes: number;
  completed_nodes: number;
  current_node_index: number;
}

export interface TaskStatusResponse {
  task_id: string;
  status: TaskStatus;
  current_node?: string | null;
  progress?: TaskProgressData | null;
  started_at?: string | null;
  elapsed_seconds?: number | null;
}

export interface TaskResultData {
  input?: { positioning: string };
  profile?: AccountProfile;
  style_profile?: StyleProfile | Record<string, unknown> | null;
  retrieved_memories?: ContentMemory[] | Record<string, unknown> | null;
  outline_plan?: OutlinePlan | Record<string, unknown> | null;
  section_drafts?: SectionDraft[] | Record<string, unknown> | null;
  review_results?: ReviewResult[] | Record<string, unknown> | null;
  rewrite_result?: RewriteResult | Record<string, unknown> | null;
  evaluation?: EvaluationSummary | Record<string, unknown> | null;
  hot_topics?: { hot_topics: HotTopic[] };
  topics?: { topics: TopicCandidate[] };
  titles?: { selected_topic: string; titles: TitleCandidate[] };
  content?: ArticleContent;
  audit_result?: AuditResult;
  [key: string]: unknown;
}

export interface AccountProfile {
  domain?: string;
  subdomain?: string;
  target_audience?: {
    age_range?: string;
    occupation?: string;
    interests?: string[];
  };
  tone?: string;
  content_style?: string;
  keywords?: string[];
  positioning_raw?: string;
}

export interface HotTopic {
  title: string;
  source?: string;
  heat_score?: number;
  summary?: string;
  relevance_score?: number;
}

export interface TopicCandidate {
  title: string;
  angle?: string;
  hook?: string;
  target_emotion?: string;
  estimated_appeal?: number;
  reasoning?: string;
}

export interface TitleCandidate {
  text: string;
  style?: string;
  score?: number;
  reasoning?: string;
}

export interface ArticleContent {
  content_markdown: string;
  word_count?: number;
  structure?: {
    sections?: { heading: string; summary: string }[];
  };
  tags?: string[];
}

export interface ContentMemory {
  id: number | string;
  title: string;
  summary?: string | null;
  tags?: string[] | null;
  source_draft_id?: number | null;
  source_task_id?: string | null;
  article_id?: string | null;
  content_excerpt?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface OutlineSection {
  id?: number | string | null;
  title: string;
  summary?: string | null;
  goal?: string | null;
  notes?: string | null;
}

export interface OutlinePlan {
  summary?: string | null;
  sections: OutlineSection[];
  raw?: Record<string, unknown> | null;
}

export interface SectionDraft {
  id?: number | string | null;
  heading: string;
  summary?: string | null;
  content_markdown?: string | null;
  content_html?: string | null;
  status?: string | null;
}

export interface ReviewIssueDetail {
  title?: string | null;
  description: string;
  severity?: string | null;
  location?: string | null;
  suggestion?: string | null;
}

export interface ReviewResult {
  reviewer?: string | null;
  passed?: boolean | null;
  summary?: string | null;
  issues?: ReviewIssueDetail[] | null;
  raw?: Record<string, unknown> | null;
}

export interface RewriteResult {
  title?: string | null;
  summary?: string | null;
  notes?: string | null;
  content_markdown?: string | null;
  content_html?: string | null;
  changed_sections?: string[] | null;
  raw?: Record<string, unknown> | null;
}

export interface EvaluationDimension {
  score?: number | null;
  explanation?: string | null;
  badges?: string[] | null;
}

export interface EvaluationSummary {
  style_score?: number | null;
  structure_score?: number | null;
  evidence_score?: number | null;
  readability_score?: number | null;
  final_score?: number | null;
  summary?: string | null;
  dimensions?: Record<string, EvaluationDimension> | null;
  raw?: Record<string, unknown> | null;
}

export interface StyleProfile {
  summary?: string | null;
  tone_profile?: string | null;
  title_style?: string | null;
  intro_style?: string | null;
  structure_style?: string | null;
  cta_style?: string | null;
  lexical_features?: string[] | null;
  banned_patterns?: string[] | null;
  evidence_article_ids?: Array<number | string> | null;
  raw?: Record<string, unknown> | null;
}

export interface NodeRun {
  node_id: string;
  agent_id: string;
  name?: string;
  status: NodeStatus;
  input_data: Record<string, unknown> | null;
  output_data: Record<string, unknown> | null;
  started_at: string | null;
  completed_at: string | null;
  elapsed_seconds: number | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  model_used?: string | null;
  degraded: boolean;
  error_message: string | null;
}

export interface TaskSummary {
  task_id: string;
  account_id: string | null;
  account_name: string | null;
  positioning_summary: string;
  status: TaskStatus;
  created_at: string;
  elapsed_seconds: number | null;
  error_message: string | null;
  audit_result: AuditResult | null;
}

export interface TaskListResponse {
  tasks: TaskSummary[];
  pagination: PaginationMeta;
}

export interface TaskNodeListResponse {
  nodes: NodeRun[];
}

export interface AuditResult {
  passed: boolean;
  risk_level: "low" | "medium" | "high" | "unknown" | string;
  issues: AuditIssue[];
  overall_comment: string;
}

export interface AuditIssue {
  type: string;
  description: string;
  severity: "low" | "medium" | "high" | string;
  location?: string;
}

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

export interface AgentCharacter {
  agent_id: string;
  name: string;
  role: string;
  color: string;
  accent: string;
  deskX: number;
  deskY: number;
  idleFrames: number;
}

export interface DashboardStats {
  account_name: string;
  followers: number;
  total_reads: number;
  avg_reads: number;
  articles_count: number;
  weekly_growth: number;
}

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
  publish_paused?: boolean;
  max_posts_per_day?: number | null;
  min_interval_minutes?: number | null;
}

export interface AccountUpdateRequest extends Partial<AccountCreateRequest> {}

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
  last_publish_status?: string | null;
  last_publish_error_message?: string | null;
  last_published_at?: string | null;
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
  publish_paused: boolean;
  max_posts_per_day: number | null;
  min_interval_minutes: number | null;
  last_publish_status: string | null;
  last_publish_error_message: string | null;
  last_published_at: string | null;
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
  pagination: PaginationMeta;
}

export type PublishDecision = "ALLOW_PUBLISH" | "SAVE_AS_DRAFT" | "SKIP" | "BLOCK";

export interface PublishDecisionResult {
  decision: PublishDecision;
  reason_code: string;
  reason_message: string;
  checks: Record<string, unknown>;
}

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
  title_candidates: Array<string | Record<string, unknown>> | null;
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
  style_profile?: StyleProfile | Record<string, unknown> | null;
  retrieved_memories?: ContentMemory[] | Record<string, unknown> | null;
  outline_plan?: OutlinePlan | Record<string, unknown> | null;
  section_drafts?: SectionDraft[] | Record<string, unknown> | null;
  review_results?: ReviewResult[] | Record<string, unknown> | null;
  rewrite_result?: RewriteResult | Record<string, unknown> | null;
  evaluation?: EvaluationSummary | Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface DraftListResponse {
  drafts: DraftSummary[];
  pagination: PaginationMeta;
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

export interface WeChatConfigSummary {
  account_id: string;
  app_id_masked: string;
  has_app_secret: boolean;
  default_author: string | null;
  default_thumb_media_id?: string | null;
  need_open_comment?: boolean;
  only_fans_can_comment?: boolean;
  is_enabled: boolean;
  test_status: string | null;
  test_message: string | null;
  last_sync_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface WeChatConfigDetail extends WeChatConfigSummary {
  need_open_comment: boolean;
  only_fans_can_comment: boolean;
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

export interface PublishRecord {
  id: number;
  draft_id?: number;
  account_id?: string;
  task_id?: string | null;
  wechat_draft_id?: string | null;
  media_id?: string | null;
  publish_id?: string | null;
  article_id?: string | null;
  url?: string | null;
  publish_status: string;
  source_mode: string;
  trigger_type: string;
  publish_attempt: number;
  retry_count: number;
  error_code?: string;
  error_message?: string;
  started_at?: string;
  published_at?: string;
  finished_at?: string;
  last_checked_at?: string;
  created_at: string;
}

export interface PublishRecordListResponse {
  draft_id: number;
  total: number;
  records: PublishRecord[];
}

export interface RefreshStatusResponse {
  record_id: number;
  previous_status: string;
  new_status: string;
  synced_draft: boolean;
  message: string;
}

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

export interface SkillInfo {
  skill_id: string;
  name: string;
  description: string;
  version: string;
  config_data: Record<string, unknown> | null;
  status: string;
}

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

export type SystemConfigValue = string | number | boolean | Record<string, unknown> | Array<unknown> | null;
export type SystemConfigMap = Record<string, SystemConfigValue>;
export type AppLocale = "en" | "zh-CN";

export interface AppSession {
  email: string;
  displayName: string;
  provider: "local_adapter";
}

export interface AccountMemoryListResponse {
  account_id: string;
  total: number;
  query?: string | null;
  memories: ContentMemory[];
}

export interface AccountMemoryActionResponse {
  account_id: string;
  status: string;
  message?: string | null;
  job_id?: string | null;
}

export interface AccountStyleProfileResponse {
  account_id: string;
  generated_at?: string | null;
  style_profile: StyleProfile | null;
}

export interface AccountStyleProfileActionResponse {
  account_id: string;
  status: string;
  message?: string | null;
  generated_at?: string | null;
}
