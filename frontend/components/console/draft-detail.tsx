"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  confirmPublishDraft,
  discardDraft,
  getDraft,
  getDraftPublishRecords,
  publishDraftToWeChat,
  rejectDraft,
  rerunFromDraft,
  retryPublishDraft,
} from "@/lib/api";
import {
  normalizeContentMemories,
  normalizeEvaluation,
  normalizeOutlinePlan,
  normalizeReviewResults,
  normalizeRewriteResult,
  normalizeSectionDrafts,
  normalizeStyleProfile,
} from "@/lib/content-insights";
import { useI18n } from "@/lib/i18n";
import { formatDateTime } from "@/lib/utils";
import type { DraftDetail, PublishRecord, SectionDraft } from "@/types";
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
import { Badge, Button, Card, EmptyState, ErrorState, Input, PageHeader, SkeletonRows, Table, Tabs, Textarea } from "@/components/console/ui";
import { useAppStore } from "@/store/appStore";

type PreviewMode = "markdown" | "html" | "sections";

function tone(status: string): "brand" | "success" | "warning" | "danger" | "muted" {
  if (status === "approved" || status === "published") return "success";
  if (status === "pending_review") return "warning";
  if (status === "rejected" || status === "discarded" || status === "failed") return "danger";
  if (status === "pending" || status === "publishing") return "warning";
  return "muted";
}

function fallbackSections(detail: DraftDetail | null): SectionDraft[] {
  const outline = normalizeOutlinePlan(detail?.outline_plan);
  return (outline?.sections ?? []).map((section, index) => ({
    id: section.id ?? index,
    heading: section.title,
    summary: section.summary,
  }));
}

export function DraftDetailPage({ draftId }: { draftId: string }) {
  const { locale, draftStatusLabel, publishStatusLabel } = useI18n();
  const parsedId = Number(draftId);
  const pushToast = useAppStore((state) => state.pushToast);
  const [detail, setDetail] = useState<DraftDetail | null>(null);
  const [records, setRecords] = useState<PublishRecord[]>([]);
  const [previewMode, setPreviewMode] = useState<PreviewMode>("html");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const loadRequestRef = useRef(0);

  const load = async () => {
    const requestId = ++loadRequestRef.current;
    if (!Number.isFinite(parsedId)) {
      setLoading(false);
      setError(locale === "zh-CN" ? "草稿 ID 必须是数字。" : "Draft id must be numeric.");
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setDetail(null);
      setRecords([]);
      const [detailRes, recordRes] = await Promise.all([
        getDraft(parsedId),
        getDraftPublishRecords(parsedId).catch(() => ({ draft_id: parsedId, total: 0, records: [] })),
      ]);
      if (requestId !== loadRequestRef.current) return;
      setDetail(detailRes);
      setRecords(recordRes.records);
    } catch (loadError) {
      if (requestId !== loadRequestRef.current) return;
      setError(loadError instanceof Error ? loadError.message : locale === "zh-CN" ? "无法加载草稿详情。" : "Unable to load draft detail.");
    } finally {
      if (requestId === loadRequestRef.current) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    void load();
  }, [draftId]);

  const detailMatchesRoute = Boolean(detail && detail.id === parsedId);

  const actions = useMemo(() => {
    if (!detail || !detailMatchesRoute || loading) return { canApprove: false, canReject: false, canDiscard: false, canPublish: false, canRetry: false };
    return {
      canApprove: detail.draft_status === "pending_review",
      canReject: detail.draft_status === "pending_review",
      canDiscard: detail.draft_status === "pending_review",
      canPublish: detail.draft_status === "approved" && !["published", "pending", "publishing"].includes(detail.publish_status),
      canRetry: detail.publish_status === "failed",
    };
  }, [detail, detailMatchesRoute, loading]);

  const insights = useMemo(() => {
    const sections = normalizeSectionDrafts(detail?.section_drafts);
    return {
      memories: normalizeContentMemories(detail?.retrieved_memories),
      styleProfile: normalizeStyleProfile(detail?.style_profile),
      outline: normalizeOutlinePlan(detail?.outline_plan),
      sections: sections.length ? sections : fallbackSections(detail),
      reviews: normalizeReviewResults(
        {
          review_results: detail?.review_results,
          style_review: detail?.style_review,
          structure_review: detail?.structure_review,
        },
        detail?.audit_result ?? null,
      ),
      rewrite: normalizeRewriteResult(detail?.rewrite_result),
      evaluation: normalizeEvaluation(detail?.evaluation),
    };
  }, [detail]);

  const missingDraft = Boolean(error && /(not found|unavailable)/i.test(error));

  const runAction = async (callback: () => Promise<unknown>, successTitle: string, successMessage: string) => {
    try {
      await callback();
      pushToast({ tone: "success", title: successTitle, message: successMessage });
      await load();
    } catch (actionError) {
      pushToast({
        tone: "danger",
        title: locale === "zh-CN" ? "草稿操作失败" : "Draft action failed",
        message: actionError instanceof Error ? actionError.message : locale === "zh-CN" ? "发生了意外错误。" : "Unexpected error.",
      });
    }
  };

  const renderPreview = () => {
    if (!detail) return null;

    if (previewMode === "markdown") {
      return <pre className="whitespace-pre-wrap text-sm leading-7 text-slate-600">{detail.content_markdown || (locale === "zh-CN" ? "暂无 Markdown 内容。" : "No markdown content.")}</pre>;
    }

    if (previewMode === "sections") {
      return insights.sections.length ? (
        <SectionDraftsView sections={insights.sections} locale={locale} />
      ) : (
        <EmptyState
          title={locale === "zh-CN" ? "暂无分段结构" : "No section structure yet"}
          description={locale === "zh-CN" ? "后端还没有返回 outline_plan 或 section_drafts。" : "The backend has not returned outline_plan or section_drafts yet."}
        />
      );
    }

    return detail.content_html ? (
      <div className="prose prose-slate max-w-none text-sm" dangerouslySetInnerHTML={{ __html: detail.content_html }} />
    ) : (
      <EmptyState
        title={locale === "zh-CN" ? "暂无 HTML 预览" : "No rendered HTML yet"}
        description={locale === "zh-CN" ? "后端没有返回 content_html，已经自动降级到 Markdown 查看模式。" : "The backend did not return content_html, so the page falls back to markdown when needed."}
      />
    );
  };

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={locale === "zh-CN" ? "审核详情" : "Review Detail"}
        title={detail?.title || (missingDraft ? (locale === "zh-CN" ? "草稿详情" : "Draft Detail") : `${locale === "zh-CN" ? "草稿" : "Draft"} ${draftId}`)}
        description={
          detail
            ? locale === "zh-CN"
              ? "在现有审核与发布流上，补充内容结构、reviewer 结果、rewrite 摘要和评分，让草稿详情更接近内容工作台。"
              : "Builds on the existing review and publish flow with content structure, reviewer output, rewrite summary and scoring."
            : locale === "zh-CN"
              ? "查看单条草稿的审核结果、发布记录和可执行动作。"
              : "Inspect a single draft record, its review outcome, publish history and allowed actions."
        }
        actions={
          detail ? (
            <>
              {detail.account_id ? (
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
                disabled={!actions.canApprove}
                onClick={() =>
                  void runAction(
                    () => confirmPublishDraft(detail.id),
                    locale === "zh-CN" ? "草稿已通过" : "Draft approved",
                    locale === "zh-CN" ? "该草稿已确认可发布。" : "The draft was confirmed for publishing.",
                  )
                }
              >
                {locale === "zh-CN" ? "通过" : "Approve"}
              </Button>
              <Button
                variant="secondary"
                disabled={!actions.canReject}
                onClick={() =>
                  void runAction(
                    () => rejectDraft(detail.id),
                    locale === "zh-CN" ? "草稿已拒绝" : "Draft rejected",
                    locale === "zh-CN" ? "该草稿已被标记为拒绝。" : "The draft has been marked as rejected.",
                  )
                }
              >
                {locale === "zh-CN" ? "拒绝" : "Reject"}
              </Button>
              <Button
                variant="destructive"
                disabled={!actions.canDiscard}
                onClick={() =>
                  void runAction(
                    () => discardDraft(detail.id),
                    locale === "zh-CN" ? "草稿已丢弃" : "Draft discarded",
                    locale === "zh-CN" ? "该草稿已被丢弃。" : "The draft has been discarded.",
                  )
                }
              >
                {locale === "zh-CN" ? "丢弃" : "Discard"}
              </Button>
              <Button
                variant="secondary"
                disabled={!actions.canPublish}
                onClick={() =>
                  void runAction(
                    () => publishDraftToWeChat(detail.id),
                    locale === "zh-CN" ? "发布已开始" : "Publish started",
                    locale === "zh-CN" ? "草稿已进入微信发布流水线。" : "The draft was sent to the WeChat publish pipeline.",
                  )
                }
              >
                {locale === "zh-CN" ? "发布" : "Publish"}
              </Button>
              <Button
                variant="secondary"
                disabled={!actions.canRetry}
                onClick={() =>
                  void runAction(
                    () => retryPublishDraft(detail.id),
                    locale === "zh-CN" ? "重试已开始" : "Retry started",
                    locale === "zh-CN" ? "已经创建新的发布重试记录。" : "A retry publish attempt was created.",
                  )
                }
              >
                {locale === "zh-CN" ? "重试" : "Retry"}
              </Button>
              <Button
                variant="ghost"
                onClick={() =>
                  void runAction(
                    () => rerunFromDraft(detail.id),
                    locale === "zh-CN" ? "重跑已加入队列" : "Rerun queued",
                    locale === "zh-CN" ? "已基于这条草稿创建新的任务。" : "A new task was created from this draft.",
                  )
                }
              >
                {locale === "zh-CN" ? "重跑任务" : "Rerun Task"}
              </Button>
            </>
          ) : undefined
        }
      />

      {loading ? (
        <SkeletonRows rows={5} />
      ) : error ? (
        missingDraft ? (
          <div className="grid gap-6 xl:grid-cols-[1.2fr_0.9fr]">
            <Card
              title={locale === "zh-CN" ? "草稿记录不可用" : "Draft Record Unavailable"}
              description={
                locale === "zh-CN"
                  ? "请求的草稿 ID 可以解析，但当前后端数据集里没有对应记录。"
                  : "The requested draft id resolves correctly, but there is no matching record in the current backend dataset."
              }
            >
              <EmptyState
                title={locale === "zh-CN" ? "没有找到草稿" : "No draft found"}
                description={
                  locale === "zh-CN"
                    ? "等任务真正产出草稿后，这里会自动切换到完整的审核与发布工作台。"
                    : "Once the backend starts producing drafts, this page will automatically switch to the full review and publishing workbench."
                }
                action={
                  <div className="flex flex-wrap items-center justify-center gap-3">
                    <Link href="/drafts">
                      <Button>{locale === "zh-CN" ? "返回草稿中心" : "Back to Drafts"}</Button>
                    </Link>
                    <Link href="/workspace">
                      <Button variant="secondary">{locale === "zh-CN" ? "打开工作台" : "Open Workspace"}</Button>
                    </Link>
                  </div>
                }
              />
            </Card>
            <Card
              title={locale === "zh-CN" ? "下一步建议" : "Next Steps"}
              description={locale === "zh-CN" ? "在草稿箱还为空时，优先检查这些入口。" : "Suggested paths to inspect while the draft inbox is still empty."}
            >
              <div className="grid gap-3">
                <Link href="/workspace" className="rounded-2xl border border-slate-200 p-4 transition hover:border-brand-200 hover:bg-brand-50/60">
                  <p className="text-sm font-semibold text-slate-900">{locale === "zh-CN" ? "运行手动工作流" : "Run a manual workflow"}</p>
                  <p className="mt-1 text-sm text-slate-500">{locale === "zh-CN" ? "从工作台生成新任务，推动草稿产生。" : "Generate a new task from the workspace to produce drafts."}</p>
                </Link>
                <Link href="/accounts" className="rounded-2xl border border-slate-200 p-4 transition hover:border-brand-200 hover:bg-brand-50/60">
                  <p className="text-sm font-semibold text-slate-900">{locale === "zh-CN" ? "检查账号自动化" : "Check account automation"}</p>
                  <p className="mt-1 text-sm text-slate-500">{locale === "zh-CN" ? "查看托管账号、调度配置和审核入口。" : "Review managed accounts, schedules and review entry points."}</p>
                </Link>
              </div>
            </Card>
          </div>
        ) : (
          <ErrorState title={locale === "zh-CN" ? "草稿详情不可用" : "Draft detail unavailable"} description={error} retry={() => void load()} />
        )
      ) : detail ? (
        <div className="grid gap-6 xl:grid-cols-[1.2fr_0.9fr]">
          <div className="space-y-6">
            <Card
              title={locale === "zh-CN" ? "文章预览" : "Article Preview"}
              description={locale === "zh-CN" ? "在 Markdown、渲染 HTML 和 section 结构之间切换查看。" : "Switch between markdown, rendered HTML and section structure."}
              action={
                <Tabs<PreviewMode>
                  value={previewMode}
                  onChange={setPreviewMode}
                  items={[
                    { value: "html", label: locale === "zh-CN" ? "渲染 HTML" : "Rendered HTML" },
                    { value: "markdown", label: "Markdown" },
                    { value: "sections", label: locale === "zh-CN" ? "Sections" : "Sections" },
                  ]}
                />
              }
            >
              <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={tone(detail.draft_status)}>{draftStatusLabel(detail.draft_status)}</Badge>
                  <Badge tone={tone(detail.publish_status)}>{publishStatusLabel(detail.publish_status)}</Badge>
                  {insights.rewrite ? (
                    <Badge tone={insights.rewrite.used_rewrite ? "success" : "muted"}>
                      {insights.rewrite.used_rewrite
                        ? locale === "zh-CN"
                          ? "使用修订稿"
                          : "Using revised draft"
                        : locale === "zh-CN"
                          ? "保留原组装稿"
                          : "Using assembled draft"}
                    </Badge>
                  ) : null}
                  <Badge tone={detail.audit_result?.passed ? "success" : "warning"}>
                    {detail.audit_result?.passed ? (locale === "zh-CN" ? "审核通过" : "Audit Passed") : locale === "zh-CN" ? "待审核" : "Audit Review"}
                  </Badge>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "摘要" : "Summary"}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{detail.summary || (locale === "zh-CN" ? "还没有摘要。" : "No summary available.")}</p>
                </div>
                <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5">{renderPreview()}</div>
              </div>
            </Card>

            <Card
              title={locale === "zh-CN" ? "编辑工作台入口" : "Editing Hooks"}
              description={locale === "zh-CN" ? "第一版先提供结构化入口，为后续标题编辑、摘要编辑和局部重写预留位置。"
                : "This first pass reserves structured hooks for title editing, summary editing and section-level rewrite."}
            >
              <div className="space-y-5">
                <div>
                  <p className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "编辑标题" : "Edit Title"}</p>
                  <Input value={detail.title} readOnly />
                </div>
                <div>
                  <p className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "编辑摘要" : "Edit Summary"}</p>
                  <Textarea value={detail.summary ?? ""} readOnly className="min-h-24" />
                </div>
                <div className="flex flex-wrap gap-3">
                  <Button variant="secondary" disabled>
                    {locale === "zh-CN" ? "编辑标题（即将支持）" : "Edit Title (Soon)"}
                  </Button>
                  <Button variant="secondary" disabled>
                    {locale === "zh-CN" ? "编辑摘要（即将支持）" : "Edit Summary (Soon)"}
                  </Button>
                  <Button variant="secondary" disabled>
                    {locale === "zh-CN" ? "局部重写（占位）" : "Section Rewrite (Placeholder)"}
                  </Button>
                </div>
              </div>
            </Card>
          </div>

          <div className="space-y-6">
            <Card
              title={locale === "zh-CN" ? "审核快照" : "Review Snapshot"}
              description={locale === "zh-CN" ? "元数据、审核结果和最近发布错误上下文。" : "Metadata, audit result and latest publish error context."}
            >
              <div className="grid gap-4 text-sm text-slate-600">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "账号" : "Account"}</p>
                  {detail.account_id ? (
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <Link href={`/accounts/${detail.account_id}`} className="text-sm font-semibold text-brand-700 hover:text-brand-800">
                        {detail.account_name || detail.account_id}
                      </Link>
                      <Badge tone="brand">{detail.account_id}</Badge>
                    </div>
                  ) : (
                    <p className="mt-2">{locale === "zh-CN" ? "未分配" : "Unassigned"}</p>
                  )}
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "选题" : "Selected Topic"}</p>
                  <p className="mt-2">{detail.selected_topic || (locale === "zh-CN" ? "没有选题" : "No topic selected")}</p>
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "创建时间" : "Created"}</p>
                    <p className="mt-2">{formatDateTime(detail.created_at)}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "更新时间" : "Updated"}</p>
                    <p className="mt-2">{formatDateTime(detail.updated_at)}</p>
                  </div>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "审核备注" : "Audit Comment"}</p>
                  <p className="mt-2">{detail.audit_result?.overall_comment || (locale === "zh-CN" ? "暂无审核备注。" : "No audit comment recorded.")}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "发布错误" : "Publish Error"}</p>
                  <p className="mt-2">{detail.publish_error_message || (locale === "zh-CN" ? "暂无发布错误。" : "No publish error recorded.")}</p>
                </div>
              </div>
            </Card>

            <InsightDisclosureCard
              title={locale === "zh-CN" ? "风格画像摘要" : "Style Profile Summary"}
              description={locale === "zh-CN" ? "用于判断当前草稿是否贴近账号的既有风格资产。"
                : "Helps assess whether the current draft aligns with the account's established style asset."}
              defaultOpen
            >
              {insights.styleProfile ? (
                <StyleProfileSummaryView profile={insights.styleProfile} locale={locale} />
              ) : (
                <p className="text-sm text-slate-500">{locale === "zh-CN" ? "后端还没有返回 style_profile 字段。" : "The backend has not returned a style_profile field yet."}</p>
              )}
            </InsightDisclosureCard>

            <InsightDisclosureCard
              title={locale === "zh-CN" ? "本文引用的历史文章" : "Referenced Article Memories"}
              description={locale === "zh-CN" ? "展示本次草稿基于哪些历史文章进行风格和内容检索。" : "Shows which historical article memories informed this draft."}
              badge={<Badge tone="info">{insights.memories.length}</Badge>}
            >
              {insights.memories.length ? (
                <MemoryReferenceList memories={insights.memories} locale={locale} />
              ) : (
                <p className="text-sm text-slate-500">{locale === "zh-CN" ? "没有关联的历史文章记忆。" : "No historical article memories were linked to this draft."}</p>
              )}
            </InsightDisclosureCard>

            <InsightDisclosureCard
              title={locale === "zh-CN" ? "提纲与段落结构" : "Outline & Section Structure"}
              description={locale === "zh-CN" ? "结合 outline_plan 与 section_drafts，快速审查文章组织方式。" : "Combines outline_plan and section_drafts to inspect article structure."}
            >
              <div className="space-y-5">
                {insights.outline ? <OutlinePlanView outline={insights.outline} locale={locale} /> : null}
                {insights.sections.length ? <SectionDraftsView sections={insights.sections} locale={locale} /> : null}
                {!insights.outline && !insights.sections.length ? (
                  <p className="text-sm text-slate-500">{locale === "zh-CN" ? "暂时没有提纲和段落结构数据。" : "No outline or section structure data is available yet."}</p>
                ) : null}
              </div>
            </InsightDisclosureCard>

            <InsightDisclosureCard
              title={locale === "zh-CN" ? "Reviewer 问题列表" : "Reviewer Issues"}
              description={locale === "zh-CN" ? "把 reviewer 和 audit 中暴露的问题集中起来，方便人工处理。" : "Brings reviewer and audit issues together for fast operator review."}
            >
              {insights.reviews.length ? (
                <ReviewResultsView results={insights.reviews} locale={locale} />
              ) : (
                <p className="text-sm text-slate-500">{locale === "zh-CN" ? "当前没有 reviewer 问题列表。" : "There is no reviewer issue list for this draft yet."}</p>
              )}
            </InsightDisclosureCard>

            <InsightDisclosureCard
              title={locale === "zh-CN" ? "Rewrite 摘要" : "Rewrite Summary"}
              description={locale === "zh-CN" ? "快速查看 rewrite 阶段的修改结论与影响段落。" : "Quickly inspect the rewrite stage summary and impacted sections."}
            >
              {insights.rewrite ? (
                <RewriteResultView rewrite={insights.rewrite} locale={locale} />
              ) : (
                <p className="text-sm text-slate-500">{locale === "zh-CN" ? "没有 rewrite 摘要。" : "No rewrite summary is available."}</p>
              )}
            </InsightDisclosureCard>

            <InsightDisclosureCard
              title={locale === "zh-CN" ? "Evaluation Score" : "Evaluation Score"}
              description={locale === "zh-CN" ? "通过统一 score card 展示文章为什么好或不好。" : "Uses a unified score card to show why the article performs well or poorly."}
            >
              {insights.evaluation ? (
                <EvaluationScoreCard evaluation={insights.evaluation} locale={locale} />
              ) : (
                <p className="text-sm text-slate-500">{locale === "zh-CN" ? "评测指标暂时不可用。" : "Evaluation metrics are not available yet."}</p>
              )}
            </InsightDisclosureCard>

            <Card
              title={locale === "zh-CN" ? "版本与发布记录" : "Version & Publish Records"}
              description={locale === "zh-CN" ? "保留现有发布记录表格，不影响现有发布追踪。"
                : "Preserves the existing publish-record table so the current publishing trace remains intact."}
            >
              {records.length ? (
                <Table columns={[locale === "zh-CN" ? "记录" : "Record", locale === "zh-CN" ? "状态" : "Status", locale === "zh-CN" ? "尝试次数" : "Attempt", locale === "zh-CN" ? "创建时间" : "Created"]}>
                  {records.map((record) => (
                    <tr key={record.id}>
                      <td className="px-5 py-4 text-sm font-semibold text-slate-900">#{record.id}</td>
                      <td className="px-5 py-4">
                        <Badge tone={tone(record.publish_status)}>{publishStatusLabel(record.publish_status)}</Badge>
                      </td>
                      <td className="px-5 py-4 text-sm text-slate-600">{locale === "zh-CN" ? `第 ${record.publish_attempt} 次尝试` : `Attempt ${record.publish_attempt}`}</td>
                      <td className="px-5 py-4 text-sm text-slate-600">{formatDateTime(record.created_at)}</td>
                    </tr>
                  ))}
                </Table>
              ) : (
                <EmptyState
                  title={locale === "zh-CN" ? "暂无发布尝试" : "No publish attempts yet"}
                  description={locale === "zh-CN" ? "只有草稿进入微信发布流程后，才会生成发布记录。" : "Publish records are created only after a draft enters the WeChat publishing flow."}
                />
              )}
            </Card>
          </div>
        </div>
      ) : (
        <EmptyState
          title={locale === "zh-CN" ? "未找到草稿" : "Draft not found"}
          description={locale === "zh-CN" ? "当前环境里没有对应草稿记录。任务产出草稿后，这里会自动显示真实详情。" : "There is no matching draft record in the current environment. Once tasks produce drafts, this page will show the live detail view."}
          action={
            <Link href="/drafts">
              <Button>{locale === "zh-CN" ? "返回草稿中心" : "Back to Drafts"}</Button>
            </Link>
          }
        />
      )}
    </div>
  );
}
