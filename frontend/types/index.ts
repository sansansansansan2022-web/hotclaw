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
export type AutomationPlanType = OperationMode;
export type AutomationRunStrategy = "manual_only" | "scheduled" | "hybrid";
export type AutomationScheduleType = "none" | "daily" | "weekly" | "monthly";
export type DraftStatus = "draft" | "pending_review" | "approved" | "rejected" | "discarded" | "published";
export type PublishStatus = "not_published" | "pending" | "publishing" | "published" | "failed" | "skipped" | "unknown";
export type SourceType = "manual_task" | "semi_auto_task";
export type ToastTone = "brand" | "success" | "warning" | "danger" | "info";
export type ReferenceSourceType = "wechat_account" | "article_url" | "pasted_article";
export type ReferenceSourceSyncStatus = "pending" | "synced" | "failed" | "manual_only";
export type AccountHealthStatus = "ready" | "attention" | "risk_recovery";

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
  ops_context?: OpsContext | null;
  error_message?: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  elapsed_seconds: number | null;
  total_tokens: number | null;
  latest_draft?: {
    id: number;
    account_id: string | null;
    title: string;
    draft_status: DraftStatus;
    publish_status: PublishStatus;
    updated_at: string | null;
  } | null;
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

export interface TaskArtifact {
  artifact_key: string;
  stage: string;
  title: string;
  status: "available" | "pending" | "failed" | "missing" | string;
  display_payload: Record<string, unknown> | null;
  raw_output: Record<string, unknown> | null;
  source_node_ids: string[];
  updated_at: string | null;
}

export interface TaskArtifactListResponse {
  task_id: string;
  account_id: string | null;
  status: TaskStatus | string;
  artifacts: TaskArtifact[];
}

export interface TaskEffectiveInputResponse {
  task_id: string;
  account_id: string | null;
  workflow_id: string;
  status: TaskStatus | string;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  positioning: string | null;
  ops_context: OpsContext | Record<string, unknown> | null;
  explicit_input: Record<string, unknown>;
  selection_session_id: string | null;
  selected_recommendations: Record<string, unknown>[];
  selected_reference_sources: Record<string, unknown>[];
  compose_preview: Record<string, unknown> | null;
  query_plan: QueryPlanInsight | Record<string, unknown> | null;
  reference_digest: ReferenceDigestInsight | Record<string, unknown> | null;
  outline_seed: OutlinePlan | Record<string, unknown> | null;
  creation_note: string | null;
  external_evidence: Record<string, unknown> | null;
  input_data: Record<string, unknown>;
}

export interface TaskResultData {
  input?: { positioning: string };
  profile?: AccountProfile;
  query_plan?: QueryPlanInsight | Record<string, unknown> | null;
  reference_digest?: ReferenceDigestInsight | Record<string, unknown> | null;
  source_candidates?: SourceCandidateInsight[] | Record<string, unknown> | null;
  style_profile?: StyleProfile | Record<string, unknown> | null;
  retrieved_memories?: ContentMemory[] | Record<string, unknown> | null;
  outline_plan?: OutlinePlan | Record<string, unknown> | null;
  section_drafts?: SectionDraft[] | Record<string, unknown> | null;
  style_review?: ReviewResult | Record<string, unknown> | null;
  structure_review?: ReviewResult | Record<string, unknown> | null;
  review_results?: ReviewResult[] | Record<string, unknown> | null;
  rewrite_result?: RewriteResult | Record<string, unknown> | null;
  evaluation?: EvaluationSummary | Record<string, unknown> | null;
  content_pipeline?: {
    version?: string | null;
    used_structured_pipeline?: boolean;
    fallback_to_content_writer?: boolean;
    degraded?: boolean;
    fallback_reason?: string | null;
  } | null;
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

export interface QueryPlanInsight {
  lane?: {
    id?: string | null;
    label?: string | null;
    input_hint?: string | null;
    reason?: string | null;
  } | null;
  selected_topic?: string | null;
  selected_title?: string | null;
  primary_queries?: string[] | null;
  secondary_queries?: string[] | null;
  source_preferences?: string[] | null;
  banned_angles?: string[] | null;
  account_keywords?: string[] | null;
  search_terms?: string[] | null;
}

export interface SourceCandidateInsight {
  source_id?: string | null;
  source_type?: string | null;
  source_name?: string | null;
  source_title: string;
  url?: string | null;
  snippet?: string | null;
  fit_score?: number | null;
  origin?: string | null;
  why_selected?: string | null;
}

export interface ReferenceDigestSource {
  source_id?: string | null;
  source_type?: string | null;
  source_name?: string | null;
  source_title?: string | null;
  style_brief?: string | null;
  structure_brief?: string | null;
  useful_points?: string[] | null;
  snippet?: string | null;
  origin?: string | null;
  fit_score?: number | null;
}

export interface ReferenceDigestInsight {
  summary?: string | null;
  source_count?: number | null;
  selected_source_ids?: string[] | null;
  preferred_source_names?: string[] | null;
  style_takeaways?: string[] | null;
  structure_takeaways?: string[] | null;
  useful_points?: string[] | null;
  usage_rules?: string[] | null;
  source_digests?: ReferenceDigestSource[] | null;
  source_snippets?: Array<Record<string, unknown>> | null;
  raw?: Record<string, unknown> | null;
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
  selected_topic?: string | null;
  title_candidates?: string[] | null;
  selected_title?: string | null;
  summary?: string | null;
  content_markdown: string;
  content_html?: string | null;
  word_count?: number;
  structure?: {
    sections?: {
      section_id?: string | number | null;
      heading: string;
      summary: string;
      word_count?: number | null;
      evidence_refs?: string[] | null;
    }[];
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
  section_id?: number | string | null;
  title: string;
  heading?: string | null;
  summary?: string | null;
  goal?: string | null;
  purpose?: string | null;
  key_points?: string[] | null;
  tone_hint?: string | null;
  evidence_refs?: string[] | null;
  notes?: string | null;
}

export interface OutlinePlan {
  article_goal?: string | null;
  target_reader_takeaway?: string | null;
  opening_hook?: string | null;
  summary?: string | null;
  sections: OutlineSection[];
  ending_cta?: string | null;
  estimated_word_count?: number | null;
  raw?: Record<string, unknown> | null;
}

export interface SectionDraft {
  id?: number | string | null;
  section_id?: number | string | null;
  heading: string;
  summary?: string | null;
  content_markdown?: string | null;
  content_html?: string | null;
  word_count?: number | null;
  evidence_refs?: string[] | null;
  status?: string | null;
}

export interface ReviewIssueDetail {
  code?: string | null;
  title?: string | null;
  description: string;
  severity?: string | null;
  location?: string | null;
  section_id?: string | null;
  suggestion?: string | null;
}

export interface ReviewResult {
  reviewer?: string | null;
  passed?: boolean | null;
  score?: number | null;
  summary?: string | null;
  rewrite_suggestions?: string[] | null;
  issues?: ReviewIssueDetail[] | null;
  failed?: boolean | null;
  degraded?: boolean | null;
  error_message?: string | null;
  raw?: Record<string, unknown> | null;
}

export interface RewriteResult {
  title?: string | null;
  summary?: string | null;
  notes?: string | null;
  used_rewrite?: boolean | null;
  content_markdown?: string | null;
  content_html?: string | null;
  fixed_issues?: string[] | null;
  changed_sections?: string[] | null;
  rewrite_failed?: boolean | null;
  rewrite_skipped?: boolean | null;
  failure_reason?: string | null;
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
  repetition_score?: number | null;
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

export interface AutomationPlanSummary {
  id: number | null;
  account_id: string;
  config_source: "plan" | "legacy_fallback";
  plan_type: AutomationPlanType;
  is_enabled: boolean;
  run_strategy: AutomationRunStrategy;
  schedule_type: AutomationScheduleType;
  schedule_config: Record<string, unknown> | null;
  schedule_summary: string | null;
  auto_publish_enabled: boolean;
  publish_review_required: boolean;
  max_posts_per_day: number | null;
  min_interval_minutes: number | null;
  timezone: string;
  next_run_at: string | null;
  last_run_at: string | null;
  notes: string | null;
  latest_status: string | null;
  is_active_plan: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface AutomationPlan extends AutomationPlanSummary {}

export interface AccountHealthSummary {
  status: AccountHealthStatus;
  issues: string[];
}

export interface RunStrategy {
  allow_run: boolean;
  requested_mode?: OperationMode | null;
  effective_mode: OperationMode;
  allow_auto_publish: boolean;
  preferred_reference_source_ids: string[];
  avoid_recent_topics: string[];
  preferred_content_lane?: string | null;
  degraded_from?: OperationMode | null;
  degrade_reason?: string | null;
}

export interface OpsContext {
  generated_at?: string | null;
  trigger?: {
    source?: "manual" | "scheduler" | string;
    requested_plan_type?: OperationMode | string | null;
  } | null;
  account_health: AccountHealthSummary;
  operation_stage?: string | null;
  run_strategy: RunStrategy;
  ops_notes: string[];
  signals?: {
    enabled_reference_source_count?: number;
    pending_review_count?: number;
    recent_failed_publish_count?: number;
    recent_success_publish_count?: number;
    recent_failed_task_count?: number;
    recent_task_count?: number;
    recent_draft_count?: number;
    recent_publish_count?: number;
    preferred_content_lane?: string | null;
    [key: string]: unknown;
  } | null;
  fallback_used?: boolean;
  account_summary?: {
    account_id?: string;
    account_name?: string;
  } | null;
}

export interface CreateAutomationPlanRequest {
  plan_type?: AutomationPlanType;
  is_enabled?: boolean;
  run_strategy?: AutomationRunStrategy;
  schedule_type?: AutomationScheduleType;
  schedule_config?: Record<string, unknown> | null;
  auto_publish_enabled?: boolean;
  publish_review_required?: boolean;
  max_posts_per_day?: number | null;
  min_interval_minutes?: number | null;
  timezone?: string;
  notes?: string;
}

export interface UpdateAutomationPlanRequest extends Partial<CreateAutomationPlanRequest> {}

export interface AccountCreateRequest {
  name: string;
  category?: string;
  positioning: string;
  audience?: string;
  tone_style?: string;
  // Legacy scheduling inputs kept for compatibility while AutomationPlan
  // remains the runtime source of truth.
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
  automation_plan?: CreateAutomationPlanRequest;
}

export interface AccountUpdateRequest extends Partial<AccountCreateRequest> {}

export interface AccountSummary {
  account_id: string;
  name: string;
  category: string | null;
  positioning: string;
  // Compatibility mirror fields only. Prefer automation_plan_summary on detail.
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
  reference_source_count: number;
  reference_source_enabled_count: number;
  reference_source_last_sync_status: string | null;
  // Frontend primary source for effective automation semantics.
  automation_plan_summary?: AutomationPlanSummary | null;
  latest_ops_context?: OpsContext | null;
  latest_effective_mode?: OperationMode | null;
  latest_allow_auto_publish?: boolean | null;
  latest_ops_degraded?: boolean;
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

export type AccountOnboardingPath = "new" | "existing";
export type AccountOnboardingStep = "choose" | "new_details" | "existing_input" | "wechat_connect" | "existing_review";
export type AccountWeChatOnboardingMode = "connect_now" | "skip_for_now";

export interface ExistingAccountAnalysisRequest {
  account_name: string;
  article_urls?: string[];
  article_texts?: string[];
}

export interface ExistingAccountAnalysisResponse {
  account_name: string;
  inferred_positioning: string;
  inferred_audience: string;
  inferred_tone_style: string;
  inferred_content_strategy: string;
  inferred_reference_accounts_summary: string | null;
  recommended_operation_mode: OperationMode;
  onboarding_notes: string[];
  extracted_topics: string[];
  style_summary: string;
  analysis_confidence: "low" | "medium" | "high";
  source_summary: string;
  used_article_count: number;
}

export interface ReferenceSource {
  id: number;
  account_id: string;
  source_type: ReferenceSourceType;
  name: string;
  source_value: string;
  notes: string | null;
  is_enabled: boolean;
  sync_status: ReferenceSourceSyncStatus;
  last_synced_at: string | null;
  article_count: number;
  latest_error_message: string | null;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface ReferenceSourceListResponse {
  account_id: string;
  sources: ReferenceSource[];
  total: number;
}

export interface CreateReferenceSourceRequest {
  source_type: ReferenceSourceType;
  name?: string;
  source_value: string;
  notes?: string;
  is_enabled?: boolean;
}

export interface UpdateReferenceSourceRequest {
  name?: string;
  notes?: string;
  is_enabled?: boolean;
}

export interface SyncReferenceSourceResponse {
  source: ReferenceSource;
  message: string;
}

export interface RecommendationSource {
  source_type: string;
  source_name: string | null;
  source_url: string | null;
  published_at: string | null;
}

export interface RecommendationScores {
  relevance: number | null;
  authority: number | null;
  freshness: number | null;
  overall: number | null;
}

export interface RecommendationRationale {
  reason: string | null;
  evidence_points: string[];
}

export interface RecommendedContentItem {
  id: string;
  account_id: string;
  title: string;
  summary: string | null;
  source: RecommendationSource;
  scores: RecommendationScores;
  rationale: RecommendationRationale;
  topic_tags: string[];
  risk_flags: string[];
  status: string;
  created_at: string;
  updated_at: string;
}

export interface RecommendationCoverage {
  requested_min_count: number;
  high_relevance_count: number;
  extended_count: number;
  returned_count: number;
  shortage_count: number;
  meets_requested_min_count: boolean;
}

export interface RecommendationShortageNotice {
  status: "ok" | "insufficient_high_relevance" | "insufficient_total";
  reason_code: string | null;
  message: string | null;
  recommended_action: string | null;
}

export interface RecommendationSourceDiagnostic {
  source_key: string;
  label: string;
  source_type: string;
  status: "success" | "empty" | "failed" | "disabled" | "not_applicable" | "cached_only";
  query: string | null;
  candidate_count: number;
  high_relevance_count: number;
  extended_count: number;
  filtered_out_count: number;
  error_code: string | null;
  error_message: string | null;
  detail: string | null;
}

export interface RecommendationFilterDiagnostics {
  raw_candidate_count: number;
  high_relevance_count: number;
  extended_count: number;
  filtered_out_count: number;
  filtered_low_relevance_count: number;
  filtered_low_authority_count: number;
  sources_with_candidates: number;
  sources_failed_or_disabled: number;
}

export interface RecommendationListFilters {
  source_type: string | null;
  sort_by: "relevance" | "freshness";
  status: string | null;
}

export interface RecommendationListSummary {
  source_counts: Record<string, number>;
  status_counts: Record<string, number>;
  high_relevance_count: number;
  extended_count: number;
}

export interface RecommendationBucketedResponse {
  account_id: string;
  filters: RecommendationListFilters;
  summary: RecommendationListSummary;
  min_count: 5 | 8 | 10;
  high_relevance_items: RecommendedContentItem[];
  extended_items: RecommendedContentItem[];
  total: number;
  coverage: RecommendationCoverage;
  shortage_notice: RecommendationShortageNotice;
  source_diagnostics: RecommendationSourceDiagnostic[];
  filter_diagnostics: RecommendationFilterDiagnostics;
  refreshed_at: string | null;
}

export interface ComposeSelectionSession {
  id: string;
  account_id: string;
  selected_recommendation_ids: string[];
  selected_reference_source_ids: string[];
  creation_note: string | null;
  preferred_lane: string | null;
  title_direction: string | null;
  source_confirmed: boolean;
  outline_confirmed: boolean;
  preview_version: number;
  approved_outline_seed: Record<string, unknown> | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface SelectedSource {
  id: string;
  title: string;
  summary: string | null;
  source_type: string;
  source_name: string | null;
  source_url: string | null;
  reason: string | null;
  topic_tags: string[];
}

export interface SelectedReferenceSource {
  id: number;
  name: string;
  source_type: string;
  sync_status: string;
  notes: string | null;
  preview: string | null;
}

export interface ComposeSelectionSessionBundle {
  selection_session: ComposeSelectionSession;
  selected_recommendations: SelectedSource[];
  selected_reference_sources: SelectedReferenceSource[];
}

export interface RecommendationSelectResponse {
  selection_session: ComposeSelectionSession | null;
  selected_recommendations: SelectedSource[];
  selected_reference_sources: SelectedReferenceSource[];
}

export interface ComposeProfileSummary {
  positioning_summary: string;
  audience_summary: string | null;
  tone_summary: string | null;
  preferred_lane: string | null;
  style_keywords: string[];
  creation_note: string | null;
}

export interface ComposeSourceBundle {
  selected_source_count: number;
  selected_reference_source_count: number;
  source_types: string[];
}

export interface ComposeLane {
  id: string;
  label: string;
  input_hint: string | null;
  reason: string;
}

export interface ComposeQueryPlan {
  lane: ComposeLane;
  selected_topic: string | null;
  selected_title: string | null;
  primary_queries: string[];
  secondary_queries: string[];
  source_preferences: string[];
  banned_angles: string[];
  search_terms: string[];
}

export interface TopicDirection {
  title: string;
  angle: string;
  topic_kind: string;
  reason: string;
  source_ids: string[];
}

export interface TitleDirection {
  title: string;
  style: string;
  rationale: string;
}

export interface OutlineSectionPreview {
  section_id: string;
  heading: string;
  purpose: string;
  key_points: string[];
  evidence_refs: string[];
}

export interface OutlinePreview {
  article_goal: string;
  why_this_topic: string;
  strategic_angle: string;
  reference_basis: string;
  target_reader: string;
  content_lane: string;
  target_reader_takeaway: string;
  opening_hook: string;
  emotional_arc: string;
  sections: OutlineSectionPreview[];
  ending_cta: string;
  estimated_word_count: number;
  summary: string;
}

export interface CitationGuardrails {
  must_ground_titles_in_evidence: boolean;
  must_ground_repo_names_in_evidence: boolean;
}

export interface ComposePreviewResponse {
  selection_session: ComposeSelectionSession;
  account_profile_summary: ComposeProfileSummary;
  source_bundle: ComposeSourceBundle;
  selected_sources: SelectedSource[];
  selected_reference_sources: SelectedReferenceSource[];
  query_plan: ComposeQueryPlan;
  topic_directions: TopicDirection[];
  title_directions: TitleDirection[];
  outline_preview: OutlinePreview;
  citation_guardrails: CitationGuardrails;
}

export type ReferenceSourceSelectionCard = ReferenceSource & {
  selected?: boolean;
  preview?: string | null;
};

export interface AccountRunData {
  account_id: string;
  task_id: string;
  status: TaskStatus;
  operation_mode: OperationMode;
  effective_mode?: OperationMode | null;
  selection_session_id?: string | null;
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
  style_review?: ReviewResult | Record<string, unknown> | null;
  structure_review?: ReviewResult | Record<string, unknown> | null;
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
  simulated?: boolean;
  simulation_source?: string | null;
  provider?: string | null;
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
  publish_record_id?: number;
  decision?: PublishDecisionResult;
  error?: string;
  simulated?: boolean;
  simulation_source?: string | null;
  provider?: string | null;
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
  parent_record_id?: number | null;
  error_code?: string;
  error_message?: string;
  request_snapshot?: string | null;
  response_snapshot?: string | null;
  simulated?: boolean;
  simulation_source?: string | null;
  provider?: string | null;
  started_at?: string;
  published_at?: string;
  finished_at?: string;
  last_checked_at?: string;
  created_at: string;
  updated_at?: string;
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

export interface AgentUpdateRequest {
  model_config_data?: Record<string, unknown>;
  prompt_template?: string;
  retry_config?: Record<string, unknown>;
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
