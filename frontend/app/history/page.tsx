"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { listTasks } from "@/lib/api";
import type { TaskSummary } from "@/types";

const STATUS_LABEL: Record<string, { text: string; color: string }> = {
  pending: { text: "等待中", color: "text-gray-400" },
  running: { text: "执行中", color: "text-yellow-400" },
  completed: { text: "已完成", color: "text-green-400" },
  failed: { text: "失败", color: "text-red-400" },
};

export default function HistoryPage() {
  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const pageSize = 20;

  const fetchTasks = useCallback(async (p: number) => {
    setLoading(true);
    try {
      const data = await listTasks(p, pageSize);
      setTasks(data.tasks);
      setTotal(data.pagination.total);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTasks(page);
  }, [page, fetchTasks]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="min-h-screen bg-[#1a1a2e] text-gray-200 font-mono">
      {/* Header */}
      <header className="bg-[#2a2a4a] border-b border-gray-700 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-cyan-400 hover:text-cyan-300 text-[12px]">
            &larr; 返回编辑部
          </Link>
          <span className="text-[14px] text-gray-300 tracking-widest">历史任务</span>
        </div>
        <button
          onClick={() => fetchTasks(page)}
          className="text-[10px] text-gray-500 hover:text-gray-300 border border-gray-600 px-2 py-1 rounded-sm"
        >
          刷新
        </button>
      </header>

      {/* Content */}
      <main className="max-w-[800px] mx-auto p-6">
        {loading ? (
          <div className="text-center text-[12px] text-gray-500 py-12">加载中...</div>
        ) : tasks.length === 0 ? (
          <div className="text-center text-[12px] text-gray-500 py-12">
            暂无任务记录
          </div>
        ) : (
          <>
            <div className="space-y-2">
              {tasks.map((task) => {
                const st = STATUS_LABEL[task.status] || STATUS_LABEL.pending;
                return (
                  <Link
                    key={task.task_id}
                    href={`/task/${task.task_id}`}
                    className="block bg-gray-900/50 border border-gray-700 rounded-sm px-4 py-3
                               hover:border-cyan-600/50 hover:bg-gray-900/70 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="text-[11px] text-gray-300 truncate">
                          {task.positioning_summary || "(无描述)"}
                        </div>
                        <div className="text-[9px] text-gray-500 mt-1 flex items-center gap-3">
                          <span>{task.task_id}</span>
                          <span>{task.created_at?.replace("T", " ").slice(0, 19)}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 ml-4">
                        {task.elapsed_seconds !== null && (
                          <span className="text-[9px] text-gray-500">
                            {task.elapsed_seconds.toFixed(1)}s
                          </span>
                        )}
                        <span className={`text-[10px] ${st.color}`}>{st.text}</span>
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-3 mt-6">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="text-[10px] text-gray-400 hover:text-white disabled:text-gray-600 px-2 py-1"
                >
                  &laquo; 上一页
                </button>
                <span className="text-[10px] text-gray-500">
                  {page} / {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="text-[10px] text-gray-400 hover:text-white disabled:text-gray-600 px-2 py-1"
                >
                  下一页 &raquo;
                </button>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
