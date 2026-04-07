/**
 * Shell Layout — 固定壳层 (V3)
 *
 * 【视觉重构 V3】
 * - 左侧导航：280px，增强选中态和层级感
 * - 顶部统计：放大数字，强调"核心运营指标"
 * - 右侧面板：增加容器感，不是透明占位
 * - 整体风格：成熟 SaaS 控制台
 */

"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { listAccounts, listDrafts, listTasks } from "@/lib/api";
import type { AccountSummary, DraftSummary, TaskSummary } from "@/types";
import { ShellContext, useShellContext, type DashboardStats, type RecentEvent, type ShellContextValue } from "./context";

// 导出 context hooks 供子页面使用
export { useShellContext };
export type { DashboardStats, RecentEvent };

// =============================================================================
// TopBar 组件 (V3)
// =============================================================================

function TopBar({ stats, currentView }: { stats: DashboardStats; currentView: string }) {
  const viewTitles: Record<string, string> = {
    "/": "运营总览",
    "/workspace": "创作工作台",
    "/accounts": "账号管理",
    "/drafts": "草稿箱",
  };

  return (
    <header className="h-[72px] bg-[var(--bg-surface)] border-b border-[var(--border-default)] px-6 flex items-center justify-between flex-shrink-0 z-30">
      {/* Logo + 当前视图 */}
      <div className="flex items-center gap-5">
        <Link href="/" className="flex items-center gap-3.5 group">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--accent)] to-[var(--accent-dim)] flex items-center justify-center font-bold text-[var(--bg-void)] text-sm shadow-lg">
            HC
          </div>
          <div className="flex flex-col">
            <span className="text-white font-semibold text-[16px] leading-tight tracking-wide">HotClaw</span>
            <span className="text-[var(--text-muted)] text-[11px] leading-tight">
              {viewTitles[currentView] || "运营总览"}
            </span>
          </div>
        </Link>

        {/* 视图切换指示器 */}
        <div className="hidden lg:flex items-center gap-1 ml-4 pl-4 border-l border-[var(--border-subtle)]">
          <span className="text-[var(--text-muted)] text-[11px] uppercase tracking-wider">模块</span>
        </div>
      </div>

      {/* 核心运营指标 - 大尺寸统计卡片 */}
      <div className="flex items-center gap-3">
        <StatCard label="今日任务" value={stats.todayTasks} icon="📋" color="cyan" />
        <StatCard label="待确认" value={stats.pendingDrafts} icon="📝" color="yellow" />
        <StatCard label="已发布" value={stats.publishedToday} icon="✅" color="green" />
        <StatCard label="失败" value={stats.publishFailed} icon="❌" color="red" />
      </div>

      {/* 快捷入口 */}
      <div className="flex items-center gap-3">
        <Link
          href="/settings"
          className="h-9 px-4 flex items-center gap-2 text-[13px] text-[var(--text-secondary)] hover:text-white hover:bg-[var(--bg-hover)] rounded-lg transition-all"
        >
          <span>⚙️</span>
          <span>设置</span>
        </Link>
      </div>
    </header>
  );
}

/**
 * StatCard - 核心统计卡片 (V3)
 * 放大数字，强调"运营指标"感
 */
function StatCard({
  label,
  value,
  icon,
  color,
}: {
  label: string;
  value: number;
  icon: string;
  color: "cyan" | "yellow" | "green" | "red";
}) {
  const colorMap = {
    cyan: {
      bg: "bg-[var(--stat-cyan-bg)]",
      border: "border-[var(--stat-cyan-border)]",
      text: "text-[var(--stat-cyan)]",
      shadow: "shadow-[var(--stat-cyan-glow)]",
    },
    yellow: {
      bg: "bg-[var(--stat-yellow-bg)]",
      border: "border-[var(--stat-yellow-border)]",
      text: "text-[var(--stat-yellow)]",
      shadow: "shadow-[var(--stat-yellow-glow)]",
    },
    green: {
      bg: "bg-[var(--stat-green-bg)]",
      border: "border-[var(--stat-green-border)]",
      text: "text-[var(--stat-green)]",
      shadow: "shadow-[var(--stat-green-glow)]",
    },
    red: {
      bg: "bg-[var(--stat-red-bg)]",
      border: "border-[var(--stat-red-border)]",
      text: "text-[var(--stat-red)]",
      shadow: "shadow-[var(--stat-red-glow)]",
    },
  };

  const c = colorMap[color];

  return (
    <div className={`
      flex items-center gap-3 px-4 py-3 rounded-xl
      ${c.bg} border ${c.border}
      transition-all duration-200 hover:scale-[1.02] cursor-pointer
      shadow-[var(--shadow-card)]
    `}>
      <span className="text-xl">{icon}</span>
      <div className="flex flex-col min-w-[48px]">
        <span className={`text-[28px] font-bold leading-none ${c.text}`}>{value}</span>
        <span className="text-[11px] text-[var(--text-muted)] leading-tight mt-1 font-medium">{label}</span>
      </div>
    </div>
  );
}

// =============================================================================
// Sidebar 组件 (V3)
// =============================================================================

const NAV_ITEMS = [
  { href: "/", icon: "📊", label: "运营总览" },
  { href: "/workspace", icon: "🔧", label: "创作工作台" },
  { href: "/accounts", icon: "📋", label: "账号管理" },
  { href: "/drafts", icon: "📝", label: "草稿箱" },
  { href: "/history", icon: "📜", label: "历史任务" },
];

/**
 * Sidebar - 左侧工作台导航 (V3)
 * 280px宽度，增强选中态，更明确的导航层级
 */
function Sidebar({
  accounts,
  loading,
  currentPath,
}: {
  accounts: AccountSummary[];
  loading: boolean;
  currentPath: string;
}) {
  function getStatusDot(status: string | null, isActive: boolean) {
    if (!isActive) return "bg-[var(--text-muted)] opacity-50";
    switch (status) {
      case "success": return "bg-[var(--stat-green)] shadow-[0_0_6px_var(--stat-green)]";
      case "failed": return "bg-[var(--stat-red)] shadow-[0_0_6px_var(--stat-red)]";
      case "running": return "bg-[var(--stat-yellow)] animate-pulse shadow-[0_0_6px_var(--stat-yellow)]";
      default: return "bg-[var(--accent)] shadow-[0_0_6px_var(--accent)]";
    }
  }

  function getModeIcon(mode: string) {
    switch (mode) {
      case "semi_auto": return "🤖";
      case "full_auto": return "⚡";
      default: return "👤";
    }
  }

  return (
    <aside className="w-[280px] bg-[var(--bg-surface)] border-r border-[var(--border-default)] flex flex-col flex-shrink-0">
      {/* 导航菜单区 */}
      <nav className="p-4">
        <div className="text-[10px] text-[var(--text-muted)] font-semibold uppercase tracking-wider px-3 mb-3">
          导航菜单
        </div>
        <div className="space-y-1">
          {NAV_ITEMS.map((item) => {
            const isActive = currentPath === item.href ||
              (item.href !== "/" && currentPath.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`
                  group flex items-center gap-3 px-3 py-2.5 rounded-lg text-[14px] transition-all duration-200 relative overflow-hidden
                  ${isActive
                    ? "bg-[var(--nav-active-bg)] text-[var(--accent)]"
                    : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-white"
                  }
                `}
              >
                {/* 激活态左侧高亮条 */}
                {isActive && (
                  <>
                    <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-[var(--accent)]" />
                    <div className="absolute inset-0 bg-gradient-to-r from-[var(--accent)]/5 to-transparent" />
                  </>
                )}
                <span className="text-lg relative z-10">{item.icon}</span>
                <span className="font-medium relative z-10">{item.label}</span>
                {isActive && (
                  <span className="ml-auto relative z-10">
                    <span className="inline-block w-1.5 h-1.5 rounded-full bg-[var(--accent)]" />
                  </span>
                )}
              </Link>
            );
          })}
        </div>
      </nav>

      {/* 分割线 */}
      <div className="mx-4 border-t border-[var(--border-subtle)]" />

      {/* 账号快捷列表 */}
      <div className="flex-1 overflow-hidden flex flex-col p-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-[10px] text-[var(--text-muted)] font-semibold uppercase tracking-wider">快速访问</span>
          <Link
            href="/accounts/new"
            className="text-[12px] text-[var(--accent)] hover:text-[var(--accent-hover)] font-medium transition-colors flex items-center gap-1 px-2 py-1 rounded-md hover:bg-[var(--accent-bg)]"
          >
            <span>+</span>
            <span>新建账号</span>
          </Link>
        </div>
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-12">
              <div className="w-8 h-8 rounded-full border-2 border-[var(--border-default)] border-t-[var(--accent)] animate-spin mb-3" />
              <div className="text-[var(--text-muted)] text-[12px]">加载中...</div>
            </div>
          ) : accounts.length === 0 ? (
            <div className="flex flex-col items-center py-10 px-4 text-center rounded-xl bg-[var(--bg-elevated)]/50">
              <div className="text-[36px] mb-3 opacity-40">📭</div>
              <div className="text-[var(--text-secondary)] text-[13px] mb-2">暂无账号</div>
              <Link
                href="/accounts/new"
                className="text-[var(--accent)] hover:text-[var(--accent-hover)] text-[12px] font-medium transition-colors"
              >
                创建一个账号 →
              </Link>
            </div>
          ) : (
            <div className="space-y-1">
              {accounts.slice(0, 12).map((account) => (
                <Link
                  key={account.account_id}
                  href={`/accounts/${account.account_id}`}
                  className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-[var(--bg-hover)] transition-all group"
                >
                  <div
                    className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${getStatusDot(
                      account.last_run_status,
                      account.is_active
                    )}`}
                  />
                  <span className="text-[13px] text-[var(--text-secondary)] truncate flex-1 group-hover:text-white transition-colors font-medium">
                    {account.name}
                  </span>
                  <span className="text-[12px] opacity-60">{getModeIcon(account.operation_mode)}</span>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 底部链接 */}
      <div className="p-4 border-t border-[var(--border-subtle)]">
        <Link
          href="/accounts"
          className="flex items-center justify-center gap-2 text-[12px] text-[var(--text-muted)] hover:text-[var(--accent)] transition-colors py-2.5 rounded-lg hover:bg-[var(--bg-hover)]"
        >
          <span>管理全部账号</span>
          <span>→</span>
        </Link>
      </div>
    </aside>
  );
}

// =============================================================================
// RightPanel 组件 (V3)
// =============================================================================

function RightPanel({ events }: { events: RecentEvent[] }) {
  const iconMap: Record<string, string> = {
    task: "📋",
    draft: "📝",
    publish: "🚀",
    success: "✅",
    failed: "❌",
    pending: "⏳",
  };

  const statusConfig: Record<string, { bg: string; text: string; border: string; label: string }> = {
    success: {
      bg: "bg-[var(--stat-green-bg)]",
      text: "text-[var(--stat-green)]",
      border: "border-[var(--stat-green-border)]",
      label: "成功"
    },
    failed: {
      bg: "bg-[var(--stat-red-bg)]",
      text: "text-[var(--stat-red)]",
      border: "border-[var(--stat-red-border)]",
      label: "失败"
    },
    pending: {
      bg: "bg-[var(--stat-yellow-bg)]",
      text: "text-[var(--stat-yellow)]",
      border: "border-[var(--stat-yellow-border)]",
      label: "进行中"
    },
    info: {
      bg: "bg-[var(--bg-elevated)]",
      text: "text-[var(--text-secondary)]",
      border: "border-[var(--border-subtle)]",
      label: "更新"
    },
  };

  return (
    <aside className="w-[320px] bg-[var(--bg-surface)] border-l border-[var(--border-default)] flex flex-col flex-shrink-0">
      {/* 标题区 - 增加视觉重量 */}
      <div className="px-5 py-4 border-b border-[var(--border-default)] bg-[var(--bg-elevated)]">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[var(--accent-bg)] border border-[var(--border-accent)] flex items-center justify-center">
            <span className="text-sm">📡</span>
          </div>
          <div>
            <h2 className="text-white font-semibold text-[15px]">最近事件</h2>
            <p className="text-[var(--text-muted)] text-[11px]">实时动态监控</p>
          </div>
        </div>
      </div>

      {/* 事件列表 - 增加容器感 */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2 bg-[var(--bg-base)]">
        {events.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full py-16 px-6 text-center">
            <div className="w-16 h-16 rounded-2xl bg-[var(--bg-elevated)] border border-[var(--border-default)] flex items-center justify-center mb-4">
              <span className="text-3xl opacity-50">📭</span>
            </div>
            <div className="text-[var(--text-secondary)] text-[14px] font-medium mb-2">暂无事件记录</div>
            <div className="text-[var(--text-muted)] text-[12px] leading-relaxed">
              创建任务后，事件将实时显示在这里
            </div>
          </div>
        ) : (
          events.slice(0, 15).map((event, idx) => {
            const config = statusConfig[event.status] || statusConfig.info;
            return (
              <div
                key={event.id}
                className={`
                  p-4 rounded-xl
                  bg-[var(--bg-card)] border
                  transition-all duration-200
                  hover:border-[var(--border-accent)] hover:shadow-[var(--shadow-card-hover)]
                  cursor-pointer
                  ${config.border}
                `}
              >
                <div className="flex items-start gap-3">
                  <div className={`w-10 h-10 rounded-xl ${config.bg} border ${config.border} flex items-center justify-center flex-shrink-0`}>
                    <span className="text-base">{iconMap[event.type] || iconMap[event.status] || "📋"}</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className={`text-[13px] font-semibold ${config.text}`}>
                        {event.action}
                      </span>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full ${config.bg} ${config.text} font-medium`}>
                        {config.label}
                      </span>
                    </div>
                    <div className="text-[var(--text-secondary)] text-[13px] line-clamp-2 leading-snug">
                      {event.title}
                    </div>
                    <div className="text-[var(--text-muted)] text-[11px] mt-2 flex items-center gap-1.5">
                      <span className="w-1 h-1 rounded-full bg-[var(--text-muted)]" />
                      <span>{event.time}</span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* 底部链接 */}
      <div className="p-4 border-t border-[var(--border-default)] bg-[var(--bg-elevated)]">
        <Link
          href="/history"
          className="flex items-center justify-center gap-2 text-[12px] text-[var(--text-muted)] hover:text-[var(--accent)] transition-colors py-2.5 rounded-lg hover:bg-[var(--bg-hover)] font-medium"
        >
          <span>查看全部历史</span>
          <span>→</span>
        </Link>
      </div>
    </aside>
  );
}

// =============================================================================
// Shell Layout 主组件
// =============================================================================

export default function ShellLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  // 数据状态
  const [accounts, setAccounts] = useState<AccountSummary[]>([]);
  const [drafts, setDrafts] = useState<DraftSummary[]>([]);
  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [loading, setLoading] = useState(true);

  // 统计数据
  const [stats, setStats] = useState<DashboardStats>({
    todayTasks: 0,
    pendingDrafts: 0,
    publishedToday: 0,
    publishFailed: 0,
  });

  // 事件列表
  const [events, setEvents] = useState<RecentEvent[]>([]);

  // 今日开始时间
  const todayStart = new Date();
  todayStart.setHours(0, 0, 0, 0);

  // 加载数据
  const loadData = useCallback(async () => {
    try {
      const [accountsRes, draftsRes, tasksRes] = await Promise.all([
        listAccounts(1, 50),
        listDrafts(1, 100),
        listTasks(1, 50),
      ]);

      setAccounts(accountsRes.accounts);
      setDrafts(draftsRes.drafts);
      setTasks(tasksRes.tasks);

      // 统计
      const todayTasks = tasksRes.tasks.filter(
        (t) => new Date(t.created_at) >= todayStart
      ).length;

      const pendingDrafts = draftsRes.drafts.filter(
        (d) => d.draft_status === "pending_review"
      ).length;

      const publishedToday = draftsRes.drafts.filter(
        (d) =>
          d.publish_status === "published" &&
          new Date(d.updated_at) >= todayStart
      ).length;

      const publishFailed = draftsRes.drafts.filter(
        (d) => d.publish_status === "failed"
      ).length;

      setStats({ todayTasks, pendingDrafts, publishedToday, publishFailed });

      // 生成事件列表
      const recentEvents: RecentEvent[] = [];

      tasksRes.tasks.slice(0, 10).forEach((task) => {
        const createdAt = new Date(task.created_at);
        recentEvents.push({
          id: `task-${task.task_id}`,
          type: "task",
          action: task.status === "completed" ? "任务完成" : task.status === "failed" ? "任务失败" : "任务进行中",
          title: task.positioning_summary || "内容创作任务",
          time: createdAt.toLocaleString("zh-CN", {
            month: "numeric",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          }),
          timestamp: createdAt.getTime(),
          status: task.status === "completed" ? "success" : task.status === "failed" ? "failed" : "pending",
        });
      });

      draftsRes.drafts.slice(0, 10).forEach((draft) => {
        const createdAt = new Date(draft.created_at);
        recentEvents.push({
          id: `draft-${draft.id}`,
          type: "draft",
          action: draft.draft_status === "pending_review" ? "新草稿待确认" : "草稿已更新",
          title: draft.title,
          time: createdAt.toLocaleString("zh-CN", {
            month: "numeric",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          }),
          timestamp: createdAt.getTime(),
          status: draft.draft_status === "pending_review" ? "pending" : "info",
        });
      });

      recentEvents.sort((a, b) => b.timestamp - a.timestamp);

      setEvents(recentEvents.slice(0, 15));
    } catch (e) {
      console.error("Failed to load shell data:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    // 每 30 秒刷新一次
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, [loadData]);

  const contextValue: ShellContextValue = {
    stats,
    accounts,
    drafts,
    tasks,
    events,
    refreshData: loadData,
  };

  return (
    <ShellContext.Provider value={contextValue}>
      <div className="h-screen flex flex-col bg-[var(--bg-base)] text-white overflow-hidden">
        {/* 顶部状态栏 */}
        <TopBar stats={stats} currentView={pathname} />

        {/* 主内容区 */}
        <div className="flex-1 flex overflow-hidden">
          {/* 左侧导航栏 */}
          <Sidebar accounts={accounts} loading={loading} currentPath={pathname} />

          {/* 中间内容区 */}
          <main className="flex-1 overflow-y-auto bg-[var(--bg-base)]">
            {children}
          </main>

          {/* 右侧事件流 */}
          <RightPanel events={events} />
        </div>
      </div>
    </ShellContext.Provider>
  );
}
