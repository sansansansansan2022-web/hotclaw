'use client'

import { useSearchParams, useRouter } from 'next/navigation'
import { useEffect, useState, useCallback, Suspense } from 'react'
import { useTaskSSE } from '@/hooks/useTaskSSE'
import { createTask, getTaskDetail } from '@/lib/api'
import { useTaskStore } from '@/store/taskStore'
import MissionStatusBar from '../../components/command-center/MissionStatusBar'
import CentralConsole from '../../components/command-center/CentralConsole'
import AgentNode, { type AgentNodeData } from '../../components/command-center/AgentNode'
import HoloLines from '../../components/command-center/HoloLines'
import AgentDetailModal from '../../components/command-center/AgentDetailModal'

// Agent metadata
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
    description: "对内容进行合规性检查、风险评估、质量评分与优化建议。",
  },
}

// Circular orbit positions (percentage offsets from center)
// 6 nodes arranged in a circle, starting from top (12 o'clock), clockwise
const NODE_ORBIT: { x: number; y: number }[] = [
  { x: 0, y: -30 },          // 0: top
  { x: 26, y: -15 },         // 1: top-right
  { x: 26, y: 15 },          // 2: bottom-right
  { x: 0, y: 30 },           // 3: bottom
  { x: -26, y: 15 },         // 4: bottom-left
  { x: -26, y: -15 },        // 5: top-left
]

function NewsroomContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  
  // Zustand 全局状态
  const { activeTaskId, activePositioning, setActiveTask, clearActiveTask } = useTaskStore()
  
  // 本地状态
  const [positioning, setPositioning] = useState(activePositioning || "")
  const [loading, setLoading] = useState(false)
  const [selectedAgent, setSelectedAgent] = useState<AgentNodeData | null>(null)
  const [resultData, setResultData] = useState<Record<string, unknown> | null>(null)

  // taskId 优先从 URL 获取，否则从 store 恢复
  const urlTaskId = searchParams.get('taskId')
  const taskId = urlTaskId || activeTaskId

  const { nodes, taskDone, taskError, isConnected, reset } = useTaskSSE(taskId)

  // Fetch result when done
  const fetchResult = useCallback(async (tid: string) => {
    try {
      const detail = await getTaskDetail(tid)
      if (detail.result_data) setResultData(detail.result_data)
    } catch { /* non-critical */ }
  }, [])

  useEffect(() => {
    if (taskDone && taskId && !resultData) fetchResult(taskId)
  }, [taskDone, taskId, resultData, fetchResult])

  // 任务完成时清理全局状态
  useEffect(() => {
    if (taskDone) {
      // 延迟清理，等用户看完结果
      const timer = setTimeout(() => {
        clearActiveTask()
      }, 30000) // 30秒后自动清理
      return () => clearTimeout(timer)
    }
  }, [taskDone, clearActiveTask])

  async function handleCreateTask() {
    if (!positioning.trim()) return
    setLoading(true)
    setResultData(null)
    reset()
    try {
      const data = await createTask(positioning)
      // 保存到全局状态
      setActiveTask(data.task_id, positioning)
      // 同时更新 URL
      router.push(`/newsroom?taskId=${data.task_id}`)
    } catch (err) {
      alert(err instanceof Error ? err.message : "创建任务失败")
    } finally {
      setLoading(false)
    }
  }

  function handleReset() {
    // 清除 URL 参数
    router.push('/newsroom')
    // 清除全局状态
    clearActiveTask()
    setResultData(null)
    setPositioning("")
    setSelectedAgent(null)
    reset()
  }

  // Build agent nodes with metadata
  const agents: AgentNodeData[] = nodes.map((node, index) => {
    const meta = AGENT_META[node.node_id] || { icon: "🤖", description: "" }
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
    }
  })

  const completedCount = nodes.filter((n) => n.status === "completed").length

  // Compute node viewport positions for HoloLines
  const nodePositions = agents.map((agent, i) => {
    const orbit = NODE_ORBIT[i] || { x: 0, y: 0 }
    const cx = 50 + orbit.x
    const cy = 50 + orbit.y
    return { node_id: agent.node_id, status: agent.status, cx, cy }
  })

  return (
    <div className="cc-space-bg" style={{ position: "relative" }}>
      {/* Center glow */}
      <div className="cc-center-glow" />

      {/* Top Status Bar */}
      <MissionStatusBar
        isConnected={isConnected}
        taskId={taskId}
        completedCount={completedCount}
        totalCount={agents.length}
        taskDone={taskDone}
        taskError={taskError}
      />

      {/* Main content */}
      <div style={{ position: "relative", zIndex: 10, width: "100vw", height: "100vh" }}>
        {/* Central Console */}
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

        {/* Agent Nodes — arranged in circular orbit */}
        {agents.map((agent, i) => (
          <AgentNode
            key={agent.node_id}
            agent={agent}
            position={NODE_ORBIT[i] || { x: 0, y: 0 }}
            onExpand={setSelectedAgent}
            delay={i * 80}
          />
        ))}

        {/* Holo Connection Lines */}
        <HoloLines nodes={nodePositions} />
      </div>

      {/* Result Preview Panel */}
      {resultData != null && taskDone && (
        <div className="cc-result-panel">
          <div className="cc-result-header">
            <div className="cc-result-title">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <circle cx="7" cy="7" r="6" stroke="var(--cc-cyan)" strokeWidth="1" />
                <path d="M4 7l2 2 4-4" stroke="var(--cc-cyan)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              链路产出
            </div>
            <div className="cc-result-badge">
              <div className="cc-sdot done" style={{ width: 6, height: 6 }} />
              任务完成
            </div>
          </div>
          <div className="cc-result-grid">
            {resultData.profile != null ? (
              <div className="cc-result-card">
                <div className="cc-result-card-label">账号画像</div>
                <div className="cc-result-card-value" style={{ color: "var(--cc-cyan)" }}>
                  {(resultData.profile as Record<string, unknown>).domain as string || "—"}
                </div>
              </div>
            ) : null}
            {resultData.hot_topics != null ? (
              <div className="cc-result-card">
                <div className="cc-result-card-label">热点话题</div>
                <div className="cc-result-card-value" style={{ color: "var(--cc-purple)" }}>
                  {((resultData.hot_topics as Record<string, unknown[]>).hot_topics || []).length} 条
                </div>
              </div>
            ) : null}
            {resultData.topics != null ? (
              <div className="cc-result-card">
                <div className="cc-result-card-label">选题方向</div>
                <div className="cc-result-card-value" style={{ color: "var(--cc-active)" }}>
                  {((resultData.topics as Record<string, unknown[]>).topics || []).length} 个
                </div>
              </div>
            ) : null}
            {resultData.content != null ? (
              <div className="cc-result-card">
                <div className="cc-result-card-label">文章正文</div>
                <div className="cc-result-card-value">
                  {(resultData.content as Record<string, number>).word_count || 0} 字
                </div>
              </div>
            ) : null}
          </div>
          <div style={{ marginTop: 12, textAlign: "center" }}>
            <a
              href={`/task/${taskId}`}
              style={{
                fontSize: 11, color: "var(--cc-cyan)",
                fontFamily: "var(--cc-font-mono)", textDecoration: "none",
                opacity: 0.8, transition: "opacity 0.2s",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.opacity = "1" }}
              onMouseLeave={(e) => { e.currentTarget.style.opacity = "0.8" }}
            >
              查看完整产出详情 →
            </a>
          </div>
        </div>
      )}

      {/* Agent Detail Modal */}
      <AgentDetailModal
        agent={selectedAgent}
        onClose={() => setSelectedAgent(null)}
        taskId={taskId}
      />
    </div>
  )
}

// Wrap with Suspense for useSearchParams
export default function NewsroomPage() {
  return (
    <Suspense fallback={<div style={{ color: '#00ffff', padding: 20 }}>加载中...</div>}>
      <NewsroomContent />
    </Suspense>
  )
}
