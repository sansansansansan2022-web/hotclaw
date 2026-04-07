"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { getAccount, runAccount, enableAccount, disableAccount, getPendingDraftCount } from "@/lib/api";
import type { AccountDetail } from "@/types";

export default function AccountDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const accountId = params?.id;

  // 状态管理
  // account: 账号详情数据
  // pendingDraftCount: 待审核草稿数量
  // loading: 加载状态
  // error: 错误信息
  // actionLoading: 操作中状态（run/toggle）
  const [account, setAccount] = useState<AccountDetail | null>(null);
  const [drafts, setDrafts] = useState<DraftSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // 页面加载时获取账号详情
  useEffect(() => {
    if (!accountId) return;
    loadAccount();
  }, [accountId]);

  async function load() {
    if (!accountId) return;
    setLoading(true);
    setError(null);
    try {
      if (!accountId) return;
      const data = await getAccount(accountId);
      setAccount(data);
      // Fetch pending draft count
      // 仅 semi_auto/full_auto 模式需要显示草稿入口
      if (data.operation_mode !== "full_auto") {
        try {
          const countData = await getPendingDraftCount(data.account_id);
          setPendingDraftCount(countData.count);
        } catch {
          // Ignore error, count is optional
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  /**
   * handleRun - 手动触发账号运行
   *
   * 调用 API: runAccount(accountId)
   * 成功后: 跳转到任务详情页
   */
  async function handleRun() {
    if (!account) return;
    setActionLoading("run");
    try {
      const result = await runAccount(account.account_id);
      router.push(`/task/${result.task_id}`);
    } catch (e) {
      alert(e instanceof Error ? e.message : "启动失败");
    } finally {
      setActionLoading(null);
    }
  }

  /**
   * handleToggleActive - 切换账号启用/禁用状态
   *
   * 调用 API: disableAccount / enableAccount
   * 成功后: 重新加载账号详情
   */
  async function handleToggleActive() {
    if (!account) return;
    setActionLoading("toggle");
    try {
      if (account.is_active) {
        await disableAccount(account.account_id);
      } else {
        await enableAccount(account.account_id);
      }
      await loadAccount();
    } catch (e) {
      alert(e instanceof Error ? e.message : "操作失败");
    } finally {
      setActionLoading(null);
    }
  }

  function formatDate(dateStr: string | null) {
    if (!dateStr) return "-";
    return new Date(dateStr).toLocaleString("zh-CN");
  }

  function getRunStatusBadge(status: string | null) {
    switch (status) {
      case "success":
        return <span className="px-2 py-0.5 text-xs rounded-full bg-green-900/30 text-green-400">成功</span>;
      case "failed":
        return <span className="px-2 py-0.5 text-xs rounded-full bg-red-900/30 text-red-400">失败</span>;
      case "running":
        return <span className="px-2 py-0.5 text-xs rounded-full bg-cyan-900/30 text-cyan-400">运行中</span>;
      case "never_run":
        return <span className="px-2 py-0.5 text-xs rounded-full bg-slate-700 text-slate-400">未运行</span>;
      default:
        return status ? <span className="px-2 py-0.5 text-xs rounded-full bg-slate-700 text-slate-400">{status}</span> : null;
    }
  }

  function getModeLabel(mode: string) {
    switch (mode) {
      case "manual": return "手动";
      case "semi_auto": return "半自动";
      case "full_auto": return "全自动";
      default: return mode;
    }
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
