"use client";

import Link from "next/link";
import { useTaskStore } from "@/store/taskStore";
import { useTaskSSE } from "@/hooks/useTaskSSE";

export default function TaskStatusBanner() {
  const { activeTaskId } = useTaskStore();
  
  // 如果没有活跃任务，不显示
  if (!activeTaskId) return null;
  
  const { nodes, taskDone } = useTaskSSE(activeTaskId);
  
  // 任务已完成，显示完成提示
  if (taskDone) {
    return (
      <div
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          zIndex: 1000,
          background: "linear-gradient(90deg, #059669, #10b981)",
          color: "white",
          padding: "8px 16px",
          fontSize: 12,
          fontFamily: "var(--cc-font-mono, monospace)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <span>✅ 任务已完成</span>
        <Link
          href={`/newsroom?taskId=${activeTaskId}`}
          style={{
            color: "white",
            textDecoration: "underline",
          }}
        >
          返回编辑部查看
        </Link>
      </div>
    );
  }
  
  const completed = nodes.filter((n) => n.status === "completed").length;
  const total = nodes.length || 6;
  const percent = Math.round((completed / total) * 100);
  
  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        zIndex: 1000,
        background: "linear-gradient(90deg, #1e3a5f, #2563eb)",
        color: "white",
        padding: "8px 16px",
        fontSize: 12,
        fontFamily: "var(--cc-font-mono, monospace)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <span style={{ animation: "pulse 2s infinite" }}>⚡</span>
        <span>任务执行中</span>
        <span style={{ opacity: 0.7 }}>
          {completed}/{total} 节点已完成 ({percent}%)
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div
          style={{
            width: 100,
            height: 4,
            background: "rgba(255,255,255,0.2)",
            borderRadius: 2,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              width: `${percent}%`,
              height: "100%",
              background: "#10b981",
              transition: "width 0.3s",
            }}
          />
        </div>
        <Link
          href={`/newsroom?taskId=${activeTaskId}`}
          style={{
            color: "white",
            textDecoration: "underline",
          }}
        >
          返回编辑部
        </Link>
      </div>
      <style jsx global>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  );
}
