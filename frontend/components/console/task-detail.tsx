"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getTaskDetail, getTaskNodes } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { formatDateTime, formatDuration, formatNumber, truncate } from "@/lib/utils";
import type { NodeRun, TaskDetail } from "@/types";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, SkeletonRows, StatCard, Table } from "@/components/console/ui";
import { Icon } from "@/components/console/icons";

function taskTone(status: string): "success" | "warning" | "danger" | "muted" {
  if (status === "completed") return "success";
  if (status === "failed") return "danger";
  if (status === "running") return "warning";
  return "muted";
}

export function TaskDetailPage({ taskId }: { taskId: string }) {
  const { locale, taskStatusLabel } = useI18n();
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const [nodes, setNodes] = useState<NodeRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      const [detailRes, nodesRes] = await Promise.all([getTaskDetail(taskId), getTaskNodes(taskId)]);
      setDetail(detailRes);
      setNodes(nodesRes.nodes);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : locale === "zh-CN" ? "无法加载任务详情" : "Unable to load task detail");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [taskId, locale]);

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={locale === "zh-CN" ? "执行轨迹" : "Execution Trace"}
        title={`${locale === "zh-CN" ? "任务" : "Task"} ${taskId}`}
        description={locale === "zh-CN" ? "查看编排引擎返回的任务快照、结果载荷和节点级执行轨迹。" : "Detailed task snapshot, result payload and node-level execution trace from the orchestration engine."}
        actions={
          <Link href="/tasks/history">
            <Button variant="secondary">{locale === "zh-CN" ? "返回历史" : "Back to History"}</Button>
          </Link>
        }
      />

      {loading ? (
        <SkeletonRows rows={4} />
      ) : error ? (
        <ErrorState title={locale === "zh-CN" ? "任务详情加载失败" : "Task detail failed to load"} description={error} retry={() => void load()} />
      ) : detail ? (
        <>
          <div className="grid gap-5 md:grid-cols-4">
            <StatCard label={locale === "zh-CN" ? "状态" : "Status"} value={taskStatusLabel(detail.status)} hint={locale === "zh-CN" ? "当前任务生命周期状态" : "Current task lifecycle state"} tone={taskTone(detail.status)} icon={<Icon name="history" className="h-6 w-6" />} />
            <StatCard label={locale === "zh-CN" ? "工作流" : "Workflow"} value={detail.workflow_id} hint={locale === "zh-CN" ? "编排器使用的工作流模板" : "Workflow template used by the orchestrator"} tone="info" icon={<Icon name="workspace" className="h-6 w-6" />} />
            <StatCard label={locale === "zh-CN" ? "耗时" : "Duration"} value={formatDuration(detail.elapsed_seconds)} hint={locale === "zh-CN" ? "累计执行时长" : "Elapsed execution time"} tone="brand" icon={<Icon name="play" className="h-6 w-6" />} />
            <StatCard label={locale === "zh-CN" ? "Tokens" : "Tokens"} value={formatNumber(detail.total_tokens)} hint={locale === "zh-CN" ? "累计 prompt 与 completion 用量" : "Accumulated prompt and completion usage"} tone="muted" icon={<Icon name="dashboard" className="h-6 w-6" />} />
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.1fr_1fr]">
            <Card title={locale === "zh-CN" ? "输入快照" : "Input Snapshot"} description={locale === "zh-CN" ? "触发任务时的原始定位或载荷。" : "The original positioning or payload that kicked off the task."}>
              <p className="whitespace-pre-wrap text-sm leading-7 text-slate-600">
                {typeof detail.input_data?.positioning === "string" ? detail.input_data.positioning : JSON.stringify(detail.input_data, null, 2)}
              </p>
            </Card>
            <Card title={locale === "zh-CN" ? "生命周期" : "Lifecycle"} description={locale === "zh-CN" ? "任务时间戳和终态错误信息。" : "Task timestamps and terminal errors."}>
              <dl className="grid gap-4 text-sm text-slate-600">
                <div className="flex items-center justify-between gap-4">
                  <dt className="text-slate-500">{locale === "zh-CN" ? "创建时间" : "Created"}</dt>
                  <dd>{formatDateTime(detail.created_at)}</dd>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <dt className="text-slate-500">{locale === "zh-CN" ? "开始时间" : "Started"}</dt>
                  <dd>{formatDateTime(detail.started_at)}</dd>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <dt className="text-slate-500">{locale === "zh-CN" ? "完成时间" : "Completed"}</dt>
                  <dd>{formatDateTime(detail.completed_at)}</dd>
                </div>
                <div className="border-t border-slate-200 pt-4">
                  <dt className="text-slate-500">{locale === "zh-CN" ? "错误" : "Error"}</dt>
                  <dd className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">{detail.error_message || (locale === "zh-CN" ? "没有终态错误" : "No terminal error")}</dd>
                </div>
              </dl>
            </Card>
          </div>

          <Card title={locale === "zh-CN" ? "节点轨迹" : "Node Trace"} description={locale === "zh-CN" ? "从 profile 到 audit 的逐 Agent 执行详情。" : "Per-agent execution detail from profile through audit."}>
            {nodes.length ? (
              <Table columns={[locale === "zh-CN" ? "节点" : "Node", locale === "zh-CN" ? "状态" : "Status", locale === "zh-CN" ? "耗时" : "Duration", locale === "zh-CN" ? "模型" : "Model", locale === "zh-CN" ? "降级" : "Degraded", locale === "zh-CN" ? "错误" : "Error"]}>
                {nodes.map((node) => (
                  <tr key={node.node_id}>
                    <td className="px-5 py-4">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{node.node_id}</p>
                        <p className="mt-1 text-xs text-slate-500">{node.agent_id}</p>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <Badge tone={taskTone(node.status)}>{taskStatusLabel(node.status)}</Badge>
                    </td>
                    <td className="px-5 py-4 text-sm text-slate-600">{formatDuration(node.elapsed_seconds)}</td>
                    <td className="px-5 py-4 text-sm text-slate-600">{node.model_used || (locale === "zh-CN" ? "默认模型" : "Default model")}</td>
                    <td className="px-5 py-4 text-sm text-slate-600">{node.degraded ? (locale === "zh-CN" ? "是" : "Yes") : locale === "zh-CN" ? "否" : "No"}</td>
                    <td className="px-5 py-4 text-sm text-slate-500">{truncate(node.error_message, 80) || (locale === "zh-CN" ? "无错误" : "No error")}</td>
                  </tr>
                ))}
              </Table>
            ) : (
              <EmptyState title={locale === "zh-CN" ? "暂无节点运行记录" : "No node runs recorded yet"} description={locale === "zh-CN" ? "编排器开始执行工作流后，才会生成节点运行记录。" : "Node runs are created once the orchestrator starts executing the workflow."} />
            )}
          </Card>
        </>
      ) : null}
    </div>
  );
}
