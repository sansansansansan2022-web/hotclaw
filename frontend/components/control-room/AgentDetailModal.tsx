"use client";

import { useEffect, useRef } from "react";
import type { AgentDisplayInfo } from "./AgentMonitor";
import type { NodeStatus } from "@/types";

interface AgentDetailModalProps {
  agent: AgentDisplayInfo | null;
  onClose: () => void;
  taskId: string | null;
}

const STATUS_LABELS: Record<NodeStatus, { text: string; color: string }> = {
  pending: { text: "等待中", color: "var(--cr-gray)" },
  running: { text: "执行中", color: "var(--cr-green)" },
  completed: { text: "已完成", color: "var(--cr-accent)" },
  failed: { text: "异常", color: "var(--cr-red)" },
  skipped: { text: "已跳过", color: "var(--cr-gray)" },
};

export default function AgentDetailModal({ agent, onClose, taskId }: AgentDetailModalProps) {
  const backdropRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    if (agent) {
      document.addEventListener("keydown", handleKey);
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.removeEventListener("keydown", handleKey);
      document.body.style.overflow = "";
    };
  }, [agent, onClose]);

  if (!agent) return null;

  const statusInfo = STATUS_LABELS[agent.status] || STATUS_LABELS.pending;
  const isRunning = agent.status === "running";

  return (
    <div
      ref={backdropRef}
      onClick={(e) => { if (e.target === backdropRef.current) onClose(); }}
      style={{
        position: "fixed", inset: 0, zIndex: 50,
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: 24, animation: "cr-fade-in 0.2s ease forwards",
      }}
    >
      <div style={{ position: "absolute", inset: 0, background: "rgba(8, 12, 24, 0.85)", backdropFilter: "blur(8px)" }} />

      <div
        style={{
          position: "relative", width: "100%", maxWidth: 500, borderRadius: 16,
          border: "1px solid var(--cr-border-light)", background: "var(--cr-bg-surface)",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.7)",
          animation: "cr-slide-up 0.3s cubic-bezier(0.4, 0, 0.2, 1) forwards",
          overflow: "hidden",
        }}
      >
        <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 1, background: "linear-gradient(90deg, transparent, rgba(0, 229, 255, 0.2), transparent)" }} />

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 20px", borderBottom: "1px solid var(--cr-border)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: 24 }}>{agent.icon}</span>
            <div>
              <h2 style={{ fontSize: 15, fontWeight: 600, color: "var(--cr-text-primary)", margin: 0 }}>{agent.name}</h2>
              <p style={{ fontSize: 11, color: "var(--cr-text-muted)", fontFamily: "var(--cr-font-mono)", marginTop: 2 }}>{agent.agent_id}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              width: 32, height: 32, borderRadius: 8, border: "none",
              background: "transparent", color: "var(--cr-text-muted)", cursor: "pointer",
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16,
            }}
          >
            ✕
          </button>
        </div>

        <div style={{ padding: 20 }}>
          <div style={{ display: "flex", gap: 32, marginBottom: 20 }}>
            <div>
              <span style={{ fontSize: 10, color: "var(--cr-text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", display: "block", marginBottom: 4, fontFamily: "var(--cr-font-mono)" }}>状态</span>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span className={`cr-dot ${agent.status}`} />
                <span style={{ fontSize: 13, fontWeight: 500, color: statusInfo.color, fontFamily: "var(--cr-font-mono)" }}>{statusInfo.text}</span>
              </div>
            </div>
            {agent.elapsed_seconds !== null && (
              <div>
                <span style={{ fontSize: 10, color: "var(--cr-text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", display: "block", marginBottom: 4, fontFamily: "var(--cr-font-mono)" }}>耗时</span>
                <span style={{ fontSize: 13, color: "var(--cr-text-primary)", fontFamily: "var(--cr-font-mono)" }}>{agent.elapsed_seconds.toFixed(1)}s</span>
              </div>
            )}
            {taskId && (
              <div>
                <span style={{ fontSize: 10, color: "var(--cr-text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", display: "block", marginBottom: 4, fontFamily: "var(--cr-font-mono)" }}>任务</span>
                <span style={{ fontSize: 11, color: "var(--cr-accent)", fontFamily: "var(--cr-font-mono)" }}>{taskId.slice(0, 12)}…</span>
              </div>
            )}
          </div>

          <div style={{ marginBottom: 16 }}>
            <span style={{ fontSize: 10, color: "var(--cr-text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", display: "block", marginBottom: 4, fontFamily: "var(--cr-font-mono)" }}>功能描述</span>
            <p style={{ fontSize: 13, color: "var(--cr-text-secondary)", lineHeight: 1.6 }}>{agent.description}</p>
          </div>

          {agent.output_summary && (
            <div style={{ marginBottom: 16 }}>
              <span style={{ fontSize: 10, color: "var(--cr-text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", display: "block", marginBottom: 4, fontFamily: "var(--cr-font-mono)" }}>输出摘要</span>
              <div className="cr-console has-output" style={{ maxHeight: 180, overflowY: "auto" }}>{agent.output_summary}</div>
            </div>
          )}

          {agent.error && (
            <div>
              <span style={{ fontSize: 10, color: "var(--cr-red)", textTransform: "uppercase", letterSpacing: "0.08em", display: "block", marginBottom: 4, fontFamily: "var(--cr-font-mono)" }}>错误信息</span>
              <div className="cr-console has-error">{agent.error}</div>
            </div>
          )}

          {isRunning && (
            <div style={{ marginTop: 16, height: 2, borderRadius: 1, background: "var(--cr-border)", overflow: "hidden", position: "relative" }}>
              <div style={{ position: "absolute", inset: 0, background: "linear-gradient(90deg, transparent, var(--cr-green), transparent)", backgroundSize: "200% 100%", animation: "cr-data-flow 1.5s linear infinite" }} />
            </div>
          )}
        </div>

        <div style={{ padding: "12px 20px", borderTop: "1px solid var(--cr-border)", display: "flex", justifyContent: "flex-end", gap: 10 }}>
          {taskId && agent.status === "completed" && (
            <a href={`/task/${taskId}`} style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "6px 14px", borderRadius: 8, background: "rgba(0, 229, 255, 0.1)", color: "var(--cr-accent)", fontSize: 12, fontWeight: 500, textDecoration: "none" }}>
              查看详细结果 →
            </a>
          )}
          <button onClick={onClose} style={{ padding: "6px 14px", borderRadius: 8, border: "none", background: "var(--cr-bg-elevated)", color: "var(--cr-text-secondary)", fontSize: 12, fontWeight: 500, cursor: "pointer" }}>
            关闭
          </button>
        </div>
      </div>
    </div>
  );
}
