/**
 * AgentNode — 智能体环形节点
 *
 * 【设计理念】
 * 每个智能体是一个立体感的小球体，悬浮在深空背景中。
 * 状态驱动视觉变化：
 * - pending: 暗灰色，静止
 * - running: 绿色呼吸光效 + 旋转外环
 * - completed: 青色持续光晕
 * - error: 红色闪烁
 *
 * 悬浮行为：
 * - 悬浮时放大，显示详情卡片
 * - 详情卡片显示：名称、描述、状态、输出摘要、耗时
 * - 点击"详细"打开模态框
 *
 * CSS 定位：position: absolute, left/top = calc(50% + x%)
 *
 * 面试点：
 * - React 条件渲染
 * - CSS 组合类名（模板字符串 + 状态）
 * - CSS 动画（@keyframes）
 * - TypeScript interface
 */

"use client";

import { type NodeStatus } from "@/types";

/** 节点数据类型 */
export interface AgentNodeData {
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

interface AgentNodeProps {
  agent: AgentNodeData;
  position: { x: number; y: number };  // 相对视口中心的百分比偏移
  onExpand: (agent: AgentNodeData) => void;  // 展开详情回调
  delay?: number;  // 动画延迟（毫秒）
  isPrimary?: boolean; // 是否当前主关注节点（通常是 running）
  isDimmed?: boolean; // 是否降噪显示
}

/** 状态中文标签 */
const STATUS_LABEL: Record<NodeStatus, string> = {
  pending: "待机",
  running: "执行中",
  completed: "已完成",
  failed: "异常",
  skipped: "跳过",
};

export default function AgentNode({
  agent,
  position,
  onExpand,
  delay = 0,
  isPrimary = false,
  isDimmed = false,
}: AgentNodeProps) {
  const { x, y } = position;
  const isActive = agent.status === "running";
  const isDone = agent.status === "completed";
  const isError = agent.status === "failed";

  return (
    /**
     * 节点容器 — 绝对定位
     * 使用 calc(50% + x%) 实现以视口中心为原点的偏移
     */
    <div
      className="cc-node-wrapper"
      style={{
        // 【布局】以视口中心为原点
        left: `calc(50% + ${x}%)`,
        top: `calc(50% + ${y}%)`,
        transform: `translate(-50%, -50%) scale(${isPrimary ? 1.12 : 1})`,
        opacity: isDimmed ? 0.62 : 1,
        filter: isDimmed ? "saturate(0.75)" : "none",
        transition: "transform .22s ease, opacity .22s ease, filter .22s ease",
        // 依次延迟出现（制造"展开"效果）
        animationDelay: `${delay}ms`,
      }}
    >
      {/*
       * 节点外壳
       * className 组合：固定类 + 状态类
       * CSS 中 .cc-node-shell.{pending|active|done|error} 驱动不同光效
       */}
      <div
        className={`cc-node-shell ${agent.status}`}
        onClick={() => onExpand(agent)}
        title={agent.name}
      >
        {/* 旋转外环 — 仅 active 状态显示 */}
        <div className="cc-node-ring" />

        {/* 内部球体 */}
        <div className="cc-node-inner">
          {agent.icon}
        </div>

        {/* 右上角状态指示灯 */}
        <div className={`cc-node-light ${agent.status}`} />
      </div>

      {/* 节点名称标签 */}
      <div className="cc-node-name">
        {agent.name}
      </div>

      {/*
       * 悬浮详情卡片
       * 仅在非 pending 状态时显示（避免初始状态信息过少）
       */}
      {(isActive || isDone || isError) && (
        <div className="cc-node-info">
          {/* 标题 + 状态徽章 */}
          <div style={{
            display: "flex", alignItems: "center",
            justifyContent: "space-between", marginBottom: 4
          }}>
            <div className="cc-node-info-title">{agent.name}</div>
            <div style={{
              fontSize: 9, fontFamily: "var(--cc-font-mono)",
              padding: "1px 6px", borderRadius: 4,
              // 【状态驱动颜色】
              background: isActive ? "rgba(34,197,94,0.1)"
                : isError ? "rgba(239,68,68,0.1)"
                : "rgba(0,229,255,0.08)",
              color: isActive ? "var(--cc-active)"
                : isError ? "var(--cc-error)"
                : "var(--cc-cyan)",
              border: `1px solid ${isActive ? "rgba(34,197,94,0.2)"
                : isError ? "rgba(239,68,68,0.2)"
                : "var(--cc-cyan-border)"}`,
            }}>
              {STATUS_LABEL[agent.status]}
            </div>
          </div>

          {/* 职能描述 */}
          <div className="cc-node-info-desc">{agent.description}</div>

          {/* 控制台输出 — running 状态 */}
          {isActive && (
            <div className="cc-node-info-console active">
              <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
                {/* 旋转加载指示器 */}
                <span style={{
                  width: 8, height: 8, borderRadius: "50%",
                  border: "1.5px solid var(--cc-active)",
                  borderTopColor: "transparent",
                  animation: "cc-spin 0.7s linear infinite",
                  flexShrink: 0
                }} />
                数据处理中...
              </span>
            </div>
          )}

          {/* 输出摘要 — completed 状态 */}
          {isDone && agent.output_summary && (
            <div className="cc-node-info-console done">
              {agent.output_summary}
            </div>
          )}

          {/* 错误信息 — error 状态 */}
          {isError && agent.error && (
            <div className="cc-node-info-console error">
              {agent.error.slice(0, 80)}
            </div>
          )}

          {/* 执行耗时 */}
          {agent.elapsed_seconds !== null && isDone && (
            <div style={{
              marginTop: 6, fontSize: 9, fontFamily: "var(--cc-font-mono)",
              color: "var(--cc-text-muted)"
            }}>
              ⏱ {agent.elapsed_seconds.toFixed(1)}s
            </div>
          )}

          {/* 展开按钮 */}
          <button
            className="cc-expand-btn"
            onClick={(e) => {
              e.stopPropagation();  // 阻止冒泡，不触发节点点击
              onExpand(agent);
            }}
          >
            详细 <span style={{ opacity: 0.6 }}>→</span>
          </button>
        </div>
      )}
    </div>
  );
}
