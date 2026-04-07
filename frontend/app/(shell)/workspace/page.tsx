"use client";

import Link from "next/link";
import { useMemo } from "react";
import { EmptyState, PageHeader, SectionCard, StatusBadge, formatDateTime } from "@/components/console-ui";
import { useShellContext } from "../context";

export default function WorkspacePage() {
  const { drafts, accounts } = useShellContext();

  const columns = useMemo(
    () => [
      { key: "idea", label: "选题池", items: drafts.filter((d) => d.draft_status === "draft") },
      { key: "review", label: "待审核", items: drafts.filter((d) => d.draft_status === "pending_review") },
      { key: "published", label: "已发布", items: drafts.filter((d) => d.publish_status === "published") },
      {
        key: "blocked",
        label: "阻断/失败",
        items: drafts.filter((d) => d.publish_status === "failed" || ["rejected", "discarded"].includes(d.draft_status)),
      },
    ],
    [drafts]
  );

  return (
    <div className="space-y-5">
      <PageHeader
        title="内容工作台"
        subtitle="按内容流转状态查看草稿与发布进展"
        action={<Link href="/workspace" className="rounded-lg bg-emerald-500 px-3 py-2 text-sm text-white">新建任务入口</Link>}
      />

      <SectionCard title="账号筛选（降级）" extra={<span className="text-xs text-slate-500">当前按全账号聚合</span>}>
        <div className="flex flex-wrap gap-2">
          {accounts.slice(0, 8).map((a) => (
            <span key={a.account_id} className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-600">
              {a.name}
            </span>
          ))}
        </div>
      </SectionCard>

      {drafts.length === 0 ? (
        <EmptyState title="暂无内容卡片" description="先在工作台创建任务，系统会生成草稿并进入流转。" action={<Link href="/" className="rounded-lg bg-emerald-500 px-3 py-2 text-sm text-white">返回总览</Link>} />
      ) : (
        <section className="grid gap-4 xl:grid-cols-4">
          {columns.map((column) => (
            <SectionCard key={column.key} title={`${column.label} (${column.items.length})`}>
              <div className="space-y-2">
                {column.items.slice(0, 10).map((item) => (
                  <Link key={item.id} href={`/drafts/${item.id}`} className="block rounded-lg border border-slate-200 p-3 hover:bg-slate-50">
                    <p className="line-clamp-2 text-sm font-medium text-slate-700">{item.title}</p>
                    <p className="mt-1 text-xs text-slate-500">更新于 {formatDateTime(item.updated_at)}</p>
                    <div className="mt-2 flex gap-1">
                      <StatusBadge status={item.draft_status} />
                      <StatusBadge status={item.publish_status} />
                    </div>
                  </Link>
                ))}
                {column.items.length === 0 && <p className="text-xs text-slate-400">暂无数据</p>}
              </div>
            </SectionCard>
          ))}
        </section>
      )}
    </div>
  );
}
