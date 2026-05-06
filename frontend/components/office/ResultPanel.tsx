/** Result panel: slides in from the right when task is complete. Shows articles, topics, etc. */

"use client";

import { useState } from "react";

interface Props {
  data: Record<string, unknown>;
}

export default function ResultPanel({ data }: Props) {
  const [open, setOpen] = useState(true);

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed right-3 top-1/2 -translate-y-1/2 z-50
                   bg-cyan-600 text-white text-[10px] font-mono px-2 py-4 rounded-l-sm
                   border border-cyan-500 hover:bg-cyan-500 transition-colors
                   writing-mode-vertical"
        style={{ writingMode: "vertical-rl" }}
      >
        查看结果 ▸
      </button>
    );
  }

  // Extract data
  const profile = data.profile as Record<string, unknown> | undefined;
  const topics = data.topics as { topics?: Array<{ title: string; estimated_appeal: number }> } | undefined;
  const titles = data.titles as { titles?: Array<{ text: string; score: number }> } | undefined;
  const content = data.content as { content_markdown?: string; word_count?: number } | undefined;
  const audit = data.audit_result as { passed?: boolean; risk_level?: string; overall_comment?: string } | undefined;

  return (
    <div className="fixed right-0 top-0 bottom-0 w-[380px] z-50
                    bg-[#111827]/95 border-l border-gray-700 overflow-y-auto">
      {/* Header */}
      <div className="sticky top-0 bg-[#111827] border-b border-gray-700 px-4 py-3 flex items-center justify-between">
        <span className="text-[12px] font-mono text-cyan-400">▸ 编辑部产出</span>
        <button
          onClick={() => setOpen(false)}
          className="text-gray-500 hover:text-white text-[14px] font-mono"
        >
          ✕
        </button>
      </div>

      <div className="p-4 space-y-4">
        {/* Profile */}
        {profile && (
          <Section title="账号画像">
            <KV label="领域" value={String(profile.domain || "-")} />
            <KV label="调性" value={String(profile.tone || "-")} />
            <KV label="风格" value={String(profile.content_style || "-")} />
          </Section>
        )}

        {/* Topics */}
        {topics?.topics && (
          <Section title="候选选题">
            {topics.topics.map((t, i) => (
              <div key={i} className="flex items-start gap-2 mb-1.5">
                <span className="text-[10px] font-mono text-yellow-400 mt-0.5">#{i + 1}</span>
                <div>
                  <div className="text-[11px] font-mono text-gray-200">{t.title}</div>
                  <div className="text-[9px] font-mono text-gray-500">
                    吸引力: {(t.estimated_appeal * 100).toFixed(0)}%
                  </div>
                </div>
              </div>
            ))}
          </Section>
        )}

        {/* Titles */}
        {titles?.titles && (
          <Section title="候选标题">
            {titles.titles.map((t, i) => (
              <div key={i} className="flex items-start gap-2 mb-1.5">
                <span className="text-[9px] font-mono text-green-400 mt-0.5">
                  {t.score.toFixed(1)}
                </span>
                <div className="text-[11px] font-mono text-gray-200">{t.text}</div>
              </div>
            ))}
          </Section>
        )}

        {/* Article */}
        {content?.content_markdown && (
          <Section title={`正文草稿 (${content.word_count || 0}字)`}>
            <div className="bg-gray-800/50 rounded-sm p-3 max-h-[300px] overflow-y-auto">
              <pre className="text-[10px] font-mono text-gray-300 whitespace-pre-wrap leading-relaxed">
                {content.content_markdown}
              </pre>
            </div>
          </Section>
        )}

        {/* Audit */}
        {audit && (
          <Section title="审核结果">
            <div className="flex items-center gap-2 mb-1">
              <span
                className={`w-[8px] h-[8px] rounded-full ${
                  audit.passed ? "bg-green-500" : "bg-red-500"
                }`}
              />
              <span className="text-[11px] font-mono text-gray-200">
                {audit.passed ? "通过" : "未通过"} | 风险等级: {audit.risk_level}
              </span>
            </div>
            {audit.overall_comment && (
              <p className="text-[10px] font-mono text-gray-400 mt-1">
                {audit.overall_comment}
              </p>
            )}
          </Section>
        )}
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[10px] font-mono text-cyan-400/80 mb-1.5 border-b border-gray-700/50 pb-1">
        {title}
      </div>
      <div>{children}</div>
    </div>
  );
}

function KV({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2 mb-0.5">
      <span className="text-[9px] font-mono text-gray-500 min-w-[40px]">{label}</span>
      <span className="text-[10px] font-mono text-gray-300">{value}</span>
    </div>
  );
}
