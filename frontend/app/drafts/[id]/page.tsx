"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getDraft, confirmPublishDraft, discardDraft, rejectDraft, rerunFromDraft } from "@/lib/api";
import type { DraftDetail } from "@/types";

export default function DraftDetailPage() {
  const params = useParams();
  const draftId = Number(params.id);

  const [draft, setDraft] = useState<DraftDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"content" | "candidates">("content");

  useEffect(() => {
    loadDraft();
  }, [draftId]);

  async function loadDraft() {
    setLoading(true);
    setError(null);
    try {
      const data = await getDraft(draftId);
      setDraft(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirmPublish() {
    if (!confirm("确定要确认发布这篇草稿吗？")) return;
    setActionLoading("confirm");
    try {
      await confirmPublishDraft(draftId);
      alert("发布确认成功！");
      loadDraft();
    } catch (e) {
      alert(e instanceof Error ? e.message : "确认发布失败");
    } finally {
      setActionLoading(null);
    }
  }

  async function handleDiscard() {
    if (!confirm("确定要废弃这篇草稿吗？此操作不可撤销。")) return;
    setActionLoading("discard");
    try {
      await discardDraft(draftId);
      alert("草稿已废弃");
      window.location.href = "/drafts";
    } catch (e) {
      alert(e instanceof Error ? e.message : "废弃失败");
    } finally {
      setActionLoading(null);
    }
  }

  async function handleReject() {
    if (!confirm("确定要拒绝这篇草稿吗？")) return;
    setActionLoading("reject");
    try {
      await rejectDraft(draftId);
      alert("草稿已拒绝");
      loadDraft();
    } catch (e) {
      alert(e instanceof Error ? e.message : "拒绝失败");
    } finally {
      setActionLoading(null);
    }
  }

  async function handleRerun() {
    if (!confirm("确定要基于这篇草稿重新生成内容吗？")) return;
    setActionLoading("rerun");
    try {
      const result = await rerunFromDraft(draftId);
      alert(`已创建新任务: ${result.new_task_id}`);
      window.location.href = `/task/${result.new_task_id}`;
    } catch (e) {
      alert(e instanceof Error ? e.message : "重跑失败");
    } finally {
      setActionLoading(null);
    }
  }

  function formatDate(dateStr: string | null) {
    if (!dateStr) return "-";
    return new Date(dateStr).toLocaleString("zh-CN");
  }

  function getDraftStatusBadge(status: string) {
    switch (status) {
      case "pending_review":
        return <span className="px-3 py-1 text-sm rounded-full bg-yellow-900/30 text-yellow-400 border border-yellow-700">待确认</span>;
      case "approved":
        return <span className="px-3 py-1 text-sm rounded-full bg-green-900/30 text-green-400 border border-green-700">已批准</span>;
      case "rejected":
        return <span className="px-3 py-1 text-sm rounded-full bg-red-900/30 text-red-400 border border-red-700">已拒绝</span>;
      case "discarded":
        return <span className="px-3 py-1 text-sm rounded-full bg-slate-700/50 text-slate-400 border border-slate-600">已废弃</span>;
      case "draft":
        return <span className="px-3 py-1 text-sm rounded-full bg-slate-700/50 text-slate-300 border border-slate-600">草稿</span>;
      default:
        return <span className="px-3 py-1 text-sm rounded-full bg-slate-700/50 text-slate-400 border border-slate-600">{status}</span>;
    }
  }

  function getPublishStatusBadge(status: string) {
    switch (status) {
      case "published":
        return <span className="px-3 py-1 text-sm rounded-full bg-green-900/30 text-green-400 border border-green-700">已发布</span>;
      case "pending":
        return <span className="px-3 py-1 text-sm rounded-full bg-yellow-900/30 text-yellow-400 border border-yellow-700">发布中</span>;
      case "failed":
        return <span className="px-3 py-1 text-sm rounded-full bg-red-900/30 text-red-400 border border-red-700">发布失败</span>;
      case "not_published":
      default:
        return <span className="px-3 py-1 text-sm rounded-full bg-slate-700/50 text-slate-400 border border-slate-600">未发布</span>;
    }
  }

  function getAuditBadge(passed: boolean, riskLevel: string) {
    if (passed) {
      return <span className="px-3 py-1 text-sm rounded-full bg-green-900/30 text-green-400 border border-green-700">审核通过</span>;
    }
    const riskColor = riskLevel === "high" ? "red" : riskLevel === "medium" ? "yellow" : "slate";
    return (
      <span className={`px-3 py-1 text-sm rounded-full bg-${riskColor}-900/30 text-${riskColor}-400 border border-${riskColor}-700`}>
        风险提示
      </span>
    );
  }

  // 简单 Markdown 转 HTML（用于预览）
  function renderMarkdown(content: string): string {
    return content
      // 标题
      .replace(/^### (.+)$/gm, '<h3 class="text-lg font-semibold text-white mt-4 mb-2">$1</h3>')
      .replace(/^## (.+)$/gm, '<h2 class="text-xl font-semibold text-white mt-6 mb-3">$1</h2>')
      .replace(/^# (.+)$/gm, '<h1 class="text-2xl font-bold text-white mt-8 mb-4">$1</h1>')
      // 粗体和斜体
      .replace(/\*\*(.+?)\*\*/g, '<strong class="font-bold text-white">$1</strong>')
      .replace(/\*(.+?)\*/g, '<em class="italic text-slate-300">$1</em>')
      // 引用
      .replace(/^> (.+)$/gm, '<blockquote class="border-l-4 border-cyan-600 pl-4 py-2 my-4 bg-slate-800/50 text-slate-300 italic">$1</blockquote>')
      // 代码块
      .replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre class="bg-slate-900 rounded-lg p-4 my-4 overflow-x-auto"><code class="text-sm text-slate-300">$2</code></pre>')
      // 行内代码
      .replace(/`(.+?)`/g, '<code class="bg-slate-800 text-cyan-400 px-1 py-0.5 rounded text-sm">$1</code>')
      // 列表
      .replace(/^- (.+)$/gm, '<li class="ml-4 text-slate-300 list-disc">$1</li>')
      .replace(/^(\d+)\. (.+)$/gm, '<li class="ml-4 text-slate-300 list-decimal">$2</li>')
      // 段落
      .replace(/\n\n/g, '</p><p class="text-slate-300 leading-relaxed my-3">')
      // 换行
      .replace(/\n/g, "<br/>");
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white flex items-center justify-center">
        <div className="text-slate-400">加载中...</div>
      </div>
    );
  }

  if (error || !draft) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
        <header className="bg-slate-800/80 backdrop-blur-sm border-b border-slate-700 px-6 py-4 sticky top-0 z-20">
          <div className="max-w-5xl mx-auto flex items-center gap-4">
            <Link href="/drafts" className="text-cyan-400 hover:text-cyan-300 transition-colors flex items-center gap-2">
              <span>&larr;</span>
              <span>返回草稿箱</span>
            </Link>
          </div>
        </header>
        <main className="max-w-5xl mx-auto p-6">
          <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 text-red-300">
            {error || "草稿不存在"}
          </div>
        </main>
      </div>
    );
  }

  const isPendingReview = draft.draft_status === "pending_review";
  const isDiscarded = draft.draft_status === "discarded";
  const isRejected = draft.draft_status === "rejected";
  const isPublished = draft.publish_status === "published";
  // Terminal states: discarded, rejected, or published cannot be operated on
  const isTerminal = isDiscarded || isRejected || isPublished;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
      {/* Header */}
      <header className="bg-slate-800/80 backdrop-blur-sm border-b border-slate-700 px-6 py-4 sticky top-0 z-20">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/drafts" className="text-cyan-400 hover:text-cyan-300 transition-colors flex items-center gap-2">
              <span>&larr;</span>
              <span>返回草稿箱</span>
            </Link>
          </div>
          <div className="flex items-center gap-3">
            {getDraftStatusBadge(draft.draft_status)}
            {getPublishStatusBadge(draft.publish_status)}
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-5xl mx-auto p-6">
        {/* Title Section */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-white mb-2">{draft.title}</h1>
          <div className="flex flex-wrap items-center gap-4 text-sm text-slate-400">
            {draft.account_name && (
              <Link href={`/accounts/${draft.account_id}`} className="text-cyan-400 hover:underline">
                账号: {draft.account_name}
              </Link>
            )}
            <span>字数: {draft.word_count}</span>
            <span>来源: {draft.source_type === "semi_auto_task" ? "半自动任务" : "手动任务"}</span>
            <span>创建: {formatDate(draft.created_at)}</span>
            {draft.published_at && <span>发布: {formatDate(draft.published_at)}</span>}
          </div>
        </div>

        {/* Audit Result */}
        {draft.audit_result && (
          <div className="mb-6 bg-slate-800/60 border border-slate-700 rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-medium text-white">审核结果</h2>
              <div className="flex items-center gap-2">
                {getAuditBadge(draft.audit_result.passed, draft.audit_result.risk_level)}
                <span className="text-sm text-slate-400">风险等级: {draft.audit_result.risk_level}</span>
              </div>
            </div>
            {draft.audit_result.overall_comment && (
              <p className="text-slate-300 mb-3">{draft.audit_result.overall_comment}</p>
            )}
            {draft.audit_result.issues && draft.audit_result.issues.length > 0 && (
              <div className="space-y-2">
                {draft.audit_result.issues.map((issue: unknown, idx: number) => {
                  const i = issue as { type: string; description: string; severity: string };
                  return (
                    <div key={idx} className={`p-3 rounded-lg border ${
                      i.severity === "high" ? "bg-red-900/20 border-red-700" :
                      i.severity === "medium" ? "bg-yellow-900/20 border-yellow-700" :
                      "bg-slate-700/50 border-slate-600"
                    }`}>
                      <span className={`text-sm font-medium ${
                        i.severity === "high" ? "text-red-400" :
                        i.severity === "medium" ? "text-yellow-400" :
                        "text-slate-400"
                      }`}>
                        [{i.severity}] {i.type}
                      </span>
                      <p className="text-slate-300 text-sm mt-1">{i.description}</p>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Topic Summary */}
        {draft.selected_topic && (
          <div className="mb-6 bg-slate-800/60 border border-slate-700 rounded-xl p-5">
            <h2 className="text-lg font-medium text-white mb-2">选题摘要</h2>
            {draft.summary && (
              <p className="text-slate-300 mb-3">{draft.summary}</p>
            )}
            <div className="bg-slate-900/50 rounded-lg p-4">
              <p className="text-cyan-400 text-sm">📌 {draft.selected_topic}</p>
            </div>
          </div>
        )}

        {/* Content Tabs */}
        <div className="bg-slate-800/60 border border-slate-700 rounded-xl overflow-hidden">
          <div className="flex border-b border-slate-700">
            <button
              onClick={() => setActiveTab("content")}
              className={`px-6 py-3 text-sm font-medium transition-colors ${
                activeTab === "content"
                  ? "text-cyan-400 border-b-2 border-cyan-400 bg-slate-700/30"
                  : "text-slate-400 hover:text-white hover:bg-slate-700/30"
              }`}
            >
              正文内容
            </button>
            {draft.title_candidates && draft.title_candidates.length > 0 && (
              <button
                onClick={() => setActiveTab("candidates")}
                className={`px-6 py-3 text-sm font-medium transition-colors ${
                  activeTab === "candidates"
                    ? "text-cyan-400 border-b-2 border-cyan-400 bg-slate-700/30"
                    : "text-slate-400 hover:text-white hover:bg-slate-700/30"
                }`}
              >
                备选标题 ({draft.title_candidates.length})
              </button>
            )}
          </div>

          <div className="p-6">
            {activeTab === "content" && (
              <div className="prose prose-invert max-w-none">
                <div
                  className="text-slate-300 leading-relaxed"
                  dangerouslySetInnerHTML={{ __html: renderMarkdown(draft.content_markdown) }}
                />
              </div>
            )}
            {activeTab === "candidates" && draft.title_candidates && (
              <div className="space-y-4">
                {draft.title_candidates.map((candidate: unknown, idx: number) => {
                  const c = candidate as { text: string; style: string; score: number; reasoning: string };
                  return (
                    <div key={idx} className="bg-slate-900/50 rounded-lg p-4 border border-slate-700">
                      <div className="flex items-start justify-between mb-2">
                        <h3 className="text-white font-medium">{c.text}</h3>
                        <span className="text-sm text-cyan-400">评分: {c.score}/10</span>
                      </div>
                      <p className="text-xs text-slate-400 mb-2">风格: {c.style}</p>
                      <p className="text-sm text-slate-400">{c.reasoning}</p>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Tags */}
        {draft.tags && draft.tags.length > 0 && (
          <div className="mt-6 bg-slate-800/60 border border-slate-700 rounded-xl p-5">
            <h2 className="text-lg font-medium text-white mb-3">标签</h2>
            <div className="flex flex-wrap gap-2">
              {draft.tags.map((tag, idx) => (
                <span key={idx} className="px-3 py-1 text-sm rounded-full bg-cyan-900/30 text-cyan-400 border border-cyan-700">
                  {tag}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Publish Error */}
        {draft.publish_status === "failed" && draft.publish_error_message && (
          <div className="mt-6 bg-red-900/30 border border-red-700 rounded-xl p-5">
            <h2 className="text-lg font-medium text-red-400 mb-2">发布失败</h2>
            <p className="text-red-300 text-sm">{draft.publish_error_message}</p>
          </div>
        )}

        {/* Actions */}
        {!isDiscarded && (
          <div className="mt-6 bg-slate-800/60 border border-slate-700 rounded-xl p-5">
            <h2 className="text-lg font-medium text-white mb-4">操作</h2>
            <div className="flex flex-wrap gap-3">
              {isPendingReview && !isPublished && (
                <>
                  <button
                    onClick={handleConfirmPublish}
                    disabled={actionLoading === "confirm"}
                    className="bg-green-600 hover:bg-green-500 disabled:bg-slate-700 text-white px-6 py-3 rounded-lg font-medium transition-colors"
                  >
                    {actionLoading === "confirm" ? "处理中..." : "✅ 确认发布"}
                  </button>
                  <button
                    onClick={handleReject}
                    disabled={actionLoading === "reject"}
                    className="bg-yellow-600 hover:bg-yellow-500 disabled:bg-slate-700 text-white px-6 py-3 rounded-lg font-medium transition-colors"
                  >
                    {actionLoading === "reject" ? "处理中..." : "❌ 拒绝草稿"}
                  </button>
                </>
              )}

              {isPendingReview && (
                <button
                  onClick={handleDiscard}
                  disabled={actionLoading === "discard"}
                  className="bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 text-white px-6 py-3 rounded-lg font-medium transition-colors"
                >
                  {actionLoading === "discard" ? "处理中..." : "🗑️ 废弃草稿"}
                </button>
              )}

              {!isPublished && (
                <button
                  onClick={handleRerun}
                  disabled={actionLoading === "rerun"}
                  className="bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-700 text-white px-6 py-3 rounded-lg font-medium transition-colors"
                >
                  {actionLoading === "rerun" ? "处理中..." : "🔄 重新生成"}
                </button>
              )}

              <Link
                href={`/task/${draft.task_id}`}
                className="bg-slate-700 hover:bg-slate-600 text-white px-6 py-3 rounded-lg font-medium transition-colors inline-block text-center"
              >
                📋 查看原任务
              </Link>
            </div>
          </div>
        )}

        {/* Meta Info */}
        <div className="mt-6 text-sm text-slate-500 text-center">
          <p>草稿 ID: {draft.id} | 任务 ID: {draft.task_id}</p>
          <p className="mt-1">创建于 {formatDate(draft.created_at)} | 更新于 {formatDate(draft.updated_at)}</p>
          {draft.confirmed_at && (
            <p>确认于 {formatDate(draft.confirmed_at)}{draft.confirmed_by ? ` by ${draft.confirmed_by}` : ""}</p>
          )}
        </div>
      </main>
    </div>
  );
}
