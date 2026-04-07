"use client";

import Link from "next/link";
import { PageHeader, SectionCard, StatusBadge, formatDateTime } from "@/components/console-ui";
import { useShellContext } from "../context";

export default function HistoryPage() {
  const { tasks } = useShellContext();

  return (
    <div className="space-y-5">
      <PageHeader title="历史任务" subtitle="任务运行历史与回看（内部）" />
      <SectionCard title={`任务列表 (${tasks.length})`}>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs text-slate-500">
                <th className="px-2 py-2">Task ID</th>
                <th className="px-2 py-2">状态</th>
                <th className="px-2 py-2">创建时间</th>
                <th className="px-2 py-2">耗时</th>
                <th className="px-2 py-2">错误</th>
                <th className="px-2 py-2">操作</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((task) => (
                <tr key={task.task_id} className="border-b border-slate-100 last:border-0">
                  <td className="px-2 py-3 font-mono text-xs text-slate-700">{task.task_id.slice(0, 10)}...</td>
                  <td className="px-2 py-3"><StatusBadge status={task.status} /></td>
                  <td className="px-2 py-3 text-slate-500">{formatDateTime(task.created_at)}</td>
                  <td className="px-2 py-3 text-slate-500">{task.elapsed_seconds ? `${task.elapsed_seconds.toFixed(1)}s` : "-"}</td>
                  <td className="px-2 py-3 text-xs text-rose-600">{task.error_message ?? "-"}</td>
                  <td className="px-2 py-3"><Link href={`/task/${task.task_id}`} className="text-emerald-600 hover:underline">查看详情</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionCard>
    </div>
  );
}
