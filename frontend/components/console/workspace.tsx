"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createTask, listAccounts, listDrafts, listTasks } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { truncate } from "@/lib/utils";
import type { AccountSummary, DraftSummary, TaskSummary } from "@/types";
import { Badge, Button, Card, EmptyState, ErrorState, Input, PageHeader, SkeletonRows } from "@/components/console/ui";
import { Icon } from "@/components/console/icons";
import { useAppStore } from "@/store/appStore";
import { useWorkspaceStore } from "@/store/workspaceStore";

type WorkspaceLane = "idea" | "drafting" | "review" | "published" | "blocked";

interface WorkspaceState {
  accounts: AccountSummary[];
  tasks: TaskSummary[];
  drafts: DraftSummary[];
}

interface WorkspaceCard {
  id: string;
  title: string;
  body: string;
  meta: string;
  href?: string;
  tone: "muted" | "warning" | "success" | "danger" | "brand";
}

export function WorkspacePage() {
  const { locale, t } = useI18n();
  const router = useRouter();
  const pushToast = useAppStore((state) => state.pushToast);
  const composerValue = useWorkspaceStore((state) => state.composerValue);
  const setComposerValue = useWorkspaceStore((state) => state.setComposerValue);
  const selectedLane = useWorkspaceStore((state) => state.selectedLane);
  const setSelectedLane = useWorkspaceStore((state) => state.setSelectedLane);

  const [data, setData] = useState<WorkspaceState | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      const [accountsRes, tasksRes, draftsRes] = await Promise.all([
        listAccounts(1, 100),
        listTasks(1, 50),
        listDrafts(1, 50).catch(() => ({ drafts: [], pagination: { page: 1, page_size: 50, total: 0 } })),
      ]);
      setData({
        accounts: accountsRes.accounts,
        tasks: tasksRes.tasks,
        drafts: draftsRes.drafts,
      });
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : t("workspace.loadError"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const lanes = useMemo<Record<WorkspaceLane, WorkspaceCard[]>>(() => {
    if (!data) {
      return { idea: [], drafting: [], review: [], published: [], blocked: [] };
    }

    return {
      idea: data.accounts
        .filter((account) => !account.last_run_at || !account.posting_frequency)
        .map((account) => ({
          id: account.account_id,
          title: account.name,
          body: truncate(account.positioning, 120),
          meta: account.posting_frequency ? (locale === "zh-CN" ? "等待首次任务运行" : "Awaiting first task run") : (locale === "zh-CN" ? "缺少发布频率配置" : "Missing cadence setup"),
          href: `/accounts/${account.account_id}`,
          tone: "muted",
        })),
      drafting: data.tasks
        .filter((task) => task.status === "pending" || task.status === "running")
        .map((task) => ({
          id: task.task_id,
          title: task.task_id,
          body: truncate(task.positioning_summary, 120),
          meta: task.status === "running" ? (locale === "zh-CN" ? "Agent 链路执行中" : "Agent chain is executing") : (locale === "zh-CN" ? "等待编排执行" : "Queued for orchestration"),
          href: `/task/${task.task_id}`,
          tone: "warning",
        })),
      review: data.drafts
        .filter((draft) => draft.draft_status === "pending_review")
        .map((draft) => ({
          id: String(draft.id),
          title: draft.title,
          body: draft.selected_topic || (locale === "zh-CN" ? "发布前等待人工审核" : "Pending manual review before publish"),
          meta: `Draft #${draft.id}`,
          href: `/drafts/${draft.id}`,
          tone: "brand",
        })),
      published: data.drafts
        .filter((draft) => draft.publish_status === "published")
        .map((draft) => ({
          id: String(draft.id),
          title: draft.title,
          body: draft.selected_topic || (locale === "zh-CN" ? "已通过微信集成发布" : "Published through WeChat integration"),
          meta: locale === "zh-CN" ? "已发布" : "Published",
          href: `/drafts/${draft.id}`,
          tone: "success",
        })),
      blocked: [
        ...data.tasks
          .filter((task) => task.status === "failed")
          .map((task) => ({
            id: task.task_id,
            title: task.task_id,
            body: task.error_message || (locale === "zh-CN" ? "任务在编排过程中失败" : "Task failed during orchestration"),
            meta: locale === "zh-CN" ? "任务失败" : "Task failure",
            href: `/task/${task.task_id}`,
            tone: "danger" as const,
          })),
        ...data.drafts
          .filter((draft) => draft.publish_status === "failed" || draft.draft_status === "rejected" || draft.draft_status === "discarded")
          .map((draft) => ({
            id: `draft-${draft.id}`,
            title: draft.title,
            body: draft.selected_topic || (locale === "zh-CN" ? "草稿需要恢复或重新生成" : "Draft requires recovery or regeneration"),
            meta: draft.publish_status === "failed" ? (locale === "zh-CN" ? "发布失败" : "Publish failed") : `${locale === "zh-CN" ? "草稿" : "Draft"} ${draft.draft_status}`,
            href: `/drafts/${draft.id}`,
            tone: "danger" as const,
          })),
      ],
    };
  }, [data, locale]);

  const submitManualTask = async () => {
    if (!composerValue.trim()) {
      pushToast({
        tone: "warning",
        title: t("workspace.positioningRequired"),
        message: t("workspace.positioningRequiredDesc"),
      });
      return;
    }

    try {
      setSubmitting(true);
      const created = await createTask(composerValue.trim());
      pushToast({
        tone: "success",
        title: t("workspace.taskCreated"),
        message: locale === "zh-CN" ? `任务 ${created.task_id} 已进入队列。` : `Task ${created.task_id} is now queued.`,
      });
      router.push(`/task/${created.task_id}`);
    } catch (submitError) {
      pushToast({
        tone: "danger",
        title: t("workspace.taskCreateFailed"),
        message: submitError instanceof Error ? submitError.message : (locale === "zh-CN" ? "发生了意外错误" : "Unexpected error"),
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={t("workspace.eyebrow")}
        title={t("workspace.title")}
        description={t("workspace.description")}
        actions={
          <Link href="/tasks/history">
            <Button variant="secondary">
              <Icon name="history" className="h-4 w-4" />
              {t("workspace.fullTaskHistory")}
            </Button>
          </Link>
        }
      />

      <div className="grid gap-6 xl:grid-cols-[1.1fr_2fr]">
        <Card title={t("workspace.manualTaskComposer")} description={t("workspace.manualTaskComposerDesc")}>
          <div className="space-y-4">
            <Input
              placeholder={t("workspace.composerPlaceholder")}
              value={composerValue}
              onChange={(event) => setComposerValue(event.target.value)}
            />
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
              {t("workspace.composerApiHint")}
            </div>
            <Button className="w-full" disabled={submitting} onClick={() => void submitManualTask()}>
              <Icon name="play" className="h-4 w-4" />
              {submitting ? t("workspace.creatingTask") : t("workspace.runWorkflow")}
            </Button>
          </div>
        </Card>

        <Card title={t("workspace.laneFocus")} description={t("workspace.laneFocusDesc")}>
          <div className="grid gap-3 sm:grid-cols-5">
            {([
              ["idea", locale === "zh-CN" ? "筹备" : "Idea"],
              ["drafting", locale === "zh-CN" ? "执行中" : "Drafting"],
              ["review", locale === "zh-CN" ? "待审核" : "Review"],
              ["published", locale === "zh-CN" ? "已发布" : "Published"],
              ["blocked", locale === "zh-CN" ? "受阻" : "Blocked"],
            ] as Array<[WorkspaceLane, string]>).map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setSelectedLane(value)}
                className={`rounded-2xl border px-4 py-4 text-left transition ${
                  selectedLane === value ? "border-brand-200 bg-brand-50" : "border-slate-200 bg-white hover:border-slate-300"
                }`}
              >
                <p className="text-sm font-semibold text-slate-900">{label}</p>
                <p className="mt-1 text-xs text-slate-500">{locale === "zh-CN" ? `${lanes[value].length} 条` : `${lanes[value].length} items`}</p>
              </button>
            ))}
          </div>
        </Card>
      </div>

      {loading ? (
        <SkeletonRows rows={5} />
      ) : error ? (
        <ErrorState title={t("workspace.loadError")} description={error} retry={() => void load()} />
      ) : (
        <div className="grid gap-5 xl:grid-cols-5">
          {([
            ["idea", locale === "zh-CN" ? "筹备" : "Idea"],
            ["drafting", locale === "zh-CN" ? "执行中" : "Drafting"],
            ["review", locale === "zh-CN" ? "待审核" : "Review"],
            ["published", locale === "zh-CN" ? "已发布" : "Published"],
            ["blocked", locale === "zh-CN" ? "受阻" : "Blocked"],
          ] as Array<[WorkspaceLane, string]>).map(([lane, label]) => (
            <Card key={lane} title={label} description={locale === "zh-CN" ? `${lanes[lane].length} 条` : `${lanes[lane].length} items`} className={selectedLane === lane ? "ring-2 ring-brand-200" : ""}>
              {lanes[lane].length ? (
                <div className="space-y-3">
                  {lanes[lane].map((card) => (
                    <Link
                      key={card.id}
                      href={card.href ?? "#"}
                      className="block rounded-2xl border border-slate-200 bg-slate-50/70 p-4 transition hover:border-brand-200 hover:bg-brand-50/60"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <p className="text-sm font-semibold text-slate-900">{card.title}</p>
                        <Badge tone={card.tone}>{card.meta}</Badge>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-slate-500">{card.body}</p>
                    </Link>
                  ))}
                </div>
              ) : (
                <EmptyState
                  title={locale === "zh-CN" ? `暂无${label}` : `No ${label.toLowerCase()} items`}
                  description={locale === "zh-CN" ? `当真实后端数据进入${label}阶段后，这个泳道会自动填充。` : `This lane will fill as real backend data reaches the ${label.toLowerCase()} stage.`}
                />
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
