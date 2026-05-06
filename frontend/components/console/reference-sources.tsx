"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  createReferenceSource,
  getAccount,
  listReferenceSources,
  syncReferenceSource,
  updateReferenceSource,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { formatDateTime, formatNumber, truncate } from "@/lib/utils";
import type {
  AccountDetail,
  CreateReferenceSourceRequest,
  ReferenceSource,
  ReferenceSourceType,
} from "@/types";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Input,
  PageHeader,
  Select,
  SkeletonRows,
  StatCard,
  Textarea,
} from "@/components/console/ui";
import { Icon } from "@/components/console/icons";
import { useAppStore } from "@/store/appStore";

function syncTone(status: string): "success" | "warning" | "danger" | "muted" {
  if (status === "synced" || status === "manual_only") return "success";
  if (status === "failed") return "danger";
  if (status === "pending") return "warning";
  return "muted";
}

function sourceTypeLabel(sourceType: ReferenceSourceType, locale: "en" | "zh-CN"): string {
  if (sourceType === "wechat_account") return locale === "zh-CN" ? "公众号 / 站点" : "WeChat Account";
  if (sourceType === "article_url") return locale === "zh-CN" ? "文章 URL" : "Article URL";
  return locale === "zh-CN" ? "粘贴文章" : "Pasted Article";
}

interface ReferenceSourcesState {
  account: AccountDetail;
  sources: ReferenceSource[];
}

const initialDraft: CreateReferenceSourceRequest = {
  source_type: "wechat_account",
  name: "",
  source_value: "",
  notes: "",
  is_enabled: true,
};

export function ReferenceSourcesPage({ accountId }: { accountId: string }) {
  const { locale, token } = useI18n();
  const pushToast = useAppStore((state) => state.pushToast);
  const [data, setData] = useState<ReferenceSourcesState | null>(null);
  const [draft, setDraft] = useState<CreateReferenceSourceRequest>(initialDraft);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [actingId, setActingId] = useState<number | null>(null);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      const [account, list] = await Promise.all([getAccount(accountId), listReferenceSources(accountId)]);
      setData({
        account,
        sources: list.sources,
      });
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : locale === "zh-CN" ? "无法加载参考源。" : "Unable to load reference sources.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [accountId]);

  const metrics = useMemo(() => {
    const sources = data?.sources ?? [];
    const enabled = sources.filter((source) => source.is_enabled).length;
    const synced = sources.filter((source) => source.sync_status === "synced" || source.sync_status === "manual_only").length;
    const failed = sources.filter((source) => source.sync_status === "failed").length;
    return { total: sources.length, enabled, synced, failed };
  }, [data]);

  const handleCreate = async () => {
    if (!draft.source_value?.trim()) {
      pushToast({
        tone: "warning",
        title: locale === "zh-CN" ? "请先补全参考源内容" : "Complete the source first",
        message:
          draft.source_type === "wechat_account"
            ? locale === "zh-CN"
              ? "请填写公众号标识或站点名称。"
              : "Add a WeChat/publication identifier first."
            : draft.source_type === "article_url"
              ? locale === "zh-CN"
                ? "请填写文章 URL。"
                : "Add an article URL first."
              : locale === "zh-CN"
                ? "请粘贴文章正文。"
                : "Paste the article body first.",
      });
      return;
    }

    try {
      setSubmitting(true);
      const source = await createReferenceSource(accountId, {
        ...draft,
        name: draft.name?.trim() || undefined,
        notes: draft.notes?.trim() || undefined,
        source_value: draft.source_value.trim(),
      });
      pushToast({
        tone: "success",
        title: locale === "zh-CN" ? "参考源已创建" : "Reference source created",
        message: locale === "zh-CN" ? `${source.name} 已加入当前账号。` : `${source.name} was added to this account.`,
      });
      setDraft(initialDraft);
      await load();
    } catch (createError) {
      pushToast({
        tone: "danger",
        title: locale === "zh-CN" ? "创建失败" : "Create failed",
        message: createError instanceof Error ? createError.message : locale === "zh-CN" ? "发生了意外错误。" : "Unexpected error.",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const toggleSource = async (source: ReferenceSource) => {
    try {
      setActingId(source.id);
      const updated = await updateReferenceSource(accountId, source.id, {
        is_enabled: !source.is_enabled,
      });
      pushToast({
        tone: updated.is_enabled ? "success" : "warning",
        title: updated.is_enabled
          ? locale === "zh-CN"
            ? "参考源已启用"
            : "Reference source enabled"
          : locale === "zh-CN"
            ? "参考源已停用"
            : "Reference source disabled",
        message: updated.name,
      });
      await load();
    } catch (toggleError) {
      pushToast({
        tone: "danger",
        title: locale === "zh-CN" ? "状态更新失败" : "Status update failed",
        message: toggleError instanceof Error ? toggleError.message : locale === "zh-CN" ? "发生了意外错误。" : "Unexpected error.",
      });
    } finally {
      setActingId(null);
    }
  };

  const syncSourceNow = async (source: ReferenceSource) => {
    try {
      setActingId(source.id);
      const result = await syncReferenceSource(accountId, source.id);
      pushToast({
        tone: result.source.sync_status === "failed" ? "warning" : "success",
        title: locale === "zh-CN" ? "同步已完成" : "Sync finished",
        message: result.message,
      });
      await load();
    } catch (syncError) {
      pushToast({
        tone: "danger",
        title: locale === "zh-CN" ? "同步失败" : "Sync failed",
        message: syncError instanceof Error ? syncError.message : locale === "zh-CN" ? "发生了意外错误。" : "Unexpected error.",
      });
    } finally {
      setActingId(null);
    }
  };

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={locale === "zh-CN" ? "参考源系统" : "Reference Source System"}
        title={
          data?.account.name
            ? locale === "zh-CN"
              ? `${data.account.name} 参考源`
              : `${data.account.name} Reference Sources`
            : locale === "zh-CN"
              ? "参考源"
              : "Reference Sources"
        }
        description={
          locale === "zh-CN"
            ? "把当前账号参考的公众号、文章 URL 和粘贴文章，管理成真实可追踪的账号资产。"
            : "Manage the publications, URLs and pasted articles this account uses as trackable operating assets."
        }
        actions={
          <>
            <Link href={`/accounts/${accountId}`}>
              <Button variant="secondary">{locale === "zh-CN" ? "回到账号" : "Back to Account"}</Button>
            </Link>
            <Link href={`/accounts/${accountId}/workspace`}>
              <Button variant="secondary">{locale === "zh-CN" ? "回到工作台" : "Back to Workspace"}</Button>
            </Link>
          </>
        }
      />

      {loading ? (
        <SkeletonRows rows={6} />
      ) : error ? (
        <ErrorState title={locale === "zh-CN" ? "参考源加载失败" : "Reference sources failed to load"} description={error} retry={() => void load()} />
      ) : data ? (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">{locale === "zh-CN" ? "当前账号" : "Current Account"}</Badge>
            <Badge tone="muted">{data.account.name}</Badge>
            <Badge tone="muted">{accountId}</Badge>
          </div>

          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label={locale === "zh-CN" ? "参考源总数" : "Total Sources"}
              value={formatNumber(metrics.total)}
              hint={locale === "zh-CN" ? "当前账号的全部参考对象" : "All reference objects under this account"}
              tone="brand"
              icon={<Icon name="settings" className="h-6 w-6" />}
            />
            <StatCard
              label={locale === "zh-CN" ? "已启用" : "Enabled"}
              value={formatNumber(metrics.enabled)}
              hint={locale === "zh-CN" ? "当前仍参与运营参考的来源" : "Sources still active for operator use"}
              tone="success"
              icon={<Icon name="check" className="h-6 w-6" />}
            />
            <StatCard
              label={locale === "zh-CN" ? "可用状态" : "Usable Status"}
              value={formatNumber(metrics.synced)}
              hint={locale === "zh-CN" ? "已同步或手动型参考源" : "Synced or manual-only sources"}
              tone="info"
              icon={<Icon name="refresh" className="h-6 w-6" />}
            />
            <StatCard
              label={locale === "zh-CN" ? "同步失败" : "Failed Syncs"}
              value={formatNumber(metrics.failed)}
              hint={locale === "zh-CN" ? "允许失败，但必须可见" : "Failures stay visible until manually handled"}
              tone="warning"
              icon={<Icon name="warning" className="h-6 w-6" />}
            />
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
            <Card
              title={locale === "zh-CN" ? "参考源列表" : "Reference Source List"}
              description={
                locale === "zh-CN"
                  ? "每条记录都属于当前账号，并带有启停状态、同步状态和最新错误。"
                  : "Every row belongs to this account and keeps its own enablement, sync status and latest error."
              }
            >
              {data.sources.length ? (
                <div className="space-y-4">
                  {data.sources.map((source) => (
                    <div key={source.id} className="rounded-2xl border border-slate-200 p-4">
                      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-sm font-semibold text-slate-900">{source.name}</p>
                            <Badge tone="info">{sourceTypeLabel(source.source_type, locale)}</Badge>
                            <Badge tone={syncTone(source.sync_status)}>{token(source.sync_status)}</Badge>
                            <Badge tone={source.is_enabled ? "success" : "muted"}>
                              {source.is_enabled ? (locale === "zh-CN" ? "已启用" : "Enabled") : locale === "zh-CN" ? "已停用" : "Disabled"}
                            </Badge>
                          </div>
                          <p className="mt-3 text-sm leading-6 text-slate-600">
                            {source.source_type === "pasted_article" ? truncate(source.source_value, 220) : source.source_value}
                          </p>
                          {source.notes ? <p className="mt-2 text-sm text-slate-500">{source.notes}</p> : null}
                          <div className="mt-3 flex flex-wrap gap-3 text-xs uppercase tracking-[0.14em] text-slate-400">
                            <span>{locale === "zh-CN" ? `文章 ${source.article_count}` : `Articles ${source.article_count}`}</span>
                            <span>{locale === "zh-CN" ? `更新于 ${formatDateTime(source.updated_at)}` : `Updated ${formatDateTime(source.updated_at)}`}</span>
                            <span>{locale === "zh-CN" ? `上次同步 ${formatDateTime(source.last_synced_at)}` : `Last sync ${formatDateTime(source.last_synced_at)}`}</span>
                          </div>
                          {source.latest_error_message ? (
                            <div className="mt-3 rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                              {source.latest_error_message}
                            </div>
                          ) : null}
                        </div>
                        <div className="flex flex-wrap gap-3">
                          <Button
                            variant="secondary"
                            size="sm"
                            disabled={actingId === source.id}
                            onClick={() => void toggleSource(source)}
                          >
                            {source.is_enabled ? (locale === "zh-CN" ? "停用" : "Disable") : locale === "zh-CN" ? "启用" : "Enable"}
                          </Button>
                          <Button
                            size="sm"
                            disabled={actingId === source.id}
                            onClick={() => void syncSourceNow(source)}
                          >
                            <Icon name="refresh" className="h-4 w-4" />
                            {actingId === source.id ? (locale === "zh-CN" ? "同步中..." : "Syncing...") : locale === "zh-CN" ? "手动同步" : "Sync"}
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState
                  title={locale === "zh-CN" ? "还没有参考源" : "No reference sources yet"}
                  description={
                    locale === "zh-CN"
                      ? "当前账号还没有参考源。你可以先录入公众号、文章 URL 或粘贴文章，让“参考谁”变成真实资产。"
                      : "This account has no reference sources yet. Add a publication, URL, or pasted article to start tracking what the account references."
                  }
                />
              )}
            </Card>

            <Card
              title={locale === "zh-CN" ? "新增参考源" : "Add a Reference Source"}
              description={
                locale === "zh-CN"
                  ? "先支持公众号、文章 URL 和粘贴文章三类来源。同步能力先做最小可用。"
                  : "Start with WeChat/publication identifiers, article URLs and pasted articles. Sync behavior is intentionally lightweight in this phase."
              }
            >
              <div className="space-y-5">
                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-700">{locale === "zh-CN" ? "来源类型" : "Source Type"}</label>
                  <Select
                    value={draft.source_type}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        source_type: event.target.value as ReferenceSourceType,
                        source_value: "",
                      }))
                    }
                  >
                    <option value="wechat_account">{locale === "zh-CN" ? "公众号 / 站点" : "WeChat Account / Publication"}</option>
                    <option value="article_url">{locale === "zh-CN" ? "文章 URL" : "Article URL"}</option>
                    <option value="pasted_article">{locale === "zh-CN" ? "粘贴文章" : "Pasted Article"}</option>
                  </Select>
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-700">{locale === "zh-CN" ? "展示名称（可选）" : "Display Name (Optional)"}</label>
                  <Input
                    value={draft.name ?? ""}
                    onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))}
                    placeholder={locale === "zh-CN" ? "如果不填，系统会自动生成" : "Leave empty to let the system derive a name"}
                  />
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-700">
                    {draft.source_type === "wechat_account"
                      ? locale === "zh-CN"
                        ? "公众号标识 / 站点名称"
                        : "Publication Handle / Site Name"
                      : draft.source_type === "article_url"
                        ? locale === "zh-CN"
                          ? "文章 URL"
                          : "Article URL"
                        : locale === "zh-CN"
                          ? "文章正文"
                          : "Article Body"}
                  </label>
                  {draft.source_type === "pasted_article" ? (
                    <Textarea
                      value={draft.source_value}
                      onChange={(event) => setDraft((current) => ({ ...current, source_value: event.target.value }))}
                      className="min-h-48"
                      placeholder={
                        locale === "zh-CN"
                          ? "粘贴一篇代表文章正文。系统会把它保存成 manual-only 参考源。"
                          : "Paste a representative article body. It will be stored as a manual-only reference source."
                      }
                    />
                  ) : (
                    <Input
                      value={draft.source_value}
                      onChange={(event) => setDraft((current) => ({ ...current, source_value: event.target.value }))}
                      placeholder={
                        draft.source_type === "article_url"
                          ? "https://example.com/article"
                          : locale === "zh-CN"
                            ? "例如：增长黑客研究所"
                            : "For example: legacy-growth-lab"
                      }
                    />
                  )}
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-700">{locale === "zh-CN" ? "备注（可选）" : "Notes (Optional)"}</label>
                  <Textarea
                    value={draft.notes ?? ""}
                    onChange={(event) => setDraft((current) => ({ ...current, notes: event.target.value }))}
                    placeholder={
                      locale === "zh-CN"
                        ? "说明这个来源为什么值得参考，或它来自哪次 onboarding。"
                        : "Explain why this source matters or where it came from."
                    }
                  />
                </div>

                <Button onClick={() => void handleCreate()} disabled={submitting} className="w-full">
                  <Icon name="plus" className="h-4 w-4" />
                  {submitting ? (locale === "zh-CN" ? "创建中..." : "Creating...") : locale === "zh-CN" ? "创建参考源" : "Create Reference Source"}
                </Button>
              </div>
            </Card>
          </div>
        </>
      ) : null}
    </div>
  );
}
