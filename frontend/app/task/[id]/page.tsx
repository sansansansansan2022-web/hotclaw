"use client";

import { useState, useEffect, use } from "react";
import Link from "next/link";
import { getTaskDetail, getTaskNodes } from "@/lib/api";
import type { TaskDetail, NodeRun } from "@/types";

const STATUS_LABEL: Record<string, { text: string; color: string }> = {
  pending: { text: "等待中", color: "text-gray-400" },
  running: { text: "执行中", color: "text-yellow-400" },
  completed: { text: "已完成", color: "text-green-400" },
  failed: { text: "失败", color: "text-red-400" },
  skipped: { text: "跳过", color: "text-gray-500" },
};

export default function TaskDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [nodes, setNodes] = useState<NodeRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedNode, setExpandedNode] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const [taskData, nodesData] = await Promise.all([
          getTaskDetail(id),
          getTaskNodes(id),
        ]);
        setTask(taskData);
        setNodes(nodesData.nodes);
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#1a1a2e] flex items-center justify-center">
        <span className="text-[12px] font-mono text-gray-500">加载中...</span>
      </div>
    );
  }

  if (!task) {
    return (
      <div className="min-h-screen bg-[#1a1a2e] flex flex-col items-center justify-center gap-4">
        <span className="text-[12px] font-mono text-red-400">任务不存在</span>
        <Link href="/history" className="text-[10px] font-mono text-cyan-400">&larr; 返回列表</Link>
      </div>
    );
  }

  const st = STATUS_LABEL[task.status] || STATUS_LABEL.pending;
  const positioning = task.input_data?.positioning || "(无)";
  const resultData = task.result_data as Record<string, unknown> | null;

  return (
    <div className="min-h-screen bg-[#1a1a2e] text-gray-200 font-mono">
      {/* Header */}
      <header className="bg-[#2a2a4a] border-b border-gray-700 px-6 py-3 flex items-center gap-4">
        <Link href="/history" className="text-cyan-400 hover:text-cyan-300 text-[12px]">
          &larr; 历史任务
        </Link>
        <span className="text-[14px] text-gray-300 tracking-widest">任务详情</span>
      </header>

      <main className="max-w-[800px] mx-auto p-6 space-y-6">
        {/* Task summary */}
        <section className="bg-gray-900/50 border border-gray-700 rounded-sm p-4">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-[9px] text-gray-500 mb-1">{task.task_id}</div>
              <div className="text-[12px] text-gray-200">{positioning}</div>
            </div>
            <span className={`text-[11px] ${st.color}`}>{st.text}</span>
          </div>
          <div className="flex gap-4 mt-3 text-[9px] text-gray-500">
            <span>创建: {task.created_at?.replace("T", " ").slice(0, 19)}</span>
            {task.started_at && <span>开始: {task.started_at.replace("T", " ").slice(0, 19)}</span>}
            {task.elapsed_seconds !== null && <span>耗时: {task.elapsed_seconds.toFixed(1)}s</span>}
            {task.total_tokens !== null && task.total_tokens > 0 && <span>Tokens: {task.total_tokens}</span>}
          </div>
          {task.error_message && (
            <div className="mt-2 text-[10px] text-red-400 bg-red-900/20 border border-red-800/30 rounded-sm p-2">
              {task.error_message}
            </div>
          )}
        </section>

        {/* Node runs */}
        <section>
          <div className="text-[10px] text-cyan-400/80 mb-2 border-b border-gray-700/50 pb-1">
            执行节点
          </div>
          <div className="space-y-2">
            {nodes.map((node) => {
              const nst = STATUS_LABEL[node.status] || STATUS_LABEL.pending;
              const isExpanded = expandedNode === node.node_id;
              return (
                <div key={node.node_id} className="bg-gray-900/30 border border-gray-700/50 rounded-sm">
                  <button
                    onClick={() => setExpandedNode(isExpanded ? null : node.node_id)}
                    className="w-full px-3 py-2 flex items-center justify-between text-left hover:bg-gray-800/30"
                  >
                    <div className="flex items-center gap-2">
                      <span className={`w-[6px] h-[6px] rounded-full ${
                        node.status === "completed" ? "bg-green-500" :
                        node.status === "running" ? "bg-yellow-500 animate-pulse" :
                        node.status === "failed" ? "bg-red-500" : "bg-gray-600"
                      }`} />
                      <span className="text-[11px] text-gray-300">{node.node_id}</span>
                      <span className="text-[9px] text-gray-500">({node.agent_id})</span>
                    </div>
                    <div className="flex items-center gap-3">
                      {node.degraded && (
                        <span className="text-[8px] text-orange-400 border border-orange-600/30 px-1 rounded-sm">降级</span>
                      )}
                      {node.elapsed_seconds !== null && (
                        <span className="text-[9px] text-gray-500">{node.elapsed_seconds.toFixed(2)}s</span>
                      )}
                      <span className={`text-[9px] ${nst.color}`}>{nst.text}</span>
                      <span className="text-[8px] text-gray-500">{isExpanded ? "▲" : "▼"}</span>
                    </div>
                  </button>
                  {isExpanded && (
                    <div className="px-3 pb-3 border-t border-gray-700/30">
                      {node.error_message && (
                        <div className="mt-2 text-[9px] text-red-400">{node.error_message}</div>
                      )}
                      {node.output_data && (
                        <pre className="mt-2 text-[9px] text-gray-400 bg-gray-800/50 p-2 rounded-sm overflow-auto max-h-[200px]">
                          {JSON.stringify(node.output_data, null, 2)}
                        </pre>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>

        {/* Result data */}
        {resultData && (
          <section>
            <div className="text-[10px] text-cyan-400/80 mb-2 border-b border-gray-700/50 pb-1">
              产出结果
            </div>
            <pre className="text-[9px] text-gray-400 bg-gray-900/50 border border-gray-700 rounded-sm p-3 overflow-auto max-h-[400px]">
              {JSON.stringify(resultData, null, 2)}
            </pre>
          </section>
        )}
      </main>
    </div>
  );
}
