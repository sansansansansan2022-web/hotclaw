"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { listTasks, rerunTask } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { formatDateTime, formatDuration, formatNumber, truncate } from "@/lib/utils";
import type { TaskSummary } from "@/types";
import { Badge, Button, EmptyState, ErrorState, PageHeader, Select, SkeletonRows, StatCard, Table } from "@/components/console/ui";
import { Icon } from "@/components/console/icons";
import { useAppStore } from "@/store/appStore";

function taskTone(status: string): "success" | "warning" | "danger" | "muted" {
  if (status === "completed") return "success";
  if (status === "failed") return "danger";
  if (status === "running") return "warning";
  return "muted";
}

export function TaskHistoryPage({ initialAccountId }: { initialAccountId?: string | null }) {
  const { locale, t, taskStatusLabel } = useI18n();
  const pushToast = useAppStore((state) => state.pushToast);
  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("all");

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await listTasks(1, 100, status === "all" ? undefined : status, initialAccountId ?? undefined);
      setTasks(response.tasks);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : t("tasks.loadError"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [initialAccountId, status]);

  const stats = useMemo(() => {
    const completed = tasks.filter((task) => task.status === "completed").length;
    const failed = tasks.filter((task) => task.status === "failed").length;
    const running = tasks.filter((task) => task.status === "running").length;
    return { completed, failed, running };
  }, [tasks]);

  const rerun = async (taskId: string) => {
    try {
      const created = await rerunTask(taskId);
      pushToast({
        tone: "success",
        title: t("tasks.rerunQueued"),
        message: locale === "zh-CN" ? `任务 ${created.task_id} 已重新进入队列。` : `Task ${created.task_id} is queued again.`,
      });
      await load();
    } catch (rerunError) {
      pushToast({
        tone: "danger",
        title: t("tasks.rerunFailed"),
        message: rerunError instanceof Error ? rerunError.message : locale === "zh-CN" ? "发生了意外错误。" : "Unexpected error",
      });
    }
  };

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={initialAccountId ? (locale === "zh-CN" ? "账号任务历史" : "Account Task History") : t("tasks.eyebrow")}
        title={initialAccountId ? (locale === "zh-CN" ? "本账号任务" : "Account Tasks") : t("tasks.title")}
        description={
          initialAccountId
            ? locale === "zh-CN"
              ? "只展示这个账号上下文里产生的任务记录，让任务重新回到账号工作区语义。"
              : "Show only the task records created inside this account context so tasks stay anchored to the account workspace."
            : t("tasks.description")
        }
        actions={
          <div className="flex flex-wrap items-center gap-3">
            {initialAccountId ? (
              <Link href={`/accounts/${initialAccountId}`}>
                <Button variant="secondary">{locale === "zh-CN" ? "返回账号" : "Back to Account"}</Button>
              </Link>
            ) : null}
            <Select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="all">{t("tasks.allStatuses")}</option>
              <option value="pending">{taskStatusLabel("pending")}</option>
              <option value="running">{taskStatusLabel("running")}</option>
              <option value="completed">{taskStatusLabel("completed")}</option>
              <option value="failed">{taskStatusLabel("failed")}</option>
            </Select>
          </div>
        }
      />

      <div className="grid gap-5 md:grid-cols-3">
        <StatCard label={locale === "zh-CN" ? "运行中" : "Running"} value={formatNumber(stats.running)} hint={locale === "zh-CN" ? "当前仍在执行的编排任务" : "Currently active orchestrations"} tone="warning" icon={<Icon name="play" className="h-6 w-6" />} />
        <StatCard label={locale === "zh-CN" ? "已完成" : "Completed"} value={formatNumber(stats.completed)} hint={locale === "zh-CN" ? "已产出结果快照的任务链路" : "Finished task chains with result snapshots"} tone="success" icon={<Icon name="check" className="h-6 w-6" />} />
        <StatCard label={locale === "zh-CN" ? "失败" : "Failed"} value={formatNumber(stats.failed)} hint={locale === "zh-CN" ? "需要排查或重跑的任务" : "Tasks requiring inspection or rerun"} tone="danger" icon={<Icon name="warning" className="h-6 w-6" />} />
      </div>

      {loading ? (
        <SkeletonRows rows={6} />
      ) : error ? (
        <ErrorState title={t("tasks.loadError")} description={error} retry={() => void load()} />
      ) : tasks.length ? (
        <Table
          columns={[
            locale === "zh-CN" ? "任务" : "Task",
            locale === "zh-CN" ? "所属账号" : "Account",
            locale === "zh-CN" ? "状态" : "Status",
            locale === "zh-CN" ? "创建时间" : "Created",
            locale === "zh-CN" ? "耗时" : "Duration",
            locale === "zh-CN" ? "错误" : "Error",
            locale === "zh-CN" ? "操作" : "Action",
          ]}
        >
          {tasks.map((task) => (
            <tr key={task.task_id}>
              <td className="px-5 py-4">
                <div>
                  <p className="text-sm font-semibold text-slate-900">{task.task_id}</p>
                  <p className="mt-1 text-sm text-slate-500">{truncate(task.positioning_summary, 96)}</p>
                </div>
              </td>
              <td className="px-5 py-4">
                {task.account_id ? (
                  <Link href={`/accounts/${task.account_id}`} className="inline-flex items-center gap-2 text-sm font-medium text-brand-700 hover:text-brand-800">
                    <Badge tone="brand">{task.account_name || task.account_id}</Badge>
                  </Link>
                ) : (
                  <Badge tone="muted">{locale === "zh-CN" ? "全局调试" : "Global Debug"}</Badge>
                )}
              </td>
              <td className="px-5 py-4">
                <Badge tone={taskTone(task.status)}>{taskStatusLabel(task.status)}</Badge>
              </td>
              <td className="px-5 py-4 text-sm text-slate-600">{formatDateTime(task.created_at)}</td>
              <td className="px-5 py-4 text-sm text-slate-600">{formatDuration(task.elapsed_seconds)}</td>
              <td className="px-5 py-4 text-sm text-slate-500">{truncate(task.error_message, 80) || (locale === "zh-CN" ? "无错误" : "No error")}</td>
              <td className="px-5 py-4">
                <div className="flex gap-2">
                  <Link href={`/task/${task.task_id}`}>
                    <Button variant="secondary" size="sm">
                      {t("tasks.inspect")}
                    </Button>
                  </Link>
                  <Button variant="ghost" size="sm" onClick={() => void rerun(task.task_id)}>
                    {t("tasks.rerun")}
                  </Button>
                </div>
              </td>
            </tr>
          ))}
        </Table>
      ) : (
        <EmptyState
          title={initialAccountId ? (locale === "zh-CN" ? "这个账号还没有任务" : "No account tasks yet") : t("tasks.emptyTitle")}
          description={
            initialAccountId
              ? locale === "zh-CN"
                ? "从账号工作台或账号详情页点击“立即运行”后，这里会出现该账号的任务记录。"
                : "Run the account from its workspace or detail page and its task records will appear here."
              : t("tasks.emptyDesc")
          }
        />
      )}
    </div>
  );
}
