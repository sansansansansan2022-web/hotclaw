"use client";

import Link from "next/link";
import { PageHeader, SectionCard, StatusBadge, formatDateTime } from "@/components/console-ui";
import { useShellContext } from "../context";

export default function PublishRecordsPage() {
  const { drafts } = useShellContext();
  const records = drafts.filter((d) => d.publish_status !== "not_published");

  return (
    <div className="space-y-5">
      <PageHeader title="发布记录" subtitle="按草稿发布状态聚合展示（当前后端无全局 publish_record 列表接口）" />
      <SectionCard title={`记录 (${records.length})`}>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs text-slate-500">
                <th className="px-2 py-2">草稿</th>
                <th className="px-2 py-2">账号</th>
                <th className="px-2 py-2">发布状态</th>
                <th className="px-2 py-2">更新时间</th>
                <th className="px-2 py-2">操作</th>
              </tr>
            </thead>
            <tbody>
              {records.map((row) => (
                <tr key={row.id} className="border-b border-slate-100 last:border-0">
                  <td className="px-2 py-3 text-slate-700">{row.title}</td>
                  <td className="px-2 py-3 text-slate-500">{row.account_id ?? "-"}</td>
                  <td className="px-2 py-3"><StatusBadge status={row.publish_status} /></td>
                  <td className="px-2 py-3 text-slate-500">{formatDateTime(row.updated_at)}</td>
                  <td className="px-2 py-3"><Link className="text-emerald-600 hover:underline" href={`/drafts/${row.id}`}>查看详情</Link></td>
                </tr>
              ))}
              {records.length === 0 && (
                <tr><td className="px-2 py-10 text-center text-slate-400" colSpan={5}>暂无发布记录</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </SectionCard>
    </div>
  );
}
