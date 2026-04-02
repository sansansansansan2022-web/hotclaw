"use client";

import { type NodeStatus } from "@/types";

export interface AgentDisplayInfo {
  node_id: string;
  agent_id: string;
  name: string;
  description: string;
  icon: string;
  status: NodeStatus;
  output_summary: string;
  error: string | null;
  elapsed_seconds: number | null;
  index: number;
}

interface AgentMonitorProps {
  agent: AgentDisplayInfo;
  onClick: (agent: AgentDisplayInfo) => void;
}

const STATUS_LABEL: Record<NodeStatus, string> = {
  pending: "STANDBY",
  running: "ACTIVE",
  completed: "DONE",
  failed: "ERROR",
  skipped: "SKIP",
};

export default function AgentMonitor({ agent, onClick }: AgentMonitorProps) {
  const isRunning = agent.status === "running";
  const isCompleted = agent.status === "completed";
  const isFailed = agent.status === "failed";

  const monitorClass = [
    "cr-monitor",
    isRunning ? "is-running" : "",
    isCompleted ? "is-completed" : "",
    isFailed ? "is-failed" : "",
  ].filter(Boolean).join(" ");

  return (
    <button
      onClick={() => onClick(agent)}
      className={monitorClass}
      style={{
        animation: `cr-slide-up 0.5s cubic-bezier(0.4, 0, 0.2, 1) ${agent.index * 80}ms both`,
        textAlign: "left",
        width: "100%",
        display: "block",
      }}
    >
      {/* Header: icon + name + badge */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div
            style={{
              width: 42,
              height: 42,
              borderRadius: 10,
              background: "var(--cr-bg-elevated)",
              border: `1px solid ${isRunning ? "rgba(34, 197, 94, 0.3)" : isCompleted ? "rgba(0, 229, 255, 0.2)" : "var(--cr-border)"}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 20,
              transition: "all 0.3s ease",
              boxShadow: isRunning
                ? "0 0 15px -3px rgba(34, 197, 94, 0.3)"
                : isCompleted
                ? "0 0 10px -3px rgba(0, 229, 255, 0.2)"
                : "none",
            }}
          >
            {agent.icon}
          </div>
          <div>
            <h3
              style={{
                fontSize: 14,
                fontWeight: 600,
                color: "var(--cr-text-primary)",
                lineHeight: 1.3,
                fontFamily: "var(--cr-font-sans)",
                margin: 0,
              }}
            >
              {agent.name}
            </h3>
            <p
              style={{
                fontSize: 11,
                color: "var(--cr-text-muted)",
                fontFamily: "var(--cr-font-mono)",
                marginTop: 2,
              }}
            >
              {agent.agent_id}
            </p>
          </div>
        </div>

        <div className={`cr-badge ${agent.status}`}>
          <span className={`cr-dot ${agent.status}`} />
          {STATUS_LABEL[agent.status]}
        </div>
      </div>

      <p
        style={{
          fontSize: 12,
          color: "var(--cr-text-secondary)",
          lineHeight: 1.6,
          marginBottom: 14,
        }}
      >
        {agent.description}
      </p>

      <div
        className={[
          "cr-console",
          isFailed && agent.error ? "has-error" : "",
          isCompleted && agent.output_summary ? "has-output" : "",
        ].filter(Boolean).join(" ")}
      >
        {isRunning && (
          <span style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--cr-green)" }}>
            <span
              style={{
                width: 12,
                height: 12,
                borderRadius: "50%",
                border: "2px solid var(--cr-green)",
                borderTopColor: "transparent",
                animation: "cr-spin 0.8s linear infinite",
                flexShrink: 0,
              }}
            />
            Processing...
          </span>
        )}
        {isFailed && agent.error && (
          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {agent.error}
          </span>
        )}
        {isCompleted && agent.output_summary && (
          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {agent.output_summary}
          </span>
        )}
        {agent.status === "pending" && "Awaiting upstream..."}
        {agent.status === "skipped" && "— skipped —"}
      </div>

      {agent.elapsed_seconds !== null && isCompleted && (
        <div style={{ marginTop: 8, textAlign: "right" }}>
          <span
            style={{
              fontSize: 10,
              color: "var(--cr-text-muted)",
              fontFamily: "var(--cr-font-mono)",
            }}
          >
            ⏱ {agent.elapsed_seconds.toFixed(1)}s
          </span>
        </div>
      )}
    </button>
  );
}
