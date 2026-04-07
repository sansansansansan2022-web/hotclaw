"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { confirmPublishDraft, discardDraft, getDraft, getDraftPublishRecords, publishDraftToWeChat, refreshPublishStatus, rerunFromDraft, retryPublishDraft } from "@/lib/api";
import type { DraftDetail, PublishRecord } from "@/types";
import { PageHeader, SectionCard, StatusBadge, formatDateTime } from "@/components/console-ui";

export default function DraftDetailPage() {
  const params = useParams<{ id: string }>();
  const draftId = Number(params?.id);
  const [draft, setDraft] = useState<DraftDetail | null>(null);
  const [records, setRecords] = useState<PublishRecord[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    if (!draftId) return;
    setLoading(true);
    const [detail, rec] = await Promise.all([getDraft(draftId), getDraftPublishRecords(draftId).catch(() => ({ records: [] as PublishRecord[] }))]);
    setDraft(detail);
    setRecords(rec.records ?? []);
    setLoading(false);
  }
  useEffect(() => { load().catch(console.error); }, [draftId]);

  if (loading || !draft) return <div className="min-h-screen bg-[#F5F7FA] p-6">加载中...</div>;

  const latestRecord = records[0];

  return (
    <div className="min-h-screen bg-[#F5F7FA] p-6">
      <div className="mx-auto grid max-w-7xl gap-4 xl:grid-cols-[1.6fr_1fr]">
        <div className="space-y-4">
          <div><Link href="/drafts" className="text-sm text-emerald-600">← 返回草稿箱</Link></div>
          <PageHeader title={draft.title} subtitle={`草稿 #${draft.id}`} />

          <SectionCard title="正文预览">
            <div className="prose prose-sm max-w-none text-slate-700">
              <pre className="whitespace-pre-wrap font-sans">{draft.content_markdown}</pre>
            </div>
          </SectionCard>

          <SectionCard title="审核结果">
            {draft.audit_result ? (
              <div className="space-y-2 text-sm text-slate-600">
                <p>risk_level: <strong>{draft.audit_result.risk_level}</strong></p>
                <p>overall_comment: {draft.audit_result.overall_comment ?? "-"}</p>
                <p>issues: {Array.isArray(draft.audit_result.issues) ? draft.audit_result.issues.length : 0}</p>
              </div>
            ) : <p className="text-sm text-slate-500">暂无审核结果</p>}
          </SectionCard>
        </div>

        <div className="space-y-4">
          <SectionCard title="状态信息">
            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between"><span className="text-slate-500">草稿状态</span><StatusBadge status={draft.draft_status} /></div>
              <div className="flex items-center justify-between"><span className="text-slate-500">发布状态</span><StatusBadge status={draft.publish_status} /></div>
              <div><p className="text-slate-500">最近失败原因</p><p className="text-rose-600">{draft.publish_error_message ?? "-"}</p></div>
              <div><p className="text-slate-500">已发布链接</p><p>{latestRecord?.url ? <a className="text-emerald-600" href={latestRecord.url} target="_blank">查看文章</a> : "-"}</p></div>
            </div>
          </SectionCard>

          <SectionCard title="操作">
            <div className="grid grid-cols-2 gap-2 text-sm">
              <button onClick={() => confirmPublishDraft(draft.id).then(load)} className="rounded-lg bg-emerald-500 px-3 py-2 text-white">确认发布</button>
              <button onClick={() => discardDraft(draft.id).then(load)} className="rounded-lg border border-slate-200 px-3 py-2">废弃</button>
              <button onClick={() => retryPublishDraft(draft.id).then(load)} className="rounded-lg border border-slate-200 px-3 py-2">重试发布</button>
              <button onClick={() => publishDraftToWeChat(draft.id).then(load)} className="rounded-lg border border-slate-200 px-3 py-2">立即发布</button>
              <button onClick={() => latestRecord && refreshPublishStatus(latestRecord.id).then(load)} className="rounded-lg border border-slate-200 px-3 py-2">刷新状态</button>
              <button onClick={() => rerunFromDraft(draft.id).then((r) => (window.location.href = `/task/${r.new_task_id}`))} className="rounded-lg border border-slate-200 px-3 py-2">重跑</button>
            </div>
          </SectionCard>

          <SectionCard title="发布记录">
            <div className="space-y-2">
              {records.map((r) => (
                <div key={r.id} className="rounded-lg border border-slate-200 p-2 text-xs text-slate-600">
                  <div className="flex items-center justify-between"><span>#{r.id}</span><StatusBadge status={r.publish_status} /></div>
                  <div className="mt-1">{formatDateTime(r.created_at)}</div>
                </div>
              ))}
              {records.length === 0 && <p className="text-xs text-slate-400">暂无发布记录</p>}
            </div>
          </SectionCard>
        </div>
      </div>
    </div>
  );
}
