"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { listAccounts, listDrafts } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { formatDateTime, formatNumber, truncate } from "@/lib/utils";
import type { AccountSummary, DraftSummary } from "@/types";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, Select, SkeletonRows, StatCard, Table } from "@/components/console/ui";

function draftTone(status: string): "brand" | "success" | "warning" | "danger" | "muted" {
  if (status === "approved" || status === "published") return "success";
  if (status === "pending_review") return "warning";
  if (status === "rejected" || status === "discarded") return "danger";
  if (status === "failed") return "danger";
  if (status === "pending" || status === "publishing") return "warning";
  return "muted";
}

export function DraftsCenterPage() {
  const { locale, t, draftStatusLabel, publishStatusLabel } = useI18n();
  const [drafts, setDrafts] = useState<DraftSummary[]>([]);
  const [accounts, setAccounts] = useState<AccountSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [draftStatus, setDraftStatus] = useState<string>("all");
  const [publishStatus, setPublishStatus] = useState<string>("all");
  const [accountId, setAccountId] = useState<string>("all");

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      const [draftsRes, accountsRes] = await Promise.all([
        listDrafts(1, 100, {
          draft_status: draftStatus === "all" ? undefined : draftStatus,
          publish_status: publishStatus === "all" ? undefined : publishStatus,
          account_id: accountId === "all" ? undefined : accountId,
        }),
        listAccounts(1, 100).catch(() => ({ accounts: [], pagination: { page: 1, page_size: 100, total: 0 } })),
      ]);
      setDrafts(draftsRes.drafts);
      setAccounts(accountsRes.accounts);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : t("drafts.loadError"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [draftStatus, publishStatus, accountId]);

  const counts = useMemo(() => {
    return {
      pending: drafts.filter((draft) => draft.draft_status === "pending_review").length,
      approved: drafts.filter((draft) => draft.draft_status === "approved").length,
      failed: drafts.filter((draft) => draft.publish_status === "failed").length,
    };
  }, [drafts]);

  const accountMap = useMemo(() => new Map(accounts.map((account) => [account.account_id, account.name])), [accounts]);

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={t("drafts.eyebrow")}
        title={t("drafts.title")}
        description={t("drafts.description")}
      />

      <div className="grid gap-5 md:grid-cols-3">
        <StatCard label={t("drafts.loaded")} value={formatNumber(drafts.length)} hint={t("drafts.loadedHint")} tone="brand" />
        <StatCard label={t("drafts.needsReview")} value={formatNumber(counts.pending)} hint={t("drafts.needsReviewHint")} tone="warning" />
        <StatCard label={t("drafts.publishFailures")} value={formatNumber(counts.failed)} hint={t("drafts.publishFailuresHint")} tone="danger" />
      </div>

      <Card title={t("drafts.filters")} description={t("drafts.filtersDesc")}>
        <div className="grid gap-4 md:grid-cols-3">
          <Select value={accountId} onChange={(event) => setAccountId(event.target.value)}>
            <option value="all">{t("drafts.allAccounts")}</option>
            {accounts.map((account) => (
              <option key={account.account_id} value={account.account_id}>
                {account.name}
              </option>
            ))}
          </Select>
          <Select value={draftStatus} onChange={(event) => setDraftStatus(event.target.value)}>
            <option value="all">{t("drafts.allDraftStatuses")}</option>
            <option value="draft">{draftStatusLabel("draft")}</option>
            <option value="pending_review">{draftStatusLabel("pending_review")}</option>
            <option value="approved">{draftStatusLabel("approved")}</option>
            <option value="rejected">{draftStatusLabel("rejected")}</option>
            <option value="discarded">{draftStatusLabel("discarded")}</option>
            <option value="published">{draftStatusLabel("published")}</option>
          </Select>
          <Select value={publishStatus} onChange={(event) => setPublishStatus(event.target.value)}>
            <option value="all">{t("drafts.allPublishStatuses")}</option>
            <option value="not_published">{publishStatusLabel("not_published")}</option>
            <option value="pending">{publishStatusLabel("pending")}</option>
            <option value="publishing">{publishStatusLabel("publishing")}</option>
            <option value="published">{publishStatusLabel("published")}</option>
            <option value="failed">{publishStatusLabel("failed")}</option>
          </Select>
        </div>
      </Card>

      {loading ? (
        <SkeletonRows rows={6} />
      ) : error ? (
        <ErrorState title={t("drafts.loadError")} description={error} retry={() => void load()} />
      ) : drafts.length ? (
        <Table
          columns={[
            locale === "zh-CN" ? "标题" : "Title",
            locale === "zh-CN" ? "账号" : "Account",
            locale === "zh-CN" ? "草稿状态" : "Draft Status",
            locale === "zh-CN" ? "发布状态" : "Publish Status",
            locale === "zh-CN" ? "更新时间" : "Updated",
            locale === "zh-CN" ? "操作" : "Action",
          ]}
        >
          {drafts.map((draft) => (
            <tr key={draft.id}>
              <td className="px-5 py-4">
                <div>
                  <p className="text-sm font-semibold text-slate-900">{draft.title}</p>
                  <p className="mt-1 text-sm text-slate-500">
                    {truncate(draft.selected_topic, 80) || (locale === "zh-CN" ? "没有选题快照" : "No selected topic snapshot")}
                  </p>
                </div>
              </td>
              <td className="px-5 py-4 text-sm text-slate-600">{draft.account_id ? accountMap.get(draft.account_id) ?? draft.account_id : (locale === "zh-CN" ? "未分配" : "Unassigned")}</td>
              <td className="px-5 py-4">
                <Badge tone={draftTone(draft.draft_status)}>{draftStatusLabel(draft.draft_status)}</Badge>
              </td>
              <td className="px-5 py-4">
                <Badge tone={draftTone(draft.publish_status)}>{publishStatusLabel(draft.publish_status)}</Badge>
              </td>
              <td className="px-5 py-4 text-sm text-slate-600">{formatDateTime(draft.updated_at)}</td>
              <td className="px-5 py-4">
                <Link href={`/drafts/${draft.id}`}>
                  <Button variant="secondary" size="sm">
                    {t("drafts.open")}
                  </Button>
                </Link>
              </td>
            </tr>
          ))}
        </Table>
      ) : (
        <EmptyState
          title={t("drafts.emptyTitle")}
          description={t("drafts.emptyDesc")}
          action={
            <Link href="/workspace">
              <Button>{t("drafts.openWorkspace")}</Button>
            </Link>
          }
        />
      )}
    </div>
  );
}
