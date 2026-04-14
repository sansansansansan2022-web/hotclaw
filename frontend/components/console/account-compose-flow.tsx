"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  buildComposePreview,
  confirmSelectionOutline,
  confirmSelectionSources,
  createSelectionSession,
  getAccount,
  getRecommendations,
  getSelectionSession,
  listReferenceSources,
  refreshRecommendations,
  runAccount,
  selectRecommendations,
  selectReferenceSourcesForSession,
  submitSelectionSession,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { formatDateTime, truncate } from "@/lib/utils";
import type {
  AccountDetail,
  ComposePreviewResponse,
  ComposeSelectionSessionBundle,
  RecommendedContentItem,
  RecommendationBucketedResponse,
  ReferenceSource,
} from "@/types";
import { Badge, Button, Card, EmptyState, ErrorState, Input, PageHeader, SkeletonRows, Textarea } from "@/components/console/ui";
import { Icon } from "@/components/console/icons";
import { useAppStore } from "@/store/appStore";

const MIN_COUNT_OPTIONS = [5, 8, 10] as const;

function syncTone(status: string): "success" | "warning" | "danger" | "muted" {
  if (status === "synced" || status === "manual_only") return "success";
  if (status === "failed") return "danger";
  if (status === "pending") return "warning";
  return "muted";
}

function recommendationTone(item: RecommendedContentItem): "brand" | "success" | "warning" | "danger" | "muted" {
  if ((item.scores.overall ?? 0) >= 0.75) return "success";
  if ((item.scores.overall ?? 0) >= 0.6) return "brand";
  if ((item.scores.overall ?? 0) >= 0.45) return "warning";
  return "muted";
}

function diagnosticTone(status: string): "success" | "warning" | "danger" | "muted" {
  if (status === "success") return "success";
  if (status === "failed" || status === "disabled") return "danger";
  if (status === "empty" || status === "not_applicable") return "warning";
  return "muted";
}

function diagnosticStatusLabel(status: string, locale: "en" | "zh-CN") {
  if (locale === "zh-CN") {
    if (status === "success") return "成功";
    if (status === "failed") return "失败";
    if (status === "disabled") return "已关闭";
    if (status === "empty") return "无结果";
    if (status === "not_applicable") return "不适用";
    if (status === "cached_only") return "缓存";
    return status;
  }
  if (status === "success") return "Success";
  if (status === "failed") return "Failed";
  if (status === "disabled") return "Disabled";
  if (status === "empty") return "Empty";
  if (status === "not_applicable") return "Not Applicable";
  if (status === "cached_only") return "Cached";
  return status;
}

function referenceSourceTypeLabel(type: string, locale: "en" | "zh-CN") {
  if (type === "wechat_account") return locale === "zh-CN" ? "公众号 / 站点" : "Publication";
  if (type === "article_url") return locale === "zh-CN" ? "文章 URL" : "Article URL";
  return locale === "zh-CN" ? "粘贴文章" : "Pasted Article";
}

function sourcePreview(source: ReferenceSource) {
  const metadata = source.metadata_json && typeof source.metadata_json === "object" ? source.metadata_json : null;
  const preview = metadata && typeof metadata.preview === "string" ? metadata.preview : null;
  return preview || source.notes || truncate(source.source_value, 200);
}

function scoreLabel(value: number | null) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "--";
  }
  return value.toFixed(2);
}

export function AccountComposeFlowPage({ accountId }: { accountId: string }) {
  const { locale } = useI18n();
  const router = useRouter();
  const searchParams = useSearchParams();
  const pushToast = useAppStore((state) => state.pushToast);
  const sessionId = searchParams.get("session");
  const [account, setAccount] = useState<AccountDetail | null>(null);
  const [sessionBundle, setSessionBundle] = useState<ComposeSelectionSessionBundle | null>(null);
  const [referenceSources, setReferenceSources] = useState<ReferenceSource[]>([]);
  const [recommendations, setRecommendations] = useState<RecommendationBucketedResponse | null>(null);
  const [preview, setPreview] = useState<ComposePreviewResponse | null>(null);
  const [minCount, setMinCount] = useState<(typeof MIN_COUNT_OPTIONS)[number]>(5);
  const [loading, setLoading] = useState(true);
  const [recommendationLoading, setRecommendationLoading] = useState(false);
  const [recommendationError, setRecommendationError] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [legacyRunning, setLegacyRunning] = useState(false);
  const [selectionBusyKey, setSelectionBusyKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creationNote, setCreationNote] = useState("");
  const [preferredLane, setPreferredLane] = useState("");
  const [titleDirection, setTitleDirection] = useState("");
  const hydratedSessionIdRef = useRef<string | null>(null);

  const copy = locale === "zh-CN"
    ? {
        eyebrow: "新建任务",
        title: "新建任务",
        description: "先把推荐资讯和参考文章加入本次任务，再生成预览并提交正式生成。",
        backAccount: "返回账号",
        backWorkspace: "返回工作台",
        refreshRecommendations: "刷新推荐",
        bootstrapError: "无法初始化任务草稿。",
        loadError: "无法加载新建任务页面。",
        recommendationError: "无法刷新推荐资讯。",
        previewError: "生成预览失败。",
        submitError: "提交生成失败。",
        sessionSummary: "当前任务草稿",
        accountSummary: "账号摘要",
        recommendationZone: "推荐资讯",
        recommendationDesc: "根据账号定位、受众和内容方向返回高相关候选；不足时会单独给出扩展推荐。",
        highRelevance: "高相关推荐",
        extended: "扩展推荐",
        noRecommendations: "还没有推荐资讯",
        noRecommendationsDesc: "先刷新推荐，或者稍后再回来查看可用来源。",
        selectedSources: "已加入本次创作的推荐资讯",
        selectedSourcesDesc: "这些推荐资讯会进入预览和正式生成。",
        noSelectedSources: "还没有加入推荐资讯",
        noSelectedSourcesDesc: "从上面的高相关推荐或扩展推荐中挑选值得写的一组来源。",
        referenceZone: "参考文章",
        referenceDesc: "像选购一样把参考文章加入本次任务篮子，后端会把完整已选列表写回当前任务草稿。",
        availableReferences: "可加入的参考文章",
        selectedReferences: "已加入本次任务的参考文章",
        noReferences: "还没有参考文章",
        noReferencesDesc: "先去账号的参考源页面补几篇文章或 URL，再回来加入本次创作。",
        noSelectedReferences: "还没有加入参考文章",
        noSelectedReferencesDesc: "如果你希望预览更稳，可以额外加入几篇长期参考文章。",
        addToCreation: "加入本次创作",
        removeFromBasket: "移出篮子",
        inputZone: "创作意图",
        creationNote: "创作备注",
        preferredLane: "内容方向",
        titleDirection: "标题方向",
        creationNotePlaceholder: "例如：强调适用边界、判断感和读者能直接带走的结论。",
        preferredLanePlaceholder: "例如：AI 工具拆解 / 研究趋势 / 开源盘点",
        titleDirectionPlaceholder: "例如：判断型 / 拆解型 / 方法解释型",
        previewZone: "任务预览",
        previewDesc: "预览只做决策显式化，不直接写正文。",
        previewButton: "生成预览",
        previewing: "生成预览中...",
        submitButton: "提交生成",
        submitting: "提交中...",
        previewEmpty: "还没有生成预览",
        previewEmptyDesc: "先选择推荐资讯和参考文章，再生成预览查看 query plan、标题方向和大纲。",
        shortage: "结果不足提示",
        selectedCount: "已选",
        requestedCount: "目标数量",
        generatedAt: "刷新时间",
        topicDirections: "选题方向",
        titleDirections: "标题方向",
        outlinePreview: "大纲预览",
        queryPlan: "查询计划",
        gotoTask: (taskId: string) => `任务 ${taskId} 已创建，正在跳转。`,
      }
    : {
        eyebrow: "New Task",
        title: "New Task",
        description: "Pick recommendation candidates and reference articles first, then preview the angle before submitting generation.",
        backAccount: "Back to Account",
        backWorkspace: "Back to Workspace",
        refreshRecommendations: "Refresh Recommendations",
        bootstrapError: "Unable to initialize the task draft.",
        loadError: "Unable to load the new task flow.",
        recommendationError: "Unable to refresh recommendations.",
        previewError: "Failed to build the compose preview.",
        submitError: "Failed to submit generation.",
        sessionSummary: "Current Task Draft",
        accountSummary: "Account Summary",
        recommendationZone: "Recommended News",
        recommendationDesc: "Recommendations are ranked to the account's positioning, audience, and content lane, then split into high relevance and extended buckets.",
        highRelevance: "High Relevance",
        extended: "Extended Picks",
        noRecommendations: "No recommendations yet",
        noRecommendationsDesc: "Refresh recommendations now, or come back later when more sources are available.",
        selectedSources: "Recommendation Basket",
        selectedSourcesDesc: "These recommendation items will feed the preview and the formal generation input.",
        noSelectedSources: "No selected recommendations yet",
        noSelectedSourcesDesc: "Pick from the high-relevance or extended buckets to build the creation basket.",
        referenceZone: "Reference Articles",
        referenceDesc: "Add reference articles like a shopping basket. The full selected set is synced back into this task draft.",
        availableReferences: "Available Reference Articles",
        selectedReferences: "Task Reference Basket",
        noReferences: "No reference articles yet",
        noReferencesDesc: "Add a few URLs or pasted articles on the account reference source page, then come back here.",
        noSelectedReferences: "No reference articles in the basket",
        noSelectedReferencesDesc: "Add a few longer-lived references if you want a stronger preview and draft grounding.",
        addToCreation: "Add to Creation",
        removeFromBasket: "Remove",
        inputZone: "Creation Intent",
        creationNote: "Creation Note",
        preferredLane: "Preferred Lane",
        titleDirection: "Title Direction",
        creationNotePlaceholder: "For example: emphasize practical boundary, operator judgment, and what the reader can take away.",
        preferredLanePlaceholder: "For example: AI tools / research trend / open-source roundup",
        titleDirectionPlaceholder: "For example: judgment-led / teardown / method explainer",
        previewZone: "Task Preview",
        previewDesc: "The preview only makes the plan explicit. It does not write the article body yet.",
        previewButton: "Generate Preview",
        previewing: "Generating Preview...",
        submitButton: "Submit Generation",
        submitting: "Submitting...",
        previewEmpty: "No preview yet",
        previewEmptyDesc: "Select recommendation items and reference articles first, then build a preview to inspect the query plan, title directions, and outline.",
        shortage: "Coverage Notice",
        selectedCount: "Selected",
        requestedCount: "Requested",
        generatedAt: "Updated",
        topicDirections: "Topic Directions",
        titleDirections: "Title Directions",
        outlinePreview: "Outline Preview",
        queryPlan: "Query Plan",
        gotoTask: (taskId: string) => `Task ${taskId} created. Redirecting now.`,
      };

  const sourceConfirmLabel = locale === "zh-CN" ? "确认来源" : "Confirm Sources";
  const sourceConfirmedLabel = locale === "zh-CN" ? "来源已确认" : "Sources Confirmed";
  const sourcePendingLabel = locale === "zh-CN" ? "待确认来源" : "Awaiting Source Confirmation";
  const outlineConfirmLabel = locale === "zh-CN" ? "确认大纲" : "Confirm Outline";
  const outlineConfirmedLabel = locale === "zh-CN" ? "大纲已确认" : "Outline Confirmed";
  const outlinePendingLabel = locale === "zh-CN" ? "待确认大纲" : "Awaiting Outline Confirmation";
  const previewVersionLabel = locale === "zh-CN" ? "预览版本" : "Preview Version";
  const previewConfirmHint =
    locale === "zh-CN"
      ? "先确认来源，再生成预览；预览完成后还需要确认大纲才能正式提交。"
      : "Confirm sources first, then generate a preview. The outline must be confirmed before submission.";

  const selectedRecommendationIds = sessionBundle?.selection_session.selected_recommendation_ids ?? [];
  const selectedReferenceSourceIds = useMemo(
    () => (sessionBundle?.selection_session.selected_reference_source_ids ?? []).map((item) => Number(item)),
    [sessionBundle],
  );
  const selectedReferenceIdSet = useMemo(() => new Set(selectedReferenceSourceIds), [selectedReferenceSourceIds]);
  const canPreview = selectedRecommendationIds.length > 0 || selectedReferenceSourceIds.length > 0;
  const sourceConfirmed = Boolean(sessionBundle?.selection_session.source_confirmed);
  const outlineConfirmed = Boolean(sessionBundle?.selection_session.outline_confirmed);
  const previewVersion = sessionBundle?.selection_session.preview_version ?? 0;

  const loadRecommendationsForCount = async (targetMinCount: (typeof MIN_COUNT_OPTIONS)[number]) => {
    setRecommendationLoading(true);
    try {
      let response = await getRecommendations(accountId, { min_count: targetMinCount });
      if (response.total === 0) {
        response = await refreshRecommendations(accountId, { min_count: targetMinCount });
      }
      setRecommendationError(null);
      setRecommendations(response);
    } catch (error) {
      try {
        const fallback = await getRecommendations(accountId, { min_count: targetMinCount });
        setRecommendationError(null);
        setRecommendations(fallback);
      } catch (fallbackError) {
        const message = fallbackError instanceof Error ? fallbackError.message : copy.recommendationError;
        setRecommendationError(message);
      }
    } finally {
      setRecommendationLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    const bootstrap = async () => {
      if (sessionId) {
        return;
      }
      try {
        setLoading(true);
        setError(null);
        const created = await createSelectionSession(accountId);
        if (!active) {
          return;
        }
        router.replace(`/accounts/${accountId}/create?session=${created.selection_session.id}`);
      } catch (bootstrapError) {
        if (!active) {
          return;
        }
        setError(bootstrapError instanceof Error ? bootstrapError.message : copy.bootstrapError);
        setLoading(false);
      }
    };
    void bootstrap();
    return () => {
      active = false;
    };
  }, [accountId, sessionId, router, copy.bootstrapError]);

  useEffect(() => {
    let active = true;
    const load = async () => {
      if (!sessionId) {
        return;
      }
      try {
        setLoading(true);
        setError(null);
        const [accountDetail, bundle, sourceList] = await Promise.all([
          getAccount(accountId),
          getSelectionSession(accountId, sessionId),
          listReferenceSources(accountId),
        ]);
        if (!active) {
          return;
        }
        setAccount(accountDetail);
        setSessionBundle(bundle);
        setReferenceSources(sourceList.sources);
        if (hydratedSessionIdRef.current !== bundle.selection_session.id) {
          hydratedSessionIdRef.current = bundle.selection_session.id;
          setCreationNote(bundle.selection_session.creation_note ?? "");
          setPreferredLane(bundle.selection_session.preferred_lane ?? "");
          setTitleDirection(bundle.selection_session.title_direction ?? "");
          setPreview(null);
        }
      } catch (loadError) {
        if (!active) {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : copy.loadError);
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, [accountId, sessionId, copy.loadError]);

  useEffect(() => {
    if (!sessionId) {
      return;
    }
    void loadRecommendationsForCount(minCount);
  }, [accountId, sessionId, minCount]);

  const selectedRecommendationItems = useMemo(() => {
    if (!recommendations) {
      return [];
    }
    const byId = new Map<string, RecommendedContentItem>();
    for (const item of [...recommendations.high_relevance_items, ...recommendations.extended_items]) {
      byId.set(item.id, item);
    }
    return selectedRecommendationIds
      .map((id) => byId.get(id))
      .filter((item): item is RecommendedContentItem => Boolean(item));
  }, [recommendations, selectedRecommendationIds]);

  const selectedReferenceItems = useMemo(() => {
    const byId = new Map<number, ReferenceSource>();
    for (const row of referenceSources) {
      byId.set(row.id, row);
    }
    return selectedReferenceSourceIds
      .map((id) => byId.get(id))
      .filter((row): row is ReferenceSource => Boolean(row));
  }, [referenceSources, selectedReferenceSourceIds]);

  const invalidatePreview = () => {
    setPreview(null);
    setSessionBundle((current) =>
      current
        ? {
            ...current,
            selection_session: {
              ...current.selection_session,
              outline_confirmed: false,
              approved_outline_seed: null,
            },
          }
        : current,
    );
  };

  const toggleRecommendation = async (item: RecommendedContentItem) => {
    if (!sessionBundle) {
      return;
    }
    const alreadySelected = selectedRecommendationIds.includes(item.id);
    setSelectionBusyKey(`rec:${item.id}`);
    try {
      const response = await selectRecommendations(accountId, {
        recommendation_ids: [item.id],
        action: alreadySelected ? "remove_from_creation" : "use_for_creation",
        selection_session_id: sessionBundle.selection_session.id,
      });
      if (response.selection_session) {
        setSessionBundle({
          selection_session: response.selection_session,
          selected_recommendations: response.selected_recommendations,
          selected_reference_sources: response.selected_reference_sources,
        });
      }
      invalidatePreview();
    } catch (toggleError) {
      pushToast({
        tone: "danger",
        title: locale === "zh-CN" ? "推荐更新失败" : "Recommendation update failed",
        message: toggleError instanceof Error ? toggleError.message : copy.recommendationError,
      });
    } finally {
      setSelectionBusyKey(null);
    }
  };

  const toggleReferenceSource = async (row: ReferenceSource) => {
    if (!sessionBundle) {
      return;
    }
    const alreadySelected = selectedReferenceIdSet.has(row.id);
    const nextIds = alreadySelected
      ? selectedReferenceSourceIds.filter((id) => id !== row.id)
      : [...selectedReferenceSourceIds, row.id];
    setSelectionBusyKey(`ref:${row.id}`);
    try {
      const bundle = await selectReferenceSourcesForSession(accountId, sessionBundle.selection_session.id, {
        reference_source_ids: nextIds,
      });
      setSessionBundle(bundle);
      invalidatePreview();
    } catch (toggleError) {
      pushToast({
        tone: "danger",
        title: locale === "zh-CN" ? "参考文章更新失败" : "Reference basket update failed",
        message: toggleError instanceof Error ? toggleError.message : copy.loadError,
      });
    } finally {
      setSelectionBusyKey(null);
    }
  };

  const handleConfirmSources = async () => {
    if (!sessionBundle) {
      return;
    }
    try {
      setSelectionBusyKey("confirm-sources");
      const bundle = await confirmSelectionSources(accountId, sessionBundle.selection_session.id, {
        confirmed: true,
      });
      setSessionBundle(bundle);
      pushToast({
        tone: "success",
        title: sourceConfirmedLabel,
        message: previewConfirmHint,
      });
    } catch (confirmError) {
      pushToast({
        tone: "danger",
        title: sourceConfirmLabel,
        message: confirmError instanceof Error ? confirmError.message : copy.previewError,
      });
    } finally {
      setSelectionBusyKey(null);
    }
  };

  const buildPreview = async () => {
    if (!sessionBundle) {
      return;
    }
    try {
      setPreviewing(true);
      const response = await buildComposePreview(accountId, {
        selection_session_id: sessionBundle.selection_session.id,
        creation_note: creationNote || undefined,
        preferred_lane: preferredLane || undefined,
        title_direction: titleDirection || undefined,
      });
      setPreview(response);
      setSessionBundle((current) =>
        current
          ? {
              ...current,
              selection_session: response.selection_session,
            }
          : current,
      );
    } catch (previewError) {
      pushToast({
        tone: "danger",
        title: copy.previewError,
        message: previewError instanceof Error ? previewError.message : copy.previewError,
      });
    } finally {
      setPreviewing(false);
    }
  };

  const handleConfirmOutline = async () => {
    if (!sessionBundle || !preview) {
      return;
    }
    try {
      setSelectionBusyKey("confirm-outline");
      const confirmedSession = await confirmSelectionOutline(accountId, sessionBundle.selection_session.id, {
        preview_version: preview.selection_session.preview_version,
        approved_outline_seed: preview.outline_preview as unknown as Record<string, unknown>,
      });
      setSessionBundle((current) =>
        current
          ? {
              ...current,
              selection_session: confirmedSession,
            }
          : current,
      );
      pushToast({
        tone: "success",
        title: outlineConfirmedLabel,
        message: locale === "zh-CN" ? "可以正式提交生成了。" : "The creation session is ready to submit.",
      });
    } catch (confirmError) {
      pushToast({
        tone: "danger",
        title: outlineConfirmLabel,
        message: confirmError instanceof Error ? confirmError.message : copy.previewError,
      });
    } finally {
      setSelectionBusyKey(null);
    }
  };

  const submitGeneration = async () => {
    if (!sessionBundle) {
      return;
    }
    try {
      setSubmitting(true);
      const response = await submitSelectionSession(accountId, sessionBundle.selection_session.id, {
        creation_note: creationNote || undefined,
        preferred_lane: preferredLane || undefined,
        title_direction: titleDirection || undefined,
      });
      pushToast({
        tone: "success",
        title: locale === "zh-CN" ? "生成已提交" : "Generation submitted",
        message: copy.gotoTask(response.task_id),
      });
      router.push(`/task/${response.task_id}`);
    } catch (submitError) {
      pushToast({
        tone: "danger",
        title: copy.submitError,
        message: submitError instanceof Error ? submitError.message : copy.submitError,
      });
    } finally {
      setSubmitting(false);
    }
  };

  const triggerLegacyRun = async () => {
    try {
      setLegacyRunning(true);
      const response = await runAccount(accountId);
      pushToast({
        tone: "success",
        title: locale === "zh-CN" ? "兼容直跑已排队" : "Legacy run queued",
        message: copy.gotoTask(response.task_id),
      });
      router.push(`/task/${response.task_id}`);
    } catch (runError) {
      pushToast({
        tone: "danger",
        title: copy.submitError,
        message: runError instanceof Error ? runError.message : copy.submitError,
      });
    } finally {
      setLegacyRunning(false);
    }
  };
  const manualRefreshRecommendations = async () => {
    try {
      setRecommendationLoading(true);
      const response = await refreshRecommendations(accountId, { min_count: minCount });
      setRecommendationError(null);
      setRecommendations(response);
    } catch (refreshError) {
      pushToast({
        tone: "danger",
        title: copy.recommendationError,
        message: refreshError instanceof Error ? refreshError.message : copy.recommendationError,
      });
    } finally {
      setRecommendationLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={copy.eyebrow}
        title={account?.name ? `${account.name} / ${copy.title}` : copy.title}
        description={copy.description}
        actions={
          <>
            <Link href={`/accounts/${accountId}`}>
              <Button variant="secondary">{copy.backAccount}</Button>
            </Link>
            <Link href={`/accounts/${accountId}/workspace`}>
              <Button variant="secondary">{copy.backWorkspace}</Button>
            </Link>
            <Button variant="secondary" onClick={() => void manualRefreshRecommendations()} disabled={recommendationLoading}>
              <Icon name="refresh" className="h-4 w-4" />
              {copy.refreshRecommendations}
            </Button>
          </>
        }
      />

      {loading ? (
        <SkeletonRows rows={6} />
      ) : error ? (
        <ErrorState title={copy.loadError} description={error} retry={() => router.refresh()} />
      ) : account && sessionBundle ? (
        <>
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
            <Card title={copy.sessionSummary}>
              <div className="space-y-3 text-sm text-slate-600">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="brand">{sessionBundle.selection_session.status}</Badge>
                  <Badge tone="muted">{sessionBundle.selection_session.id}</Badge>
                  <Badge tone={sourceConfirmed ? "success" : "warning"}>
                    {sourceConfirmed ? sourceConfirmedLabel : sourcePendingLabel}
                  </Badge>
                  <Badge tone={outlineConfirmed ? "success" : "muted"}>
                    {outlineConfirmed ? outlineConfirmedLabel : outlinePendingLabel}
                  </Badge>
                </div>
                <p>{copy.selectedCount}: {selectedRecommendationIds.length + selectedReferenceSourceIds.length}</p>
                <p>{copy.requestedCount}: {minCount}</p>
                <p>{previewVersionLabel}: {previewVersion}</p>
                <p>{copy.generatedAt}: {formatDateTime(recommendations?.refreshed_at ?? sessionBundle.selection_session.updated_at)}</p>
              </div>
            </Card>
            <Card title={copy.accountSummary}>
              <div className="space-y-2 text-sm text-slate-600">
                <p className="font-medium text-slate-900">{account.name}</p>
                <p>{truncate(account.positioning, 140)}</p>
                <div className="flex flex-wrap gap-2">
                  <Badge tone="muted">{account.operation_mode}</Badge>
                  {account.audience ? <Badge tone="muted">{truncate(account.audience, 30)}</Badge> : null}
                </div>
              </div>
            </Card>
            <Card title={copy.selectedSources}>
              <p className="text-3xl font-semibold tracking-tight text-slate-950">{selectedRecommendationIds.length}</p>
              <p className="mt-2 text-sm text-slate-500">{copy.selectedSourcesDesc}</p>
            </Card>
            <Card title={copy.selectedReferences}>
              <p className="text-3xl font-semibold tracking-tight text-slate-950">{selectedReferenceSourceIds.length}</p>
              <p className="mt-2 text-sm text-slate-500">{copy.noSelectedReferencesDesc}</p>
            </Card>
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            <Card title={copy.recommendationZone} description={copy.recommendationDesc}>
              <div className="space-y-5">
                <div className="flex flex-wrap items-center gap-2">
                  {MIN_COUNT_OPTIONS.map((value) => (
                    <Button
                      key={value}
                      size="sm"
                      variant={minCount === value ? "primary" : "secondary"}
                      onClick={() => setMinCount(value)}
                      disabled={recommendationLoading}
                    >
                      {value}
                    </Button>
                  ))}
                </div>

                {recommendations && recommendations.shortage_notice.status !== "ok" ? (
                  <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                    <p className="font-medium">{copy.shortage}</p>
                    <p className="mt-1">{recommendations.shortage_notice.message}</p>
                    {recommendations.shortage_notice.recommended_action ? (
                      <p className="mt-1 text-amber-800">{recommendations.shortage_notice.recommended_action}</p>
                    ) : null}
                    {recommendations.shortage_notice.reason_code ? (
                      <p className="mt-2 text-xs uppercase tracking-wide text-amber-700">
                        {recommendations.shortage_notice.reason_code}
                      </p>
                    ) : null}
                    {recommendations.source_diagnostics.length ? (
                      <div className="mt-3 space-y-2 border-t border-amber-200 pt-3">
                        {recommendations.source_diagnostics.map((item) => (
                          <div key={`${item.source_key}-${item.query ?? "default"}`} className="rounded-xl border border-amber-200 bg-white/60 px-3 py-2">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="text-xs font-semibold text-slate-900">{item.label}</p>
                              <Badge tone={diagnosticTone(item.status)}>{diagnosticStatusLabel(item.status, locale)}</Badge>
                              {item.query ? <Badge tone="muted">{truncate(item.query, 48)}</Badge> : null}
                            </div>
                            <p className="mt-1 text-xs text-amber-900/90">
                              candidates {item.candidate_count} · high {item.high_relevance_count} · extended {item.extended_count} · filtered {item.filtered_out_count}
                            </p>
                            {item.detail ? <p className="mt-1 text-xs text-amber-800">{item.detail}</p> : null}
                            {item.error_message ? <p className="mt-1 text-xs text-rose-700">{item.error_message}</p> : null}
                          </div>
                        ))}
                        <p className="text-xs text-amber-800">
                          raw {recommendations.filter_diagnostics.raw_candidate_count} · filtered out {recommendations.filter_diagnostics.filtered_out_count} · low relevance {recommendations.filter_diagnostics.filtered_low_relevance_count} · low authority {recommendations.filter_diagnostics.filtered_low_authority_count}
                        </p>
                      </div>
                    ) : null}
                  </div>
                ) : null}

                {recommendationError ? (
                  <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                    {recommendationError}
                  </div>
                ) : null}

                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-slate-900">{copy.highRelevance}</h3>
                    <Badge tone="success">{recommendations?.coverage.high_relevance_count ?? 0}</Badge>
                  </div>
                  {recommendations?.high_relevance_items.length ? (
                    <div className="space-y-3">
                      {recommendations.high_relevance_items.map((item) => {
                        const selected = selectedRecommendationIds.includes(item.id);
                        return (
                          <div key={item.id} className="rounded-2xl border border-slate-200 p-4">
                            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                              <div className="min-w-0">
                                <div className="flex flex-wrap items-center gap-2">
                                  <p className="text-sm font-semibold text-slate-900">{item.title}</p>
                                  <Badge tone={recommendationTone(item)}>{scoreLabel(item.scores.overall)}</Badge>
                                  <Badge tone="muted">{item.source.source_name || item.source.source_type}</Badge>
                                </div>
                                {item.summary ? <p className="mt-2 text-sm leading-6 text-slate-600">{item.summary}</p> : null}
                                <p className="mt-2 text-sm text-slate-500">{item.rationale.reason}</p>
                              </div>
                              <Button
                                size="sm"
                                variant={selected ? "secondary" : "primary"}
                                disabled={selectionBusyKey === `rec:${item.id}`}
                                onClick={() => void toggleRecommendation(item)}
                              >
                                {selected ? copy.removeFromBasket : copy.addToCreation}
                              </Button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <EmptyState title={copy.noRecommendations} description={copy.noRecommendationsDesc} />
                  )}
                </div>

                {recommendations?.extended_items.length ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-semibold text-slate-900">{copy.extended}</h3>
                      <Badge tone="warning">{recommendations.coverage.extended_count}</Badge>
                    </div>
                    <div className="space-y-3">
                      {recommendations.extended_items.map((item) => {
                        const selected = selectedRecommendationIds.includes(item.id);
                        return (
                          <div key={item.id} className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                              <div className="min-w-0">
                                <div className="flex flex-wrap items-center gap-2">
                                  <p className="text-sm font-semibold text-slate-900">{item.title}</p>
                                  <Badge tone="warning">{scoreLabel(item.scores.overall)}</Badge>
                                  <Badge tone="muted">{item.source.source_name || item.source.source_type}</Badge>
                                </div>
                                {item.summary ? <p className="mt-2 text-sm leading-6 text-slate-600">{item.summary}</p> : null}
                                <p className="mt-2 text-sm text-slate-500">{item.rationale.reason}</p>
                              </div>
                              <Button
                                size="sm"
                                variant="secondary"
                                disabled={selectionBusyKey === `rec:${item.id}`}
                                onClick={() => void toggleRecommendation(item)}
                              >
                                {selected ? copy.removeFromBasket : copy.addToCreation}
                              </Button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : null}
              </div>
            </Card>

            <Card title={copy.selectedSources} description={copy.selectedSourcesDesc}>
              {selectedRecommendationItems.length ? (
                <div className="space-y-3">
                  {selectedRecommendationItems.map((item) => (
                    <div key={item.id} className="rounded-2xl border border-slate-200 p-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-slate-900">{item.title}</p>
                          <p className="mt-1 text-sm text-slate-500">{truncate(item.summary || item.rationale.reason || "", 120)}</p>
                        </div>
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={selectionBusyKey === `rec:${item.id}`}
                          onClick={() => void toggleRecommendation(item)}
                        >
                          {copy.removeFromBasket}
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title={copy.noSelectedSources} description={copy.noSelectedSourcesDesc} />
              )}
            </Card>
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            <Card title={copy.referenceZone} description={copy.referenceDesc}>
              {referenceSources.length ? (
                <div className="space-y-4">
                  <h3 className="text-sm font-semibold text-slate-900">{copy.availableReferences}</h3>
                  {referenceSources.map((row) => {
                    const selected = selectedReferenceIdSet.has(row.id);
                    return (
                      <div key={row.id} className="rounded-2xl border border-slate-200 p-4">
                        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="text-sm font-semibold text-slate-900">{row.name}</p>
                              <Badge tone="muted">{referenceSourceTypeLabel(row.source_type, locale)}</Badge>
                              <Badge tone={syncTone(row.sync_status)}>{row.sync_status}</Badge>
                            </div>
                            <p className="mt-2 text-sm leading-6 text-slate-600">{sourcePreview(row)}</p>
                          </div>
                          <Button
                            size="sm"
                            variant={selected ? "secondary" : "primary"}
                            disabled={selectionBusyKey === `ref:${row.id}`}
                            onClick={() => void toggleReferenceSource(row)}
                          >
                            {selected ? copy.removeFromBasket : copy.addToCreation}
                          </Button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <EmptyState
                  title={copy.noReferences}
                  description={copy.noReferencesDesc}
                  action={
                    <Link href={`/accounts/${accountId}/reference-sources`}>
                      <Button>{locale === "zh-CN" ? "去补参考文章" : "Manage Reference Sources"}</Button>
                    </Link>
                  }
                />
              )}
            </Card>

            <Card title={copy.selectedReferences} description={copy.noSelectedReferencesDesc}>
              {selectedReferenceItems.length ? (
                <div className="space-y-3">
                  {selectedReferenceItems.map((row) => (
                    <div key={row.id} className="rounded-2xl border border-slate-200 p-4">
                      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-sm font-semibold text-slate-900">{row.name}</p>
                            <Badge tone={syncTone(row.sync_status)}>{row.sync_status}</Badge>
                          </div>
                          <p className="mt-2 text-sm leading-6 text-slate-600">{sourcePreview(row)}</p>
                        </div>
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={selectionBusyKey === `ref:${row.id}`}
                          onClick={() => void toggleReferenceSource(row)}
                        >
                          {copy.removeFromBasket}
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title={copy.noSelectedReferences} description={copy.noSelectedReferencesDesc} />
              )}
            </Card>
          </div>

          <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
            <Card title={copy.inputZone}>
              <div className="space-y-5">
                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-700">{copy.creationNote}</label>
                  <Textarea
                    value={creationNote}
                    onChange={(event) => {
                      setCreationNote(event.target.value);
                      invalidatePreview();
                    }}
                    placeholder={copy.creationNotePlaceholder}
                  />
                </div>
                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-700">{copy.preferredLane}</label>
                  <Input
                    value={preferredLane}
                    onChange={(event) => {
                      setPreferredLane(event.target.value);
                      invalidatePreview();
                    }}
                    placeholder={copy.preferredLanePlaceholder}
                  />
                </div>
                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-700">{copy.titleDirection}</label>
                  <Input
                    value={titleDirection}
                    onChange={(event) => {
                      setTitleDirection(event.target.value);
                      invalidatePreview();
                    }}
                    placeholder={copy.titleDirectionPlaceholder}
                  />
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={sourceConfirmed ? "success" : "warning"}>
                      {sourceConfirmed ? sourceConfirmedLabel : sourcePendingLabel}
                    </Badge>
                    <Badge tone={outlineConfirmed ? "success" : "muted"}>
                      {outlineConfirmed ? outlineConfirmedLabel : outlinePendingLabel}
                    </Badge>
                    <Badge tone="muted">{`${previewVersionLabel}: ${previewVersion}`}</Badge>
                  </div>
                  <p className="mt-3">{previewConfirmHint}</p>
                </div>
                <div className="flex flex-wrap gap-3">
                  <Button
                    variant={sourceConfirmed ? "secondary" : "primary"}
                    onClick={() => void handleConfirmSources()}
                    disabled={!canPreview || sourceConfirmed || selectionBusyKey === "confirm-sources"}
                  >
                    <Icon name="check" className="h-4 w-4" />
                    {sourceConfirmLabel}
                  </Button>
                  <Button
                    onClick={() => void buildPreview()}
                    disabled={!canPreview || !sourceConfirmed || previewing}
                  >
                    <Icon name="refresh" className="h-4 w-4" />
                    {previewing ? copy.previewing : copy.previewButton}
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => void handleConfirmOutline()}
                    disabled={!preview || outlineConfirmed || selectionBusyKey === "confirm-outline"}
                  >
                    <Icon name="check" className="h-4 w-4" />
                    {outlineConfirmLabel}
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => void submitGeneration()}
                    disabled={!preview || !outlineConfirmed || submitting}
                  >
                    <Icon name="play" className="h-4 w-4" />
                    {submitting ? copy.submitting : copy.submitButton}
                  </Button>
                </div>
              </div>
            </Card>

            <Card title={copy.previewZone} description={copy.previewDesc}>
              {preview ? (
                <div className="space-y-5">
                  <div className="rounded-2xl border border-slate-200 p-4">
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{copy.queryPlan}</p>
                    <p className="mt-2 text-sm font-semibold text-slate-900">{preview.query_plan.lane.label}</p>
                    <p className="mt-2 text-sm text-slate-600">{preview.account_profile_summary.positioning_summary}</p>
                    {preview.query_plan.primary_queries.length ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {preview.query_plan.primary_queries.slice(0, 6).map((query) => (
                          <Badge key={query} tone="muted">{query}</Badge>
                        ))}
                      </div>
                    ) : null}
                  </div>

                  <div>
                    <p className="text-sm font-semibold text-slate-900">{copy.topicDirections}</p>
                    <div className="mt-3 space-y-3">
                      {preview.topic_directions.map((item) => (
                        <div key={`${item.title}-${item.topic_kind}`} className="rounded-2xl border border-slate-200 p-4">
                          <p className="text-sm font-semibold text-slate-900">{item.title}</p>
                          <p className="mt-1 text-sm text-slate-500">{item.reason}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div>
                    <p className="text-sm font-semibold text-slate-900">{copy.titleDirections}</p>
                    <div className="mt-3 space-y-3">
                      {preview.title_directions.map((item) => (
                        <div key={`${item.title}-${item.style}`} className="rounded-2xl border border-slate-200 p-4">
                          <p className="text-sm font-semibold text-slate-900">{item.title}</p>
                          <p className="mt-1 text-sm text-slate-500">{item.rationale}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div>
                    <p className="text-sm font-semibold text-slate-900">{copy.outlinePreview}</p>
                    <div className="mt-3 rounded-2xl border border-slate-200 p-4">
                      <p className="text-sm text-slate-600">{preview.outline_preview.summary}</p>
                      <div className="mt-4 space-y-3">
                        {preview.outline_preview.sections.map((section) => (
                          <div key={section.section_id} className="rounded-2xl bg-slate-50 px-4 py-3">
                            <p className="text-sm font-semibold text-slate-900">{section.heading}</p>
                            <p className="mt-1 text-sm text-slate-500">{section.purpose}</p>
                            {section.key_points.length ? (
                              <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-600">
                                {section.key_points.map((point) => (
                                  <li key={point}>{point}</li>
                                ))}
                              </ul>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <EmptyState title={copy.previewEmpty} description={copy.previewEmptyDesc} />
              )}
            </Card>
          </div>
        </>
      ) : null}
    </div>
  );
}
