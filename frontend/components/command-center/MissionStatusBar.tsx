"use client";

/**
 * ============================================================
 * MissionStatusBar.tsx - 任务状态栏组件
 * ============================================================
 *
 * 【组件定位】
 * 悬浮于页面顶部的状态栏，类似于航天器的 HUD（抬头显示系统）。
 * 实时展示系统连接状态、当前任务进度和快速导航入口。
 *
 * 【设计理念】
 * - 固定定位：始终可见，不随页面滚动消失
 * - 信息密度高：紧凑布局呈现多维度状态
 * - 视觉分层：左(Logo) → 中(状态) → 右(导航)，黄金比例布局
 *
 * 【布局结构】
 * ┌──────────────────────────────────────────────────────────────────────┐
 * │ [Logo区域]          [状态指示器|任务ID|进度条]          [导航链接]     │
 * │  HC HotClaw          ● 链路传输中  TSK:ABC123  [████░░] 60%    历史|智能体|LLM │
 * └──────────────────────────────────────────────────────────────────────┘
 */

// ============================================================
// Props 接口定义
// ============================================================

interface MissionStatusBarProps {
  // SSE 连接状态：true=已连接，false=未连接/断开
  isConnected: boolean;
  // 当前任务ID，用于显示任务标识
  taskId: string | null;
  // 已完成的节点数量
  completedCount: number;
  // 总节点数量
  totalCount: number;
  // 任务是否已完成
  taskDone: boolean;
  // 任务错误信息，有值表示执行异常
  taskError: string | null;
  // 节点整体状态
  nodeStatus?: "running" | "idle";
}

// ============================================================
// 组件实现
// ============================================================

export default function MissionStatusBar({
  isConnected,
  taskId,
  completedCount,
  totalCount,
  taskDone,
  taskError,
  nodeStatus = "idle",
}: MissionStatusBarProps) {
  // =====================================================
  // 状态派生计算
  // =====================================================

  // 计算执行进度百分比
  // 防止除以零错误
  const progress = totalCount > 0
    ? Math.round((completedCount / totalCount) * 100)
    : 0;

  // =====================================================
  // 渲染逻辑
  // =====================================================

  return (
    // 状态栏主容器
    // position: fixed 固定定位
    // top: 0 从页面顶部开始
    // z-index: 100 保证在内容之上
    <div className="cc-status-bar">

      {/* =============================================== */}
      {/* 左侧：Logo 区域 */}
      {/* =============================================== */}
      <div className="cc-logo">
        {/* Logo 标志字符 */}
        <div className="cc-logo-mark">HC</div>

        {/* Logo 文字信息 */}
        <div>
          <div className="cc-logo-text">HotClaw</div>
          <div className="cc-logo-sub">Agent Command</div>
        </div>
      </div>

      {/* =============================================== */}
      {/* 中间：状态信息区 */}
      {/* =============================================== */}
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>

        {/* 状态指示器：圆点 + 文字 */}
        <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
          {/* 动态状态圆点 */}
          {/* 根据状态切换不同样式：active/done/error/pending */}
          <div className={`cc-sdot ${
            isConnected
              ? "active"      // 已连接：绿色活跃
              : taskDone
                ? "done"      // 已完成：青色
                : taskError
                  ? "error"   // 错误：红色
                  : "pending" // 待命：灰色
          }`} />

          {/* 状态文字 */}
          <span style={{
            fontSize: 11,
            color: "var(--cc-text-muted)",
            fontFamily: "var(--cc-font-mono)"
          }}>
            {isConnected
              ? "执行中"       // SSE已连接，数据流动中
              : taskDone
                ? "已完成"     // 任务执行完毕
                : taskError
                  ? "异常"      // 执行出错
                  : "待命"     // 空闲等待
            }
          </span>
        </div>

        {/* 分隔线：有任务ID时才显示 */}
        {taskId && (
          <div style={{
            width: 1,
            height: 16,
            background: "var(--cc-border)"
          }} />
        )}

        {/* 任务ID显示：仅在有任务时显示 */}
        {taskId && (
          <span style={{
            fontSize: 11,
            fontFamily: "var(--cc-font-mono)",
            color: "var(--cc-text-muted)"
          }}>
            {/* 显示前缀 + 任务ID前8位（转大写） */}
            TSK: <span style={{ color: "var(--cc-cyan)" }}>
              {taskId.slice(0, 8).toUpperCase()}
            </span>
          </span>
        )}

        {/* 分隔线：任务ID后 */}
        {taskId && (
          <div style={{
            width: 1,
            height: 16,
            background: "var(--cc-border)"
          }} />
        )}

        {/* 进度显示区：仅在有任务时显示 */}
        {taskId && (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {/* 进度条轨道 */}
            <div className="cc-progress-bar">
              {/* 进度条填充：宽度动态绑定 */}
              <div
                className="cc-progress-fill"
                style={{ width: `${progress}%` }}
              />
            </div>

            {/* 进度数字：已完成/总数 */}
            <span style={{
              fontSize: 10,
              fontFamily: "var(--cc-font-mono)",
              color: "var(--cc-text-muted)"
            }}>
              {completedCount}/{totalCount}
            </span>
          </div>
        )}
      </div>

      {/* =============================================== */}
      {/* 右侧：导航链接区 */}
      {/* =============================================== */}
      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>

        {/* 导航链接映射表 */}
        {[
          { href: "/history", label: "历史" },           // 任务历史记录
          { href: "/settings/agents", label: "智能体" }, // 智能体配置
          { href: "/settings/llm-providers", label: "LLM" }, // LLM提供商配置
        ].map(({ href, label }) => (
          // 使用 taskId 作为 key（稳定且唯一）
          <a key={href} href={href} className="cc-nav-link">
            {label}
          </a>
        ))}
      </div>
    </div>
  );
}
