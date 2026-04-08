"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { getAccount, getApiOriginDebugInfo, getPendingDraftCount, listAccountTasks, listDrafts, runAccount } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { formatDateTime, formatDuration, formatNumber, truncate } from "@/lib/utils";
import type { AccountDetail, DraftSummary, TaskSummary } from "@/types";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  SkeletonRows,
  StatCard,
  Table,
} from "@/components/console/ui";
import { Icon } from "@/components/console/icons";
import { useAppStore } from "@/store/appStore";

function taskTone(status: string | null): "success" | "warning" | "danger" | "muted" {
  if (status === "completed") return "success";
  if (status === "running") return "warning";
  if (status === "failed") return "danger";
  return "muted";
}

function draftTone(status: string): "brand" | "success" | "warning" | "danger" | "muted" {
  if (status === "approved" || status === "published") return "success";
  if (status === "pending_review") return "warning";
  if (status === "rejected" || status === "discarded") return "danger";
  return "muted";
}

interface AccountWorkspaceState {
  account: AccountDetail;
  tasks: TaskSummary[];
  drafts: DraftSummary[];
  pendingReviewCount: number;
  filteredOutTaskCount: number;
  filteredOutDraftCount: number;
}

export function AccountWorkspacePage({ accountId }: { accountId: string }) {
  const { operationModeLabel, taskStatusLabel, draftStatusLabel, publishStatusLabel } = useI18n();
  const router = useRouter();
  const pushToast = useAppStore((state) => state.pushToast);
  const [data, setData] = useState<AccountWorkspaceState | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);

      const [account, tasksRes, draftsRes, pendingRes] = await Promise.all([
        getAccount(accountId),
        listAccountTasks(accountId, 1, 8),
        listDrafts(1, 8, { account_id: accountId }),
        getPendingDraftCount(accountId).catch(() => ({ count: 0 })),
      ]);

      const scopedTasks = tasksRes.tasks.filter((task) => task.account_id === accountId);
      const filteredOutTaskCount = tasksRes.tasks.length - scopedTasks.length;
      const scopedDrafts = draftsRes.drafts.filter((draft) => draft.account_id === accountId);
      const filteredOutDraftCount = draftsRes.drafts.length - scopedDrafts.length;

      if (process.env.NODE_ENV !== "production" && typeof window !== "undefined") {
        const apiInfo = getApiOriginDebugInfo();
        console.info("[HotClaw][account-workspace] load", {
          accountId,
          apiOrigin: apiInfo.origin || "/api",
          apiSource: apiInfo.source,
          taskCount: scopedTasks.length,
          draftCount: scopedDrafts.length,
          filteredOutTaskCount,
          filteredOutDraftCount,
        });

        if (filteredOutTaskCount || filteredOutDraftCount) {
          console.warn("[HotClaw][account-workspace] filtered cross-account records", {
            accountId,
            filteredOutTaskCount,
            filteredOutDraftCount,
          });
        }
      }

      setData({
        account,
        tasks: scopedTasks,
        drafts: scopedDrafts,
        pendingReviewCount: pendingRes.count,
        filteredOutTaskCount,
        filteredOutDraftCount,
      });
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load account workspace.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [accountId]);

  const runNow = async () => {
    try {
      setRunning(true);

      if (process.env.NODE_ENV !== "production" && typeof window !== "undefined") {
        console.info("[HotClaw][account-workspace] run-click", { accountId });
      }

      const created = await runAccount(accountId);
      pushToast({
        tone: "success",
        title: "Account run queued",
        message: `Task ${created.task_id} started in this account workspace.`,
      });
      router.push(`/task/${created.task_id}`);
    } catch (runError) {
      pushToast({
        tone: "danger",
        title: "Run failed",
        message: runError instanceof Error ? runError.message : "Unexpected error.",
      });
    } finally {
      setRunning(false);
    }
  };

  const pendingDrafts = useMemo(
    () => (data?.drafts ?? []).filter((draft) => draft.draft_status === "pending_review").slice(0, 6),
    [data],
  );

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Account Workspace"
        title={data?.account.name || "Account Workspace"}
        description="Run this account, inspect this account's tasks and drafts, and keep the whole operator path anchored to the current account."
        actions={
          <>
            <Link href={`/accounts/${accountId}`}>
              <Button variant="secondary">Back to Account</Button>
            </Link>
            <Button onClick={() => void runNow()} disabled={running}>
              <Icon name="play" className="h-4 w-4" />
              {running ? "Running..." : "Run Now"}
            </Button>
          </>
        }
      />

      {loading ? (
        <SkeletonRows rows={6} />
      ) : error ? (
        <ErrorState title="Account workspace failed to load" description={error} retry={() => void load()} />
      ) : data ? (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">Current Account Workspace</Badge>
            <Badge tone="muted">{data.account.name}</Badge>
            <Badge tone="muted">{accountId}</Badge>
          </div>

          {data.filteredOutTaskCount || data.filteredOutDraftCount ? (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              {`Filtered out records that do not belong to this account: ${data.filteredOutTaskCount} task(s), ${data.filteredOutDraftCount} draft(s).`}
            </div>
          ) : null}

          <div className="grid gap-5 md:grid-cols-4">
            <StatCard
              label="Operation Mode"
              value={operationModeLabel(data.account.operation_mode)}
              hint="Backend operation mode for this account"
              tone="brand"
              icon={<Icon name="workspace" className="h-6 w-6" />}
            />
            <StatCard
              label="Account Tasks"
              value={formatNumber(data.tasks.length)}
              hint="Counts only tasks returned for this account"
              tone="info"
              icon={<Icon name="history" className="h-6 w-6" />}
            />
            <StatCard
              label="Pending Review"
              value={formatNumber(data.pendingReviewCount)}
              hint="Only drafts awaiting action for this account"
              tone="warning"
              icon={<Icon name="drafts" className="h-6 w-6" />}
            />
            <StatCard
              label="Last Run Status"
              value={taskStatusLabel(data.account.last_run_status)}
              hint={data.account.last_error_message || "Latest runtime signal for this account"}
              tone={taskTone(data.account.last_run_status)}
              icon={<Icon name="dashboard" className="h-6 w-6" />}
            />
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.1fr_0.95fr]">
            <Card
              title="Account Context"
              description="Keep the account identity and positioning visible so this page cannot be mistaken for a global task center."
            >
              <div className="space-y-5">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Account Identity</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Badge tone="brand">{data.account.name}</Badge>
                    <Badge tone="muted">{accountId}</Badge>
                  </div>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Positioning</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-slate-600">{data.account.positioning}</p>
                </div>
                <div className="grid gap-5 md:grid-cols-2">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Audience</p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{data.account.audience || "Not set"}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Tone & Style</p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{data.account.tone_style || "Not set"}</p>
                  </div>
                </div>
                <div className="grid gap-5 md:grid-cols-2">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Cadence</p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">
                      {data.account.posting_frequency
                        ? `${data.account.posting_frequency}${data.account.posting_time ? ` @ ${data.account.posting_time}` : ""}`
                        : "Not scheduled"}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Runtime Flags</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Badge tone={data.account.is_active ? "success" : "muted"}>{data.account.is_active ? "Account Active" : "Account Paused"}</Badge>
                      <Badge tone={data.account.auto_run_enabled ? "success" : "muted"}>{data.account.auto_run_enabled ? "Auto-run" : "Manual Run"}</Badge>
                      <Badge tone={data.account.auto_publish_enabled ? "success" : "muted"}>{data.account.auto_publish_enabled ? "Auto-publish" : "Manual Publish"}</Badge>
                    </div>
                  </div>
                </div>
              </div>
            </Card>

            <Card
              title="Operations & Assets"
              description="Every link stays in the current account context instead of routing operators back through the global workspace."
            >
              <div className="grid gap-4 md:grid-cols-2">
                {[
                  {
                    href: `/accounts/${accountId}/workspace`,
                    title: "Account Workspace",
                    desc: "Run tasks and inspect queues inside this account context.",
                  },
                  {
                    href: `/drafts?account_id=${accountId}`,
                    title: "Account Drafts",
                    desc: "Open review and publish drafts that belong to this account only.",
                  },
                  {
                    href: `/tasks/history?account_id=${accountId}`,
                    title: "Account Tasks",
                    desc: "View only task runs created for this account.",
                  },
                  {
                    href: "/publish-logs",
                    title: "Publish Logs",
                    desc: "Inspect publish attempts and failures linked to this account's drafts.",
                  },
                  {
                    href: `/accounts/${accountId}/memory`,
                    title: "Content Memory",
                    desc: "Review historical content memories accumulated for this account.",
                  },
                  {
                    href: `/accounts/${accountId}/style-profile`,
                    title: "Style Profile",
                    desc: "Inspect tone, structure and banned-pattern style assets.",
                  },
                ].map((item) => (
                  <Link key={item.href} href={item.href} className="rounded-2xl border border-slate-200 p-4 transition hover:border-brand-200 hover:bg-brand-50/60">
                    <p className="text-sm font-semibold text-slate-900">{item.title}</p>
                    <p className="mt-1 text-sm leading-6 text-slate-500">{item.desc}</p>
                  </Link>
                ))}
              </div>
            </Card>
          </div>

          <Card
            title="This Account's Tasks"
            description="Only task runs belonging to this account are rendered here. Any cross-account records are filtered out."
          >
            {data.tasks.length ? (
              <Table columns={["Task", "Status", "Created", "Duration", "Action"]}>
                {data.tasks.map((task) => (
                  <tr key={task.task_id}>
                    <td className="px-5 py-4">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{task.task_id}</p>
                        <div className="mt-1 flex flex-wrap gap-2">
                          <Badge tone="brand">Account Task</Badge>
                          <Badge tone="muted">{task.account_name || accountId}</Badge>
                        </div>
                        <p className="mt-2 text-sm text-slate-500">{truncate(task.positioning_summary, 100)}</p>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <Badge tone={taskTone(task.status)}>{taskStatusLabel(task.status)}</Badge>
                    </td>
                    <td className="px-5 py-4 text-sm text-slate-600">{formatDateTime(task.created_at)}</td>
                    <td className="px-5 py-4 text-sm text-slate-600">{formatDuration(task.elapsed_seconds)}</td>
                    <td className="px-5 py-4">
                      <Link href={`/task/${task.task_id}`}>
                        <Button variant="secondary" size="sm">
                          Inspect
                        </Button>
                      </Link>
                    </td>
                  </tr>
                ))}
              </Table>
            ) : (
              <EmptyState
                title="No account tasks yet"
                description="Start this account from here and its task history will accumulate in this workspace."
              />
            )}
          </Card>

          <Card
            title="Pending Review Drafts"
            description="Only drafts belonging to this account and still needing operator action appear here."
          >
            {pendingDrafts.length ? (
              <Table columns={["Title", "Draft Status", "Publish Status", "Updated", "Action"]}>
                {pendingDrafts.map((draft) => (
                  <tr key={draft.id}>
                    <td className="px-5 py-4">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{draft.title}</p>
                        <div className="mt-1 flex flex-wrap gap-2">
                          <Badge tone="brand">Account Draft</Badge>
                          <Badge tone="muted">{accountId}</Badge>
                        </div>
                        <p className="mt-2 text-sm text-slate-500">{truncate(draft.selected_topic, 100) || "No selected topic snapshot"}</p>
                      </div>
                    </td>
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
                          Open Draft
                        </Button>
                      </Link>
                    </td>
                  </tr>
                ))}
              </Table>
            ) : (
              <EmptyState
                title="No pending review drafts"
                description="This account has no pending review drafts right now. You can still open the account draft center for the full list."
                action={
                  <Link href={`/drafts?account_id=${accountId}`}>
                    <Button>Open Account Drafts</Button>
                  </Link>
                }
              />
            )}
          </Card>
        </>
      ) : null}
    </div>
  );
}
