"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { createAccount, getAccount, updateAccount } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { AccountCreateRequest, AccountDetail, OperationMode, PostingFrequency } from "@/types";
import { Button, Card, ErrorState, Input, PageHeader, Select, Textarea } from "@/components/console/ui";
import { useAppStore } from "@/store/appStore";

const initialForm: AccountCreateRequest = {
  name: "",
  category: "",
  positioning: "",
  audience: "",
  tone_style: "",
  posting_frequency: undefined,
  posting_time: "",
  content_strategy: "",
  reference_accounts: "",
  operation_mode: "manual",
  auto_run_enabled: false,
  auto_publish_enabled: false,
  is_active: true,
  publish_paused: false,
  max_posts_per_day: null,
  min_interval_minutes: null,
};

function normalize(detail: AccountDetail): AccountCreateRequest {
  return {
    name: detail.name,
    category: detail.category ?? "",
    positioning: detail.positioning,
    audience: detail.audience ?? "",
    tone_style: detail.tone_style ?? "",
    posting_frequency: detail.posting_frequency ?? undefined,
    posting_time: detail.posting_time ?? "",
    content_strategy: detail.content_strategy ?? "",
    reference_accounts: detail.reference_accounts ?? "",
    operation_mode: detail.operation_mode,
    auto_run_enabled: detail.auto_run_enabled,
    auto_publish_enabled: detail.auto_publish_enabled,
    is_active: detail.is_active,
    publish_paused: detail.publish_paused,
    max_posts_per_day: detail.max_posts_per_day,
    min_interval_minutes: detail.min_interval_minutes,
  };
}

export function AccountFormPage({ accountId }: { accountId?: string }) {
  const { locale, operationModeLabel } = useI18n();
  const router = useRouter();
  const pushToast = useAppStore((state) => state.pushToast);
  const [form, setForm] = useState<AccountCreateRequest>(initialForm);
  const [loading, setLoading] = useState(Boolean(accountId));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const editing = Boolean(accountId);

  useEffect(() => {
    if (!accountId) return;
    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const detail = await getAccount(accountId);
        setForm(normalize(detail));
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : locale === "zh-CN" ? "无法加载账号" : "Unable to load account");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [accountId, locale]);

  const title = useMemo(() => (editing ? (locale === "zh-CN" ? "编辑账号" : "Edit Account") : locale === "zh-CN" ? "新增账号" : "Add Account"), [editing, locale]);

  const operationModes: Array<{ value: OperationMode; label: string }> = useMemo(
    () => [
      { value: "manual", label: operationModeLabel("manual") },
      { value: "semi_auto", label: operationModeLabel("semi_auto") },
      { value: "full_auto", label: operationModeLabel("full_auto") },
    ],
    [operationModeLabel],
  );

  const postingFrequencies: Array<{ value: PostingFrequency; label: string }> = useMemo(
    () => [
      { value: "daily", label: locale === "zh-CN" ? "每日" : "Daily" },
      { value: "weekly", label: locale === "zh-CN" ? "每周" : "Weekly" },
      { value: "biweekly", label: locale === "zh-CN" ? "双周" : "Biweekly" },
      { value: "monthly", label: locale === "zh-CN" ? "每月" : "Monthly" },
    ],
    [locale],
  );

  const setField = <K extends keyof AccountCreateRequest>(key: K, value: AccountCreateRequest[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const submit = async () => {
    if (!form.name.trim() || !form.positioning.trim()) {
      pushToast({
        tone: "warning",
        title: locale === "zh-CN" ? "缺少必填项" : "Missing required fields",
        message: locale === "zh-CN" ? "账号名称和定位是必填项。" : "Account name and positioning are required.",
      });
      return;
    }

    try {
      setSaving(true);
      setError(null);
      if (editing && accountId) {
        await updateAccount(accountId, form);
        pushToast({
          tone: "success",
          title: locale === "zh-CN" ? "账号已更新" : "Account updated",
          message: locale === "zh-CN" ? "账号资料已成功保存。" : "The account profile was saved successfully.",
        });
        router.push(`/accounts/${accountId}`);
      } else {
        const created = await createAccount(form);
        pushToast({
          tone: "success",
          title: locale === "zh-CN" ? "账号已创建" : "Account created",
          message: locale === "zh-CN" ? `账号 ${created.name} 已准备好继续配置。` : `Account ${created.name} is ready for configuration.`,
        });
        router.push(`/accounts/${created.account_id}`);
      }
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : locale === "zh-CN" ? "无法保存账号" : "Unable to save account");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={editing ? (locale === "zh-CN" ? "编辑账号" : "Account Editing") : locale === "zh-CN" ? "账号接入" : "Account Onboarding"}
        title={title}
        description={locale === "zh-CN" ? "填写后端调度器所需的真实账号定位、自动化模式和发布保护设置。" : "Capture the real account positioning, automation mode and publish protection settings used by the backend scheduler."}
        actions={
          <Button variant="secondary" onClick={() => router.back()}>
            {locale === "zh-CN" ? "取消" : "Cancel"}
          </Button>
        }
      />

      {loading ? (
        <Card title={locale === "zh-CN" ? "正在加载账号表单" : "Loading account form"} description={locale === "zh-CN" ? "从后端获取账号详情。" : "Fetching account detail from the backend."}>
          <div className="h-64 animate-pulse rounded-3xl bg-slate-100" />
        </Card>
      ) : (
        <>
          {error ? <ErrorState title={locale === "zh-CN" ? "账号表单错误" : "Account form error"} description={error} /> : null}

          <div className="grid gap-6 xl:grid-cols-[1.25fr_0.95fr]">
            <Card title={locale === "zh-CN" ? "资料与定位" : "Profile & Positioning"} description={locale === "zh-CN" ? "这些字段定义了内容流水线的战略输入。" : "These fields define the strategic input for the content pipeline."}>
              <div className="grid gap-5">
                <div className="grid gap-5 md:grid-cols-2">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">{locale === "zh-CN" ? "账号名称" : "Account name"}</label>
                    <Input value={form.name} onChange={(event) => setField("name", event.target.value)} placeholder={locale === "zh-CN" ? "HotClaw 增长实验室" : "HotClaw Growth Lab"} />
                  </div>
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">{locale === "zh-CN" ? "分类" : "Category"}</label>
                    <Input value={form.category ?? ""} onChange={(event) => setField("category", event.target.value)} placeholder={locale === "zh-CN" ? "科技 / 财经 / 生活方式" : "Tech / Finance / Lifestyle"} />
                  </div>
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-700">{locale === "zh-CN" ? "定位" : "Positioning"}</label>
                  <Textarea
                    value={form.positioning}
                    onChange={(event) => setField("positioning", event.target.value)}
                    placeholder={locale === "zh-CN" ? "描述受众、细分方向、内容承诺和业务目标。" : "Describe the audience, niche, editorial promise and business objective."}
                  />
                </div>

                <div className="grid gap-5 md:grid-cols-2">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">{locale === "zh-CN" ? "受众" : "Audience"}</label>
                    <Textarea value={form.audience ?? ""} onChange={(event) => setField("audience", event.target.value)} placeholder={locale === "zh-CN" ? "创始人、PM、公众号运营..." : "Founders, PMs, WeChat operators..."} />
                  </div>
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">{locale === "zh-CN" ? "语气与风格" : "Tone & style"}</label>
                    <Textarea value={form.tone_style ?? ""} onChange={(event) => setField("tone_style", event.target.value)} placeholder={locale === "zh-CN" ? "理性、锋利、简洁..." : "Analytical, sharp, concise..."} />
                  </div>
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-700">{locale === "zh-CN" ? "内容策略" : "Content strategy"}</label>
                  <Textarea value={form.content_strategy ?? ""} onChange={(event) => setField("content_strategy", event.target.value)} placeholder={locale === "zh-CN" ? "固定主题、活动角度、合规要求..." : "Recurring themes, campaign angles, compliance rules..."} />
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-700">{locale === "zh-CN" ? "参考账号" : "Reference accounts"}</label>
                  <Textarea value={form.reference_accounts ?? ""} onChange={(event) => setField("reference_accounts", event.target.value)} placeholder={locale === "zh-CN" ? "竞品、灵感账号或 benchmark 参考。" : "Competitors, inspiration accounts or benchmark references."} />
                </div>
              </div>
            </Card>

            <div className="space-y-6">
              <Card title={locale === "zh-CN" ? "自动化设置" : "Automation Settings"} description={locale === "zh-CN" ? "这些设置直接映射到后端运行模式和调度语义。" : "These settings map directly to backend operation modes and scheduler semantics."}>
                <div className="grid gap-5">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">{locale === "zh-CN" ? "运行模式" : "Operation mode"}</label>
                    <Select value={form.operation_mode} onChange={(event) => setField("operation_mode", event.target.value as OperationMode)}>
                      {operationModes.map((mode) => (
                        <option key={mode.value} value={mode.value}>
                          {mode.label}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div className="grid gap-5 md:grid-cols-2">
                    <div>
                      <label className="mb-2 block text-sm font-medium text-slate-700">{locale === "zh-CN" ? "发布频率" : "Posting frequency"}</label>
                      <Select
                        value={form.posting_frequency ?? ""}
                        onChange={(event) => setField("posting_frequency", (event.target.value || undefined) as PostingFrequency | undefined)}
                      >
                        <option value="">{locale === "zh-CN" ? "未设置" : "Not set"}</option>
                        {postingFrequencies.map((frequency) => (
                          <option key={frequency.value} value={frequency.value}>
                            {frequency.label}
                          </option>
                        ))}
                      </Select>
                    </div>
                    <div>
                      <label className="mb-2 block text-sm font-medium text-slate-700">{locale === "zh-CN" ? "发布时间" : "Posting time"}</label>
                      <Input value={form.posting_time ?? ""} onChange={(event) => setField("posting_time", event.target.value)} placeholder="08:00" />
                    </div>
                  </div>
                  <label className="flex items-center justify-between rounded-2xl border border-slate-200 p-4">
                    <span>
                      <span className="block text-sm font-medium text-slate-900">{locale === "zh-CN" ? "启用自动运行" : "Auto-run enabled"}</span>
                      <span className="text-sm text-slate-500">{locale === "zh-CN" ? "允许调度器自动触发该账号。" : "Allow the scheduler to trigger this account automatically."}</span>
                    </span>
                    <input type="checkbox" checked={Boolean(form.auto_run_enabled)} onChange={(event) => setField("auto_run_enabled", event.target.checked)} />
                  </label>
                  <label className="flex items-center justify-between rounded-2xl border border-slate-200 p-4">
                    <span>
                      <span className="block text-sm font-medium text-slate-900">{locale === "zh-CN" ? "启用自动发布" : "Auto-publish enabled"}</span>
                      <span className="text-sm text-slate-500">{locale === "zh-CN" ? "在后端模式允许时执行自动发布。" : "Permit publish automation when the backend mode allows it."}</span>
                    </span>
                    <input type="checkbox" checked={Boolean(form.auto_publish_enabled)} onChange={(event) => setField("auto_publish_enabled", event.target.checked)} />
                  </label>
                </div>
              </Card>

              <Card title={locale === "zh-CN" ? "发布保护" : "Publish Safeguards"} description={locale === "zh-CN" ? "与后端账号保护字段保持一致的运行时安全约束。" : "Runtime safety constraints mirrored from backend account protection fields."}>
                <div className="grid gap-5">
                  <label className="flex items-center justify-between rounded-2xl border border-slate-200 p-4">
                    <span>
                      <span className="block text-sm font-medium text-slate-900">{locale === "zh-CN" ? "账号启用" : "Account active"}</span>
                      <span className="text-sm text-slate-500">{locale === "zh-CN" ? "停用账号不能被调度，也不能手动运行。" : "Inactive accounts cannot be scheduled or manually run."}</span>
                    </span>
                    <input type="checkbox" checked={Boolean(form.is_active)} onChange={(event) => setField("is_active", event.target.checked)} />
                  </label>
                  <label className="flex items-center justify-between rounded-2xl border border-slate-200 p-4">
                    <span>
                      <span className="block text-sm font-medium text-slate-900">{locale === "zh-CN" ? "暂停发布" : "Publish paused"}</span>
                      <span className="text-sm text-slate-500">{locale === "zh-CN" ? "用于需要继续生成内容但不向外发布的场景。" : "Use this when you need content generation but no outbound publishing."}</span>
                    </span>
                    <input type="checkbox" checked={Boolean(form.publish_paused)} onChange={(event) => setField("publish_paused", event.target.checked)} />
                  </label>
                  <div className="grid gap-5 md:grid-cols-2">
                    <div>
                      <label className="mb-2 block text-sm font-medium text-slate-700">{locale === "zh-CN" ? "每日最大发布数" : "Max posts per day"}</label>
                      <Input
                        type="number"
                        value={form.max_posts_per_day ?? ""}
                        onChange={(event) => setField("max_posts_per_day", event.target.value ? Number(event.target.value) : null)}
                        placeholder={locale === "zh-CN" ? "可选" : "Optional"}
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-sm font-medium text-slate-700">{locale === "zh-CN" ? "最小发布间隔（分钟）" : "Min interval minutes"}</label>
                      <Input
                        type="number"
                        value={form.min_interval_minutes ?? ""}
                        onChange={(event) => setField("min_interval_minutes", event.target.value ? Number(event.target.value) : null)}
                        placeholder={locale === "zh-CN" ? "可选" : "Optional"}
                      />
                    </div>
                  </div>
                </div>
              </Card>
            </div>
          </div>

          <div className="flex justify-end">
            <Button disabled={saving} onClick={() => void submit()}>
              {saving ? (locale === "zh-CN" ? "保存中..." : "Saving...") : editing ? (locale === "zh-CN" ? "保存修改" : "Save Changes") : locale === "zh-CN" ? "创建账号" : "Create Account"}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
