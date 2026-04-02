"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createAccount } from "@/lib/api";
import type { AccountCreateRequest } from "@/types";

export default function NewAccountPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<AccountCreateRequest>({
    name: "",
    positioning: "",
    category: "",
    audience: "",
    tone_style: "",
    posting_frequency: undefined,
    posting_time: "",
    content_strategy: "",
    reference_accounts: "",
    operation_mode: "manual",
    auto_run_enabled: false,
    auto_publish_enabled: false,
    is_active: true,
  });

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
    if (!form.positioning?.trim() || form.positioning.length < 5) {
      setError("请输入账号定位（至少5个字符）");
      return;
    }

    setSubmitting(true);
    try {
      const result = await createAccount(form);
      router.push(`/accounts/${result.account_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "创建失败");
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
      {/* Header */}
      <header className="bg-slate-800/80 backdrop-blur-sm border-b border-slate-700 px-6 py-4 sticky top-0 z-20">
        <div className="max-w-2xl mx-auto flex items-center gap-4">
          <Link
            href="/accounts"
            className="text-cyan-400 hover:text-cyan-300 transition-colors flex items-center gap-2"
          >
            <span>&larr;</span>
            <span>返回列表</span>
          </Link>
          <span className="text-slate-500">/</span>
          <span className="text-white font-medium">新建账号</span>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-2xl mx-auto p-6">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-white mb-2">新建账号</h1>
          <p className="text-slate-400 text-sm">
            创建一个新的公众号账号，配置定位和运行策略
          </p>
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
                  placeholder="例如：科技前沿观察"
                  maxLength={100}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-sm text-slate-400 mb-1">
                  账号类别
                </label>
                <input
                  type="text"
                  name="category"
                  value={form.category || ""}
                  onChange={handleChange}
                  placeholder="例如：科技、财经、生活"
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
                  placeholder="描述你的公众号定位、受众群体、内容风格等。例如：面向25-35岁职场人士的科技数码内容，偏重产品评测和行业趋势分析，语言风格专业但易懂..."
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
                  placeholder="例如：25-35岁职场人士、科技爱好者"
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
                  placeholder="例如：专业严谨、轻松活泼、深度分析"
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
                  placeholder="描述内容选题方向、来源渠道等"
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
                  placeholder="例如：36氪、虎嗅App"
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
                  <span className="text-white text-sm">创建后立即启用</span>
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
              {submitting ? "创建中..." : "创建账号"}
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}
