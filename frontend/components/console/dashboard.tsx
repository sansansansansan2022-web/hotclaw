"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getAllSystemConfigs, getPendingDraftCount, listAccounts, listDrafts, listTasks } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { formatDateTime, formatDuration, formatNumber, startCase, truncate } from "@/lib/utils";
import type { AccountSummary, DraftListResponse, SystemConfigMap, TaskSummary } from "@/types";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, SkeletonRows, StatCard, Table } from "@/components/console/ui";
import { Icon } from "@/components/console/icons";

interface DashboardState {
  accounts: AccountSummary[];
  tasks: TaskSummary[];
  drafts: DraftListResponse["drafts"];
  pendingReviewCount: number;
  configs: SystemConfigMap;
}

function accountTone(status: string | null): "success" | "warning" | "danger" | "muted" {
  if (status === "running") return "warning";
  if (status === "failed") return "danger";
  if (status === "completed") return "success";
  return "muted";
}

function formatDashboardLoadError(error: unknown, locale: string): string {
  const fallback = locale === "zh-CN" ? "无法加载仪表盘。" : "Unable to load dashboard.";
  const message = error instanceof Error ? error.message : fallback;
  if (!/failed to fetch|load failed|networkerror/i.test(message)) {
    return message;
  }

  return locale === "zh-CN"
    ? "无法连接后端服务，仪表盘数据暂时不可用。请确认后端已启动，并检查 /api/v1/health 后重试。"
    : "Unable to connect to the backend service, so dashboard data is unavailable. Confirm the backend is running, check /api/v1/health, then retry.";
}

export function DashboardPage() {
  const { locale, t, taskStatusLabel, draftStatusLabel, publishStatusLabel, token } = useI18n();
  const [data, setData] = useState<DashboardState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const safeAccounts = Array.isArray(data?.accounts) ? data.accounts : [];
  const safeTasks = Array.isArray(data?.tasks) ? data.tasks : [];
  const safeDrafts = Array.isArray(data?.drafts) ? data.drafts : [];
  const safeConfigs = (data?.configs && typeof data.configs === "object" ? data.configs : {}) as SystemConfigMap;

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      const [accountsRes, tasksRes, draftsRes, pendingRes, configsRes] = await Promise.all([
        listAccounts(1, 100),
        listTasks(1, 20),
        listDrafts(1, 20).catch(() => ({ drafts: [], pagination: { page: 1, page_size: 20, total: 0, total_pages: 0 } })),
        getPendingDraftCount().catch(() => ({ count: 0 })),
        getAllSystemConfigs().catch(() => ({})),
      ]);

      setData({
        accounts: Array.isArray(accountsRes?.accounts) ? accountsRes.accounts : [],
        tasks: Array.isArray(tasksRes?.tasks) ? tasksRes.tasks : [],
        drafts: Array.isArray(draftsRes?.drafts) ? draftsRes.drafts : [],
        pendingReviewCount: typeof pendingRes?.count === "number" ? pendingRes.count : 0,
        configs: (configsRes && typeof configsRes === "object" ? configsRes : {}) as SystemConfigMap,
      });
    } catch (loadError) {
      setError(formatDashboardLoadError(loadError, locale));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const metrics = useMemo(() => {
    const failedTasks = safeTasks.filter((task) => task.status === "failed").length;
    const activeAccounts = safeAccounts.filter((account) => account.is_active).length;

    return [
      {
        label: t("dashboard.managedAccounts"),
        value: formatNumber(safeAccounts.length),
        hint:
          locale === "zh-CN"
            ? `${activeAccounts} 个启用，${safeAccounts.length - activeAccounts} 个暂停`
            : `${activeAccounts} active, ${safeAccounts.length - activeAccounts} paused`,
        tone: "success" as const,
        icon: <Icon name="accounts" className="h-6 w-6" />,
      },
      {
        label: t("dashboard.pendingReview"),
        value: formatNumber(data?.pendingReviewCount ?? 0),
        hint: locale === "zh-CN" ? "等待人工确认的草稿" : "Drafts waiting for manual approval",
        tone: "warning" as const,
        icon: <Icon name="drafts" className="h-6 w-6" />,
      },
      {
        label: t("dashboard.recentTasks"),
        value: formatNumber(safeTasks.length),
        hint:
          locale === "zh-CN"
            ? `${failedTasks} 个失败任务待跟进`
            : `${failedTasks} failed task${failedTasks === 1 ? "" : "s"} need follow-up`,
        tone: "info" as const,
        icon: <Icon name="history" className="h-6 w-6" />,
      },
      {
        label: t("dashboard.publishReady"),
        value: formatNumber(safeDrafts.filter((draft) => draft.draft_status === "approved").length),
        hint: locale === "zh-CN" ? "已通过审核、可投递到微信的草稿" : "Approved drafts ready for WeChat delivery",
        tone: "brand" as const,
        icon: <Icon name="publish" className="h-6 w-6" />,
      },
    ];
  }, [locale, safeAccounts, safeDrafts, safeTasks, t]);

  const pendingCenter = useMemo(() => {
    const failedTasks = safeTasks.filter((task) => task.status === "failed").length;
    const setupGap = safeAccounts.filter((account) => !account.posting_frequency).length;
    const globalPublish = safeConfigs.global_publish_enabled;
    const missingRuntime = globalPublish === false || globalPublish === "false" ? 1 : 0;

    return [
      {
        title: locale === "zh-CN" ? "草稿审核队列" : "Draft review queue",
        count: data?.pendingReviewCount ?? 0,
        link: "/drafts",
        description:
          locale === "zh-CN"
            ? "待审核草稿是内容工作流中的下一个人工检查点。"
            : "Pending review drafts are the next manual checkpoint in the content workflow.",
      },
      {
        title: locale === "zh-CN" ? "失败任务重跑" : "Failed task reruns",
        count: failedTasks,
        link: "/tasks/history",
        description:
          locale === "zh-CN"
            ? "Agent 链路中的最近失败需要在下个调度窗口前重试或排查。"
            : "Recent failures from the agent chain should be retried or inspected before the next schedule window.",
      },
      {
        title: locale === "zh-CN" ? "账号配置缺口" : "Account setup gaps",
        count: setupGap,
        link: "/accounts",
        description:
          locale === "zh-CN"
            ? "缺少频率或策略信息的账号无法稳定参与自动化。"
            : "Accounts missing cadence or strategy details cannot run a reliable automation plan.",
      },
      {
        title: locale === "zh-CN" ? "发布保护" : "Publish safeguards",
        count: missingRuntime,
        link: "/settings",
        description:
          locale === "zh-CN"
            ? "全局发布开关和超时配置位于运行时设置中。"
            : "Global publish toggles and timeout configuration live in runtime settings.",
      },
    ];
  }, [data?.pendingReviewCount, locale, safeAccounts, safeConfigs, safeTasks]);

  const flowBoard = useMemo(() => {
    return [
      { label: draftStatusLabel("draft"), value: safeDrafts.filter((draft) => draft.draft_status === "draft").length, tone: "muted" as const },
      { label: draftStatusLabel("pending_review"), value: data?.pendingReviewCount ?? 0, tone: "warning" as const },
      { label: draftStatusLabel("approved"), value: safeDrafts.filter((draft) => draft.draft_status === "approved").length, tone: "success" as const },
      { label: publishStatusLabel("published"), value: safeDrafts.filter((draft) => draft.publish_status === "published").length, tone: "brand" as const },
      { label: locale === "zh-CN" ? "发布失败" : "Failed Publish", value: safeDrafts.filter((draft) => draft.publish_status === "failed").length, tone: "danger" as const },
    ];
  }, [data?.pendingReviewCount, draftStatusLabel, locale, publishStatusLabel, safeDrafts]);

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Operations Overview"
        title="Dashboard"
        description="Core metrics, pending actions, workflow flow and the latest account activity across HotClaw."
        actions={
          <>
            <Link href="/accounts/new">
              <Button>
                <Icon name="plus" className="h-4 w-4" />
                {locale === "zh-CN" ? "接入公众号" : "Connect Account"}
              </Button>
            </Link>
            <Link href="/workspace">
              <Button variant="secondary">
                <Icon name="arrowUpRight" className="h-4 w-4" />
                {locale === "zh-CN" ? "调试工作台" : "Debug Workspace"}
              </Button>
            </Link>
          </>
        }
      />

      {loading ? (
        <SkeletonRows rows={6} />
      ) : error ? (
        <ErrorState title={t("dashboard.loadError")} description={error} retry={() => void load()} />
      ) : data ? (
        <>
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
            {metrics.map((metric) => (
              <StatCard key={metric.label} label={metric.label} value={metric.value} hint={metric.hint} tone={metric.tone} icon={metric.icon} />
            ))}
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.25fr_1fr]">
            <Card title={t("dashboard.pendingCenter")} description={t("dashboard.pendingCenterDesc")}>
              <div className="space-y-4">
                {pendingCenter.map((item) => (
                  <Link
                    key={item.title}
                    href={item.link}
                    className="flex items-start justify-between gap-4 rounded-2xl border border-slate-200 p-4 transition hover:border-brand-200 hover:bg-brand-50/60"
                  >
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{item.title}</p>
                      <p className="mt-1 text-sm leading-6 text-slate-500">{item.description}</p>
                    </div>
                    <Badge tone={item.count > 0 ? "brand" : "muted"}>{formatNumber(item.count)}</Badge>
                  </Link>
                ))}
              </div>
            </Card>

            <Card title={t("dashboard.flowBoard")} description={t("dashboard.flowBoardDesc")}>
              <div className="grid gap-3 sm:grid-cols-2">
                {flowBoard.map((item) => (
                  <div key={item.label} className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-medium text-slate-600">{item.label}</p>
                      <Badge tone={item.tone}>{formatNumber(item.value)}</Badge>
                    </div>
                    <div className="mt-4 h-2 rounded-full bg-slate-200">
                      <div className="h-2 rounded-full bg-brand-500" style={{ width: `${Math.min(item.value * 16, 100)}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.2fr_1fr]">
            <Card
              title={locale === "zh-CN" ? "最近账号运行" : "Recent Account Runs"}
              description={locale === "zh-CN" ? "基于账号调度状态提取的最新运行信号。" : "Latest runtime signals pulled from account scheduler state."}
            >
              {safeAccounts.length ? (
                <div className="space-y-4">
                  {safeAccounts
                    .slice()
                    .sort((left, right) => {
                      const leftDate = new Date(left.last_run_at ?? left.created_at).getTime();
                      const rightDate = new Date(right.last_run_at ?? right.created_at).getTime();
                      return rightDate - leftDate;
                    })
                    .slice(0, 6)
                    .map((account) => (
                      <div key={account.account_id} className="flex flex-col gap-3 rounded-2xl border border-slate-200 p-4 md:flex-row md:items-center md:justify-between">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="truncate text-sm font-semibold text-slate-900">{account.name}</p>
                            <Badge tone={accountTone(account.last_run_status)}>{taskStatusLabel(account.last_run_status)}</Badge>
                            <Badge tone={account.is_active ? "success" : "muted"}>{token(account.is_active ? "active" : "paused")}</Badge>
                          </div>
                          <p className="mt-2 text-sm leading-6 text-slate-500">{truncate(account.positioning, 120)}</p>
                        </div>
                        <div className="flex items-center gap-3 md:text-right">
                          <div>
                            <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{t("dashboard.lastRun")}</p>
                            <p className="mt-1 text-sm font-medium text-slate-700">{formatDateTime(account.last_run_at ?? account.created_at)}</p>
                          </div>
                          <Link href={`/accounts/${account.account_id}`}>
                            <Button variant="secondary" size="sm">
                              {t("dashboard.open")}
                            </Button>
                          </Link>
                        </div>
                      </div>
                    ))}
                </div>
              ) : (
                <EmptyState
                  title={t("dashboard.noAccounts")}
                  description={t("dashboard.noAccountsDesc")}
                  action={
                    <Link href="/accounts/new">
                      <Button>{locale === "zh-CN" ? "接入第一个公众号" : "Connect Your First Account"}</Button>
                    </Link>
                  }
                />
              )}
            </Card>

            <Card title="Quick Access" description="Shortcut blocks that mirror the UXPilot dashboard structure.">
              <div className="grid gap-3">
                {[
                  { href: "/drafts", title: "Draft Inbox", desc: "Review draft approvals and publication blockers." },
                  { href: "/publish-logs", title: "Failed Publishes", desc: "Inspect WeChat failures, retries and error messages." },
                  { href: "/tasks/history", title: "Task History", desc: "Audit the latest agent chain runs and rerun failed tasks." },
                  { href: "/settings/wechat", title: "WeChat Config", desc: "Bind credentials, test connections and set default publish rules." },
                ].map((card) => (
                  <Link key={card.href} href={card.href} className="rounded-2xl border border-slate-200 p-4 transition hover:border-brand-200 hover:bg-brand-50/60">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{card.title}</p>
                        <p className="mt-1 text-sm text-slate-500">{card.desc}</p>
                      </div>
                      <Icon name="arrowUpRight" className="h-4 w-4 text-slate-400" />
                    </div>
                  </Link>
                ))}
              </div>
            </Card>
          </div>

          <Card title="Recent Tasks" description="Latest task runs across manual and account-triggered workflows.">
            {safeTasks.length ? (
              <Table columns={["Task", "Status", "Created", "Duration", "Audit", "Action"]}>
                {safeTasks.slice(0, 8).map((task) => (
                  <tr key={task.task_id} className="align-top">
                    <td className="px-5 py-4">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{task.task_id}</p>
                        <p className="mt-1 text-sm text-slate-500">{truncate(task.positioning_summary, 84)}</p>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <Badge
                        tone={
                          task.status === "completed"
                            ? "success"
                            : task.status === "failed"
                              ? "danger"
                              : task.status === "running"
                                ? "warning"
                                : "muted"
                        }
                      >
                        {startCase(task.status)}
                      </Badge>
                    </td>
                    <td className="px-5 py-4 text-sm text-slate-600">{formatDateTime(task.created_at)}</td>
                    <td className="px-5 py-4 text-sm text-slate-600">{formatDuration(task.elapsed_seconds)}</td>
                    <td className="px-5 py-4">
                      {task.audit_result ? (
                        <Badge tone={task.audit_result.passed ? "success" : "warning"}>{task.audit_result.passed ? "Passed" : "Review"}</Badge>
                      ) : (
                        <span className="text-sm text-slate-400">No audit snapshot</span>
                      )}
                    </td>
                    <td className="px-5 py-4">
                      <Link href={`/task/${task.task_id}`}>
                        <Button variant="secondary" size="sm">
                          Inspect
                        </Button>
                      </Link>
                    </td>
                  </tr>
                ))}
              </Table>
            ) : (
              <EmptyState
                title="No tasks have been run yet"
                description="Kick off a manual workflow from the workspace or run an account to populate task history."
                action={
                  <Link href="/workspace">
                    <Button>{locale === "zh-CN" ? "打开调试工作台" : "Open Debug Workspace"}</Button>
                  </Link>
                }
              />
            )}
          </Card>
        </>
      ) : null}
    </div>
  );
}
