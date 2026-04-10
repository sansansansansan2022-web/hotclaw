"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  createAutomationPlan,
  getAccount,
  getAutomationPlan,
  updateAutomationPlan,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { formatDateTime } from "@/lib/utils";
import type {
  AccountDetail,
  AutomationPlan,
  AutomationPlanType,
  AutomationRunStrategy,
  AutomationScheduleType,
  UpdateAutomationPlanRequest,
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

interface AutomationPlanPageState {
  account: AccountDetail;
  plan: AutomationPlan;
}

function buildInitialForm(plan: AutomationPlan): UpdateAutomationPlanRequest {
  return {
    plan_type: plan.plan_type,
    is_enabled: plan.is_enabled,
    run_strategy: plan.run_strategy,
    schedule_type: plan.schedule_type,
    schedule_config: plan.schedule_config ?? null,
    auto_publish_enabled: plan.auto_publish_enabled,
    publish_review_required: plan.publish_review_required,
    max_posts_per_day: plan.max_posts_per_day,
    min_interval_minutes: plan.min_interval_minutes,
    timezone: plan.timezone,
    notes: plan.notes ?? "",
  };
}

function getTimeValue(scheduleConfig: Record<string, unknown> | null | undefined): string {
  const value = scheduleConfig?.time;
  return typeof value === "string" && value ? value : "09:00";
}

function getWeekdayValue(scheduleConfig: Record<string, unknown> | null | undefined): string {
  const value = scheduleConfig?.weekday;
  return typeof value === "string" && value ? value : "mon";
}

function getMonthlyDayValue(scheduleConfig: Record<string, unknown> | null | undefined): number {
  const value = scheduleConfig?.day;
  return typeof value === "number" ? value : 1;
}

function buildScheduleConfig(
  scheduleType: AutomationScheduleType | undefined,
  currentConfig: Record<string, unknown> | null | undefined,
): Record<string, unknown> | null {
  if (!scheduleType || scheduleType === "none") {
    return null;
  }

  if (scheduleType === "daily") {
    return { time: getTimeValue(currentConfig) };
  }

  if (scheduleType === "weekly") {
    return {
      weekday: getWeekdayValue(currentConfig),
      time: getTimeValue(currentConfig),
    };
  }

  return {
    day: getMonthlyDayValue(currentConfig),
    time: getTimeValue(currentConfig),
  };
}

export function AutomationPlanPage({ accountId }: { accountId: string }) {
  const { locale, operationModeLabel, t, token } = useI18n();
  const pushToast = useAppStore((state) => state.pushToast);
  const [data, setData] = useState<AutomationPlanPageState | null>(null);
  const [form, setForm] = useState<UpdateAutomationPlanRequest | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      const [account, plan] = await Promise.all([getAccount(accountId), getAutomationPlan(accountId)]);
      setData({ account, plan });
      setForm(buildInitialForm(plan));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : t("automationPlan.loadError"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [accountId]);

  const formatDisplayDateTime = (value?: string | null) => {
    if (!value) return t("automationPlan.notAvailable");
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat(locale === "zh-CN" ? "zh-CN" : "en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  };

  const scheduleSummary = useMemo(() => {
    if (!form) return t("automationPlan.manualOnly");
    if (form.schedule_type === "none" || !form.schedule_type) return t("automationPlan.manualOnly");
    const config = buildScheduleConfig(form.schedule_type, form.schedule_config);
    if (form.schedule_type === "daily") {
      return t("automationPlan.dailyAt", { time: getTimeValue(config) });
    }
    if (form.schedule_type === "weekly") {
      return t("automationPlan.weeklyAt", {
        weekday: token(String(config?.weekday || "mon")),
        time: getTimeValue(config),
      });
    }
    return t("automationPlan.monthlyAt", {
      day: getMonthlyDayValue(config),
      time: getTimeValue(config),
    });
  }, [form, t, token]);

  const handleSave = async () => {
    if (!form) return;

    try {
      setSaving(true);
      const payload: UpdateAutomationPlanRequest = {
        ...form,
        schedule_config: buildScheduleConfig(form.schedule_type, form.schedule_config),
        notes: form.notes?.trim() || undefined,
      };

      const saved =
        data?.plan.id == null
          ? await createAutomationPlan(accountId, payload)
          : await updateAutomationPlan(accountId, payload);

      pushToast({
        tone: "success",
        title: t("automationPlan.savedTitle"),
        message: t("automationPlan.savedMessage"),
      });
      setData((current) => (current ? { ...current, plan: saved } : current));
      setForm(buildInitialForm(saved));
    } catch (saveError) {
      pushToast({
        tone: "danger",
        title: t("automationPlan.saveFailedTitle"),
        message: saveError instanceof Error ? saveError.message : t("automationPlan.unexpectedError"),
      });
    } finally {
      setSaving(false);
    }
  };

  const planType = (form?.plan_type ?? "manual") as AutomationPlanType;
  const scheduleType = (form?.schedule_type ?? "none") as AutomationScheduleType;
  const runStrategy = (form?.run_strategy ?? "manual_only") as AutomationRunStrategy;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={t("automationPlan.eyebrow")}
        title={
          data?.account.name
            ? t("automationPlan.titleWithAccount", { name: data.account.name })
            : t("automationPlan.title")
        }
        description={t("automationPlan.description")}
        actions={
          <>
            <Link href={`/accounts/${accountId}`}>
              <Button variant="secondary">{t("automationPlan.backToAccount")}</Button>
            </Link>
            <Link href={`/accounts/${accountId}/workspace`}>
              <Button variant="secondary">{t("automationPlan.backToWorkspace")}</Button>
            </Link>
          </>
        }
      />

      {loading ? (
        <SkeletonRows rows={6} />
      ) : error ? (
        <ErrorState title={t("automationPlan.loadFailed")} description={error} retry={() => void load()} />
      ) : data && form ? (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">{t("automationPlan.currentAccount")}</Badge>
            <Badge tone="muted">{data.account.name}</Badge>
            <Badge tone="muted">{accountId}</Badge>
            <Badge tone={data.plan.config_source === "plan" ? "success" : "warning"}>
              {data.plan.config_source === "plan" ? t("automationPlan.planBacked") : t("automationPlan.legacyFallback")}
            </Badge>
          </div>

          {data.plan.config_source === "legacy_fallback" ? (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              {t("automationPlan.legacyBanner")}
            </div>
          ) : null}

          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label={t("automationPlan.stat.planType")}
              value={operationModeLabel(planType)}
              hint={scheduleSummary}
              tone="brand"
              icon={<Icon name="workspace" className="h-6 w-6" />}
            />
            <StatCard
              label={t("automationPlan.stat.planStatus")}
              value={form.is_enabled ? t("automationPlan.enabled") : t("automationPlan.disabled")}
              hint={token(runStrategy)}
              tone={form.is_enabled ? "success" : "muted"}
              icon={<Icon name="check" className="h-6 w-6" />}
            />
            <StatCard
              label={t("automationPlan.stat.autoPublish")}
              value={form.auto_publish_enabled ? t("automationPlan.allowed") : t("automationPlan.off")}
              hint={form.publish_review_required ? t("automationPlan.reviewRequired") : t("automationPlan.reviewOptional")}
              tone={form.auto_publish_enabled ? "warning" : "muted"}
              icon={<Icon name="publish" className="h-6 w-6" />}
            />
            <StatCard
              label={t("automationPlan.stat.nextRun")}
              value={formatDisplayDateTime(data.plan.next_run_at)}
              hint={t("automationPlan.timezoneHint", { timezone: form.timezone || "Asia/Shanghai" })}
              tone="info"
              icon={<Icon name="history" className="h-6 w-6" />}
            />
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            <Card
              title={t("automationPlan.config.title")}
              description={t("automationPlan.config.description")}
            >
              <div className="grid gap-5">
                <div className="grid gap-5 md:grid-cols-2">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">{t("automationPlan.label.planType")}</label>
                    <Select
                      value={planType}
                      onChange={(event) =>
                        setForm((current) =>
                          current
                            ? {
                                ...current,
                                plan_type: event.target.value as AutomationPlanType,
                                run_strategy:
                                  event.target.value === "manual"
                                    ? "manual_only"
                                    : current.schedule_type === "none"
                                      ? "manual_only"
                                      : "hybrid",
                              }
                            : current,
                        )
                      }
                    >
                      <option value="manual">{operationModeLabel("manual")}</option>
                      <option value="semi_auto">{operationModeLabel("semi_auto")}</option>
                      <option value="full_auto">{operationModeLabel("full_auto")}</option>
                    </Select>
                  </div>
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">{t("automationPlan.label.runStrategy")}</label>
                    <Select
                      value={runStrategy}
                      onChange={(event) =>
                        setForm((current) =>
                          current ? { ...current, run_strategy: event.target.value as AutomationRunStrategy } : current,
                        )
                      }
                    >
                      <option value="manual_only">{token("manual_only")}</option>
                      <option value="scheduled">{token("scheduled")}</option>
                      <option value="hybrid">{token("hybrid")}</option>
                    </Select>
                  </div>
                </div>

                <div className="grid gap-5 md:grid-cols-2">
                  <label className="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      checked={Boolean(form.is_enabled)}
                      onChange={(event) =>
                        setForm((current) => (current ? { ...current, is_enabled: event.target.checked } : current))
                      }
                    />
                    {t("automationPlan.label.enablePlan")}
                  </label>
                  <label className="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      checked={Boolean(form.auto_publish_enabled)}
                      onChange={(event) =>
                        setForm((current) =>
                          current ? { ...current, auto_publish_enabled: event.target.checked } : current,
                        )
                      }
                    />
                    {t("automationPlan.label.allowAutoPublish")}
                  </label>
                </div>

                <label className="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={Boolean(form.publish_review_required)}
                    onChange={(event) =>
                      setForm((current) =>
                        current ? { ...current, publish_review_required: event.target.checked } : current,
                      )
                    }
                  />
                  {t("automationPlan.label.requireReview")}
                </label>

                <div className="grid gap-5 md:grid-cols-2">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">{t("automationPlan.label.scheduleType")}</label>
                    <Select
                      value={scheduleType}
                      onChange={(event) =>
                        setForm((current) =>
                          current
                            ? {
                                ...current,
                                schedule_type: event.target.value as AutomationScheduleType,
                                schedule_config: buildScheduleConfig(
                                  event.target.value as AutomationScheduleType,
                                  current.schedule_config,
                                ),
                              }
                            : current,
                        )
                      }
                    >
                      <option value="none">{token("none")}</option>
                      <option value="daily">{token("daily")}</option>
                      <option value="weekly">{token("weekly")}</option>
                      <option value="monthly">{token("monthly")}</option>
                    </Select>
                  </div>
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">{t("automationPlan.label.timezone")}</label>
                    <Input
                      value={form.timezone ?? "Asia/Shanghai"}
                      onChange={(event) =>
                        setForm((current) => (current ? { ...current, timezone: event.target.value } : current))
                      }
                      placeholder="Asia/Shanghai"
                    />
                  </div>
                </div>

                {scheduleType !== "none" ? (
                  <div className="grid gap-5 md:grid-cols-3">
                    {scheduleType === "weekly" ? (
                      <div>
                        <label className="mb-2 block text-sm font-medium text-slate-700">{t("automationPlan.label.weekday")}</label>
                        <Select
                          value={getWeekdayValue(form.schedule_config)}
                          onChange={(event) =>
                            setForm((current) =>
                              current
                                ? {
                                    ...current,
                                    schedule_config: {
                                      ...buildScheduleConfig(current.schedule_type, current.schedule_config),
                                      weekday: event.target.value,
                                    },
                                  }
                                : current,
                            )
                          }
                        >
                          <option value="mon">{token("mon")}</option>
                          <option value="tue">{token("tue")}</option>
                          <option value="wed">{token("wed")}</option>
                          <option value="thu">{token("thu")}</option>
                          <option value="fri">{token("fri")}</option>
                          <option value="sat">{token("sat")}</option>
                          <option value="sun">{token("sun")}</option>
                        </Select>
                      </div>
                    ) : null}
                    {scheduleType === "monthly" ? (
                      <div>
                        <label className="mb-2 block text-sm font-medium text-slate-700">{t("automationPlan.label.day")}</label>
                        <Input
                          type="number"
                          min={1}
                          max={28}
                          value={String(getMonthlyDayValue(form.schedule_config))}
                          onChange={(event) =>
                            setForm((current) =>
                              current
                                ? {
                                    ...current,
                                    schedule_config: {
                                      ...buildScheduleConfig(current.schedule_type, current.schedule_config),
                                      day: Number(event.target.value || 1),
                                    },
                                  }
                                : current,
                            )
                          }
                        />
                      </div>
                    ) : null}
                    <div>
                      <label className="mb-2 block text-sm font-medium text-slate-700">{t("automationPlan.label.time")}</label>
                      <Input
                        type="time"
                        value={getTimeValue(form.schedule_config)}
                        onChange={(event) =>
                          setForm((current) =>
                            current
                              ? {
                                  ...current,
                                  schedule_config: {
                                    ...buildScheduleConfig(current.schedule_type, current.schedule_config),
                                    time: event.target.value,
                                  },
                                }
                              : current,
                          )
                        }
                      />
                    </div>
                  </div>
                ) : null}

                <div className="grid gap-5 md:grid-cols-2">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">{t("automationPlan.label.maxPostsPerDay")}</label>
                    <Input
                      type="number"
                      min={1}
                      max={100}
                      value={form.max_posts_per_day ?? ""}
                      onChange={(event) =>
                        setForm((current) =>
                          current
                            ? {
                                ...current,
                                max_posts_per_day: event.target.value ? Number(event.target.value) : null,
                              }
                            : current,
                        )
                      }
                    />
                  </div>
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">{t("automationPlan.label.minIntervalMinutes")}</label>
                    <Input
                      type="number"
                      min={1}
                      max={1440}
                      value={form.min_interval_minutes ?? ""}
                      onChange={(event) =>
                        setForm((current) =>
                          current
                            ? {
                                ...current,
                                min_interval_minutes: event.target.value ? Number(event.target.value) : null,
                              }
                            : current,
                        )
                      }
                    />
                  </div>
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-700">{t("automationPlan.label.notes")}</label>
                  <Textarea
                    value={form.notes ?? ""}
                    onChange={(event) =>
                      setForm((current) => (current ? { ...current, notes: event.target.value } : current))
                    }
                    placeholder={t("automationPlan.notesPlaceholder")}
                  />
                </div>
              </div>
            </Card>

            <Card
              title={t("automationPlan.preview.title")}
              description={t("automationPlan.preview.description")}
            >
              <div className="space-y-4 text-sm text-slate-600">
                <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                  <p className="font-semibold text-slate-900">{t("automationPlan.preview.visibleSchedule")}</p>
                  <p className="mt-2">{scheduleSummary}</p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                  <p className="font-semibold text-slate-900">{t("automationPlan.preview.runtimeSignals")}</p>
                  <p className="mt-2">{t("automationPlan.preview.lastRun", { time: formatDisplayDateTime(data.plan.last_run_at) })}</p>
                  <p className="mt-1">{t("automationPlan.preview.latestStatus", { status: token(data.plan.latest_status ?? "unknown") })}</p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                  <p className="font-semibold text-slate-900">{t("automationPlan.preview.publishSafeguards")}</p>
                  <p className="mt-2">
                    {form.publish_review_required
                      ? t("automationPlan.preview.reviewStillRequired")
                      : t("automationPlan.preview.reviewNotRequired")}
                  </p>
                </div>
                <div className="flex flex-wrap gap-3 pt-2">
                  <Button onClick={() => void handleSave()} disabled={saving}>
                    <Icon name="check" className="h-4 w-4" />
                    {saving ? t("automationPlan.saving") : t("automationPlan.save")}
                  </Button>
                  <Button
                    variant="secondary"
                    disabled={saving}
                    onClick={() => setForm(buildInitialForm(data.plan))}
                  >
                    {t("automationPlan.reset")}
                  </Button>
                </div>
              </div>
            </Card>
          </div>

          {!data.plan.id ? (
            <EmptyState
              title={t("automationPlan.firstPlanTitle")}
              description={t("automationPlan.firstPlanDesc")}
            />
          ) : null}
        </>
      ) : null}
    </div>
  );
}
