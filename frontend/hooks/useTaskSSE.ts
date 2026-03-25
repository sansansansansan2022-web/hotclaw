/** SSE hook for real-time task event streaming. */

import { useEffect, useRef, useCallback, useState } from "react";
import { getTaskStreamUrl } from "@/lib/api";
import type { NodeStatus } from "@/types";

export interface NodeState {
  node_id: string;
  agent_id: string;
  name: string;
  status: NodeStatus;
  elapsed_seconds: number | null;
  error: string | null;
  output_summary: string;
  degraded: boolean;
}

// Initial node states matching backend pipeline order
const INITIAL_NODES: Omit<NodeState, "status" | "elapsed_seconds" | "error" | "output_summary" | "degraded">[] = [
  { node_id: "profile_parsing", agent_id: "profile_agent", name: "账号定位解析" },
  { node_id: "hot_topic_analysis", agent_id: "hot_topic_agent", name: "热点分析" },
  { node_id: "topic_planning", agent_id: "topic_planner_agent", name: "选题策划" },
  { node_id: "title_generation", agent_id: "title_generator_agent", name: "标题生成" },
  { node_id: "content_writing", agent_id: "content_writer_agent", name: "正文生成" },
  { node_id: "audit", agent_id: "audit_agent", name: "审核评估" },
];

export function useTaskSSE(taskId: string | null) {
  const [nodes, setNodes] = useState<NodeState[]>(
    INITIAL_NODES.map((n) => ({
      ...n,
      status: "pending" as NodeStatus,
      elapsed_seconds: null,
      error: null,
      output_summary: "",
      degraded: false,
    }))
  );
  const [taskDone, setTaskDone] = useState(false);
  const [taskError, setTaskError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  const reset = useCallback(() => {
    setNodes(
      INITIAL_NODES.map((n) => ({
        ...n,
        status: "pending" as NodeStatus,
        elapsed_seconds: null,
        error: null,
        output_summary: "",
        degraded: false,
      }))
    );
    setTaskDone(false);
    setTaskError(null);
  }, []);

  useEffect(() => {
    if (!taskId) return;
    reset();

    const es = new EventSource(getTaskStreamUrl(taskId));
    esRef.current = es;

    es.addEventListener("node_start", (e) => {
      const data = JSON.parse(e.data);
      setNodes((prev) =>
        prev.map((n) =>
          n.node_id === data.node_id ? { ...n, status: "running" } : n
        )
      );
    });

    es.addEventListener("node_complete", (e) => {
      const data = JSON.parse(e.data);
      setNodes((prev) =>
        prev.map((n) =>
          n.node_id === data.node_id
            ? {
                ...n,
                status: "completed",
                elapsed_seconds: data.elapsed_seconds,
                output_summary: data.output_summary || "",
                degraded: data.degraded || false,
              }
            : n
        )
      );
    });

    es.addEventListener("node_error", (e) => {
      const data = JSON.parse(e.data);
      setNodes((prev) =>
        prev.map((n) =>
          n.node_id === data.node_id
            ? { ...n, status: "failed", error: data.error }
            : n
        )
      );
    });

    es.addEventListener("task_complete", () => {
      setTaskDone(true);
      es.close();
    });

    es.addEventListener("task_error", (e) => {
      const data = JSON.parse(e.data);
      setTaskError(data.error || "unknown error");
      es.close();
    });

    es.onerror = () => {
      es.close();
    };

    return () => {
      es.close();
    };
  }, [taskId, reset]);

  return { nodes, taskDone, taskError, reset };
}
