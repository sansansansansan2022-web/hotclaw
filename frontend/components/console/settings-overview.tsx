"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { LanguageSwitcher } from "@/components/console/language-switcher";
import {
  IMAGE_GENERATION_PROVIDER_PRESETS,
  getAllSystemConfigs,
  listAccounts,
  listAgents,
  listLLMProviders,
  listSkills,
  testImageGenerationConnection,
  upsertSystemConfig,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { formatNumber, startCase } from "@/lib/utils";
import type { AccountSummary, AgentInfo, LLMProviderInfo, SkillInfo, SystemConfigMap } from "@/types";
import { Badge, Button, Card, EmptyState, ErrorState, Input, PageHeader, SkeletonRows, StatCard } from "@/components/console/ui";
import { Icon } from "@/components/console/icons";

export function SettingsPage() {
  const { t } = useI18n();
  const [configs, setConfigs] = useState<SystemConfigMap>({});
  const [providers, setProviders] = useState<LLMProviderInfo[]>([]);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [accounts, setAccounts] = useState<AccountSummary[]>([]);
  const [imageGenerationProvider, setImageGenerationProvider] = useState("dashscope");
  const [imageGenerationModel, setImageGenerationModel] = useState("wan2.7-image");
  const [imageGenerationApiKey, setImageGenerationApiKey] = useState("");
  const [imageGenerationApiKeyHint, setImageGenerationApiKeyHint] = useState("");
  const [imageGenerationEnabled, setImageGenerationEnabled] = useState(false);
  const [imageGenerationBaseUrl, setImageGenerationBaseUrl] = useState(
    "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation",
  );
  const [imageConfigSaving, setImageConfigSaving] = useState(false);
  const [imageConfigNotice, setImageConfigNotice] = useState<string | null>(null);
  const [imageTestRunning, setImageTestRunning] = useState(false);
  const [imageTestResult, setImageTestResult] = useState<{
    success: boolean;
    message: string;
    latency?: number;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      const [configsRes, providersRes, agentsRes, skillsRes, accountsRes] = await Promise.all([
        getAllSystemConfigs().catch(() => ({})),
        listLLMProviders().catch(() => []),
        listAgents().catch(() => ({ agents: [] })),
        listSkills().catch(() => ({ skills: [] })),
        listAccounts(1, 100).catch(() => ({ accounts: [], pagination: { page: 1, page_size: 100, total: 0 } })),
      ]);
      const nextConfigs = configsRes as SystemConfigMap;
      setConfigs(nextConfigs);
      setImageGenerationProvider(String(nextConfigs.image_generation_provider ?? "dashscope"));
      setImageGenerationModel(String(nextConfigs.image_generation_model ?? "wan2.7-image"));
      setImageGenerationEnabled(String(nextConfigs.image_generation_enabled ?? "false").toLowerCase() === "true");
      const apiKeyValue = String(nextConfigs.image_generation_api_key ?? "");
      setImageGenerationApiKey(apiKeyValue.startsWith("***") || apiKeyValue === "****" ? "" : apiKeyValue);
      setImageGenerationApiKeyHint(apiKeyValue.startsWith("***") || apiKeyValue === "****" ? apiKeyValue : "");
      setImageGenerationBaseUrl(
        String(
          nextConfigs.image_generation_base_url ??
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation",
        ),
      );
      setProviders(providersRes);
      setAgents(agentsRes.agents);
      setSkills(skillsRes.skills);
      setAccounts(accountsRes.accounts);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : t("settings.title"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const selectedImageProvider =
    IMAGE_GENERATION_PROVIDER_PRESETS.find((preset) => preset.provider_id === imageGenerationProvider) ??
    IMAGE_GENERATION_PROVIDER_PRESETS[0];

  const handleImageProviderChange = (providerId: string) => {
    const preset = IMAGE_GENERATION_PROVIDER_PRESETS.find((item) => item.provider_id === providerId);
    setImageGenerationProvider(providerId);
    if (preset?.default_model) {
      setImageGenerationModel(preset.default_model);
    }
    setImageGenerationBaseUrl(preset?.default_base_url || "");
    setImageConfigNotice(null);
    setImageTestResult(null);
  };

  const saveImageGenerationConfig = async () => {
    const provider = imageGenerationProvider.trim() || "dashscope";
    const model = imageGenerationModel.trim();
    const apiKey = imageGenerationApiKey.trim();
    const baseUrl = imageGenerationBaseUrl.trim();
    if (!model) {
      setImageConfigNotice("Enter an image generation model before saving.");
      return;
    }

    setImageConfigSaving(true);
    setImageConfigNotice(null);
    try {
      const updates = [
        upsertSystemConfig("image_generation_provider", provider, "string", {
          category: "image_assets",
          description: "Provider used for AI image generation.",
        }),
        upsertSystemConfig("image_generation_model", model, "string", {
          category: "image_assets",
          description: "Default AI image generation model.",
        }),
        upsertSystemConfig("image_generation_base_url", baseUrl, "string", {
          category: "image_assets",
          description: "Base URL or endpoint for the selected image generation provider.",
        }),
        upsertSystemConfig("image_generation_enabled", imageGenerationEnabled ? "true" : "false", "boolean", {
          category: "image_assets",
          description: "Enable AI image generation for draft preview image assets.",
        }),
      ];
      if (apiKey) {
        updates.push(
          upsertSystemConfig("image_generation_api_key", apiKey, "string", {
            category: "image_assets",
            description: "API key for the selected image generation provider.",
            isSensitive: true,
          }),
        );
      }
      await Promise.all(updates);
      setConfigs((current) => ({
        ...current,
        image_generation_provider: provider,
        image_generation_model: model,
        image_generation_base_url: baseUrl,
        image_generation_enabled: imageGenerationEnabled ? "true" : "false",
        ...(apiKey ? { image_generation_api_key: `***${apiKey.slice(-4)}` } : {}),
      }));
      if (apiKey) {
        setImageGenerationApiKey("");
        setImageGenerationApiKeyHint(`***${apiKey.slice(-4)}`);
      }
      setImageConfigNotice("Image generation config saved.");
    } catch (saveError) {
      setImageConfigNotice(saveError instanceof Error ? saveError.message : "Unable to save image generation config.");
    } finally {
      setImageConfigSaving(false);
    }
  };

  const handleImageConnectionTest = async () => {
    setImageTestRunning(true);
    setImageTestResult(null);
    setImageConfigNotice(null);
    try {
      const result = await testImageGenerationConnection({
        provider: imageGenerationProvider.trim() || "dashscope",
        model: imageGenerationModel.trim(),
        base_url: imageGenerationBaseUrl.trim() || undefined,
        api_key: imageGenerationApiKey.trim() || undefined,
      });

      if (result.success) {
        setImageTestResult({
          success: true,
          message: result.response_preview || "Connection test succeeded.",
          latency: result.latency_ms,
        });
      } else {
        setImageTestResult({
          success: false,
          message: result.error_message || "Connection test failed.",
          latency: result.latency_ms,
        });
      }
    } catch (testError) {
      setImageTestResult({
        success: false,
        message: testError instanceof Error ? testError.message : "Unable to test image generation connection.",
      });
    } finally {
      setImageTestRunning(false);
    }
  };

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={t("settings.eyebrow")}
        title={t("settings.title")}
        description={t("settings.description")}
      />

      {loading ? (
        <SkeletonRows rows={5} />
      ) : error ? (
        <ErrorState title={`${t("settings.title")} ${t("tasks.failed")}`} description={error} retry={() => void load()} />
      ) : (
        <>
          <div className="grid gap-5 md:grid-cols-4">
            <StatCard label={t("settings.systemConfigs")} value={formatNumber(Object.keys(configs).length)} hint={`Environment: ${String(configs.app_env ?? "unknown")}`} tone="brand" icon={<Icon name="settings" className="h-6 w-6" />} />
            <StatCard label={t("settings.providers")} value={formatNumber(providers.length)} hint="Configured provider records" tone="info" icon={<Icon name="dashboard" className="h-6 w-6" />} />
            <StatCard label={t("settings.agents")} value={formatNumber(agents.length)} hint="Registered agent definitions" tone="success" icon={<Icon name="workspace" className="h-6 w-6" />} />
            <StatCard label={t("settings.skills")} value={formatNumber(skills.length)} hint="Registered skills" tone="warning" icon={<Icon name="drafts" className="h-6 w-6" />} />
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.05fr_1.2fr]">
            <Card title={t("settings.priorityTitle")} description={t("settings.priorityDescription")}>
              <div className="grid gap-3 sm:grid-cols-2">
                <Link href="/settings/wechat" className="rounded-2xl border border-slate-200 p-4 transition hover:border-brand-200 hover:bg-brand-50/60">
                  <p className="text-sm font-semibold text-slate-900">{t("settings.wechatConfig")}</p>
                  <p className="mt-1 text-sm text-slate-500">{t("settings.wechatConfigDesc")}</p>
                </Link>
                <div className="rounded-2xl border border-slate-200 p-4">
                  <p className="text-sm font-semibold text-slate-900">{t("settings.notifications")}</p>
                  <p className="mt-1 text-sm text-slate-500">{t("settings.notificationsDesc")}</p>
                  <Badge tone="muted" className="mt-3">Gap</Badge>
                </div>
                <div className="rounded-2xl border border-slate-200 p-4">
                  <p className="text-sm font-semibold text-slate-900">{t("settings.billing")}</p>
                  <p className="mt-1 text-sm text-slate-500">{t("settings.billingDesc")}</p>
                  <Badge tone="muted" className="mt-3">Gap</Badge>
                </div>
                <div className="rounded-2xl border border-slate-200 p-4">
                  <p className="text-sm font-semibold text-slate-900">{t("settings.audit")}</p>
                  <p className="mt-1 text-sm text-slate-500">{t("settings.auditDesc")}</p>
                  <Badge tone="warning" className="mt-3">Partial</Badge>
                </div>
              </div>
            </Card>

            <Card title={t("settings.systemInfo")} description={t("settings.systemInfoDesc")}>
              <div className="grid gap-4 md:grid-cols-2">
                {[
                  ["App Env", String(configs.app_env ?? "unknown")],
                  ["App Debug", String(configs.app_debug ?? "unknown")],
                  ["App Port", String(configs.app_port ?? "unknown")],
                  ["Publish Enabled", String(configs.global_publish_enabled ?? "unknown")],
                  ["Emergency Stop", String(configs.global_emergency_stop ?? "unknown")],
                  ["Agent Timeout", String(configs.agent_timeout ?? "unknown")],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{label}</p>
                    <p className="mt-2 text-sm font-semibold text-slate-900">{value}</p>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          <Card title={t("settings.languageRegion")} description={t("settings.languageRegionDesc")}>
            <LanguageSwitcher />
          </Card>

          <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
            <Card title="Providers, Agents & Skills" description="Configuration inventory that already exists in the backend.">
              <div className="space-y-4">
                <Link href="/settings/llm-providers" className="flex items-center justify-between gap-3 rounded-2xl border border-slate-200 p-4 transition hover:border-brand-200 hover:bg-brand-50/60">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">LLM Providers</p>
                    <p className="mt-1 text-sm text-slate-500">The backend supports provider records and default provider switching.</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge tone={providers.length ? "success" : "muted"}>{formatNumber(providers.length)}</Badge>
                    <Button variant="secondary" size="sm">{t("settings.configure")}</Button>
                  </div>
                </Link>
                <div title="Image Asset Configuration" className="rounded-2xl border border-slate-200 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">Image Asset Configuration</p>
                      <p className="mt-1 text-sm leading-6 text-slate-500">
                        Preconfigure image generation provider, API key, base URL and model for draft image assets.
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button variant="secondary" onClick={() => void handleImageConnectionTest()} disabled={imageTestRunning} size="sm">
                        {imageTestRunning ? "Testing..." : "Test Connection"}
                      </Button>
                      <Button onClick={() => void saveImageGenerationConfig()} disabled={imageConfigSaving} size="sm">
                        {imageConfigSaving ? "Saving..." : "Save"}
                      </Button>
                    </div>
                  </div>
                  <div className="mt-4 grid gap-4">
                    <label className="flex items-start gap-3 rounded-2xl border border-slate-200 bg-slate-50/70 p-4 text-sm text-slate-600">
                      <input
                        type="checkbox"
                        checked={imageGenerationEnabled}
                        onChange={(event) => {
                          setImageGenerationEnabled(event.target.checked);
                          setImageConfigNotice(null);
                          setImageTestResult(null);
                        }}
                        className="mt-1 h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-200"
                        data-testid="image-generation-enabled"
                      />
                      <span>
                        <span className="block font-semibold text-slate-900">Enable AI image generation during post-process</span>
                        <span className="mt-1 block leading-5">
                          When enabled and an API key is configured, draft previews can call the selected image model. Leave off to use local fallback artwork only.
                        </span>
                      </span>
                    </label>
                    <div>
                      <label className="mb-2 block text-sm font-medium text-slate-700">Image Generation Provider</label>
                      <select
                        value={imageGenerationProvider}
                        onChange={(event) => handleImageProviderChange(event.target.value)}
                        className="h-11 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-900 shadow-sm outline-none transition focus:border-brand-300 focus:ring-4 focus:ring-brand-100"
                        data-testid="image-generation-provider"
                      >
                        {IMAGE_GENERATION_PROVIDER_PRESETS.map((preset) => (
                          <option key={preset.provider_id} value={preset.provider_id}>
                            {preset.name}
                          </option>
                        ))}
                      </select>
                      <p className="mt-2 text-xs leading-5 text-slate-500">
                        Credential reminder: {selectedImageProvider?.api_key_hint || "Provider-specific API key"}
                      </p>
                    </div>
                    <div>
                      <label className="mb-2 block text-sm font-medium text-slate-700">Image Generation API Key</label>
                      <Input
                        type="password"
                        value={imageGenerationApiKey}
                        onChange={(event) => {
                          setImageGenerationApiKey(event.target.value);
                          setImageConfigNotice(null);
                          setImageTestResult(null);
                        }}
                        placeholder={imageGenerationApiKeyHint ? `Configured (${imageGenerationApiKeyHint})` : "Enter image provider API key"}
                        data-testid="image-generation-api-key"
                      />
                      <p className="mt-2 text-xs leading-5 text-slate-500">
                        Stored as <span className="font-medium text-slate-700">image_generation_api_key</span>. Leave blank to keep the current key.
                      </p>
                    </div>
                    <div>
                      <label className="mb-2 block text-sm font-medium text-slate-700">Image Generation Base URL</label>
                      <Input
                        value={imageGenerationBaseUrl}
                        onChange={(event) => {
                          setImageGenerationBaseUrl(event.target.value);
                          setImageConfigNotice(null);
                          setImageTestResult(null);
                        }}
                        placeholder="https://api.example.com/v1/images/generations"
                        data-testid="image-generation-base-url"
                      />
                      <p className="mt-2 text-xs leading-5 text-slate-500">
                        Stored as <span className="font-medium text-slate-700">image_generation_base_url</span>.
                      </p>
                    </div>
                    <div>
                      <label className="mb-2 block text-sm font-medium text-slate-700">Image Generation Model</label>
                      <Input
                        value={imageGenerationModel}
                        onChange={(event) => {
                          setImageGenerationModel(event.target.value);
                          setImageConfigNotice(null);
                          setImageTestResult(null);
                        }}
                        placeholder="wan2.7-image"
                        data-testid="image-generation-model"
                      />
                      <p className="mt-2 text-xs leading-5 text-slate-500">
                        Stored as <span className="font-medium text-slate-700">image_generation_model</span>.
                      </p>
                    </div>
                  </div>
                  <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-5 text-amber-800">
                    Image search APIs are not wired yet. If we later add Unsplash/Pexels/Bing/SerpAPI-like image retrieval,
                    we will need the matching search API key and copyright policy before automatic fetching can run.
                  </div>
                  {imageConfigNotice ? (
                    <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                      {imageConfigNotice}
                    </div>
                  ) : null}
                  {imageTestResult ? (
                    <div
                      className={`mt-3 rounded-2xl border px-4 py-3 text-sm ${
                        imageTestResult.success
                          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                          : "border-rose-200 bg-rose-50 text-rose-700"
                      }`}
                    >
                      <p>{imageTestResult.message}</p>
                      {typeof imageTestResult.latency === "number" ? (
                        <p className="mt-1 text-xs opacity-80">Latency: {imageTestResult.latency} ms</p>
                      ) : null}
                    </div>
                  ) : null}
                </div>
                <Link href="/settings/agents" className="flex items-center justify-between gap-3 rounded-2xl border border-slate-200 p-4 transition hover:border-brand-200 hover:bg-brand-50/60">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">Agents</p>
                    <p className="mt-1 text-sm text-slate-500">These are the registered nodes in the six-agent workflow.</p>
                    <div className="mt-3 inline-flex items-center gap-2 rounded-xl border border-brand-200 bg-brand-50 px-3 py-1.5 text-xs font-medium text-brand-700">
                      <Icon name="arrowUpRight" className="h-3.5 w-3.5" />
                      Open Agent Configuration
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge tone={agents.length ? "success" : "muted"}>{formatNumber(agents.length)}</Badge>
                    <span className="inline-flex items-center rounded-xl border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700">
                      {t("settings.configure")}
                    </span>
                  </div>
                </Link>
                <Link href="/settings/skills" className="flex items-center justify-between gap-3 rounded-2xl border border-slate-200 p-4 transition hover:border-brand-200 hover:bg-brand-50/60">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">Skills</p>
                    <p className="mt-1 text-sm text-slate-500">Skill configuration is available, but the UI is consolidated into the main settings view for now.</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge tone={skills.length ? "success" : "muted"}>{formatNumber(skills.length)}</Badge>
                    <Button variant="secondary" size="sm">{t("settings.configure")}</Button>
                  </div>
                </Link>
              </div>
            </Card>

            <Card title={t("settings.coverage")} description={t("settings.coverageDesc")}>
              {accounts.length ? (
                <div className="space-y-3">
                  {accounts.slice(0, 8).map((account) => (
                    <Link key={account.account_id} href={`/settings/wechat/${account.account_id}`} className="flex items-center justify-between gap-3 rounded-2xl border border-slate-200 p-4 transition hover:border-brand-200 hover:bg-brand-50/60">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{account.name}</p>
                        <p className="mt-1 text-sm text-slate-500">{startCase(account.operation_mode)} mode</p>
                      </div>
                      <Button variant="secondary" size="sm">
                        {t("settings.configure")}
                      </Button>
                    </Link>
                  ))}
                </div>
              ) : (
                <EmptyState title={t("settings.accountsEmpty")} description={t("settings.accountsEmptyDesc")} />
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
