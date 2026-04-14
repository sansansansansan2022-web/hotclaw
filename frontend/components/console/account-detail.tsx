"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { disableAccount, enableAccount, getAccount, getApiOriginDebugInfo, getPendingDraftCount, getWeChatConfig, runAccount } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { formatDateTime, formatDuration, formatNumber, truncate } from "@/lib/utils";
import type { AccountDetail, WeChatConfigDetail } from "@/types";
import { Badge, Button, Card, ConfirmDialog, EmptyState, ErrorState, PageHeader, SkeletonRows, StatCard, Table } from "@/components/console/ui";
import { Icon } from "@/components/console/icons";
import { useAppStore } from "@/store/appStore";

function accountTone(status: string | null): "success" | "warning" | "danger" | "muted" {
  if (status === "running") return "warning";
  if (status === "failed") return "danger";
  if (status === "completed" || status === "success") return "success";
  return "muted";
}

function referenceSyncTone(status: string | null): "success" | "warning" | "danger" | "muted" {
  if (status === "synced" || status === "manual_only") return "success";
  if (status === "failed") return "danger";
  if (status === "pending") return "warning";
  return "muted";
}

function getAutomationPlan(detail: AccountDetail) {
  if (detail.automation_plan_summary) {
    return detail.automation_plan_summary;
  }

  // Deprecated compatibility fallback only. Remove after account detail and
  // workspace surfaces stop depending on Account legacy scheduling mirrors.
  return {
    id: null,
    account_id: detail.account_id,
    config_source: "legacy_fallback" as const,
    plan_type: detail.operation_mode,
    is_enabled: detail.auto_run_enabled,
    run_strategy:
      detail.operation_mode === "manual"
        ? "manual_only"
        : detail.posting_frequency
          ? "hybrid"
          : "manual_only",
    schedule_type: detail.posting_frequency === "daily" ? "daily" : detail.posting_frequency ? "weekly" : "none",
    schedule_config: detail.posting_time ? { time: detail.posting_time } : null,
    schedule_summary: detail.posting_frequency
      ? `${detail.posting_frequency}${detail.posting_time ? ` @ ${detail.posting_time}` : ""}`
      : "Manual only",
    auto_publish_enabled: detail.auto_publish_enabled,
    publish_review_required: !detail.auto_publish_enabled,
    max_posts_per_day: detail.max_posts_per_day,
    min_interval_minutes: detail.min_interval_minutes,
    timezone: "Asia/Shanghai",
    next_run_at: detail.next_run_at,
    last_run_at: detail.last_run_at,
    notes: null,
    latest_status: detail.last_run_status,
    is_active_plan: true,
    created_at: null,
    updated_at: null,
  };
}

function getWeChatConnectionSummary(config: WeChatConfigDetail | null) {
  if (config && config.is_enabled && config.has_app_secret && config.test_status === "success") {
    return {
      connected: true,
      title: "Connected",
      description: config.test_message || "The real official account connection has been validated.",
      tone: "success" as const,
    };
  }

  return {
    connected: false,
    title: "Content-only",
    description:
      config?.test_message ||
      "This account can still operate in content mode, but it is not ready for the real publish chain yet.",
    tone: "warning" as const,
  };
}

export function AccountDetailPage({ accountId }: { accountId: string }) {
  const { locale, operationModeLabel, taskStatusLabel, publishStatusLabel } = useI18n();
  const pushToast = useAppStore((state) => state.pushToast);
  const [detail, setDetail] = useState<AccountDetail | null>(null);
  const [wechatConfig, setWeChatConfig] = useState<WeChatConfigDetail | null>(null);
  const [pendingCount, setPendingCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [confirmDisable, setConfirmDisable] = useState(false);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      const [detailRes, pendingRes] = await Promise.all([
        getAccount(accountId),
        getPendingDraftCount(accountId).catch(() => ({ count: 0 })),
      ]);
      setDetail(detailRes);
      setPendingCount(pendingRes.count);
      setWeChatConfig(await getWeChatConfig(accountId).catch(() => null));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : locale === "zh-CN" ? "无法加载账号详情。" : "Unable to load account detail.");
    } finally {
      setLoading(false);
    }
  };

  const automationPlan = detail ? getAutomationPlan(detail) : null;
  const latestOps = detail?.latest_ops_context ?? null;
  const latestRunStrategy = latestOps?.run_strategy ?? null;
  const latestEffectiveMode = detail?.latest_effective_mode ?? latestRunStrategy?.effective_mode ?? null;
  const latestOpsDegraded =
    detail?.latest_ops_degraded ??
    Boolean(
      automationPlan?.plan_type &&
        latestEffectiveMode &&
        automationPlan.plan_type !== latestEffectiveMode,
    );
  const wechatConnection = getWeChatConnectionSummary(wechatConfig);

  useEffect(() => {
    void load();
  }, [accountId]);

  const runNow = async () => {
    try {
      if (process.env.NODE_ENV !== "production" && typeof window !== "undefined") {
        const apiInfo = getApiOriginDebugInfo();
        console.info("[HotClaw][account-detail] run-click", {
          accountId,
          apiOrigin: apiInfo.origin || "/api",
          apiSource: apiInfo.source,
        });
      }
      const response = await runAccount(accountId);
      pushToast({
        tone: "success",
        title: locale === "zh-CN" ? "账号运行已排队" : "Account run queued",
        message:
          locale === "zh-CN"
            ? `任务 ${response.task_id} 已在当前账号上下文中启动。`
            : `Task ${response.task_id} started inside this account context.`,
      });
      await load();
    } catch (runError) {
      pushToast({
        tone: "danger",
        title: locale === "zh-CN" ? "运行失败" : "Run failed",
        message: runError instanceof Error ? runError.message : locale === "zh-CN" ? "发生了意外错误。" : "Unexpected error.",
      });
    }
  };

  const toggleActive = async (nextActive: boolean) => {
    try {
      if (nextActive) {
        await enableAccount(accountId);
        pushToast({
          tone: "success",
          title: locale === "zh-CN" ? "账号已启用" : "Account enabled",
          message: locale === "zh-CN" ? "调度器现在可以再次使用这个账号。" : "The scheduler can use this account again.",
        });
      } else {
        await disableAccount(accountId);
        pushToast({
          tone: "warning",
          title: locale === "zh-CN" ? "账号已停用" : "Account disabled",
          message:
            locale === "zh-CN"
              ? "这个账号的自动化与定时运行现在都已暂停。"
              : "Automations and scheduled runs for this account are now paused.",
        });
      }
      setConfirmDisable(false);
      await load();
    } catch (toggleError) {
      pushToast({
        tone: "danger",
        title: locale === "zh-CN" ? "状态更新失败" : "Status change failed",
        message: toggleError instanceof Error ? toggleError.message : locale === "zh-CN" ? "发生了意外错误。" : "Unexpected error.",
      });
    }
  };

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Account Detail"
        title={detail?.name || "Account"}
        description="Inspect the backend-backed account profile, runtime posture, recent tasks, and the account-scoped asset entry points."
        actions={
          <>
            <Link href={`/accounts/${accountId}/create`}>
              <Button>
                <Icon name="plus" className="h-4 w-4" />
                {locale === "zh-CN" ? "新建任务" : "New Task"}
              </Button>
            </Link>
            <Link href={`/accounts/${accountId}/workspace`}>
              <Button variant="secondary">
                <Icon name="workspace" className="h-4 w-4" />
                {locale === "zh-CN" ? "打开工作台" : "Open Workspace"}
              </Button>
            </Link>
            <Link href={`/accounts/${accountId}/edit`}>
              <Button variant="secondary">
                <Icon name="edit" className="h-4 w-4" />
                Edit
              </Button>
            </Link>
            <Link href={`/settings/wechat/${accountId}`}>
              <Button variant="secondary">WeChat Config</Button>
            </Link>
            <Link href={`/accounts/${accountId}/reference-sources`}>
              <Button variant="secondary">Reference Sources</Button>
            </Link>
            <Link href={`/accounts/${accountId}/automation`}>
              <Button variant="secondary">Automation Plan</Button>
            </Link>
            <Button variant={detail?.is_active === false ? "secondary" : "destructive"} onClick={() => (detail?.is_active ? setConfirmDisable(true) : void toggleActive(true))}>
              {detail?.is_active ? "Disable" : "Enable"}
            </Button>
          </>
        }
      />

      {loading ? (
        <SkeletonRows rows={5} />
      ) : error ? (
        <ErrorState
          title={locale === "zh-CN" ? "账号详情加载失败" : "Account detail failed to load"}
          description={error}
          retry={() => void load()}
        />
      ) : detail ? (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">Current Account</Badge>
            <Badge tone="muted">{detail.name}</Badge>
            <Badge tone="muted">{accountId}</Badge>
            <Badge tone={wechatConnection.tone}>{wechatConnection.connected ? "WeChat Connected" : "Content-only Mode"}</Badge>
          </div>

          <Card
            title="Official Account Connection"
            description="Real official-account credentials are now part of onboarding, but you can still keep an account in content-only mode if the binding is skipped or not validated yet."
            action={
              <Link href={`/settings/wechat/${accountId}`}>
                <Button variant="secondary" size="sm">
                  Open WeChat Config
                </Button>
              </Link>
            }
          >
            <div className="flex flex-wrap items-center gap-3">
              <Badge tone={wechatConnection.tone}>{wechatConnection.title}</Badge>
              {wechatConfig?.app_id_masked ? <Badge tone="muted">{wechatConfig.app_id_masked}</Badge> : null}
            </div>
            <p className="mt-4 text-sm leading-6 text-slate-600">{wechatConnection.description}</p>
            {automationPlan?.plan_type !== "manual" && !wechatConnection.connected ? (
              <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                {`The current ${automationPlan?.plan_type} plan cannot enter the real publish chain until the official account connection succeeds.`}
              </div>
            ) : null}
          </Card>

          <Card
            title="Automation Plan Summary"
            description="This account now reads runtime and publish posture from the active automation plan first."
            action={
              <Link href={`/accounts/${accountId}/automation`}>
                <Button variant="secondary" size="sm">
                  Manage Plan
                </Button>
              </Link>
            }
          >
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-2xl border border-slate-200 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Plan Type</p>
                <p className="mt-2 text-sm font-semibold text-slate-900">{operationModeLabel(automationPlan?.plan_type ?? detail.operation_mode)}</p>
              </div>
              <div className="rounded-2xl border border-slate-200 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Schedule</p>
                <p className="mt-2 text-sm font-semibold text-slate-900">{automationPlan?.schedule_summary || "Manual only"}</p>
              </div>
              <div className="rounded-2xl border border-slate-200 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Plan Status</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Badge tone={automationPlan?.is_enabled ? "success" : "muted"}>{automationPlan?.is_enabled ? "Enabled" : "Disabled"}</Badge>
                  <Badge tone={automationPlan?.auto_publish_enabled ? "success" : "muted"}>{automationPlan?.auto_publish_enabled ? "Auto Publish" : "Manual Publish"}</Badge>
                </div>
              </div>
              <div className="rounded-2xl border border-slate-200 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Next Run</p>
                <p className="mt-2 text-sm font-semibold text-slate-900">{formatDateTime(automationPlan?.next_run_at || detail.next_run_at)}</p>
              </div>
            </div>

            {latestRunStrategy ? (
              <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="info">Latest Ops Decision</Badge>
                  <Badge tone={latestRunStrategy.allow_run ? "success" : "danger"}>
                    {latestRunStrategy.allow_run ? "Run Allowed" : "Run Blocked"}
                  </Badge>
                  <Badge tone={latestRunStrategy.allow_auto_publish ? "success" : "warning"}>
                    {latestRunStrategy.allow_auto_publish ? "Auto Publish Allowed" : "Review First"}
                  </Badge>
                  <Badge tone={latestOps?.account_health?.status === "ready" ? "success" : latestOps?.account_health?.status === "risk_recovery" ? "danger" : "warning"}>
                    {latestOps?.account_health?.status ?? "attention"}
                  </Badge>
                </div>
                <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Plan Type</p>
                    <p className="mt-2 text-sm font-semibold text-slate-900">{operationModeLabel(automationPlan?.plan_type ?? detail.operation_mode)}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Last Effective Mode</p>
                    <p className="mt-2 text-sm font-semibold text-slate-900">{latestEffectiveMode ?? "Not recorded"}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Preferred Sources</p>
                    <p className="mt-2 text-sm font-semibold text-slate-900">{latestRunStrategy.preferred_reference_source_ids.length}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Avoided Topics</p>
                    <p className="mt-2 text-sm font-semibold text-slate-900">{latestRunStrategy.avoid_recent_topics.length}</p>
                  </div>
                </div>
                {latestOpsDegraded ? (
                  <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                    {`The active ${automationPlan?.plan_type ?? detail.operation_mode} plan was downgraded to ${latestEffectiveMode} on the latest run.`}
                  </div>
                ) : null}
                {(latestOps?.ops_notes ?? []).length ? (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {latestOps?.ops_notes?.map((note) => (
                      <Badge key={note} tone="muted">
                        {note}
                      </Badge>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}
          </Card>

          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-6">
            <StatCard
              label="Operation Mode"
              value={operationModeLabel(detail.operation_mode)}
              hint="Effective runtime mode mirrored from the active plan"
              tone="brand"
              icon={<Icon name="workspace" className="h-6 w-6" />}
            />
            <StatCard
              label="Pending Review"
              value={formatNumber(pendingCount)}
              hint="Drafts that still require manual action for this account"
              tone="warning"
              icon={<Icon name="drafts" className="h-6 w-6" />}
            />
            <StatCard
              label="Last Run Status"
              value={taskStatusLabel(detail.last_run_status)}
              hint={detail.last_error_message || "Most recent runtime signal"}
              tone={accountTone(detail.last_run_status)}
              icon={<Icon name="history" className="h-6 w-6" />}
            />
            <StatCard
              label="Publish Status"
              value={publishStatusLabel(detail.last_publish_status)}
              hint={detail.last_publish_error_message || "Most recent publish signal"}
              tone={accountTone(detail.last_publish_status)}
              icon={<Icon name="publish" className="h-6 w-6" />}
            />
            <StatCard
              label="Reference Sources"
              value={formatNumber(detail.reference_source_count ?? 0)}
              hint={`Enabled ${formatNumber(detail.reference_source_enabled_count ?? 0)} · Latest ${detail.reference_source_last_sync_status ?? "none"}`}
              tone={referenceSyncTone(detail.reference_source_last_sync_status)}
              icon={<Icon name="settings" className="h-6 w-6" />}
            />
            <StatCard
              label="Official Account"
              value={wechatConnection.connected ? "Connected" : "Content-only"}
              hint={wechatConnection.description}
              tone={wechatConnection.tone}
              icon={<Icon name="publish" className="h-6 w-6" />}
            />
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.1fr_0.95fr]">
            <Card
              title="Account Overview"
              description="Keep positioning, audience, references and content strategy visible as the account identity layer."
            >
              <div className="space-y-5">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Positioning</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-slate-600">{detail.positioning}</p>
                </div>
                <div className="grid gap-5 md:grid-cols-2">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Audience</p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{detail.audience || "Not set"}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Tone & Style</p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{detail.tone_style || "Not set"}</p>
                  </div>
                </div>
                <div className="grid gap-5 md:grid-cols-2">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Reference Accounts</p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{detail.reference_accounts || "Not set"}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Content Strategy</p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{detail.content_strategy || "Not set"}</p>
                  </div>
                </div>
              </div>
            </Card>

            <Card
              title="Runtime & Safeguards"
              description="These values remain backward-compatible on the account detail response, but the system now prefers the active automation plan."
            >
              <div className="grid gap-4 text-sm text-slate-600">
                <div className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 p-4">
                  <div>
                    <p className="font-medium text-slate-900">Account State</p>
                    <p className="text-slate-500">Whether the scheduler can operate this account.</p>
                  </div>
                  <Badge tone={detail.is_active ? "success" : "muted"}>{detail.is_active ? "Active" : "Paused"}</Badge>
                </div>
                <div className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 p-4">
                  <div>
                    <p className="font-medium text-slate-900">Plan Enablement</p>
                    <p className="text-slate-500">Whether scheduled automation is currently allowed to run.</p>
                  </div>
                  <Badge tone={automationPlan?.is_enabled ? "success" : "muted"}>{automationPlan?.is_enabled ? "Enabled" : "Disabled"}</Badge>
                </div>
                <div className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 p-4">
                  <div>
                    <p className="font-medium text-slate-900">Auto Publish</p>
                    <p className="text-slate-500">Whether the active plan allows automatic publishing.</p>
                  </div>
                  <Badge tone={automationPlan?.auto_publish_enabled ? "success" : "muted"}>{automationPlan?.auto_publish_enabled ? "Enabled" : "Disabled"}</Badge>
                </div>
                <div className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 p-4">
                  <div>
                    <p className="font-medium text-slate-900">Publish Paused</p>
                    <p className="text-slate-500">Manual emergency stop for outbound publishing.</p>
                  </div>
                  <Badge tone={detail.publish_paused ? "danger" : "success"}>{detail.publish_paused ? "Paused" : "Open"}</Badge>
                </div>
                <div className="rounded-2xl border border-slate-200 p-4">
                  <p className="font-medium text-slate-900">Publish Limits</p>
                  <p className="mt-2 text-slate-500">Max posts per day: {automationPlan?.max_posts_per_day ?? "Not set"}</p>
                  <p className="mt-1 text-slate-500">Min interval minutes: {automationPlan?.min_interval_minutes ?? "Not set"}</p>
                </div>
              </div>
            </Card>
          </div>

          <Card
            title="Recent Task Runs"
            description="Recent execution records produced while operating this account. Tasks stay inside the account workspace path rather than acting as the main product entry."
          >
            {detail.recent_tasks.length ? (
              <Table columns={["Task", "Status", "Created", "Duration", "Action"]}>
                {detail.recent_tasks.map((task) => (
                  <tr key={task.task_id}>
                    <td className="px-5 py-4 text-sm font-semibold text-slate-900">{task.task_id}</td>
                    <td className="px-5 py-4">
                      <Badge tone={accountTone(task.status)}>{taskStatusLabel(task.status)}</Badge>
                    </td>
                    <td className="px-5 py-4 text-sm text-slate-600">{formatDateTime(task.created_at)}</td>
                    <td className="px-5 py-4 text-sm text-slate-600">{formatDuration(task.elapsed_seconds)}</td>
                    <td className="px-5 py-4">
                      <Link href={`/task/${task.task_id}`}>
                        <Button variant="secondary" size="sm">
                          Open
                        </Button>
                      </Link>
                    </td>
                  </tr>
                ))}
              </Table>
            ) : (
              <EmptyState
                title="No recent tasks"
                description="Open this account workspace and run it once to populate recent tasks here."
              />
            )}
          </Card>

          <Card
            title="Operations & Assets"
            description="Collect the workspace, drafts, tasks, publish, reference, automation and content-asset entry points for this account in one place."
          >
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <Link href={`/accounts/${accountId}/workspace`} className="rounded-2xl border border-slate-200 p-4 transition hover:border-brand-200 hover:bg-brand-50/60">
                <p className="text-sm font-semibold text-slate-900">Account Workspace</p>
                <p className="mt-1 text-sm text-slate-500">Run tasks, inspect review queues and operate inside this account context.</p>
              </Link>
              <Link href={`/accounts/${accountId}/reference-sources`} className="rounded-2xl border border-slate-200 p-4 transition hover:border-brand-200 hover:bg-brand-50/60">
                <p className="text-sm font-semibold text-slate-900">Reference Sources</p>
                <p className="mt-1 text-sm text-slate-500">Manage the publications, URLs and pasted articles this account tracks as references. Currently {detail.reference_source_count ?? 0} source(s).</p>
              </Link>
              <Link href={`/accounts/${accountId}/automation`} className="rounded-2xl border border-slate-200 p-4 transition hover:border-brand-200 hover:bg-brand-50/60">
                <p className="text-sm font-semibold text-slate-900">Automation Plan</p>
                <p className="mt-1 text-sm text-slate-500">{automationPlan?.schedule_summary || "Currently configured as a manual-only plan."}</p>
              </Link>
              <Link href={`/drafts?account_id=${accountId}`} className="rounded-2xl border border-slate-200 p-4 transition hover:border-brand-200 hover:bg-brand-50/60">
                <p className="text-sm font-semibold text-slate-900">Account Drafts</p>
                <p className="mt-1 text-sm text-slate-500">{pendingCount} pending review draft(s) linked to this account.</p>
              </Link>
              <Link href={`/tasks/history?account_id=${accountId}`} className="rounded-2xl border border-slate-200 p-4 transition hover:border-brand-200 hover:bg-brand-50/60">
                <p className="text-sm font-semibold text-slate-900">Account Tasks</p>
                <p className="mt-1 text-sm text-slate-500">Inspect only the task history and execution traces created for this account.</p>
              </Link>
              <Link href="/publish-logs" className="rounded-2xl border border-slate-200 p-4 transition hover:border-brand-200 hover:bg-brand-50/60">
                <p className="text-sm font-semibold text-slate-900">Publish Logs</p>
                <p className="mt-1 text-sm text-slate-500">{truncate(detail.last_publish_error_message, 90) || "Inspect the latest publish attempts, failures and retry status."}</p>
              </Link>
              <Link href={`/accounts/${accountId}/memory`} className="rounded-2xl border border-slate-200 p-4 transition hover:border-brand-200 hover:bg-brand-50/60">
                <p className="text-sm font-semibold text-slate-900">Content Memory</p>
                <p className="mt-1 text-sm text-slate-500">Inspect the historical content memories accumulated for this account.</p>
              </Link>
              <Link href={`/accounts/${accountId}/style-profile`} className="rounded-2xl border border-slate-200 p-4 transition hover:border-brand-200 hover:bg-brand-50/60">
                <p className="text-sm font-semibold text-slate-900">Style Profile</p>
                <p className="mt-1 text-sm text-slate-500">Review tone, structure, lexical features and banned patterns.</p>
              </Link>
              <Link href={`/settings/wechat/${accountId}`} className="rounded-2xl border border-slate-200 p-4 transition hover:border-brand-200 hover:bg-brand-50/60">
                <p className="text-sm font-semibold text-slate-900">WeChat Config</p>
                <p className="mt-1 text-sm text-slate-500">Configure credentials, test connectivity and maintain default publish information.</p>
              </Link>
            </div>
          </Card>

          <Card
            title={locale === "zh-CN" ? "兼容旧实例动作" : "Legacy Runtime Action"}
            description={
              locale === "zh-CN"
                ? "账号直跑先封存在这里，给旧流程、旧联调和应急场景使用。主路径已经切到“新建任务”。"
                : "Direct account run is archived here for older flows, older integrations, and emergency use. The main path now starts from New Task."
            }
          >
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <p className="text-sm leading-6 text-slate-600">
                {locale === "zh-CN"
                  ? "如果只是正常运营这个账号，不应该再从这里直接跑系统。"
                  : "For normal account operations, you should not start the system from here anymore."}
              </p>
              <Button data-testid="account-detail-run-button" variant="secondary" onClick={() => void runNow()}>
                <Icon name="play" className="h-4 w-4" />
                {locale === "zh-CN" ? "兼容直跑（旧实例）" : "Legacy Quick Run"}
              </Button>
            </div>
          </Card>
        </>
      ) : null}

      <ConfirmDialog
        open={confirmDisable}
        title="Disable Account"
        description="This will pause scheduler activity for the account. Existing tasks are not deleted, but new scheduled runs will stop."
        confirmLabel="Disable Account"
        tone="danger"
        onCancel={() => setConfirmDisable(false)}
        onConfirm={() => void toggleActive(false)}
      />
    </div>
  );
}
