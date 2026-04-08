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
  const { operationModeLabel } = useI18n();
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
      setError(loadError instanceof Error ? loadError.message : "Unable to load automation plan.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [accountId]);

  const scheduleSummary = useMemo(() => {
    if (!form) return "Manual only";
    if (form.schedule_type === "none" || !form.schedule_type) return "Manual only";
    const config = buildScheduleConfig(form.schedule_type, form.schedule_config);
    if (form.schedule_type === "daily") {
      return `Daily at ${getTimeValue(config)}`;
    }
    if (form.schedule_type === "weekly") {
      return `Weekly on ${String(config?.weekday || "mon").toUpperCase()} at ${getTimeValue(config)}`;
    }
    return `Monthly on day ${getMonthlyDayValue(config)} at ${getTimeValue(config)}`;
  }, [form]);

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
        title: "Automation plan saved",
        message: "The account runtime posture now reads from this plan first.",
      });
      setData((current) => (current ? { ...current, plan: saved } : current));
      setForm(buildInitialForm(saved));
    } catch (saveError) {
      pushToast({
        tone: "danger",
        title: "Save failed",
        message: saveError instanceof Error ? saveError.message : "Unexpected error.",
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
        eyebrow="Automation Plan"
        title={data?.account.name ? `${data.account.name} Automation Plan` : "Automation Plan"}
        description="Manage the active automation-plan object that controls how this account runs, schedules, and protects publishing."
        actions={
          <>
            <Link href={`/accounts/${accountId}`}>
              <Button variant="secondary">Back to Account</Button>
            </Link>
            <Link href={`/accounts/${accountId}/workspace`}>
              <Button variant="secondary">Back to Workspace</Button>
            </Link>
          </>
        }
      />

      {loading ? (
        <SkeletonRows rows={6} />
      ) : error ? (
        <ErrorState title="Automation plan failed to load" description={error} retry={() => void load()} />
      ) : data && form ? (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">Current Account</Badge>
            <Badge tone="muted">{data.account.name}</Badge>
            <Badge tone="muted">{accountId}</Badge>
            <Badge tone={data.plan.config_source === "plan" ? "success" : "warning"}>
              {data.plan.config_source === "plan" ? "plan-backed" : "legacy fallback"}
            </Badge>
          </div>

          {data.plan.config_source === "legacy_fallback" ? (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              This account is still using a legacy fallback summary. Saving once will materialize the dedicated automation-plan record.
            </div>
          ) : null}

          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Plan Type"
              value={operationModeLabel(planType)}
              hint={scheduleSummary}
              tone="brand"
              icon={<Icon name="workspace" className="h-6 w-6" />}
            />
            <StatCard
              label="Plan Status"
              value={form.is_enabled ? "Enabled" : "Disabled"}
              hint={runStrategy}
              tone={form.is_enabled ? "success" : "muted"}
              icon={<Icon name="check" className="h-6 w-6" />}
            />
            <StatCard
              label="Auto Publish"
              value={form.auto_publish_enabled ? "Allowed" : "Off"}
              hint={form.publish_review_required ? "Human review still required" : "Can publish without human review"}
              tone={form.auto_publish_enabled ? "warning" : "muted"}
              icon={<Icon name="publish" className="h-6 w-6" />}
            />
            <StatCard
              label="Next Run"
              value={formatDateTime(data.plan.next_run_at)}
              hint={`Timezone ${form.timezone || "Asia/Shanghai"}`}
              tone="info"
              icon={<Icon name="history" className="h-6 w-6" />}
            />
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            <Card
              title="Plan Configuration"
              description="Phase 4 keeps one active plan per account and focuses on making runtime posture manageable."
            >
              <div className="grid gap-5">
                <div className="grid gap-5 md:grid-cols-2">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">Plan Type</label>
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
                    <label className="mb-2 block text-sm font-medium text-slate-700">Run Strategy</label>
                    <Select
                      value={runStrategy}
                      onChange={(event) =>
                        setForm((current) =>
                          current ? { ...current, run_strategy: event.target.value as AutomationRunStrategy } : current,
                        )
                      }
                    >
                      <option value="manual_only">manual_only</option>
                      <option value="scheduled">scheduled</option>
                      <option value="hybrid">hybrid</option>
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
                    Enable plan
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
                    Allow auto publish
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
                  Require human review before publish
                </label>

                <div className="grid gap-5 md:grid-cols-2">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">Schedule Type</label>
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
                      <option value="none">none</option>
                      <option value="daily">daily</option>
                      <option value="weekly">weekly</option>
                      <option value="monthly">monthly</option>
                    </Select>
                  </div>
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">Timezone</label>
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
                        <label className="mb-2 block text-sm font-medium text-slate-700">Weekday</label>
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
                          <option value="mon">MON</option>
                          <option value="tue">TUE</option>
                          <option value="wed">WED</option>
                          <option value="thu">THU</option>
                          <option value="fri">FRI</option>
                          <option value="sat">SAT</option>
                          <option value="sun">SUN</option>
                        </Select>
                      </div>
                    ) : null}
                    {scheduleType === "monthly" ? (
                      <div>
                        <label className="mb-2 block text-sm font-medium text-slate-700">Day</label>
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
                      <label className="mb-2 block text-sm font-medium text-slate-700">Time</label>
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
                    <label className="mb-2 block text-sm font-medium text-slate-700">Max Posts Per Day</label>
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
                    <label className="mb-2 block text-sm font-medium text-slate-700">Min Interval Minutes</label>
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
                  <label className="mb-2 block text-sm font-medium text-slate-700">Notes</label>
                  <Textarea
                    value={form.notes ?? ""}
                    onChange={(event) =>
                      setForm((current) => (current ? { ...current, notes: event.target.value } : current))
                    }
                    placeholder="For example: keep manual review enabled until the first successful content cycle."
                  />
                </div>
              </div>
            </Card>

            <Card
              title="Plan Preview"
              description="This is the summary that the workspace and runtime paths will now prefer."
            >
              <div className="space-y-4 text-sm text-slate-600">
                <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                  <p className="font-semibold text-slate-900">Visible Schedule</p>
                  <p className="mt-2">{scheduleSummary}</p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                  <p className="font-semibold text-slate-900">Runtime Signals</p>
                  <p className="mt-2">{`Last run: ${formatDateTime(data.plan.last_run_at)}`}</p>
                  <p className="mt-1">{`Latest status: ${data.plan.latest_status ?? "unknown"}`}</p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                  <p className="font-semibold text-slate-900">Publish Safeguards</p>
                  <p className="mt-2">
                    {form.publish_review_required
                      ? "Human review still stays in front of publishing."
                      : "Publishing can proceed without an extra human review gate."}
                  </p>
                </div>
                <div className="flex flex-wrap gap-3 pt-2">
                  <Button onClick={() => void handleSave()} disabled={saving}>
                    <Icon name="check" className="h-4 w-4" />
                    {saving ? "Saving..." : "Save Plan"}
                  </Button>
                  <Button
                    variant="secondary"
                    disabled={saving}
                    onClick={() => setForm(buildInitialForm(data.plan))}
                  >
                    Reset to Current
                  </Button>
                </div>
              </div>
            </Card>
          </div>

          {!data.plan.id ? (
            <EmptyState
              title="This will become the first stored plan"
              description="The account is still using a legacy fallback summary. The first save will create the dedicated automation-plan record."
            />
          ) : null}
        </>
      ) : null}
    </div>
  );
}
