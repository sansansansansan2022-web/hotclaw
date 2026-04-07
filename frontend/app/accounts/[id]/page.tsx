"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { disableAccount, enableAccount, getAccount, listDrafts, runAccount } from "@/lib/api";
import type { AccountDetail, DraftSummary } from "@/types";
import { PageHeader, SectionCard, StatusBadge, formatDateTime } from "@/components/console-ui";

export default function AccountDetailPage() {
  const params = useParams<{ id: string }>();
  const accountId = params?.id;
  const [account, setAccount] = useState<AccountDetail | null>(null);
  const [drafts, setDrafts] = useState<DraftSummary[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    if (!accountId) return;
    setLoading(true);
    const [a, d] = await Promise.all([getAccount(accountId), listDrafts(1, 20, { account_id: accountId })]);
    setAccount(a);
    setDrafts(d.drafts);
    setLoading(false);
  }

  useEffect(() => { load().catch(console.error); }, [accountId]);

  if (loading || !account) return <div className="min-h-screen bg-[#F5F7FA] p-6">加载中...</div>;

  return (
    <div className="min-h-screen bg-[#F5F7FA] p-6">
      <div className="mx-auto max-w-6xl space-y-4">
        <div><Link href="/accounts" className="text-sm text-emerald-600">← 返回账号管理</Link></div>
        <PageHeader
          title={account.name}
          subtitle="单账号控制台"
          action={<Link href={`/accounts/${account.account_id}/edit`} className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600">编辑账号</Link>}
        />

        <section className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
          <SectionCard title="基本信息">
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <Info label="状态" value={<StatusBadge status={account.is_active ? "success" : "discarded"} />} />
              <Info label="模式" value={<StatusBadge status={account.operation_mode} />} />
              <Info label="定位" value={account.positioning} full />
              <Info label="风格" value={account.tone_style ?? "-"} />
              <Info label="发布频率" value={account.posting_frequency ?? "-"} />
            </dl>
          </SectionCard>
          <SectionCard title="快捷操作">
            <div className="grid grid-cols-2 gap-2">
              <button onClick={() => runAccount(account.account_id).then(load)} className="rounded-lg bg-emerald-500 px-3 py-2 text-sm text-white">立即运行</button>
              {account.is_active ? (
                <button onClick={() => disableAccount(account.account_id).then(load)} className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600">禁用</button>
              ) : (
                <button onClick={() => enableAccount(account.account_id).then(load)} className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600">启用</button>
              )}
              <Link href={`/drafts?account_id=${account.account_id}`} className="rounded-lg border border-slate-200 px-3 py-2 text-center text-sm text-slate-600">查看草稿</Link>
              <Link href={`/settings/wechat/${account.account_id}`} className="rounded-lg border border-slate-200 px-3 py-2 text-center text-sm text-slate-600">微信配置</Link>
            </div>
          </SectionCard>
        </section>

        <SectionCard title="运行状态">
          <div className="grid grid-cols-3 gap-3 text-sm">
            <div><p className="text-slate-500">最近运行</p><p>{formatDateTime(account.last_run_at)}</p></div>
            <div><p className="text-slate-500">下次运行</p><p>{formatDateTime(account.next_run_at)}</p></div>
            <div><p className="text-slate-500">最近错误</p><p className="text-rose-600">{account.last_error_message ?? "-"}</p></div>
          </div>
        </SectionCard>

        <SectionCard title="最近草稿">
          <div className="space-y-2">
            {drafts.slice(0, 6).map((d) => (
              <Link key={d.id} href={`/drafts/${d.id}`} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 hover:bg-slate-50">
                <div>
                  <p className="text-sm text-slate-700">{d.title}</p>
                  <p className="text-xs text-slate-500">{formatDateTime(d.updated_at)}</p>
                </div>
                <div className="flex gap-1"><StatusBadge status={d.draft_status} /><StatusBadge status={d.publish_status} /></div>
              </Link>
            ))}
          </div>
        </SectionCard>
      </div>
    </div>
  );
}

function Info({ label, value, full = false }: { label: string; value: React.ReactNode; full?: boolean }) {
  return (
    <div className={full ? "col-span-2" : ""}>
      <dt className="text-slate-500">{label}</dt>
      <dd className="mt-1 text-slate-700">{value}</dd>
    </div>
  );
}
