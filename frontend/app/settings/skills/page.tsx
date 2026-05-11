"use client";

import { useEffect, useState } from "react";
import { Icon } from "@/components/console/icons";
import { Badge, Card, EmptyState, ErrorState, PageHeader, SkeletonRows, StatCard } from "@/components/console/ui";
import { listSettingsSkills, type SkillInfo } from "@/lib/api";

export default function SkillsPage() {
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const activeCount = skills.filter((skill) => skill.status === "active").length;

  async function loadSkills() {
    setLoading(true);
    try {
      const response = await listSettingsSkills();
      setSkills(response.skills);
      setError(null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load skills.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadSkills();
  }, []);

  return (
    <div className="space-y-8">
        <PageHeader
          eyebrow="Capability Inventory"
          title="Skills"
          description="Review the skill modules currently exposed to the console and inspect any structured configuration they carry."
        />

        {loading ? (
          <SkeletonRows rows={5} />
        ) : error ? (
          <ErrorState title="Skills failed to load" description={error} retry={() => void loadSkills()} />
        ) : (
          <>
            <div className="grid gap-5 md:grid-cols-3">
              <StatCard
                label="Registered Skills"
                value={String(skills.length)}
                hint="All skills returned by the backend registry."
                tone="info"
                icon={<Icon name="drafts" className="h-6 w-6" />}
              />
              <StatCard
                label="Active Skills"
                value={String(activeCount)}
                hint="Skills that are currently marked active."
                tone="success"
                icon={<Icon name="check" className="h-6 w-6" />}
              />
              <StatCard
                label="With Config"
                value={String(skills.filter((skill) => skill.config_data && Object.keys(skill.config_data).length > 0).length)}
                hint="Skills exposing structured config data."
                tone="warning"
                icon={<Icon name="settings" className="h-6 w-6" />}
              />
            </div>

            <Card title="Registered Skills" description="The current skill inventory from the backend, shown with the same presentation used throughout settings.">
              {skills.length ? (
                <div className="space-y-4">
                  {skills.map((skill) => (
                    <div key={skill.skill_id} className="rounded-2xl border border-slate-200 bg-slate-50/50 p-5">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-slate-900">{skill.name}</p>
                          <p className="mt-1 text-xs text-slate-500">
                            {skill.skill_id} · v{skill.version}
                          </p>
                        </div>
                        <Badge tone={skill.status === "active" ? "success" : "muted"}>{skill.status}</Badge>
                      </div>

                      <p className="mt-3 text-sm leading-6 text-slate-500">{skill.description}</p>

                      {skill.config_data && Object.keys(skill.config_data).length > 0 ? (
                        <pre className="mt-4 overflow-auto rounded-2xl border border-slate-200 bg-white p-4 text-xs leading-6 text-slate-700">
                          {JSON.stringify(skill.config_data, null, 2)}
                        </pre>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState
                  title="No skills found"
                  description="The backend did not return any registered skills for this environment."
                />
              )}
            </Card>
          </>
        )}
    </div>
  );
}
