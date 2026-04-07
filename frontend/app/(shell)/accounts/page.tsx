"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { runAccount } from "@/lib/api";
import { EmptyState, PageHeader, SectionCard, StatusBadge, formatDateTime } from "@/components/console-ui";
import { useShellContext } from "../context";

export default function AccountsPage() {
  const { accounts, refreshData } = useShellContext();
  const [runningId, setRunningId] = useState<string | null>(null);

  const sortedAccounts = useMemo(() => [...accounts].sort((a, b) => Number(b.is_active) - Number(a.is_active)), [accounts]);

  async function handleRun(accountId: string) {
    setRunningId(accountId);
    try {
      const res = await runAccount(accountId);
      alert(`任务已创建：${res.task_id}`);
      refreshData();
    } catch (e) {
      alert(e instanceof Error ? e.message : "运行失败");
    } finally {
      setRunningId(null);
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="账号管理"
        subtitle="管理运营账号、运行模式与调度状态"
        action={<Link href="/accounts/new" className="rounded-lg bg-emerald-500 px-3 py-2 text-sm text-white">新建账号</Link>}
      />

      <SectionCard title={`账号面板 (${sortedAccounts.length})`}>
        {sortedAccounts.length === 0 ? (
          <EmptyState title="暂无账号" description="先创建账号，才能进入自动运行与发布流程。" action={<Link href="/accounts/new" className="rounded-lg bg-emerald-500 px-3 py-2 text-sm text-white">创建账号</Link>} />
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {sortedAccounts.map((account) => (
              <div key={account.account_id} className="rounded-xl border border-slate-200 p-4">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-base font-semibold text-slate-800">{account.name}</p>
                    <p className="line-clamp-2 text-sm text-slate-500">{account.positioning}</p>
                  </div>
                  <StatusBadge status={account.is_active ? "success" : "discarded"} />
                </div>

                <div className="mt-3 flex flex-wrap gap-1">
                  <StatusBadge status={account.operation_mode} />
                  <StatusBadge status={account.last_run_status ?? "unknown"} />
                  <StatusBadge status={account.auto_run_enabled ? "running" : "draft"} />
                </div>

                <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-slate-500">
                  <div><dt>下次运行</dt><dd>{formatDateTime(account.next_run_at)}</dd></div>
                  <div><dt>最近运行</dt><dd>{formatDateTime(account.last_run_at)}</dd></div>
                </dl>

                <div className="mt-4 flex gap-2">
                  <Link href={`/accounts/${account.account_id}`} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-600">查看</Link>
                  <Link href={`/accounts/${account.account_id}/edit`} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-600">编辑</Link>
                  <button
                    type="button"
                    onClick={() => handleRun(account.account_id)}
                    disabled={runningId === account.account_id}
                    className="rounded-lg bg-emerald-500 px-3 py-1.5 text-xs text-white disabled:opacity-60"
                  >
                    {runningId === account.account_id ? "运行中..." : "立即运行"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </SectionCard>
    </div>
  );
}
