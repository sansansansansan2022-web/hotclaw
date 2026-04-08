"use client";

import type { ReactNode } from "react";
import { cn, startCase, truncate } from "@/lib/utils";
import type { ContentMemory, EvaluationSummary, OutlinePlan, ReviewResult, RewriteResult, SectionDraft, StyleProfile } from "@/types";
import { Badge, Card } from "@/components/console/ui";
import { Icon } from "@/components/console/icons";

export function InsightDisclosureCard({
  title,
  description,
  badge,
  defaultOpen = false,
  children,
}: {
  title: string;
  description?: string;
  badge?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  return (
    <Card className="p-0">
      <details open={defaultOpen} className="group">
        <summary className="flex cursor-pointer list-none items-start justify-between gap-4 p-6">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
              {badge}
            </div>
            {description ? <p className="text-sm text-slate-500">{description}</p> : null}
          </div>
          <span className="rounded-full border border-slate-200 p-2 text-slate-500 transition group-open:rotate-90">
            <Icon name="chevronRight" className="h-4 w-4" />
          </span>
        </summary>
        <div className="border-t border-slate-200 px-6 py-5">{children}</div>
      </details>
    </Card>
  );
}

function BadgeCluster({ values, tone = "muted" }: { values: Array<string | number>; tone?: "brand" | "muted" | "warning" | "danger" | "success" | "info" }) {
  if (!values.length) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {values.map((value) => (
        <Badge key={String(value)} tone={tone}>
          {value}
        </Badge>
      ))}
    </div>
  );
}

function InfoField({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div>
      <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{label}</p>
      <p className="mt-2 text-sm leading-6 text-slate-600">{value}</p>
    </div>
  );
}

export function EvaluationScoreCard({ evaluation, locale }: { evaluation: EvaluationSummary; locale: "en" | "zh-CN" }) {
  const labels: Record<string, string> =
    locale === "zh-CN"
      ? {
          style_score: "风格一致性",
          structure_score: "结构完整度",
          evidence_score: "证据支撑",
          readability_score: "可读性",
          final_score: "综合得分",
        }
      : {
          style_score: "Style",
          structure_score: "Structure",
          evidence_score: "Evidence",
          readability_score: "Readability",
          final_score: "Final",
        };

  const metrics = [
    ["style_score", evaluation.style_score],
    ["structure_score", evaluation.structure_score],
    ["evidence_score", evaluation.evidence_score],
    ["readability_score", evaluation.readability_score],
    ["final_score", evaluation.final_score],
  ] as const;

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        {metrics.map(([key, score]) => {
          const dimension = evaluation.dimensions?.[key];
          const safeScore = typeof score === "number" ? Math.max(0, Math.min(100, score)) : null;
          return (
            <div key={key} className={cn("rounded-2xl border border-slate-200 bg-slate-50 p-4", key === "final_score" && "border-brand-200 bg-brand-50/60")}>
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-slate-900">{labels[key]}</p>
                <Badge tone={key === "final_score" ? "brand" : "muted"}>{safeScore ?? "--"}</Badge>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-white">
                <div className={cn("h-full rounded-full", key === "final_score" ? "bg-brand-500" : "bg-slate-400")} style={{ width: `${safeScore ?? 0}%` }} />
              </div>
              <p className="mt-3 text-xs leading-5 text-slate-500">
                {dimension?.explanation ||
                  (locale === "zh-CN" ? "后端尚未返回这个维度的说明。" : "The backend has not returned an explanation for this dimension yet.")}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Badge tone={key === "final_score" ? "brand" : "info"}>{labels[key]}</Badge>
                {dimension?.badges?.map((item) => (
                  <Badge key={item} tone="muted">
                    {item}
                  </Badge>
                ))}
              </div>
            </div>
          );
        })}
      </div>
      {evaluation.summary ? <p className="text-sm leading-6 text-slate-600">{evaluation.summary}</p> : null}
    </div>
  );
}

export function MemoryReferenceList({ memories, locale }: { memories: ContentMemory[]; locale: "en" | "zh-CN" }) {
  return (
    <div className="space-y-3">
      {memories.map((memory) => (
        <article key={String(memory.id)} className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-slate-900">{memory.title}</h3>
            {memory.source_draft_id ? <Badge tone="info">{locale === "zh-CN" ? `草稿 #${memory.source_draft_id}` : `Draft #${memory.source_draft_id}`}</Badge> : null}
            {memory.source_task_id ? <Badge tone="muted">{memory.source_task_id}</Badge> : null}
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-600">{memory.summary || memory.content_excerpt || (locale === "zh-CN" ? "暂无摘要。" : "No summary available.")}</p>
          {memory.tags?.length ? <div className="mt-3"><BadgeCluster values={memory.tags} tone="muted" /></div> : null}
        </article>
      ))}
    </div>
  );
}

export function StyleProfileSummaryView({ profile, locale }: { profile: StyleProfile; locale: "en" | "zh-CN" }) {
  return (
    <div className="space-y-5">
      <InfoField label={locale === "zh-CN" ? "摘要" : "Summary"} value={profile.summary} />
      <div className="grid gap-5 md:grid-cols-2">
        <InfoField label={locale === "zh-CN" ? "语气画像" : "Tone Profile"} value={profile.tone_profile} />
        <InfoField label={locale === "zh-CN" ? "标题风格" : "Title Style"} value={profile.title_style} />
        <InfoField label={locale === "zh-CN" ? "开头风格" : "Intro Style"} value={profile.intro_style} />
        <InfoField label={locale === "zh-CN" ? "结构风格" : "Structure Style"} value={profile.structure_style} />
        <InfoField label={locale === "zh-CN" ? "CTA 风格" : "CTA Style"} value={profile.cta_style} />
      </div>
      {profile.lexical_features?.length ? (
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "词汇特征" : "Lexical Features"}</p>
          <div className="mt-3">
            <BadgeCluster values={profile.lexical_features} tone="brand" />
          </div>
        </div>
      ) : null}
      {profile.banned_patterns?.length ? (
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "禁用表达" : "Banned Patterns"}</p>
          <div className="mt-3">
            <BadgeCluster values={profile.banned_patterns} tone="danger" />
          </div>
        </div>
      ) : null}
      {profile.evidence_article_ids?.length ? (
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "证据文章" : "Evidence Articles"}</p>
          <div className="mt-3">
            <BadgeCluster values={profile.evidence_article_ids} tone="info" />
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function OutlinePlanView({ outline, locale }: { outline: OutlinePlan; locale: "en" | "zh-CN" }) {
  return (
    <div className="space-y-4">
      {outline.summary ? <p className="text-sm leading-6 text-slate-600">{outline.summary}</p> : null}
      {outline.sections.length ? (
        <div className="space-y-3">
          {outline.sections.map((section, index) => (
            <div key={String(section.id ?? index)} className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
              <div className="flex items-start gap-3">
                <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-white text-xs font-semibold text-brand-700">
                  {index + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-slate-900">{section.title}</p>
                  {section.summary ? <p className="mt-2 text-sm leading-6 text-slate-600">{section.summary}</p> : null}
                  {section.goal ? <p className="mt-2 text-xs text-slate-500">{locale === "zh-CN" ? `目标：${section.goal}` : `Goal: ${section.goal}`}</p> : null}
                  {section.notes ? <p className="mt-1 text-xs text-slate-500">{section.notes}</p> : null}
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function SectionDraftsView({ sections, locale }: { sections: SectionDraft[]; locale: "en" | "zh-CN" }) {
  return (
    <div className="space-y-3">
      {sections.map((section, index) => (
        <div key={String(section.id ?? index)} className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-slate-900">{section.heading}</p>
            {section.status ? <Badge tone="muted">{startCase(section.status)}</Badge> : null}
          </div>
          {section.summary ? <p className="mt-2 text-sm leading-6 text-slate-600">{section.summary}</p> : null}
          {section.content_markdown || section.content_html ? (
            <pre className="mt-3 whitespace-pre-wrap rounded-2xl border border-slate-200 bg-white p-4 text-xs leading-6 text-slate-600">
              {truncate(section.content_markdown || section.content_html || "", 420)}
            </pre>
          ) : (
            <p className="mt-3 text-xs text-slate-500">{locale === "zh-CN" ? "该段落还没有正文内容。" : "This section does not have body content yet."}</p>
          )}
        </div>
      ))}
    </div>
  );
}

export function ReviewResultsView({ results, locale }: { results: ReviewResult[]; locale: "en" | "zh-CN" }) {
  return (
    <div className="space-y-4">
      {results.map((result, index) => (
        <div key={`${result.reviewer ?? "review"}-${index}`} className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-slate-900">{result.reviewer || (locale === "zh-CN" ? "审稿器" : "Reviewer")}</p>
            {typeof result.passed === "boolean" ? (
              <Badge tone={result.passed ? "success" : "warning"}>
                {result.passed ? (locale === "zh-CN" ? "通过" : "Passed") : locale === "zh-CN" ? "待修正" : "Needs revision"}
              </Badge>
            ) : null}
          </div>
          {result.summary ? <p className="mt-2 text-sm leading-6 text-slate-600">{result.summary}</p> : null}
          {result.issues?.length ? (
            <div className="mt-3 space-y-3">
              {result.issues.map((issue, issueIndex) => (
                <div key={`${issue.description}-${issueIndex}`} className="rounded-2xl border border-slate-200 bg-white p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    {issue.title ? <p className="text-sm font-semibold text-slate-900">{issue.title}</p> : null}
                    {issue.severity ? <Badge tone={issue.severity === "high" ? "danger" : issue.severity === "medium" ? "warning" : "muted"}>{startCase(issue.severity)}</Badge> : null}
                    {issue.location ? <Badge tone="info">{issue.location}</Badge> : null}
                  </div>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{issue.description}</p>
                  {issue.suggestion ? <p className="mt-2 text-xs text-slate-500">{issue.suggestion}</p> : null}
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}

export function RewriteResultView({ rewrite, locale }: { rewrite: RewriteResult; locale: "en" | "zh-CN" }) {
  return (
    <div className="space-y-4">
      <InfoField label={locale === "zh-CN" ? "改写摘要" : "Rewrite Summary"} value={rewrite.summary} />
      <InfoField label={locale === "zh-CN" ? "说明" : "Notes"} value={rewrite.notes} />
      {rewrite.changed_sections?.length ? (
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "变更段落" : "Changed Sections"}</p>
          <div className="mt-3">
            <BadgeCluster values={rewrite.changed_sections} tone="warning" />
          </div>
        </div>
      ) : null}
      {rewrite.content_markdown || rewrite.content_html ? (
        <pre className="whitespace-pre-wrap rounded-2xl border border-slate-200 bg-slate-50/70 p-4 text-xs leading-6 text-slate-600">
          {truncate(rewrite.content_markdown || rewrite.content_html || "", 560)}
        </pre>
      ) : null}
    </div>
  );
}
