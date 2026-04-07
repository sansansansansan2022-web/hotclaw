"use client";

import Link from "next/link";
import { EmptyState, PageHeader, SectionCard, StatCard, StatusBadge, formatDateTime } from "@/components/console-ui";
import { useShellContext } from "./context";

export default function DashboardPage() {
  const { stats, accounts, drafts } = useShellContext();

  const mainAccount = accounts[0];
  const pendingDrafts = drafts.filter((d) => d.draft_status === "pending_review").slice(0, 5);
  const failedDrafts = drafts.filter((d) => d.publish_status === "failed").slice(0, 5);

  const flow = {
    idea: drafts.filter((d) => d.draft_status === "draft").length,
    review: drafts.filter((d) => d.draft_status === "pending_review").length,
    approved: drafts.filter((d) => d.draft_status === "approved").length,
    published: drafts.filter((d) => d.publish_status === "published").length,
    blocked: drafts.filter((d) => ["failed", "rejected", "discarded"].includes(d.publish_status) || ["rejected", "discarded"].includes(d.draft_status)).length,
  };

  return (
    <div className="space-y-5">
      <PageHeader title="运营总览" subtitle={`${stats.todayTasks} 个任务 · ${stats.pendingDrafts} 待确认 · ${stats.publishedToday} 已发布`} />

      <section className="grid gap-4 xl:grid-cols-[1.6fr_1fr]">
        <SectionCard title="默认账号摘要" extra={<Link href="/accounts" className="text-xs text-emerald-600">切换账号</Link>}>
          {mainAccount ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-lg font-semibold text-slate-800">{mainAccount.name}</p>
                  <p className="text-sm text-slate-500">{mainAccount.positioning}</p>
                </div>
                <div className="flex gap-2">
                  <StatusBadge status={mainAccount.is_active ? "success" : "discarded"} />
                  <StatusBadge status={mainAccount.operation_mode} />
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link href={`/accounts/${mainAccount.account_id}`} className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600">查看详情</Link>
                <Link href={`/accounts/${mainAccount.account_id}/edit`} className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600">编辑账号</Link>
                <Link href={`/settings/wechat/${mainAccount.account_id}`} className="rounded-lg bg-emerald-500 px-3 py-1.5 text-sm text-white">连接公众号</Link>
              </div>
            </div>
          ) : (
            <EmptyState title="尚未创建账号" description="先创建运营账号，再开始任务调度与发布。" action={<Link className="rounded-lg bg-emerald-500 px-3 py-2 text-sm text-white" href="/accounts/new">新建账号</Link>} />
          )}
        </SectionCard>

        <SectionCard title="快捷创作">
          <p className="text-sm text-slate-500">当前工作台支持输入定位并创建任务，适合运营快速发起创作。</p>
          <div className="mt-3 flex gap-2">
            <Link href="/workspace" className="rounded-lg bg-emerald-500 px-3 py-2 text-sm text-white">进入工作台</Link>
            <Link href="/history" className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600">查看任务历史</Link>
          </div>
        </SectionCard>
      </section>

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="今日任务" value={stats.todayTasks} href="/history" />
        <StatCard label="待确认草稿" value={stats.pendingDrafts} tone="warning" href="/drafts?draft_status=pending_review" />
        <StatCard label="已发布" value={stats.publishedToday} tone="success" href="/drafts?publish_status=published" />
        <StatCard label="发布失败" value={stats.publishFailed} tone="danger" href="/drafts?publish_status=failed" />
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <SectionCard title="待处理中心">
          {[...pendingDrafts, ...failedDrafts].length === 0 ? (
            <EmptyState title="暂无待处理事项" description="当前审核与发布队列为空。" action={<Link href="/workspace" className="rounded-lg bg-emerald-500 px-3 py-2 text-sm text-white">创建任务</Link>} />
          ) : (
            <div className="space-y-2">
              {[...pendingDrafts, ...failedDrafts].slice(0, 6).map((d) => (
                <Link key={d.id} href={`/drafts/${d.id}`} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 hover:bg-slate-50">
                  <div>
                    <p className="text-sm font-medium text-slate-700">{d.title}</p>
                    <p className="text-xs text-slate-500">更新时间：{formatDateTime(d.updated_at)}</p>
                  </div>
                  <StatusBadge status={d.publish_status === "failed" ? "failed" : d.draft_status} />
                </Link>
              ))}
            </div>
          )}
        </SectionCard>

        <SectionCard title="内容流转">
          <div className="grid grid-cols-2 gap-3">
            {[
              ["选题池", flow.idea],
              ["待审核", flow.review],
              ["可发布", flow.approved],
              ["已发布", flow.published],
              ["阻断/失败", flow.blocked],
            ].map(([label, count]) => (
              <div key={String(label)} className="rounded-lg bg-slate-50 px-3 py-3">
                <p className="text-xs text-slate-500">{label}</p>
                <p className="mt-1 text-2xl font-semibold text-slate-700">{count}</p>
              </div>
            ))}
          </div>
        </SectionCard>
      </section>
    </div>
  );
}
