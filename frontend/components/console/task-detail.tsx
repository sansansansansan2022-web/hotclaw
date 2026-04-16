"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { getTaskArtifacts, getTaskDetail, getTaskEffectiveInput, getTaskNodes, rerunTask } from "@/lib/api";
import {
  normalizeContentMemories,
  normalizeEvaluation,
  normalizeOutlinePlan,
  normalizeQueryPlan,
  normalizeReferenceDigest,
  normalizeReviewResults,
  normalizeRewriteResult,
  normalizeSectionDrafts,
  normalizeSourceCandidates,
  normalizeStyleProfile,
} from "@/lib/content-insights";
import { useI18n } from "@/lib/i18n";
import { formatDateTime, formatDuration, formatNumber, truncate } from "@/lib/utils";
import type { NodeRun, SectionDraft, TaskArtifact, TaskDetail, TaskEffectiveInputResponse } from "@/types";
import {
  EvaluationScoreCard,
  InsightDisclosureCard,
  MemoryReferenceList,
  OutlinePlanView,
  ReviewResultsView,
  RewriteResultView,
  SectionDraftsView,
  StyleProfileSummaryView,
} from "@/components/console/content-insights";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, SkeletonRows, StatCard, Table } from "@/components/console/ui";
import { Icon } from "@/components/console/icons";

function taskTone(status: string): "success" | "warning" | "danger" | "muted" {
  if (status === "completed") return "success";
  if (status === "failed") return "danger";
  if (status === "running") return "warning";
  return "muted";
}

function artifactTone(status: string): "success" | "warning" | "danger" | "muted" {
  if (status === "available") return "success";
  if (status === "failed") return "danger";
  if (status === "pending") return "warning";
  return "muted";
}

function fallbackSections(detail: TaskDetail | null): SectionDraft[] {
  const sections = detail?.result_data?.content?.structure?.sections ?? [];
  return sections.map((section, index) => ({
    id: index,
    heading: section.heading,
    summary: section.summary,
  }));
}

export function TaskDetailPage({ taskId }: { taskId: string }) {
  const { locale, taskStatusLabel } = useI18n();
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const [nodes, setNodes] = useState<NodeRun[]>([]);
  const [artifacts, setArtifacts] = useState<TaskArtifact[]>([]);
  const [effectiveInput, setEffectiveInput] = useState<TaskEffectiveInputResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async (silent = false) => {
    try {
      if (!silent) {
        setLoading(true);
      }
      setError(null);
      const [detailRes, nodesRes, artifactRes, effectiveInputRes] = await Promise.all([
        getTaskDetail(taskId),
        getTaskNodes(taskId),
        getTaskArtifacts(taskId),
        getTaskEffectiveInput(taskId),
      ]);
      setDetail(detailRes);
      setNodes(nodesRes.nodes);
      setArtifacts(artifactRes.artifacts);
      setEffectiveInput(effectiveInputRes);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : locale === "zh-CN" ? "无法加载任务详情。" : "Unable to load task detail.");
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    void load();
  }, [taskId]);

  useEffect(() => {
    if (!detail || !["pending", "running"].includes(detail.status)) {
      return;
    }
    const timer = window.setTimeout(() => {
      void load(true);
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [detail, taskId]);

  const artifactMap = useMemo(
    () => Object.fromEntries(artifacts.map((artifact) => [artifact.artifact_key, artifact])) as Record<string, TaskArtifact>,
    [artifacts],
  );

  const insights = useMemo(() => {
    const result = detail?.result_data;
    const evidenceBundle = artifactMap.evidence_bundle?.display_payload as Record<string, unknown> | null | undefined;
    const profileSnapshot = artifactMap.profile_snapshot?.display_payload as Record<string, unknown> | null | undefined;
    const outlinePreview = artifactMap.outline_preview?.display_payload as Record<string, unknown> | null | undefined;
    const sectionDrafts = artifactMap.section_drafts?.display_payload as Record<string, unknown> | null | undefined;
    const reviewSummary = artifactMap.review_summary?.display_payload as Record<string, unknown> | null | undefined;
    const rewriteSummary = artifactMap.rewrite_summary?.display_payload as Record<string, unknown> | null | undefined;
    const auditSummary = artifactMap.audit_summary?.display_payload as Record<string, unknown> | null | undefined;
    const sections = normalizeSectionDrafts((sectionDrafts?.section_drafts as unknown) ?? result?.section_drafts);
    return {
      memories: normalizeContentMemories(result?.retrieved_memories),
      queryPlan: normalizeQueryPlan((evidenceBundle?.query_plan as unknown) ?? result?.query_plan),
      sourceCandidates: normalizeSourceCandidates((evidenceBundle?.source_candidates as unknown) ?? result?.source_candidates),
      referenceDigest: normalizeReferenceDigest((evidenceBundle?.reference_digest as unknown) ?? result?.reference_digest),
      styleProfile: normalizeStyleProfile(
        (profileSnapshot?.style_profile as unknown) ?? result?.style_profile,
        (profileSnapshot?.profile as unknown) ?? result?.profile ?? null,
      ),
      outline: normalizeOutlinePlan((outlinePreview?.outline_plan as unknown) ?? result?.outline_plan),
      sections: sections.length ? sections : fallbackSections(detail),
      reviews: normalizeReviewResults(reviewSummary ?? result),
      rewrite: normalizeRewriteResult((rewriteSummary?.rewrite_result as unknown) ?? result?.rewrite_result),
      evaluation: normalizeEvaluation(auditSummary ?? result),
      topicSelection: artifactMap.topic_selection?.display_payload ?? null,
      titleCandidates: artifactMap.title_candidates?.display_payload ?? null,
      assembledArticle: artifactMap.assembled_article?.display_payload ?? null,
    };
  }, [artifactMap, detail]);

  const inputSnapshot = useMemo(() => {
    if (effectiveInput?.explicit_input && Object.keys(effectiveInput.explicit_input).length > 0) {
      return JSON.stringify(effectiveInput.explicit_input, null, 2);
    }

    if (!detail?.input_data) {
      return locale === "zh-CN" ? "暂无输入快照。" : "No input snapshot available.";
    }

    if (typeof detail.input_data.positioning === "string" && detail.input_data.positioning.trim()) {
      return detail.input_data.positioning;
    }

    return JSON.stringify(detail.input_data, null, 2);
  }, [detail, effectiveInput, locale]);

  const positioningSnapshot = useMemo(() => {
    if (typeof effectiveInput?.positioning === "string" && effectiveInput.positioning.trim()) {
      return effectiveInput.positioning;
    }
    if (typeof detail?.input_data?.positioning === "string" && detail.input_data.positioning.trim()) {
      return detail.input_data.positioning;
    }
    return inputSnapshot;
  }, [detail, effectiveInput, inputSnapshot]);

  const opsContext = detail?.ops_context ?? null;
  const runStrategy = opsContext?.run_strategy ?? null;
  const healthSummary = opsContext?.account_health ?? null;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={locale === "zh-CN" ? "执行轨迹" : "Execution Trace"}
        title={`${locale === "zh-CN" ? "任务" : "Task"} ${taskId}`}
        description={
          locale === "zh-CN"
            ? "保留原有状态、生命周期和节点调试视角，同时把账号归属和内容生产中间结果放到同一个任务详情里。"
            : "Keep the original status, lifecycle and node-trace debugger while making account ownership and content-generation artifacts first-class."
        }
        actions={
          <>
            {detail?.account_id ? (
              <>
                <Link href={`/accounts/${detail.account_id}`}>
                  <Button variant="secondary">{locale === "zh-CN" ? "返回账号" : "Back to Account"}</Button>
                </Link>
                <Link href={`/accounts/${detail.account_id}/workspace`}>
                  <Button variant="secondary">{locale === "zh-CN" ? "账号工作台" : "Account Workspace"}</Button>
                </Link>
              </>
            ) : null}
            <Button
              variant="secondary"
              data-testid="task-rerun-button"
              disabled={detail?.status === "running"}
              onClick={() => {
                void (async () => {
                  await rerunTask(taskId);
                  await load();
                })();
              }}
            >
              {locale === "zh-CN" ? "重新运行" : "Rerun"}
            </Button>
            <Link href="/tasks/history">
              <Button variant="secondary">{locale === "zh-CN" ? "返回任务历史" : "Back to History"}</Button>
            </Link>
          </>
        }
      />

      {loading ? (
        <SkeletonRows rows={4} />
      ) : error ? (
        <ErrorState title={locale === "zh-CN" ? "任务详情加载失败" : "Task detail failed to load"} description={error} retry={() => void load()} />
      ) : detail ? (
        <>
          <div className="grid gap-5 md:grid-cols-4">
            <StatCard
              label={locale === "zh-CN" ? "状态" : "Status"}
              value={taskStatusLabel(detail.status)}
              hint={locale === "zh-CN" ? "当前任务生命周期状态" : "Current task lifecycle state"}
              tone={taskTone(detail.status)}
              icon={<Icon name="history" className="h-6 w-6" />}
            />
            <StatCard
              label={locale === "zh-CN" ? "所属账号" : "Account"}
              value={detail.account_name || detail.account_id || (locale === "zh-CN" ? "未绑定" : "Unassigned")}
              hint={detail.account_id || (locale === "zh-CN" ? "这是一个全局调试任务" : "This is a global debug task")}
              tone={detail.account_id ? "brand" : "muted"}
              icon={<Icon name="accounts" className="h-6 w-6" />}
            />
            <StatCard
              label={locale === "zh-CN" ? "工作流" : "Workflow"}
              value={detail.workflow_id}
              hint={locale === "zh-CN" ? "编排器使用的工作流模板" : "Workflow template used by the orchestrator"}
              tone="info"
              icon={<Icon name="workspace" className="h-6 w-6" />}
            />
            <StatCard
              label="Tokens"
              value={formatNumber(detail.total_tokens)}
              hint={locale === "zh-CN" ? "累计 prompt 和 completion 使用量" : "Accumulated prompt and completion usage"}
              tone="muted"
              icon={<Icon name="dashboard" className="h-6 w-6" />}
            />
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.05fr_1fr]">
            <Card
              title={locale === "zh-CN" ? "任务归属与上下文" : "Ownership & Context"}
              description={
                locale === "zh-CN"
                  ? "明确这是哪个账号的运行记录，并保留回到账号和账号工作台的主路径。"
                  : "Make it obvious which account this run belongs to and preserve the path back to the account workspace."
              }
            >
              <div className="grid gap-4 text-sm text-slate-600 md:grid-cols-2">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "账号" : "Account"}</p>
                  {detail.account_id ? (
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <Badge tone="brand">{detail.account_name || detail.account_id}</Badge>
                      <span className="text-slate-400">{detail.account_id}</span>
                    </div>
                  ) : (
                    <p className="mt-2">{locale === "zh-CN" ? "未绑定账号，全局调试任务。" : "No account binding. This is a global debug task."}</p>
                  )}
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "耗时" : "Duration"}</p>
                  <p className="mt-2">{formatDuration(detail.elapsed_seconds)}</p>
                </div>
                <div className="md:col-span-2">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "定位摘要" : "Positioning Snapshot"}</p>
                  <p className="mt-2 whitespace-pre-wrap leading-7 text-slate-600">{truncate(positioningSnapshot, 260)}</p>
                </div>
              </div>
            </Card>

            <Card
              title={locale === "zh-CN" ? "生命周期" : "Lifecycle"}
              description={locale === "zh-CN" ? "任务时间戳和终态错误上下文。" : "Task timestamps and terminal error context."}
            >
              <dl className="grid gap-4 text-sm text-slate-600">
                <div className="flex items-center justify-between gap-4">
                  <dt className="text-slate-500">{locale === "zh-CN" ? "当前状态" : "Current Status"}</dt>
                  <dd>
                    <Badge data-testid="task-status-badge" data-status={detail.status} tone={taskTone(detail.status)}>
                      {taskStatusLabel(detail.status)}
                    </Badge>
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <dt className="text-slate-500">{locale === "zh-CN" ? "创建时间" : "Created"}</dt>
                  <dd>{formatDateTime(detail.created_at)}</dd>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <dt className="text-slate-500">{locale === "zh-CN" ? "开始时间" : "Started"}</dt>
                  <dd>{formatDateTime(detail.started_at)}</dd>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <dt className="text-slate-500">{locale === "zh-CN" ? "完成时间" : "Completed"}</dt>
                  <dd>{formatDateTime(detail.completed_at)}</dd>
                </div>
                <div className="border-t border-slate-200 pt-4">
                  <dt className="text-slate-500">{locale === "zh-CN" ? "错误" : "Error"}</dt>
                  <dd data-testid="task-error-message" className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">
                    {detail.error_message || (locale === "zh-CN" ? "没有终态错误。" : "No terminal error.")}
                  </dd>
                </div>
              </dl>
            </Card>
          </div>

          <Card
            title={locale === "zh-CN" ? "阶段产物" : "Stage Artifacts"}
            description={
              locale === "zh-CN"
                ? "浠ュ眬閮ㄧ敤鎴疯瑙掓煡鐪嬭繖娆′换鍔＄湡姝ｅ唴鍚冧簡浠€涔堛€佷骇鍑轰簡浠€涔堬紝鑺傜偣杞ㄨ抗鏀惧埌浜岀骇瑙嗗浘銆?"
                : "Review the user-facing stage artifacts first, then drop into node trace when you need lower-level debugging."
            }
          >
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
              {artifacts.map((artifact) => (
                <div key={artifact.artifact_key} className="rounded-2xl border border-slate-200 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{artifact.stage}</p>
                      <p className="mt-2 text-sm font-semibold text-slate-900">{artifact.title}</p>
                    </div>
                    <Badge tone={artifactTone(artifact.status)}>{artifact.status}</Badge>
                  </div>
                  <p className="mt-3 text-xs text-slate-500">
                    {formatDateTime(artifact.updated_at) || (locale === "zh-CN" ? "暂无时间" : "No timestamp")}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {artifact.source_node_ids.map((nodeId) => (
                      <Badge key={`${artifact.artifact_key}-${nodeId}`} tone="muted">
                        {nodeId}
                      </Badge>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {detail.latest_draft ? (
            <Card
              title={locale === "zh-CN" ? "生成草稿" : "Generated Draft"}
              description={locale === "zh-CN" ? "任务生成出的最新草稿与当前状态。" : "The latest draft produced by this task and its current state."}
            >
              <div
                data-testid="task-generated-draft-region"
                data-draft-id={detail.latest_draft.id}
                className="flex flex-wrap items-center justify-between gap-4"
              >
                <div className="space-y-2">
                  <p className="text-sm font-semibold text-slate-900">{detail.latest_draft.title}</p>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge data-testid="task-generated-draft-status" data-status={detail.latest_draft.draft_status} tone={detail.latest_draft.draft_status === "published" || detail.latest_draft.draft_status === "approved" ? "success" : detail.latest_draft.draft_status === "pending_review" ? "warning" : "muted"}>
                      {detail.latest_draft.draft_status}
                    </Badge>
                    <Badge data-testid="task-generated-publish-status" data-status={detail.latest_draft.publish_status} tone={detail.latest_draft.publish_status === "published" ? "success" : detail.latest_draft.publish_status === "failed" ? "danger" : detail.latest_draft.publish_status === "pending" ? "warning" : "muted"}>
                      {detail.latest_draft.publish_status}
                    </Badge>
                  </div>
                </div>
                <Link href={`/drafts/${detail.latest_draft.id}`} data-testid="task-related-draft-link" data-draft-id={detail.latest_draft.id}>
                  <Button variant="secondary">{locale === "zh-CN" ? "打开草稿" : "Open Draft"}</Button>
                </Link>
              </div>
            </Card>
          ) : null}

          {opsContext && runStrategy ? (
            <Card
              title="Ops Strategy"
              description="This task now records the account-level operations judgment that shaped the run before the workflow started."
            >
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-2xl border border-slate-200 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Allow Run</p>
                  <div className="mt-2">
                    <Badge tone={runStrategy.allow_run ? "success" : "danger"}>
                      {runStrategy.allow_run ? "Allowed" : "Blocked"}
                    </Badge>
                  </div>
                </div>
                <div className="rounded-2xl border border-slate-200 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Effective Mode</p>
                  <p className="mt-2 text-sm font-semibold text-slate-900">{runStrategy.effective_mode}</p>
                  {runStrategy.degraded_from ? (
                    <p className="mt-1 text-xs text-amber-700">{`Downgraded from ${runStrategy.degraded_from}`}</p>
                  ) : null}
                </div>
                <div className="rounded-2xl border border-slate-200 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Auto Publish</p>
                  <div className="mt-2">
                    <Badge tone={runStrategy.allow_auto_publish ? "success" : "warning"}>
                      {runStrategy.allow_auto_publish ? "Allowed" : "Review First"}
                    </Badge>
                  </div>
                </div>
                <div className="rounded-2xl border border-slate-200 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Account Health</p>
                  <div className="mt-2">
                    <Badge tone={healthSummary?.status === "ready" ? "success" : healthSummary?.status === "risk_recovery" ? "danger" : "warning"}>
                      {healthSummary?.status ?? "attention"}
                    </Badge>
                  </div>
                </div>
              </div>

              <div className="mt-5 grid gap-5 md:grid-cols-2">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Ops Notes</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {(opsContext.ops_notes ?? []).length ? (
                      opsContext.ops_notes.map((note) => (
                        <Badge key={note} tone="muted">
                          {note}
                        </Badge>
                      ))
                    ) : (
                      <span className="text-sm text-slate-500">No ops notes recorded.</span>
                    )}
                  </div>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-2xl border border-slate-200 p-4 text-sm text-slate-600">
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Avoided Topics</p>
                    <p className="mt-2 font-semibold text-slate-900">{runStrategy.avoid_recent_topics.length}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 p-4 text-sm text-slate-600">
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Preferred Sources</p>
                    <p className="mt-2 font-semibold text-slate-900">{runStrategy.preferred_reference_source_ids.length}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 p-4 text-sm text-slate-600 sm:col-span-2">
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Preferred Content Lane</p>
                    <p className="mt-2 font-semibold text-slate-900">{runStrategy.preferred_content_lane || "Not specified"}</p>
                  </div>
                </div>
              </div>
            </Card>
          ) : null}

          <Card
            title={locale === "zh-CN" ? "有效输入" : "Effective Input"}
            description={
              locale === "zh-CN"
                ? "优先显示这次任务真正吃到的显式创作输入；如果没有，再回退到原始 task input。"
                : "Prefer the explicit creation payload actually consumed by this run, then fall back to the raw task input."
            }
          >
            <pre className="whitespace-pre-wrap text-sm leading-7 text-slate-600">{inputSnapshot}</pre>
          </Card>

          <div className="space-y-6">
            <InsightDisclosureCard
              title="Source Layer"
              description="Inspect the query plan, source scout candidates, and reusable reference digest before the writing stages."
              badge={<Badge tone="info">{insights.sourceCandidates.length}</Badge>}
              defaultOpen
            >
              <div className="grid gap-6 xl:grid-cols-3">
                <div className="rounded-2xl border border-slate-200 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Query Plan</p>
                  {insights.queryPlan ? (
                    <div className="mt-3 space-y-3 text-sm text-slate-600">
                      <div>
                        <p className="font-semibold text-slate-900">
                          {insights.queryPlan.lane?.label || "No lane"}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          {insights.queryPlan.lane?.reason || "No planner rationale recorded."}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Primary Queries</p>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {(insights.queryPlan.primary_queries ?? []).map((query) => (
                            <Badge key={query} tone="muted">
                              {query}
                            </Badge>
                          ))}
                        </div>
                      </div>
                      <div>
                        <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Banned Angles</p>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {(insights.queryPlan.banned_angles ?? []).map((angle) => (
                            <Badge key={angle} tone="warning">
                              {angle}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <p className="mt-3 text-sm text-slate-500">No query plan returned.</p>
                  )}
                </div>

                <div className="rounded-2xl border border-slate-200 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Source Candidates</p>
                  {insights.sourceCandidates.length ? (
                    <div className="mt-3 space-y-3">
                      {insights.sourceCandidates.slice(0, 5).map((source) => (
                        <div key={`${source.source_id ?? source.source_title}`} className="rounded-2xl border border-slate-200/80 p-3">
                          <div className="flex items-center justify-between gap-3">
                            <p className="text-sm font-semibold text-slate-900">{source.source_title}</p>
                            <Badge tone="muted">{source.source_type || "source"}</Badge>
                          </div>
                          <p className="mt-2 text-xs text-slate-500">
                            {source.source_name || "Unnamed source"}
                            {typeof source.fit_score === "number" ? ` · fit ${source.fit_score.toFixed(2)}` : ""}
                          </p>
                          {source.why_selected ? (
                            <p className="mt-2 text-sm leading-6 text-slate-600">{source.why_selected}</p>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-3 text-sm text-slate-500">No source candidates returned.</p>
                  )}
                </div>

                <div className="rounded-2xl border border-slate-200 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Reference Digest</p>
                  {insights.referenceDigest ? (
                    <div className="mt-3 space-y-3 text-sm text-slate-600">
                      <p>{insights.referenceDigest.summary || "No digest summary recorded."}</p>
                      <div>
                        <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Style Takeaways</p>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {(insights.referenceDigest.style_takeaways ?? []).map((item) => (
                            <Badge key={item} tone="brand">
                              {item}
                            </Badge>
                          ))}
                        </div>
                      </div>
                      <div>
                        <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Useful Points</p>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {(insights.referenceDigest.useful_points ?? []).map((item) => (
                            <Badge key={item} tone="muted">
                              {item}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <p className="mt-3 text-sm text-slate-500">No reference digest returned.</p>
                  )}
                </div>
              </div>
            </InsightDisclosureCard>

            <InsightDisclosureCard
              title={locale === "zh-CN" ? "选题与标题产物" : "Topic & Title Artifacts"}
              description={
                locale === "zh-CN"
                  ? "把选题、标题候选和最终成稿放在同一组里，先看阶段产物，再看底层节点轨迹。"
                  : "Review topic selection, title candidates, and the assembled article as first-class artifacts before diving into node trace."
              }
            >
              <div className="grid gap-6 xl:grid-cols-3">
                <div className="rounded-2xl border border-slate-200 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "选题" : "Topic Selection"}</p>
                  {insights.topicSelection ? (
                    <div className="mt-3 space-y-3 text-sm text-slate-600">
                      {(insights.topicSelection as { selected_topic?: string | null }).selected_topic ? (
                        <p className="font-semibold text-slate-900">
                          {(insights.topicSelection as { selected_topic?: string | null }).selected_topic}
                        </p>
                      ) : null}
                      {Array.isArray((insights.topicSelection as { topics?: Array<{ title?: string }> }).topics) ? (
                        <div className="flex flex-wrap gap-2">
                          {((insights.topicSelection as { topics?: Array<{ title?: string }> }).topics ?? []).map((item) =>
                            item?.title ? (
                              <Badge key={item.title} tone="muted">
                                {item.title}
                              </Badge>
                            ) : null,
                          )}
                        </div>
                      ) : (
                        <p>{locale === "zh-CN" ? "没有返回选题候选。" : "No topic candidates returned."}</p>
                      )}
                    </div>
                  ) : (
                    <p className="mt-3 text-sm text-slate-500">{locale === "zh-CN" ? "没有选题产物。" : "No topic artifact available."}</p>
                  )}
                </div>

                <div className="rounded-2xl border border-slate-200 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "标题" : "Title Candidates"}</p>
                  {insights.titleCandidates ? (
                    <div className="mt-3 space-y-3 text-sm text-slate-600">
                      {(insights.titleCandidates as { selected_title?: string | null }).selected_title ? (
                        <p className="font-semibold text-slate-900">
                          {(insights.titleCandidates as { selected_title?: string | null }).selected_title}
                        </p>
                      ) : null}
                      {Array.isArray((insights.titleCandidates as { titles?: Array<{ text?: string }> }).titles) ? (
                        <div className="flex flex-wrap gap-2">
                          {((insights.titleCandidates as { titles?: Array<{ text?: string }> }).titles ?? []).map((item) =>
                            item?.text ? (
                              <Badge key={item.text} tone="brand">
                                {item.text}
                              </Badge>
                            ) : null,
                          )}
                        </div>
                      ) : (
                        <p>{locale === "zh-CN" ? "没有返回标题候选。" : "No title candidates returned."}</p>
                      )}
                    </div>
                  ) : (
                    <p className="mt-3 text-sm text-slate-500">{locale === "zh-CN" ? "没有标题产物。" : "No title artifact available."}</p>
                  )}
                </div>

                <div className="rounded-2xl border border-slate-200 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "成稿" : "Assembled Article"}</p>
                  {insights.assembledArticle ? (
                    <div className="mt-3 space-y-3 text-sm text-slate-600">
                      {(insights.assembledArticle as { content?: { selected_title?: string | null } }).content?.selected_title ? (
                        <p className="font-semibold text-slate-900">
                          {(insights.assembledArticle as { content?: { selected_title?: string | null } }).content?.selected_title}
                        </p>
                      ) : null}
                      {(insights.assembledArticle as { content?: { summary?: string | null } }).content?.summary ? (
                        <p>{(insights.assembledArticle as { content?: { summary?: string | null } }).content?.summary}</p>
                      ) : null}
                      {(insights.assembledArticle as { content?: { content_markdown?: string | null } }).content?.content_markdown ? (
                        <p className="text-xs leading-6 text-slate-500">
                          {truncate(
                            (insights.assembledArticle as { content?: { content_markdown?: string | null } }).content?.content_markdown ?? "",
                            220,
                          )}
                        </p>
                      ) : (
                        <p>{locale === "zh-CN" ? "没有返回成稿正文。" : "No assembled article body returned."}</p>
                      )}
                    </div>
                  ) : (
                    <p className="mt-3 text-sm text-slate-500">{locale === "zh-CN" ? "没有成稿产物。" : "No assembled article artifact available."}</p>
                  )}
                </div>
              </div>
            </InsightDisclosureCard>
            <InsightDisclosureCard
              title={locale === "zh-CN" ? "检索到的历史文章" : "Retrieved Article Memories"}
              description={locale === "zh-CN" ? "查看这次任务引用了哪些历史文章记忆。" : "Inspect which historical article memories were retrieved for this run."}
              badge={<Badge tone="info">{insights.memories.length}</Badge>}
              defaultOpen
            >
              {insights.memories.length ? (
                <MemoryReferenceList memories={insights.memories} locale={locale} />
              ) : (
                <p className="text-sm text-slate-500">{locale === "zh-CN" ? "后端当前没有返回文章记忆，任务详情仍然可以正常查看。" : "No article memories were returned by the backend; the task detail remains usable."}</p>
              )}
            </InsightDisclosureCard>

            <InsightDisclosureCard
              title={locale === "zh-CN" ? "风格画像摘要" : "Style Profile Summary"}
              description={locale === "zh-CN" ? "汇总这次任务使用的风格画像，便于判断生成结果是否贴近账号语气。" : "Summarize the style profile used for this run so the output can be compared against the account voice."}
            >
              {insights.styleProfile ? (
                <StyleProfileSummaryView profile={insights.styleProfile} locale={locale} />
              ) : (
                <p className="text-sm text-slate-500">{locale === "zh-CN" ? "暂无风格画像字段，页面已优雅降级为基础任务调试视图。" : "No style profile field is available yet; the page gracefully falls back to the base task debugger."}</p>
              )}
            </InsightDisclosureCard>

            <InsightDisclosureCard
              title={locale === "zh-CN" ? "提纲计划" : "Outline Plan"}
              description={locale === "zh-CN" ? "查看生成前的内容结构规划。" : "Review the structural plan prepared before long-form drafting."}
            >
              {insights.outline ? (
                <OutlinePlanView outline={insights.outline} locale={locale} />
              ) : (
                <p className="text-sm text-slate-500">{locale === "zh-CN" ? "后端尚未返回提纲计划。" : "The backend has not returned an outline plan."}</p>
              )}
            </InsightDisclosureCard>

            <InsightDisclosureCard
              title={locale === "zh-CN" ? "分段写作结果" : "Section Drafts"}
              description={locale === "zh-CN" ? "定位每个段落草稿的生成结果，便于调试局部写作问题。" : "Inspect each drafted section to debug partial writing issues."}
              badge={<Badge tone="muted">{insights.sections.length}</Badge>}
            >
              {insights.sections.length ? (
                <SectionDraftsView sections={insights.sections} locale={locale} />
              ) : (
                <p className="text-sm text-slate-500">{locale === "zh-CN" ? "没有返回分段写作结果。" : "No section-level draft output was returned."}</p>
              )}
            </InsightDisclosureCard>

            <InsightDisclosureCard
              title={locale === "zh-CN" ? "Reviewer / Rewrite 结果" : "Reviewer / Rewrite Results"}
              description={locale === "zh-CN" ? "合并展示 reviewer 发现的问题和 rewrite 产出。" : "Combine reviewer findings and the downstream rewrite result in one debugging block."}
            >
              <div className="grid gap-6 xl:grid-cols-2">
                <div>
                  <h3 className="mb-3 text-sm font-semibold text-slate-900">{locale === "zh-CN" ? "Reviewer 结果" : "Reviewer Results"}</h3>
                  {insights.reviews.length ? (
                    <ReviewResultsView results={insights.reviews} locale={locale} />
                  ) : (
                    <p className="text-sm text-slate-500">{locale === "zh-CN" ? "暂无 reviewer 结果。" : "No reviewer results returned."}</p>
                  )}
                </div>
                <div>
                  <h3 className="mb-3 text-sm font-semibold text-slate-900">{locale === "zh-CN" ? "Rewrite 结果" : "Rewrite Result"}</h3>
                  {insights.rewrite ? (
                    <RewriteResultView rewrite={insights.rewrite} locale={locale} />
                  ) : (
                    <p className="text-sm text-slate-500">{locale === "zh-CN" ? "暂无 rewrite 结果。" : "No rewrite result returned."}</p>
                  )}
                </div>
              </div>
            </InsightDisclosureCard>

            <InsightDisclosureCard
              title={locale === "zh-CN" ? "评测指标" : "Evaluation Metrics"}
              description={locale === "zh-CN" ? "在任务调试时同时看到文章得分和简短解释。" : "See article scores and short explanations directly inside the task debugger."}
            >
              {insights.evaluation ? (
                <EvaluationScoreCard evaluation={insights.evaluation} locale={locale} />
              ) : (
                <p className="text-sm text-slate-500">{locale === "zh-CN" ? "后端当前还没有返回评测指标。" : "The backend is not returning evaluation metrics yet."}</p>
              )}
            </InsightDisclosureCard>
          </div>

          <Card
            title={locale === "zh-CN" ? "节点轨迹" : "Node Trace"}
            description={locale === "zh-CN" ? "保留结构化内容链的节点调试表，方便排查提纲、分段、组装与回退行为。" : "Keep the structured content pipeline trace visible, including outline, sections, assembly and fallback behavior."}
          >
            {nodes.length ? (
              <Table columns={[locale === "zh-CN" ? "节点" : "Node", locale === "zh-CN" ? "状态" : "Status", locale === "zh-CN" ? "耗时" : "Duration", locale === "zh-CN" ? "模型" : "Model", locale === "zh-CN" ? "降级" : "Degraded", locale === "zh-CN" ? "错误" : "Error"]}>
                {nodes.map((node) => (
                  <tr key={`${node.node_id}-${node.started_at ?? "row"}`} className="align-top">
                    <td className="px-5 py-4">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{node.name || node.node_id}</p>
                        <p className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-400">{node.agent_id}</p>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <Badge tone={taskTone(node.status)}>{taskStatusLabel(node.status)}</Badge>
                    </td>
                    <td className="px-5 py-4 text-sm text-slate-600">{formatDuration(node.elapsed_seconds)}</td>
                    <td className="px-5 py-4 text-sm text-slate-600">{node.model_used || (locale === "zh-CN" ? "未记录" : "Not recorded")}</td>
                    <td className="px-5 py-4 text-sm text-slate-600">{node.degraded ? (locale === "zh-CN" ? "是" : "Yes") : locale === "zh-CN" ? "否" : "No"}</td>
                    <td className="px-5 py-4 text-sm text-slate-500">
                      <p>{truncate(node.error_message, 90) || (locale === "zh-CN" ? "无错误" : "No error")}</p>
                      {node.runtime ? (
                        <p className="mt-1 text-xs text-slate-400">
                          {`runtime: ${String(node.runtime.error_class || "ok")} | retries: ${node.retry_count ?? 0}`}
                        </p>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </Table>
            ) : (
              locale === "zh-CN" ? "暂无节点轨迹" : "No node trace available"
            )}
          </Card>
        </>
      ) : null}
    </div>
  );
}
