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

function getAutomationPlan(
  account: AccountDetail,
  locale: "en" | "zh-CN",
  token: (value?: string | null) => string,
) {
  const scheduleSummary = account.posting_frequency
    ? account.posting_time
      ? locale === "zh-CN"
        ? `${token(account.posting_frequency)} ${account.posting_time}`
        : `${token(account.posting_frequency)} @ ${account.posting_time}`
      : token(account.posting_frequency)
    : locale === "zh-CN"
      ? "仅手动"
      : "Manual only";

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
      schedule_summary: scheduleSummary,
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

function getWeChatConnectionSummary(config: WeChatConfigDetail | null, locale: "en" | "zh-CN") {
  if (config && config.is_enabled && config.has_app_secret && config.test_status === "success") {
    return {
      connected: true,
      title: locale === "zh-CN" ? "微信已连接" : "WeChat Connected",
      description:
        config.test_message ||
        (locale === "zh-CN"
          ? "真实公众号绑定已经就绪，可以进入发布链路。"
          : "The real official account binding is ready for publishing."),
      tone: "success" as const,
    };
  }

  return {
    connected: false,
    title: locale === "zh-CN" ? "仅内容模式" : "Content-only Mode",
    description:
      config?.test_message ||
      (locale === "zh-CN"
        ? "这个账号可以继续跑选题和草稿，但在微信连接成功前，真实公众号发布仍会保持关闭。"
        : "The account can run topics and drafts, but real official-account publishing stays disabled until WeChat connection succeeds."),
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
  const { locale, operationModeLabel, taskStatusLabel, draftStatusLabel, publishStatusLabel, token } = useI18n();
  const router = useRouter();
  const searchParams = useSearchParams();
  const pushToast = useAppStore((state) => state.pushToast);
  const [data, setData] = useState<AccountWorkspaceState | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const onboardingSource = searchParams.get("source");
  const showOnboardingChecklist = searchParams.get("onboarding") === "1";
  const seededSourceCount = Number(searchParams.get("seeded_sources") || "0");
  const seedFailureCount = Number(searchParams.get("seed_failures") || "0");
  const automationSeeded = searchParams.get("automation_seeded") === "1";
  const seededPlanType = searchParams.get("plan_type");
  const wechatConnectedParam = searchParams.get("wechat_connected");
  const wechatTestFailed = searchParams.get("wechat_test_failed") === "1";
  const copy = locale === "zh-CN"
    ? {
        unexpectedError: "发生了意外错误。",
        loadError: "无法加载账号工作台。",
        runQueuedTitle: "账号运行已排队",
        runQueuedMessage: (taskId: string) => `任务 ${taskId} 已在这个账号工作台里启动。`,
        runFailedTitle: "运行失败",
        pageEyebrow: "账号工作台",
        pageTitle: "账号工作台",
        pageDescription: "在当前账号上下文里发起运行、查看该账号的任务和草稿，并把整条运营链路固定在这个账号上。",
        backToAccount: "返回账号",
        runNow: "立即运行",
        running: "运行中...",
        loadFailedTitle: "账号工作台加载失败",
        currentWorkspace: "当前账号工作台",
        onboardingChecklist: "接入清单",
        reviewAutomationPlan: "检查自动化计划",
        officialConnected: "公众号已连接",
        officialPending: "公众号待完成",
        onboardingWechatFailed: "接入时微信凭证测试没有通过。账号仍然会以仅内容模式进入工作台。",
        reviewWechatConfig: "检查微信配置",
        filteredOutRecords: (tasks: number, drafts: number) => `已过滤掉不属于这个账号的记录：${tasks} 条任务，${drafts} 条草稿。`,
        activePlan: "当前计划",
        accountTasks: "账号任务",
        accountTasksHint: "只统计属于这个账号的任务",
        pendingReview: "待审核",
        pendingReviewHint: "只统计这个账号仍需处理的草稿",
        referenceSources: "参考源",
        referenceHint: (enabled: string, latest: string) => `已启用 ${enabled} · 最近 ${latest}`,
        lastEffectiveMode: "最近生效模式",
        latestRuntimePosture: "这个账号最近一次运行时采用的姿态",
        downgradedFrom: (mode: string) => `最近一次运行已从 ${mode} 降级`,
        officialAccount: "公众号状态",
        connected: "已连接",
        contentOnly: "仅内容模式",
        accountContext: "账号上下文",
        accountContextDesc: "把账号身份和定位固定显示在这里，避免把这个页面误当成全局任务中心。",
        accountIdentity: "账号身份",
        positioning: "定位",
        audience: "受众",
        toneStyle: "语气与风格",
        cadence: "节奏",
        automationFlags: "自动化标记",
        notSet: "未设置",
        manualOnly: "仅手动",
        accountActive: "账号已启用",
        accountPaused: "账号已暂停",
        planEnabled: "计划已启用",
        planDisabled: "计划已关闭",
        autoPublish: "自动发布",
        manualPublish: "人工发布",
        reviewRequired: "需要审核",
        publishWithoutReview: "无需审核即可发布",
        officialAccountStatus: "公众号状态",
        openWechatConfig: "打开微信配置",
        operationsAssets: "操作入口与资产",
        operationsAssetsDesc: "所有链接都保持在当前账号上下文里，不会把运营人员重新带回全局工作台。",
        automationPlan: "自动化计划",
        automationPlanDesc: "查看这个账号当前生效的计划类型、调度姿态和发布保护。",
        referenceSourcesDesc: "管理这个账号追踪的公众号、URL 和粘贴文章参考源。",
        wechatConfig: "微信配置",
        wechatConfigConnectedDesc: "检查这个账号已连接的 AppID/AppSecret 绑定和默认发布字段。",
        wechatConfigPendingDesc: "如果想让这个账号离开仅内容模式，就在这里完成真实公众号连接。",
        workspace: "账号工作台",
        workspaceDesc: "在这个账号上下文里发起任务并查看队列。",
        drafts: "账号草稿",
        draftsDesc: "打开仅属于这个账号的审核和发布草稿。",
        tasks: "账号任务",
        tasksLinkDesc: "只查看为这个账号创建的任务运行记录。",
        publishLogs: "发布日志",
        publishLogsDesc: "查看和这个账号草稿相关的发布尝试与失败。",
        contentMemory: "内容记忆",
        contentMemoryDesc: "回看这个账号已经积累下来的历史内容记忆。",
        styleProfile: "风格画像",
        styleProfileDesc: "查看语气、结构和禁用表达等风格资产。",
        latestOpsTitle: "最近一次运营判断",
        latestOpsDesc: "这里展示的是这个账号最近一次运行前记录下来的运营决策。",
        allowRun: "允许运行",
        allowed: "允许",
        blocked: "阻止",
        effectiveMode: "实际模式",
        notRecorded: "未记录",
        autoPublishTitle: "自动发布",
        reviewFirst: "先审核",
        health: "健康状态",
        opsNotes: "运营备注",
        noOpsNotes: "还没有运营备注。",
        preferredSources: "偏好来源",
        avoidedTopics: "规避主题",
        preferredContentLane: "偏好内容路径",
        notSpecified: "未指定",
        tasksTitle: "这个账号的任务",
        tasksDesc: "这里只展示属于这个账号的任务运行记录。跨账号的数据会被过滤掉。",
        taskColumn: "任务",
        statusColumn: "状态",
        createdColumn: "创建时间",
        durationColumn: "耗时",
        actionColumn: "操作",
        accountTaskBadge: "账号任务",
        inspect: "查看",
        noTasksTitle: "这个账号还没有任务",
        noTasksDesc: "从这里发起一次运行后，这个工作台里就会开始累积任务历史。",
        pendingDraftsTitle: "待审核草稿",
        pendingDraftsDesc: "这里只会显示属于这个账号、并且仍需人工处理的草稿。",
        titleColumn: "标题",
        draftStatusColumn: "草稿状态",
        publishStatusColumn: "发布状态",
        updatedColumn: "更新时间",
        accountDraftBadge: "账号草稿",
        noTopicSnapshot: "暂无选题快照",
        openDraft: "打开草稿",
        noPendingDraftsTitle: "没有待审核草稿",
        noPendingDraftsDesc: "这个账号当前没有待审核草稿。你仍然可以打开账号草稿中心查看完整列表。",
        openAccountDrafts: "打开账号草稿",
      }
    : {
        unexpectedError: "Unexpected error.",
        loadError: "Unable to load account workspace.",
        runQueuedTitle: "Account run queued",
        runQueuedMessage: (taskId: string) => `Task ${taskId} started in this account workspace.`,
        runFailedTitle: "Run failed",
        pageEyebrow: "Account Workspace",
        pageTitle: "Account Workspace",
        pageDescription: "Run this account, inspect this account's tasks and drafts, and keep the whole operator path anchored to the current account.",
        backToAccount: "Back to Account",
        runNow: "Run Now",
        running: "Running...",
        loadFailedTitle: "Account workspace failed to load",
        currentWorkspace: "Current Account Workspace",
        onboardingChecklist: "Onboarding Checklist",
        reviewAutomationPlan: "Review Automation Plan",
        officialConnected: "Official Account Connected",
        officialPending: "Official Account Pending",
        onboardingWechatFailed: "The WeChat credential test did not pass during onboarding. The account still entered the workspace in content-only mode.",
        reviewWechatConfig: "Review WeChat Config",
        filteredOutRecords: (tasks: number, drafts: number) => `Filtered out records that do not belong to this account: ${tasks} task(s), ${drafts} draft(s).`,
        activePlan: "Active Plan",
        accountTasks: "Account Tasks",
        accountTasksHint: "Counts only tasks returned for this account",
        pendingReview: "Pending Review",
        pendingReviewHint: "Only drafts awaiting action for this account",
        referenceSources: "Reference Sources",
        referenceHint: (enabled: string, latest: string) => `Enabled ${enabled} · Latest ${latest}`,
        lastEffectiveMode: "Last Effective Mode",
        latestRuntimePosture: "Latest runtime posture for this account",
        downgradedFrom: (mode: string) => `Downgraded from ${mode} on the latest run`,
        officialAccount: "Official Account",
        connected: "Connected",
        contentOnly: "Content-only",
        accountContext: "Account Context",
        accountContextDesc: "Keep the account identity and positioning visible so this page cannot be mistaken for a global task center.",
        accountIdentity: "Account Identity",
        positioning: "Positioning",
        audience: "Audience",
        toneStyle: "Tone & Style",
        cadence: "Cadence",
        automationFlags: "Automation Flags",
        notSet: "Not set",
        manualOnly: "Manual only",
        accountActive: "Account Active",
        accountPaused: "Account Paused",
        planEnabled: "Plan Enabled",
        planDisabled: "Plan Disabled",
        autoPublish: "Auto-publish",
        manualPublish: "Manual Publish",
        reviewRequired: "Review Required",
        publishWithoutReview: "Publish Without Review",
        officialAccountStatus: "Official Account Status",
        openWechatConfig: "Open WeChat Config",
        operationsAssets: "Operations & Assets",
        operationsAssetsDesc: "Every link stays in the current account context instead of routing operators back through the global workspace.",
        automationPlan: "Automation Plan",
        automationPlanDesc: "Inspect the active plan type, schedule posture and publish safeguards for this account.",
        referenceSourcesDesc: "Manage the publications, URLs and pasted articles this account uses as trackable references.",
        wechatConfig: "WeChat Config",
        wechatConfigConnectedDesc: "Review the connected AppID/AppSecret binding and the default publish fields for this account.",
        wechatConfigPendingDesc: "Complete the real official-account connection if you want this account to leave content-only mode.",
        workspace: "Account Workspace",
        workspaceDesc: "Run tasks and inspect queues inside this account context.",
        drafts: "Account Drafts",
        draftsDesc: "Open review and publish drafts that belong to this account only.",
        tasks: "Account Tasks",
        tasksLinkDesc: "View only task runs created for this account.",
        publishLogs: "Publish Logs",
        publishLogsDesc: "Inspect publish attempts and failures linked to this account's drafts.",
        contentMemory: "Content Memory",
        contentMemoryDesc: "Review historical content memories accumulated for this account.",
        styleProfile: "Style Profile",
        styleProfileDesc: "Inspect tone, structure and banned-pattern style assets.",
        latestOpsTitle: "Latest Ops Judgment",
        latestOpsDesc: "This is the most recent pre-run operations decision recorded for the account.",
        allowRun: "Allow Run",
        allowed: "Allowed",
        blocked: "Blocked",
        effectiveMode: "Effective Mode",
        notRecorded: "Not recorded",
        autoPublishTitle: "Auto Publish",
        reviewFirst: "Review First",
        health: "Health",
        opsNotes: "Ops Notes",
        noOpsNotes: "No ops notes recorded.",
        preferredSources: "Preferred Sources",
        avoidedTopics: "Avoided Topics",
        preferredContentLane: "Preferred Content Lane",
        notSpecified: "Not specified",
        tasksTitle: "This Account's Tasks",
        tasksDesc: "Only task runs belonging to this account are rendered here. Any cross-account records are filtered out.",
        taskColumn: "Task",
        statusColumn: "Status",
        createdColumn: "Created",
        durationColumn: "Duration",
        actionColumn: "Action",
        accountTaskBadge: "Account Task",
        inspect: "Inspect",
        noTasksTitle: "No account tasks yet",
        noTasksDesc: "Start this account from here and its task history will accumulate in this workspace.",
        pendingDraftsTitle: "Pending Review Drafts",
        pendingDraftsDesc: "Only drafts belonging to this account and still needing operator action appear here.",
        titleColumn: "Title",
        draftStatusColumn: "Draft Status",
        publishStatusColumn: "Publish Status",
        updatedColumn: "Updated",
        accountDraftBadge: "Account Draft",
        noTopicSnapshot: "No selected topic snapshot",
        openDraft: "Open Draft",
        noPendingDraftsTitle: "No pending review drafts",
        noPendingDraftsDesc: "This account has no pending review drafts right now. You can still open the account draft center for the full list.",
        openAccountDrafts: "Open Account Drafts",
      };

  useEffect(() => {
    let active = true;

    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        setData(null);

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

        if (!active) {
          return;
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
        if (!active) {
          return;
        }

        setError(loadError instanceof Error ? loadError.message : copy.loadError);
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    void load();

    return () => {
      active = false;
    };
  }, [accountId, copy.loadError, reloadKey]);

  const workspaceData = data?.account.account_id === accountId ? data : null;

  const runNow = async () => {
    if (!workspaceData) {
      return;
    }

    try {
      setRunning(true);

      if (process.env.NODE_ENV !== "production" && typeof window !== "undefined") {
        console.info("[HotClaw][account-workspace] run-click", { accountId });
      }

      const created = await runAccount(accountId);
      pushToast({
        tone: "success",
        title: copy.runQueuedTitle,
        message: copy.runQueuedMessage(created.task_id),
      });
      router.push(`/task/${created.task_id}`);
    } catch (runError) {
      pushToast({
        tone: "danger",
        title: copy.runFailedTitle,
        message: runError instanceof Error ? runError.message : copy.unexpectedError,
      });
    } finally {
      setRunning(false);
    }
  };

  const pendingDrafts = useMemo(
    () => (workspaceData?.drafts ?? []).filter((draft) => draft.draft_status === "pending_review").slice(0, 6),
    [workspaceData],
  );

  const automationPlan = useMemo(
    () => (workspaceData ? getAutomationPlan(workspaceData.account, locale, token) : null),
    [workspaceData, locale, token],
  );
  const latestOps = workspaceData?.account.latest_ops_context ?? null;
  const latestRunStrategy = latestOps?.run_strategy ?? null;
  const latestEffectiveMode = workspaceData?.account.latest_effective_mode ?? latestRunStrategy?.effective_mode ?? null;
  const latestOpsDegraded =
    workspaceData?.account.latest_ops_degraded ??
    Boolean(
      automationPlan?.plan_type &&
        latestEffectiveMode &&
        automationPlan.plan_type !== latestEffectiveMode,
    );
  const wechatConnection = getWeChatConnectionSummary(workspaceData?.wechatConfig ?? null, locale);

  const onboardingTasks = useMemo(
    () => [
      {
        title:
          onboardingSource === "existing"
            ? locale === "zh-CN"
              ? "检查推断出的账号画像"
              : "Review the inferred account profile"
            : locale === "zh-CN"
              ? "补充几条参考源"
              : "Add a few reference sources",
        description:
          onboardingSource === "existing"
            ? seededSourceCount > 0
              ? locale === "zh-CN"
                ? `接入流程已经创建了 ${seededSourceCount} 条初始参考源，建议在下一次运行前先检查一遍。`
                : `The onboarding flow already created ${seededSourceCount} initial reference source(s). Review them before your next runs.`
              : locale === "zh-CN"
                ? "先确认推断出的定位、受众和语气是否和真实账号一致，再继续后续运行。"
                : "Check whether the inferred positioning, audience and tone match the real account before your next runs."
            : locale === "zh-CN"
              ? "参考账号和素材现在可以先保持轻量，但多补几条高质量样例会让前几次运行更稳。"
              : "Reference accounts and source material can stay lightweight now, but adding a few strong examples improves the first runs.",
      },
      {
        title: locale === "zh-CN" ? "生成或补齐风格画像" : "Generate or refine the style profile",
        description:
          locale === "zh-CN"
            ? "完成第一轮接入后，用账号资产把语气、结构和禁用表达固定下来。"
            : "Use the account assets to lock in tone, structure and banned patterns after the first onboarding pass.",
      },
      {
        title: automationSeeded
          ? locale === "zh-CN"
            ? "检查初始自动化计划"
            : "Review the initial automation plan"
          : locale === "zh-CN"
            ? "调整自动化姿态"
            : "Adjust the automation posture",
        description: automationSeeded
          ? locale === "zh-CN"
            ? `这个账号已经带着一份初始${operationModeLabel(seededPlanType || "manual")}计划进入工作台。建议先确认节奏、启用状态和发布保护，再继续提高自动化程度。`
            : `This account already has an initial ${seededPlanType || "manual"} automation plan. Review cadence, enablement and publish safeguards before turning on more automation.`
          : locale === "zh-CN"
            ? "当前的运行模式、节奏和发布保护仍是稳妥默认值，等看到第一批结果后再继续细调。"
            : "Operation mode, cadence and publish safeguards still use safe defaults. Tune them after you see the first outputs.",
      },
      {
        title: locale === "zh-CN" ? "跑通第一轮内容周期" : "Run the first content cycle",
        description:
          locale === "zh-CN"
            ? "在这个账号工作台里发起一次账号级运行，用来验证选题、草稿质量和后续发布链路。"
            : "Kick off one account-scoped run from this workspace to validate topics, draft quality and downstream publishing paths.",
      },
    ],
    [locale, onboardingSource, operationModeLabel, seededPlanType, seededSourceCount, automationSeeded],
  );

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={copy.pageEyebrow}
        title={workspaceData?.account.name || copy.pageTitle}
        description={copy.pageDescription}
        actions={
          <>
            <Link href={`/accounts/${accountId}`}>
              <Button variant="secondary">{copy.backToAccount}</Button>
            </Link>
            <Button onClick={() => void runNow()} disabled={running || !workspaceData}>
              <Icon name="play" className="h-4 w-4" />
              {running ? copy.running : copy.runNow}
            </Button>
          </>
        }
      />

      {loading ? (
        <SkeletonRows rows={6} />
      ) : error ? (
        <ErrorState title={copy.loadFailedTitle} description={error} retry={() => setReloadKey((value) => value + 1)} />
      ) : workspaceData ? (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">{copy.currentWorkspace}</Badge>
            <Badge tone="muted">{workspaceData.account.name}</Badge>
            <Badge tone="muted">{accountId}</Badge>
            <Badge tone={wechatConnection.tone}>{wechatConnection.title}</Badge>
          </div>

          {showOnboardingChecklist ? (
            <Card
              title={copy.onboardingChecklist}
              description={
                onboardingSource === "existing"
                  ? seedFailureCount > 0
                    ? locale === "zh-CN"
                      ? `这个账号是通过“已有账号接入”流程进入系统的，其中有 ${seedFailureCount} 条初始参考源保存失败，继续前建议先检查参考源列表。`
                      : `This account came in through the existing-account onboarding flow. ${seedFailureCount} initial reference source(s) failed to save, so review the source list before you continue.`
                    : locale === "zh-CN"
                      ? "这个账号是通过“已有账号接入”流程进入系统的。用这份清单把推断出的账号画像收敛成一套稳定可运行的配置。"
                      : "This account came in through the existing-account onboarding flow. Use this checklist to turn the inferred profile into a reliable operator setup."
                  : locale === "zh-CN"
                    ? "这个账号是通过“新账号接入”流程进入系统的。先完成这些低阻力步骤，再逐步提高自动化程度。"
                    : "This account came in through the new-account onboarding flow. These are the next low-friction steps before you automate more of the workflow."
              }
              action={
                <Link href={`/accounts/${accountId}/automation`}>
                  <Button variant="secondary" size="sm">
                    {copy.reviewAutomationPlan}
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
                    {wechatConnectedParam === "1" && wechatConnection.connected ? copy.officialConnected : copy.officialPending}
                  </Badge>
                  {workspaceData.wechatConfig?.app_id_masked ? <Badge tone="muted">{workspaceData.wechatConfig.app_id_masked}</Badge> : null}
                </div>
                <p className="mt-3 leading-6">
                  {wechatTestFailed
                    ? copy.onboardingWechatFailed
                    : wechatConnection.description}
                </p>
                <div className="mt-3">
                  <Link href={`/settings/wechat/${accountId}`}>
                    <Button variant="secondary" size="sm">
                      {copy.reviewWechatConfig}
                    </Button>
                  </Link>
                </div>
              </div>
            </Card>
          ) : null}

          {workspaceData.filteredOutTaskCount || workspaceData.filteredOutDraftCount ? (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              {copy.filteredOutRecords(workspaceData.filteredOutTaskCount, workspaceData.filteredOutDraftCount)}
            </div>
          ) : null}

          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-6">
            <StatCard
              label={copy.activePlan}
              value={operationModeLabel(automationPlan?.plan_type ?? workspaceData.account.operation_mode)}
              hint={automationPlan?.schedule_summary || copy.manualOnly}
              tone="brand"
              icon={<Icon name="workspace" className="h-6 w-6" />}
            />
            <StatCard
              label={copy.accountTasks}
              value={formatNumber(workspaceData.tasks.length)}
              hint={copy.accountTasksHint}
              tone="info"
              icon={<Icon name="history" className="h-6 w-6" />}
            />
            <StatCard
              label={copy.pendingReview}
              value={formatNumber(workspaceData.pendingReviewCount)}
              hint={copy.pendingReviewHint}
              tone="warning"
              icon={<Icon name="drafts" className="h-6 w-6" />}
            />
            <StatCard
              label={copy.referenceSources}
              value={formatNumber(workspaceData.account.reference_source_count ?? 0)}
              hint={copy.referenceHint(
                formatNumber(workspaceData.account.reference_source_enabled_count ?? 0),
                token(workspaceData.account.reference_source_last_sync_status ?? "none"),
              )}
              tone={referenceSyncTone(workspaceData.account.reference_source_last_sync_status)}
              icon={<Icon name="settings" className="h-6 w-6" />}
            />
            <StatCard
              label={copy.lastEffectiveMode}
              value={
                latestEffectiveMode
                  ? operationModeLabel(latestEffectiveMode)
                  : operationModeLabel(automationPlan?.plan_type ?? workspaceData.account.operation_mode)
              }
              hint={
                latestOpsDegraded
                  ? copy.downgradedFrom(operationModeLabel(automationPlan?.plan_type ?? workspaceData.account.operation_mode))
                  : workspaceData.account.last_error_message || copy.latestRuntimePosture
              }
              tone={latestOpsDegraded ? "warning" : taskTone(workspaceData.account.last_run_status)}
              icon={<Icon name="dashboard" className="h-6 w-6" />}
            />
            <StatCard
              label={copy.officialAccount}
              value={wechatConnection.connected ? copy.connected : copy.contentOnly}
              hint={wechatConnection.description}
              tone={wechatConnection.tone}
              icon={<Icon name="publish" className="h-6 w-6" />}
            />
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.1fr_0.95fr]">
            <Card title={copy.accountContext} description={copy.accountContextDesc}>
              <div className="space-y-5">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{copy.accountIdentity}</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Badge tone="brand">{workspaceData.account.name}</Badge>
                    <Badge tone="muted">{accountId}</Badge>
                  </div>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{copy.positioning}</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-slate-600">{workspaceData.account.positioning || copy.notSet}</p>
                </div>
                <div className="grid gap-5 md:grid-cols-2">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{copy.audience}</p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{workspaceData.account.audience || copy.notSet}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{copy.toneStyle}</p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{workspaceData.account.tone_style || copy.notSet}</p>
                  </div>
                </div>
                <div className="grid gap-5 md:grid-cols-2">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{copy.cadence}</p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">
                      {automationPlan?.schedule_summary || copy.manualOnly}
                    </p>
                  </div>
                    <div>
                      <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{copy.automationFlags}</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        <Badge tone={workspaceData.account.is_active ? "success" : "muted"}>{workspaceData.account.is_active ? copy.accountActive : copy.accountPaused}</Badge>
                        <Badge tone={automationPlan?.is_enabled ? "success" : "muted"}>{automationPlan?.is_enabled ? copy.planEnabled : copy.planDisabled}</Badge>
                      <Badge tone={automationPlan?.auto_publish_enabled ? "success" : "muted"}>
                        {automationPlan?.auto_publish_enabled ? copy.autoPublish : copy.manualPublish}
                      </Badge>
                        <Badge tone={automationPlan?.publish_review_required ? "warning" : "success"}>
                          {automationPlan?.publish_review_required ? copy.reviewRequired : copy.publishWithoutReview}
                        </Badge>
                        <Badge tone={wechatConnection.tone}>{wechatConnection.title}</Badge>
                      </div>
                    </div>
                  </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3 text-sm text-slate-600">
                  <p className="font-medium text-slate-900">{copy.officialAccountStatus}</p>
                  <p className="mt-2 leading-6">{wechatConnection.description}</p>
                  <div className="mt-3">
                    <Link href={`/settings/wechat/${accountId}`}>
                      <Button variant="secondary" size="sm">
                        {copy.openWechatConfig}
                      </Button>
                    </Link>
                  </div>
                </div>
              </div>
            </Card>

            <Card title={copy.operationsAssets} description={copy.operationsAssetsDesc}>
              <div className="grid gap-4 md:grid-cols-2">
                {[
                  {
                    href: `/accounts/${accountId}/automation`,
                    title: copy.automationPlan,
                    desc: copy.automationPlanDesc,
                  },
                  {
                    href: `/accounts/${accountId}/reference-sources`,
                    title: copy.referenceSources,
                    desc: copy.referenceSourcesDesc,
                  },
                  {
                    href: `/settings/wechat/${accountId}`,
                    title: copy.wechatConfig,
                    desc: wechatConnection.connected
                      ? copy.wechatConfigConnectedDesc
                      : copy.wechatConfigPendingDesc,
                  },
                  {
                    href: `/accounts/${accountId}/workspace`,
                    title: copy.workspace,
                    desc: copy.workspaceDesc,
                  },
                  {
                    href: `/drafts?account_id=${accountId}`,
                    title: copy.drafts,
                    desc: copy.draftsDesc,
                  },
                  {
                    href: `/tasks/history?account_id=${accountId}`,
                    title: copy.tasks,
                    desc: copy.tasksLinkDesc,
                  },
                  {
                    href: "/publish-logs",
                    title: copy.publishLogs,
                    desc: copy.publishLogsDesc,
                  },
                  {
                    href: `/accounts/${accountId}/memory`,
                    title: copy.contentMemory,
                    desc: copy.contentMemoryDesc,
                  },
                  {
                    href: `/accounts/${accountId}/style-profile`,
                    title: copy.styleProfile,
                    desc: copy.styleProfileDesc,
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
              title={copy.latestOpsTitle}
              description={copy.latestOpsDesc}
              action={
                <Link href={`/accounts/${accountId}/automation`}>
                  <Button variant="secondary" size="sm">
                    {copy.reviewAutomationPlan}
                  </Button>
                </Link>
              }
            >
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-2xl border border-slate-200 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{copy.allowRun}</p>
                  <div className="mt-2">
                    <Badge tone={latestRunStrategy.allow_run ? "success" : "danger"}>
                      {latestRunStrategy.allow_run ? copy.allowed : copy.blocked}
                    </Badge>
                  </div>
                </div>
                <div className="rounded-2xl border border-slate-200 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{copy.effectiveMode}</p>
                  <p className="mt-2 text-sm font-semibold text-slate-900">
                    {latestEffectiveMode ? operationModeLabel(latestEffectiveMode) : copy.notRecorded}
                  </p>
                  {latestOpsDegraded ? (
                    <p className="mt-1 text-xs text-amber-700">
                      {copy.downgradedFrom(
                        operationModeLabel(automationPlan?.plan_type ?? workspaceData.account.operation_mode),
                      )}
                    </p>
                  ) : null}
                </div>
                <div className="rounded-2xl border border-slate-200 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{copy.autoPublishTitle}</p>
                  <div className="mt-2">
                    <Badge tone={latestRunStrategy.allow_auto_publish ? "success" : "warning"}>
                      {latestRunStrategy.allow_auto_publish ? copy.allowed : copy.reviewFirst}
                    </Badge>
                  </div>
                </div>
                <div className="rounded-2xl border border-slate-200 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{copy.health}</p>
                  <div className="mt-2">
                    <Badge tone={latestOps?.account_health?.status === "ready" ? "success" : latestOps?.account_health?.status === "risk_recovery" ? "danger" : "warning"}>
                      {token(latestOps?.account_health?.status ?? "attention")}
                    </Badge>
                  </div>
                </div>
              </div>

              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <div className="rounded-2xl border border-slate-200 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{copy.opsNotes}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {(latestOps?.ops_notes ?? []).length ? (
                      latestOps?.ops_notes?.map((note) => (
                        <Badge key={note} tone="muted">
                          {note}
                        </Badge>
                      ))
                    ) : (
                      <span className="text-sm text-slate-500">{copy.noOpsNotes}</span>
                    )}
                  </div>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-2xl border border-slate-200 p-4 text-sm text-slate-600">
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{copy.preferredSources}</p>
                    <p className="mt-2 font-semibold text-slate-900">{latestRunStrategy.preferred_reference_source_ids.length}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 p-4 text-sm text-slate-600">
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{copy.avoidedTopics}</p>
                    <p className="mt-2 font-semibold text-slate-900">{latestRunStrategy.avoid_recent_topics.length}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 p-4 text-sm text-slate-600 sm:col-span-2">
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{copy.preferredContentLane}</p>
                    <p className="mt-2 font-semibold text-slate-900">{latestRunStrategy.preferred_content_lane || copy.notSpecified}</p>
                  </div>
                </div>
              </div>
            </Card>
          ) : null}

          <Card
            title={copy.tasksTitle}
            description={copy.tasksDesc}
          >
            {workspaceData.tasks.length ? (
              <Table columns={[copy.taskColumn, copy.statusColumn, copy.createdColumn, copy.durationColumn, copy.actionColumn]}>
                {workspaceData.tasks.map((task) => (
                  <tr key={task.task_id}>
                    <td className="px-5 py-4">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{task.task_id}</p>
                        <div className="mt-1 flex flex-wrap gap-2">
                          <Badge tone="brand">{copy.accountTaskBadge}</Badge>
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
                          {copy.inspect}
                        </Button>
                      </Link>
                    </td>
                  </tr>
                ))}
              </Table>
            ) : (
              <EmptyState title={copy.noTasksTitle} description={copy.noTasksDesc} />
            )}
          </Card>

          <Card
            title={copy.pendingDraftsTitle}
            description={copy.pendingDraftsDesc}
          >
            {pendingDrafts.length ? (
              <Table
                columns={[
                  copy.titleColumn,
                  copy.draftStatusColumn,
                  copy.publishStatusColumn,
                  copy.updatedColumn,
                  copy.actionColumn,
                ]}
              >
                {pendingDrafts.map((draft) => (
                  <tr key={draft.id}>
                    <td className="px-5 py-4">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{draft.title}</p>
                        <div className="mt-1 flex flex-wrap gap-2">
                          <Badge tone="brand">{copy.accountDraftBadge}</Badge>
                          <Badge tone="muted">{accountId}</Badge>
                        </div>
                        <p className="mt-2 text-sm text-slate-500">{truncate(draft.selected_topic, 100) || copy.noTopicSnapshot}</p>
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
                          {copy.openDraft}
                        </Button>
                      </Link>
                    </td>
                  </tr>
                ))}
              </Table>
            ) : (
              <EmptyState
                title={copy.noPendingDraftsTitle}
                description={copy.noPendingDraftsDesc}
                action={
                  <Link href={`/drafts?account_id=${accountId}`}>
                    <Button>{copy.openAccountDrafts}</Button>
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
