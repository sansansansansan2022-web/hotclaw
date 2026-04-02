"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { listTasks, rerunTask } from "@/lib/api";
import type { TaskSummary, AuditResult } from "@/types";

const STATUS_LABEL: Record<string, { text: string; color: string; bg: string }> = {
  pending: { text: "等待中", color: "text-gray-400", bg: "bg-gray-700" },
  running: { text: "执行中", color: "text-yellow-400", bg: "bg-yellow-700" },
  completed: { text: "已完成", color: "text-green-400", bg: "bg-green-700" },
  failed: { text: "失败", color: "text-red-400", bg: "bg-red-700" },
};

const RISK_LABEL: Record<string, { text: string; color: string }> = {
  low: { text: "低风险", color: "text-green-400" },
  medium: { text: "中风险", color: "text-yellow-400" },
  high: { text: "高风险", color: "text-red-400" },
  unknown: { text: "未知", color: "text-gray-400" },
};

const FILTER_OPTIONS = [
  { value: "", label: "全部" },
  { value: "running", label: "执行中" },
  { value: "completed", label: "已完成" },
  { value: "failed", label: "失败" },
  { value: "pending", label: "等待中" },
];

export default function HistoryPage() {
  const router = useRouter();
  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [rerunningId, setRerunningId] = useState<string | null>(null);
  const pageSize = 20;

  const fetchTasks = useCallback(
    async (p: number, status: string) => {
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
    },
    []
  );

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
      router.push(`/newsroom?taskId=${data.task_id}`);
    } catch (err) {
      alert(`重跑失败: ${err instanceof Error ? err.message : "未知错误"}`);
      setRerunningId(null);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
      {/* Header */}
      <header className="bg-slate-800/80 backdrop-blur-sm border-b border-slate-700 px-6 py-4 sticky top-0 z-20">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="text-cyan-400 hover:text-cyan-300 transition-colors flex items-center gap-2"
            >
              <span>&larr;</span>
              <span>首页</span>
            </Link>
            <span className="text-slate-500">/</span>
            <span className="text-white font-medium">历史任务</span>
            <span className="text-slate-500 text-sm">({total})</span>
          </div>
          <div className="flex items-center gap-3">
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
                      : "bg-slate-700 text-slate-400 hover:text-white"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <button
              onClick={() => fetchTasks(page, statusFilter)}
              className="text-slate-400 hover:text-white transition-colors text-sm flex items-center gap-1"
            >
              <span>&#8635;</span> 刷新
            </button>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-5xl mx-auto p-6">
        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center py-20">
            <div className="w-10 h-10 border-4 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin" />
          </div>
        )}

        {/* Empty */}
        {!loading && tasks.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 gap-4">
            <div className="text-6xl">&#128196;</div>
            <div className="text-slate-400 text-lg">暂无任务记录</div>
            <Link
              href="/"
              className="text-cyan-400 hover:text-cyan-300 transition-colors text-sm"
            >
              立即创建一个任务
            </Link>
          </div>
        )}

        {/* Task List */}
        {!loading && tasks.length > 0 && (
          <div className="space-y-3">
            {tasks.map((task) => {
              const st = STATUS_LABEL[task.status] || STATUS_LABEL.pending;
              const canRerun = task.status === "completed" || task.status === "failed";
              const audit = task.audit_result as AuditResult | null;

              return (
                <Link
                  key={task.task_id}
                  href={`/task/${task.task_id}`}
                  className="block bg-slate-800/60 border border-slate-700 rounded-xl p-5
                             hover:border-cyan-500/50 hover:bg-slate-800/80 transition-all group"
                >
                  <div className="flex items-start justify-between gap-4">
                    {/* 左侧信息 */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-2">
                        {/* 状态标签 */}
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${st.bg} ${st.color}`}>
                          {st.text}
                        </span>
                        {/* 审核结果 */}
                        {audit && task.status === "completed" && (
                          <>
                            {audit.passed ? (
                              <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-green-900/40 text-green-400 border border-green-700/50">
                                &#2705; 可发布
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-900/40 text-red-400 border border-red-700/50">
                                &#9888; 需修改
                              </span>
                            )}
                            {audit.risk_level && (
                              <span
                                className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                                  RISK_LABEL[audit.risk_level]?.color
                                } bg-slate-700`}
                              >
                                {RISK_LABEL[audit.risk_level]?.text}
                              </span>
                            )}
                          </>
                        )}
                      </div>

                      {/* 定位描述 */}
                      <div className="text-white font-medium mb-1">
                        {task.positioning_summary || "(无描述)"}
                      </div>

                      {/* 元信息 */}
                      <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500">
                        <span className="font-mono">{task.task_id.slice(0, 16)}...</span>
                        <span>&#128197; {task.created_at?.replace("T", " ").slice(0, 19)}</span>
                        {task.elapsed_seconds !== null && (
                          <span>&#9201;&#65039; {task.elapsed_seconds.toFixed(1)}s</span>
                        )}
                        {audit?.issues && audit.issues.length > 0 && (
                          <span>&#128737; {audit.issues.length}个问题</span>
                        )}
                      </div>

                      {/* 错误信息预览 */}
                      {task.error_message && (
                        <div className="mt-2 p-2 bg-red-900/20 border border-red-800/30 rounded-lg">
                          <div className="text-xs text-red-400">错误: {task.error_message.slice(0, 100)}{task.error_message.length > 100 ? "..." : ""}</div>
                        </div>
                      )}

                      {/* 审核意见预览 */}
                      {audit?.overall_comment && task.status === "completed" && (
                        <div className="mt-2 text-xs text-slate-400 italic">
                          &ldquo;{audit.overall_comment.slice(0, 80)}{audit.overall_comment.length > 80 ? "..." : ""}&rdquo;
                        </div>
                      )}
                    </div>

                    {/* 右侧操作 */}
                    <div className="flex-shrink-0 flex items-center gap-3">
                      {canRerun && (
                        <button
                          onClick={(e) => handleRerun(e, task.task_id)}
                          disabled={rerunningId === task.task_id}
                          className="px-3 py-1.5 text-xs bg-slate-700 hover:bg-cyan-600 disabled:bg-slate-800
                                     disabled:text-slate-500 rounded-lg transition-colors flex items-center gap-1.5"
                        >
                          {rerunningId === task.task_id ? (
                            <>
                              <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                              重跑中
                            </>
                          ) : (
                            <>
                              <span>&#8635;</span> 重跑
                            </>
                          )}
                        </button>
                      )}
                      <span className="text-slate-600 group-hover:text-slate-400 transition-colors text-sm">
                        &rarr;
                      </span>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-3 mt-8">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-4 py-2 text-sm bg-slate-800 hover:bg-slate-700 disabled:bg-slate-900 disabled:text-slate-600
                         text-slate-400 hover:text-white rounded-lg transition-colors border border-slate-700"
            >
              &laquo; 上一页
            </button>
            <span className="text-sm text-slate-500 px-4">
              第 {page} / {totalPages} 页，共 {total} 条
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="px-4 py-2 text-sm bg-slate-800 hover:bg-slate-700 disabled:bg-slate-900 disabled:text-slate-600
                         text-slate-400 hover:text-white rounded-lg transition-colors border border-slate-700"
            >
              下一页 &raquo;
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
