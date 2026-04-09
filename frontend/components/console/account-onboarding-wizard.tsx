"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  analyzeExistingAccount,
  createAccount,
  createAccountWeChatConfig,
  createReferenceSource,
  testAccountWeChatConfig,
  testWeChatConnection,
} from "@/lib/api";
import type {
  AccountCreateRequest,
  AccountOnboardingPath,
  AccountOnboardingStep,
  AccountWeChatOnboardingMode,
  CreateAutomationPlanRequest,
  ExistingAccountAnalysisResponse,
  OperationMode,
} from "@/types";
import { Badge, Button, Card, Input, PageHeader, Select, Textarea } from "@/components/console/ui";
import { Icon } from "@/components/console/icons";
import { useAppStore } from "@/store/appStore";

interface NewAccountDraft {
  name: string;
  positioning: string;
  audience: string;
  toneStyle: string;
  operationMode: OperationMode;
}

interface ExistingInputDraft {
  accountName: string;
  articleUrlsText: string;
  articleTextsText: string;
}

interface ExistingReviewDraft {
  name: string;
  positioning: string;
  audience: string;
  toneStyle: string;
  contentStrategy: string;
  referenceAccounts: string;
  operationMode: OperationMode;
}

interface WeChatDraft {
  mode: AccountWeChatOnboardingMode;
  app_id: string;
  app_secret: string;
  default_author: string;
  default_thumb_media_id: string;
  need_open_comment: boolean;
  only_fans_can_comment: boolean;
}

const newDraftDefaults: NewAccountDraft = {
  name: "",
  positioning: "",
  audience: "",
  toneStyle: "",
  operationMode: "manual",
};

const existingInputDefaults: ExistingInputDraft = {
  accountName: "",
  articleUrlsText: "",
  articleTextsText: "",
};

const wechatDraftDefaults: WeChatDraft = {
  mode: "skip_for_now",
  app_id: "",
  app_secret: "",
  default_author: "",
  default_thumb_media_id: "",
  need_open_comment: true,
  only_fans_can_comment: false,
};

function parseLineItems(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseArticleTexts(value: string): string[] {
  const trimmed = value.trim();
  if (!trimmed) {
    return [];
  }

  const segments = trimmed
    .split(/\n\s*---+\s*\n/g)
    .map((item) => item.trim())
    .filter(Boolean);

  return segments.length ? segments : [trimmed];
}

function buildAutomationPlan(mode: OperationMode): CreateAutomationPlanRequest {
  return {
    plan_type: mode,
    is_enabled: false,
    run_strategy: mode === "manual" ? "manual_only" : "hybrid",
    schedule_type: "none",
    schedule_config: null,
    auto_publish_enabled: false,
    publish_review_required: true,
    timezone: "Asia/Shanghai",
  };
}

function buildReviewDraft(
  analysis: ExistingAccountAnalysisResponse,
  accountName: string,
): ExistingReviewDraft {
  return {
    name: accountName,
    positioning: analysis.inferred_positioning,
    audience: analysis.inferred_audience,
    toneStyle: analysis.inferred_tone_style,
    contentStrategy: analysis.inferred_content_strategy,
    referenceAccounts: analysis.inferred_reference_accounts_summary ?? "",
    operationMode: analysis.recommended_operation_mode,
  };
}

export function AccountOnboardingWizard() {
  const router = useRouter();
  const pushToast = useAppStore((state) => state.pushToast);

  const [path, setPath] = useState<AccountOnboardingPath | null>(null);
  const [step, setStep] = useState<AccountOnboardingStep>("choose");
  const [newDraft, setNewDraft] = useState<NewAccountDraft>(newDraftDefaults);
  const [existingInput, setExistingInput] = useState<ExistingInputDraft>(existingInputDefaults);
  const [existingAnalysis, setExistingAnalysis] = useState<ExistingAccountAnalysisResponse | null>(null);
  const [existingReview, setExistingReview] = useState<ExistingReviewDraft | null>(null);
  const [wechatDraft, setWeChatDraft] = useState<WeChatDraft>(wechatDraftDefaults);
  const [wechatTestResult, setWeChatTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [busyLabel, setBusyLabel] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedMode = useMemo<OperationMode>(() => {
    if (path === "existing" && existingReview) {
      return existingReview.operationMode;
    }
    if (path === "existing") {
      return existingAnalysis?.recommended_operation_mode ?? "semi_auto";
    }
    return newDraft.operationMode;
  }, [existingAnalysis, existingReview, newDraft.operationMode, path]);

  const parsedArticleUrls = useMemo(() => parseLineItems(existingInput.articleUrlsText), [existingInput.articleUrlsText]);
  const parsedArticleTexts = useMemo(() => parseArticleTexts(existingInput.articleTextsText), [existingInput.articleTextsText]);
  const needsRealPublishWarning = wechatDraft.mode === "skip_for_now" && selectedMode !== "manual";
  const canContinueAfterWeChat =
    wechatDraft.mode === "skip_for_now" || (Boolean(wechatDraft.app_id.trim()) && Boolean(wechatDraft.app_secret.trim()));

  const stepItems = useMemo(() => {
    const items: Array<{ value: AccountOnboardingStep; label: string }> = [{ value: "choose", label: "Choose" }];
    if (path === "new") {
      items.push({ value: "new_details", label: "Basics" });
    }
    if (path === "existing") {
      items.push({ value: "existing_input", label: "History" });
    }
    if (path) {
      items.push({ value: "wechat_connect", label: "WeChat" });
    }
    if (path === "existing" && existingAnalysis) {
      items.push({ value: "existing_review", label: "Review" });
    }
    return items;
  }, [existingAnalysis, path]);

  const choosePath = (nextPath: AccountOnboardingPath) => {
    setPath(nextPath);
    setError(null);
    setExistingAnalysis(null);
    setExistingReview(null);
    setWeChatTestResult(null);
    setStep(nextPath === "new" ? "new_details" : "existing_input");
  };

  const resetWizard = () => {
    setPath(null);
    setStep("choose");
    setNewDraft(newDraftDefaults);
    setExistingInput(existingInputDefaults);
    setExistingAnalysis(null);
    setExistingReview(null);
    setWeChatDraft(wechatDraftDefaults);
    setWeChatTestResult(null);
    setBusyLabel(null);
    setError(null);
  };

  const runPreflightWeChatTest = async () => {
    if (!wechatDraft.app_id.trim() || !wechatDraft.app_secret.trim()) {
      pushToast({
        tone: "warning",
        title: "Credentials required",
        message: "Enter AppID and AppSecret before testing the official account connection.",
      });
      return;
    }

    try {
      setBusyLabel("Testing WeChat connection...");
      setError(null);
      const result = await testWeChatConnection({
        app_id: wechatDraft.app_id.trim(),
        app_secret: wechatDraft.app_secret.trim(),
      });
      setWeChatTestResult({ success: result.success, message: result.message });
      pushToast({
        tone: result.success ? "success" : "warning",
        title: result.success ? "Connection successful" : "Connection failed",
        message: result.message,
      });
    } catch (testError) {
      const message = testError instanceof Error ? testError.message : "Unable to test the WeChat connection.";
      setWeChatTestResult({ success: false, message });
      pushToast({
        tone: "danger",
        title: "Connection test failed",
        message,
      });
    } finally {
      setBusyLabel(null);
    }
  };

  const analyzeExisting = async () => {
    try {
      setBusyLabel("Analyzing historical articles...");
      setError(null);
      const analysis = await analyzeExistingAccount({
        account_name: existingInput.accountName.trim(),
        article_urls: parsedArticleUrls,
        article_texts: parsedArticleTexts,
      });
      setExistingAnalysis(analysis);
      setExistingReview(buildReviewDraft(analysis, existingInput.accountName.trim()));
      setStep("existing_review");
    } catch (analysisError) {
      setError(analysisError instanceof Error ? analysisError.message : "Unable to analyze existing account content.");
    } finally {
      setBusyLabel(null);
    }
  };

  const seedExistingReferenceSources = async (accountId: string) => {
    const urls = parsedArticleUrls.slice(0, 10);
    const articles = parsedArticleTexts.slice(0, 10);
    let seeded = 0;
    let failures = 0;

    for (const [index, url] of urls.entries()) {
      try {
        await createReferenceSource(accountId, {
          source_type: "article_url",
          name: `Imported article URL ${index + 1}`,
          source_value: url,
          notes: "Seeded from existing-account onboarding.",
          is_enabled: true,
        });
        seeded += 1;
      } catch {
        failures += 1;
      }
    }

    for (const [index, articleText] of articles.entries()) {
      try {
        await createReferenceSource(accountId, {
          source_type: "pasted_article",
          name: `Imported article text ${index + 1}`,
          source_value: articleText,
          notes: "Seeded from existing-account onboarding.",
          is_enabled: true,
        });
        seeded += 1;
      } catch {
        failures += 1;
      }
    }

    return { seeded, failures };
  };

  const attachWeChatConfig = async (accountId: string) => {
    if (wechatDraft.mode === "skip_for_now") {
      return { connected: false, failed: false, message: "Skipped during onboarding." };
    }

    try {
      await createAccountWeChatConfig(accountId, {
        app_id: wechatDraft.app_id.trim(),
        app_secret: wechatDraft.app_secret.trim(),
        default_author:
          wechatDraft.default_author.trim() ||
          (path === "existing" ? existingInput.accountName.trim() : newDraft.name.trim()) ||
          undefined,
        default_thumb_media_id: wechatDraft.default_thumb_media_id.trim() || undefined,
        need_open_comment: wechatDraft.need_open_comment,
        only_fans_can_comment: wechatDraft.only_fans_can_comment,
        is_enabled: true,
      });
      const testResult = await testAccountWeChatConfig(accountId);
      return {
        connected: testResult.success,
        failed: !testResult.success,
        message: testResult.message,
      };
    } catch (wechatError) {
      return {
        connected: false,
        failed: true,
        message: wechatError instanceof Error ? wechatError.message : "Unable to finish WeChat onboarding.",
      };
    }
  };

  const finalizeOnboarding = async () => {
    const isExisting = path === "existing";
    const accountName = isExisting ? existingReview?.name.trim() : newDraft.name.trim();
    const positioning = isExisting ? existingReview?.positioning.trim() : newDraft.positioning.trim();

    if (!accountName || !positioning) {
      setError("Account name and positioning are required before creating the account.");
      return;
    }

    try {
      setBusyLabel("Creating account...");
      setError(null);

      const payload: AccountCreateRequest = isExisting
        ? {
            name: existingReview?.name.trim() ?? "",
            positioning: existingReview?.positioning.trim() ?? "",
            audience: existingReview?.audience.trim() || undefined,
            tone_style: existingReview?.toneStyle.trim() || undefined,
            content_strategy: existingReview?.contentStrategy.trim() || undefined,
            reference_accounts: existingReview?.referenceAccounts.trim() || undefined,
            operation_mode: existingReview?.operationMode ?? "semi_auto",
            auto_run_enabled: false,
            auto_publish_enabled: false,
            automation_plan: buildAutomationPlan(existingReview?.operationMode ?? "semi_auto"),
          }
        : {
            name: newDraft.name.trim(),
            category: newDraft.positioning.trim(),
            positioning: newDraft.positioning.trim(),
            audience: newDraft.audience.trim() || undefined,
            tone_style: newDraft.toneStyle.trim() || undefined,
            operation_mode: newDraft.operationMode,
            auto_run_enabled: false,
            auto_publish_enabled: false,
            automation_plan: buildAutomationPlan(newDraft.operationMode),
          };

      const created = await createAccount(payload);
      const [wechatResult, seededSources] = await Promise.all([
        attachWeChatConfig(created.account_id),
        isExisting ? seedExistingReferenceSources(created.account_id) : Promise.resolve({ seeded: 0, failures: 0 }),
      ]);

      if (wechatResult.failed) {
        pushToast({
          tone: "warning",
          title: "Official account connection incomplete",
          message: `${wechatResult.message} The account was still created and can continue in content-only mode.`,
        });
      } else if (wechatResult.connected) {
        pushToast({
          tone: "success",
          title: "Official account connected",
          message: "The account was created and validated against the real WeChat configuration.",
        });
      }

      const params = new URLSearchParams({
        onboarding: "1",
        source: isExisting ? "existing" : "new",
        automation_seeded: "1",
        plan_type: payload.automation_plan?.plan_type ?? payload.operation_mode ?? "manual",
        wechat_connected: wechatResult.connected ? "1" : "0",
      });

      if (isExisting) {
        params.set("seeded_sources", String(seededSources.seeded));
        params.set("seed_failures", String(seededSources.failures));
      }

      if (wechatResult.failed) {
        params.set("wechat_test_failed", "1");
      }

      router.push(`/accounts/${created.account_id}/workspace?${params.toString()}`);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Unable to create the account.");
    } finally {
      setBusyLabel(null);
    }
  };

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Account Onboarding"
        title="Connect an Official Account"
        description="Choose whether this is a brand new public account or an existing one, then decide whether to connect the real AppID and AppSecret during onboarding."
        actions={
          step !== "choose" ? (
            <Button variant="secondary" onClick={resetWizard}>
              Start Over
            </Button>
          ) : null
        }
      />

      <div className="flex flex-wrap items-center gap-2">
        {stepItems.map((item, index) => {
          const active = item.value === step;
          return (
            <div key={item.value} className="flex items-center gap-2">
              <Badge tone={active ? "brand" : "muted"}>{`${index + 1}. ${item.label}`}</Badge>
              {index < stepItems.length - 1 ? <Icon name="chevronRight" className="h-4 w-4 text-slate-300" /> : null}
            </div>
          );
        })}
      </div>

      {error ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>
      ) : null}

      {step === "choose" ? (
        <div className="grid gap-6 md:grid-cols-2">
          <Card title="New Official Account" description="Use a lightweight setup if this is a new public account and you want to start operating quickly.">
            <p className="text-sm leading-6 text-slate-600">
              You only need the basic positioning, audience and tone. The wizard will generate a conservative automation plan and let you connect the real AppID/AppSecret before entering the workspace.
            </p>
            <div className="mt-5">
              <Button onClick={() => choosePath("new")}>
                <Icon name="plus" className="h-4 w-4" />
                Start New Account Setup
              </Button>
            </div>
          </Card>

          <Card title="Existing Official Account" description="Bring an existing public account in by analyzing a few representative historical articles first.">
            <p className="text-sm leading-6 text-slate-600">
              Paste article URLs or full article bodies, then confirm the inferred positioning and operating posture. The same wizard can also bind the real WeChat credentials before you enter the workspace.
            </p>
            <div className="mt-5">
              <Button onClick={() => choosePath("existing")}>
                <Icon name="history" className="h-4 w-4" />
                Analyze Existing Account
              </Button>
            </div>
          </Card>
        </div>
      ) : null}

      {step === "new_details" ? (
        <Card title="Basic Account Information" description="Keep the first step lightweight. The rest of the account configuration can continue inside the account workspace later.">
          <div className="grid gap-5 md:grid-cols-2">
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Account Name</label>
              <Input value={newDraft.name} onChange={(event) => setNewDraft((current) => ({ ...current, name: event.target.value }))} placeholder="HotClaw Growth Notes" />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Content Lane / Positioning</label>
              <Input value={newDraft.positioning} onChange={(event) => setNewDraft((current) => ({ ...current, positioning: event.target.value }))} placeholder="AI tools, creator growth, digital operations" />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Target Audience</label>
              <Input value={newDraft.audience} onChange={(event) => setNewDraft((current) => ({ ...current, audience: event.target.value }))} placeholder="Operators, founders, and content teams" />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Preferred Tone</label>
              <Input value={newDraft.toneStyle} onChange={(event) => setNewDraft((current) => ({ ...current, toneStyle: event.target.value }))} placeholder="Practical, sharp, high-signal, not fluffy" />
            </div>
            <div className="md:col-span-2">
              <label className="mb-2 block text-sm font-medium text-slate-700">Initial Operating Mode</label>
              <Select value={newDraft.operationMode} onChange={(event) => setNewDraft((current) => ({ ...current, operationMode: event.target.value as OperationMode }))}>
                <option value="manual">manual</option>
                <option value="semi_auto">semi_auto</option>
                <option value="full_auto">full_auto</option>
              </Select>
              <p className="mt-2 text-sm text-slate-500">
                The backend will still create a conservative automation plan. If you choose semi_auto or full_auto without completing WeChat connection, the account can only operate in content mode until real credentials are connected.
              </p>
            </div>
          </div>

          <div className="mt-6 flex justify-between gap-3">
            <Button variant="secondary" onClick={resetWizard}>
              Back
            </Button>
            <Button
              onClick={() => {
                setError(null);
                setStep("wechat_connect");
              }}
              disabled={!newDraft.name.trim() || !newDraft.positioning.trim()}
            >
              Continue to WeChat Connection
            </Button>
          </div>
        </Card>
      ) : null}

      {step === "existing_input" ? (
        <Card title="Existing Account History Input" description="Paste representative historical article URLs or full article bodies. Text input is still the most reliable path if URL fetching is incomplete.">
          <div className="grid gap-5">
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Account Name</label>
              <Input value={existingInput.accountName} onChange={(event) => setExistingInput((current) => ({ ...current, accountName: event.target.value }))} placeholder="HotClaw Existing Account" />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Article URLs</label>
              <Textarea value={existingInput.articleUrlsText} onChange={(event) => setExistingInput((current) => ({ ...current, articleUrlsText: event.target.value }))} placeholder={"One URL per line\nhttps://mp.weixin.qq.com/...\nhttps://mp.weixin.qq.com/..."} />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Article Texts</label>
              <Textarea value={existingInput.articleTextsText} onChange={(event) => setExistingInput((current) => ({ ...current, articleTextsText: event.target.value }))} placeholder={"Paste 3-10 representative article bodies.\nUse a standalone line with --- between articles."} />
            </div>
            <div className="flex flex-wrap gap-2 text-xs text-slate-500">
              <Badge tone="muted">{`${parsedArticleUrls.length} URL(s)`}</Badge>
              <Badge tone="muted">{`${parsedArticleTexts.length} article text block(s)`}</Badge>
            </div>
          </div>

          <div className="mt-6 flex justify-between gap-3">
            <Button variant="secondary" onClick={resetWizard}>
              Back
            </Button>
            <Button
              onClick={() => {
                setError(null);
                setStep("wechat_connect");
              }}
              disabled={!existingInput.accountName.trim() || (!parsedArticleUrls.length && !parsedArticleTexts.length)}
            >
              Continue to WeChat Connection
            </Button>
          </div>
        </Card>
      ) : null}

      {step === "wechat_connect" ? (
        <Card title="Official Account Connection" description="Connect the real public account now if you want this account to enter the real publishing chain. You can also skip and keep the account in content-only mode for now.">
          <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
            <div className="space-y-5">
              <div className="grid gap-3 md:grid-cols-2">
                <button
                  type="button"
                  onClick={() => setWeChatDraft((current) => ({ ...current, mode: "connect_now" }))}
                  className={`rounded-2xl border p-4 text-left transition ${
                    wechatDraft.mode === "connect_now"
                      ? "border-brand-300 bg-brand-50"
                      : "border-slate-200 bg-white hover:border-brand-200 hover:bg-brand-50/60"
                  }`}
                >
                  <p className="text-sm font-semibold text-slate-900">Connect Real Official Account</p>
                  <p className="mt-2 text-sm leading-6 text-slate-500">Fill AppID and AppSecret now, then test the connection before entering the workspace.</p>
                </button>
                <button
                  type="button"
                  onClick={() => setWeChatDraft((current) => ({ ...current, mode: "skip_for_now" }))}
                  className={`rounded-2xl border p-4 text-left transition ${
                    wechatDraft.mode === "skip_for_now"
                      ? "border-brand-300 bg-brand-50"
                      : "border-slate-200 bg-white hover:border-brand-200 hover:bg-brand-50/60"
                  }`}
                >
                  <p className="text-sm font-semibold text-slate-900">Skip for Now</p>
                  <p className="mt-2 text-sm leading-6 text-slate-500">Create the account first and keep it in content mode until real credentials are configured later.</p>
                </button>
              </div>

              {wechatDraft.mode === "connect_now" ? (
                <div className="grid gap-5 md:grid-cols-2">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">AppID</label>
                    <Input value={wechatDraft.app_id} onChange={(event) => setWeChatDraft((current) => ({ ...current, app_id: event.target.value }))} placeholder="wx1234567890" />
                  </div>
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">AppSecret</label>
                    <Input type="password" value={wechatDraft.app_secret} onChange={(event) => setWeChatDraft((current) => ({ ...current, app_secret: event.target.value }))} placeholder="Enter the real AppSecret" />
                  </div>
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">Default Author</label>
                    <Input value={wechatDraft.default_author} onChange={(event) => setWeChatDraft((current) => ({ ...current, default_author: event.target.value }))} placeholder={path === "existing" ? existingInput.accountName || "Default author" : newDraft.name || "Default author"} />
                  </div>
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">Default Thumb Media ID</label>
                    <Input value={wechatDraft.default_thumb_media_id} onChange={(event) => setWeChatDraft((current) => ({ ...current, default_thumb_media_id: event.target.value }))} placeholder="Optional media_id" />
                  </div>
                  <label className="flex items-center justify-between rounded-2xl border border-slate-200 p-4 md:col-span-2">
                    <span>
                      <span className="block text-sm font-medium text-slate-900">Enable Comments</span>
                      <span className="text-sm text-slate-500">Maps to the official account `need_open_comment` setting.</span>
                    </span>
                    <input type="checkbox" checked={wechatDraft.need_open_comment} onChange={(event) => setWeChatDraft((current) => ({ ...current, need_open_comment: event.target.checked }))} />
                  </label>
                  <label className="flex items-center justify-between rounded-2xl border border-slate-200 p-4 md:col-span-2">
                    <span>
                      <span className="block text-sm font-medium text-slate-900">Only Fans Can Comment</span>
                      <span className="text-sm text-slate-500">Maps to `only_fans_can_comment` on the official account publish payload.</span>
                    </span>
                    <input type="checkbox" checked={wechatDraft.only_fans_can_comment} onChange={(event) => setWeChatDraft((current) => ({ ...current, only_fans_can_comment: event.target.checked }))} />
                  </label>
                </div>
              ) : (
                <div className="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-4 text-sm leading-6 text-slate-600">
                  This account will still be created, but without real WeChat credentials it will stay in content-only mode. You can continue generating tasks and drafts, but real publish operations remain gated until the official account is connected.
                </div>
              )}
            </div>

            <div className="space-y-4">
              <Card title="What this step controls" description="This is the earliest point where the wizard can switch the account from content-only mode to real official-account operations.">
                <div className="space-y-3 text-sm leading-6 text-slate-600">
                  <p>Connected now: the wizard will create the account, save the account-scoped WeChat config, then run a backend connection test.</p>
                  <p>Skipped or failed: the account still enters the workspace, but it is clearly marked as content-only until the official account binding succeeds.</p>
                </div>
                {wechatTestResult ? (
                  <div className={`mt-4 rounded-2xl border px-4 py-3 text-sm ${wechatTestResult.success ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-amber-200 bg-amber-50 text-amber-700"}`}>
                    {wechatTestResult.message}
                  </div>
                ) : null}
                {needsRealPublishWarning ? (
                  <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                    {`The selected ${selectedMode} mode cannot enter the real publish chain until the official account is connected.`}
                  </div>
                ) : null}
                <div className="mt-5 flex flex-wrap gap-3">
                  <Button variant="secondary" onClick={() => void runPreflightWeChatTest()} disabled={busyLabel !== null || wechatDraft.mode !== "connect_now"}>
                    Test Connection
                  </Button>
                </div>
              </Card>
            </div>
          </div>

          <div className="mt-6 flex justify-between gap-3">
            <Button
              variant="secondary"
              onClick={() => {
                setError(null);
                setStep(path === "existing" ? "existing_input" : "new_details");
              }}
            >
              Back
            </Button>
            <Button
              onClick={() => (path === "existing" ? void analyzeExisting() : void finalizeOnboarding())}
              disabled={busyLabel !== null || !canContinueAfterWeChat}
            >
              {busyLabel ?? (path === "existing" ? "Analyze Historical Articles" : "Create Account")}
            </Button>
          </div>
        </Card>
      ) : null}

      {step === "existing_review" && existingReview && existingAnalysis ? (
        <Card title="Review Inferred Existing-Account Profile" description="The system inferred a starting profile from the historical articles. Adjust anything you want before the account is created.">
          <div className="grid gap-5 md:grid-cols-2">
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Account Name</label>
              <Input value={existingReview.name} onChange={(event) => setExistingReview((current) => (current ? { ...current, name: event.target.value } : current))} />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Recommended Confidence</label>
              <div className="flex h-11 items-center rounded-xl border border-slate-200 bg-slate-50 px-3.5 text-sm text-slate-700">
                {existingAnalysis.analysis_confidence}
              </div>
            </div>
            <div className="md:col-span-2">
              <label className="mb-2 block text-sm font-medium text-slate-700">Positioning</label>
              <Textarea value={existingReview.positioning} onChange={(event) => setExistingReview((current) => (current ? { ...current, positioning: event.target.value } : current))} />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Audience</label>
              <Textarea value={existingReview.audience} onChange={(event) => setExistingReview((current) => (current ? { ...current, audience: event.target.value } : current))} />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Tone & Style</label>
              <Textarea value={existingReview.toneStyle} onChange={(event) => setExistingReview((current) => (current ? { ...current, toneStyle: event.target.value } : current))} />
            </div>
            <div className="md:col-span-2">
              <label className="mb-2 block text-sm font-medium text-slate-700">Content Strategy</label>
              <Textarea value={existingReview.contentStrategy} onChange={(event) => setExistingReview((current) => (current ? { ...current, contentStrategy: event.target.value } : current))} />
            </div>
            <div className="md:col-span-2">
              <label className="mb-2 block text-sm font-medium text-slate-700">Reference Summary</label>
              <Textarea value={existingReview.referenceAccounts} onChange={(event) => setExistingReview((current) => (current ? { ...current, referenceAccounts: event.target.value } : current))} />
            </div>
            <div className="md:col-span-2">
              <label className="mb-2 block text-sm font-medium text-slate-700">Initial Operating Mode</label>
              <Select value={existingReview.operationMode} onChange={(event) => setExistingReview((current) => (current ? { ...current, operationMode: event.target.value as OperationMode } : current))}>
                <option value="manual">manual</option>
                <option value="semi_auto">semi_auto</option>
                <option value="full_auto">full_auto</option>
              </Select>
              {wechatDraft.mode === "skip_for_now" && existingReview.operationMode !== "manual" ? (
                <p className="mt-2 text-sm text-amber-700">
                  Without a successful official account connection, this mode can only continue as a content-mode account until WeChat binding is completed later.
                </p>
              ) : null}
            </div>
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            {existingAnalysis.extracted_topics.map((topic) => (
              <Badge key={topic} tone="muted">
                {topic}
              </Badge>
            ))}
          </div>

          <div className="mt-6 flex justify-between gap-3">
            <Button variant="secondary" onClick={() => setStep("wechat_connect")}>
              Back
            </Button>
            <Button onClick={() => void finalizeOnboarding()} disabled={busyLabel !== null}>
              {busyLabel ?? "Create Account"}
            </Button>
          </div>
        </Card>
      ) : null}
    </div>
  );
}
