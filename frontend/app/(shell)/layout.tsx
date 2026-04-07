"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { listAccounts, listDrafts, listTasks } from "@/lib/api";
import type { AccountSummary, DraftSummary, TaskSummary } from "@/types";
import { ShellContext, type DashboardStats, type RecentEvent, type ShellContextValue } from "./context";
import { ShellNav, StatusBadge, formatDateTime } from "@/components/console-ui";

const NAV_ITEMS = [
  { href: "/", label: "运营总览" },
  { href: "/workspace", label: "内容工作台" },
  { href: "/accounts", label: "账号管理" },
  { href: "/drafts", label: "草稿中心" },
  { href: "/publish-records", label: "发布记录" },
  { href: "/history", label: "任务历史" },
  { href: "/settings", label: "设置" },
];

export { useShellContext } from "./context";

function TopBar({ stats }: { stats: DashboardStats }) {
  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 px-5 py-3 backdrop-blur">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-lg font-semibold text-slate-800">HotClaw 运营控制台</p>
          <p className="text-xs text-slate-500">账号运营 · 审核发布 · 任务追踪</p>
        </div>
        <div className="grid grid-cols-4 gap-2 text-right">
          <Metric label="今日任务" value={stats.todayTasks} />
          <Metric label="待确认" value={stats.pendingDrafts} />
          <Metric label="已发布" value={stats.publishedToday} />
          <Metric label="发布失败" value={stats.publishFailed} danger />
        </div>
      </div>
    </header>
  );
}

function Metric({ label, value, danger = false }: { label: string; value: number; danger?: boolean }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2">
      <p className="text-[11px] text-slate-500">{label}</p>
      <p className={`text-base font-semibold ${danger ? "text-rose-600" : "text-slate-700"}`}>{value}</p>
    </div>
  );
}

function RightActivity({ events }: { events: RecentEvent[] }) {
  return (
    <aside className="hidden w-[300px] border-l border-slate-200 bg-white xl:block">
      <div className="border-b border-slate-100 px-4 py-3">
        <p className="text-sm font-semibold text-slate-700">活动流</p>
      </div>
      <div className="space-y-2 p-3">
        {events.slice(0, 10).map((event) => (
          <div key={event.id} className="rounded-lg border border-slate-200 p-3">
            <div className="mb-1 flex items-center justify-between">
              <p className="text-sm text-slate-700">{event.action}</p>
              <StatusBadge status={event.status} />
            </div>
            <p className="line-clamp-2 text-xs text-slate-500">{event.title}</p>
            <p className="mt-2 text-xs text-slate-400">{event.time}</p>
          </div>
        ))}
      </div>
      <div className="px-3 pb-4">
        <Link href="/history" className="block rounded-lg border border-slate-200 px-3 py-2 text-center text-xs text-slate-600 hover:bg-slate-50">
          查看全部历史
        </Link>
      </div>
    </aside>
  );
}

export default function ShellLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [accounts, setAccounts] = useState<AccountSummary[]>([]);
  const [drafts, setDrafts] = useState<DraftSummary[]>([]);
  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [stats, setStats] = useState<DashboardStats>({ todayTasks: 0, pendingDrafts: 0, publishedToday: 0, publishFailed: 0 });
  const [events, setEvents] = useState<RecentEvent[]>([]);

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
    loadData().catch(console.error);
    const timer = setInterval(() => loadData().catch(console.error), 30000);
    return () => clearInterval(timer);
  }, [loadData]);

  const contextValue: ShellContextValue = { stats, accounts, drafts, tasks, events, refreshData: () => void loadData() };

  return (
    <ShellContext.Provider value={contextValue}>
      <div className="min-h-screen bg-[#F5F7FA] text-slate-800">
        <TopBar stats={stats} />
        <div className="flex min-h-[calc(100vh-73px)]">
          <aside className="sticky top-[73px] hidden h-[calc(100vh-73px)] w-[240px] shrink-0 border-r border-slate-200 bg-white p-4 lg:block">
            <div className="mb-4 rounded-xl bg-emerald-50 p-3">
              <p className="text-sm font-semibold text-emerald-700">导航</p>
              <p className="text-xs text-emerald-600">{pathname}</p>
            </div>
            <ShellNav items={NAV_ITEMS} />
          </aside>
          <main className="flex-1 overflow-x-hidden p-5">
            <div className="mx-auto w-full max-w-[1280px]">{children}</div>
          </main>
          <RightActivity events={events} />
        </div>
      </div>
    </ShellContext.Provider>
  );
}
