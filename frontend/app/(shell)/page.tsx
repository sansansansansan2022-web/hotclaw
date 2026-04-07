"use client";

import Link from "next/link";
import { EmptyState, PageHeader, SectionCard, StatCard, StatusBadge, formatDateTime } from "@/components/console-ui";
import { useShellContext } from "./context";

const PAGE_CONTAINER = "max-w-[1320px] mx-auto px-6 lg:px-8 py-6 space-y-5";
const PANEL = "rounded-xl bg-[#111827] border border-white/10";

function MetricCard({
  label,
  value,
  icon,
  tone,
  href,
}: {
  label: string;
  value: number;
  icon: string;
  tone: "cyan" | "yellow" | "green" | "red";
  href: string;
}) {
  const toneMap = {
    cyan: "text-cyan-400",
    yellow: "text-amber-400",
    green: "text-emerald-400",
    red: "text-rose-400",
  };

  return (
    <Link
      href={href}
      className={`${PANEL} p-4 hover:border-cyan-400/35 transition-colors`}
    >
      <div className="flex items-start justify-between">
        <div>
          <div className="text-[12px] text-white/55">{label}</div>
          <div className={`text-[30px] font-semibold leading-none mt-2 ${toneMap[tone]}`}>
            {value}
          </div>
        </div>
        <span className="text-lg opacity-80">{icon}</span>
      </div>
    </Link>
  );
}

function StatusDot({ status }: { status: "success" | "pending" | "failed" | "idle" }) {
  const cls = {
    success: "bg-emerald-400",
    pending: "bg-amber-400",
    failed: "bg-rose-400",
    idle: "bg-white/30",
  };
  return <span className={`inline-block w-2 h-2 rounded-full ${cls[status]}`} />;
}

function PendingCenter() {
  const { drafts } = useShellContext();

  const pending = drafts.filter((d) => d.draft_status === "pending_review");
  const failed = drafts.filter((d) => d.publish_status === "failed");
  const items = [
    ...pending.map((d) => ({ id: d.id, title: d.title, kind: "待确认" as const, href: `/drafts/${d.id}` })),
    ...failed.map((d) => ({ id: d.id, title: d.title, kind: "发布失败" as const, href: `/drafts/${d.id}` })),
  ].slice(0, 6);

  if (items.length === 0) {
    return (
      <section className={`${PANEL} p-6`}>
        <div className="text-sm text-white/80 font-medium">待处理中心</div>
        <div className="mt-6 rounded-lg bg-[#0F172A] border border-white/10 p-8 text-center">
          <div className="text-3xl mb-3">🎉</div>
          <div className="text-white font-medium">没有待处理事项</div>
          <div className="text-xs text-white/50 mt-2">当前内容流程运行正常</div>
          <div className="flex items-center justify-center gap-3 mt-5">
            <Link href="/workspace" className="px-4 py-2 rounded-md bg-cyan-500 text-slate-950 text-sm font-medium">创建任务</Link>
            <Link href="/drafts" className="px-4 py-2 rounded-md border border-white/15 text-white/75 text-sm hover:text-white">查看草稿</Link>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className={`${PANEL} overflow-hidden`}>
      <div className="px-5 py-4 border-b border-white/10 flex items-center justify-between">
        <div className="text-sm text-white/85 font-medium">待处理中心</div>
        <Link href="/drafts" className="text-xs text-cyan-300 hover:text-cyan-200">前往处理 →</Link>
      </div>
      <div className="divide-y divide-white/10">
        {items.map((item) => (
          <Link
            key={`${item.kind}-${item.id}`}
            href={item.href}
            className="px-5 py-3 flex items-center justify-between hover:bg-white/[0.03] transition-colors"
          >
            <div className="min-w-0">
              <div className="text-sm text-white truncate">{item.title}</div>
              <div className="mt-1 text-xs text-white/45">{item.kind}</div>
            </div>
            <span
              className={`text-[11px] px-2 py-1 rounded-md border ${
                item.kind === "待确认"
                  ? "text-amber-300 border-amber-300/35"
                  : "text-rose-300 border-rose-300/35"
              }`}
            >
              {item.kind}
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}

function FlowBoard() {
  const { drafts } = useShellContext();
  const counts = {
    generating: drafts.filter((d) => d.draft_status === "draft").length,
    pending: drafts.filter((d) => d.draft_status === "pending_review").length,
    published: drafts.filter((d) => d.publish_status === "published").length,
    failed: drafts.filter((d) => d.publish_status === "failed").length,
  };

  const cards = [
    { label: "生成中", value: counts.generating, tone: "text-cyan-300" },
    { label: "待确认", value: counts.pending, tone: "text-amber-300" },
    { label: "已发布", value: counts.published, tone: "text-emerald-300" },
    { label: "失败", value: counts.failed, tone: "text-rose-300" },
  ];

  return (
    <section className={`${PANEL} p-5`}>
      <div className="text-sm text-white/85 font-medium mb-4">内容流转看板</div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {cards.map((c) => (
          <div key={c.label} className="rounded-lg bg-[#0F172A] border border-white/10 px-4 py-3">
            <div className="text-xs text-white/50">{c.label}</div>
            <div className={`text-2xl font-semibold mt-1 ${c.tone}`}>{c.value}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

function RecentAccountsPanel() {
  const { accounts } = useShellContext();

  const top = accounts.slice(0, 6);

  return (
    <section className={`${PANEL} overflow-hidden`}>
      <div className="px-5 py-4 border-b border-white/10 flex items-center justify-between">
        <div className="text-sm text-white/85 font-medium">最近账号运行</div>
        <Link href="/accounts" className="text-xs text-cyan-300 hover:text-cyan-200">管理账号 →</Link>
      </div>
      {top.length === 0 ? (
        <div className="px-5 py-8 text-sm text-white/45">暂无账号，先创建一个账号开始运行。</div>
      ) : (
        <div className="divide-y divide-white/10">
          {top.map((account) => {
            const runStatus = account.last_run_status === "success"
              ? "success"
              : account.last_run_status === "failed"
              ? "failed"
              : account.last_run_status === "running"
              ? "pending"
              : "idle";

            return (
              <Link
                key={account.account_id}
                href={`/accounts/${account.account_id}`}
                className="px-5 py-3 flex items-center justify-between hover:bg-white/[0.03] transition-colors"
              >
                <div className="min-w-0">
                  <div className="text-sm text-white truncate">{account.name}</div>
                  <div className="mt-1 text-xs text-white/45">
                    上次运行：{account.last_run_at ? new Date(account.last_run_at).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }) : "-"}
                  </div>
                </div>
                <div className="flex items-center gap-2 text-xs text-white/70">
                  <StatusDot status={runStatus} />
                  <span>
                    {runStatus === "success" ? "正常运行" : runStatus === "failed" ? "运行失败" : runStatus === "pending" ? "执行中" : "未运行"}
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </section>
  );
}

export default function DashboardView() {
  const { stats } = useShellContext();

  return (
    <div className={PAGE_CONTAINER}>
      <section className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight text-white">运营总览</h1>
        <p className="text-sm text-white/55">
          {stats.todayTasks} 个任务 · {stats.pendingDrafts} 待确认 · {stats.publishedToday} 已发布
        </p>
      </section>

      <section className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <MetricCard label="今日任务" value={stats.todayTasks} icon="📘" tone="cyan" href="/history" />
        <MetricCard label="待确认草稿" value={stats.pendingDrafts} icon="📒" tone="yellow" href="/drafts?draft_status=pending_review" />
        <MetricCard label="今日发布" value={stats.publishedToday} icon="✅" tone="green" href="/drafts?publish_status=published" />
        <MetricCard label="发布失败" value={stats.publishFailed} icon="❌" tone="red" href="/drafts?publish_status=failed" />
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-[1.35fr_1fr] gap-4">
        <PendingCenter />
        <FlowBoard />
      </section>

      <RecentAccountsPanel />
    </div>
  );
}
