"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { listAccounts } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { formatDateTime, formatNumber, truncate } from "@/lib/utils";
import type { AccountSummary } from "@/types";
import { Badge, Button, EmptyState, ErrorState, PageHeader, SkeletonRows, StatCard, Table } from "@/components/console/ui";
import { Icon } from "@/components/console/icons";

function accountTone(status: string | null): "success" | "warning" | "danger" | "muted" {
  if (status === "running") return "warning";
  if (status === "failed") return "danger";
  if (status === "completed") return "success";
  return "muted";
}

export function AccountManagementPage() {
  const { locale, t, operationModeLabel, taskStatusLabel, token } = useI18n();
  const [accounts, setAccounts] = useState<AccountSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await listAccounts(1, 100);
      setAccounts(response.accounts);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : t("accounts.loadError"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const metrics = useMemo(() => {
    const active = accounts.filter((account) => account.is_active).length;
    const autoRun = accounts.filter((account) => account.auto_run_enabled).length;
    const attention = accounts.filter((account) => account.last_run_status === "failed" || !account.posting_frequency).length;
    return { active, autoRun, attention };
  }, [accounts]);

  /* Legacy direct-run stays archived on account detail/workspace. The list page
     should only route users into the new task flow. */

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Managed Accounts"
        title={t("accounts.title")}
        description={t("accounts.description")}
        actions={
          <Link href="/accounts/new">
            <Button>
              <Icon name="plus" className="h-4 w-4" />
              {locale === "zh-CN" ? "接入公众号" : "Connect Account"}
            </Button>
          </Link>
        }
      />

      <div className="grid gap-5 md:grid-cols-3">
        <StatCard
          label={t("accounts.accounts")}
          value={formatNumber(accounts.length)}
          hint={locale === "zh-CN" ? `${metrics.active} 个启用账号` : `${metrics.active} active accounts`}
          tone="brand"
          icon={<Icon name="accounts" className="h-6 w-6" />}
        />
        <StatCard
          label={t("accounts.automationEnabled")}
          value={formatNumber(metrics.autoRun)}
          hint={locale === "zh-CN" ? "参与调度器的账号" : "Accounts participating in the scheduler"}
          tone="success"
          icon={<Icon name="play" className="h-6 w-6" />}
        />
        <StatCard
          label={t("accounts.needsAttention")}
          value={formatNumber(metrics.attention)}
          hint={locale === "zh-CN" ? "缺少节奏配置或最近运行异常" : "Missing cadence or last run issues"}
          tone="warning"
          icon={<Icon name="warning" className="h-6 w-6" />}
        />
      </div>

      {loading ? (
        <SkeletonRows rows={6} />
      ) : error ? (
        <ErrorState title={t("accounts.loadError")} description={error} retry={() => void load()} />
      ) : accounts.length ? (
        <Table
          columns={[
            locale === "zh-CN" ? "账号" : "Account",
            locale === "zh-CN" ? "模式" : "Mode",
            locale === "zh-CN" ? "最近运行" : "Last Run",
            locale === "zh-CN" ? "下次运行" : "Next Run",
            locale === "zh-CN" ? "状态" : "State",
            locale === "zh-CN" ? "操作" : "Action",
          ]}
        >
          {accounts.map((account) => (
            <tr key={account.account_id}>
              <td className="px-5 py-4">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold text-slate-900">{account.name}</p>
                    <Badge tone={account.is_active ? "success" : "muted"}>{token(account.is_active ? "active" : "paused")}</Badge>
                  </div>
                  <p className="mt-1 text-sm text-slate-500">{truncate(account.positioning, 100)}</p>
                </div>
              </td>
              <td className="px-5 py-4">
                <Badge tone="info">{operationModeLabel(account.operation_mode)}</Badge>
              </td>
              <td className="px-5 py-4 text-sm text-slate-600">{formatDateTime(account.last_run_at)}</td>
              <td className="px-5 py-4 text-sm text-slate-600">{formatDateTime(account.next_run_at)}</td>
              <td className="px-5 py-4">
                <Badge tone={accountTone(account.last_run_status)}>{taskStatusLabel(account.last_run_status)}</Badge>
              </td>
              <td className="px-5 py-4">
                <div className="flex gap-2">
                  <Link href={`/accounts/${account.account_id}`}>
                    <Button variant="secondary" size="sm">
                      {t("accounts.view")}
                    </Button>
                  </Link>
                  <Link href={`/accounts/${account.account_id}/create`}>
                    <Button size="sm">
                      {locale === "zh-CN" ? "新建任务" : "New Task"}
                    </Button>
                  </Link>
                </div>
              </td>
            </tr>
          ))}
        </Table>
      ) : (
        <EmptyState
          title={t("accounts.emptyTitle")}
          description={t("accounts.emptyDesc")}
          action={
            <Link href="/accounts/new">
              <Button>{locale === "zh-CN" ? "接入第一个公众号" : "Connect Your First Account"}</Button>
            </Link>
          }
        />
      )}
    </div>
  );
}
