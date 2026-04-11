import type {
  AccountProfile,
  AuditResultInfo,
  ContentMemory,
  EvaluationDimension,
  EvaluationSummary,
  OutlinePlan,
  OutlineSection,
  QueryPlanInsight,
  ReferenceDigestInsight,
  ReferenceDigestSource,
  ReviewIssueDetail,
  ReviewResult,
  RewriteResult,
  SectionDraft,
  SourceCandidateInsight,
  StyleProfile,
} from "@/types";

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return isRecord(value) ? value : null;
}

function asString(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function asBoolean(value: unknown): boolean | null {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    if (value === "true") return true;
    if (value === "false") return false;
  }
  return null;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => asString(item))
    .filter((item): item is string => Boolean(item));
}

function asRecordArray<T>(value: unknown, mapper: (record: Record<string, unknown>, index: number) => T | null): T[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item, index) => {
      const record = asRecord(item);
      return record ? mapper(record, index) : null;
    })
    .filter((item): item is T => Boolean(item));
}

function arrayFromKeys(record: Record<string, unknown> | null, keys: string[]): unknown[] {
  if (!record) return [];
  for (const key of keys) {
    const value = record[key];
    if (Array.isArray(value)) {
      return value;
    }
  }
  return [];
}

export function hasMeaningfulValue(value: unknown): boolean {
  if (value === null || value === undefined) return false;
  if (typeof value === "string") return value.trim().length > 0;
  if (typeof value === "number") return true;
  if (typeof value === "boolean") return true;
  if (Array.isArray(value)) return value.some((item) => hasMeaningfulValue(item));
  if (isRecord(value)) return Object.values(value).some((item) => hasMeaningfulValue(item));
  return false;
}

function mapMemoryItem(value: unknown, index: number): ContentMemory | null {
  if (typeof value === "string") {
    return {
      id: `memory-${index}`,
      title: value,
      summary: value,
    };
  }

  const record = asRecord(value);
  if (!record) return null;

  const title = asString(record.title) ?? asString(record.headline) ?? asString(record.name);
  if (!title) return null;

  return {
    id: (record.id as number | string | undefined) ?? `memory-${index}`,
    title,
    summary: asString(record.summary) ?? asString(record.abstract) ?? asString(record.snippet),
    tags: asStringArray(record.tags),
    source_draft_id: asNumber(record.source_draft_id) ?? asNumber(record.draft_id),
    source_task_id: asString(record.source_task_id) ?? asString(record.task_id),
    article_id: asString(record.article_id),
    content_excerpt: asString(record.content_excerpt) ?? asString(record.excerpt),
    created_at: asString(record.created_at),
    updated_at: asString(record.updated_at),
    metadata: record,
  };
}

export function normalizeContentMemories(value: unknown): ContentMemory[] {
  const source = Array.isArray(value)
    ? value
    : arrayFromKeys(asRecord(value), ["memories", "items", "articles", "results", "retrieved_memories"]);

  return source
    .map((item, index) => mapMemoryItem(item, index))
    .filter((item): item is ContentMemory => Boolean(item));
}

export function normalizeQueryPlan(value: unknown): QueryPlanInsight | null {
  const record = asRecord(value);
  if (!record) return null;

  return {
    lane: asRecord(record.lane)
      ? {
          id: asString(asRecord(record.lane)?.id),
          label: asString(asRecord(record.lane)?.label),
          input_hint: asString(asRecord(record.lane)?.input_hint),
          reason: asString(asRecord(record.lane)?.reason),
        }
      : null,
    selected_topic: asString(record.selected_topic),
    selected_title: asString(record.selected_title),
    primary_queries: asStringArray(record.primary_queries),
    secondary_queries: asStringArray(record.secondary_queries),
    source_preferences: asStringArray(record.source_preferences),
    banned_angles: asStringArray(record.banned_angles),
    account_keywords: asStringArray(record.account_keywords),
    search_terms: asStringArray(record.search_terms),
  };
}

export function normalizeSourceCandidates(value: unknown): SourceCandidateInsight[] {
  const source = Array.isArray(value)
    ? value
    : arrayFromKeys(asRecord(value), ["source_candidates", "sources", "items"]);

  const normalized: SourceCandidateInsight[] = [];
  source
    .map((item) => asRecord(item))
    .filter((item): item is Record<string, unknown> => Boolean(item))
    .forEach((record) => {
      const sourceTitle = asString(record.source_title) ?? asString(record.title);
      if (!sourceTitle) return;
      normalized.push({
        source_id: asString(record.source_id),
        source_type: asString(record.source_type),
        source_name: asString(record.source_name) ?? asString(record.source),
        source_title: sourceTitle,
        url: asString(record.url),
        snippet: asString(record.snippet) ?? asString(record.summary),
        fit_score: asNumber(record.fit_score),
        origin: asString(record.origin),
        why_selected: asString(record.why_selected),
      });
    });
  return normalized;
}

function mapReferenceDigestSource(record: Record<string, unknown>): ReferenceDigestSource | null {
  const sourceTitle = asString(record.source_title) ?? asString(record.title) ?? asString(record.source_name);
  if (!sourceTitle) return null;
  return {
    source_id: asString(record.source_id),
    source_type: asString(record.source_type),
    source_name: asString(record.source_name),
    source_title: sourceTitle,
    style_brief: asString(record.style_brief),
    structure_brief: asString(record.structure_brief),
    useful_points: asStringArray(record.useful_points),
    snippet: asString(record.snippet),
    origin: asString(record.origin),
    fit_score: asNumber(record.fit_score),
  };
}

export function normalizeReferenceDigest(value: unknown): ReferenceDigestInsight | null {
  const record = asRecord(value);
  if (!record) return null;

  const sourceDigests = asRecordArray(record.source_digests, (item) => mapReferenceDigestSource(item));
  return {
    summary: asString(record.summary),
    source_count: asNumber(record.source_count),
    selected_source_ids: asStringArray(record.selected_source_ids),
    preferred_source_names: asStringArray(record.preferred_source_names),
    style_takeaways: asStringArray(record.style_takeaways),
    structure_takeaways: asStringArray(record.structure_takeaways),
    useful_points: asStringArray(record.useful_points),
    usage_rules: asStringArray(record.usage_rules),
    source_digests: sourceDigests,
    source_snippets: Array.isArray(record.source_snippets)
      ? record.source_snippets.filter((item): item is Record<string, unknown> => isRecord(item))
      : [],
    raw: record,
  };
}

function mapOutlineSection(value: unknown, index: number): OutlineSection | null {
  if (typeof value === "string") {
    return { id: index, title: value };
  }

  const record = asRecord(value);
  if (!record) return null;

  const title = asString(record.title) ?? asString(record.heading) ?? asString(record.name) ?? `Section ${index + 1}`;
  return {
    id: (record.id as number | string | undefined) ?? index,
    section_id: (record.section_id as number | string | undefined) ?? (record.id as number | string | undefined) ?? index,
    title,
    heading: asString(record.heading) ?? title,
    summary: asString(record.summary) ?? asString(record.description),
    goal: asString(record.goal) ?? asString(record.objective) ?? asString(record.purpose),
    purpose: asString(record.purpose) ?? asString(record.goal) ?? asString(record.objective),
    key_points: asStringArray(record.key_points),
    tone_hint: asString(record.tone_hint),
    evidence_refs: asStringArray(record.evidence_refs),
    notes: asString(record.notes),
  };
}

export function normalizeOutlinePlan(value: unknown): OutlinePlan | null {
  if (!value) return null;
  if (typeof value === "string") {
    return { summary: value, sections: [] };
  }

  const record = asRecord(value);
  if (!record) return null;
  const sections = arrayFromKeys(record, ["sections", "outline", "items"]).map(mapOutlineSection).filter((item): item is OutlineSection => Boolean(item));

  if (!sections.length && !hasMeaningfulValue(record.summary) && !hasMeaningfulValue(record.description)) {
    return null;
  }

  return {
    article_goal: asString(record.article_goal),
    target_reader_takeaway: asString(record.target_reader_takeaway),
    opening_hook: asString(record.opening_hook),
    summary: asString(record.summary) ?? asString(record.description),
    sections,
    ending_cta: asString(record.ending_cta),
    estimated_word_count: asNumber(record.estimated_word_count),
    raw: record,
  };
}

function mapSectionDraft(value: unknown, index: number): SectionDraft | null {
  if (typeof value === "string") {
    return {
      id: index,
      heading: `Section ${index + 1}`,
      content_markdown: value,
    };
  }

  const record = asRecord(value);
  if (!record) return null;
  return {
    id: (record.id as number | string | undefined) ?? index,
    section_id: (record.section_id as number | string | undefined) ?? (record.id as number | string | undefined) ?? index,
    heading: asString(record.heading) ?? asString(record.title) ?? asString(record.section_title) ?? `Section ${index + 1}`,
    summary: asString(record.summary) ?? asString(record.brief),
    content_markdown: asString(record.content_markdown) ?? asString(record.markdown) ?? asString(record.content),
    content_html: asString(record.content_html) ?? asString(record.html),
    word_count: asNumber(record.word_count),
    evidence_refs: asStringArray(record.evidence_refs),
    status: asString(record.status),
  };
}

export function normalizeSectionDrafts(value: unknown): SectionDraft[] {
  const source = Array.isArray(value)
    ? value
    : arrayFromKeys(asRecord(value), ["section_drafts", "sections", "drafts", "items"]);

  return source
    .map((item, index) => mapSectionDraft(item, index))
    .filter((item): item is SectionDraft => Boolean(item));
}

function mapReviewIssue(value: unknown): ReviewIssueDetail | null {
  if (typeof value === "string") {
    return { description: value };
  }

  const record = asRecord(value);
  if (!record) return null;
  const description = asString(record.description) ?? asString(record.message) ?? asString(record.issue);
  if (!description) return null;
  return {
    code: asString(record.code),
    title: asString(record.title),
    description,
    severity: asString(record.severity) ?? asString(record.level),
    location: asString(record.location) ?? asString(record.section_id),
    section_id: asString(record.section_id),
    suggestion: asString(record.suggestion) ?? asString(record.recommendation),
  };
}

function mapReviewResult(value: unknown, index: number): ReviewResult | null {
  if (typeof value === "string") {
    return {
      reviewer: `reviewer_${index + 1}`,
      summary: value,
      issues: [],
    };
  }

  const record = asRecord(value);
  if (!record) return null;

  const issues = arrayFromKeys(record, ["issues", "findings", "problems"]).map(mapReviewIssue).filter((item): item is ReviewIssueDetail => Boolean(item));
  const summary = asString(record.summary) ?? asString(record.overall_comment) ?? asString(record.comment);

  if (!summary && !issues.length) return null;

  return {
    reviewer: asString(record.reviewer) ?? asString(record.agent) ?? `reviewer_${index + 1}`,
    passed: asBoolean(record.passed),
    score: asNumber(record.score),
    summary,
    rewrite_suggestions: asStringArray(record.rewrite_suggestions),
    issues,
    failed: asBoolean(record.failed),
    degraded: asBoolean(record.degraded),
    error_message: asString(record.error_message),
    raw: record,
  };
}

export function normalizeReviewResults(value: unknown, auditResult?: AuditResultInfo | null): ReviewResult[] {
  const record = asRecord(value);
  const source = Array.isArray(value)
    ? value
    : [
        ...arrayFromKeys(record, ["review_results", "reviews", "results", "items"]),
        ...(record?.style_review ? [record.style_review] : []),
        ...(record?.structure_review ? [record.structure_review] : []),
      ];

  const normalized = source
    .map((item, index) => mapReviewResult(item, index))
    .filter((item): item is ReviewResult => Boolean(item));

  if (normalized.length) return normalized;

  if (!auditResult) return [];
  const auditIssues = Array.isArray(auditResult.issues)
    ? auditResult.issues.map(mapReviewIssue).filter((item): item is ReviewIssueDetail => Boolean(item))
    : [];

  if (!auditIssues.length && !auditResult.overall_comment) return [];

  return [
    {
      reviewer: "audit",
      passed: auditResult.passed,
      summary: auditResult.overall_comment,
      issues: auditIssues,
    },
  ];
}

export function normalizeRewriteResult(value: unknown): RewriteResult | null {
  if (!value) return null;
  if (typeof value === "string") {
    return { summary: value };
  }

  const record = asRecord(value);
  if (!record) return null;
  if (!hasMeaningfulValue(record)) return null;

  return {
    title: asString(record.title),
    summary: asString(record.summary) ?? asString(record.rewrite_summary) ?? asString(record.revision_summary),
    notes: asString(record.notes) ?? asString(record.comment),
    used_rewrite: asBoolean(record.used_rewrite),
    content_markdown:
      asString(record.revised_content_markdown)
      ?? asString(record.content_markdown)
      ?? asString(record.markdown)
      ?? asString(record.content),
    content_html: asString(record.revised_content_html) ?? asString(record.content_html) ?? asString(record.html),
    fixed_issues: asStringArray(record.fixed_issues),
    changed_sections: asStringArray(record.changed_sections),
    rewrite_failed: asBoolean(record.rewrite_failed),
    rewrite_skipped: asBoolean(record.rewrite_skipped),
    failure_reason: asString(record.failure_reason),
    raw: record,
  };
}

function extractDimension(record: Record<string, unknown>, key: string): EvaluationDimension {
  const directScore = asNumber(record[key]);
  const nested = asRecord(record[`${key}_detail`]) ?? asRecord(record[key]);

  return {
    score: directScore ?? asNumber(nested?.score),
    explanation: asString(nested?.explanation) ?? asString(nested?.comment) ?? asString(record[`${key}_explanation`]),
    badges: asStringArray(nested?.badges),
  };
}

export function normalizeEvaluation(value: unknown): EvaluationSummary | null {
  const record = asRecord(value);
  if (!record) return null;

  const dimensions: Record<string, EvaluationDimension> = {
    style_score: extractDimension(record, "style_score"),
    structure_score: extractDimension(record, "structure_score"),
    evidence_score: extractDimension(record, "evidence_score"),
    repetition_score: extractDimension(record, "repetition_score"),
    readability_score: extractDimension(record, "readability_score"),
    final_score: extractDimension(record, "final_score"),
  };

  const summary: EvaluationSummary = {
    style_score: dimensions.style_score.score,
    structure_score: dimensions.structure_score.score,
    evidence_score: dimensions.evidence_score.score,
    repetition_score: dimensions.repetition_score.score,
    readability_score: dimensions.readability_score.score,
    final_score: dimensions.final_score.score,
    summary: asString(record.summary) ?? asString(record.overall_comment),
    dimensions,
    raw: record,
  };

  return hasMeaningfulValue(summary) ? summary : null;
}

export function normalizeStyleProfile(value: unknown, fallbackProfile?: AccountProfile | null): StyleProfile | null {
  const record = asRecord(value);

  if (!record && !fallbackProfile) return null;

  const normalized: StyleProfile = {
    summary: record ? asString(record.summary) : null,
    tone_profile: record ? asString(record.tone_profile) ?? asString(record.tone) : fallbackProfile?.tone ?? null,
    title_style: record ? asString(record.title_style) : null,
    intro_style: record ? asString(record.intro_style) : null,
    structure_style: record ? asString(record.structure_style) : fallbackProfile?.content_style ?? null,
    cta_style: record ? asString(record.cta_style) : null,
    lexical_features: record ? asStringArray(record.lexical_features) : fallbackProfile?.keywords ?? [],
    banned_patterns: record ? asStringArray(record.banned_patterns) : [],
    evidence_article_ids: record && Array.isArray(record.evidence_article_ids)
      ? record.evidence_article_ids.filter((item): item is string | number => typeof item === "string" || typeof item === "number")
      : [],
    raw: record,
  };

  if (!normalized.summary && fallbackProfile) {
    normalized.summary = [fallbackProfile.tone, fallbackProfile.content_style].filter(Boolean).join(" / ") || null;
  }

  return hasMeaningfulValue(normalized) ? normalized : null;
}
