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
    <div className="min-h-screen bg-[#1a1a2e] text-gray-200 font-mono">
      <header className="bg-[#2a2a4a] border-b border-gray-700 px-6 py-3 flex items-center gap-4">
        <Link href="/" className="text-cyan-400 hover:text-cyan-300 text-[12px]">&larr; 返回编辑部</Link>
        <span className="text-[14px] text-gray-300 tracking-widest">Skill 管理</span>
      </header>

      <main className="max-w-[800px] mx-auto p-6">
        <div className="text-[10px] text-cyan-400/80 mb-3 border-b border-gray-700/50 pb-1">
          已注册 Skill
        </div>

        {loading ? (
          <div className="text-[10px] text-gray-500 py-12 text-center">加载中...</div>
        ) : skills.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-[12px] text-gray-500 mb-2">暂无已注册的 Skill</div>
            <div className="text-[9px] text-gray-600">
              Skill 是 Agent 调用的原子能力。MVP 阶段使用 Mock Agent，暂未注册独立 Skill。
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            {skills.map((s) => (
              <div
                key={s.skill_id}
                className="bg-gray-900/50 border border-gray-700 rounded-sm px-4 py-3"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-[11px] text-gray-300 font-bold">{s.name}</div>
                    <div className="text-[9px] text-gray-500 mt-0.5">{s.skill_id} v{s.version}</div>
                  </div>
                  <span className={`text-[9px] px-2 py-0.5 rounded-sm border ${
                    s.status === "active"
                      ? "text-green-400 border-green-600/30"
                      : "text-gray-400 border-gray-600/30"
                  }`}>
                    {s.status}
                  </span>
                </div>
                <div className="text-[10px] text-gray-400 mt-1">{s.description}</div>
                {s.config_data && (
                  <pre className="mt-2 text-[9px] text-gray-500 bg-gray-800/50 p-2 rounded-sm overflow-auto max-h-[100px]">
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
