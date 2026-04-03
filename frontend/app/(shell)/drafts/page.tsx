/**
 * Drafts — 草稿箱视图 (V3)
 *
 * 【视觉重构 V3】
 * - 标签筛选样式优化
 * - 空状态完整，有图标+文案+引导动作
 * - 卡片样式统一，有实体感
 * - 操作按钮风格统一
 */

"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useShellContext } from "../layout";
import { listDrafts, confirmPublishDraft, discardDraft, rerunFromDraft } from "@/lib/api";
import type { DraftSummary } from "@/types";

type FilterTab = "all" | "pending_review" | "published" | "discarded";

function DraftsContent() {
  const searchParams = useSearchParams();
  const { refreshData } = useShellContext();
  const accountIdFromUrl = searchParams.get("account_id");
  const draftStatusFromUrl = searchParams.get("draft_status");

  const [drafts, setDrafts] = useState<DraftSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [activeTab, setActiveTab] = useState<FilterTab>(
    draftStatusFromUrl === "pending_review" ? "pending_review" :
    draftStatusFromUrl === "published" ? "published" :
    draftStatusFromUrl === "discarded" ? "discarded" : "all"
  );
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  const loadDrafts = useCallback(async () => {
    setLoading(true);
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
      setTotal(res.pagination.total);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [page, activeTab, accountIdFromUrl]);

  useEffect(() => {
    loadDrafts();
  }, [loadDrafts]);

  async function handleConfirmPublish(draftId: number) {
    setActionLoading(draftId);
    try {
      await confirmPublishDraft(draftId);
      alert("发布确认成功！");
      loadDrafts();
      refreshData();
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
      refreshData();
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
    return new Date(dateStr).toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function getDraftStatusBadge(status: string) {
    switch (status) {
      case "pending_review":
        return (
          <span className="px-2.5 py-1 text-[11px] rounded-lg bg-[var(--stat-yellow-bg)] text-[var(--stat-yellow)] border border-[var(--stat-yellow-border)] font-medium">
            ⏳ 待确认
          </span>
        );
      case "approved":
        return (
          <span className="px-2.5 py-1 text-[11px] rounded-lg bg-[var(--stat-green-bg)] text-[var(--stat-green)] border border-[var(--stat-green-border)] font-medium">
            ✅ 已批准
          </span>
        );
      case "rejected":
        return (
          <span className="px-2.5 py-1 text-[11px] rounded-lg bg-[var(--stat-red-bg)] text-[var(--stat-red)] border border-[var(--stat-red-border)] font-medium">
            ❌ 已拒绝
          </span>
        );
      case "discarded":
        return (
          <span className="px-2.5 py-1 text-[11px] rounded-lg bg-[var(--bg-elevated)] text-[var(--text-muted)] border border-[var(--border-subtle)] font-medium">
            🗑️ 已废弃
          </span>
        );
      case "draft":
        return (
          <span className="px-2.5 py-1 text-[11px] rounded-lg bg-[var(--bg-elevated)] text-[var(--text-secondary)] border border-[var(--border-subtle)] font-medium">
            📝 草稿
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-1 text-[11px] rounded-lg bg-[var(--bg-elevated)] text-[var(--text-secondary)] border border-[var(--border-subtle)] font-medium">
            {status}
          </span>
        );
    }
  }

  function getPublishStatusBadge(status: string) {
    switch (status) {
      case "published":
        return (
          <span className="px-2.5 py-1 text-[11px] rounded-lg bg-[var(--stat-green-bg)] text-[var(--stat-green)] border border-[var(--stat-green-border)] font-medium">
            🚀 已发布
          </span>
        );
      case "pending":
        return (
          <span className="px-2.5 py-1 text-[11px] rounded-lg bg-[var(--stat-yellow-bg)] text-[var(--stat-yellow)] border border-[var(--stat-yellow-border)] font-medium">
            ⏳ 发布中
          </span>
        );
      case "failed":
        return (
          <span className="px-2.5 py-1 text-[11px] rounded-lg bg-[var(--stat-red-bg)] text-[var(--stat-red)] border border-[var(--stat-red-border)] font-medium">
            ❌ 发布失败
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-1 text-[11px] rounded-lg bg-[var(--bg-elevated)] text-[var(--text-muted)] border border-[var(--border-subtle)] font-medium">
            未发布
          </span>
        );
    }
  }

  const tabs: { key: FilterTab; label: string; icon: string }[] = [
    { key: "all", label: "全部", icon: "📋" },
    { key: "pending_review", label: "待确认", icon: "⏳" },
    { key: "published", label: "已发布", icon: "🚀" },
    { key: "discarded", label: "已废弃", icon: "🗑️" },
  ];

  return (
    <div className="p-8 max-w-[1200px] mx-auto">
      {/* 页面标题 */}
      <div className="mb-8">
        <h1 className="text-[26px] font-bold text-[var(--text-primary)] mb-2 tracking-tight">
          📝 {accountIdFromUrl ? "账号草稿" : "草稿箱"}
        </h1>
        <p className="text-[var(--text-secondary)] text-[14px]">
          {accountIdFromUrl ? "查看该账号生成的所有草稿" : "管理所有生成的文章草稿"}
        </p>
      </div>

      {/* 标签筛选 - V3 样式 */}
      <div className="flex items-center gap-1 mb-6 p-1.5 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] w-fit">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => { setActiveTab(tab.key); setPage(1); }}
            className={`px-5 py-2 rounded-lg text-[13px] font-medium transition-all flex items-center gap-2 ${
              activeTab === tab.key
                ? "bg-[var(--accent)] text-[var(--bg-void)] shadow-[0_2px_8px_rgba(34,211,238,0.3)]"
                : "text-[var(--text-secondary)] hover:text-white hover:bg-[var(--bg-hover)]"
            }`}
          >
            <span>{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* 草稿列表 */}
      {loading ? (
        <div className="flex justify-center py-20">
          <div className="flex flex-col items-center gap-4">
            <div className="w-12 h-12 border-3 border-[var(--border-default)] border-t-[var(--accent)] rounded-full animate-spin" />
            <div className="text-[var(--text-muted)] text-[14px]">加载中...</div>
          </div>
        </div>
      ) : drafts.length === 0 ? (
        /* 空状态 - V3 */
        <div className="rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)] shadow-[var(--shadow-card)] p-16">
          <div className="flex flex-col items-center justify-center text-center max-w-md mx-auto">
            {/* 空状态图标 - 增加视觉重量 */}
            <div className="w-24 h-24 rounded-2xl bg-[var(--bg-elevated)] border-2 border-[var(--border-default)] flex items-center justify-center text-5xl mb-6 shadow-inner">
              {activeTab === "pending_review" ? "📭" : activeTab === "published" ? "📤" : activeTab === "discarded" ? "🗑️" : "📝"}
            </div>

            {/* 文案 */}
            <h2 className="text-[20px] font-semibold text-[var(--text-primary)] mb-3">
              {activeTab === "pending_review"
                ? "暂无待确认草稿"
                : activeTab === "published"
                ? "暂无已发布草稿"
                : activeTab === "discarded"
                ? "暂无已废弃草稿"
                : "暂无草稿"}
            </h2>
            <p className="text-[var(--text-secondary)] text-[14px] mb-8 leading-relaxed">
              {activeTab === "pending_review"
                ? "所有生成的内容都已确认发布或处理完毕，继续保持！"
                : activeTab === "published"
                ? "发布的内容将显示在这里，让你的成果有迹可循"
                : activeTab === "discarded"
                ? "被废弃的草稿将显示在这里"
                : "开始创作内容后，草稿将出现在这里，等待你的审核"}
            </p>

            {/* 引导动作 */}
            <div className="flex items-center gap-4">
              {activeTab !== "all" ? (
                <button
                  onClick={() => setActiveTab("all")}
                  className="px-6 py-3 rounded-xl bg-[var(--bg-elevated)] text-[var(--text-secondary)] font-medium text-[14px] hover:bg-[var(--bg-hover)] hover:text-white transition-colors border border-[var(--border-default)]"
                >
                  查看全部草稿
                </button>
              ) : (
                <>
                  <Link
                    href="/workspace"
                    className="px-6 py-3 rounded-xl bg-[var(--accent)] text-[var(--bg-void)] font-semibold text-[14px] hover:bg-[var(--accent-hover)] transition-colors shadow-[0_4px_12px_rgba(34,211,238,0.3)] flex items-center gap-2"
                  >
                    <span>🚀</span>
                    <span>创建新任务</span>
                  </Link>
                  <Link
                    href="/accounts"
                    className="px-6 py-3 rounded-xl bg-[var(--bg-elevated)] text-[var(--text-secondary)] font-medium text-[14px] hover:bg-[var(--bg-hover)] hover:text-white transition-colors border border-[var(--border-default)] flex items-center gap-2"
                  >
                    <span>📋</span>
                    <span>查看账号</span>
                  </Link>
                </>
              )}
            </div>
          </div>
        </div>
      ) : (
        <>
          {/* 结果统计 */}
          <div className="text-[var(--text-muted)] text-[13px] mb-5 flex items-center gap-2">
            <span>共</span>
            <span className="text-[var(--text-primary)] font-semibold">{total}</span>
            <span>条结果</span>
          </div>

          {/* 草稿卡片列表 - V3 卡片样式 */}
          <div className="space-y-4">
            {drafts.map((draft) => (
              <div
                key={draft.id}
                className="rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)] p-6 shadow-[var(--shadow-card)] hover:shadow-[var(--shadow-card-hover)] hover:border-[var(--border-accent)] transition-all duration-300 group"
              >
                <div className="flex items-start justify-between gap-6">
                  {/* 左侧信息 */}
                  <div className="flex-1 min-w-0">
                    {/* 标题和标签 */}
                    <div className="flex items-center gap-2 mb-3 flex-wrap">
                      <h3 className="text-[var(--text-primary)] font-semibold text-[16px] group-hover:text-[var(--accent)] transition-colors">
                        {draft.title}
                      </h3>
                      {getDraftStatusBadge(draft.draft_status)}
                      {getPublishStatusBadge(draft.publish_status)}
                    </div>

                    {/* 选题摘要 */}
                    {draft.selected_topic && (
                      <p className="text-[var(--text-secondary)] text-[13px] mb-3 line-clamp-1 flex items-center gap-2">
                        <span className="text-[var(--accent)]">📌</span>
                        <span>{draft.selected_topic}</span>
                      </p>
                    )}

                    {/* 元信息 */}
                    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-[12px] text-[var(--text-muted)]">
                      <span className="flex items-center gap-1.5">
                        <span>📊</span>
                        <span>{draft.word_count} 字</span>
                      </span>
                      <span className="flex items-center gap-1.5">
                        <span>🕐</span>
                        <span>{formatDate(draft.created_at)}</span>
                      </span>
                      {draft.account_id && (
                        <Link
                          href={`/accounts/${draft.account_id}`}
                          className="text-[var(--accent)] hover:underline flex items-center gap-1.5 transition-colors"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <span>👤</span>
                          <span>查看账号</span>
                        </Link>
                      )}
                    </div>
                  </div>

                  {/* 右侧操作 */}
                  <div className="flex flex-col gap-2.5 min-w-[140px]">
                    <Link
                      href={`/drafts/${draft.id}`}
                      className="bg-[var(--bg-elevated)] hover:bg-[var(--bg-hover)] text-[var(--text-primary)] px-4 py-2.5 rounded-xl text-[13px] font-medium transition-colors text-center border border-[var(--border-default)] hover:border-[var(--border-accent)] flex items-center justify-center gap-2"
                    >
                      <span>📖</span>
                      <span>查看详情</span>
                    </Link>

                    {draft.draft_status === "pending_review" && (
                      <>
                        <button
                          onClick={() => handleConfirmPublish(draft.id)}
                          disabled={actionLoading === draft.id}
                          className="bg-[var(--stat-green-bg)] hover:bg-[var(--stat-green-bg)]/80 text-[var(--stat-green)] px-4 py-2.5 rounded-xl text-[13px] font-semibold transition-colors disabled:opacity-50 border border-[var(--stat-green-border)] flex items-center justify-center gap-2"
                        >
                          {actionLoading === draft.id ? (
                            <>
                              <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                              <span>处理中...</span>
                            </>
                          ) : (
                            <>
                              <span>✅</span>
                              <span>确认发布</span>
                            </>
                          )}
                        </button>
                        <button
                          onClick={() => handleDiscard(draft.id)}
                          disabled={actionLoading === draft.id}
                          className="bg-[var(--bg-elevated)] hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] px-4 py-2.5 rounded-xl text-[13px] font-medium transition-colors disabled:opacity-50 border border-[var(--border-default)] flex items-center justify-center gap-2"
                        >
                          <span>🗑️</span>
                          <span>废弃</span>
                        </button>
                      </>
                    )}

                    {draft.draft_status !== "discarded" && draft.publish_status !== "published" && (
                      <button
                        onClick={() => handleRerun(draft.id)}
                        disabled={actionLoading === draft.id}
                        className="bg-[var(--bg-elevated)] hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] px-4 py-2.5 rounded-xl text-[13px] font-medium transition-colors disabled:opacity-50 border border-[var(--border-default)] flex items-center justify-center gap-2"
                      >
                        <span>🔄</span>
                        <span>{actionLoading === draft.id ? "处理中..." : "重新生成"}</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* 分页 - V3 样式 */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-4 mt-10">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-5 py-2.5 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-default)] disabled:opacity-40 hover:bg-[var(--bg-hover)] transition-colors text-[var(--text-secondary)] text-[13px] font-medium flex items-center gap-2"
              >
                <span>←</span>
                <span>上一页</span>
              </button>
              <div className="px-5 py-2.5 rounded-xl bg-[var(--bg-card)] border border-[var(--border-default)] text-[var(--text-primary)] text-[14px] font-medium">
                第 <span className="text-[var(--accent)]">{page}</span> / {totalPages} 页
              </div>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="px-5 py-2.5 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-default)] disabled:opacity-40 hover:bg-[var(--bg-hover)] transition-colors text-[var(--text-secondary)] text-[13px] font-medium flex items-center gap-2"
              >
                <span>下一页</span>
                <span>→</span>
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function DraftsView() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-3 border-[var(--border-default)] border-t-[var(--accent)] rounded-full animate-spin" />
          <div className="text-[var(--text-muted)] text-[14px]">加载中...</div>
        </div>
      </div>
    }>
      <DraftsContent />
    </Suspense>
  );
}
