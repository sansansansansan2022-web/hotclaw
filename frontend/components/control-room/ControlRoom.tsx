"use client";

import { useState, useCallback, useEffect } from "react";
import { useTaskSSE } from "@/hooks/useTaskSSE";
import { createTask, getTaskDetail } from "@/lib/api";
import type { NodeState } from "@/hooks/useTaskSSE";
import AgentMonitor, { type AgentDisplayInfo } from "./AgentMonitor";
import PipelineFlow from "./PipelineFlow";
import AgentDetailModal from "./AgentDetailModal";
import SystemStatusBar from "./SystemStatusBar";

const AGENT_META: Record<string, { icon: string; description: string }> = {
  profile_parsing: {
    icon: "📡",
    description: "解析用户输入的账号定位，提取领域关键词，生成结构化画像数据。",
  },
  hot_topic_analysis: {
    icon: "🔥",
    description: "多搜索引擎并发抓取热点话题，分析与账号领域的相关度和时效性。",
  },
  topic_planning: {
    icon: "💡",
    description: "基于热点和账号画像，策划 3-5 个选题方向，评估吸引力与可行性。",
  },
  title_generation: {
    icon: "✏️",
    description: "为每个选题生成多个候选标题，结合多种标题策略，预测点击率。",
  },
  content_writing: {
    icon: "📄",
    description: "按照选定标题与大纲，撰写 1500-3000 字结构化文章正文。",
  },
  audit: {
    icon: "🛡️",
    description: "对生成内容进行合规性检查、风险等级评估、质量评分与建议。",
  },
};

export default function ControlRoom() {
  const [positioning, setPositioning] = useState("");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<AgentDisplayInfo | null>(null);
  const [resultData, setResultData] = useState<Record<string, unknown> | null>(null);

  const { nodes, taskDone, taskError, isConnected, reset } = useTaskSSE(taskId);

  const fetchResult = useCallback(async (tid: string) => {
    try {
      const detail = await getTaskDetail(tid);
      if (detail.result_data) setResultData(detail.result_data);
    } catch { /* non-critical */ }
  }, []);

  useEffect(() => {
    if (taskDone && taskId && !resultData) fetchResult(taskId);
  }, [taskDone, taskId, resultData, fetchResult]);

  async function handleCreateTask() {
    if (!positioning.trim()) return;
    setLoading(true);
    setResultData(null);
    reset();
    try {
      const data = await createTask(positioning);
      setTaskId(data.task_id);
    } catch (err) {
      alert(err instanceof Error ? err.message : "创建任务失败");
    } finally {
      setLoading(false);
    }
  }

  function handleReset() {
    setTaskId(null);
    setResultData(null);
    setPositioning("");
    setSelectedAgent(null);
    reset();
  }

  const agents: AgentDisplayInfo[] = nodes.map((node: NodeState, index: number) => {
    const meta = AGENT_META[node.node_id] || { icon: "🤖", description: "" };
    return {
      node_id: node.node_id,
      agent_id: node.agent_id,
      name: node.name,
      description: meta.description,
      icon: meta.icon,
      status: node.status,
      output_summary: node.output_summary,
      error: node.error,
      elapsed_seconds: node.elapsed_seconds,
      index,
    };
  });

  const completedCount = nodes.filter((n) => n.status === "completed").length;

  return (
    <div className="cr-grid-bg" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      {/* ── Header ── */}
      <header
        style={{
          position: "relative",
          zIndex: 10,
          padding: "12px 24px",
          borderBottom: "1px solid var(--cr-border)",
          background: "rgba(12, 17, 32, 0.85)",
          backdropFilter: "blur(12px)",
        }}
      >
        <div style={{ maxWidth: 1200, margin: "0 auto", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            {/* Logo */}
            <div
              style={{
                width: 36, height: 36, borderRadius: 8,
                background: "linear-gradient(135deg, var(--cr-accent-dim), var(--cr-accent))",
                display: "flex", alignItems: "center", justifyContent: "center",
                color: "var(--cr-bg-deep)", fontWeight: 700, fontSize: 13,
                fontFamily: "var(--cr-font-mono)",
                boxShadow: "0 0 20px -5px rgba(0, 229, 255, 0.3)",
              }}
            >
              HC
            </div>
            <div>
              <h1 style={{ fontSize: 16, fontWeight: 600, color: "var(--cr-text-primary)", margin: 0, lineHeight: 1.2 }}>
                HotClaw 控制中心
              </h1>
              <p style={{ fontSize: 10, color: "var(--cr-text-muted)", fontFamily: "var(--cr-font-mono)", letterSpacing: "0.15em", textTransform: "uppercase", marginTop: 1 }}>
                Agent Orchestration Console
              </p>
            </div>
          </div>

          <nav style={{ display: "flex", alignItems: "center", gap: 4 }}>
            {[
              { href: "/history", label: "历史任务" },
              { href: "/settings/agents", label: "智能体设置" },
              { href: "/settings/llm-providers", label: "LLM 配置" },
            ].map(({ href, label }) => (
              <a
                key={href}
                href={href}
                style={{
                  padding: "6px 12px",
                  borderRadius: 6,
                  fontSize: 12,
                  color: "var(--cr-text-secondary)",
                  textDecoration: "none",
                  fontFamily: "var(--cr-font-mono)",
                  transition: "all 0.15s ease",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "var(--cr-bg-elevated)";
                  e.currentTarget.style.color = "var(--cr-text-primary)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "transparent";
                  e.currentTarget.style.color = "var(--cr-text-secondary)";
                }}
              >
                {label}
              </a>
            ))}
          </nav>
        </div>
      </header>

      {/* ── Main ── */}
      <main style={{ flex: 1, position: "relative", zIndex: 1 }}>
        <div style={{ maxWidth: 1200, margin: "0 auto", padding: "32px 24px" }}>

          {/* Task Input */}
          <div
            style={{
              borderRadius: 16,
              border: "1px solid var(--cr-border-light)",
              background: "linear-gradient(180deg, #131b2e, #0e1524)",
              padding: 24,
              marginBottom: 32,
              boxShadow: "0 4px 24px -4px rgba(0, 0, 0, 0.5)",
              position: "relative",
              overflow: "hidden",
            }}
          >
            {/* Top accent line */}
            <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 1, background: "linear-gradient(90deg, transparent, rgba(0, 229, 255, 0.15), transparent)" }} />

            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
              <div style={{ width: 24, height: 24, borderRadius: 12, background: "rgba(0, 229, 255, 0.1)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M6 1V11M1 6H11" stroke="var(--cr-accent)" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              </div>
              <h2 style={{ fontSize: 14, fontWeight: 500, color: "var(--cr-text-primary)", margin: 0 }}>创建创作任务</h2>
            </div>

            <div style={{ display: "flex", gap: 12 }}>
              <textarea
                value={positioning}
                onChange={(e) => setPositioning(e.target.value)}
                placeholder="描述你的公众号定位，例如：关注职场成长的公众号，目标读者 25-35 岁互联网从业者"
                disabled={loading || !!taskId}
                rows={2}
                style={{
                  flex: 1, padding: "12px 16px", borderRadius: 10,
                  border: "1px solid var(--cr-border)",
                  background: "rgba(8, 12, 24, 0.6)",
                  color: "var(--cr-text-primary)", fontSize: 14,
                  fontFamily: "var(--cr-font-sans)", resize: "none",
                  outline: "none", transition: "all 0.25s ease",
                }}
                onFocus={(e) => { e.currentTarget.style.borderColor = "var(--cr-accent-dim)"; e.currentTarget.style.boxShadow = "0 0 0 2px rgba(0, 229, 255, 0.1)"; }}
                onBlur={(e) => { e.currentTarget.style.borderColor = "var(--cr-border)"; e.currentTarget.style.boxShadow = "none"; }}
              />
              <div style={{ display: "flex", flexDirection: "column", gap: 8, flexShrink: 0 }}>
                <button
                  onClick={handleCreateTask}
                  disabled={loading || !positioning.trim() || !!taskId}
                  style={{
                    padding: "12px 24px", borderRadius: 10, border: "none",
                    background: "linear-gradient(135deg, var(--cr-accent-dim), var(--cr-accent))",
                    color: "var(--cr-bg-deep)", fontSize: 14, fontWeight: 600,
                    cursor: loading || !positioning.trim() || !!taskId ? "not-allowed" : "pointer",
                    opacity: loading || !positioning.trim() || !!taskId ? 0.4 : 1,
                    transition: "all 0.25s ease",
                    boxShadow: "0 0 20px -5px rgba(0, 229, 255, 0.3)",
                    fontFamily: "var(--cr-font-sans)",
                  }}
                >
                  {loading ? "创建中..." : "启动任务"}
                </button>
                {taskId && (
                  <button
                    onClick={handleReset}
                    style={{
                      padding: "8px 24px", borderRadius: 10, border: "none",
                      background: "var(--cr-bg-elevated)", color: "var(--cr-text-secondary)",
                      fontSize: 12, fontWeight: 500, cursor: "pointer",
                      transition: "all 0.15s ease",
                    }}
                  >
                    重置
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Pipeline Flow */}
          {taskId && (
            <div
              style={{
                borderRadius: 16,
                border: "1px solid var(--cr-border-light)",
                background: "linear-gradient(180deg, #131b2e, #0e1524)",
                marginBottom: 24,
                boxShadow: "0 4px 24px -4px rgba(0, 0, 0, 0.5)",
                overflow: "hidden",
                animation: "cr-slide-up 0.4s cubic-bezier(0.4, 0, 0.2, 1) forwards",
              }}
            >
              <div
                style={{
                  padding: "10px 20px",
                  borderBottom: "1px solid var(--cr-border)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <span style={{ fontSize: 11, color: "var(--cr-text-muted)", fontFamily: "var(--cr-font-mono)", letterSpacing: "0.1em", textTransform: "uppercase" }}>
                  Pipeline Flow
                </span>
                {taskDone && (
                  <a href={`/task/${taskId}`} style={{ fontSize: 11, color: "var(--cr-accent)", fontFamily: "var(--cr-font-mono)", textDecoration: "none" }}>
                    查看完整结果 →
                  </a>
                )}
              </div>
              <PipelineFlow
                nodes={agents.map((a) => ({ node_id: a.node_id, name: a.name, status: a.status, icon: a.icon }))}
              />
            </div>
          )}

          {/* Agent Monitor Grid */}
          <div style={{ marginBottom: 24 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
              <h2 style={{ fontSize: 14, fontWeight: 500, color: "var(--cr-text-primary)", margin: 0 }}>智能体监控面板</h2>
              <span
                style={{
                  fontSize: 10, color: "var(--cr-text-muted)",
                  padding: "2px 8px", borderRadius: 100,
                  background: "var(--cr-bg-elevated)",
                  fontFamily: "var(--cr-font-mono)",
                }}
              >
                {agents.length} AGENTS
              </span>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))",
                gap: 16,
              }}
            >
              {agents.map((agent) => (
                <AgentMonitor key={agent.node_id} agent={agent} onClick={setSelectedAgent} />
              ))}
            </div>
          </div>

          {/* Result Preview */}
          {resultData != null && taskDone && (
            <div
              style={{
                borderRadius: 16,
                border: "1px solid var(--cr-border-light)",
                background: "linear-gradient(180deg, #131b2e, #0e1524)",
                padding: 24,
                boxShadow: "0 4px 24px -4px rgba(0, 0, 0, 0.5)",
                animation: "cr-slide-up 0.4s cubic-bezier(0.4, 0, 0.2, 1) forwards",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                <h2 style={{ fontSize: 14, fontWeight: 500, color: "var(--cr-text-primary)", margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ width: 20, height: 20, borderRadius: 10, background: "rgba(0, 229, 255, 0.1)", display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: 10, color: "var(--cr-accent)" }}>✓</span>
                  任务产出概览
                </h2>
                <a href={`/task/${taskId}`} style={{ fontSize: 11, color: "var(--cr-accent)", fontFamily: "var(--cr-font-mono)", textDecoration: "none" }}>
                  查看完整详情 →
                </a>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 12 }}>
                {resultData.profile != null ? <ResultCard label="账号画像" value={(resultData.profile as Record<string, string>).domain || "已生成"} color="var(--cr-accent)" /> : null}
                {resultData.hot_topics != null ? <ResultCard label="热点话题" value={`${((resultData.hot_topics as Record<string, unknown[]>).hot_topics || []).length} 条`} color="var(--cr-red)" /> : null}
                {resultData.topics != null ? <ResultCard label="选题方向" value={`${((resultData.topics as Record<string, unknown[]>).topics || []).length} 个`} color="var(--cr-green)" /> : null}
                {resultData.content != null ? <ResultCard label="文章正文" value={`${(resultData.content as Record<string, number>).word_count || 0} 字`} color="var(--cr-accent)" /> : null}
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Bottom Status Bar */}
      <SystemStatusBar
        isConnected={isConnected}
        taskId={taskId}
        completedCount={completedCount}
        totalCount={agents.length}
        taskDone={taskDone}
        taskError={taskError}
      />

      {/* Modal */}
      <AgentDetailModal agent={selectedAgent} onClose={() => setSelectedAgent(null)} taskId={taskId} />
    </div>
  );
}

function ResultCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div
      style={{
        borderRadius: 10, border: "1px solid var(--cr-border)",
        background: "rgba(8, 12, 24, 0.5)", padding: "12px 16px",
      }}
    >
      <span style={{ fontSize: 10, color: "var(--cr-text-muted)", fontFamily: "var(--cr-font-mono)", textTransform: "uppercase", letterSpacing: "0.08em", display: "block", marginBottom: 4 }}>
        {label}
      </span>
      <span style={{ fontSize: 20, fontWeight: 600, color, fontFamily: "var(--cr-font-mono)" }}>
        {value}
      </span>
    </div>
  );
}
