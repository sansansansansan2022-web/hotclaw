/**
 * SSE hook for real-time task event streaming.
 *
 * 【SSE Hook — 实时任务状态推送】
 * 封装 EventSource API，提供简洁的 React Hook 接口，
 * 让组件轻松订阅后端的 SSE 事件流。
 *
 * 核心功能：
 * 1. 根据 taskId 自动建立/断开 SSE 连接
 * 2. 解析后端发送的命名事件 (node_start, node_complete 等)
 * 3. 维护节点状态数组，供 UI 渲染环形节点
 * 4. 处理连接错误，允许浏览器自动重连
 *
 * 【为什么用 EventSource 而不是 WebSocket？】
 * - SSE：服务端推送，单向，更简单，支持自动重连
 * - WebSocket：双向，低延迟，需要心跳保活
 * - 本场景只需要服务端推送，SSE 更轻量
 *
 * 【为什么 onerror 不调用 es.close()？】
 * EventSource 有内置的自动重连机制（指数退避）。
 * 如果在 onerror 中调用 es.close()，会杀死这个机制，
 * 导致连接断开后永远无法恢复。
 *
 * 面试点：
 * - EventSource API（addEventListener / onerror）
 * - React Hooks (useState / useEffect / useCallback / useRef)
 * - SSE 协议格式（event: / data:）
 * - React 状态更新（prev => ... 函数式更新）
 * - useEffect 依赖数组设计
 */

import { useEffect, useRef, useCallback, useState } from "react";
import { getTaskStreamUrl } from "@/lib/api";
import type { NodeStatus } from "@/types";

/** 节点状态类型 */
export interface NodeState {
  node_id: string;          // 节点 ID (如 "profile_parsing")
  agent_id: string;         // 智能体 ID (如 "profile_agent")
  name: string;             // 中文名称
  status: NodeStatus;        // 状态 (pending/running/completed/failed)
  elapsed_seconds: number | null;  // 执行耗时
  error: string | null;     // 错误信息
  output_summary: string;   // 输出摘要
  degraded: boolean;        // 是否降级执行
}

/**
 * 初始节点状态
 * 6 个节点对应流水线中的 6 个智能体
 * 所有节点初始状态为 pending
 */
const INITIAL_NODES: Omit<NodeState, "status" | "elapsed_seconds" | "error" | "output_summary" | "degraded">[] = [
  { node_id: "context_building",  agent_id: "context_builder_agent",   name: "上下文装配" },
  { node_id: "hot_topic_analysis", agent_id: "hot_topic_agent",        name: "热点分析" },
  { node_id: "topic_selection",   agent_id: "topic_selection_agent",   name: "选题与标题" },
  { node_id: "content_drafting",  agent_id: "content_drafter_agent",   name: "内容起草" },
  { node_id: "editorial_review",  agent_id: "editorial_review_agent",  name: "编辑审核" },
  { node_id: "rewrite_agent",     agent_id: "rewrite_agent",           name: "润色改写" },
  { node_id: "memory_curation",   agent_id: "memory_curator_agent",    name: "记忆整理" },
];

/**
 * useTaskSSE — SSE 状态 Hook
 *
 * @param taskId - 任务 ID，传入 null 时断开连接
 *
 * Returns:
 * - nodes: 节点状态数组
 * - taskDone: 任务是否完成
 * - taskError: 任务错误信息
 * - isConnected: SSE 连接是否活跃
 * - reset: 重置所有状态
 *
 * 使用示例：
 *   const { nodes, taskDone, isConnected, reset } = useTaskSSE(taskId);
 *
 *   // 渲染环形节点
 *   nodes.map(node => (
 *     <AgentNode key={node.node_id} status={node.status} />
 *   ))
 */
export function useTaskSSE(taskId: string | null) {
  /**
   * nodes — 节点状态数组
   *
   * 使用函数式更新 setNodes(prev => ...) 避免闭包陷阱。
   * 如果用 setNodes([...])，可能因闭包引用旧状态导致更新丢失。
   */
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
  const [isConnected, setIsConnected] = useState(false);

  // 存储 EventSource 实例，防止 React 严格模式重复创建
  const esRef = useRef<EventSource | null>(null);

  /**
   * reset — 重置所有状态
   *
   * 每次创建新任务时调用，将所有节点恢复为 pending。
   * 使用 useCallback 缓存函数引用，避免 useEffect 依赖膨胀。
   */
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
    setIsConnected(false);
  }, []);

  useEffect(() => {
    // taskId 为 null 时不建立连接
    if (!taskId) return;

    // 重置状态（新任务开始）
    reset();

    // 获取 SSE URL（直连后端，绕过 Next.js 代理）
    const url = getTaskStreamUrl(taskId);
    console.log("[SSE] Connecting to:", url);

    // 创建 EventSource 实例
    const es = new EventSource(url);
    esRef.current = es;

    // ===== 连接打开回调 =====
    es.onopen = () => {
      console.log("[SSE] Connection opened for task:", taskId);
      setIsConnected(true);
    };

    // ===== 节点启动事件 =====
    es.addEventListener("node_start", (e) => {
      const data = JSON.parse(e.data);
      console.log("[SSE] node_start:", data.node_id);

      // 【关键】函数式更新，基于前一状态计算新状态
      setNodes((prev) =>
        prev.map((n) =>
          n.node_id === data.node_id
            ? { ...n, status: "running" as NodeStatus }
            : n
        )
      );
    });

    // ===== 节点完成事件 =====
    es.addEventListener("node_complete", (e) => {
      const data = JSON.parse(e.data);
      console.log("[SSE] node_complete:", data.node_id, data.output_summary?.slice(0, 50));

      setNodes((prev) =>
        prev.map((n) =>
          n.node_id === data.node_id
            ? {
                ...n,
                status: "completed" as NodeStatus,
                elapsed_seconds: data.elapsed_seconds,
                output_summary: data.output_summary || "",
                degraded: data.degraded || false,
              }
            : n
        )
      );
    });

    // ===== 节点错误事件 =====
    es.addEventListener("node_error", (e) => {
      const data = JSON.parse(e.data);
      console.log("[SSE] node_error:", data.node_id, data.error);

      setNodes((prev) =>
        prev.map((n) =>
          n.node_id === data.node_id
            ? { ...n, status: "failed" as NodeStatus, error: data.error }
            : n
        )
      );
    });

    // ===== 任务完成事件 =====
    es.addEventListener("task_complete", (e) => {
      console.log("[SSE] task_complete");
      setTaskDone(true);
      setIsConnected(false);
      es.close();
    });

    // ===== 任务错误事件 =====
    es.addEventListener("task_error", (e) => {
      const data = JSON.parse(e.data);
      console.log("[SSE] task_error:", data.error);
      setTaskError(data.error || "unknown error");
      setIsConnected(false);
      es.close();
    });

    // ===== 错误回调 =====
    // 【关键】不调用 es.close()！让 EventSource 自动重连
    es.onerror = (err) => {
      console.warn("[SSE] Connection error, browser will auto-reconnect...", err);
    };

    // ===== 清理函数 =====
    // 组件卸载或 taskId 变化时调用
    // 关闭 SSE 连接，防止连接泄漏
    return () => {
      console.log("[SSE] Cleanup: closing connection");
      es.close();
      setIsConnected(false);
    };
  }, [taskId, reset]);  // taskId 或 reset 变化时重新执行

  return { nodes, taskDone, taskError, isConnected, reset };
}
