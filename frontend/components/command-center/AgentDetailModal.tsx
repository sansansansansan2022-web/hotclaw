"use client";

/**
 * ============================================================
 * AgentDetailModal.tsx - 智能体详情弹窗组件
 * ============================================================
 *
 * 【组件定位】
 * 点击智能体节点后弹出的详细信息面板，类似于数据库记录的详情查看模式。
 * 展示智能体的当前状态、输出内容和执行指标。
 *
 * 【设计理念】
 * - 模态弹窗：聚焦展示单一智能体的完整信息
 * - 毛玻璃背景：backdrop-filter 实现高级感
 * - 动画入场：slide-up 从下方滑入，fade-in 背景渐显
 * - 键盘支持：ESC 键关闭弹窗
 *
 * 【布局结构】
 * ┌─────────────────────────────────────────────────┐
 * │  ═══════════ 顶部装饰线 ═══════════            │
 * │                                              │
 * │  [图标] 智能体名称            [状态徽章] [X]  │  ← 头部
 * │         agent_id                             │
 * │                                              │
 * │  ────────── 职能说明 ──────────              │
 * │  智能体功能描述文字...                        │  ← 描述
 * │                                              │
 * │  ────────── 输出摘要 ──────────              │
 * │  ┌──────────────────────────────────────┐    │
 * │  │ 执行中：旋转图标 + 正在处理...        │    │  ← 状态相关输出
 * │  │ 完成时：output_summary 内容          │    │
 * │  │ 失败时：error 错误信息               │    │
 * │  └──────────────────────────────────────┘    │
 * │                                              │
 * │  耗时: 2.3s    节点: NODE_1    任务: ABC123  │  ← 元信息
 * └─────────────────────────────────────────────────┘
 */

import { useEffect } from "react";
import { type AgentNodeData } from "./AgentNode";
import { type NodeStatus } from "@/types";

// ============================================================
// 状态标签映射表
// ============================================================

/**
 * 状态码到显示文本和颜色的映射
 * 用于统一不同状态在UI中的呈现方式
 */
const STATUS_LABEL: Record<NodeStatus, { text: string; color: string }> = {
  // 待命状态：灰色，低调
  pending: { text: "待机", color: "var(--cc-text-muted)" },
  // 执行中：绿色，活跃
  running: { text: "执行中", color: "var(--cc-active)" },
  // 已完成：青色，成功
  completed: { text: "已完成", color: "var(--cc-cyan)" },
  // 失败：红色，警告
  failed: { text: "执行异常", color: "var(--cc-error)" },
  // 已跳过：灰色
  skipped: { text: "已跳过", color: "var(--cc-text-muted)" },
};

// ============================================================
// Props 接口定义
// ============================================================

interface AgentDetailModalProps {
  // 要展示的智能体数据，null 时不渲染
  agent: AgentNodeData | null;
  // 关闭弹窗回调
  onClose: () => void;
  // 当前任务ID，用于显示关联信息
  taskId: string | null;
}

// ============================================================
// 组件实现
// ============================================================

export default function AgentDetailModal({
  agent,
  onClose,
  taskId,
}: AgentDetailModalProps) {
  // =====================================================
  // 副作用：键盘事件监听
  // =====================================================

  /**
   * ESC 键关闭弹窗
   * - 组件挂载时注册 keydown 监听
   * - 组件卸载时移除监听（防止内存泄漏）
   * - 使用 onClose 回调，需要加入依赖数组
   */
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // 检测 ESC 键（keyCode 27 也可，但 key 更语义化）
      if (e.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handler);
    // 清理函数：组件卸载时移除监听
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);  // 依赖 onClose，确保使用最新版本

  // =====================================================
  // 防护性检查
  // =====================================================

  // agent 为 null 时不渲染任何内容
  if (!agent) return null;

  // 获取当前状态的标签信息
  const statusInfo = STATUS_LABEL[agent.status];

  // =====================================================
  // 渲染逻辑
  // =====================================================

  return (
    <>
      {/* =============================================== */}
      {/* 背景遮罩层 */}
      {/* =============================================== */}

      {/* 固定定位遮罩，覆盖整个视口 */}
      <div
        style={{
          position: "fixed",
          inset: 0,           // top:0, right:0, bottom:0, left:0
          zIndex: 200,        // 确保在最上层
          // 半透明深色背景
          background: "rgba(2, 5, 9, 0.7)",
          // 毛玻璃模糊效果
          backdropFilter: "blur(4px)",
          // 入场动画：0.2秒淡入
          animation: "cc-fade-in 0.2s ease",
        }}
        onClick={onClose}  // 点击背景也可关闭
      />

      {/* =============================================== */}
      {/* 弹窗主体 */}
      {/* =============================================== */}

      <div
        style={{
          position: "fixed",
          // 居中定位：left 50% + translate(-50%)
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          zIndex: 201,         // 遮罩层之上
          // 宽度响应式：最大520px，最小为视口92%
          width: "min(520px, 92vw)",
          // 渐变背景：从深蓝到近黑
          background: "linear-gradient(180deg, rgba(17, 30, 51, 0.99), rgba(8, 13, 26, 0.99))",
          // 细边框
          border: "1px solid var(--cc-border-light)",
          // 圆角
          borderRadius: 20,
          // 内边距
          padding: 28,
          // 毛玻璃效果（内容区域也模糊）
          backdropFilter: "blur(24px)",
          // 多层阴影组合：
          // 1. 内发光边缘（青色）
          // 2. 外发光（青色）
          // 3. 底部投影（黑色）
          boxShadow: `
            0 0 0 1px rgba(0,229,255,0.04),
            0 0 60px -10px rgba(0,229,255,0.12),
            0 24px 80px -15px rgba(0,0,0,0.7)
          `,
          // 入场动画：从下方滑入
          animation: "cc-slide-up 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
        }}
      >
        {/* ---------------------------------------- */}
        {/* 顶部装饰线 */}
        {/* ---------------------------------------- */}
        <div style={{
          position: "absolute",
          top: 0,
          // 左右各留15%，居中显示
          left: "15%",
          right: "15%",
          height: 1,
          // 渐变：透明 → 青色 → 透明
          background: "linear-gradient(90deg, transparent, var(--cc-cyan), transparent)",
          opacity: 0.4,
          borderRadius: 1,
        }} />

        {/* ---------------------------------------- */}
        {/* 头部区域：图标 + 名称 + 状态徽章 */}
        {/* ---------------------------------------- */}
        <div style={{
          display: "flex",
          alignItems: "flex-start",    // 顶部对齐
          justifyContent: "space-between", // 左右分布
          marginBottom: 20,
        }}>
          {/* 左侧：图标 + 名称信息 */}
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            {/* 智能体图标容器 */}
            <div style={{
              width: 52,
              height: 52,
              borderRadius: 14,
              // 渐变背景
              background: "linear-gradient(135deg, rgba(17, 30, 51, 0.9), rgba(8, 13, 26, 0.95))",
              // 边框颜色根据状态变化
              border: `1px solid ${
                agent.status === "running"
                  ? "rgba(34,197,94,0.4)"     // 执行中：绿色边框
                  : agent.status === "completed"
                    ? "var(--cc-cyan-border)"  // 完成：青色边框
                    : "var(--cc-border-light)" // 其他：灰色边框
              }`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 24,
              position: "relative",       // 用于定位旋转环
              // 阴影根据状态变化
              boxShadow:
                agent.status === "running"
                  ? "0 0 15px -3px var(--cc-active-glow)"
                  : agent.status === "completed"
                    ? "0 0 15px -3px var(--cc-cyan-glow)"
                    : "none",
            }}>
              {/* 智能体图标 */}
              {agent.icon}

              {/* 执行中状态的旋转环 */}
              {/* 仅在 running 状态显示 */}
              {agent.status === "running" && (
                <div style={{
                  position: "absolute",
                  inset: -4,          // 向外扩展4px
                  borderRadius: 18,
                  border: "2px solid var(--cc-active)",
                  // 顶部透明，形成旋转效果
                  borderTopColor: "transparent",
                  // 旋转动画
                  animation: "cc-ring-spin 1s linear infinite",
                }} />
              )}
            </div>

            {/* 名称和ID信息 */}
            <div>
              <div style={{
                fontSize: 16,
                fontWeight: 600,
                color: "var(--cc-text-primary)",
                marginBottom: 4,
              }}>
                {agent.name}
              </div>
              <div style={{
                fontSize: 11,
                fontFamily: "var(--cc-font-mono)",
                color: "var(--cc-text-muted)",
              }}>
                {agent.agent_id}
              </div>
            </div>
          </div>

          {/* 右侧：状态徽章 */}
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            // 胶囊形状
            padding: "4px 12px",
            borderRadius: 100,
            // 背景色根据状态变化
            background:
              agent.status === "running"
                ? "rgba(34,197,94,0.08)"      // 绿色背景
                : agent.status === "completed"
                  ? "rgba(0,229,255,0.08)"     // 青色背景
                  : agent.status === "failed"
                    ? "rgba(239,68,68,0.08)"    // 红色背景
                    : "rgba(74,99,130,0.08)",   // 灰色背景
            // 边框颜色
            border: `1px solid ${
              agent.status === "running"
                ? "rgba(34,197,94,0.2)"
                : agent.status === "completed"
                  ? "var(--cc-cyan-border)"
                  : agent.status === "failed"
                    ? "rgba(239,68,68,0.2)"
                    : "var(--cc-border)"
            }`,
          }}>
            {/* 状态指示圆点 */}
            <div className={`cc-sdot ${
              agent.status === "running"
                ? "active"      // 绿色
                : agent.status === "completed"
                  ? "done"      // 青色
                  : agent.status === "failed"
                    ? "error"   // 红色
                    : "pending" // 灰色
            }`} />

            {/* 状态文字 */}
            <span style={{
              fontSize: 11,
              fontFamily: "var(--cc-font-mono)",
              color: statusInfo.color,
            }}>
              {statusInfo.text}
            </span>
          </div>
        </div>

        {/* ---------------------------------------- */}
        {/* 职能说明区域 */}
        {/* ---------------------------------------- */}
        <div style={{ marginBottom: 20 }}>
          {/* 区域标签 */}
          <div style={{
            fontSize: 10,
            fontFamily: "var(--cc-font-mono)",
            color: "var(--cc-text-muted)",
            letterSpacing: "0.08em",      // 字母间距
            textTransform: "uppercase",     // 全大写
            marginBottom: 8,
          }}>
            职能说明
          </div>

          {/* 描述内容 */}
          <div style={{
            fontSize: 13,
            color: "var(--cc-text-secondary)",
            lineHeight: 1.6,  // 行高
          }}>
            {agent.description}
          </div>
        </div>

        {/* ---------------------------------------- */}
        {/* 输出摘要区域 */}
        {/* 仅在非待命状态显示 */}
        {/* ---------------------------------------- */}
        {(agent.status === "completed" ||
          agent.status === "running" ||
          agent.status === "failed") && (
          <div style={{ marginBottom: 20 }}>
            {/* 区域标签 */}
            <div style={{
              fontSize: 10,
              fontFamily: "var(--cc-font-mono)",
              color: "var(--cc-text-muted)",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              marginBottom: 8,
            }}>
              输出摘要
            </div>

            {/* 执行中状态：显示加载动画 */}
            {agent.status === "running" && (
              <div style={{
                padding: "12px 14px",
                borderRadius: 10,
                background: "rgba(34,197,94,0.04)",
                border: "1px solid rgba(34,197,94,0.15)",
                display: "flex",
                alignItems: "center",
                gap: 10,
                fontSize: 12,
                fontFamily: "var(--cc-font-mono)",
                color: "var(--cc-active)",
              }}>
                {/* 旋转加载器 */}
                <span style={{
                  width: 12,
                  height: 12,
                  borderRadius: "50%",
                  border: "2px solid var(--cc-active)",
                  borderTopColor: "transparent",
                  animation: "cc-spin 0.8s linear infinite",
                  flexShrink: 0,  // 防止缩小
                }} />
                正在处理数据...
              </div>
            )}

            {/* 已完成状态：显示输出摘要 */}
            {agent.status === "completed" && agent.output_summary && (
              <div style={{
                padding: "12px 14px",
                borderRadius: 10,
                background: "rgba(0,229,255,0.04)",
                border: "1px solid var(--cc-border-light)",
                fontSize: 12,
                fontFamily: "var(--cc-font-mono)",
                color: "var(--cc-text-secondary)",
                lineHeight: 1.5,
              }}>
                {agent.output_summary}
              </div>
            )}

            {/* 失败状态：显示错误信息 */}
            {agent.status === "failed" && agent.error && (
              <div style={{
                padding: "12px 14px",
                borderRadius: 10,
                background: "rgba(239,68,68,0.04)",
                border: "1px solid rgba(239,68,68,0.15)",
                fontSize: 12,
                fontFamily: "var(--cc-font-mono)",
                color: "var(--cc-error)",
                lineHeight: 1.5,
              }}>
                {agent.error}
              </div>
            )}
          </div>
        )}

        {/* ---------------------------------------- */}
        {/* 元信息区域 */}
        {/* ---------------------------------------- */}
        <div style={{
          display: "flex",
          gap: 16,
          paddingTop: 16,
          borderTop: "1px solid var(--cc-border)",
        }}>
          {/* 耗时：仅在有值时显示 */}
          {agent.elapsed_seconds !== null && (
            <div>
              <div style={{
                fontSize: 9,
                fontFamily: "var(--cc-font-mono)",
                color: "var(--cc-text-muted)",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                marginBottom: 2,
              }}>
                耗时
              </div>
              <div style={{
                fontSize: 14,
                fontFamily: "var(--cc-font-mono)",
                color: "var(--cc-text-primary)",
                fontWeight: 600,
              }}>
                {agent.elapsed_seconds.toFixed(1)}s
              </div>
            </div>
          )}

          {/* 节点标识 */}
          <div>
            <div style={{
              fontSize: 9,
              fontFamily: "var(--cc-font-mono)",
              color: "var(--cc-text-muted)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              marginBottom: 2,
            }}>
              节点
            </div>
            <div style={{
              fontSize: 14,
              fontFamily: "var(--cc-font-mono)",
              color: "var(--cc-text-primary)",
              fontWeight: 600,
            }}>
              {agent.node_id}
            </div>
          </div>

          {/* 任务ID：仅在有任务时显示 */}
          {taskId && (
            <div>
              <div style={{
                fontSize: 9,
                fontFamily: "var(--cc-font-mono)",
                color: "var(--cc-text-muted)",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                marginBottom: 2,
              }}>
                任务
              </div>
              <div style={{
                fontSize: 14,
                fontFamily: "var(--cc-font-mono)",
                color: "var(--cc-cyan)",
                fontWeight: 600,
              }}>
                {taskId.slice(0, 8).toUpperCase()}
              </div>
            </div>
          )}
        </div>

        {/* ---------------------------------------- */}
        {/* 关闭按钮 */}
        {/* ---------------------------------------- */}
        <button
          onClick={onClose}
          style={{
            position: "absolute",
            top: 16,
            right: 16,
            width: 28,
            height: 28,
            borderRadius: 8,
            background: "transparent",
            border: "1px solid var(--cc-border)",
            color: "var(--cc-text-muted)",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 14,
            transition: "all 0.15s",  // 过渡动画
          }}
          // 悬停效果
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "rgba(255,255,255,0.04)";
            e.currentTarget.style.color = "var(--cc-text-primary)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
            e.currentTarget.style.color = "var(--cc-text-muted)";
          }}
        >
          ✕
        </button>
      </div>
    </>
  );
}
