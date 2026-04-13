"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { LanguageSwitcher } from "@/components/console/language-switcher";
import { getAllSystemConfigs, listAccounts, listAgents, listLLMProviders, listSkills } from "@/lib/api";
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
        getAllSystemConfigs().catch(() => ({})),
        listLLMProviders().catch(() => []),
        listAgents().catch(() => ({ agents: [] })),
        listSkills().catch(() => ({ skills: [] })),
        listAccounts(1, 100).catch(() => ({ accounts: [], pagination: { page: 1, page_size: 100, total: 0 } })),
      ]);
      setConfigs(configsRes);
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
