"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { disableAccount, enableAccount, getAccount, getPendingDraftCount, runAccount } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { formatDateTime, formatDuration, formatNumber, truncate } from "@/lib/utils";
import type { AccountDetail } from "@/types";
import { Badge, Button, Card, ConfirmDialog, EmptyState, ErrorState, PageHeader, SkeletonRows, StatCard, Table } from "@/components/console/ui";
import { Icon } from "@/components/console/icons";
import { useAppStore } from "@/store/appStore";

function accountTone(status: string | null): "success" | "warning" | "danger" | "muted" {
  if (status === "running") return "warning";
  if (status === "failed") return "danger";
  if (status === "completed") return "success";
  return "muted";
}

export function AccountDetailPage({ accountId }: { accountId: string }) {
  const { locale, operationModeLabel, taskStatusLabel, publishStatusLabel } = useI18n();
  const pushToast = useAppStore((state) => state.pushToast);
  const [detail, setDetail] = useState<AccountDetail | null>(null);
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
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : locale === "zh-CN" ? "无法加载账号" : "Unable to load account");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [accountId]);

  const runNow = async () => {
    try {
      const response = await runAccount(accountId);
      pushToast({
        tone: "success",
        title: locale === "zh-CN" ? "账号运行已入队" : "Account run queued",
        message: locale === "zh-CN" ? `任务 ${response.task_id} 已成功启动。` : `Task ${response.task_id} started successfully.`,
      });
      await load();
    } catch (runError) {
      pushToast({
        tone: "danger",
        title: locale === "zh-CN" ? "运行失败" : "Run failed",
        message: runError instanceof Error ? runError.message : locale === "zh-CN" ? "发生了意外错误" : "Unexpected error",
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
          message: locale === "zh-CN" ? "该账号已被暂停。" : "The account has been paused.",
        });
      }
      setConfirmDisable(false);
      await load();
    } catch (toggleError) {
      pushToast({
        tone: "danger",
        title: locale === "zh-CN" ? "状态切换失败" : "Status change failed",
        message: toggleError instanceof Error ? toggleError.message : locale === "zh-CN" ? "发生了意外错误" : "Unexpected error",
      });
    }
  };

  const frequencyLabel = (value?: string | null) => {
    if (!value) return locale === "zh-CN" ? "未安排" : "Not scheduled";
    if (value === "daily") return locale === "zh-CN" ? "每日" : "Daily";
    if (value === "weekly") return locale === "zh-CN" ? "每周" : "Weekly";
    if (value === "biweekly") return locale === "zh-CN" ? "双周" : "Biweekly";
    if (value === "monthly") return locale === "zh-CN" ? "每月" : "Monthly";
    return value;
  };

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={locale === "zh-CN" ? "账号详情" : "Account Detail"}
        title={detail?.name || (locale === "zh-CN" ? "账号" : "Account")}
        description={locale === "zh-CN" ? "查看真实后端账号资料、调度状态、最近任务和待审核草稿入口。" : "Backend-backed account profile, scheduling posture, recent tasks and pending draft review entry points."}
        actions={
          <>
            <Link href={`/accounts/${accountId}/edit`}>
              <Button variant="secondary">
                <Icon name="edit" className="h-4 w-4" />
                {locale === "zh-CN" ? "编辑" : "Edit"}
              </Button>
            </Link>
            <Link href={`/settings/wechat/${accountId}`}>
              <Button variant="secondary">{locale === "zh-CN" ? "微信配置" : "WeChat Config"}</Button>
            </Link>
            <Button onClick={() => void runNow()}>
              <Icon name="play" className="h-4 w-4" />
              {locale === "zh-CN" ? "立即运行" : "Run Now"}
            </Button>
            <Button variant={detail?.is_active === false ? "secondary" : "destructive"} onClick={() => (detail?.is_active ? setConfirmDisable(true) : void toggleActive(true))}>
              {detail?.is_active ? (locale === "zh-CN" ? "停用" : "Disable") : locale === "zh-CN" ? "启用" : "Enable"}
            </Button>
          </>
        }
      />

      {loading ? (
        <SkeletonRows rows={5} />
      ) : error ? (
        <ErrorState title={locale === "zh-CN" ? "账号详情加载失败" : "Account detail failed to load"} description={error} retry={() => void load()} />
      ) : detail ? (
        <>
          <div className="grid gap-5 md:grid-cols-4">
            <StatCard label={locale === "zh-CN" ? "运行模式" : "Operation Mode"} value={operationModeLabel(detail.operation_mode)} hint={locale === "zh-CN" ? "后端执行模式" : "Backend execution mode"} tone="brand" icon={<Icon name="workspace" className="h-6 w-6" />} />
            <StatCard label={locale === "zh-CN" ? "待审核" : "Pending Review"} value={formatNumber(pendingCount)} hint={locale === "zh-CN" ? "等待处理的草稿" : "Drafts waiting for action"} tone="warning" icon={<Icon name="drafts" className="h-6 w-6" />} />
            <StatCard label={locale === "zh-CN" ? "最近运行状态" : "Last Run Status"} value={taskStatusLabel(detail.last_run_status)} hint={detail.last_error_message || (locale === "zh-CN" ? "最近一次观测到的运行信号" : "Last observed runtime signal")} tone={accountTone(detail.last_run_status)} icon={<Icon name="history" className="h-6 w-6" />} />
            <StatCard label={locale === "zh-CN" ? "最近发布状态" : "Publish Status"} value={publishStatusLabel(detail.last_publish_status)} hint={detail.last_publish_error_message || (locale === "zh-CN" ? "最近一次发布信号" : "Most recent publish signal")} tone={accountTone(detail.last_publish_status)} icon={<Icon name="publish" className="h-6 w-6" />} />
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.1fr_0.95fr]">
            <Card title={locale === "zh-CN" ? "账号概览" : "Account Overview"} description={locale === "zh-CN" ? "任务编排器使用的战略输入和自动化姿态。" : "Strategic input and automation posture used by the task orchestrator."}>
              <div className="space-y-5">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "定位" : "Positioning"}</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-slate-600">{detail.positioning}</p>
                </div>
                <div className="grid gap-5 md:grid-cols-2">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "受众" : "Audience"}</p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{detail.audience || (locale === "zh-CN" ? "未设置" : "Not set")}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "语气与风格" : "Tone & style"}</p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{detail.tone_style || (locale === "zh-CN" ? "未设置" : "Not set")}</p>
                  </div>
                </div>
                <div className="grid gap-5 md:grid-cols-2">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "发布节奏" : "Posting cadence"}</p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">
                      {detail.posting_frequency
                        ? `${frequencyLabel(detail.posting_frequency)} ${locale === "zh-CN" ? "于" : "at"} ${detail.posting_time || (locale === "zh-CN" ? "未设时间" : "unset time")}`
                        : locale === "zh-CN"
                          ? "未安排"
                          : "Not scheduled"}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "参考账号" : "Reference accounts"}</p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{detail.reference_accounts || (locale === "zh-CN" ? "未设置" : "Not set")}</p>
                  </div>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "内容策略" : "Content strategy"}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{detail.content_strategy || (locale === "zh-CN" ? "未设置" : "Not set")}</p>
                </div>
              </div>
            </Card>

            <Card title={locale === "zh-CN" ? "运行与保护" : "Runtime & Safeguards"} description={locale === "zh-CN" ? "直接映射后端调度、暂停发布和保护字段。" : "Direct reflection of backend scheduling, publish pause and protection fields."}>
              <div className="grid gap-4 text-sm text-slate-600">
                <div className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 p-4">
                  <div>
                    <p className="font-medium text-slate-900">{locale === "zh-CN" ? "账号状态" : "Account state"}</p>
                    <p className="text-slate-500">{locale === "zh-CN" ? "调度器是否可以运行这个账号。" : "Whether the scheduler can run this account."}</p>
                  </div>
                  <Badge tone={detail.is_active ? "success" : "muted"}>{detail.is_active ? (locale === "zh-CN" ? "启用" : "Active") : locale === "zh-CN" ? "暂停" : "Paused"}</Badge>
                </div>
                <div className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 p-4">
                  <div>
                    <p className="font-medium text-slate-900">{locale === "zh-CN" ? "自动运行" : "Auto-run"}</p>
                    <p className="text-slate-500">{locale === "zh-CN" ? "是否参与调度器。" : "Scheduler participation flag."}</p>
                  </div>
                  <Badge tone={detail.auto_run_enabled ? "success" : "muted"}>{detail.auto_run_enabled ? (locale === "zh-CN" ? "启用" : "Enabled") : locale === "zh-CN" ? "停用" : "Disabled"}</Badge>
                </div>
                <div className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 p-4">
                  <div>
                    <p className="font-medium text-slate-900">{locale === "zh-CN" ? "自动发布" : "Auto-publish"}</p>
                    <p className="text-slate-500">{locale === "zh-CN" ? "自动发布路径是否可用。" : "Automatic publish path availability."}</p>
                  </div>
                  <Badge tone={detail.auto_publish_enabled ? "success" : "muted"}>{detail.auto_publish_enabled ? (locale === "zh-CN" ? "启用" : "Enabled") : locale === "zh-CN" ? "停用" : "Disabled"}</Badge>
                </div>
                <div className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 p-4">
                  <div>
                    <p className="font-medium text-slate-900">{locale === "zh-CN" ? "暂停发布" : "Publish paused"}</p>
                    <p className="text-slate-500">{locale === "zh-CN" ? "手动阻断对外发布。" : "Manual block for outbound publishing."}</p>
                  </div>
                  <Badge tone={detail.publish_paused ? "danger" : "success"}>{detail.publish_paused ? (locale === "zh-CN" ? "暂停" : "Paused") : locale === "zh-CN" ? "开放" : "Open"}</Badge>
                </div>
                <div className="rounded-2xl border border-slate-200 p-4">
                  <p className="font-medium text-slate-900">{locale === "zh-CN" ? "发布限制" : "Publish limits"}</p>
                  <p className="mt-2 text-slate-500">{locale === "zh-CN" ? "每日最大发布数：" : "Max posts per day: "}{detail.max_posts_per_day ?? (locale === "zh-CN" ? "未设置" : "Not set")}</p>
                  <p className="mt-1 text-slate-500">{locale === "zh-CN" ? "最小发布间隔（分钟）：" : "Min interval minutes: "}{detail.min_interval_minutes ?? (locale === "zh-CN" ? "未设置" : "Not set")}</p>
                </div>
              </div>
            </Card>
          </div>

          <Card title={locale === "zh-CN" ? "最近任务运行" : "Recent Task Runs"} description={locale === "zh-CN" ? "与这个账号关联的最新任务记录。" : "Latest task records associated with this account."}>
            {detail.recent_tasks.length ? (
              <Table columns={[locale === "zh-CN" ? "任务" : "Task", locale === "zh-CN" ? "状态" : "Status", locale === "zh-CN" ? "创建时间" : "Created", locale === "zh-CN" ? "耗时" : "Duration", locale === "zh-CN" ? "操作" : "Action"]}>
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
                          {locale === "zh-CN" ? "打开" : "Open"}
                        </Button>
                      </Link>
                    </td>
                  </tr>
                ))}
              </Table>
            ) : (
              <EmptyState title={locale === "zh-CN" ? "暂无最近任务" : "No recent tasks"} description={locale === "zh-CN" ? "先运行一次该账号，这里才会出现最近任务历史。" : "Run this account once to populate the recent task history block."} />
            )}
          </Card>

          <Card title={locale === "zh-CN" ? "审核与发布入口" : "Review & Publish Pointers"} description={locale === "zh-CN" ? "运营在账号详情页最常需要的跳转入口。" : "Entry points that operators most often need from the account detail screen."}>
            <div className="grid gap-4 md:grid-cols-3">
              <Link href="/drafts" className="rounded-2xl border border-slate-200 p-4 transition hover:border-brand-200 hover:bg-brand-50/60">
                <p className="text-sm font-semibold text-slate-900">{locale === "zh-CN" ? "草稿收件箱" : "Draft Inbox"}</p>
                <p className="mt-1 text-sm text-slate-500">{locale === "zh-CN" ? `该账号关联的待审核草稿：${pendingCount} 条。` : `${pendingCount} pending review drafts linked to this account.`}</p>
              </Link>
              <Link href="/publish-logs" className="rounded-2xl border border-slate-200 p-4 transition hover:border-brand-200 hover:bg-brand-50/60">
                <p className="text-sm font-semibold text-slate-900">{locale === "zh-CN" ? "发布日志" : "Publish Logs"}</p>
                <p className="mt-1 text-sm text-slate-500">{truncate(detail.last_publish_error_message, 90) || (locale === "zh-CN" ? "查看最近的发布尝试和重试状态。" : "Inspect the latest publish attempts and retry status.")}</p>
              </Link>
              <Link href={`/settings/wechat/${accountId}`} className="rounded-2xl border border-slate-200 p-4 transition hover:border-brand-200 hover:bg-brand-50/60">
                <p className="text-sm font-semibold text-slate-900">{locale === "zh-CN" ? "微信配置" : "WeChat Config"}</p>
                <p className="mt-1 text-sm text-slate-500">{locale === "zh-CN" ? "配置凭证、测试连接并设置默认作者信息。" : "Configure credentials, test connectivity and set default author information."}</p>
              </Link>
            </div>
          </Card>
        </>
      ) : null}

      <ConfirmDialog
        open={confirmDisable}
        title={locale === "zh-CN" ? "停用账号" : "Disable Account"}
        description={locale === "zh-CN" ? "这会暂停该账号的调度活动。已有任务不会删除，但新的定时运行会停止。" : "This will pause scheduler activity for the account. Existing tasks are not deleted, but new scheduled runs will stop."}
        confirmLabel={locale === "zh-CN" ? "停用账号" : "Disable Account"}
        tone="danger"
        onCancel={() => setConfirmDisable(false)}
        onConfirm={() => void toggleActive(false)}
      />
    </div>
  );
}
