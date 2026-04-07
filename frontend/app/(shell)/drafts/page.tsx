"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { FilterTabs, PageHeader, SectionCard, StatusBadge, formatDateTime } from "@/components/console-ui";
import { useShellContext } from "../context";

export default function DraftsPage() {
  const { drafts } = useShellContext();
  const [tab, setTab] = useState("all");

  const rows = useMemo(() => {
    return drafts.filter((d) => {
      if (tab === "all") return true;
      if (tab === "pending_review") return d.draft_status === "pending_review";
      if (tab === "published") return d.publish_status === "published";
      if (tab === "rejected") return d.draft_status === "rejected";
      if (tab === "discarded") return d.draft_status === "discarded";
      if (tab === "failed") return d.publish_status === "failed";
      return true;
    });
  }, [drafts, tab]);

  return (
    <div className="space-y-5">
      <PageHeader title="草稿管理中心" subtitle={`共 ${drafts.length} 条草稿`} />

      <SectionCard
        title="筛选"
        extra={
          <FilterTabs
            value={tab}
            onChange={setTab}
            tabs={[
              { key: "all", label: "全部" },
              { key: "pending_review", label: "待确认" },
              { key: "published", label: "已发布" },
              { key: "failed", label: "发布失败" },
              { key: "rejected", label: "已拒绝" },
              { key: "discarded", label: "已废弃" },
            ]}
          />
        }
      >
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs text-slate-500">
                <th className="px-2 py-2">标题</th>
                <th className="px-2 py-2">账号</th>
                <th className="px-2 py-2">草稿状态</th>
                <th className="px-2 py-2">发布状态</th>
                <th className="px-2 py-2">字数</th>
                <th className="px-2 py-2">更新时间</th>
                <th className="px-2 py-2">操作</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-b border-slate-100 last:border-0">
                  <td className="px-2 py-3 text-slate-700">{row.title}</td>
                  <td className="px-2 py-3 text-slate-500">{row.account_id ?? "-"}</td>
                  <td className="px-2 py-3"><StatusBadge status={row.draft_status} /></td>
                  <td className="px-2 py-3"><StatusBadge status={row.publish_status} /></td>
                  <td className="px-2 py-3 text-slate-500">{row.word_count}</td>
                  <td className="px-2 py-3 text-slate-500">{formatDateTime(row.updated_at)}</td>
                  <td className="px-2 py-3">
                    <Link href={`/drafts/${row.id}`} className="text-emerald-600 hover:underline">查看</Link>
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td className="px-2 py-10 text-center text-slate-400" colSpan={7}>暂无数据</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </SectionCard>
    </div>
  );
}
