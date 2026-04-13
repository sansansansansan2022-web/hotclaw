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
  PageHeader,
  SkeletonRows,
  StatCard,
  Textarea,
} from "@/components/console/ui";
import { cn } from "@/lib/utils";
import { ApiError, deleteAgentConfig, getAgent, listAgents, updateAgentConfig, type AgentInfo } from "@/lib/api";

type NoticeTone = "success" | "danger" | "info";

interface NoticeState {
  tone: NoticeTone;
  message: string;
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

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [selected, setSelected] = useState<AgentInfo | null>(null);
  const [promptDraft, setPromptDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<NoticeState | null>(null);

  const customCount = agents.filter((agent) => agent.has_custom_prompt).length;

  async function loadAgentDetail(agentId: string) {
    setLoadingDetail(true);
    try {
      const detail = await getAgent(agentId);
      setSelected(detail);
      setPromptDraft(detail.prompt_template || detail.default_system_prompt || "");
      setEditing(false);
      setError(null);
    } catch (detailError) {
      setError(detailError instanceof Error ? detailError.message : "Unable to load agent detail.");
    } finally {
      setLoadingDetail(false);
    }
  }

  async function loadAgents(preferredAgentId?: string) {
    setLoading(true);
    try {
      const response = await listAgents();
      setAgents(response.agents);

      const nextAgentId = preferredAgentId || selected?.agent_id || response.agents[0]?.agent_id || null;

      if (nextAgentId) {
        await loadAgentDetail(nextAgentId);
      } else {
        setSelected(null);
        setPromptDraft("");
      }

      setError(null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load agents.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadAgents();
  }, []);

  async function handleSave() {
    if (!selected) return;

    const baselinePrompt = selected.prompt_template || selected.default_system_prompt || "";
    if (promptDraft === baselinePrompt) {
      setEditing(false);
      return;
    }

    setSaving(true);
    try {
      await updateAgentConfig(selected.agent_id, { prompt_template: promptDraft });
      await loadAgents(selected.agent_id);
      setNotice({ tone: "success", message: `Saved prompt changes for ${selected.name}.` });
    } catch (saveError) {
      const message = saveError instanceof ApiError ? saveError.message : "Unable to save agent configuration.";
      setNotice({ tone: "danger", message });
    } finally {
      setSaving(false);
    }
  }

  async function handleResetToDefault() {
    if (!selected) return;

    setSaving(true);
    try {
      await updateAgentConfig(selected.agent_id, { prompt_template: "" });
      await loadAgents(selected.agent_id);
      setNotice({ tone: "success", message: `${selected.name} is now using the default prompt again.` });
    } catch (resetError) {
      const message = resetError instanceof ApiError ? resetError.message : "Unable to reset this agent.";
      setNotice({ tone: "danger", message });
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteCustomConfig() {
    if (!selected) return;

    setSaving(true);
    try {
      await deleteAgentConfig(selected.agent_id);
      setDeleteOpen(false);
      await loadAgents(selected.agent_id);
      setNotice({ tone: "success", message: `Removed the custom configuration for ${selected.name}.` });
    } catch (deleteError) {
      const message = deleteError instanceof ApiError ? deleteError.message : "Unable to delete this custom configuration.";
      setNotice({ tone: "danger", message });
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppShell>
      <div className="space-y-8">
        <PageHeader
          eyebrow="Agent Runtime"
          title="Agents"
          description="Inspect registered agents, review their effective prompts, and customize the prompt layer without leaving the main console."
          actions={
            <Button variant="secondary" onClick={() => void loadAgents(selected?.agent_id)}>
              <Icon name="refresh" className="h-4 w-4" />
              Refresh
            </Button>
          }
        />

        {loading ? (
          <SkeletonRows rows={5} />
        ) : error ? (
          <ErrorState title="Agents failed to load" description={error} retry={() => void loadAgents(selected?.agent_id)} />
        ) : (
          <>
            <div className="grid gap-5 md:grid-cols-3">
              <StatCard
                label="Registered Agents"
                value={String(agents.length)}
                hint="All runtime agents discovered from the backend registry."
                tone="info"
                icon={<Icon name="workspace" className="h-6 w-6" />}
              />
              <StatCard
                label="Customized Prompts"
                value={String(customCount)}
                hint="Agents currently using a stored custom prompt."
                tone="warning"
                icon={<Icon name="edit" className="h-6 w-6" />}
              />
              <StatCard
                label="Default Prompts"
                value={String(Math.max(agents.length - customCount, 0))}
                hint="Agents still inheriting the default system prompt."
                tone="success"
                icon={<Icon name="check" className="h-6 w-6" />}
              />
            </div>

            <div className="grid gap-6 xl:grid-cols-[0.95fr_1.25fr]">
              <Card title="Registered Agents" description="Pick an agent to inspect its prompt and runtime metadata.">
                {agents.length ? (
                  <div className="space-y-3">
                    {agents.map((agent) => {
                      const active = selected?.agent_id === agent.agent_id;
                      return (
                        <button
                          key={agent.agent_id}
                          type="button"
                          onClick={() => void loadAgentDetail(agent.agent_id)}
                          className={cn(
                            "w-full rounded-2xl border p-4 text-left transition",
                            active
                              ? "border-brand-200 bg-brand-50"
                              : "border-slate-200 bg-white hover:border-brand-200 hover:bg-brand-50/50",
                          )}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="truncate text-sm font-semibold text-slate-900">{agent.name}</p>
                              <p className="mt-1 truncate text-xs text-slate-500">{agent.agent_id}</p>
                            </div>
                            <Badge tone={agent.has_custom_prompt ? "warning" : "muted"}>
                              {agent.has_custom_prompt ? "Custom" : "Default"}
                            </Badge>
                          </div>
                          <p className="mt-3 text-sm leading-6 text-slate-500">{agent.description}</p>
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <EmptyState
                    title="No agents found"
                    description="The backend did not return any agent registrations yet."
                  />
                )}
              </Card>

              <div className="space-y-6">
                <NoticeBanner notice={notice} />

                {loadingDetail ? (
                  <SkeletonRows rows={3} />
                ) : selected ? (
                  <>
                    <Card
                      title="Agent Overview"
                      description="The selected agent's effective runtime prompt and current configuration state."
                      action={
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge tone={selected.has_custom_prompt ? "warning" : "success"}>
                            {selected.has_custom_prompt ? "Custom Prompt" : "Default Prompt"}
                          </Badge>
                          <Badge tone="muted">{selected.status}</Badge>
                        </div>
                      }
                    >
                      <div className="grid gap-4 md:grid-cols-2">
                        <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Name</p>
                          <p className="mt-2 text-sm font-semibold text-slate-900">{selected.name}</p>
                          <p className="mt-1 text-sm text-slate-500">{selected.description}</p>
                        </div>
                        <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Agent ID</p>
                          <p className="mt-2 text-sm font-semibold text-slate-900">{selected.agent_id}</p>
                          <p className="mt-1 text-sm text-slate-500">Version {selected.version}</p>
                        </div>
                      </div>
                    </Card>

                    <Card
                      title="Prompt Configuration"
                      description="Edit the effective prompt text used by this agent. Saving creates or updates the stored custom prompt."
                      action={
                        <div className="flex flex-wrap gap-2">
                          {editing ? (
                            <>
                              <Button
                                variant="secondary"
                                onClick={() => {
                                  setEditing(false);
                                  setPromptDraft(selected.prompt_template || selected.default_system_prompt || "");
                                }}
                              >
                                Cancel
                              </Button>
                              <Button onClick={() => void handleSave()} disabled={saving}>
                                {saving ? "Saving..." : "Save Prompt"}
                              </Button>
                            </>
                          ) : (
                            <>
                              {selected.has_custom_prompt ? (
                                <Button variant="secondary" onClick={() => void handleResetToDefault()} disabled={saving}>
                                  Reset to Default
                                </Button>
                              ) : null}
                              <Button variant="secondary" onClick={() => setEditing(true)}>
                                <Icon name="edit" className="h-4 w-4" />
                                Edit Prompt
                              </Button>
                            </>
                          )}
                        </div>
                      }
                    >
                      {editing ? (
                        <Textarea
                          value={promptDraft}
                          onChange={(event) => setPromptDraft(event.target.value)}
                          className="min-h-[320px] font-mono"
                          placeholder="Enter the prompt text used by this agent."
                        />
                      ) : (
                        <pre className="overflow-auto rounded-2xl border border-slate-200 bg-slate-50/70 p-4 text-sm leading-6 text-slate-700">
                          {promptDraft || "No prompt is available for this agent."}
                        </pre>
                      )}
                    </Card>

                    <div className="grid gap-6 md:grid-cols-2">
                      <Card title="Model Configuration" description="Structured model configuration persisted for this agent, if any.">
                        <pre className="overflow-auto rounded-2xl border border-slate-200 bg-slate-50/70 p-4 text-xs leading-6 text-slate-700">
                          {selected.model_config_data
                            ? JSON.stringify(selected.model_config_data, null, 2)
                            : "Using the global default model configuration."}
                        </pre>
                      </Card>

                      <Card
                        title="Retry Configuration"
                        description="Retry settings applied specifically to this agent when the backend stores them."
                        action={
                          selected.has_custom_prompt ? (
                            <Button variant="destructive" onClick={() => setDeleteOpen(true)} disabled={saving}>
                              Delete Custom Config
                            </Button>
                          ) : null
                        }
                      >
                        <pre className="overflow-auto rounded-2xl border border-slate-200 bg-slate-50/70 p-4 text-xs leading-6 text-slate-700">
                          {selected.retry_config
                            ? JSON.stringify(selected.retry_config, null, 2)
                            : "No retry override is stored for this agent."}
                        </pre>
                      </Card>
                    </div>
                  </>
                ) : (
                  <Card title="Agent Detail" description="Choose an agent from the list to inspect or customize it.">
                    <EmptyState
                      title="Select an agent"
                      description="Pick any registered agent on the left to review its effective prompt and configuration details."
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
        title="Delete Custom Agent Configuration"
        description={`This removes the stored custom configuration for ${selected?.name ?? "the selected agent"} and reverts it to the default prompt.`}
        confirmLabel="Delete Custom Config"
        tone="danger"
        onConfirm={() => void handleDeleteCustomConfig()}
        onCancel={() => setDeleteOpen(false)}
      />
    </AppShell>
  );
}
