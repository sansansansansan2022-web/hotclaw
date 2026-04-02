"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { listAgents, getAgent, updateAgentConfig } from "@/lib/api";
import type { AgentInfo } from "@/lib/api";

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<AgentInfo | null>(null);
  const [editing, setEditing] = useState(false);
  const [promptDraft, setPromptDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const data = await listAgents();
        setAgents(data.agents);
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function handleSelect(agentId: string) {
    try {
      const detail = await getAgent(agentId);
      setSelected(detail);
      setPromptDraft(detail.prompt_template || "");
      setEditing(false);
      setMessage("");
    } catch {
      // ignore
    }
  }

  async function handleSave() {
    if (!selected) return;
    setSaving(true);
    setMessage("");
    try {
      await updateAgentConfig(selected.agent_id, { prompt_template: promptDraft });
      setMessage("保存成功");
      setEditing(false);
    } catch {
      setMessage("保存失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
      <header className="bg-slate-800/80 backdrop-blur-sm border-b border-slate-700 px-6 py-4 sticky top-0 z-20">
        <div className="max-w-[900px] mx-auto flex items-center gap-4">
          <Link href="/settings" className="text-cyan-400 hover:text-cyan-300 text-sm">
            &larr; 设置中心
          </Link>
          <span className="text-slate-500">/</span>
          <span className="text-white font-medium text-sm">智能体配置</span>
        </div>
      </header>

      <main className="max-w-[900px] mx-auto p-6 flex gap-6">
        {/* Agent list */}
        <div className="w-[260px] shrink-0">
          <div className="text-xs text-cyan-400/80 mb-2 border-b border-slate-700/50 pb-1">
            已注册智能体
          </div>
          {loading ? (
            <div className="text-xs text-slate-500 py-4 flex items-center gap-2">
              <div className="w-4 h-4 border-2 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin" />
              加载中...
            </div>
          ) : agents.length === 0 ? (
            <div className="text-xs text-slate-500 py-4">暂无智能体</div>
          ) : (
            <div className="space-y-1">
              {agents.map((a) => (
                <button
                  key={a.agent_id}
                  onClick={() => handleSelect(a.agent_id)}
                  className={`w-full text-left px-3 py-2.5 rounded-lg text-xs transition-colors border ${
                    selected?.agent_id === a.agent_id
                      ? "bg-cyan-900/30 border-cyan-500/50 text-cyan-300"
                      : "bg-slate-800/30 border-slate-700/50 text-slate-300 hover:border-slate-600"
                  }`}
                >
                  <div className="font-bold">{a.name}</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">{a.agent_id}</div>
                  <div className="text-[10px] text-slate-500 truncate">{a.description}</div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Detail */}
        <div className="flex-1 min-w-0">
          {!selected ? (
            <div className="text-sm text-slate-500 py-12 text-center">
              选择左侧智能体查看详情
            </div>
          ) : (
            <div className="space-y-4">
              <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-base text-white font-medium">{selected.name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded border ${
                    selected.status === "active"
                      ? "text-green-400 border-green-600/40 bg-green-900/20"
                      : "text-slate-400 border-slate-600/40 bg-slate-800"
                  }`}>
                    {selected.status}
                  </span>
                </div>
                <div className="text-sm text-slate-400">{selected.description}</div>
                <div className="flex gap-4 mt-3 text-xs text-slate-500">
                  <span>ID: {selected.agent_id}</span>
                  <span>版本: {selected.version}</span>
                </div>
              </div>

              {/* Prompt template editor */}
              <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs text-cyan-400/80 font-medium">Prompt 模板</span>
                  {!editing ? (
                    <button
                      onClick={() => setEditing(true)}
                      className="text-xs text-slate-400 hover:text-white border border-slate-600 px-3 py-1 rounded-lg transition-colors"
                    >
                      编辑
                    </button>
                  ) : (
                    <div className="flex gap-2">
                      <button
                        onClick={handleSave}
                        disabled={saving}
                        className="text-xs text-cyan-400 hover:text-cyan-300 border border-cyan-600/50 px-3 py-1 rounded-lg disabled:opacity-50 transition-colors"
                      >
                        {saving ? "保存中..." : "保存"}
                      </button>
                      <button
                        onClick={() => { setEditing(false); setPromptDraft(selected.prompt_template || ""); }}
                        className="text-xs text-slate-400 hover:text-white border border-slate-600 px-3 py-1 rounded-lg transition-colors"
                      >
                        取消
                      </button>
                    </div>
                  )}
                </div>
                {editing ? (
                  <textarea
                    value={promptDraft}
                    onChange={(e) => setPromptDraft(e.target.value)}
                    rows={10}
                    className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-xs text-slate-300
                               focus:outline-none focus:border-cyan-500 resize-y font-mono"
                    placeholder="在此输入智能体的 prompt 模板..."
                  />
                ) : (
                  <pre className="text-xs text-slate-400 bg-slate-900/60 p-3 rounded-lg min-h-[80px] whitespace-pre-wrap font-mono">
                    {selected.prompt_template || "(未配置)"}
                  </pre>
                )}
                {message && (
                  <div className={`mt-2 text-xs ${message.includes("成功") ? "text-green-400" : "text-red-400"}`}>
                    {message}
                  </div>
                )}
              </div>

              {/* Model config */}
              <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
                <span className="text-xs text-cyan-400/80 font-medium block mb-3">模型配置</span>
                <pre className="text-xs text-slate-400 bg-slate-900/60 p-3 rounded-lg font-mono">
                  {selected.model_config_data
                    ? JSON.stringify(selected.model_config_data, null, 2)
                    : "(使用默认配置)"}
                </pre>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
