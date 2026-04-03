/**
 * Dashboard — 账号运营总览视图 (V5)
 *
 * 【字体系统统一 V5】
 * - 页面主标题: text-3xl font-semibold tracking-tight
 * - 区块标题: text-lg font-semibold
 * - 指标数字: text-3xl font-bold leading-none
 * - 正文说明: text-sm leading-6
 * - 辅助说明: text-xs text-white/60
 * - 统一 padding: p-5 或 p-6
 */

"use client";

import Link from "next/link";
import { useShellContext } from "./context";

// =============================================================================
// 布局常量
// =============================================================================

const CONTENT_CONTAINER_CLASS = "max-w-[1400px] mx-auto px-6 lg:px-8";

// =============================================================================
// 统计卡片组件 (V5)
// =============================================================================

interface StatCardProps {
  label: string;
  value: number;
  icon: string;
  color: "cyan" | "yellow" | "green" | "red";
  href: string;
}

function StatCard({ label, value, icon, color, href }: StatCardProps) {
  const colorMap = {
    cyan: {
      bg: "bg-[var(--stat-cyan-bg)]",
      border: "border-[var(--stat-cyan-border)]",
      text: "text-[var(--stat-cyan)]",
      hover: "hover:shadow-[0_0_20px_var(--stat-cyan-glow)]",
    },
    yellow: {
      bg: "bg-[var(--stat-yellow-bg)]",
      border: "border-[var(--stat-yellow-border)]",
      text: "text-[var(--stat-yellow)]",
      hover: "hover:shadow-[0_0_20px_var(--stat-yellow-glow)]",
    },
    green: {
      bg: "bg-[var(--stat-green-bg)]",
      border: "border-[var(--stat-green-border)]",
      text: "text-[var(--stat-green)]",
      hover: "hover:shadow-[0_0_20px_var(--stat-green-glow)]",
    },
    red: {
      bg: "bg-[var(--stat-red-bg)]",
      border: "border-[var(--stat-red-border)]",
      text: "text-[var(--stat-red)]",
      hover: "hover:shadow-[0_0_20px_var(--stat-red-glow)]",
    },
  };

  const c = colorMap[color];

  return (
    <Link
      href={href}
      className={`
        h-full min-h-[120px] flex flex-col items-center justify-center p-5 rounded-xl gap-3
        ${c.bg} border ${c.border}
        shadow-[var(--shadow-card)]
        hover:shadow-[var(--shadow-card-hover)] ${c.hover}
        hover:scale-[1.02]
        transition-all duration-200
        group cursor-pointer
      `}
    >
      {/* 图标 */}
      <span className="text-2xl">{icon}</span>

      {/* 数字 */}
      <span className={`text-3xl font-bold leading-none ${c.text}`}>
        {value}
      </span>

      {/* 标题 */}
      <span className="text-sm text-white/60">{label}</span>
    </Link>
  );
}

// =============================================================================
// 概览卡片 (V5)
// =============================================================================

function OverviewCards() {
  const { stats } = useShellContext();

  const cards = [
    { label: "今日任务", value: stats.todayTasks, icon: "📋", color: "cyan" as const, href: "/history" },
    { label: "待确认草稿", value: stats.pendingDrafts, icon: "📝", color: "yellow" as const, href: "/drafts?draft_status=pending_review" },
    { label: "今日发布", value: stats.publishedToday, icon: "✅", color: "green" as const, href: "/drafts?publish_status=published" },
    { label: "发布失败", value: stats.publishFailed, icon: "❌", color: "red" as const, href: "/drafts?publish_status=failed" },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card) => (
        <StatCard key={card.label} {...card} />
      ))}
    </div>
  );
}

// =============================================================================
// 待处理中心 (V5)
// =============================================================================

function PendingCenter() {
  const { drafts } = useShellContext();

  const pendingDrafts = drafts.filter((d) => d.draft_status === "pending_review");
  const failedDrafts = drafts.filter((d) => d.publish_status === "failed");
  const total = pendingDrafts.length + failedDrafts.length;

  if (total === 0) {
    return (
      <div className="rounded-xl bg-[var(--bg-card)] border border-[var(--border-default)] shadow-[var(--shadow-card)] p-6">
        <div className="flex flex-col items-center text-center py-8">
          {/* 图标 */}
          <div className="w-16 h-16 rounded-xl bg-[var(--stat-green-bg)] border border-[var(--stat-green-border)] flex items-center justify-center text-3xl mb-5">
            🎉
          </div>

          {/* 标题 */}
          <h3 className="text-lg font-semibold text-white mb-2">
            太棒了，没有待处理事项
          </h3>

          {/* 说明 */}
          <p className="text-sm text-white/60 leading-6 mb-6 max-w-xs">
            所有内容创作和审核流程都已处理完毕
          </p>

          {/* 按钮组 */}
          <div className="flex gap-3">
            <Link
              href="/workspace"
              className="px-5 py-2.5 rounded-lg bg-[var(--accent)] text-[var(--bg-void)] font-medium text-sm hover:bg-[var(--accent-hover)] transition-colors"
            >
              🚀 创建新任务
            </Link>
            <Link
              href="/accounts/new"
              className="px-5 py-2.5 rounded-lg bg-[var(--bg-elevated)] text-white/60 text-sm hover:bg-[var(--bg-hover)] hover:text-white transition-colors border border-[var(--border-default)]"
            >
              📋 添加账号
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl bg-[var(--bg-card)] border border-[var(--border-default)] shadow-[var(--shadow-card)] overflow-hidden">
      {/* 标题栏 */}
      <div className="px-5 py-4 border-b border-[var(--border-subtle)] bg-[var(--bg-elevated)] flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-[var(--stat-yellow-bg)] border border-[var(--stat-yellow-border)] flex items-center justify-center text-base">
            ⏳
          </div>
          <h3 className="text-lg font-semibold text-white">待处理中心</h3>
        </div>
        <span className="text-xs text-[var(--stat-yellow)] px-2.5 py-1 rounded-full bg-[var(--stat-yellow-bg)] border border-[var(--stat-yellow-border)] font-medium">
          {total} 项
        </span>
      </div>

      {/* 内容列表 */}
      <div className="divide-y divide-[var(--border-subtle)]">
        {pendingDrafts.length > 0 && (
          <div className="p-5">
            <div className="text-xs text-white/40 uppercase tracking-wider mb-3">待确认发布</div>
            <div className="space-y-2">
              {pendingDrafts.slice(0, 3).map((draft) => (
                <Link
                  key={`pending-${draft.id}`}
                  href={`/drafts/${draft.id}`}
                  className="flex items-center justify-between p-3 rounded-lg bg-[var(--bg-elevated)]/50 border border-[var(--border-subtle)] hover:bg-[var(--bg-hover)] hover:border-[var(--border-accent)] transition-all"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-8 h-8 rounded-lg bg-[var(--stat-yellow-bg)] border border-[var(--stat-yellow-border)] flex items-center justify-center text-sm flex-shrink-0">
                      📝
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm text-white truncate max-w-[180px]">{draft.title}</div>
                      <div className="text-xs text-white/40 mt-0.5">{draft.word_count} 字 · {new Date(draft.created_at).toLocaleDateString('zh-CN')}</div>
                    </div>
                  </div>
                  <span className="text-xs text-white/40 ml-2 flex-shrink-0">→</span>
                </Link>
              ))}
            </div>
            {pendingDrafts.length > 3 && (
              <Link href="/drafts?draft_status=pending_review" className="block text-center text-xs text-[var(--accent)] mt-3 py-1">
                查看全部 {pendingDrafts.length} 项 →
              </Link>
            )}
          </div>
        )}

        {failedDrafts.length > 0 && (
          <div className="p-5">
            <div className="text-xs text-white/40 uppercase tracking-wider mb-3">发布失败</div>
            <div className="space-y-2">
              {failedDrafts.slice(0, 3).map((draft) => (
                <Link
                  key={`failed-${draft.id}`}
                  href={`/drafts/${draft.id}`}
                  className="flex items-center justify-between p-3 rounded-lg bg-[var(--bg-elevated)]/50 border border-[var(--border-subtle)] hover:bg-[var(--bg-hover)] transition-all"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-8 h-8 rounded-lg bg-[var(--stat-red-bg)] border border-[var(--stat-red-border)] flex items-center justify-center text-sm flex-shrink-0">
                      ❌
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm text-white truncate max-w-[180px]">{draft.title}</div>
                      <div className="text-xs text-[var(--stat-red)] mt-0.5">需要处理</div>
                    </div>
                  </div>
                  <span className="text-xs text-white/40 ml-2 flex-shrink-0">→</span>
                </Link>
              ))}
            </div>
            {failedDrafts.length > 3 && (
              <Link href="/drafts?publish_status=failed" className="block text-center text-xs text-[var(--stat-red)] mt-3 py-1">
                查看全部 {failedDrafts.length} 项 →
              </Link>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// 内容流转看板 (V5)
// =============================================================================

function ContentFlow() {
  const { drafts } = useShellContext();

  const columns = [
    { key: "draft", label: "生成中", icon: "⚙️", color: "cyan" as const },
    { key: "pending_review", label: "待确认", icon: "⏳", color: "yellow" as const },
    { key: "approved", label: "已批准", icon: "✅", color: "blue" as const },
    { key: "published", label: "已发布", icon: "🚀", color: "green" as const },
  ];

  const getCount = (key: string) => {
    if (key === "published") return drafts.filter((d) => d.publish_status === "published").length;
    return drafts.filter((d) => d.draft_status === key).length;
  };

  const colorMap = {
    cyan: { bg: "bg-[var(--stat-cyan-bg)]", border: "border-[var(--stat-cyan-border)]", text: "text-[var(--stat-cyan)]" },
    yellow: { bg: "bg-[var(--stat-yellow-bg)]", border: "border-[var(--stat-yellow-border)]", text: "text-[var(--stat-yellow)]" },
    blue: { bg: "bg-blue-900/20", border: "border-blue-700/30", text: "text-blue-400" },
    green: { bg: "bg-[var(--stat-green-bg)]", border: "border-[var(--stat-green-border)]", text: "text-[var(--stat-green)]" },
  };

  return (
    <div className="rounded-xl bg-[var(--bg-card)] border border-[var(--border-default)] shadow-[var(--shadow-card)] overflow-hidden">
      {/* 标题栏 */}
      <div className="px-5 py-4 border-b border-[var(--border-subtle)] bg-[var(--bg-elevated)] flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-[var(--accent-bg)] border border-[var(--border-accent)] flex items-center justify-center text-base">
          📊
        </div>
        <h3 className="text-lg font-semibold text-white">内容流转看板</h3>
      </div>

      {/* 数字看板 */}
      <div className="grid grid-cols-4 divide-x divide-[var(--border-subtle)]">
        {columns.map((col) => {
          const c = colorMap[col.color];
          return (
            <div key={col.key} className="p-5 text-center">
              <div className={`w-10 h-10 rounded-lg ${c.bg} border ${c.border} flex items-center justify-center text-xl mx-auto mb-3`}>
                {col.icon}
              </div>
              <div className={`text-3xl font-bold leading-none ${c.text} mb-1`}>
                {getCount(col.key)}
              </div>
              <div className="text-sm text-white/60">{col.label}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// =============================================================================
// 快速开始区 (V5)
// =============================================================================

function QuickStart() {
  return (
    <div className="rounded-xl bg-[var(--bg-card)] border border-[var(--border-default)] shadow-[var(--shadow-card)] p-5 relative overflow-hidden">
      {/* 装饰 */}
      <div className="absolute top-0 right-0 w-32 h-32 bg-[var(--accent)]/5 rounded-full blur-2xl -translate-y-1/2 translate-x-1/2" />

      <div className="relative flex items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-[var(--accent-bg)] border border-[var(--border-accent)] flex items-center justify-center text-2xl">
            🚀
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white mb-1">快速开始创作</h3>
            <p className="text-sm text-white/60 leading-6">输入公众号定位，AI智能体协作完成内容创作</p>
          </div>
        </div>
        <Link
          href="/workspace"
          className="px-5 py-2.5 rounded-lg bg-[var(--accent)] text-[var(--bg-void)] font-medium text-sm hover:bg-[var(--accent-hover)] transition-colors whitespace-nowrap"
        >
          开始创作 →
        </Link>
      </div>
    </div>
  );
}

// =============================================================================
// 主组件 (V5)
// =============================================================================

export default function DashboardView() {
  const { stats } = useShellContext();

  return (
    <div className="py-6">
      {/* 居中容器 */}
      <div className={CONTENT_CONTAINER_CLASS}>
        {/* 页面标题 */}
        <div className="mb-6">
          <h1 className="text-3xl font-semibold tracking-tight text-white mb-2">
            运营总览
          </h1>
          <p className="text-sm text-white/60 leading-6">
            <span className="text-[var(--stat-cyan)] font-medium">{stats.todayTasks}</span> 个任务 ·
            <span className="text-[var(--stat-yellow)] font-medium ml-2">{stats.pendingDrafts}</span> 个待确认 ·
            <span className="text-[var(--stat-green)] font-medium ml-2">{stats.publishedToday}</span> 个已发布
          </p>
        </div>

        {/* 统计卡片 */}
        <section className="mb-5">
          <OverviewCards />
        </section>

        {/* 快速开始 */}
        <section className="mb-5">
          <QuickStart />
        </section>

        {/* 双栏布局 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <section>
            <PendingCenter />
          </section>
          <section>
            <ContentFlow />
          </section>
        </div>
      </div>
    </div>
  );
}
