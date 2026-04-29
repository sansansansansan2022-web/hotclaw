"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/console/layout";
import { Icon } from "@/components/console/icons";
import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Input,
  PageHeader,
  SkeletonRows,
  StatCard,
  Textarea,
} from "@/components/console/ui";
import { cn } from "@/lib/utils";
import {
  LLM_PROVIDER_TEMPLATES,
  createLLMProvider,
  deleteLLMProvider,
  listLLMProviders,
  setDefaultLLMProvider,
  testLLMProvider,
  updateLLMProvider,
  type LLMProviderInfo,
} from "@/lib/api";

type ProviderMode = "view" | "edit" | "create";
type NoticeTone = "success" | "danger" | "info";

interface ProviderFormState {
  provider_id: string;
  name: string;
  description: string;
  api_key: string;
  base_url: string;
  default_model: string;
  supported_models: string;
  timeout: string;
  is_enabled: boolean;
  is_default: boolean;
}

interface NoticeState {
  tone: NoticeTone;
  message: string;
}

interface TestResultState {
  success: boolean;
  message: string;
  latency?: number;
}

const emptyForm: ProviderFormState = {
  provider_id: "",
  name: "",
  description: "",
  api_key: "",
  base_url: "",
  default_model: "",
  supported_models: "",
  timeout: "60",
  is_enabled: true,
  is_default: false,
};

function providerToForm(provider: LLMProviderInfo): ProviderFormState {
  return {
    provider_id: provider.provider_id,
    name: provider.name,
    description: provider.description || "",
    api_key: provider.api_key || "",
    base_url: provider.base_url || "",
    default_model: provider.default_model || "",
    supported_models: (provider.supported_models || []).join(", "),
    timeout: String(provider.timeout || 60),
    is_enabled: provider.is_enabled,
    is_default: provider.is_default,
  };
}

function NoticeBanner({ notice }: { notice: NoticeState | null }) {
  if (!notice) return null;

  const className =
    notice.tone === "success"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : notice.tone === "danger"
        ? "border-rose-200 bg-rose-50 text-rose-700"
        : "border-sky-200 bg-sky-50 text-sky-700";

  return <div className={cn("rounded-2xl border px-4 py-3 text-sm", className)}>{notice.message}</div>;
}

export default function LLMProvidersPage() {
  const [providers, setProviders] = useState<LLMProviderInfo[]>([]);
  const [selected, setSelected] = useState<LLMProviderInfo | null>(null);
  const [form, setForm] = useState<ProviderFormState>(emptyForm);
  const [mode, setMode] = useState<ProviderMode>("view");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<NoticeState | null>(null);
  const [testResult, setTestResult] = useState<TestResultState | null>(null);

  const enabledCount = providers.filter((provider) => provider.is_enabled).length;
  const defaultProvider = providers.find((provider) => provider.is_default) || null;
  const isEditing = mode === "edit" || mode === "create";

  function setField<K extends keyof ProviderFormState>(key: K, value: ProviderFormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function loadProviders(preferredProviderId?: string) {
    setLoading(true);
    try {
      const response = await listLLMProviders();
      setProviders(response);

      const nextSelected =
        response.find((provider) => provider.provider_id === preferredProviderId) ||
        response.find((provider) => provider.provider_id === selected?.provider_id) ||
        response[0] ||
        null;

      if (nextSelected) {
        setSelected(nextSelected);
        setForm(providerToForm(nextSelected));
        setMode("view");
      } else {
        setSelected(null);
        setForm(emptyForm);
        setMode("view");
      }

      setError(null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load LLM providers.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadProviders();
  }, []);

  function handleSelect(provider: LLMProviderInfo) {
    setSelected(provider);
    setForm(providerToForm(provider));
    setMode("view");
    setNotice(null);
    setTestResult(null);
  }

  function handleCreate() {
    setSelected(null);
    setForm(emptyForm);
    setMode("create");
    setNotice(null);
    setTestResult(null);
  }

  function applyTemplate(providerId: string) {
    const template = LLM_PROVIDER_TEMPLATES.find((item) => item.provider_id === providerId);
    if (!template) return;

    setForm((current) => ({
      ...current,
      provider_id: template.provider_id,
      name: template.name,
      description: template.description,
      base_url: template.base_url,
      default_model: template.default_model,
      supported_models: template.supported_models.join(", "),
    }));
  }

  function parseSupportedModels() {
    return form.supported_models
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  async function handleSave() {
    if (!form.provider_id.trim() || !form.name.trim()) {
      setNotice({ tone: "danger", message: "Provider ID and display name are required." });
      return;
    }

    setSaving(true);
    try {
      const payload = {
        provider_id: form.provider_id.trim(),
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        api_key: form.api_key.trim() || undefined,
        base_url: form.base_url.trim() || undefined,
        default_model: form.default_model.trim() || undefined,
        supported_models: parseSupportedModels(),
        timeout: Number(form.timeout) || 60,
        is_enabled: form.is_enabled,
        is_default: form.is_default,
      };

      if (mode === "create") {
        await createLLMProvider(payload);
        await loadProviders(payload.provider_id);
        setNotice({ tone: "success", message: `Created provider ${payload.name}.` });
      } else if (selected) {
        await updateLLMProvider(selected.provider_id, payload);
        await loadProviders(selected.provider_id);
        setNotice({ tone: "success", message: `Saved changes for ${payload.name}.` });
      }
    } catch (saveError) {
      setNotice({
        tone: "danger",
        message: saveError instanceof Error ? saveError.message : "Unable to save this provider.",
      });
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    if (!form.api_key.trim()) {
      setTestResult({ success: false, message: "Enter an API key before testing the provider." });
      return;
    }

    setTesting(true);
    setTestResult(null);
    try {
      const result = await testLLMProvider({
        provider_id: form.provider_id.trim(),
        api_key: form.api_key.trim(),
        base_url: form.base_url.trim() || undefined,
        model: form.default_model.trim() || undefined,
      });

      if (result.success) {
        setTestResult({
          success: true,
          message: result.response_preview || "Connection test succeeded.",
          latency: result.latency_ms,
        });
      } else {
        setTestResult({
          success: false,
          message: result.error_message || "Connection test failed.",
        });
      }
    } catch (testError) {
      setTestResult({
        success: false,
        message: testError instanceof Error ? testError.message : "Unable to test this provider.",
      });
    } finally {
      setTesting(false);
    }
  }

  async function handleSetDefault() {
    if (!selected) return;

    try {
      await setDefaultLLMProvider(selected.provider_id);
      await loadProviders(selected.provider_id);
      setNotice({ tone: "success", message: `${selected.name} is now the default provider.` });
    } catch (defaultError) {
      setNotice({
        tone: "danger",
        message: defaultError instanceof Error ? defaultError.message : "Unable to change the default provider.",
      });
    }
  }

  async function handleDelete() {
    if (!selected) return;

    setSaving(true);
    try {
      await deleteLLMProvider(selected.provider_id);
      setDeleteOpen(false);
      await loadProviders();
      setNotice({ tone: "success", message: `Deleted provider ${selected.name}.` });
    } catch (deleteError) {
      setNotice({
        tone: "danger",
        message: deleteError instanceof Error ? deleteError.message : "Unable to delete this provider.",
      });
    } finally {
      setSaving(false);
    }
  }

  function handleCancel() {
    if (selected) {
      setForm(providerToForm(selected));
      setMode("view");
    } else {
      const firstProvider = providers[0];
      if (firstProvider) {
        handleSelect(firstProvider);
      } else {
        setForm(emptyForm);
        setMode("view");
      }
    }
    setTestResult(null);
  }

  return (
    <AppShell>
      <div className="space-y-8">
        <PageHeader
          eyebrow="Provider Setup"
          title="LLM Providers"
          description="Manage provider records, test connectivity, and control which model provider becomes the runtime default."
          actions={
            <>
              <Button variant="secondary" onClick={() => void loadProviders(selected?.provider_id)}>
                <Icon name="refresh" className="h-4 w-4" />
                Refresh
              </Button>
              <Button onClick={handleCreate}>
                <Icon name="plus" className="h-4 w-4" />
                New Provider
              </Button>
            </>
          }
        />

        {loading ? (
          <SkeletonRows rows={5} />
        ) : error ? (
          <ErrorState title="Providers failed to load" description={error} retry={() => void loadProviders(selected?.provider_id)} />
        ) : (
          <>
            <div className="grid gap-5 md:grid-cols-3">
              <StatCard
                label="Configured Providers"
                value={String(providers.length)}
                hint="All provider records currently stored in the backend."
                tone="info"
                icon={<Icon name="settings" className="h-6 w-6" />}
              />
              <StatCard
                label="Enabled Providers"
                value={String(enabledCount)}
                hint="Providers currently allowed to serve model traffic."
                tone="success"
                icon={<Icon name="check" className="h-6 w-6" />}
              />
              <StatCard
                label="Default Provider"
                value={defaultProvider?.name || "None"}
                hint="The provider the backend will prefer by default."
                tone="warning"
                icon={<Icon name="workspace" className="h-6 w-6" />}
              />
            </div>

            <div className="grid gap-6 xl:grid-cols-[0.95fr_1.25fr]">
              <Card title="Available Providers" description="Select a provider to review or edit its configuration.">
                {providers.length ? (
                  <div className="space-y-3">
                    {providers.map((provider) => {
                      const active = selected?.provider_id === provider.provider_id && mode !== "create";
                      return (
                        <button
                          key={provider.provider_id}
                          type="button"
                          onClick={() => handleSelect(provider)}
                          className={cn(
                            "w-full rounded-2xl border p-4 text-left transition",
                            active
                              ? "border-brand-200 bg-brand-50"
                              : "border-slate-200 bg-white hover:border-brand-200 hover:bg-brand-50/50",
                          )}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="truncate text-sm font-semibold text-slate-900">{provider.name}</p>
                              <p className="mt-1 truncate text-xs text-slate-500">{provider.provider_id}</p>
                            </div>
                            <div className="flex flex-wrap justify-end gap-2">
                              {provider.is_default ? <Badge tone="warning">Default</Badge> : null}
                              <Badge tone={provider.is_enabled ? "success" : "muted"}>
                                {provider.is_enabled ? "Enabled" : "Disabled"}
                              </Badge>
                            </div>
                          </div>
                          <p className="mt-3 text-sm leading-6 text-slate-500">
                            {provider.description || "No provider description is stored yet."}
                          </p>
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <EmptyState
                    title="No providers yet"
                    description="Create the first provider record to configure model access for the console."
                    action={
                      <Button onClick={handleCreate}>
                        <Icon name="plus" className="h-4 w-4" />
                        Create Provider
                      </Button>
                    }
                  />
                )}
              </Card>

              <div className="space-y-6">
                <NoticeBanner notice={notice} />

                {mode === "create" ? (
                  <Card title="Provider Templates" description="Start from a known provider template and then adjust the details below.">
                    <div className="grid gap-3 sm:grid-cols-2">
                      {LLM_PROVIDER_TEMPLATES.map((template) => (
                        <button
                          key={template.provider_id}
                          type="button"
                          onClick={() => applyTemplate(template.provider_id)}
                          className={cn(
                            "rounded-2xl border p-4 text-left transition",
                            form.provider_id === template.provider_id
                              ? "border-brand-200 bg-brand-50"
                              : "border-slate-200 bg-slate-50/50 hover:border-brand-200 hover:bg-brand-50/60",
                          )}
                        >
                          <p className="text-sm font-semibold text-slate-900">{template.name}</p>
                          <p className="mt-2 text-sm leading-6 text-slate-500">{template.description}</p>
                        </button>
                      ))}
                    </div>
                  </Card>
                ) : null}

                {selected || mode === "create" ? (
                  <>
                    <Card
                      title={mode === "create" ? "New Provider" : "Provider Configuration"}
                      description="Use the same editing flow as the WeChat settings page: review the current state on the right, then edit and save."
                      action={
                        <div className="flex flex-wrap gap-2">
                          {isEditing ? (
                            <>
                              <Button variant="secondary" onClick={handleCancel}>
                                Cancel
                              </Button>
                              <Button variant="secondary" onClick={() => void handleTest()} disabled={testing}>
                                {testing ? "Testing..." : "Test Connection"}
                              </Button>
                              <Button onClick={() => void handleSave()} disabled={saving}>
                                {saving ? "Saving..." : mode === "create" ? "Create Provider" : "Save Changes"}
                              </Button>
                            </>
                          ) : (
                            <>
                              {selected ? (
                                <Button variant="secondary" onClick={() => void handleTest()} disabled={testing}>
                                  {testing ? "Testing..." : "Test Connection"}
                                </Button>
                              ) : null}
                              {selected && !selected.is_default ? (
                                <Button variant="secondary" onClick={() => void handleSetDefault()}>
                                  Set as Default
                                </Button>
                              ) : null}
                              {selected ? (
                                <Button variant="secondary" onClick={() => setMode("edit")}>
                                  <Icon name="edit" className="h-4 w-4" />
                                  Edit Provider
                                </Button>
                              ) : null}
                            </>
                          )}
                        </div>
                      }
                    >
                      <div className="grid gap-5">
                        <div className="grid gap-5 md:grid-cols-2">
                          <div>
                            <label className="mb-2 block text-sm font-medium text-slate-700">Provider ID</label>
                            <Input
                              value={form.provider_id}
                              onChange={(event) => setField("provider_id", event.target.value)}
                              disabled={mode !== "create"}
                              placeholder="openai"
                            />
                          </div>
                          <div>
                            <label className="mb-2 block text-sm font-medium text-slate-700">Display Name</label>
                            <Input
                              value={form.name}
                              onChange={(event) => setField("name", event.target.value)}
                              disabled={!isEditing}
                              placeholder="OpenAI"
                            />
                          </div>
                        </div>

                        <div>
                          <label className="mb-2 block text-sm font-medium text-slate-700">Description</label>
                          <Textarea
                            value={form.description}
                            onChange={(event) => setField("description", event.target.value)}
                            disabled={!isEditing}
                            className="min-h-24"
                            placeholder="Describe the provider, endpoint role, or expected model family."
                          />
                        </div>

                        <div className="grid gap-5 md:grid-cols-2">
                          <div>
                            <label className="mb-2 block text-sm font-medium text-slate-700">API Key</label>
                            <Input
                              type="password"
                              value={form.api_key}
                              onChange={(event) => setField("api_key", event.target.value)}
                              disabled={!isEditing}
                              placeholder="Enter the provider API key"
                            />
                          </div>
                          <div>
                            <label className="mb-2 block text-sm font-medium text-slate-700">Base URL</label>
                            <Input
                              value={form.base_url}
                              onChange={(event) => setField("base_url", event.target.value)}
                              disabled={!isEditing}
                              placeholder="https://api.openai.com/v1"
                            />
                          </div>
                        </div>

                        <div className="grid gap-5 md:grid-cols-3">
                          <div>
                            <label className="mb-2 block text-sm font-medium text-slate-700">Default Model</label>
                            <Input
                              value={form.default_model}
                              onChange={(event) => setField("default_model", event.target.value)}
                              disabled={!isEditing}
                              placeholder="gpt-4o-mini"
                            />
                          </div>
                          <div>
                            <label className="mb-2 block text-sm font-medium text-slate-700">Timeout Seconds</label>
                            <Input
                              type="number"
                              value={form.timeout}
                              onChange={(event) => setField("timeout", event.target.value)}
                              disabled={!isEditing}
                              min={5}
                              max={300}
                            />
                          </div>
                          <div>
                            <label className="mb-2 block text-sm font-medium text-slate-700">Supported Models</label>
                            <Input
                              value={form.supported_models}
                              onChange={(event) => setField("supported_models", event.target.value)}
                              disabled={!isEditing}
                              placeholder="Comma-separated model IDs"
                            />
                          </div>
                        </div>

                        <div className="grid gap-4 md:grid-cols-2">
                          <label className="flex items-center justify-between rounded-2xl border border-slate-200 p-4">
                            <span>
                              <span className="block text-sm font-medium text-slate-900">Enabled</span>
                              <span className="text-sm text-slate-500">Allow this provider to be used at runtime.</span>
                            </span>
                            <input
                              type="checkbox"
                              checked={form.is_enabled}
                              onChange={(event) => setField("is_enabled", event.target.checked)}
                              disabled={!isEditing}
                            />
                          </label>
                          <label className="flex items-center justify-between rounded-2xl border border-slate-200 p-4">
                            <span>
                              <span className="block text-sm font-medium text-slate-900">Default Provider</span>
                              <span className="text-sm text-slate-500">Mark this provider as the default backend choice.</span>
                            </span>
                            <input
                              type="checkbox"
                              checked={form.is_default}
                              onChange={(event) => setField("is_default", event.target.checked)}
                              disabled={!isEditing}
                            />
                          </label>
                        </div>
                      </div>
                    </Card>

                    {selected ? (
                      <div className="grid gap-6 md:grid-cols-2">
                        <Card title="Current Status" description="A compact runtime summary for the selected provider.">
                          <div className="grid gap-4 text-sm text-slate-600">
                            <div className="flex items-center justify-between gap-4">
                              <span className="text-slate-500">Provider</span>
                              <span className="font-medium text-slate-900">{selected.name}</span>
                            </div>
                            <div className="flex items-center justify-between gap-4">
                              <span className="text-slate-500">Default Model</span>
                              <span className="font-medium text-slate-900">{selected.default_model || "Not set"}</span>
                            </div>
                            <div className="flex items-center justify-between gap-4">
                              <span className="text-slate-500">Enabled</span>
                              <Badge tone={selected.is_enabled ? "success" : "muted"}>
                                {selected.is_enabled ? "Yes" : "No"}
                              </Badge>
                            </div>
                            <div className="flex items-center justify-between gap-4">
                              <span className="text-slate-500">Default</span>
                              <Badge tone={selected.is_default ? "warning" : "muted"}>
                                {selected.is_default ? "Default" : "Secondary"}
                              </Badge>
                            </div>
                            <div className="flex items-center justify-between gap-4">
                              <span className="text-slate-500">Last Test</span>
                              <Badge
                                tone={
                                  selected.test_status === "success"
                                    ? "success"
                                    : selected.test_status === "failed"
                                      ? "danger"
                                      : "muted"
                                }
                              >
                                {selected.test_status || "Unknown"}
                              </Badge>
                            </div>
                          </div>
                        </Card>

                        <Card
                          title="Connection Feedback"
                          description="Latest test feedback or provider-level maintenance actions."
                          action={
                            selected ? (
                              <Button variant="destructive" onClick={() => setDeleteOpen(true)} disabled={saving}>
                                Delete Provider
                              </Button>
                            ) : null
                          }
                        >
                          {testResult ? (
                            <div
                              className={cn(
                                "rounded-2xl border px-4 py-3 text-sm",
                                testResult.success
                                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                                  : "border-rose-200 bg-rose-50 text-rose-700",
                              )}
                            >
                              <p>{testResult.message}</p>
                              {typeof testResult.latency === "number" ? (
                                <p className="mt-1 text-xs opacity-80">Latency: {testResult.latency} ms</p>
                              ) : null}
                            </div>
                          ) : (
                            <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 text-sm text-slate-500">
                              {selected.test_message || "No recent test feedback is available for this provider yet."}
                            </div>
                          )}
                        </Card>
                      </div>
                    ) : null}
                  </>
                ) : (
                  <Card title="Provider Configuration" description="Create or select a provider to work with.">
                    <EmptyState
                      title="Choose a provider"
                      description="Pick an existing provider from the list or create a new one to start editing."
                    />
                  </Card>
                )}
              </div>
            </div>
          </>
        )}
      </div>

      <ConfirmDialog
        open={deleteOpen}
        title="Delete Provider"
        description={`This permanently removes ${selected?.name ?? "the selected provider"} from the backend configuration list.`}
        confirmLabel="Delete Provider"
        tone="danger"
        onConfirm={() => void handleDelete()}
        onCancel={() => setDeleteOpen(false)}
      />
    </AppShell>
  );
}
