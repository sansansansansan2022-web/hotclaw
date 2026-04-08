"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getAccount, getApiOriginDebugInfo, getPendingDraftCount, getWeChatConfig, listAccountTasks, listDrafts, runAccount } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { formatDateTime, formatDuration, formatNumber, truncate } from "@/lib/utils";
import type { AccountDetail, DraftSummary, TaskSummary, WeChatConfigDetail } from "@/types";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  SkeletonRows,
  StatCard,
  Table,
} from "@/components/console/ui";
import { Icon } from "@/components/console/icons";
import { useAppStore } from "@/store/appStore";

function taskTone(status: string | null): "success" | "warning" | "danger" | "muted" {
  if (status === "completed") return "success";
  if (status === "running") return "warning";
  if (status === "failed") return "danger";
  return "muted";
}

function draftTone(status: string): "brand" | "success" | "warning" | "danger" | "muted" {
  if (status === "approved" || status === "published") return "success";
  if (status === "pending_review") return "warning";
  if (status === "rejected" || status === "discarded") return "danger";
  return "muted";
}

function referenceSyncTone(status: string | null): "success" | "warning" | "danger" | "muted" {
  if (status === "synced" || status === "manual_only") return "success";
  if (status === "failed") return "danger";
  if (status === "pending") return "warning";
  return "muted";
}

function getAutomationPlan(account: AccountDetail) {
  return (
    account.automation_plan_summary ?? {
      id: null,
      account_id: account.account_id,
      config_source: "legacy_fallback" as const,
      plan_type: account.operation_mode,
      is_enabled: account.auto_run_enabled,
      run_strategy:
        account.operation_mode === "manual"
          ? "manual_only"
          : account.posting_frequency
            ? "hybrid"
            : "manual_only",
      schedule_type: account.posting_frequency === "daily" ? "daily" : account.posting_frequency ? "weekly" : "none",
      schedule_config: account.posting_time ? { time: account.posting_time } : null,
      schedule_summary: account.posting_frequency
        ? `${account.posting_frequency}${account.posting_time ? ` @ ${account.posting_time}` : ""}`
        : "Manual only",
      auto_publish_enabled: account.auto_publish_enabled,
      publish_review_required: !account.auto_publish_enabled,
      max_posts_per_day: account.max_posts_per_day,
      min_interval_minutes: account.min_interval_minutes,
      timezone: "Asia/Shanghai",
      next_run_at: account.next_run_at,
      last_run_at: account.last_run_at,
      notes: null,
      latest_status: account.last_run_status,
      is_active_plan: true,
      created_at: null,
      updated_at: null,
    }
  );
}

function getWeChatConnectionSummary(config: WeChatConfigDetail | null) {
  if (config && config.is_enabled && config.has_app_secret && config.test_status === "success") {
    return {
      connected: true,
      title: "WeChat Connected",
      description: config.test_message || "The real official account binding is ready for publishing.",
      tone: "success" as const,
    };
  }

  return {
    connected: false,
    title: "Content-only Mode",
    description:
      config?.test_message ||
      "The account can run topics and drafts, but real official-account publishing stays disabled until WeChat connection succeeds.",
    tone: "warning" as const,
  };
}

interface AccountWorkspaceState {
  account: AccountDetail;
  wechatConfig: WeChatConfigDetail | null;
  tasks: TaskSummary[];
  drafts: DraftSummary[];
  pendingReviewCount: number;
  filteredOutTaskCount: number;
  filteredOutDraftCount: number;
}

export function AccountWorkspacePage({ accountId }: { accountId: string }) {
  const { operationModeLabel, taskStatusLabel, draftStatusLabel, publishStatusLabel } = useI18n();
  const router = useRouter();
  const searchParams = useSearchParams();
  const pushToast = useAppStore((state) => state.pushToast);
  const [data, setData] = useState<AccountWorkspaceState | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const onboardingSource = searchParams.get("source");
  const showOnboardingChecklist = searchParams.get("onboarding") === "1";
  const seededSourceCount = Number(searchParams.get("seeded_sources") || "0");
  const seedFailureCount = Number(searchParams.get("seed_failures") || "0");
  const automationSeeded = searchParams.get("automation_seeded") === "1";
  const seededPlanType = searchParams.get("plan_type");
  const wechatConnectedParam = searchParams.get("wechat_connected");
  const wechatTestFailed = searchParams.get("wechat_test_failed") === "1";

  const load = async () => {
    try {
      setLoading(true);
      setError(null);

      const [account, tasksRes, draftsRes, pendingRes, wechatConfig] = await Promise.all([
        getAccount(accountId),
        listAccountTasks(accountId, 1, 8),
        listDrafts(1, 8, { account_id: accountId }),
        getPendingDraftCount(accountId).catch(() => ({ count: 0 })),
        getWeChatConfig(accountId).catch(() => null),
      ]);

      const scopedTasks = tasksRes.tasks.filter((task) => task.account_id === accountId);
      const filteredOutTaskCount = tasksRes.tasks.length - scopedTasks.length;
      const scopedDrafts = draftsRes.drafts.filter((draft) => draft.account_id === accountId);
      const filteredOutDraftCount = draftsRes.drafts.length - scopedDrafts.length;

      if (process.env.NODE_ENV !== "production" && typeof window !== "undefined") {
        const apiInfo = getApiOriginDebugInfo();
        console.info("[HotClaw][account-workspace] load", {
          accountId,
          apiOrigin: apiInfo.origin || "/api",
          apiSource: apiInfo.source,
          taskCount: scopedTasks.length,
          draftCount: scopedDrafts.length,
          filteredOutTaskCount,
          filteredOutDraftCount,
        });

        if (filteredOutTaskCount || filteredOutDraftCount) {
          console.warn("[HotClaw][account-workspace] filtered cross-account records", {
            accountId,
            filteredOutTaskCount,
            filteredOutDraftCount,
          });
        }
      }

      setData({
        account,
        wechatConfig,
        tasks: scopedTasks,
        drafts: scopedDrafts,
        pendingReviewCount: pendingRes.count,
        filteredOutTaskCount,
        filteredOutDraftCount,
      });
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load account workspace.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [accountId]);

  const runNow = async () => {
    try {
      setRunning(true);

      if (process.env.NODE_ENV !== "production" && typeof window !== "undefined") {
        console.info("[HotClaw][account-workspace] run-click", { accountId });
      }

      const created = await runAccount(accountId);
      pushToast({
        tone: "success",
        title: "Account run queued",
        message: `Task ${created.task_id} started in this account workspace.`,
      });
      router.push(`/task/${created.task_id}`);
    } catch (runError) {
      pushToast({
        tone: "danger",
        title: "Run failed",
        message: runError instanceof Error ? runError.message : "Unexpected error.",
      });
    } finally {
      setRunning(false);
    }
  };

  const pendingDrafts = useMemo(
    () => (data?.drafts ?? []).filter((draft) => draft.draft_status === "pending_review").slice(0, 6),
    [data],
  );

  const automationPlan = useMemo(() => (data ? getAutomationPlan(data.account) : null), [data]);
  const latestOps = data?.account.latest_ops_context ?? null;
  const latestRunStrategy = latestOps?.run_strategy ?? null;
  const latestEffectiveMode = data?.account.latest_effective_mode ?? latestRunStrategy?.effective_mode ?? null;
  const latestOpsDegraded =
    data?.account.latest_ops_degraded ??
    Boolean(
      automationPlan?.plan_type &&
        latestEffectiveMode &&
        automationPlan.plan_type !== latestEffectiveMode,
    );
  const wechatConnection = getWeChatConnectionSummary(data?.wechatConfig ?? null);

  const onboardingTasks = useMemo(
    () => [
      {
        title: onboardingSource === "existing" ? "Review the inferred account profile" : "Add a few reference sources",
        description:
          onboardingSource === "existing"
            ? seededSourceCount > 0
              ? `The onboarding flow already created ${seededSourceCount} initial reference source(s). Review them before your next runs.`
              : "Check whether the inferred positioning, audience and tone match the real account before your next runs."
            : "Reference accounts and source material can stay lightweight now, but adding a few strong examples improves the first runs.",
      },
      {
        title: "Generate or refine the style profile",
        description: "Use the account assets to lock in tone, structure and banned patterns after the first onboarding pass.",
      },
      {
        title: automationSeeded ? "Review the initial automation plan" : "Adjust the automation posture",
        description: automationSeeded
          ? `This account already has an initial ${seededPlanType || "manual"} automation plan. Review cadence, enablement and publish safeguards before turning on more automation.`
          : "Operation mode, cadence and publish safeguards still use safe defaults. Tune them after you see the first outputs.",
      },
      {
        title: "Run the first content cycle",
        description: "Kick off one account-scoped run from this workspace to validate topics, draft quality and downstream publishing paths.",
      },
    ],
    [onboardingSource, seededSourceCount],
  );

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Account Workspace"
        title={data?.account.name || "Account Workspace"}
        description="Run this account, inspect this account's tasks and drafts, and keep the whole operator path anchored to the current account."
        actions={
          <>
            <Link href={`/accounts/${accountId}`}>
              <Button variant="secondary">Back to Account</Button>
            </Link>
            <Button onClick={() => void runNow()} disabled={running}>
              <Icon name="play" className="h-4 w-4" />
              {running ? "Running..." : "Run Now"}
            </Button>
          </>
        }
      />

      {loading ? (
        <SkeletonRows rows={6} />
      ) : error ? (
        <ErrorState title="Account workspace failed to load" description={error} retry={() => void load()} />
      ) : data ? (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">Current Account Workspace</Badge>
            <Badge tone="muted">{data.account.name}</Badge>
            <Badge tone="muted">{accountId}</Badge>
            <Badge tone={wechatConnection.tone}>{wechatConnection.title}</Badge>
          </div>

          {showOnboardingChecklist ? (
            <Card
              title="Onboarding Checklist"
              description={
                onboardingSource === "existing"
                  ? seedFailureCount > 0
                    ? `This account came in through the existing-account onboarding flow. ${seedFailureCount} initial reference source(s) failed to save, so review the source list before you continue.`
                    : "This account came in through the existing-account onboarding flow. Use this checklist to turn the inferred profile into a reliable operator setup."
                  : "This account came in through the new-account onboarding flow. These are the next low-friction steps before you automate more of the workflow."
              }
              action={
                <Link href={`/accounts/${accountId}/automation`}>
                  <Button variant="secondary" size="sm">
                    Review Automation Plan
                  </Button>
                </Link>
              }
            >
              <div className="grid gap-4 md:grid-cols-2">
                {onboardingTasks.map((item, index) => (
                  <div key={item.title} className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                    <div className="flex items-center gap-3">
                      <Badge tone="brand">{index + 1}</Badge>
                      <p className="text-sm font-semibold text-slate-900">{item.title}</p>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{item.description}</p>
                  </div>
                ))}
              </div>
              <div className="mt-4 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={wechatConnection.tone}>
                    {wechatConnectedParam === "1" && wechatConnection.connected ? "Official Account Connected" : "Official Account Pending"}
                  </Badge>
                  {data.wechatConfig?.app_id_masked ? <Badge tone="muted">{data.wechatConfig.app_id_masked}</Badge> : null}
                </div>
                <p className="mt-3 leading-6">
                  {wechatTestFailed
                    ? "The WeChat credential test did not pass during onboarding. The account still entered the workspace in content-only mode."
                    : wechatConnection.description}
                </p>
                <div className="mt-3">
                  <Link href={`/settings/wechat/${accountId}`}>
                    <Button variant="secondary" size="sm">
                      Review WeChat Config
                    </Button>
                  </Link>
                </div>
              </div>
            </Card>
          ) : null}

          {data.filteredOutTaskCount || data.filteredOutDraftCount ? (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              {`Filtered out records that do not belong to this account: ${data.filteredOutTaskCount} task(s), ${data.filteredOutDraftCount} draft(s).`}
            </div>
          ) : null}

          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-6">
            <StatCard
              label="Active Plan"
              value={operationModeLabel(automationPlan?.plan_type ?? data.account.operation_mode)}
              hint={automationPlan?.schedule_summary || "Manual only"}
              tone="brand"
              icon={<Icon name="workspace" className="h-6 w-6" />}
            />
            <StatCard
              label="Account Tasks"
              value={formatNumber(data.tasks.length)}
              hint="Counts only tasks returned for this account"
              tone="info"
              icon={<Icon name="history" className="h-6 w-6" />}
            />
            <StatCard
              label="Pending Review"
              value={formatNumber(data.pendingReviewCount)}
              hint="Only drafts awaiting action for this account"
              tone="warning"
              icon={<Icon name="drafts" className="h-6 w-6" />}
            />
            <StatCard
              label="Reference Sources"
              value={formatNumber(data.account.reference_source_count ?? 0)}
              hint={`Enabled ${formatNumber(data.account.reference_source_enabled_count ?? 0)} · Latest ${data.account.reference_source_last_sync_status ?? "none"}`}
              tone={referenceSyncTone(data.account.reference_source_last_sync_status)}
              icon={<Icon name="settings" className="h-6 w-6" />}
            />
            <StatCard
              label="Last Effective Mode"
              value={latestEffectiveMode ?? operationModeLabel(automationPlan?.plan_type ?? data.account.operation_mode)}
              hint={
                latestOpsDegraded
                  ? `Downgraded from ${automationPlan?.plan_type ?? data.account.operation_mode} on the latest run`
                  : data.account.last_error_message || "Latest runtime posture for this account"
              }
              tone={latestOpsDegraded ? "warning" : taskTone(data.account.last_run_status)}
              icon={<Icon name="dashboard" className="h-6 w-6" />}
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
              title="Account Context"
              description="Keep the account identity and positioning visible so this page cannot be mistaken for a global task center."
            >
              <div className="space-y-5">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Account Identity</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Badge tone="brand">{data.account.name}</Badge>
                    <Badge tone="muted">{accountId}</Badge>
                  </div>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Positioning</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-slate-600">{data.account.positioning}</p>
                </div>
                <div className="grid gap-5 md:grid-cols-2">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Audience</p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{data.account.audience || "Not set"}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Tone & Style</p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{data.account.tone_style || "Not set"}</p>
                  </div>
                </div>
                <div className="grid gap-5 md:grid-cols-2">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Cadence</p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">
                      {automationPlan?.schedule_summary || "Manual only"}
                    </p>
                  </div>
                    <div>
                      <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Automation Flags</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        <Badge tone={data.account.is_active ? "success" : "muted"}>{data.account.is_active ? "Account Active" : "Account Paused"}</Badge>
                        <Badge tone={automationPlan?.is_enabled ? "success" : "muted"}>{automationPlan?.is_enabled ? "Plan Enabled" : "Plan Disabled"}</Badge>
                      <Badge tone={automationPlan?.auto_publish_enabled ? "success" : "muted"}>
                        {automationPlan?.auto_publish_enabled ? "Auto-publish" : "Manual Publish"}
                      </Badge>
                        <Badge tone={automationPlan?.publish_review_required ? "warning" : "success"}>
                          {automationPlan?.publish_review_required ? "Review Required" : "Publish Without Review"}
                        </Badge>
                        <Badge tone={wechatConnection.tone}>{wechatConnection.title}</Badge>
                      </div>
                    </div>
                  </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3 text-sm text-slate-600">
                  <p className="font-medium text-slate-900">Official Account Status</p>
                  <p className="mt-2 leading-6">{wechatConnection.description}</p>
                  <div className="mt-3">
                    <Link href={`/settings/wechat/${accountId}`}>
                      <Button variant="secondary" size="sm">
                        Open WeChat Config
                      </Button>
                    </Link>
                  </div>
                </div>
              </div>
            </Card>

            <Card
              title="Operations & Assets"
              description="Every link stays in the current account context instead of routing operators back through the global workspace."
            >
              <div className="grid gap-4 md:grid-cols-2">
                {[
                  {
                    href: `/accounts/${accountId}/automation`,
                    title: "Automation Plan",
                    desc: "Inspect the active plan type, schedule posture and publish safeguards for this account.",
                  },
                  {
                    href: `/accounts/${accountId}/reference-sources`,
                    title: "Reference Sources",
                    desc: "Manage the publications, URLs and pasted articles this account uses as trackable references.",
                  },
                  {
                    href: `/settings/wechat/${accountId}`,
                    title: "WeChat Config",
                    desc: wechatConnection.connected
                      ? "Review the connected AppID/AppSecret binding and the default publish fields for this account."
                      : "Complete the real official-account connection if you want this account to leave content-only mode.",
                  },
                  {
                    href: `/accounts/${accountId}/workspace`,
                    title: "Account Workspace",
                    desc: "Run tasks and inspect queues inside this account context.",
                  },
                  {
                    href: `/drafts?account_id=${accountId}`,
                    title: "Account Drafts",
                    desc: "Open review and publish drafts that belong to this account only.",
                  },
                  {
                    href: `/tasks/history?account_id=${accountId}`,
                    title: "Account Tasks",
                    desc: "View only task runs created for this account.",
                  },
                  {
                    href: "/publish-logs",
                    title: "Publish Logs",
                    desc: "Inspect publish attempts and failures linked to this account's drafts.",
                  },
                  {
                    href: `/accounts/${accountId}/memory`,
                    title: "Content Memory",
                    desc: "Review historical content memories accumulated for this account.",
                  },
                  {
                    href: `/accounts/${accountId}/style-profile`,
                    title: "Style Profile",
                    desc: "Inspect tone, structure and banned-pattern style assets.",
                  },
                ].map((item) => (
                  <Link key={item.href} href={item.href} className="rounded-2xl border border-slate-200 p-4 transition hover:border-brand-200 hover:bg-brand-50/60">
                    <p className="text-sm font-semibold text-slate-900">{item.title}</p>
                    <p className="mt-1 text-sm leading-6 text-slate-500">{item.desc}</p>
                  </Link>
                ))}
              </div>
            </Card>
          </div>

          {latestRunStrategy ? (
            <Card
              title="Latest Ops Judgment"
              description="This is the most recent pre-run operations decision recorded for the account."
              action={
                <Link href={`/accounts/${accountId}/automation`}>
                  <Button variant="secondary" size="sm">
                    Review Automation Plan
                  </Button>
                </Link>
              }
            >
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-2xl border border-slate-200 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Allow Run</p>
                  <div className="mt-2">
                    <Badge tone={latestRunStrategy.allow_run ? "success" : "danger"}>
                      {latestRunStrategy.allow_run ? "Allowed" : "Blocked"}
                    </Badge>
                  </div>
                </div>
                <div className="rounded-2xl border border-slate-200 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Effective Mode</p>
                  <p className="mt-2 text-sm font-semibold text-slate-900">{latestEffectiveMode ?? "Not recorded"}</p>
                  {latestOpsDegraded ? (
                    <p className="mt-1 text-xs text-amber-700">{`Downgraded from ${automationPlan?.plan_type ?? data.account.operation_mode}`}</p>
                  ) : null}
                </div>
                <div className="rounded-2xl border border-slate-200 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Auto Publish</p>
                  <div className="mt-2">
                    <Badge tone={latestRunStrategy.allow_auto_publish ? "success" : "warning"}>
                      {latestRunStrategy.allow_auto_publish ? "Allowed" : "Review First"}
                    </Badge>
                  </div>
                </div>
                <div className="rounded-2xl border border-slate-200 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Health</p>
                  <div className="mt-2">
                    <Badge tone={latestOps?.account_health?.status === "ready" ? "success" : latestOps?.account_health?.status === "risk_recovery" ? "danger" : "warning"}>
                      {latestOps?.account_health?.status ?? "attention"}
                    </Badge>
                  </div>
                </div>
              </div>

              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <div className="rounded-2xl border border-slate-200 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Ops Notes</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {(latestOps?.ops_notes ?? []).length ? (
                      latestOps?.ops_notes?.map((note) => (
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
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Preferred Sources</p>
                    <p className="mt-2 font-semibold text-slate-900">{latestRunStrategy.preferred_reference_source_ids.length}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 p-4 text-sm text-slate-600">
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Avoided Topics</p>
                    <p className="mt-2 font-semibold text-slate-900">{latestRunStrategy.avoid_recent_topics.length}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 p-4 text-sm text-slate-600 sm:col-span-2">
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Preferred Content Lane</p>
                    <p className="mt-2 font-semibold text-slate-900">{latestRunStrategy.preferred_content_lane || "Not specified"}</p>
                  </div>
                </div>
              </div>
            </Card>
          ) : null}

          <Card
            title="This Account's Tasks"
            description="Only task runs belonging to this account are rendered here. Any cross-account records are filtered out."
          >
            {data.tasks.length ? (
              <Table columns={["Task", "Status", "Created", "Duration", "Action"]}>
                {data.tasks.map((task) => (
                  <tr key={task.task_id}>
                    <td className="px-5 py-4">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{task.task_id}</p>
                        <div className="mt-1 flex flex-wrap gap-2">
                          <Badge tone="brand">Account Task</Badge>
                          <Badge tone="muted">{task.account_name || accountId}</Badge>
                        </div>
                        <p className="mt-2 text-sm text-slate-500">{truncate(task.positioning_summary, 100)}</p>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <Badge tone={taskTone(task.status)}>{taskStatusLabel(task.status)}</Badge>
                    </td>
                    <td className="px-5 py-4 text-sm text-slate-600">{formatDateTime(task.created_at)}</td>
                    <td className="px-5 py-4 text-sm text-slate-600">{formatDuration(task.elapsed_seconds)}</td>
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
                title="No account tasks yet"
                description="Start this account from here and its task history will accumulate in this workspace."
              />
            )}
          </Card>

          <Card
            title="Pending Review Drafts"
            description="Only drafts belonging to this account and still needing operator action appear here."
          >
            {pendingDrafts.length ? (
              <Table columns={["Title", "Draft Status", "Publish Status", "Updated", "Action"]}>
                {pendingDrafts.map((draft) => (
                  <tr key={draft.id}>
                    <td className="px-5 py-4">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{draft.title}</p>
                        <div className="mt-1 flex flex-wrap gap-2">
                          <Badge tone="brand">Account Draft</Badge>
                          <Badge tone="muted">{accountId}</Badge>
                        </div>
                        <p className="mt-2 text-sm text-slate-500">{truncate(draft.selected_topic, 100) || "No selected topic snapshot"}</p>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <Badge tone={draftTone(draft.draft_status)}>{draftStatusLabel(draft.draft_status)}</Badge>
                    </td>
                    <td className="px-5 py-4">
                      <Badge tone={draftTone(draft.publish_status)}>{publishStatusLabel(draft.publish_status)}</Badge>
                    </td>
                    <td className="px-5 py-4 text-sm text-slate-600">{formatDateTime(draft.updated_at)}</td>
                    <td className="px-5 py-4">
                      <Link href={`/drafts/${draft.id}`}>
                        <Button variant="secondary" size="sm">
                          Open Draft
                        </Button>
                      </Link>
                    </td>
                  </tr>
                ))}
              </Table>
            ) : (
              <EmptyState
                title="No pending review drafts"
                description="This account has no pending review drafts right now. You can still open the account draft center for the full list."
                action={
                  <Link href={`/drafts?account_id=${accountId}`}>
                    <Button>Open Account Drafts</Button>
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
