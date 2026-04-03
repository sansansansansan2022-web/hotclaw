/**
 * Accounts — 账号管理视图
 *
 * 【Shell 内视图】
 * 展示所有公众号账号的列表。
 */

"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useShellContext } from "../layout";
import { listAccounts, runAccount } from "@/lib/api";
import type { AccountSummary } from "@/types";

export default function AccountsView() {
  const { refreshData } = useShellContext();
  const [accounts, setAccounts] = useState<AccountSummary[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [runningId, setRunningId] = useState<string | null>(null);

  const loadAccounts = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listAccounts(page, 20);
      setAccounts(res.accounts);
      setTotalPages(res.pagination.total_pages);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    loadAccounts();
  }, [loadAccounts]);

  async function handleRun(accountId: string) {
    setRunningId(accountId);
    try {
      await runAccount(accountId);
      alert("任务已创建，请在任务历史查看进度");
      refreshData();
    } catch (e) {
      alert(e instanceof Error ? e.message : "启动失败");
    } finally {
      setRunningId(null);
    }
  }

  function formatDate(dateStr: string | null) {
    if (!dateStr) return "-";
    return new Date(dateStr).toLocaleString("zh-CN");
  }

  function getRunStatusBadge(status: string | null) {
    switch (status) {
      case "success":
        return <span className="px-2 py-0.5 text-xs rounded-full bg-green-900/30 text-green-400">成功</span>;
      case "failed":
        return <span className="px-2 py-0.5 text-xs rounded-full bg-red-900/30 text-red-400">失败</span>;
      case "running":
        return <span className="px-2 py-0.5 text-xs rounded-full bg-cyan-900/30 text-cyan-400">运行中</span>;
      default:
        return <span className="px-2 py-0.5 text-xs rounded-full bg-slate-700 text-slate-400">未运行</span>;
    }
  }

  function getModeLabel(mode: string) {
    switch (mode) {
      case "manual": return "手动";
      case "semi_auto": return "半自动";
      case "full_auto": return "全自动";
      default: return mode;
    }
  }

  return (
    <div className="p-6">
      {/* 页面标题 */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white mb-1">账号管理</h1>
          <p className="text-slate-400 text-sm">管理公众号账号，查看运行状态</p>
        </div>
        <Link
          href="/accounts/new"
          className="bg-cyan-600 hover:bg-cyan-500 text-white px-4 py-2 rounded-lg text-sm transition-colors"
        >
          + 新建账号
        </Link>
      </div>

      {/* 账号列表 */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="text-slate-400">加载中...</div>
        </div>
      ) : accounts.length === 0 ? (
        <div className="bg-slate-800/40 border border-slate-700 rounded-xl p-12 text-center">
          <div className="text-4xl mb-4">📋</div>
          <h2 className="text-xl font-medium text-white mb-2">暂无账号</h2>
          <p className="text-slate-400 mb-6">创建你的第一个公众号账号</p>
          <Link
            href="/accounts/new"
            className="inline-block bg-cyan-600 hover:bg-cyan-500 text-white px-6 py-3 rounded-lg font-medium transition-colors"
          >
            创建第一个账号
          </Link>
        </div>
      ) : (
        <>
          <div className="space-y-4">
            {accounts.map((account) => (
              <div
                key={account.account_id}
                className="bg-slate-800/40 border border-slate-700 rounded-xl p-5 hover:border-cyan-500/50 transition-colors"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2 flex-wrap">
                      <h3 className="text-white font-medium text-lg">{account.name}</h3>
                      <span className={`px-2 py-0.5 text-xs rounded-full ${
                        account.is_active
                          ? "bg-green-900/30 text-green-400"
                          : "bg-slate-700 text-slate-400"
                      }`}>
                        {account.is_active ? "已启用" : "已禁用"}
                      </span>
                      <span className="px-2 py-0.5 text-xs rounded-full bg-purple-900/30 text-purple-400">
                        {getModeLabel(account.operation_mode)}
                      </span>
                      {account.last_run_status && getRunStatusBadge(account.last_run_status)}
                    </div>
                    <p className="text-slate-400 text-sm mb-3 line-clamp-2">
                      {account.positioning}
                    </p>
                    <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-500">
                      {account.category && <span>类别: {account.category}</span>}
                      {account.auto_run_enabled && (
                        <span className="text-cyan-400">自动运行: 已启用</span>
                      )}
                      <span>最近运行: {formatDate(account.last_run_at)}</span>
                    </div>
                  </div>

                  <div className="flex flex-col gap-2">
                    <Link
                      href={`/accounts/${account.account_id}`}
                      className="bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-lg text-sm transition-colors text-center"
                    >
                      详情
                    </Link>
                    {account.is_active && (
                      <button
                        onClick={() => handleRun(account.account_id)}
                        disabled={runningId === account.account_id}
                        className="bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-700 text-white px-4 py-2 rounded-lg text-sm transition-colors"
                      >
                        {runningId === account.account_id ? "启动中..." : "立即运行"}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* 分页 */}
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
    </div>
  );
}
