"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getDraftPublishRecords, listAccounts, listDrafts, refreshPublishStatus } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { formatDateTime, formatNumber, truncate } from "@/lib/utils";
import type { PublishRecord } from "@/types";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, SkeletonRows, StatCard, Table } from "@/components/console/ui";
import { Icon } from "@/components/console/icons";
import { useAppStore } from "@/store/appStore";

function publishTone(status: string): "success" | "warning" | "danger" | "muted" {
  if (status === "published") return "success";
  if (status === "failed") return "danger";
  if (status === "pending" || status === "publishing") return "warning";
  return "muted";
}

export function PublishLogsPage() {
  const { locale, t, publishStatusLabel } = useI18n();
  const pushToast = useAppStore((state) => state.pushToast);
  const [rows, setRows] = useState<Array<PublishRecord & { draftTitle: string; accountName: string }>>([]);
  const [draftCount, setDraftCount] = useState(0);
  const [accountCount, setAccountCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      const [draftsRes, accountsRes] = await Promise.all([
        listDrafts(1, 100).catch(() => ({ drafts: [], pagination: { page: 1, page_size: 100, total: 0 } })),
        listAccounts(1, 100).catch(() => ({ accounts: [], pagination: { page: 1, page_size: 100, total: 0 } })),
      ]);

      const accountMap = new Map(accountsRes.accounts.map((account) => [account.account_id, account.name]));
      setDraftCount(draftsRes.drafts.length);
      setAccountCount(accountsRes.accounts.length);
      const results = await Promise.all(
        draftsRes.drafts.map(async (draft) => {
          const records = await getDraftPublishRecords(draft.id).catch(() => ({ draft_id: draft.id, total: 0, records: [] }));
          return records.records.map((record) => ({
            ...record,
            draftTitle: draft.title,
            accountName: draft.account_id ? accountMap.get(draft.account_id) ?? (locale === "zh-CN" ? "未知账号" : "Unknown account") : (locale === "zh-CN" ? "未分配" : "Unassigned"),
          }));
        }),
      );

      setRows(results.flat().sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime()));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : t("publish.loadError"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const stats = useMemo(() => {
    const failed = rows.filter((row) => row.publish_status === "failed").length;
    const pending = rows.filter((row) => row.publish_status === "pending" || row.publish_status === "publishing").length;
    return { failed, pending };
  }, [rows]);

  const refresh = async (recordId: number) => {
    try {
      const updated = await refreshPublishStatus(recordId);
      pushToast({ tone: "success", title: t("publish.statusRefreshed"), message: updated.message });
      await load();
    } catch (refreshError) {
      pushToast({
        tone: "danger",
        title: t("publish.refreshFailed"),
        message: refreshError instanceof Error ? refreshError.message : (locale === "zh-CN" ? "发生了意外错误" : "Unexpected error"),
      });
    }
  };

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={t("publish.eyebrow")}
        title={t("publish.title")}
        description={t("publish.description")}
      />

      <div className="grid gap-5 md:grid-cols-3">
        <StatCard label={t("publish.records")} value={formatNumber(rows.length)} hint={locale === "zh-CN" ? "由每个草稿的记录聚合出的全局视图" : "Global view composed from per-draft records"} tone="brand" icon={<Icon name="publish" className="h-6 w-6" />} />
        <StatCard label={t("publish.pendingSync")} value={formatNumber(stats.pending)} hint={locale === "zh-CN" ? "仍处于 pending 或 publishing 状态的记录" : "Records still in pending or publishing state"} tone="warning" icon={<Icon name="refresh" className="h-6 w-6" />} />
        <StatCard label={t("publish.failedPublishes")} value={formatNumber(stats.failed)} hint={locale === "zh-CN" ? "需要重试或检查配置的记录" : "Records that need a retry or config check"} tone="danger" icon={<Icon name="warning" className="h-6 w-6" />} />
      </div>

      {loading ? (
        <SkeletonRows rows={6} />
      ) : error ? (
        <ErrorState title={t("publish.loadError")} description={error} retry={() => void load()} />
      ) : rows.length ? (
        <Table columns={[locale === "zh-CN" ? "草稿" : "Draft", locale === "zh-CN" ? "账号" : "Account", locale === "zh-CN" ? "状态" : "Status", locale === "zh-CN" ? "尝试次数" : "Attempt", locale === "zh-CN" ? "创建时间" : "Created", locale === "zh-CN" ? "信息" : "Message", locale === "zh-CN" ? "操作" : "Action"]}>
          {rows.map((row) => (
            <tr key={row.id}>
              <td className="px-5 py-4">
                <div>
                  <p className="text-sm font-semibold text-slate-900">{row.draftTitle}</p>
                  <p className="mt-1 text-xs text-slate-500">{locale === "zh-CN" ? `记录 #${row.id}` : `Record #${row.id}`}</p>
                </div>
              </td>
              <td className="px-5 py-4 text-sm text-slate-600">{row.accountName}</td>
              <td className="px-5 py-4">
                <Badge tone={publishTone(row.publish_status)}>{publishStatusLabel(row.publish_status)}</Badge>
              </td>
              <td className="px-5 py-4 text-sm text-slate-600">
                {locale === "zh-CN" ? `第 ${row.publish_attempt} 次尝试` : `Attempt ${row.publish_attempt}`}
                <div className="text-xs text-slate-400">{locale === "zh-CN" ? `重试 ${row.retry_count}` : `Retry ${row.retry_count}`}</div>
              </td>
              <td className="px-5 py-4 text-sm text-slate-600">{formatDateTime(row.created_at)}</td>
              <td className="px-5 py-4 text-sm text-slate-500">{truncate(row.error_message, 80) || row.url || (locale === "zh-CN" ? "无错误信息" : "No error message")}</td>
              <td className="px-5 py-4">
                <div className="flex gap-2">
                  <Link href={`/drafts/${row.draft_id}`}>
                    <Button variant="secondary" size="sm">
                      {t("publish.viewDraft")}
                    </Button>
                  </Link>
                  <Button variant="ghost" size="sm" onClick={() => void refresh(row.id)}>
                    {t("publish.refresh")}
                  </Button>
                </div>
              </td>
            </tr>
          ))}
        </Table>
      ) : (
        <div className="grid gap-6 xl:grid-cols-[1.2fr_0.9fr]">
          <Card title={t("publish.noRecords")} description={t("publish.noRecordsDesc")}>
            <EmptyState
              title={t("publish.emptyTitle")}
              description={t("publish.emptyDesc")}
              action={
                <div className="flex flex-wrap items-center justify-center gap-3">
                  <Link href="/drafts">
                    <Button>{t("publish.openDrafts")}</Button>
                  </Link>
                  <Link href="/settings/wechat">
                    <Button variant="secondary">{t("publish.reviewWechat")}</Button>
                  </Link>
                </div>
              }
            />
          </Card>

          <Card title={locale === "zh-CN" ? "数据覆盖情况" : "Data Coverage"} description={locale === "zh-CN" ? "当前后端为本页面提供的数据范围。" : "What the backend is currently exposing to this page."}>
            <div className="space-y-4">
              <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "扫描草稿数" : "Drafts scanned"}</p>
                <p className="mt-2 text-2xl font-semibold text-slate-950">{formatNumber(draftCount)}</p>
                <p className="mt-1 text-sm text-slate-500">{locale === "zh-CN" ? "由于还没有全局 publish-log 接口，当前会逐个草稿查询发布记录。" : "Each draft is queried for publish records because no global publish-log endpoint exists yet."}</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "可用账号数" : "Accounts available"}</p>
                <p className="mt-2 text-2xl font-semibold text-slate-950">{formatNumber(accountCount)}</p>
                <p className="mt-1 text-sm text-slate-500">{locale === "zh-CN" ? "当有记录时，会再结合账号元数据补齐账号名称。" : "Account names are joined in from account metadata when records are present."}</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                <p className="text-sm font-semibold text-slate-900">{locale === "zh-CN" ? "下一步解锁条件" : "Next unlock condition"}</p>
                <p className="mt-1 text-sm leading-6 text-slate-500">{locale === "zh-CN" ? "审核通过一个草稿并推入微信发布流程。下一次成功或失败尝试会自动填充这里的表格。" : "Approve a draft and push it into the WeChat publish flow. The next successful or failed attempt will automatically populate this table."}</p>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
