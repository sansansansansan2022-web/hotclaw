/**
 * 编辑账号页
 *
 * 【账号编辑表单页面】
 * 提供完整的账号编辑表单，与新建页类似但预填当前账号数据。
 *
 * 联动模块：
 * - API: frontend/lib/api.ts (getAccount, updateAccount)
 * - 类型: frontend/types/index.ts (AccountDetail, AccountUpdateRequest)
 * - 路由: /accounts/[id]/edit (GET)
 * - 后端 API: GET /api/v1/accounts/{id}, PATCH /api/v1/accounts/{id}
 *
 * 与新建页的区别：
 * - 页面加载时先调用 getAccount 获取当前数据
 * - 表单预填当前账号信息
 * - 提交时调用 updateAccount 而非 createAccount
 *
 * 表单字段（与新建页相同）：
 * 1. 基本信息: name(必填), category, positioning(必填)
 * 2. 受众与风格: audience, tone_style
 * 3. 发布策略: posting_frequency, posting_time, content_strategy, reference_accounts
 * 4. 运行模式: operation_mode, auto_run_enabled, auto_publish_enabled, is_active
 *
 * 提交后：
 * - 调用 updateAccount API 更新账号
 * - 成功时跳转到账号详情页 /accounts/{account_id}
 * - 失败时显示错误信息
 *
 * 调用方：
 * - 用户访问 /accounts/{id}/edit
 * - 来自账号详情页的"编辑"按钮
 */

"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { getAccount, updateAccount } from "@/lib/api";
import type { AccountDetail, AccountUpdateRequest } from "@/types";

export default function EditAccountPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const accountId = params?.id;

  // 状态管理
  // account: 原始账号数据（用于显示）
  // loading: 加载状态
  // submitting: 提交中状态
  // error: 错误信息
  // form: 表单数据
  const [account, setAccount] = useState<AccountDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<AccountUpdateRequest>({});

  // 页面加载时获取账号详情并填充表单
  useEffect(() => {
    if (!accountId) return;
    loadAccount();
  }, [accountId]);

  /**
   * loadAccount - 加载账号详情并填充表单
   *
   * 调用 API: getAccount(accountId)
   * 更新状态: account, form
   */
  async function loadAccount() {
    setLoading(true);
    try {
      if (!accountId) return;
      const data = await getAccount(accountId);
      setAccount(data);
      // 填充表单数据（将 null 转为 undefined）
      setForm({
        name: data.name,
        category: data.category ?? undefined,
        positioning: data.positioning,
        audience: data.audience ?? undefined,
        tone_style: data.tone_style ?? undefined,
        posting_frequency: data.posting_frequency ?? undefined,
        posting_time: data.posting_time ?? undefined,
        content_strategy: data.content_strategy ?? undefined,
        reference_accounts: data.reference_accounts ?? undefined,
        operation_mode: data.operation_mode,
        auto_run_enabled: data.auto_run_enabled,
        auto_publish_enabled: data.auto_publish_enabled,
        is_active: data.is_active,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  function handleChange(
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) {
    const { name, value, type } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]:
        type === "checkbox"
          ? (e.target as HTMLInputElement).checked
          : value === ""
          ? undefined
          : value,
    }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!form.name?.trim()) {
      setError("请输入账号名称");
      return;
    }
    if (!form.positioning?.trim() || (form.positioning?.length ?? 0) < 5) {
      setError("请输入账号定位（至少5个字符）");
      return;
    }

    setSubmitting(true);
    try {
      if (!accountId) return;
      await updateAccount(accountId, form);
      router.push(`/accounts/${params.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "更新失败");
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white flex items-center justify-center">
        <div className="text-slate-400">加载中...</div>
      </div>
    );
  }

  if (error && !account) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
        <header className="bg-slate-800/80 border-b border-slate-700 px-6 py-4">
          <div className="max-w-2xl mx-auto flex items-center gap-4">
            <Link href="/accounts" className="text-cyan-400 hover:text-cyan-300">
              &larr; 返回列表
            </Link>
          </div>
        </header>
        <div className="max-w-2xl mx-auto p-6">
          <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 text-red-300">
            {error}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
      {/* Header */}
      <header className="bg-slate-800/80 backdrop-blur-sm border-b border-slate-700 px-6 py-4 sticky top-0 z-20">
        <div className="max-w-2xl mx-auto flex items-center gap-4">
          <Link
            href={`/accounts/${params.id}`}
            className="text-cyan-400 hover:text-cyan-300 transition-colors flex items-center gap-2"
          >
            <span>&larr;</span>
            <span>返回详情</span>
          </Link>
          <span className="text-slate-500">/</span>
          <span className="text-white font-medium">编辑账号</span>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-2xl mx-auto p-6">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-white mb-2">编辑账号</h1>
          <p className="text-slate-400 text-sm">修改账号配置和运行策略</p>
        </div>

        {error && (
          <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 mb-6 text-red-300">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Basic Info */}
          <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-6">
            <h2 className="text-white font-medium mb-4">基本信息</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">
                  账号名称 <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  name="name"
                  value={form.name || ""}
                  onChange={handleChange}
                  maxLength={100}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-sm text-slate-400 mb-1">账号类别</label>
                <input
                  type="text"
                  name="category"
                  value={form.category || ""}
                  onChange={handleChange}
                  maxLength={50}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-sm text-slate-400 mb-1">
                  账号定位 <span className="text-red-400">*</span>
                </label>
                <textarea
                  name="positioning"
                  value={form.positioning || ""}
                  onChange={handleChange}
                  rows={4}
                  maxLength={500}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 resize-none"
                />
                <div className="text-xs text-slate-500 mt-1">
                  {(form.positioning || "").length} / 500 字符
                </div>
              </div>
            </div>
          </div>

          {/* Audience & Style */}
          <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-6">
            <h2 className="text-white font-medium mb-4">受众与风格</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">目标读者</label>
                <input
                  type="text"
                  name="audience"
                  value={form.audience || ""}
                  onChange={handleChange}
                  maxLength={200}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-sm text-slate-400 mb-1">风格调性</label>
                <input
                  type="text"
                  name="tone_style"
                  value={form.tone_style || ""}
                  onChange={handleChange}
                  maxLength={100}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                />
              </div>
            </div>
          </div>

          {/* Publishing */}
          <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-6">
            <h2 className="text-white font-medium mb-4">发布策略</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">发布频率</label>
                <select
                  name="posting_frequency"
                  value={form.posting_frequency || ""}
                  onChange={handleChange}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-cyan-500"
                >
                  <option value="">不设置</option>
                  <option value="daily">每日</option>
                  <option value="weekly">每周</option>
                  <option value="biweekly">每两周</option>
                  <option value="monthly">每月</option>
                </select>
              </div>

              <div>
                <label className="block text-sm text-slate-400 mb-1">固定发布时间</label>
                <input
                  type="time"
                  name="posting_time"
                  value={form.posting_time || ""}
                  onChange={handleChange}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-sm text-slate-400 mb-1">内容策略</label>
                <textarea
                  name="content_strategy"
                  value={form.content_strategy || ""}
                  onChange={handleChange}
                  rows={3}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 resize-none"
                />
              </div>

              <div>
                <label className="block text-sm text-slate-400 mb-1">参考公众号</label>
                <input
                  type="text"
                  name="reference_accounts"
                  value={form.reference_accounts || ""}
                  onChange={handleChange}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                />
              </div>
            </div>
          </div>

          {/* Operation Mode */}
          <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-6">
            <h2 className="text-white font-medium mb-4">运行模式</h2>
            <div className="space-y-3">
              {[
                { value: "manual", label: "手动模式", desc: "需要手动触发任务执行" },
                { value: "semi_auto", label: "半自动模式", desc: "自动生成内容，需手动确认发布" },
                { value: "full_auto", label: "全自动模式", desc: "自动生成并发布内容" },
              ].map((opt) => (
                <label
                  key={opt.value}
                  className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                    form.operation_mode === opt.value
                      ? "border-cyan-500 bg-cyan-900/20"
                      : "border-slate-700 hover:border-slate-600"
                  }`}
                >
                  <input
                    type="radio"
                    name="operation_mode"
                    value={opt.value}
                    checked={form.operation_mode === opt.value}
                    onChange={handleChange}
                    className="mt-1"
                  />
                  <div>
                    <div className="text-white text-sm font-medium">{opt.label}</div>
                    <div className="text-slate-400 text-xs">{opt.desc}</div>
                  </div>
                </label>
              ))}
            </div>

            <div className="mt-4 space-y-3">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  name="auto_run_enabled"
                  checked={form.auto_run_enabled || false}
                  onChange={handleChange}
                  className="w-4 h-4 rounded border-slate-600 bg-slate-900 text-cyan-500 focus:ring-cyan-500"
                />
                <div>
                  <span className="text-white text-sm">启用定时运行</span>
                  <p className="text-slate-400 text-xs">按照发布频率自动执行任务</p>
                </div>
              </label>

              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  name="auto_publish_enabled"
                  checked={form.auto_publish_enabled || false}
                  onChange={handleChange}
                  className="w-4 h-4 rounded border-slate-600 bg-slate-900 text-cyan-500 focus:ring-cyan-500"
                />
                <div>
                  <span className="text-white text-sm">启用自动发布</span>
                  <p className="text-slate-400 text-xs">审核通过后自动发布到公众号</p>
                </div>
              </label>

              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  name="is_active"
                  checked={form.is_active ?? true}
                  onChange={handleChange}
                  className="w-4 h-4 rounded border-slate-600 bg-slate-900 text-cyan-500 focus:ring-cyan-500"
                />
                <div>
                  <span className="text-white text-sm">账号启用状态</span>
                  <p className="text-slate-400 text-xs">禁用后账号不会被定时任务选中</p>
                </div>
              </label>
            </div>
          </div>

          {/* Submit */}
          <div className="flex gap-4">
            <button
              type="button"
              onClick={() => router.back()}
              className="flex-1 bg-slate-700 hover:bg-slate-600 text-white py-3 rounded-lg font-medium transition-colors"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="flex-1 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-700 text-white py-3 rounded-lg font-medium transition-colors"
            >
              {submitting ? "保存中..." : "保存修改"}
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}
