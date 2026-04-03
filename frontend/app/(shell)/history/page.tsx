/**
 * History — 历史任务视图
 *
 * 【Shell 内视图】
 * 展示历史任务列表。
 */

"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useShellContext } from "../layout";
import { listTasks, rerunTask } from "@/lib/api";
import type { TaskSummary, AuditResult } from "@/types";

const STATUS_LABEL: Record<string, { text: string; color: string; bg: string }> = {
  pending: { text: "等待中", color: "text-gray-400", bg: "bg-gray-700" },
  running: { text: "执行中", color: "text-yellow-400", bg: "bg-yellow-700" },
  completed: { text: "已完成", color: "text-green-400", bg: "bg-green-700" },
  failed: { text: "失败", color: "text-red-400", bg: "bg-red-700" },
};

const FILTER_OPTIONS = [
  { value: "", label: "全部" },
  { value: "running", label: "执行中" },
  { value: "completed", label: "已完成" },
  { value: "failed", label: "失败" },
  { value: "pending", label: "等待中" },
];

export default function HistoryView() {
  const { refreshData } = useShellContext();
  const router = useRouter();
  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [rerunningId, setRerunningId] = useState<string | null>(null);
  const pageSize = 20;

  const fetchTasks = useCallback(async (p: number, status: string) => {
    setLoading(true);
    try {
      const data = await listTasks(p, pageSize, status || undefined);
      setTasks(data.tasks);
      setTotal(data.pagination.total);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTasks(page, statusFilter);
  }, [page, statusFilter, fetchTasks]);

  const handleRerun = async (e: React.MouseEvent, taskId: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (rerunningId) return;
    setRerunningId(taskId);
    try {
      const data = await rerunTask(taskId);
      router.push(`/task/${data.task_id}`);
      refreshData();
    } catch (err) {
      alert(`重跑失败: ${err instanceof Error ? err.message : "未知错误"}`);
      setRerunningId(null);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="p-6">
      {/* 页面标题 */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white mb-1">历史任务</h1>
          <p className="text-slate-400 text-sm">共 {total} 个任务</p>
        </div>
        {/* 状态筛选 */}
        <div className="flex gap-1">
          {FILTER_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => {
                setPage(1);
                setStatusFilter(opt.value);
              }}
              className={`px-3 py-1.5 rounded-lg text-xs transition-colors ${
                statusFilter === opt.value
                  ? "bg-cyan-600 text-white"
                  : "bg-slate-800 text-slate-400 hover:text-white"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* 任务列表 */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="w-10 h-10 border-4 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin" />
        </div>
      ) : tasks.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <div className="text-6xl">&#128196;</div>
          <div className="text-slate-400 text-lg">暂无任务记录</div>
          <Link href="/workspace" className="text-cyan-400 hover:text-cyan-300 transition-colors text-sm">
            立即创建一个任务
          </Link>
        </div>
      ) : (
        <>
          <div className="space-y-3">
            {tasks.map((task) => {
              const st = STATUS_LABEL[task.status] || STATUS_LABEL.pending;
              const canRerun = task.status === "completed" || task.status === "failed";
              const audit = task.audit_result as AuditResult | null;

              return (
                <Link
                  key={task.task_id}
                  href={`/task/${task.task_id}`}
                  className="block bg-slate-800/40 border border-slate-700 rounded-xl p-5 hover:border-cyan-500/50 transition-all"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-2">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${st.bg} ${st.color}`}>
                          {st.text}
                        </span>
                        {audit && task.status === "completed" && (
                          <>
                            {audit.passed ? (
                              <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-green-900/40 text-green-400 border border-green-700/50">
                                可发布
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-900/40 text-red-400 border border-red-700/50">
                                需修改
                              </span>
                            )}
                          </>
                        )}
                      </div>

                      <div className="text-white font-medium mb-1">
                        {task.positioning_summary || "(无描述)"}
                      </div>

                      <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500">
                        <span className="font-mono">{task.task_id.slice(0, 16)}...</span>
                        <span>{task.created_at?.replace("T", " ").slice(0, 19)}</span>
                        {task.elapsed_seconds !== null && (
                          <span>{task.elapsed_seconds.toFixed(1)}s</span>
                        )}
                      </div>

                      {task.error_message && (
                        <div className="mt-2 p-2 bg-red-900/20 border border-red-800/30 rounded-lg">
                          <div className="text-xs text-red-400">错误: {task.error_message.slice(0, 100)}{task.error_message.length > 100 ? "..." : ""}</div>
                        </div>
                      )}
                    </div>

                    <div className="flex-shrink-0 flex items-center gap-3">
                      {canRerun && (
                        <button
                          onClick={(e) => handleRerun(e, task.task_id)}
                          disabled={rerunningId === task.task_id}
                          className="px-3 py-1.5 text-xs bg-slate-700 hover:bg-cyan-600 disabled:bg-slate-800 disabled:text-slate-500 rounded-lg transition-colors"
                        >
                          {rerunningId === task.task_id ? "重跑中..." : "重跑"}
                        </button>
                      )}
                      <span className="text-slate-600 text-sm">→</span>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>

          {/* 分页 */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-3 mt-8">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="px-4 py-2 text-sm bg-slate-800 hover:bg-slate-700 disabled:bg-slate-900 disabled:text-slate-600 text-slate-400 hover:text-white rounded-lg transition-colors border border-slate-700"
              >
                上一页
              </button>
              <span className="text-sm text-slate-500 px-4">
                第 {page} / {totalPages} 页，共 {total} 条
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="px-4 py-2 text-sm bg-slate-800 hover:bg-slate-700 disabled:bg-slate-900 disabled:text-slate-600 text-slate-400 hover:text-white rounded-lg transition-colors border border-slate-700"
              >
                下一页
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
