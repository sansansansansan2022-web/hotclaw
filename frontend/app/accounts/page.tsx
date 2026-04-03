/**
 * 账号列表页
 *
 * 【账号管理主页面】
 * 展示所有公众号账号的列表，支持分页、状态筛选、运行操作。
 *
 * 联动模块：
 * - API: frontend/lib/api.ts (listAccounts, runAccount)
 * - 类型: frontend/types/index.ts (AccountSummary)
 * - 路由: /accounts (GET)
 *
 * 功能：
 * 1. 分页展示账号列表（每页20条）
 * 2. 显示账号基本信息（名称、状态、运行模式）
 * 3. 显示最近运行时间和下次运行时间
 * 4. 手动触发账号运行
 * 5. 跳转账号详情页/新建页
 *
 * 调用方：
 * - 用户访问 /accounts
 * - 来自 /accounts/new 创建成功后跳转
 */

"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { listAccounts, runAccount } from "@/lib/api";
import type { AccountSummary } from "@/types";

export default function AccountsPage() {
  // 状态管理
  // accounts: 账号列表
  // loading: 加载状态
  // error: 错误信息
  // page/totalPages: 分页状态
  // runningId: 当前正在运行的账号ID（防止重复点击）
  const [accounts, setAccounts] = useState<AccountSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [runningId, setRunningId] = useState<string | null>(null);

  // 页面加载时和分页切换时获取数据
  useEffect(() => {
    loadAccounts();
  }, [page]);

  /**
   * loadAccounts - 加载账号列表
   *
   * 调用 API: listAccounts(page, 20)
   * 更新状态: accounts, totalPages
   * 异常处理: 设置 error 状态
   */
  async function loadAccounts() {
    setLoading(true);
    setError(null);
    try {
      const res = await listAccounts(page, 20);
      setAccounts(res.accounts);
      setTotalPages(res.pagination.total_pages);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  /**
   * handleRun - 手动触发账号运行
   *
   * 调用 API: runAccount(accountId)
   * 参数: accountId - 要运行的账号ID
   * 成功后: 提示用户查看任务历史
   * 失败后: 提示错误信息
   *
   * 注意: 使用 runningId 防止重复点击
   */
  async function handleRun(accountId: string) {
    setRunningId(accountId);
    try {
      await runAccount(accountId);
      alert("任务已创建，请在任务历史查看进度");
    } catch (e) {
      alert(e instanceof Error ? e.message : "启动失败");
    } finally {
      setRunningId(null);
    }
  }

  /**
   * formatDate - 格式化日期显示
   *
   * @param dateStr - ISO 格式日期字符串
   * @returns 本地化日期时间字符串
   */
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
      case "never_run":
        return <span className="px-2 py-0.5 text-xs rounded-full bg-slate-700 text-slate-400">未运行</span>;
      default:
        return status ? <span className="px-2 py-0.5 text-xs rounded-full bg-slate-700 text-slate-400">{status}</span> : null;
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

  function getFrequencyLabel(freq: string | null) {
    if (!freq) return null;
    switch (freq) {
      case "daily": return "每日";
      case "weekly": return "每周";
      case "biweekly": return "每两周";
      case "monthly": return "每月";
      default: return freq;
    }
  }

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
            <span className="text-white font-medium">账号管理</span>
          </div>
          <Link
            href="/accounts/new"
            className="bg-cyan-600 hover:bg-cyan-500 text-white px-4 py-2 rounded-lg font-medium transition-colors"
          >
            + 新建账号
          </Link>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-5xl mx-auto p-6">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-white mb-2">账号列表</h1>
          <p className="text-slate-400 text-sm">
            管理你的公众号账号，查看运行状态和定时计划
          </p>
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
        ) : accounts.length === 0 ? (
          <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-12 text-center">
            <div className="text-4xl mb-4">📋</div>
            <h2 className="text-xl font-medium text-white mb-2">暂无账号</h2>
            <p className="text-slate-400 mb-6">创建你的第一个公众号账号，开始自动化内容生产</p>
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
                  className="bg-slate-800/60 border border-slate-700 rounded-xl p-5 hover:border-cyan-500/50 transition-colors"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-2 flex-wrap">
                        <h3 className="text-white font-medium text-lg">{account.name}</h3>
                        <span
                          className={`px-2 py-0.5 text-xs rounded-full ${
                            account.is_active
                              ? "bg-green-900/30 text-green-400"
                              : "bg-slate-700 text-slate-400"
                          }`}
                        >
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

                      {/* Run Info */}
                      <div className="space-y-2">
                        <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-500">
                          {account.category && (
                            <span>类别: {account.category}</span>
                          )}
                          {account.posting_frequency && (
                            <span>频率: {getFrequencyLabel(account.posting_frequency)}</span>
                          )}
                          {account.auto_run_enabled && (
                            <span className="text-cyan-400">自动运行: 已启用</span>
                          )}
                        </div>

                        {/* Status Info */}
                        <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs">
                          <span className="text-slate-500">
                            最近运行: {formatDate(account.last_run_at)}
                          </span>
                          {account.auto_run_enabled && account.next_run_at && (
                            <span className="text-cyan-400">
                              下次运行: {formatDate(account.next_run_at)}
                            </span>
                          )}
                        </div>

                        {/* Error Message Preview */}
                        {account.last_run_status === "failed" && account.last_error_message && (
                          <div className="text-xs text-red-400 bg-red-900/20 rounded px-2 py-1 max-w-md truncate">
                            错误: {account.last_error_message}
                          </div>
                        )}
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
