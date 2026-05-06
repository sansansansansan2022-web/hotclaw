/** AgentSettingsDrawer: right-side panel for editing agent prompt & config. */

"use client";

import { useState, useEffect, useCallback } from "react";
import Image from "next/image";
import { getAgent, updateAgentConfig } from "@/lib/api";
import { SPRITES } from "@/lib/assets";

interface Props {
  agentId: string;
  open: boolean;
  onClose: () => void;
}

export default function AgentSettingsDrawer({ agentId, open, onClose }: Props) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [promptTemplate, setPromptTemplate] = useState("");
  const [defaultPrompt, setDefaultPrompt] = useState("");
  const [promptSource, setPromptSource] = useState("default");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  const loadAgent = useCallback(async () => {
    if (!agentId) return;
    setLoading(true);
    setMessage("");
    try {
      const data = await getAgent(agentId);
      setName(data.name);
      setDescription(data.description || "");
      setPromptTemplate(data.prompt_template || "");
      setDefaultPrompt(data.default_system_prompt || "");
      setPromptSource(data.prompt_source || "default");
    } catch {
      setMessage("加载失败");
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    if (open && agentId) loadAgent();
  }, [open, agentId, loadAgent]);

  async function handleSave() {
    setSaving(true);
    setMessage("");
    try {
      await updateAgentConfig(agentId, { prompt_template: promptTemplate });
      setPromptSource(promptTemplate.trim() ? "custom" : "default");
      setMessage("保存成功");
    } catch {
      setMessage("保存失败");
    } finally {
      setSaving(false);
    }
  }

  function handleResetDefault() {
    setPromptTemplate(defaultPrompt);
  }

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/40 z-40" onClick={onClose} />

      {/* Drawer */}
      <div className="fixed right-0 top-0 h-full w-[400px] z-50 pixel-border-pink bg-[#1a1a3e] overflow-y-auto
                      animate-[slide-in-right_0.2s_ease-out]">
        {/* Header */}
        <div className="bg-[#2a2a5a] px-4 py-3 flex items-center justify-between border-b border-[#6b4f10]">
          <div className="flex items-center gap-2">
            <Image
              src={SPRITES.agentIdle}
              alt={name}
              width={28}
              height={28}
              className="pixelated"
              style={{ imageRendering: "pixelated" }}
              unoptimized
            />
            <div>
              <div className="text-[13px] font-mono text-yellow-400 font-bold">Agent Settings</div>
              <div className="text-[9px] font-mono text-gray-400">{agentId}</div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white text-[14px] font-mono px-2"
          >
            ✕
          </button>
        </div>

        {loading ? (
          <div className="p-6 text-center text-[11px] font-mono text-gray-500">加载中...</div>
        ) : (
          <div className="p-4 space-y-4">
            {/* Agent info */}
            <div className="space-y-2">
              <div className="text-[10px] font-mono text-cyan-400/80 border-b border-gray-600/30 pb-1">
                基本信息
              </div>
              <div className="text-[11px] font-mono text-gray-200">{name}</div>
              <div className="text-[9px] font-mono text-gray-400">{description}</div>
            </div>

            {/* Prompt editor */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="text-[10px] font-mono text-cyan-400/80">
                  System Prompt
                  <span className={`ml-2 px-1.5 py-0.5 rounded-sm text-[8px] ${
                    promptSource === "custom"
                      ? "bg-yellow-900/30 text-yellow-400 border border-yellow-700/30"
                      : "bg-gray-700/30 text-gray-400 border border-gray-600/30"
                  }`}>
                    {promptSource === "custom" ? "自定义" : "默认"}
                  </span>
                </div>
                <button
                  onClick={handleResetDefault}
                  className="text-[8px] font-mono text-gray-500 hover:text-gray-300 border border-gray-600 px-1.5 py-0.5 rounded-sm"
                >
                  恢复默认
                </button>
              </div>
              <textarea
                value={promptTemplate}
                onChange={(e) => setPromptTemplate(e.target.value)}
                rows={14}
                className="w-full bg-[#0a0a1e] border border-gray-600 rounded-sm px-3 py-2 text-[10px] font-mono
                           text-gray-300 focus:outline-none focus:border-cyan-500 resize-y"
                placeholder="输入 Agent 的 system prompt..."
              />
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2">
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-4 py-1.5 bg-cyan-700 hover:bg-cyan-600 text-[10px] font-mono text-white
                           rounded-sm disabled:opacity-50 transition-colors"
              >
                {saving ? "保存中..." : "保存"}
              </button>
              <button
                onClick={onClose}
                className="px-4 py-1.5 border border-gray-600 text-[10px] font-mono text-gray-300
                           hover:text-white rounded-sm transition-colors"
              >
                取消
              </button>
              {message && (
                <span className={`text-[9px] font-mono ${
                  message.includes("成功") ? "text-green-400" : "text-red-400"
                }`}>
                  {message}
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
