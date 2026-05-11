"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { LanguageSwitcher } from "@/components/console/language-switcher";
import {
  getSettingsSystemConfigs,
  listAccounts,
  listSettingsAgents,
  listSettingsLLMProviders,
  listSettingsSkills,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { formatNumber, startCase } from "@/lib/utils";
import type { AccountSummary, AgentInfo, LLMProviderInfo, SkillInfo, SystemConfigMap } from "@/types";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, SkeletonRows, StatCard } from "@/components/console/ui";
import { Icon } from "@/components/console/icons";

export function SettingsPage() {
  const { t } = useI18n();
  const [configs, setConfigs] = useState<SystemConfigMap>({});
  const [providers, setProviders] = useState<LLMProviderInfo[]>([]);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [accounts, setAccounts] = useState<AccountSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      const [configsRes, providersRes, agentsRes, skillsRes, accountsRes] = await Promise.all([
        getSettingsSystemConfigs().catch(() => ({})),
        listSettingsLLMProviders().catch(() => []),
        listSettingsAgents().catch(() => ({ agents: [] })),
        listSettingsSkills().catch(() => ({ skills: [] })),
        listAccounts(1, 100).catch(() => ({ accounts: [], pagination: { page: 1, page_size: 100, total: 0 } })),
      ]);
      const nextConfigs = configsRes as SystemConfigMap;
      setConfigs(nextConfigs);
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
            <Link href="/settings/llm-providers" className="block transition hover:-translate-y-0.5">
              <StatCard label={t("settings.providers")} value={formatNumber(providers.length)} hint="Click to open model configuration" tone="info" icon={<Icon name="dashboard" className="h-6 w-6" />} />
            </Link>
            <Link href="/settings/agents" className="block transition hover:-translate-y-0.5">
              <StatCard label={t("settings.agents")} value={formatNumber(agents.length)} hint="Click to manage registered agents" tone="success" icon={<Icon name="workspace" className="h-6 w-6" />} />
            </Link>
            <Link href="/settings/skills" className="block transition hover:-translate-y-0.5">
              <StatCard label={t("settings.skills")} value={formatNumber(skills.length)} hint="Click to inspect skill configuration" tone="warning" icon={<Icon name="drafts" className="h-6 w-6" />} />
            </Link>
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
            <Card title="Model Configuration" description="Image and provider model settings are now unified in one page.">
              <Link
                href="/settings/llm-providers"
                className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 p-4 transition hover:border-brand-200 hover:bg-brand-50/60"
              >
                <div>
                  <p className="text-sm font-semibold text-slate-900">Open Model Configuration</p>
                  <p className="mt-1 text-sm text-slate-500">
                    Configure providers and image generation models in the same configuration page.
                  </p>
                </div>
                <Button variant="secondary" size="sm">Open</Button>
              </Link>
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
