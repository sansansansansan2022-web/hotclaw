"use client";

import { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { listDrafts, confirmPublishDraft, discardDraft, rerunFromDraft } from "@/lib/api";
import type { DraftSummary } from "@/types";

type FilterTab = "all" | "pending_review" | "published" | "discarded";

function DraftsContent() {
  const searchParams = useSearchParams();
  const accountIdFromUrl = searchParams.get("account_id");
  const draftStatusFromUrl = searchParams.get("draft_status");

  const [drafts, setDrafts] = useState<DraftSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [activeTab, setActiveTab] = useState<FilterTab>(
    draftStatusFromUrl === "pending_review" ? "pending_review" :
    draftStatusFromUrl === "published" ? "published" :
    draftStatusFromUrl === "discarded" ? "discarded" : "all"
  );
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  useEffect(() => {
    loadDrafts();
  }, [page, activeTab]);

  async function loadDrafts() {
    setLoading(true);
    setError(null);
    try {
      const filters: { draft_status?: string; publish_status?: string; account_id?: string } = {};
      if (activeTab === "pending_review") {
        filters.draft_status = "pending_review";
      } else if (activeTab === "published") {
        filters.publish_status = "published";
      } else if (activeTab === "discarded") {
        filters.draft_status = "discarded";
      }
      if (accountIdFromUrl) {
        filters.account_id = accountIdFromUrl;
      }
      const res = await listDrafts(page, 20, filters);
      setDrafts(res.drafts);
      setTotalPages(res.pagination.total_pages);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirmPublish(draftId: number) {
    setActionLoading(draftId);
    try {
      await confirmPublishDraft(draftId);
      alert("发布确认成功！");
      loadDrafts();
    } catch (e) {
      alert(e instanceof Error ? e.message : "确认发布失败");
    } finally {
      setActionLoading(null);
    }
  }

  async function handleDiscard(draftId: number) {
    if (!confirm("确定要废弃这篇草稿吗？")) return;
    setActionLoading(draftId);
    try {
      await discardDraft(draftId);
      alert("草稿已废弃");
      loadDrafts();
    } catch (e) {
      alert(e instanceof Error ? e.message : "废弃失败");
    } finally {
      setActionLoading(null);
    }
  }

  async function handleRerun(draftId: number) {
    setActionLoading(draftId);
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

  function formatDate(dateStr: string) {
    return new Date(dateStr).toLocaleString("zh-CN");
  }

  function getDraftStatusBadge(status: string) {
    switch (status) {
      case "pending_review":
        return <span className="px-2 py-0.5 text-xs rounded-full bg-yellow-900/30 text-yellow-400">待确认</span>;
      case "approved":
        return <span className="px-2 py-0.5 text-xs rounded-full bg-green-900/30 text-green-400">已批准</span>;
      case "rejected":
        return <span className="px-2 py-0.5 text-xs rounded-full bg-red-900/30 text-red-400">已拒绝</span>;
      case "discarded":
        return <span className="px-2 py-0.5 text-xs rounded-full bg-slate-700 text-slate-400">已废弃</span>;
      case "draft":
        return <span className="px-2 py-0.5 text-xs rounded-full bg-slate-700 text-slate-400">草稿</span>;
      default:
        return <span className="px-2 py-0.5 text-xs rounded-full bg-slate-700 text-slate-400">{status}</span>;
    }
  }

  function getPublishStatusBadge(status: string) {
    switch (status) {
      case "published":
        return <span className="px-2 py-0.5 text-xs rounded-full bg-green-900/30 text-green-400">已发布</span>;
      case "pending":
        return <span className="px-2 py-0.5 text-xs rounded-full bg-yellow-900/30 text-yellow-400">发布中</span>;
      case "failed":
        return <span className="px-2 py-0.5 text-xs rounded-full bg-red-900/30 text-red-400">发布失败</span>;
      case "not_published":
      default:
        return <span className="px-2 py-0.5 text-xs rounded-full bg-slate-700 text-slate-400">未发布</span>;
    }
  }

  function getSourceTypeLabel(type: string) {
    return type === "semi_auto_task" ? "半自动" : "手动";
  }

  const tabs: { key: FilterTab; label: string }[] = [
    { key: "all", label: "全部" },
    { key: "pending_review", label: "待确认" },
    { key: "published", label: "已发布" },
    { key: "discarded", label: "已废弃" },
  ];

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
            <span className="text-white font-medium">草稿箱</span>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-5xl mx-auto p-6">
        <div className="mb-6 flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white mb-2">
              {accountIdFromUrl ? "账号草稿" : "草稿箱"}
            </h1>
            <p className="text-slate-400 text-sm">
              {accountIdFromUrl
                ? "查看该账号生成的所有草稿"
                : "管理所有生成的文章草稿，确认发布或重新生成"}
            </p>
          </div>
          {accountIdFromUrl && (
            <Link
              href={`/accounts/${accountIdFromUrl}`}
              className="text-cyan-400 hover:text-cyan-300 text-sm flex items-center gap-1"
            >
              &larr; 返回账号
            </Link>
          )}
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-6 border-b border-slate-700 pb-4">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => { setActiveTab(tab.key); setPage(1); }}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                activeTab === tab.key
                  ? "bg-cyan-600 text-white"
                  : "bg-slate-800 text-slate-400 hover:bg-slate-700"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {error && (
          <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 mb-6 text-red-300">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex justify-center py-12">
            <div className="text-slate-400">加载中...</div>
          </div>
        ) : drafts.length === 0 ? (
          <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-12 text-center">
            <div className="text-4xl mb-4">📝</div>
            <h2 className="text-xl font-medium text-white mb-2">暂无草稿</h2>
            <p className="text-slate-400 mb-6">
              {activeTab === "pending_review"
                ? "当前没有待确认发布的草稿"
                : activeTab === "published"
                ? "还没有已发布的草稿"
                : activeTab === "discarded"
                ? "没有已废弃的草稿"
                : "开始生成内容后，草稿将出现在这里"}
            </p>
          </div>
        ) : (
          <>
            <div className="space-y-4">
              {drafts.map((draft) => (
                <div
                  key={draft.id}
                  className="bg-slate-800/60 border border-slate-700 rounded-xl p-5 hover:border-cyan-500/50 transition-colors"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-2 flex-wrap">
                        <h3 className="text-white font-medium text-lg">{draft.title}</h3>
                        {getDraftStatusBadge(draft.draft_status)}
                        {getPublishStatusBadge(draft.publish_status)}
                        <span className="px-2 py-0.5 text-xs rounded-full bg-purple-900/30 text-purple-400">
                          {getSourceTypeLabel(draft.source_type)}
                        </span>
                      </div>
                      {draft.selected_topic && (
                        <p className="text-slate-400 text-sm mb-2 line-clamp-1">
                          选题: {draft.selected_topic}
                        </p>
                      )}
                      <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-500">
                        <span>字数: {draft.word_count}</span>
                        <span>创建: {formatDate(draft.created_at)}</span>
                        <span>更新: {formatDate(draft.updated_at)}</span>
                        {draft.account_id && (
                          <Link
                            href={`/accounts/${draft.account_id}`}
                            className="text-cyan-400 hover:underline"
                          >
                            查看账号
                          </Link>
                        )}
                      </div>
                    </div>

                    <div className="flex flex-col gap-2 min-w-[100px]">
                      <Link
                        href={`/drafts/${draft.id}`}
                        className="bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-lg text-sm transition-colors text-center"
                      >
                        详情
                      </Link>

                      {draft.draft_status === "pending_review" && (
                        <>
                          <button
                            onClick={() => handleConfirmPublish(draft.id)}
                            disabled={actionLoading === draft.id}
                            className="bg-green-600 hover:bg-green-500 disabled:bg-slate-700 text-white px-4 py-2 rounded-lg text-sm transition-colors"
                          >
                            {actionLoading === draft.id ? "处理中..." : "确认发布"}
                          </button>
                          <button
                            onClick={() => handleDiscard(draft.id)}
                            disabled={actionLoading === draft.id}
                            className="bg-slate-700 hover:bg-slate-600 disabled:bg-slate-700 text-white px-4 py-2 rounded-lg text-sm transition-colors"
                          >
                            废弃
                          </button>
                        </>
                      )}

                      {draft.draft_status !== "discarded" && draft.publish_status !== "published" && (
                        <button
                          onClick={() => handleRerun(draft.id)}
                          disabled={actionLoading === draft.id}
                          className="bg-slate-700 hover:bg-slate-600 disabled:bg-slate-700 text-white px-4 py-2 rounded-lg text-sm transition-colors"
                        >
                          {actionLoading === draft.id ? "处理中..." : "重新生成"}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex justify-center gap-2 mt-6">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-4 py-2 rounded-lg bg-slate-800 border border-slate-700 disabled:opacity-50 hover:bg-slate-700 transition-colors"
                >
                  上一页
                </button>
                <span className="px-4 py-2 text-slate-400">
                  第 {page} / {totalPages} 页
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="px-4 py-2 rounded-lg bg-slate-800 border border-slate-700 disabled:opacity-50 hover:bg-slate-700 transition-colors"
                >
                  下一页
                </button>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

// Wrap with Suspense for useSearchParams
export default function DraftsPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white flex items-center justify-center">
        <div className="text-slate-400">加载中...</div>
      </div>
    }>
      <DraftsContent />
    </Suspense>
  );
}
