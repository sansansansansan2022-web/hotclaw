"use client";

import { useEffect, useMemo, useState } from "react";
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
import { useI18n } from "@/lib/i18n";
import { formatDateTime } from "@/lib/utils";
import type { DraftDetail, PublishRecord } from "@/types";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, SkeletonRows, Table } from "@/components/console/ui";
import { useAppStore } from "@/store/appStore";

function tone(status: string): "brand" | "success" | "warning" | "danger" | "muted" {
  if (status === "approved" || status === "published") return "success";
  if (status === "pending_review") return "warning";
  if (status === "rejected" || status === "discarded" || status === "failed") return "danger";
  if (status === "pending" || status === "publishing") return "warning";
  return "muted";
}

export function DraftDetailPage({ draftId }: { draftId: string }) {
  const { locale, draftStatusLabel, publishStatusLabel } = useI18n();
  const parsedId = Number(draftId);
  const pushToast = useAppStore((state) => state.pushToast);
  const [detail, setDetail] = useState<DraftDetail | null>(null);
  const [records, setRecords] = useState<PublishRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
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
      setDetail(detailRes);
      setRecords(recordRes.records);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : locale === "zh-CN" ? "无法加载草稿详情" : "Unable to load draft detail");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [draftId, locale]);

  const actions = useMemo(() => {
    if (!detail) return { canApprove: false, canReject: false, canDiscard: false, canPublish: false, canRetry: false };
    return {
      canApprove: detail.draft_status === "pending_review",
      canReject: detail.draft_status === "pending_review",
      canDiscard: detail.draft_status === "pending_review",
      canPublish: detail.draft_status === "approved" && detail.publish_status !== "published",
      canRetry: detail.publish_status === "failed",
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
        message: actionError instanceof Error ? actionError.message : locale === "zh-CN" ? "发生了意外错误" : "Unexpected error",
      });
    }
  };

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={locale === "zh-CN" ? "审核详情" : "Review Detail"}
        title={detail?.title || (missingDraft ? (locale === "zh-CN" ? "草稿详情" : "Draft Detail") : `${locale === "zh-CN" ? "草稿" : "Draft"} ${draftId}`)}
        description={
          detail
            ? locale === "zh-CN"
              ? "基于后端草稿工作流展示文章预览、审核结果和可执行动作。"
              : "Article preview, audit result and state-accurate actions derived from the backend draft workflow."
            : locale === "zh-CN"
              ? "用于查看单条草稿的审核备注、发布尝试和允许的后续动作。"
              : "Review surface for a single draft record, including audit notes, publish attempts and allowed next actions."
        }
        actions={
          detail ? (
          <>
            <Button variant="secondary" disabled={!actions.canApprove} onClick={() => void runAction(() => confirmPublishDraft(parsedId), locale === "zh-CN" ? "草稿已通过" : "Draft approved", locale === "zh-CN" ? "该草稿已确认可发布。" : "The draft was confirmed for publishing.")}>
              {locale === "zh-CN" ? "通过" : "Approve"}
            </Button>
            <Button variant="secondary" disabled={!actions.canReject} onClick={() => void runAction(() => rejectDraft(parsedId), locale === "zh-CN" ? "草稿已拒绝" : "Draft rejected", locale === "zh-CN" ? "该草稿已被标记为拒绝。" : "The draft has been marked as rejected.")}>
              {locale === "zh-CN" ? "拒绝" : "Reject"}
            </Button>
            <Button variant="destructive" disabled={!actions.canDiscard} onClick={() => void runAction(() => discardDraft(parsedId), locale === "zh-CN" ? "草稿已丢弃" : "Draft discarded", locale === "zh-CN" ? "该草稿已被丢弃。" : "The draft has been discarded.")}>
              {locale === "zh-CN" ? "丢弃" : "Discard"}
            </Button>
            <Button variant="secondary" disabled={!actions.canPublish} onClick={() => void runAction(() => publishDraftToWeChat(parsedId), locale === "zh-CN" ? "发布已开始" : "Publish started", locale === "zh-CN" ? "草稿已送入微信发布流水线。" : "The draft was sent to the WeChat publish pipeline.")}>
              {locale === "zh-CN" ? "发布" : "Publish"}
            </Button>
            <Button variant="secondary" disabled={!actions.canRetry} onClick={() => void runAction(() => retryPublishDraft(parsedId), locale === "zh-CN" ? "重试已开始" : "Retry started", locale === "zh-CN" ? "已创建新的发布重试记录。" : "A retry publish attempt was created.")}>
              {locale === "zh-CN" ? "重试" : "Retry"}
            </Button>
            <Button variant="ghost" onClick={() => void runAction(() => rerunFromDraft(parsedId), locale === "zh-CN" ? "重跑已入队" : "Rerun queued", locale === "zh-CN" ? "已基于这条草稿创建新任务。" : "A new task was created from this draft.")}>
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
            <Card title={locale === "zh-CN" ? "草稿记录不可用" : "Draft Record Unavailable"} description={locale === "zh-CN" ? "请求的路由能解析，但当前后端数据集中没有对应草稿。" : "The requested id resolves as a route, but no matching draft exists in the backend dataset right now."}>
              <EmptyState
                title={locale === "zh-CN" ? "后端没有找到草稿" : "No backend draft found"}
                description={locale === "zh-CN" ? "当前工作区还没有这个 ID 对应的草稿记录。等任务生成草稿后，这里会自动切换到真实审核与发布布局。" : "This workspace currently has no draft record for the requested id. Once tasks generate drafts, this page will switch to the live review and publish layout automatically."}
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

            <Card title={locale === "zh-CN" ? "下一步建议" : "Next Steps"} description={locale === "zh-CN" ? "在草稿收件箱为空时可优先执行的恢复路径。" : "Useful recovery paths while the draft inbox is still empty."}>
              <div className="grid gap-3">
                <Link href="/workspace" className="rounded-2xl border border-slate-200 p-4 transition hover:border-brand-200 hover:bg-brand-50/60">
                  <p className="text-sm font-semibold text-slate-900">{locale === "zh-CN" ? "运行手动工作流" : "Run a manual workflow"}</p>
                  <p className="mt-1 text-sm text-slate-500">{locale === "zh-CN" ? "从工作台生成新任务，以创建草稿记录。" : "Generate a new task from the workspace to create draft records."}</p>
                </Link>
                <Link href="/accounts" className="rounded-2xl border border-slate-200 p-4 transition hover:border-brand-200 hover:bg-brand-50/60">
                  <p className="text-sm font-semibold text-slate-900">{locale === "zh-CN" ? "检查账号自动化" : "Check account automation"}</p>
                  <p className="mt-1 text-sm text-slate-500">{locale === "zh-CN" ? "查看托管账号、调度设置和草稿审核入口。" : "Review managed accounts, schedules and draft-review entry points."}</p>
                </Link>
                <Link href="/tasks/history" className="rounded-2xl border border-slate-200 p-4 transition hover:border-brand-200 hover:bg-brand-50/60">
                  <p className="text-sm font-semibold text-slate-900">{locale === "zh-CN" ? "查看最近任务" : "Inspect recent tasks"}</p>
                  <p className="mt-1 text-sm text-slate-500">{locale === "zh-CN" ? "确认已完成任务是否产出了内容但尚未落成草稿。" : "Confirm whether completed tasks produced content but not draft artifacts."}</p>
                </Link>
              </div>
            </Card>
          </div>
        ) : (
          <ErrorState title={locale === "zh-CN" ? "草稿详情不可用" : "Draft detail unavailable"} description={error} retry={() => void load()} />
        )
      ) : detail ? (
        <>
          <div className="grid gap-6 xl:grid-cols-[1.2fr_0.9fr]">
            <Card title={locale === "zh-CN" ? "文章预览" : "Article Preview"} description={locale === "zh-CN" ? "来自后端草稿记录的当前内容快照。" : "Current draft snapshot from the backend draft record."}>
              <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={tone(detail.draft_status)}>{draftStatusLabel(detail.draft_status)}</Badge>
                  <Badge tone={tone(detail.publish_status)}>{publishStatusLabel(detail.publish_status)}</Badge>
                  <Badge tone={detail.audit_result?.passed ? "success" : "warning"}>{detail.audit_result?.passed ? (locale === "zh-CN" ? "审核通过" : "Audit Passed") : locale === "zh-CN" ? "待审核" : "Audit Review"}</Badge>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "摘要" : "Summary"}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{detail.summary || (locale === "zh-CN" ? "还没有生成摘要。" : "No summary generated.")}</p>
                </div>
                <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
                  {detail.content_html ? (
                    <div className="prose prose-slate max-w-none text-sm" dangerouslySetInnerHTML={{ __html: detail.content_html }} />
                  ) : (
                    <pre className="whitespace-pre-wrap text-sm leading-7 text-slate-600">{detail.content_markdown}</pre>
                  )}
                </div>
              </div>
            </Card>

            <div className="space-y-6">
              <Card title={locale === "zh-CN" ? "审核快照" : "Review Snapshot"} description={locale === "zh-CN" ? "元数据、审核结果和最近发布错误上下文。" : "Metadata, audit result and latest publish error context."}>
                <div className="grid gap-4 text-sm text-slate-600">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "账号" : "Account"}</p>
                    <p className="mt-2">{detail.account_name || detail.account_id || (locale === "zh-CN" ? "未分配" : "Unassigned")}</p>
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
                    <p className="mt-2">{detail.audit_result?.overall_comment || (locale === "zh-CN" ? "还没有审核备注。" : "No audit comment recorded.")}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "发布错误" : "Publish Error"}</p>
                    <p className="mt-2">{detail.publish_error_message || (locale === "zh-CN" ? "还没有发布错误。" : "No publish error recorded.")}</p>
                  </div>
                </div>
              </Card>

              <Card title={locale === "zh-CN" ? "版本与发布记录" : "Version & Publish Records"} description={locale === "zh-CN" ? "当前后端暴露的草稿级发布尝试记录。" : "Per-draft publish attempts currently exposed by the backend."}>
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
                  <EmptyState title={locale === "zh-CN" ? "暂无发布尝试" : "No publish attempts yet"} description={locale === "zh-CN" ? "只有草稿进入微信发布流程后才会生成发布记录。" : "Publish records are created only after a draft enters the WeChat publishing flow."} />
                )}
              </Card>
            </div>
          </div>
        </>
      ) : (
        <EmptyState
          title={locale === "zh-CN" ? "未找到草稿" : "Draft not found"}
          description={locale === "zh-CN" ? "当前环境里没有对应草稿记录。后端产出草稿后，这里会自动渲染真实详情页。" : "This environment currently has no matching draft record. Once the backend creates drafts, this page will render the live draft detail experience."}
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
