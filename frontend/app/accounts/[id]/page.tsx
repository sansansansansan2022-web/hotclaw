/**
 * 账号详情页
 *
 * 【账号信息展示页面】
 * 展示单个账号的完整信息，包括基本信息、发布策略、运行状态、最近任务。
 *
 * 联动模块：
 * - API: frontend/lib/api.ts (getAccount, runAccount, enableAccount, disableAccount, getPendingDraftCount)
 * - 类型: frontend/types/index.ts (AccountDetail)
 * - 路由: /accounts/[id] (GET)
 * - 后端 API: GET /api/v1/accounts/{id}
 *
 * 功能：
 * 1. 显示账号基本信息（名称、定位、受众、风格）
 * 2. 显示发布策略（频率、时间、内容策略）
 * 3. 显示运行状态（上次运行、下次运行、状态）
 * 4. 显示最近任务列表
 * 5. 手动触发运行
 * 6. 启用/禁用账号
 * 7. 编辑账号
 * 8. 查看草稿箱入口（semi_auto/full_auto 模式）
 *
 * 调用方：
 * - 用户访问 /accounts/{id}
 * - 来自账号列表页点击账号
 * - 来自新建账号页创建成功后跳转
 */

"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getAccount, runAccount, enableAccount, disableAccount, getPendingDraftCount } from "@/lib/api";
import type { AccountDetail } from "@/types";

export default function AccountDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const router = useRouter();

  // 状态管理
  // account: 账号详情数据
  // pendingDraftCount: 待审核草稿数量
  // loading: 加载状态
  // error: 错误信息
  // actionLoading: 操作中状态（run/toggle）
  const [account, setAccount] = useState<AccountDetail | null>(null);
  const [pendingDraftCount, setPendingDraftCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // 页面加载时获取账号详情
  useEffect(() => {
    loadAccount();
  }, [params.id]);

  /**
   * loadAccount - 加载账号详情
   *
   * 调用 API: getAccount(accountId)
   * 更新状态: account
   * 额外获取待审核草稿数量（仅 semi_auto/full_auto 模式）
   */
  async function loadAccount() {
    setLoading(true);
    setError(null);
    try {
      const data = await getAccount(params.id);
      setAccount(data);
      // Fetch pending draft count
      // 仅 semi_auto/full_auto 模式需要显示草稿入口
      if (data.operation_mode !== "full_auto") {
        try {
          const countData = await getPendingDraftCount(data.account_id);
          setPendingDraftCount(countData.count);
        } catch {
          // Ignore error, count is optional
        }
      }
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
   * 成功后: 跳转到任务详情页
   */
  async function handleRun() {
    if (!account) return;
    setActionLoading("run");
    try {
      const result = await runAccount(account.account_id);
      router.push(`/task/${result.task_id}`);
    } catch (e) {
      alert(e instanceof Error ? e.message : "启动失败");
    } finally {
      setActionLoading(null);
    }
  }

  /**
   * handleToggleActive - 切换账号启用/禁用状态
   *
   * 调用 API: disableAccount / enableAccount
   * 成功后: 重新加载账号详情
   */
  async function handleToggleActive() {
    if (!account) return;
    setActionLoading("toggle");
    try {
      if (account.is_active) {
        await disableAccount(account.account_id);
      } else {
        await enableAccount(account.account_id);
      }
      await loadAccount();
    } catch (e) {
      alert(e instanceof Error ? e.message : "操作失败");
    } finally {
      setActionLoading(null);
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

  const frequencyMap: Record<string, string> = {
    daily: "每日",
    weekly: "每周",
    biweekly: "每两周",
    monthly: "每月",
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white flex items-center justify-center">
        <div className="text-slate-400">加载中...</div>
      </div>
    );
  }

  if (error || !account) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
        <header className="bg-slate-800/80 backdrop-blur-sm border-b border-slate-700 px-6 py-4">
          <div className="max-w-4xl mx-auto flex items-center gap-4">
            <Link href="/accounts" className="text-cyan-400 hover:text-cyan-300">
              &larr; 返回列表
            </Link>
          </div>
        </header>
        <div className="max-w-4xl mx-auto p-6">
          <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 text-red-300">
            {error || "账号不存在"}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
      {/* Header */}
      <header className="bg-slate-800/80 backdrop-blur-sm border-b border-slate-700 px-6 py-4 sticky top-0 z-20">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/accounts" className="text-cyan-400 hover:text-cyan-300">
              &larr; 返回列表
            </Link>
            <span className="text-slate-500">/</span>
            <span className="text-white font-medium">{account.name}</span>
          </div>
          <div className="flex gap-2">
            <Link
              href={`/accounts/${account.account_id}/edit`}
              className="bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-lg text-sm transition-colors"
            >
              编辑
            </Link>
            {account.is_active && (
              <button
                onClick={handleRun}
                disabled={actionLoading === "run"}
                className="bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-700 text-white px-4 py-2 rounded-lg text-sm transition-colors"
              >
                {actionLoading === "run" ? "启动中..." : "立即运行"}
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-4xl mx-auto p-6 space-y-6">
        {/* Basic Info */}
        <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-6">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h1 className="text-2xl font-bold text-white mb-2">{account.name}</h1>
              <div className="flex gap-2 flex-wrap">
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
                {account.category && (
                  <span className="px-2 py-0.5 text-xs rounded-full bg-slate-700 text-slate-400">
                    {account.category}
                  </span>
                )}
              </div>
            </div>
            <button
              onClick={handleToggleActive}
              disabled={actionLoading === "toggle"}
              className={`px-4 py-2 rounded-lg text-sm transition-colors ${
                account.is_active
                  ? "bg-red-900/30 text-red-400 hover:bg-red-900/50 border border-red-700"
                  : "bg-green-900/30 text-green-400 hover:bg-green-900/50 border border-green-700"
              }`}
            >
              {actionLoading === "toggle"
                ? "处理中..."
                : account.is_active
                ? "禁用账号"
                : "启用账号"}
            </button>
          </div>

          <div className="space-y-4">
            <div>
              <h3 className="text-sm text-slate-400 mb-1">账号定位</h3>
              <p className="text-white">{account.positioning}</p>
            </div>

            {account.audience && (
              <div>
                <h3 className="text-sm text-slate-400 mb-1">目标读者</h3>
                <p className="text-white">{account.audience}</p>
              </div>
            )}

            {account.tone_style && (
              <div>
                <h3 className="text-sm text-slate-400 mb-1">风格调性</h3>
                <p className="text-white">{account.tone_style}</p>
              </div>
            )}
          </div>
        </div>

        {/* Run Status */}
        <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-6">
          <h2 className="text-white font-medium mb-4">运行状态</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h3 className="text-sm text-slate-400 mb-1">最近运行</h3>
              <p className="text-white">{formatDate(account.last_run_at)}</p>
            </div>
            <div>
              <h3 className="text-sm text-slate-400 mb-1">运行结果</h3>
              <div className="flex items-center gap-2">
                {getRunStatusBadge(account.last_run_status)}
              </div>
            </div>
            <div>
              <h3 className="text-sm text-slate-400 mb-1">定时运行</h3>
              <p className={account.auto_run_enabled ? "text-green-400" : "text-slate-400"}>
                {account.auto_run_enabled ? "已启用" : "未启用"}
              </p>
            </div>
            <div>
              <h3 className="text-sm text-slate-400 mb-1">下次运行</h3>
              <p className={account.auto_run_enabled ? "text-cyan-400" : "text-slate-400"}>
                {account.auto_run_enabled ? formatDate(account.next_run_at) : "-"}
              </p>
            </div>
          </div>

          {/* Error Message */}
          {account.last_run_status === "failed" && account.last_error_message && (
            <div className="mt-4 p-3 bg-red-900/20 border border-red-800 rounded-lg">
              <h3 className="text-sm text-red-400 mb-1">最近错误</h3>
              <p className="text-red-300 text-sm whitespace-pre-wrap">{account.last_error_message}</p>
            </div>
          )}
        </div>

        {/* Publishing Info */}
        <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-6">
          <h2 className="text-white font-medium mb-4">发布策略</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h3 className="text-sm text-slate-400 mb-1">发布频率</h3>
              <p className="text-white">
                {account.posting_frequency
                  ? frequencyMap[account.posting_frequency] || account.posting_frequency
                  : "未设置"}
              </p>
            </div>
            <div>
              <h3 className="text-sm text-slate-400 mb-1">固定发布时间</h3>
              <p className="text-white">{account.posting_time || "-"}</p>
            </div>
            <div>
              <h3 className="text-sm text-slate-400 mb-1">定时运行</h3>
              <p className={account.auto_run_enabled ? "text-green-400" : "text-slate-400"}>
                {account.auto_run_enabled ? "已启用" : "未启用"}
              </p>
            </div>
            <div>
              <h3 className="text-sm text-slate-400 mb-1">自动发布</h3>
              <p className={account.auto_publish_enabled ? "text-green-400" : "text-slate-400"}>
                {account.auto_publish_enabled ? "已启用" : "未启用"}
              </p>
            </div>
          </div>

          {account.content_strategy && (
            <div className="mt-4">
              <h3 className="text-sm text-slate-400 mb-1">内容策略</h3>
              <p className="text-white">{account.content_strategy}</p>
            </div>
          )}

          {account.reference_accounts && (
            <div className="mt-4">
              <h3 className="text-sm text-slate-400 mb-1">参考公众号</h3>
              <p className="text-white">{account.reference_accounts}</p>
            </div>
          )}
        </div>

        {/* Drafts Entry */}
        <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-white font-medium">草稿箱</h2>
            <Link
              href={`/drafts?account_id=${account.account_id}`}
              className="text-cyan-400 hover:text-cyan-300 text-sm flex items-center gap-1"
            >
              查看全部
              <span>&rarr;</span>
            </Link>
          </div>
          <p className="text-slate-400 text-sm mb-3">
            {account.operation_mode === "semi_auto"
              ? "半自动模式下，生成的内容将进入草稿箱等待确认发布"
              : account.operation_mode === "full_auto"
              ? "全自动模式下，生成的内容将自动发布，无需审核"
              : "手动模式下，生成的内容将保存在草稿箱中"}
          </p>
          {account.operation_mode !== "full_auto" && (
            <Link
              href={`/drafts?account_id=${account.account_id}&draft_status=pending_review`}
              className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-colors ${
                pendingDraftCount > 0
                  ? "bg-yellow-900/30 hover:bg-yellow-900/50 border border-yellow-700 text-yellow-400"
                  : "bg-slate-700/50 border border-slate-600 text-slate-400"
              }`}
            >
              <span>⏳</span>
              <span>
                待确认草稿
                {pendingDraftCount > 0 && (
                  <span className="ml-2 px-2 py-0.5 text-xs rounded-full bg-yellow-600/50">
                    {pendingDraftCount}
                  </span>
                )}
              </span>
            </Link>
          )}
        </div>

        {/* Run History */}
        <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-6">
          <h2 className="text-white font-medium mb-4">最近任务</h2>
          {account.recent_tasks.length === 0 ? (
            <p className="text-slate-400 text-sm">暂无任务记录</p>
          ) : (
            <div className="space-y-3">
              {account.recent_tasks.map((task) => (
                <Link
                  key={task.task_id}
                  href={`/task/${task.task_id}`}
                  className="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg hover:bg-slate-900 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`px-2 py-0.5 text-xs rounded-full ${
                        task.status === "completed"
                          ? "bg-green-900/30 text-green-400"
                          : task.status === "running"
                          ? "bg-cyan-900/30 text-cyan-400"
                          : task.status === "failed"
                          ? "bg-red-900/30 text-red-400"
                          : "bg-slate-700 text-slate-400"
                      }`}
                    >
                      {task.status === "completed"
                        ? "已完成"
                        : task.status === "running"
                        ? "运行中"
                        : task.status === "failed"
                        ? "失败"
                        : "等待中"}
                    </span>
                    <span className="text-slate-400 text-sm">
                      {formatDate(task.created_at)}
                    </span>
                  </div>
                  {task.elapsed_seconds !== null && (
                    <span className="text-slate-500 text-sm">
                      {task.elapsed_seconds.toFixed(1)}秒
                    </span>
                  )}
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Metadata */}
        <div className="text-xs text-slate-500">
          创建于 {formatDate(account.created_at)} · 最后更新 {formatDate(account.updated_at)}
        </div>
      </main>
    </div>
  );
}
