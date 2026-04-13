"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { listSkills } from "@/lib/api";
import type { SkillInfo } from "@/lib/api";

export default function SkillsPage() {
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const data = await listSkills();
        setSkills(data.skills);
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
      <header className="bg-slate-800/80 backdrop-blur-sm border-b border-slate-700 px-6 py-4 sticky top-0 z-20">
        <div className="max-w-[800px] mx-auto flex items-center gap-4">
          <Link href="/settings" className="text-cyan-400 hover:text-cyan-300 text-sm">
            &larr; 设置中心
          </Link>
          <span className="text-slate-500">/</span>
          <span className="text-white font-medium text-sm">技能配置</span>
        </div>
      </header>

      <main className="max-w-[800px] mx-auto p-6">
        <div className="text-xs text-cyan-400/80 mb-4 border-b border-slate-700/50 pb-2 font-medium">
          已注册技能
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20 gap-3">
            <div className="w-8 h-8 border-4 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin" />
            <span className="text-slate-500 text-sm">加载中...</span>
          </div>
        ) : skills.length === 0 ? (
          <div className="text-center py-16">
            <div className="text-5xl mb-4">&#128161;</div>
            <div className="text-slate-400 text-sm mb-2">暂无已注册的技能</div>
            <div className="text-slate-600 text-xs max-w-md mx-auto">
              Skill 是 Agent 调用的原子能力单元，可在 skills/ 目录下实现并注册到系统。
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {skills.map((s) => (
              <div
                key={s.skill_id}
                className="bg-slate-800/50 border border-slate-700 rounded-xl px-5 py-4"
              >
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <div className="text-white font-medium text-sm">{s.name}</div>
                    <div className="text-xs text-slate-500 mt-0.5 font-mono">{s.skill_id} v{s.version}</div>
                  </div>
                  <span className={`text-xs px-2.5 py-1 rounded-lg border ${
                    s.status === "active"
                      ? "text-green-400 border-green-600/40 bg-green-900/20"
                      : "text-slate-400 border-slate-600/40 bg-slate-800"
                  }`}>
                    {s.status}
                  </span>
                </div>
                <div className="text-sm text-slate-400 mb-3">{s.description}</div>
                {s.config_data && Object.keys(s.config_data).length > 0 && (
                  <pre className="mt-2 text-xs text-slate-500 bg-slate-900/60 p-3 rounded-lg overflow-auto max-h-[120px] font-mono">
                    {JSON.stringify(s.config_data, null, 2)}
                  </pre>
                )}
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
