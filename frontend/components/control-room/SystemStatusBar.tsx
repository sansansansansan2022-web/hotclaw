"use client";

import { useState, useEffect } from "react";

interface SystemStatusBarProps {
  isConnected: boolean;
  taskId: string | null;
  completedCount: number;
  totalCount: number;
  taskDone: boolean;
  taskError: string | null;
}

export default function SystemStatusBar({
  isConnected, taskId, completedCount, totalCount, taskDone, taskError,
}: SystemStatusBarProps) {
  const [time, setTime] = useState("");

  useEffect(() => {
    function tick() {
      const now = new Date();
      setTime(
        `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")} ${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")}`
      );
    }
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, []);

  const progress = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  return (
    <div
      style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "6px 24px", background: "rgba(12, 17, 32, 0.9)",
        borderTop: "1px solid var(--cr-border)", backdropFilter: "blur(8px)",
        fontFamily: "var(--cr-font-mono)", fontSize: 11,
        position: "sticky", bottom: 0, zIndex: 20,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span className={`cr-dot ${isConnected ? "running" : taskDone ? "completed" : "pending"}`} />
          <span style={{ color: "var(--cr-text-muted)" }}>
            {isConnected ? "SSE 实时连接" : taskDone ? "任务完成" : "待命"}
          </span>
        </div>
        {taskId && (
          <span style={{ color: "var(--cr-text-muted)" }}>
            ID: <span style={{ color: "var(--cr-accent)" }}>{taskId.slice(0, 8)}</span>
          </span>
        )}
        {taskError && <span style={{ color: "var(--cr-red)" }}>ERR: {taskError}</span>}
      </div>

      {taskId && (
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 120, height: 3, background: "var(--cr-bg-elevated)", borderRadius: 2, overflow: "hidden", position: "relative" }}>
            <div style={{ position: "absolute", top: 0, left: 0, bottom: 0, width: `${progress}%`, background: "linear-gradient(90deg, var(--cr-accent-dim), var(--cr-accent))", borderRadius: 2, transition: "width 0.5s ease" }} />
          </div>
          <span style={{ color: "var(--cr-text-muted)", fontVariantNumeric: "tabular-nums" }}>{completedCount}/{totalCount}</span>
        </div>
      )}

      <span style={{ color: "var(--cr-text-muted)", fontVariantNumeric: "tabular-nums" }}>{time}</span>
    </div>
  );
}
