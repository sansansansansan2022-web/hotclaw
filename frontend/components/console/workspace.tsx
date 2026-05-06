"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createTask, getApiOriginDebugInfo, listAccounts, listDrafts, listTasks } from "@/lib/api";
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
  const { locale } = useI18n();
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
      setError(loadError instanceof Error ? loadError.message : locale === "zh-CN" ? "无法加载调试工作台。" : "Unable to load the debug workspace.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const apiInfo = getApiOriginDebugInfo();

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
          meta: account.posting_frequency ? (locale === "zh-CN" ? "等待首次账号运行" : "Awaiting first account run") : (locale === "zh-CN" ? "缺少发布节奏配置" : "Missing cadence setup"),
          href: `/accounts/${account.account_id}`,
          tone: "muted",
        })),
      drafting: data.tasks
        .filter((task) => task.status === "pending" || task.status === "running")
        .map((task) => ({
          id: task.task_id,
          title: task.account_name || task.task_id,
          body: truncate(task.positioning_summary, 120),
          meta: task.account_id ? (locale === "zh-CN" ? "账号内运行" : "Account-scoped run") : (locale === "zh-CN" ? "全局调试任务" : "Global debug task"),
          href: `/task/${task.task_id}`,
          tone: "warning",
        })),
      review: data.drafts
        .filter((draft) => draft.draft_status === "pending_review")
        .map((draft) => ({
          id: String(draft.id),
          title: draft.title,
          body: draft.selected_topic || (locale === "zh-CN" ? "发布前等待人工审核" : "Pending manual review before publish"),
          meta: draft.account_id ? (locale === "zh-CN" ? "账号草稿" : "Account draft") : `Draft #${draft.id}`,
          href: `/drafts/${draft.id}`,
          tone: "brand",
        })),
      published: data.drafts
        .filter((draft) => draft.publish_status === "published")
        .map((draft) => ({
          id: String(draft.id),
          title: draft.title,
          body: draft.selected_topic || (locale === "zh-CN" ? "已通过微信链路发布" : "Published through the WeChat delivery pipeline"),
          meta: locale === "zh-CN" ? "已发布" : "Published",
          href: `/drafts/${draft.id}`,
          tone: "success",
        })),
      blocked: [
        ...data.tasks
          .filter((task) => task.status === "failed")
          .map((task) => ({
            id: task.task_id,
            title: task.account_name || task.task_id,
            body: task.error_message || (locale === "zh-CN" ? "任务在编排过程中失败" : "Task failed during orchestration"),
            meta: task.account_id ? (locale === "zh-CN" ? "账号任务失败" : "Account task failure") : (locale === "zh-CN" ? "全局调试失败" : "Global debug failure"),
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
        title: locale === "zh-CN" ? "需要定位描述" : "Positioning required",
        message: locale === "zh-CN" ? "全局调试任务仍然需要输入定位描述。" : "A global debug task still needs a positioning description.",
      });
      return;
    }

    try {
      setSubmitting(true);
      const created = await createTask(composerValue.trim());
      pushToast({
        tone: "success",
        title: locale === "zh-CN" ? "调试任务已创建" : "Debug task created",
        message: locale === "zh-CN" ? `任务 ${created.task_id} 已进入全局调试队列。` : `Task ${created.task_id} is now queued in the global debug workspace.`,
      });
      router.push(`/task/${created.task_id}`);
    } catch (submitError) {
      pushToast({
        tone: "danger",
        title: locale === "zh-CN" ? "调试任务创建失败" : "Debug task creation failed",
        message: submitError instanceof Error ? submitError.message : locale === "zh-CN" ? "发生了意外错误。" : "Unexpected error",
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={locale === "zh-CN" ? "全局调试入口" : "Global Debug Entry"}
        title={locale === "zh-CN" ? "实验工作台" : "Debug Workspace"}
        description={
          locale === "zh-CN"
            ? "这个页面保留给开发、验收和排障使用。普通运营主路径应从账号详情进入账号工作台，再在账号上下文里运行任务。"
            : "Keep this page for development, QA and troubleshooting. The normal operator path should start from an account detail page and continue inside the account workspace."
        }
        actions={
          <>
            <Link href="/accounts">
              <Button>
                <Icon name="accounts" className="h-4 w-4" />
                {locale === "zh-CN" ? "进入账号列表" : "Open Accounts"}
              </Button>
            </Link>
            <Link href="/tasks/history">
              <Button variant="secondary">
                <Icon name="history" className="h-4 w-4" />
                {locale === "zh-CN" ? "任务历史" : "Task History"}
              </Button>
            </Link>
          </>
        }
      />

      <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        {locale === "zh-CN"
          ? `这个 /workspace 只用于调试入口。当前 API origin：${apiInfo.origin || "/api"}。普通运营请从账号详情进入账号工作台。`
          : `This /workspace page is debug-only. Current API origin: ${apiInfo.origin || "/api"}. Normal operations should start from an account detail page and continue in the account workspace.`}
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_2fr]">
        <Card
          title={locale === "zh-CN" ? "全局调试任务发起" : "Global Debug Composer"}
          description={
            locale === "zh-CN"
              ? "这里只有在没有明确账号上下文时，才建议使用全局 POST /api/v1/tasks。"
              : "Only use the global POST /api/v1/tasks path when you intentionally do not want an account-scoped run."
          }
        >
          <div className="space-y-4">
            <Input
              placeholder={locale === "zh-CN" ? "输入用于实验或排障的定位描述..." : "Describe the positioning used for debugging or experiments..."}
              value={composerValue}
              onChange={(event) => setComposerValue(event.target.value)}
            />
            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              {locale === "zh-CN"
                ? "普通业务任务请从账号详情或账号工作台发起，这里只保留给全局实验、回归验收和问题定位。"
                : "Normal business runs should start from an account detail page or account workspace. This board is reserved for global experiments, QA and troubleshooting."}
            </div>
            <Button className="w-full" disabled={submitting} onClick={() => void submitManualTask()}>
              <Icon name="play" className="h-4 w-4" />
              {submitting ? (locale === "zh-CN" ? "创建调试任务..." : "Creating Debug Task...") : locale === "zh-CN" ? "运行全局调试任务" : "Run Global Debug Task"}
            </Button>
          </div>
        </Card>

        <Card
          title={locale === "zh-CN" ? "调试看板聚焦" : "Debug Board Focus"}
          description={
            locale === "zh-CN"
              ? "保留全局看板视图，但它现在只作为观察跨账号运行信号的调试面板。"
              : "Retain the global board view, but position it as a debugging panel for cross-account runtime signals."
          }
        >
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
                <p className="mt-1 text-xs text-slate-500">{locale === "zh-CN" ? `${lanes[value].length} 项` : `${lanes[value].length} items`}</p>
              </button>
            ))}
          </div>
        </Card>
      </div>

      {loading ? (
        <SkeletonRows rows={5} />
      ) : error ? (
        <ErrorState title={locale === "zh-CN" ? "调试工作台加载失败" : "Debug workspace failed to load"} description={error} retry={() => void load()} />
      ) : (
        <div className="grid gap-5 xl:grid-cols-5">
          {([
            ["idea", locale === "zh-CN" ? "筹备" : "Idea"],
            ["drafting", locale === "zh-CN" ? "执行中" : "Drafting"],
            ["review", locale === "zh-CN" ? "待审核" : "Review"],
            ["published", locale === "zh-CN" ? "已发布" : "Published"],
            ["blocked", locale === "zh-CN" ? "受阻" : "Blocked"],
          ] as Array<[WorkspaceLane, string]>).map(([lane, label]) => (
            <Card key={lane} title={label} description={locale === "zh-CN" ? `${lanes[lane].length} 项` : `${lanes[lane].length} items`} className={selectedLane === lane ? "ring-2 ring-brand-200" : ""}>
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
                  title={locale === "zh-CN" ? "当前泳道为空" : "No items in this lane"}
                  description={
                    lane === "idea"
                      ? locale === "zh-CN"
                        ? "建议从账号详情进入账号工作台，为具体账号发起运行。"
                        : "Prefer opening an account workspace and starting runs from a specific account."
                      : locale === "zh-CN"
                        ? "当前没有符合该调试状态的全局记录。"
                        : "There are no global records matching this debugging state."
                  }
                />
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
