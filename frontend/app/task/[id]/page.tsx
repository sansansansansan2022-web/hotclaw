"use client";

import { useState, useEffect, use, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getTaskDetail, getTaskNodes, rerunTask } from "@/lib/api";
import type {
  TaskDetail,
  NodeRun,
  TaskResultData,
  AccountProfile,
  HotTopic,
  TopicCandidate,
  TitleCandidate,
  AuditResult,
} from "@/types";
import { useTaskSSE } from "@/hooks/useTaskSSE";
import WeChatArticle, { LiveProgress, type ArticleContent } from "@/components/WeChatArticle";

const STATUS_LABEL: Record<string, { text: string; color: string; bg: string }> = {
  pending: { text: "等待中", color: "text-gray-400", bg: "bg-gray-700" },
  running: { text: "执行中", color: "text-yellow-400", bg: "bg-yellow-700" },
  completed: { text: "已完成", color: "text-green-400", bg: "bg-green-700" },
  failed: { text: "失败", color: "text-red-400", bg: "bg-red-700" },
  skipped: { text: "跳过", color: "text-gray-500", bg: "bg-gray-600" },
};

const RISK_LABEL: Record<string, { text: string; color: string; bg: string }> = {
  low: { text: "低风险", color: "text-green-400", bg: "bg-green-900/40 border-green-700" },
  medium: { text: "中风险", color: "text-yellow-400", bg: "bg-yellow-900/40 border-yellow-700" },
  high: { text: "高风险", color: "text-red-400", bg: "bg-red-900/40 border-red-700" },
  unknown: { text: "未知", color: "text-gray-400", bg: "bg-gray-800/40 border-gray-700" },
};

export default function TaskDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [nodes, setNodes] = useState<NodeRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedNode, setExpandedNode] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "article" | "details">("overview");
  const [rerunning, setRerunning] = useState(false);

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

  // 重跑任务
  const handleRerun = async () => {
    if (!task || rerunning) return;
    setRerunning(true);
    try {
      const data = await rerunTask(task.task_id);
      router.push(`/newsroom?taskId=${data.task_id}`);
    } catch (e) {
      alert(`重跑失败: ${e instanceof Error ? e.message : "未知错误"}`);
      setRerunning(false);
    }
  };

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
        <div className="text-6xl mb-4">?</div>
        <span className="text-gray-400 font-medium">任务不存在</span>
        <Link href="/history" className="text-cyan-400 hover:text-cyan-300 transition-colors">
          &larr; 返回列表
        </Link>
      </div>
    );
  }

  const st = STATUS_LABEL[task.status] || STATUS_LABEL.pending;
  const positioning = task.input_data?.positioning || "(无)";
  const resultData = task.result_data as TaskResultData | null;
  const isRunning = task.status === "running" || liveNodes.some((n) => n.status === "running");
  const canRerun = task.status === "completed" || task.status === "failed";

  // 提取文章内容
  const articleContent: ArticleContent | null =
    resultData?.content
      ? {
          content_markdown: resultData.content.content_markdown || "",
          word_count: resultData.content.word_count || 0,
          structure: resultData.content.structure,
          tags: resultData.content.tags || [],
        }
      : null;

  // 提取文章标题
  const articleTitle: string | null =
    resultData?.titles?.titles?.[0]?.text || null;

  // 类型安全的辅助
  const rd = resultData || {};

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
              <span>&larr;</span>
              <span>历史任务</span>
            </Link>
            <span className="text-slate-500">/</span>
            <span className="text-white font-medium">任务详情</span>
          </div>
          <div className="flex items-center gap-3">
            {canRerun && (
              <button
                onClick={handleRerun}
                disabled={rerunning}
                className="px-3 py-1.5 text-sm bg-cyan-600 hover:bg-cyan-500 disabled:bg-cyan-800 disabled:text-cyan-400 rounded-lg transition-colors flex items-center gap-2"
              >
                {rerunning ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    重跑中...
                  </>
                ) : (
                  <>
                    <span>&#8635;</span> 重跑任务
                  </>
                )}
              </button>
            )}
            <div className={`px-3 py-1 rounded-full text-sm font-medium ${st.bg} ${st.color}`}>
              {isRunning ? " 执行中" : st.text}
            </div>
          </div>
        </div>
      </header>

      {/* 主内容区域 */}
      <main
        className="max-w-5xl mx-auto p-6 space-y-6 overflow-y-auto"
        style={{ maxHeight: "calc(100vh - 80px)" }}
      >
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
              <span>&#128197;</span>
              创建: {task.created_at?.replace("T", " ").slice(0, 19)}
            </span>
            {task.started_at && (
              <span className="flex items-center gap-2">
                <span>&#128640;</span>
                开始: {task.started_at.replace("T", " ").slice(0, 19)}
              </span>
            )}
            {task.completed_at && (
              <span className="flex items-center gap-2">
                <span>&#9989;</span>
                完成: {task.completed_at.replace("T", " ").slice(0, 19)}
              </span>
            )}
            {task.elapsed_seconds !== null && (
              <span className="flex items-center gap-2">
                <span>&#9201;&#65039;</span>
                耗时: {task.elapsed_seconds.toFixed(1)}s
              </span>
            )}
            {task.total_tokens !== null && task.total_tokens > 0 && (
              <span className="flex items-center gap-2">
                <span>&#128142;</span>
                Tokens: {task.total_tokens.toLocaleString()}
              </span>
            )}
          </div>

          {task.error_message && (
            <div className="mt-4 p-4 bg-red-900/30 border border-red-800/50 rounded-lg">
              <div className="flex items-center gap-2 text-red-400 mb-2">
                <span>&#10060;</span>
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
              <span>&#9888;</span>
              <span className="font-medium">执行错误</span>
            </div>
            <p className="text-sm text-red-300">{taskError}</p>
          </div>
        )}

        {/* Tab 切换 */}
        <div className="flex gap-2 border-b border-slate-700 pb-2">
          <button
            onClick={() => setActiveTab("overview")}
            className={`px-4 py-2 rounded-t-lg transition-all ${
              activeTab === "overview"
                ? "bg-cyan-500/20 text-cyan-400 border-b-2 border-cyan-400"
                : "text-slate-400 hover:text-white hover:bg-slate-700/50"
            }`}
          >
            &#128200; 结果总览
          </button>
          <button
            onClick={() => setActiveTab("article")}
            className={`px-4 py-2 rounded-t-lg transition-all ${
              activeTab === "article"
                ? "bg-cyan-500/20 text-cyan-400 border-b-2 border-cyan-400"
                : "text-slate-400 hover:text-white hover:bg-slate-700/50"
            }`}
          >
            &#128240; 文章预览
          </button>
          <button
            onClick={() => setActiveTab("details")}
            className={`px-4 py-2 rounded-t-lg transition-all ${
              activeTab === "details"
                ? "bg-cyan-500/20 text-cyan-400 border-b-2 border-cyan-400"
                : "text-slate-400 hover:text-white hover:bg-slate-700/50"
            }`}
          >
            &#128736; 节点详情
          </button>
        </div>

        {/* ===== 结果总览 Tab ===== */}
        {activeTab === "overview" && (
          <div className="space-y-6">
            {/* 无结果时 */}
            {!resultData && task.status !== "running" && (
              <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-12 border border-slate-700 text-center">
                <div className="text-6xl mb-4">&#128196;</div>
                <h3 className="text-xl font-medium text-white mb-2">暂无生成结果</h3>
                <p className="text-slate-400">
                  {isRunning
                    ? "正在生成中，请稍候..."
                    : "任务执行失败，未能生成结果"}
                </p>
              </div>
            )}

            {/* 账号画像 */}
            {rd.profile && (
              <ResultSection title="账号画像" icon="&#128100;">
                <ProfileCard profile={rd.profile as AccountProfile} />
              </ResultSection>
            )}

            {/* 热点候选 */}
            {rd.hot_topics?.hot_topics && (
              <ResultSection
                title={`热点候选 (${(rd.hot_topics.hot_topics as HotTopic[]).length})`}
                icon="&#128293;"
              >
                <HotTopicsList topics={rd.hot_topics.hot_topics as HotTopic[]} />
              </ResultSection>
            )}

            {/* 选题建议 */}
            {rd.topics?.topics && (
              <ResultSection
                title={`选题建议 (${(rd.topics.topics as TopicCandidate[]).length})`}
                icon="&#128221;"
              >
                <TopicsList topics={rd.topics.topics as TopicCandidate[]} />
              </ResultSection>
            )}

            {/* 标题候选 */}
            {rd.titles?.titles && (
              <ResultSection
                title={`标题候选 (${(rd.titles.titles as TitleCandidate[]).length})`}
                icon="&#128396;"
              >
                <TitlesList
                  selectedTopic={rd.titles.selected_topic}
                  titles={rd.titles.titles as TitleCandidate[]}
                />
              </ResultSection>
            )}

            {/* 审核结果 */}
            {rd.audit_result && (
              <ResultSection title="审核结果" icon="&#128737;">
                <AuditCard audit={rd.audit_result as AuditResult} />
              </ResultSection>
            )}

            {/* 正文摘要 */}
            {rd.content && (
              <ResultSection
                title={`正文草稿 (${(rd.content as { word_count?: number }).word_count || 0}字)`}
                icon="&#128462;"
              >
                <div className="text-slate-400 text-sm">
                  {(rd.content as { content_markdown?: string }).content_markdown
                    ? `${(rd.content as { content_markdown: string }).content_markdown.slice(0, 300)}...`
                    : "(无正文)"}
                </div>
                {(rd.content as { tags?: string[] }).tags &&
                  ((rd.content as { tags: string[] }).tags).length > 0 && (
                    <div className="flex flex-wrap gap-2 mt-3">
                      {((rd.content as { tags: string[] }).tags).map((tag: string) => (
                        <span
                          key={tag}
                          className="px-2 py-0.5 bg-slate-700 text-slate-300 text-xs rounded"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
              </ResultSection>
            )}
          </div>
        )}

        {/* ===== 文章预览 Tab ===== */}
        {activeTab === "article" && (
          <div>
            {articleContent && articleContent.content_markdown ? (
              <WeChatArticle content={articleContent} title={articleTitle || ""} />
            ) : (
              <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-12 border border-slate-700 text-center">
                <div className="text-6xl mb-4">&#128221;</div>
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

        {/* ===== 节点详情 Tab ===== */}
        {activeTab === "details" && (
          <div className="space-y-4">
            <section>
              <div className="text-sm text-cyan-400/80 mb-3 flex items-center gap-2">
                <span>&#128260;</span>
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
                              &#9650; 降级
                            </span>
                          )}
                          {node.elapsed_seconds !== null && (
                            <span className="text-xs text-slate-500">
                              {node.elapsed_seconds.toFixed(2)}s
                            </span>
                          )}
                          <span className={`text-sm ${nst.color}`}>{nst.text}</span>
                          <span className="text-slate-500 text-sm">
                            {isExpanded ? "\u25B2" : "\u25BC"}
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

            {resultData && (
              <section>
                <div className="text-sm text-cyan-400/80 mb-3 flex items-center gap-2">
                  <span>&#128230;</span>
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
            <span>&larr;</span>
            <span>返回编辑部</span>
          </Link>
          <Link
            href="/"
            className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors text-sm"
          >
            &#127968; 首页
          </Link>
        </div>
      </main>
    </div>
  );
}

// =============================================================================
// 子组件
// =============================================================================

function ResultSection({
  title,
  icon,
  children,
}: {
  title: string;
  icon: string;
  children: React.ReactNode;
}) {
  return (
    <section className="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700 overflow-hidden">
      <div className="px-5 py-3 border-b border-slate-700 flex items-center gap-2 text-sm font-medium text-cyan-400/90">
        <span dangerouslySetInnerHTML={{ __html: icon }} />
        {title}
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function ProfileCard({ profile }: { profile: AccountProfile }) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-4">
        <div className="bg-slate-900/50 rounded-lg px-4 py-2 min-w-[120px]">
          <div className="text-xs text-slate-500 mb-1">主领域</div>
          <div className="text-white font-medium">{profile.domain}</div>
        </div>
        <div className="bg-slate-900/50 rounded-lg px-4 py-2 min-w-[120px]">
          <div className="text-xs text-slate-500 mb-1">细分领域</div>
          <div className="text-white font-medium">{profile.subdomain}</div>
        </div>
        <div className="bg-slate-900/50 rounded-lg px-4 py-2 min-w-[120px]">
          <div className="text-xs text-slate-500 mb-1">文风调性</div>
          <div className="text-white font-medium">{profile.tone}</div>
        </div>
        <div className="bg-slate-900/50 rounded-lg px-4 py-2 min-w-[120px]">
          <div className="text-xs text-slate-500 mb-1">内容类型</div>
          <div className="text-white font-medium">{profile.content_style}</div>
        </div>
      </div>
      {profile.target_audience && (
        <div className="bg-slate-900/50 rounded-lg px-4 py-2">
          <div className="text-xs text-slate-500 mb-1">目标受众</div>
          <div className="text-white">
            {profile.target_audience.age_range} | {profile.target_audience.occupation}
          </div>
          {profile.target_audience.interests && profile.target_audience.interests.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {profile.target_audience.interests.map((i) => (
                <span key={i} className="px-2 py-0.5 bg-cyan-900/40 text-cyan-300 text-xs rounded-full">
                  {i}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
      {profile.keywords && profile.keywords.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {profile.keywords.map((kw) => (
            <span key={kw} className="px-2 py-0.5 bg-purple-900/40 text-purple-300 text-xs rounded">
              {kw}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function HotTopicsList({ topics }: { topics: HotTopic[] }) {
  if (!topics || topics.length === 0) {
    return <div className="text-slate-500 text-sm">暂无热点数据</div>;
  }
  return (
    <div className="space-y-2">
      {topics.map((t, i) => (
        <div key={i} className="flex items-start gap-3 p-3 bg-slate-900/40 rounded-lg">
          <div className="flex-shrink-0 w-12 text-center">
            <div className="text-cyan-400 font-bold text-lg">{t.heat_score}</div>
            <div className="text-slate-500 text-xs">热度</div>
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-white font-medium text-sm">{t.title}</div>
            <div className="text-slate-400 text-xs mt-1">{t.summary}</div>
            <div className="flex items-center gap-3 mt-2">
              <span className="text-xs text-slate-500">{t.source}</span>
              <span
                className={`text-xs px-1.5 py-0.5 rounded ${
                  t.relevance_score >= 0.7
                    ? "bg-green-900/40 text-green-400"
                    : t.relevance_score >= 0.4
                    ? "bg-yellow-900/40 text-yellow-400"
                    : "bg-gray-800 text-gray-400"
                }`}
              >
                相关 {(t.relevance_score * 100).toFixed(0)}%
              </span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function TopicsList({ topics }: { topics: TopicCandidate[] }) {
  if (!topics || topics.length === 0) {
    return <div className="text-slate-500 text-sm">暂无选题数据</div>;
  }
  return (
    <div className="space-y-2">
      {topics.map((t, i) => (
        <div key={i} className="p-3 bg-slate-900/40 rounded-lg">
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-2">
              <span className="flex-shrink-0 w-5 h-5 rounded-full bg-cyan-500/20 text-cyan-400 text-xs flex items-center justify-center font-bold mt-0.5">
                {i + 1}
              </span>
              <div>
                <div className="text-white font-medium text-sm">{t.title}</div>
                <div className="text-slate-400 text-xs mt-1">{t.angle}</div>
              </div>
            </div>
            <div className="flex-shrink-0 text-right">
              <div className="text-cyan-400 font-bold">
                {(t.estimated_appeal * 100).toFixed(0)}%
              </div>
              <div className="text-slate-500 text-xs">吸引力</div>
            </div>
          </div>
          <div className="flex items-center gap-2 mt-2">
            <span className="px-2 py-0.5 bg-purple-900/40 text-purple-300 text-xs rounded">
              {t.hook}
            </span>
            <span className="px-2 py-0.5 bg-slate-700 text-slate-300 text-xs rounded">
              {t.target_emotion}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

function TitlesList({ selectedTopic, titles }: { selectedTopic?: string; titles: TitleCandidate[] }) {
  if (!titles || titles.length === 0) {
    return <div className="text-slate-500 text-sm">暂无标题数据</div>;
  }
  return (
    <div className="space-y-3">
      {selectedTopic && (
        <div className="text-xs text-slate-500 mb-2">
          基于选题: <span className="text-slate-300">{selectedTopic}</span>
        </div>
      )}
      {titles.map((t, i) => (
        <div key={i} className="flex items-start gap-3 p-3 bg-slate-900/40 rounded-lg">
          <span className="flex-shrink-0 w-6 h-6 rounded-full bg-yellow-500/20 text-yellow-400 text-xs flex items-center justify-center font-bold mt-0.5">
            {i + 1}
          </span>
          <div className="flex-1">
            <div className="text-white font-medium">{t.text}</div>
            <div className="text-slate-400 text-xs mt-1">{t.reasoning}</div>
          </div>
          <div className="flex-shrink-0 text-right">
            <div className={`font-bold ${t.score >= 8 ? "text-green-400" : t.score >= 6 ? "text-yellow-400" : "text-gray-400"}`}>
              {t.score.toFixed(1)}
            </div>
            <span className="text-xs text-slate-500">{t.style}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function AuditCard({ audit }: { audit: AuditResult }) {
  const risk = RISK_LABEL[audit.risk_level] || RISK_LABEL.unknown;
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-4">
        <div
          className={`px-4 py-2 rounded-lg font-medium border ${risk.bg} ${risk.color}`}
        >
          {audit.passed ? "\u2705 可发布" : "\u26A0\uFE0F 需修改"} &nbsp;
          {risk.text}
        </div>
      </div>
      {audit.overall_comment && (
        <div className="text-slate-300 text-sm bg-slate-900/50 rounded-lg px-4 py-3">
          {audit.overall_comment}
        </div>
      )}
      {audit.issues && audit.issues.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs text-slate-500 font-medium">发现问题 ({audit.issues.length})</div>
          {audit.issues.map((issue, i) => {
            const sev = RISK_LABEL[issue.severity] || RISK_LABEL.unknown;
            return (
              <div key={i} className="flex items-start gap-3 p-3 bg-slate-900/40 rounded-lg border border-slate-700/50">
                <span className={`flex-shrink-0 px-1.5 py-0.5 text-xs rounded border ${sev.bg} ${sev.color}`}>
                  {issue.severity}
                </span>
                <div className="flex-1">
                  <div className="text-white text-sm">
                    {issue.type !== "system" && (
                      <span className="text-slate-400 text-xs mr-2">[{issue.type}]</span>
                    )}
                    {issue.description}
                  </div>
                  {issue.location && (
                    <div className="text-slate-500 text-xs mt-1">位置: {issue.location}</div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
