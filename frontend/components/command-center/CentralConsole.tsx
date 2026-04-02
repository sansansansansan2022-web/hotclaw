"use client";

/**
 * ============================================================
 * CentralConsole.tsx - 中央控制台组件
 * ============================================================
 *
 * 【组件定位】
 * 这是 Command Center 的核心交互区域，类似于航天器的主驾驶舱。
 * 用户在此输入任务指令，监控系统执行进度，并在任务完成后查看产出链接。
 *
 * 【设计理念】
 * - 三态展示：空闲态 / 执行态 / 完成态
 * - 视觉反馈：通过进度条、按钮文案变化传达系统状态
 * - 操作保护：执行中禁用输入，防止重复提交
 *
 * 【布局结构】
 * ┌─────────────────────────────────────┐
 * │  [状态标签]                          │  ← 顶部：系统状态指示
 * │  主标题                              │  ← 标题随状态变化
 * │  副标题/说明                         │
 * │  [进度条] (执行中时显示)              │  ← 实时执行进度
 * │  ┌─────────────────────────────┐    │
 * │  │      文本输入区域            │    │  ← 用户指令输入
 * │  └─────────────────────────────┘    │
 * │  [主操作按钮] [重置按钮]             │  ← 底部操作区
 * │  [查看产出链接] (完成后显示)         │  ← 结果跳转入口
 * └─────────────────────────────────────┘
 */

// ============================================================
// Props 接口定义
// ============================================================

interface CentralConsoleProps {
  // 定位描述文本（用户输入的内容）
  positioning: string;
  // 文本变更回调，用于同步父组件状态
  onChange: (v: string) => void;
  // 提交任务回调，触发后端任务创建
  onSubmit: () => void;
  // 重置回调，清空输入并重置任务状态
  onReset: () => void;
  // 加载状态（任务创建中）
  loading: boolean;
  // 当前任务ID，有值表示任务已创建
  taskId: string | null;
  // 任务是否已完成
  taskDone: boolean;
  // 已完成的节点数量
  completedCount: number;
  // 总节点数量
  totalCount: number;
  // 节点整体状态：idle=空闲, running=执行中, done=完成
  nodeStatus?: "idle" | "running" | "done";
}

// ============================================================
// 组件实现
// ============================================================

export default function CentralConsole({
  positioning,
  onChange,
  onSubmit,
  onReset,
  loading,
  taskId,
  taskDone,
  completedCount,
  totalCount,
  nodeStatus = "idle",
}: CentralConsoleProps) {
  // =====================================================
  // 状态派生计算
  // =====================================================

  // 任务是否处于执行中：有任务ID且未完成
  const isRunning = !!taskId && !taskDone;

  // 计算执行进度百分比，保留整数
  // 公式：(已完成数 / 总数) * 100
  // 防止除以零：totalCount 为 0 时进度为 0
  const progress = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  // =====================================================
  // 样式类名动态组合
  // =====================================================

  // 基础类名 + 空闲态额外样式
  // 空闲态时添加 cc-console-idle 类，启用发光边框动画
  const consoleClass = ["cc-console", !taskId ? "cc-console-idle" : ""]
    .filter(Boolean)  // 过滤空字符串
    .join(" ");       // 拼接为字符串

  // =====================================================
  // 渲染逻辑
  // =====================================================

  return (
    // 主容器：控制台面板
    // 使用动态类名，空闲时显示脉冲边框动画
    <div className={consoleClass}>

      {/* ------------------------------------------------ */}
      {/* 状态标签行 */}
      {/* ------------------------------------------------ */}
      <div className="cc-console-label">
        {/* 状态指示灯 SVG */}
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
          {/* 外圈圆环 */}
          <circle cx="5" cy="5" r="4" stroke="var(--cc-cyan)" strokeWidth="1" />
          {/* 中心实心圆点 */}
          <circle cx="5" cy="5" r="1.5" fill="var(--cc-cyan)" />
        </svg>

        {/* 标签文案：三种状态不同显示 */}
        {isRunning
          ? "任务执行中"      // 执行中状态
          : taskDone
            ? "任务完成"      // 已完成状态
            : "主控台"        // 空闲状态
        }
      </div>

      {/* ------------------------------------------------ */}
      {/* 主标题行 */}
      {/* ------------------------------------------------ */}
      <div className="cc-console-title">
        {isRunning
          ? "链路执行中"       // 执行中
          : taskDone
            ? "执行完毕"       // 已完成
            : "发起创作任务"   // 空闲
        }
      </div>

      {/* ------------------------------------------------ */}
      {/* 副标题/说明行 */}
      {/* ------------------------------------------------ */}
      <div className="cc-console-sub">
        {isRunning
          // 执行中：显示节点完成进度和数据流动提示
          ? `${completedCount}/${totalCount} 个节点已完成，数据正在链路中传递...`
          : taskDone
            // 已完成：简洁的成功提示
            ? "所有节点执行完成，结果已产出"
            // 空闲：引导用户输入任务描述
            : "描述你的公众号定位，6 个智能体将协作完成内容创作"
        }
      </div>

      {/* ------------------------------------------------ */}
      {/* 进度条（仅执行中显示） */}
      {/* ------------------------------------------------ */}
      {isRunning && (
        <div style={{ marginBottom: 16 }}>
          {/* 进度标签行：左侧文字 + 右侧百分比 */}
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <span style={{
              fontSize: 10,
              fontFamily: "var(--cc-font-mono)",
              color: "var(--cc-text-muted)"
            }}>
              执行进度
            </span>
            <span style={{
              fontSize: 10,
              fontFamily: "var(--cc-font-mono)",
              color: "var(--cc-active)"  // 活跃色高亮百分比
            }}>
              {progress}%
            </span>
          </div>

          {/* 进度条轨道 */}
          <div style={{
            height: 3,
            background: "var(--cc-border)",
            borderRadius: 2,
            overflow: "hidden"  // 隐藏内部填充超出部分
          }}>
            {/* 进度条填充 */}
            {/* width 动态绑定实现进度效果 */}
            {/* transition 实现平滑动画 */}
            <div style={{
              height: "100%",
              width: `${progress}%`,
              // 渐变色：从活跃绿到青色
              background: "linear-gradient(90deg, var(--cc-active), var(--cc-cyan))",
              borderRadius: 2,
              // 进度变化时的平滑过渡动画
              // cubic-bezier 提供缓动效果
              transition: "width 0.6s cubic-bezier(0.4, 0, 0.2, 1)",
            }} />
          </div>
        </div>
      )}

      {/* ------------------------------------------------ */}
      {/* 任务描述输入区域 */}
      {/* ------------------------------------------------ */}
      <textarea
        className="cc-textarea"
        rows={3}              // 默认显示3行
        value={positioning}   // 受控组件：值由父组件控制
        onChange={(e) => onChange(e.target.value)}  // 变更回调同步父组件
        // 占位提示文本，引导用户输入
        placeholder="描述你的公众号定位，例如：专注职场成长，目标读者 25-35 岁互联网从业者"
        // 禁用条件：加载中 或 任务执行中
        // 防止用户在执行过程中修改输入
        disabled={loading || isRunning}
      />

      {/* ------------------------------------------------ */}
      {/* 操作按钮区 */}
      {/* ------------------------------------------------ */}
      <div className="cc-console-actions">

        {/* 主操作按钮：创建/提交任务 */}
        <button
          className="cc-btn-primary"
          onClick={onSubmit}
          // 禁用条件（全部满足才可点击）：
          // 1. 非加载中
          // 2. 有输入内容（去空格）
          // 3. 任务未在执行中
          disabled={loading || !positioning.trim() || isRunning}
        >
          {/* 按钮文案动态变化 */}
          {loading ? (
            // 加载中：显示旋转图标 + 创建中提示
            <span style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8
            }}>
              {/* 旋转加载指示器 */}
              <span style={{
                width: 12,
                height: 12,
                borderRadius: "50%",
                border: "2px solid rgba(0,0,0,0.3)",
                borderTopColor: "var(--cc-void)",  // 动画旋转的蓝色
                animation: "cc-spin 0.8s linear infinite",  // CSS 旋转动画
              }} />
              创建任务...
            </span>
          ) : isRunning ? (
            // 执行中：显示当前状态
            "链路执行中"
          ) : taskDone ? (
            // 已完成：允许重新发起
            "重新发起"
          ) : (
            // 空闲：正常提交
            "启动任务链路"
          )}
        </button>

        {/* 重置按钮：仅在有任务ID或输入内容时显示 */}
        {/* 使用逻辑与：有任一条件满足即显示 */}
        {(taskId || positioning) && (
          <button className="cc-btn-secondary" onClick={onReset}>
            重置
          </button>
        )}
      </div>

      {/* ------------------------------------------------ */}
      {/* 任务完成后的产出链接（可选区域） */}
      {/* ------------------------------------------------ */}
      {taskId && taskDone && (
        <div style={{ marginTop: 12, textAlign: "center" }}>
          <a
            href={`/task/${taskId}`}  // 跳转到任务详情页
            style={{
              fontSize: 11,
              color: "var(--cc-cyan)",
              fontFamily: "var(--cc-font-mono)",
              textDecoration: "none",     // 去除下划线
              opacity: 0.8,                // 默认透明度
              transition: "opacity 0.2s", // 悬停过渡
            }}
            // 悬停效果：透明度变为1
            onMouseEnter={(e) => { e.currentTarget.style.opacity = "1"; }}
            onMouseLeave={(e) => { e.currentTarget.style.opacity = "0.8"; }}
          >
            查看完整产出 →
          </a>
        </div>
      )}
    </div>
  );
}
