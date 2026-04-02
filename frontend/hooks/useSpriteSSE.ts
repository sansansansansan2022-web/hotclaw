"use client";

import { useEffect, useCallback, useState } from "react";
import { getTaskStreamUrl } from "@/lib/api";

// 节点状态
export type SpriteStatus = "pending" | "running" | "completed" | "failed" | "skipped";

// 精灵体状态接口
export interface SpriteState {
  node_id: string;
  agent_id: string;
  name: string;
  status: SpriteStatus;
  output_summary: string;
  error: string | null;
}

// 节点名称映射
const NODE_NAMES: Record<string, string> = {
  profile_parsing: "账号定位解析",
  hot_topic_analysis: "热点分析",
  topic_planning: "选题策划",
  title_generation: "标题生成",
  content_writing: "正文生成",
  audit: "审核",
};

// 初始节点状态
const INITIAL_SPRITES: Omit<SpriteState, "output_summary" | "error">[] = [
  { node_id: "profile_parsing", agent_id: "profile_agent", name: "账号定位解析", status: "pending" },
  { node_id: "hot_topic_analysis", agent_id: "hot_topic_agent", name: "热点分析", status: "pending" },
  { node_id: "topic_planning", agent_id: "topic_planner_agent", name: "选题策划", status: "pending" },
  { node_id: "title_generation", agent_id: "title_generator_agent", name: "标题生成", status: "pending" },
  { node_id: "content_writing", agent_id: "content_writer_agent", name: "正文生成", status: "pending" },
  { node_id: "audit", agent_id: "audit_agent", name: "审核", status: "pending" },
];

// SSE 钩子接口
export interface UseSpriteSSEResult {
  sprites: SpriteState[];
  taskDone: boolean;
  taskError: string | null;
  isConnected: boolean;
  reset: () => void;
}

// 精灵体 SSE 钩子
export function useSpriteSSE(taskId: string | null): UseSpriteSSEResult {
  const [sprites, setSprites] = useState<SpriteState[]>(
    INITIAL_SPRITES.map((n) => ({ ...n, output_summary: "", error: null }))
  );
  const [taskDone, setTaskDone] = useState(false);
  const [taskError, setTaskError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  const reset = useCallback(() => {
    setSprites(INITIAL_SPRITES.map((n) => ({ ...n, output_summary: "", error: null })));
    setTaskDone(false);
    setTaskError(null);
    setIsConnected(false);
  }, []);

  useEffect(() => {
    if (!taskId) {
      reset();
      return;
    }

    reset();
    setIsConnected(true);

    const es = new EventSource(getTaskStreamUrl(taskId));

    es.addEventListener("node_start", (e) => {
      const data = JSON.parse(e.data);
      const nodeName = NODE_NAMES[data.node_id] || data.node_id;
      setSprites((prev) =>
        prev.map((s) =>
          s.node_id === data.node_id
            ? { ...s, status: "running" as SpriteStatus, name: nodeName }
            : s
        )
      );
    });

    es.addEventListener("node_complete", (e) => {
      const data = JSON.parse(e.data);
      setSprites((prev) =>
        prev.map((s) =>
          s.node_id === data.node_id
            ? {
                ...s,
                status: "completed" as SpriteStatus,
                output_summary: data.output_summary || "",
              }
            : s
        )
      );
    });

    es.addEventListener("node_error", (e) => {
      const data = JSON.parse(e.data);
      setSprites((prev) =>
        prev.map((s) =>
          s.node_id === data.node_id
            ? { ...s, status: "failed" as SpriteStatus, error: data.error }
            : s
        )
      );
    });

    es.addEventListener("task_complete", () => {
      setTaskDone(true);
      setIsConnected(false);
      es.close();
    });

    es.addEventListener("task_error", (e) => {
      const data = JSON.parse(e.data);
      setTaskError(data.error || "unknown error");
      setIsConnected(false);
      es.close();
    });

    es.onerror = () => {
      // 不立即关闭，让浏览器自动重连
      console.log("SSE connection lost, waiting for reconnect...");
    };

    return () => {
      es.close();
      setIsConnected(false);
    };
  }, [taskId, reset]);

  return { sprites, taskDone, taskError, isConnected, reset };
}

// 将精灵体状态映射到 Canvas 组件需要的格式
export function mapSpriteToCanvasStatus(status: SpriteStatus): "working" | "sync" | "idle" | "offline" {
  switch (status) {
    case "running":
      return "working";
    case "completed":
      return "sync";
    case "failed":
      return "offline";
    default:
      return "idle";
  }
}
