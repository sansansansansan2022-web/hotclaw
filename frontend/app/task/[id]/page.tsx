"use client";

import { useState, useEffect, use, useCallback } from "react";
import Link from "next/link";
import { getTaskDetail, getTaskNodes } from "@/lib/api";
import type { TaskDetail, NodeRun } from "@/types";
import { useTaskSSE } from "@/hooks/useTaskSSE";
import WeChatArticle, { LiveProgress, type ArticleContent } from "@/components/WeChatArticle";

const STATUS_LABEL: Record<string, { text: string; color: string; bg: string }> = {
  pending: { text: "等待中", color: "text-gray-400", bg: "bg-gray-700" },
  running: { text: "执行中", color: "text-yellow-400", bg: "bg-yellow-700" },
  completed: { text: "已完成", color: "text-green-400", bg: "bg-green-700" },
  failed: { text: "失败", color: "text-red-400", bg: "bg-red-700" },
  skipped: { text: "跳过", color: "text-gray-500", bg: "bg-gray-600" },
};

export default function TaskDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [nodes, setNodes] = useState<NodeRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedNode, setExpandedNode] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"article" | "details">("article");

  // SSE 实时进度
  const { nodes: liveNodes, taskDone, taskError } = useTaskSSE(id);

  // 加载任务数据
  const loadTask = useCallback(async () => {
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
  }, [id]);

  useEffect(() => {
    loadTask();
  }, [loadTask]);

  // 当 SSE 显示任务完成时，重新加载数据
  useEffect(() => {
    if (taskDone) {
      loadTask();
    }
  }, [taskDone, loadTask]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin mx-auto mb-4" />
          <span className="text-gray-400 font-medium">加载中...</span>
        </div>
      </div>
    );
  }

  if (!task) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex flex-col items-center justify-center gap-4">
        <div className="text-6xl mb-4">😕</div>
        <span className="text-gray-400 font-medium">任务不存在</span>
        <Link href="/history" className="text-cyan-400 hover:text-cyan-300 transition-colors">
          &larr; 返回列表
        </Link>
      </div>
    );
  }

  const st = STATUS_LABEL[task.status] || STATUS_LABEL.pending;
  const positioning = task.input_data?.positioning || "(无)";
  const resultData = task.result_data as Record<string, unknown> | null;
  const isRunning = task.status === "running" || liveNodes.some((n) => n.status === "running");

  // 提取文章内容
  const articleContent: ArticleContent | null = resultData?.content
    ? {
        content_markdown: (resultData.content as Record<string, unknown>).content_markdown as string || "",
        word_count: (resultData.content as Record<string, unknown>).word_count as number || 0,
        structure: (resultData.content as Record<string, unknown>).structure as ArticleContent["structure"],
        tags: (resultData.content as Record<string, unknown>).tags as string[] || [],
      }
    : null;

  // 提取文章标题
  const articleTitle = resultData?.titles
    ? (((resultData.titles as Record<string, unknown>).titles as Array<{ text: string; score: number }>) || [])[0]?.text
    : null;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
      {/* Header */}
      <header className="bg-slate-800/80 backdrop-blur-sm border-b border-slate-700 px-6 py-4 sticky top-0 z-20">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              href="/history"
              className="text-cyan-400 hover:text-cyan-300 transition-colors flex items-center gap-2"
            >
              <span>←</span>
              <span>历史任务</span>
            </Link>
            <span className="text-slate-500">/</span>
            <span className="text-white font-medium">任务详情</span>
          </div>
          <div className={`px-3 py-1 rounded-full text-sm font-medium ${st.bg} ${st.color}`}>
            {isRunning ? "⚡ 执行中" : st.text}
          </div>
        </div>
      </header>

      {/* 主内容区域 - 可滚动 */}
      <main className="max-w-5xl mx-auto p-6 space-y-6 overflow-y-auto" style={{ maxHeight: "calc(100vh - 80px)" }}>
        {/* 任务概览 */}
        <section className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 border border-slate-700">
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="text-xs text-slate-500 font-mono mb-1">{task.task_id}</div>
              <div className="text-lg text-white font-medium">{positioning}</div>
            </div>
          </div>

          <div className="flex flex-wrap gap-4 text-sm text-slate-400">
            <span className="flex items-center gap-2">
              <span>📅</span>
              创建: {task.created_at?.replace("T", " ").slice(0, 19)}
            </span>
            {task.started_at && (
              <span className="flex items-center gap-2">
                <span>🚀</span>
                开始: {task.started_at.replace("T", " ").slice(0, 19)}
              </span>
            )}
            {task.elapsed_seconds !== null && (
              <span className="flex items-center gap-2">
                <span>⏱️</span>
                耗时: {task.elapsed_seconds.toFixed(1)}s
              </span>
            )}
            {task.total_tokens !== null && task.total_tokens > 0 && (
              <span className="flex items-center gap-2">
                <span>💎</span>
                Tokens: {task.total_tokens.toLocaleString()}
              </span>
            )}
          </div>

          {task.error_message && (
            <div className="mt-4 p-4 bg-red-900/30 border border-red-800/50 rounded-lg">
              <div className="flex items-center gap-2 text-red-400 mb-2">
                <span>❌</span>
                <span className="font-medium">错误信息</span>
              </div>
              <pre className="text-sm text-red-300/80 whitespace-pre-wrap">{task.error_message}</pre>
            </div>
          )}
        </section>

        {/* SSE 实时进度 */}
        {(isRunning || taskDone) && liveNodes.length > 0 && (
          <LiveProgress nodes={liveNodes} taskStatus={task.status} />
        )}

        {/* 任务错误提示 */}
        {taskError && (
          <div className="p-4 bg-red-900/30 border border-red-800/50 rounded-lg">
            <div className="flex items-center gap-2 text-red-400 mb-2">
              <span>⚠️</span>
              <span className="font-medium">执行错误</span>
            </div>
            <p className="text-sm text-red-300">{taskError}</p>
          </div>
        )}

        {/* Tab 切换 */}
        <div className="flex gap-2 border-b border-slate-700 pb-2">
          <button
            onClick={() => setActiveTab("article")}
            className={`px-4 py-2 rounded-t-lg transition-all ${
              activeTab === "article"
                ? "bg-cyan-500/20 text-cyan-400 border-b-2 border-cyan-400"
                : "text-slate-400 hover:text-white hover:bg-slate-700/50"
            }`}
          >
            📰 文章预览
          </button>
          <button
            onClick={() => setActiveTab("details")}
            className={`px-4 py-2 rounded-t-lg transition-all ${
              activeTab === "details"
                ? "bg-cyan-500/20 text-cyan-400 border-b-2 border-cyan-400"
                : "text-slate-400 hover:text-white hover:bg-slate-700/50"
            }`}
          >
            🔧 节点详情
          </button>
        </div>

        {/* 文章预览 */}
        {activeTab === "article" && (
          <div>
            {articleContent && articleContent.content_markdown ? (
              <WeChatArticle content={articleContent} title={articleTitle as string} />
            ) : (
              <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-12 border border-slate-700 text-center">
                <div className="text-6xl mb-4">📝</div>
                <h3 className="text-xl font-medium text-white mb-2">文章尚未生成</h3>
                <p className="text-slate-400">
                  {task.status === "running" ? "正在生成中，请稍候..." : "任务完成后将展示文章内容"}
                </p>
                {task.status === "running" && (
                  <div className="mt-6">
                    <div className="w-12 h-12 border-4 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin mx-auto" />
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* 节点详情 */}
        {activeTab === "details" && (
          <div className="space-y-4">
            {/* 执行节点 */}
            <section>
              <div className="text-sm text-cyan-400/80 mb-3 flex items-center gap-2">
                <span>🔄</span>
                <span>执行节点 ({nodes.length})</span>
              </div>
              <div className="space-y-2">
                {nodes.map((node, index) => {
                  const nst = STATUS_LABEL[node.status] || STATUS_LABEL.pending;
                  const isExpanded = expandedNode === node.node_id;
                  return (
                    <div
                      key={node.node_id}
                      className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-lg overflow-hidden"
                    >
                      <button
                        onClick={() => setExpandedNode(isExpanded ? null : node.node_id)}
                        className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-700/30 transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <span className="w-6 h-6 rounded-full bg-slate-700 text-xs flex items-center justify-center text-slate-400">
                            {index + 1}
                          </span>
                          <span
                            className={`w-2.5 h-2.5 rounded-full ${
                              node.status === "completed"
                                ? "bg-green-500"
                                : node.status === "running"
                                ? "bg-yellow-500 animate-pulse"
                                : node.status === "failed"
                                ? "bg-red-500"
                                : "bg-gray-600"
                            }`}
                          />
                          <span className="text-white font-medium">{node.node_id}</span>
                          <span className="text-xs text-slate-500">({node.agent_id})</span>
                        </div>
                        <div className="flex items-center gap-3">
                          {node.degraded && (
                            <span className="text-xs px-2 py-0.5 bg-orange-900/50 text-orange-400 rounded">
                              降级
                            </span>
                          )}
                          {node.elapsed_seconds !== null && (
                            <span className="text-xs text-slate-500">
                              {node.elapsed_seconds.toFixed(2)}s
                            </span>
                          )}
                          <span className={`text-sm ${nst.color}`}>{nst.text}</span>
                          <span className="text-slate-500 text-sm">
                            {isExpanded ? "▲" : "▼"}
                          </span>
                        </div>
                      </button>
                      {isExpanded && (
                        <div className="px-4 pb-4 border-t border-slate-700/50">
                          {node.error_message && (
                            <div className="mt-3 p-3 bg-red-900/20 border border-red-800/30 rounded-lg">
                              <div className="text-xs text-red-400 mb-1">错误信息</div>
                              <pre className="text-xs text-red-300 whitespace-pre-wrap">
                                {node.error_message}
                              </pre>
                            </div>
                          )}
                          {node.output_data && (
                            <div className="mt-3">
                              <div className="text-xs text-slate-500 mb-2">输出数据</div>
                              <pre className="text-xs text-slate-400 bg-slate-900/50 p-3 rounded-lg overflow-auto max-h-[300px]">
                                {JSON.stringify(node.output_data, null, 2)}
                              </pre>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>

            {/* 原始结果数据 */}
            {resultData && (
              <section>
                <div className="text-sm text-cyan-400/80 mb-3 flex items-center gap-2">
                  <span>📦</span>
                  <span>完整结果数据</span>
                </div>
                <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-lg p-4">
                  <pre className="text-xs text-slate-400 overflow-auto max-h-[400px]">
                    {JSON.stringify(resultData, null, 2)}
                  </pre>
                </div>
              </section>
            )}
          </div>
        )}

        {/* 底部导航 */}
        <div className="flex justify-between items-center pt-6 border-t border-slate-700/50">
          <Link
            href="/newsroom"
            className="text-slate-400 hover:text-white transition-colors flex items-center gap-2"
          >
            <span>←</span>
            <span>返回编辑部</span>
          </Link>
          <Link
            href="/"
            className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors text-sm"
          >
            🏠 首页
          </Link>
        </div>
      </main>
    </div>
  );
}
