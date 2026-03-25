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
    <div className="min-h-screen bg-[#1a1a2e] text-gray-200 font-mono">
      <header className="bg-[#2a2a4a] border-b border-gray-700 px-6 py-3 flex items-center gap-4">
        <Link href="/" className="text-cyan-400 hover:text-cyan-300 text-[12px]">&larr; 返回编辑部</Link>
        <span className="text-[14px] text-gray-300 tracking-widest">Agent 管理</span>
      </header>

      <main className="max-w-[900px] mx-auto p-6 flex gap-6">
        {/* Agent list */}
        <div className="w-[260px] shrink-0">
          <div className="text-[10px] text-cyan-400/80 mb-2 border-b border-gray-700/50 pb-1">
            已注册 Agent
          </div>
          {loading ? (
            <div className="text-[10px] text-gray-500 py-4">加载中...</div>
          ) : agents.length === 0 ? (
            <div className="text-[10px] text-gray-500 py-4">暂无 Agent</div>
          ) : (
            <div className="space-y-1">
              {agents.map((a) => (
                <button
                  key={a.agent_id}
                  onClick={() => handleSelect(a.agent_id)}
                  className={`w-full text-left px-3 py-2 rounded-sm text-[11px] transition-colors border ${
                    selected?.agent_id === a.agent_id
                      ? "bg-cyan-900/30 border-cyan-600/50 text-cyan-300"
                      : "bg-gray-900/30 border-gray-700/50 text-gray-300 hover:border-gray-600"
                  }`}
                >
                  <div className="font-bold">{a.name}</div>
                  <div className="text-[9px] text-gray-500 mt-0.5">{a.agent_id}</div>
                  <div className="text-[9px] text-gray-500 truncate">{a.description}</div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Detail */}
        <div className="flex-1 min-w-0">
          {!selected ? (
            <div className="text-[11px] text-gray-500 py-12 text-center">
              选择左侧 Agent 查看详情
            </div>
          ) : (
            <div className="space-y-4">
              <div className="bg-gray-900/50 border border-gray-700 rounded-sm p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[13px] text-gray-200">{selected.name}</span>
                  <span className={`text-[9px] px-2 py-0.5 rounded-sm border ${
                    selected.status === "active"
                      ? "text-green-400 border-green-600/30"
                      : "text-gray-400 border-gray-600/30"
                  }`}>
                    {selected.status}
                  </span>
                </div>
                <div className="text-[10px] text-gray-400">{selected.description}</div>
                <div className="flex gap-4 mt-2 text-[9px] text-gray-500">
                  <span>ID: {selected.agent_id}</span>
                  <span>版本: {selected.version}</span>
                </div>
              </div>

              {/* Prompt template editor */}
              <div className="bg-gray-900/50 border border-gray-700 rounded-sm p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] text-cyan-400/80">Prompt 模板</span>
                  {!editing ? (
                    <button
                      onClick={() => setEditing(true)}
                      className="text-[9px] text-gray-400 hover:text-white border border-gray-600 px-2 py-0.5 rounded-sm"
                    >
                      编辑
                    </button>
                  ) : (
                    <div className="flex gap-2">
                      <button
                        onClick={handleSave}
                        disabled={saving}
                        className="text-[9px] text-cyan-400 hover:text-cyan-300 border border-cyan-600/50 px-2 py-0.5 rounded-sm disabled:opacity-50"
                      >
                        {saving ? "保存中..." : "保存"}
                      </button>
                      <button
                        onClick={() => { setEditing(false); setPromptDraft(selected.prompt_template || ""); }}
                        className="text-[9px] text-gray-400 hover:text-white border border-gray-600 px-2 py-0.5 rounded-sm"
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
                    rows={8}
                    className="w-full bg-gray-800 border border-gray-600 rounded-sm px-3 py-2 text-[10px] text-gray-300
                               focus:outline-none focus:border-cyan-500 resize-y"
                    placeholder="在此输入 Agent 的 prompt 模板..."
                  />
                ) : (
                  <pre className="text-[10px] text-gray-400 bg-gray-800/50 p-3 rounded-sm min-h-[60px] whitespace-pre-wrap">
                    {selected.prompt_template || "(未配置)"}
                  </pre>
                )}
                {message && (
                  <div className={`mt-2 text-[9px] ${message.includes("成功") ? "text-green-400" : "text-red-400"}`}>
                    {message}
                  </div>
                )}
              </div>

              {/* Model config */}
              <div className="bg-gray-900/50 border border-gray-700 rounded-sm p-4">
                <span className="text-[10px] text-cyan-400/80">模型配置</span>
                <pre className="mt-2 text-[9px] text-gray-400 bg-gray-800/50 p-3 rounded-sm">
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
