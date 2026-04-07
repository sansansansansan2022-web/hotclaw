/**
 * CommandCenter — 深空指挥舱主组件
 *
 * 【核心布局】
 * 整个页面以视口中心为圆心，6 个智能体节点环形分布，
 * 中央是主控制台（任务输入 + 进度），顶部是状态栏。
 *
 * 布局计算：
 * - 中心点: 50% 50%
 * - 节点位置: calc(50% + x%)，以视口中心为原点
 * - 全息连线: SVG 贝塞尔曲线，连接相邻节点
 *
 * 状态管理：
 * - useTaskSSE: SSE 连接 + 节点状态
 * - 本地 state: positioning、taskId、resultData
 *
 * 面试点：
 * - React 状态提升（state hoisting）
 * - useEffect 副作用管理
 * - 条件渲染优化
 * - CSS calc() 动态布局
 */

"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useTaskSSE } from "@/hooks/useTaskSSE";
import { createTask, getTaskDetail } from "@/lib/api";
import MissionStatusBar from "./MissionStatusBar";
import CentralConsole from "./CentralConsole";
import AgentNode, { type AgentNodeData } from "./AgentNode";
import HoloLines from "./HoloLines";
import AgentDetailModal from "./AgentDetailModal";

// =============================================================================
// 智能体元数据
// =============================================================================

/**
 * AGENT_META — 智能体图标和描述
 *
 * 每个智能体的 emoji 图标和职能说明。
 * 实际运行时这些数据由后端提供，这里是静态展示数据。
 */
const AGENT_META: Record<string, { icon: string; description: string }> = {
  profile_parsing: {
    icon: "📡",
    description: "解析账号定位，提取领域关键词，生成结构化画像数据。",
  },
  hot_topic_analysis: {
    icon: "🔥",
    description: "多搜索引擎并发抓取热点，分析与账号领域相关度和时效性。",
  },
  topic_planning: {
    icon: "💡",
    description: "基于热点和画像，策划 3-5 个选题方向，评估吸引力与可行性。",
  },
  title_generation: {
    icon: "✏️",
    description: "为每个选题生成多个候选标题，结合多种标题策略预测点击率。",
  },
  content_writing: {
    icon: "📄",
    description: "按选定标题与大纲，撰写 1500-3000 字结构化文章正文。",
  },
  audit: {
    icon: "🛡️",
    description: "对内容进行合规性检查、风险评估，质量评分与优化建议。",
  },
};

// =============================================================================
// 环形轨道位置
// =============================================================================

/**
 * NODE_ORBIT — 6 个节点在圆形上的相对位置
 *
 * 【布局算法】以视口中心为圆心，6 等分圆周
 * 从 12 点钟方向开始，顺时针排列：
 *   0: 正上方 (x=0, y=-30)
 *   1: 右上 (x=+26, y=-15)
 *   2: 右下 (x=+26, y=+15)
 *   3: 正下方 (x=0, y=+30)
 *   4: 左下 (x=-26, y=+15)
 *   5: 左上 (x=-26, y=-15)
 *
 * CSS 定位：left: calc(50% + 26%), top: calc(50% - 15%)
 */
const NODE_ORBIT: { x: number; y: number }[] = [
  { x: 0,   y: -30 },   // 0: top (12 o'clock)
  { x: 26,  y: -15 },   // 1: top-right
  { x: 26,  y: 15  },   // 2: bottom-right
  { x: 0,   y: 30  },   // 3: bottom (6 o'clock)
  { x: -26, y: 15  },   // 4: bottom-left
  { x: -26, y: -15 },   // 5: top-left
];

export default function CommandCenter() {
  // ===== 组件状态 =====
  const [positioning, setPositioning] = useState("");      // 用户输入的账号定位
  const [taskId, setTaskId] = useState<string | null>(null);  // 当前任务 ID
  const [loading, setLoading] = useState(false);            // 创建任务中
  const [selectedAgent, setSelectedAgent] = useState<AgentNodeData | null>(null);  // 选中的节点
  const [resultData, setResultData] = useState<Record<string, unknown> | null>(null);  // 最终结果

  // ===== SSE Hook — 实时接收任务状态 =====
  const { nodes, taskDone, taskError, isConnected, reset } = useTaskSSE(taskId);

  // ===== 视口尺寸追踪（用于响应式）=====
  const viewportRef = useRef<{ w: number; h: number }>({ w: 1200, h: 800 });
  useEffect(() => {
    function update() {
      viewportRef.current = { w: window.innerWidth, h: window.innerHeight };
    }
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  // ===== 任务完成后获取结果 =====
  const fetchResult = useCallback(async (tid: string) => {
    try {
      const detail = await getTaskDetail(tid);
      if (detail.result_data) setResultData(detail.result_data);
    } catch { /* 非关键错误 */ }
  }, []);

  // 监听任务完成事件
  useEffect(() => {
    if (taskDone && taskId && !resultData) fetchResult(taskId);
  }, [taskDone, taskId, resultData, fetchResult]);

  // ===== 创建任务 =====
  async function handleCreateTask() {
    if (!positioning.trim()) return;
    setLoading(true);
    setResultData(null);
    reset();  // 重置 SSE 状态
    try {
      // 调用后端 API 创建任务
      const data = await createTask(positioning);
      // 设置 taskId 后，useTaskSSE 自动建立 SSE 连接
      setTaskId(data.task_id);
    } catch (err) {
      alert(err instanceof Error ? err.message : "创建任务失败");
    } finally {
      setLoading(false);
    }
  }

  // ===== 重置 =====
  function handleReset() {
    setTaskId(null);
    setResultData(null);
    setPositioning("");
    setSelectedAgent(null);
    reset();
  }

  // ===== 构建智能体节点数据 =====
  const agents: AgentNodeData[] = nodes.map((node, index) => {
    const meta = AGENT_META[node.node_id] || { icon: "🤖", description: "" };
    return {
      node_id: node.node_id,
      agent_id: node.agent_id,
      name: node.name,
      description: meta.description,
      icon: meta.icon,
      status: node.status,
      output_summary: node.output_summary,
      error: node.error,
      elapsed_seconds: node.elapsed_seconds,
      index,
    };
  });

  // 已完成节点数
  const completedCount = nodes.filter((n) => n.status === "completed").length;
  const runningNodeId = nodes.find((n) => n.status === "running")?.node_id ?? null;

  // ===== 节点位置（用于 HoloLines）=====
  // 转换为 SVG 视口坐标百分比（50 + x 是为了让 0 为中心）
  const nodePositions = agents.map((agent, i) => {
    const orbit = NODE_ORBIT[i] || { x: 0, y: 0 };
    const cx = 50 + orbit.x;
    const cy = 50 + orbit.y;
    return { node_id: agent.node_id, status: agent.status, cx, cy };
  });

  // ===== 渲染 =====
  return (
    // 深空背景（CSS 伪元素 + 星点网格）
    <div className="cc-space-bg" style={{ position: "relative" }}>
      {/* 中心光晕 */}
      <div className="cc-center-glow" />

      {/* 顶部状态栏 */}
      <MissionStatusBar
        isConnected={isConnected}
        taskId={taskId}
        completedCount={completedCount}
        totalCount={agents.length}
        taskDone={taskDone}
        taskError={taskError}
      />

      {/* 主内容层 */}
      <div style={{ position: "relative", zIndex: 10, width: "100vw", height: "100vh" }}>
        {/* 中央控制台 — 固定在视口中心 */}
        <CentralConsole
          positioning={positioning}
          onChange={setPositioning}
          onSubmit={handleCreateTask}
          onReset={handleReset}
          loading={loading}
          taskId={taskId}
          taskDone={taskDone}
          completedCount={completedCount}
          totalCount={agents.length}
        />

        {/* 环形智能体节点 */}
        {agents.map((agent, i) => (
          <AgentNode
            key={agent.node_id}
            agent={agent}
            position={NODE_ORBIT[i] || { x: 0, y: 0 }}
            onExpand={setSelectedAgent}
            delay={i * 80}  // 依次延迟出现
            isPrimary={runningNodeId === agent.node_id}
            isDimmed={runningNodeId !== null && runningNodeId !== agent.node_id}
          />
        ))}

        {/* 全息连接线（SVG） */}
        <HoloLines nodes={nodePositions} />
      </div>

      {/* 结果预览面板（任务完成后显示） */}
      {resultData != null && taskDone && (
        <div className="cc-result-panel">
          <div className="cc-result-header">
            <div className="cc-result-title">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <circle cx="7" cy="7" r="6" stroke="var(--cc-cyan)" strokeWidth="1" />
                <path d="M4 7l2 2 4-4" stroke="var(--cc-cyan)" strokeWidth="1.5"
                      strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              链路产出
            </div>
            <div className="cc-result-badge">
              <div className="cc-sdot done" style={{ width: 6, height: 6 }} />
              任务完成
            </div>
          </div>

          {/* 结果卡片 */}
          <div className="cc-result-grid">
            {resultData.profile != null && (
              <div className="cc-result-card">
                <div className="cc-result-card-label">账号画像</div>
                <div className="cc-result-card-value" style={{ color: "var(--cc-cyan)" }}>
                  {(resultData.profile as Record<string, unknown>).domain as string || "—"}
                </div>
              </div>
            )}
            {resultData.hot_topics != null && (
              <div className="cc-result-card">
                <div className="cc-result-card-label">热点话题</div>
                <div className="cc-result-card-value" style={{ color: "var(--cc-purple)" }}>
                  {((resultData.hot_topics as Record<string, unknown[]>).hot_topics || []).length} 条
                </div>
              </div>
            )}
            {resultData.topics != null && (
              <div className="cc-result-card">
                <div className="cc-result-card-label">选题方向</div>
                <div className="cc-result-card-value" style={{ color: "var(--cc-active)" }}>
                  {((resultData.topics as Record<string, unknown[]>).topics || []).length} 个
                </div>
              </div>
            )}
            {resultData.content != null && (
              <div className="cc-result-card">
                <div className="cc-result-card-label">文章正文</div>
                <div className="cc-result-card-value">
                  {(resultData.content as Record<string, number>).word_count || 0} 字
                </div>
              </div>
            )}
          </div>

          {/* 查看详情链接 */}
          <div style={{ marginTop: 12, textAlign: "center" }}>
            <a
              href={`/task/${taskId}`}
              style={{
                fontSize: 11, color: "var(--cc-cyan)",
                fontFamily: "var(--cc-font-mono)", textDecoration: "none",
                opacity: 0.8, transition: "opacity 0.2s",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.opacity = "1"; }}
              onMouseLeave={(e) => { e.currentTarget.style.opacity = "0.8"; }}
            >
              查看完整产出详情 →
            </a>
          </div>
        </div>
      )}

      {/* 节点详情弹窗 */}
      <AgentDetailModal
        agent={selectedAgent}
        onClose={() => setSelectedAgent(null)}
        taskId={taskId}
      />
    </div>
  );
}
