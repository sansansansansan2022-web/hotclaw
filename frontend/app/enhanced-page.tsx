/** Enhanced PixelOffice — Canvas-based pixel art editorial office with advanced visualization.
 *
 * Features:
 * - Optimized rendering performance with sprite caching
 * - Real-time dashboard with task monitoring
 * - Agent analytics panel with performance metrics
 * - Toggleable visualization panels
 * - Enhanced pixel art UI with consistent styling
 */

"use client"

import { useEffect, useRef, useCallback, useState } from 'react'
import { OfficeState } from '@/lib/pixel-office/OfficeState'
import { GameLoop } from '@/lib/pixel-office/GameLoop'
import type { NodeState } from '@/hooks/useTaskSSE'
import TaskDashboard from '@/components/dashboard/TaskDashboard'
import AgentAnalytics from '@/components/analytics/AgentAnalytics'

interface Props {
  nodes: NodeState[]
  taskDone: boolean
  taskError: string | null
  taskId: string | null
  onCreateTask: (positioning: string) => void
  loading: boolean
  resultData: Record<string, unknown> | null
}

export default function EnhancedPixelOffice({
  nodes,
  taskDone,
  taskError,
  taskId,
  onCreateTask,
  loading,
  resultData,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const loopRef = useRef<GameLoop | null>(null)
  const officeStateRef = useRef<OfficeState | null>(null)

  const [selectedAgent, setSelectedAgent] = useState<number | null>(null)
  const [inputValue, setInputValue] = useState('')
  const [elapsedTime, setElapsedTime] = useState(0)
  const [showDashboard, setShowDashboard] = useState(true)
  const [showAnalytics, setShowAnalytics] = useState(false)

  // 计时器 - 跟踪任务执行时间
  useEffect(() => {
    if (!taskId || taskDone || taskError) return
    
    const interval = setInterval(() => {
      setElapsedTime(prev => prev + 1)
    }, 1000)
    
    return () => clearInterval(interval)
  }, [taskId, taskDone, taskError])

  // 重置计时器
  useEffect(() => {
    if (!taskId) {
      setElapsedTime(0)
    }
  }, [taskId])

  // ── 初始化游戏循环 ──────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    // 设置canvas大小以填充容器
    const updateSize = () => {
      const parent = canvas.parentElement
      if (!parent) return
      const w = parent.clientWidth
      const h = parent.clientHeight
      canvas.width = w
      canvas.height = h
    }
    updateSize()
    window.addEventListener('resize', updateSize)

    // 创建办公室状态和游戏循环
    const state = new OfficeState()
    officeStateRef.current = state

    const loop = new GameLoop(canvas, state, 3)
    loopRef.current = loop
    loop.start()

    return () => {
      loop.stop()
      window.removeEventListener('resize', updateSize)
    }
  }, [])

  // ── 同步SSE事件到游戏循环 ───────────────────────────
  useEffect(() => {
    const loop = loopRef.current
    if (!loop) return

    // 查找正在运行的节点
    const runningNode = nodes.find(n => n.status === 'running')
    const completedNode = nodes.find(n => n.status === 'completed' && n.output_summary)
    const failedNode = nodes.find(n => n.status === 'failed')

    if (runningNode) {
      loop.onNodeStart(runningNode)
    } else if (completedNode) {
      loop.onNodeComplete(completedNode)
    } else if (failedNode) {
      loop.onNodeError(failedNode)
    }
  }, [nodes])

  // 任务级事件
  useEffect(() => {
    const loop = loopRef.current
    if (!loop) return
    if (taskDone) loop.onTaskComplete()
  }, [taskDone])

  useEffect(() => {
    const loop = loopRef.current
    if (!loop || !taskError) return
    loop.onTaskError(taskError)
  }, [taskError])

  // ── Canvas交互 ────────────────────────────────────
  const handleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    const loop = loopRef.current
    if (!canvas || !loop) return

    const id = loop.getCharacterAt(e.clientX, e.clientY)
    setSelectedAgent(id)
    loop.selectAgent(id ?? null)
  }, [])

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    const loop = loopRef.current
    if (!canvas || !loop) return

    const id = loop.getCharacterAt(e.clientX, e.clientY)
    if (officeStateRef.current) {
      officeStateRef.current.hoverAgent(id)
    }
  }, [])

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault()
    if (inputValue.trim() && !loading) {
      onCreateTask(inputValue.trim())
      setInputValue('')
    }
  }, [inputValue, loading, onCreateTask])

  // ── Agent信息面板 ─────────────────────────────────────
  const selectedChar = selectedAgent !== null
    ? officeStateRef.current?.getCharacter(selectedAgent)
    : null

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden bg-[#1a1a2e]">
      {/* 顶部工具栏 */}
      <div className="h-12 shrink-0 flex items-center justify-between px-4 bg-[#2a2a5a] border-b border-[#6b4f10]">
        <div className="flex items-center gap-4">
          <span className="text-[14px] font-mono text-yellow-400 tracking-widest">
            HOTCLAW PIXEL OFFICE
          </span>
          {/* 面板切换按钮 */}
          <div className="flex gap-2">
            <button
              onClick={() => setShowDashboard(!showDashboard)}
              className={`px-3 py-1 text-[11px] font-mono rounded transition-colors ${
                showDashboard 
                  ? 'bg-cyan-700 text-white shadow-lg' 
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              📊 仪表板
            </button>
            <button
              onClick={() => setShowAnalytics(!showAnalytics)}
              className={`px-3 py-1 text-[11px] font-mono rounded transition-colors ${
                showAnalytics 
                  ? 'bg-purple-700 text-white shadow-lg' 
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              📈 分析面板
            </button>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          {/* 任务输入表单 */}
          <form onSubmit={handleSubmit} className="flex gap-2">
            <input
              type="text"
              value={inputValue}
              onChange={e => setInputValue(e.target.value)}
              placeholder="输入账号定位..."
              disabled={loading}
              className="bg-[#0a0a1e] border border-gray-600 rounded px-3 py-1 text-[11px] font-mono text-gray-200
                         focus:outline-none focus:border-cyan-500 w-48 placeholder-gray-600 disabled:opacity-50
                         transition-colors"
            />
            <button
              type="submit"
              disabled={loading || !inputValue.trim()}
              className="px-3 py-1 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 
                         text-[11px] font-mono text-white rounded disabled:opacity-40 transition-all
                         shadow-md hover:shadow-lg"
            >
              {loading ? '⏳ 执行中...' : '▶ 开始任务'}
            </button>
          </form>
          
          {/* 任务状态指示器 */}
          <div className="flex items-center gap-2">
            {taskId ? (
              <>
                {nodes.some(n => n.status === 'running') && (
                  <div className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />
                    <span className="text-[10px] font-mono text-yellow-400">运行中</span>
                  </div>
                )}
                {taskDone && (
                  <div className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-green-400" />
                    <span className="text-[10px] font-mono text-green-400">完成</span>
                  </div>
                )}
                {taskError && (
                  <div className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-red-400" />
                    <span className="text-[10px] font-mono text-red-400">错误</span>
                  </div>
                )}
                <span className="text-[10px] font-mono text-gray-400 bg-gray-800 px-2 py-1 rounded">
                  ID: {taskId.slice(0, 8)}...
                </span>
              </>
            ) : (
              <span className="text-[10px] font-mono text-gray-500">⏱ 等待新任务</span>
            )}
          </div>
        </div>
      </div>

      {/* 主要内容区域 */}
      <div className="flex-1 flex min-h-0">
        {/* 左侧面板区域 */}
        {(showDashboard || showAnalytics) && (
          <div className="w-80 shrink-0 bg-[#1a1a3e] border-r border-[#6b4f10] flex flex-col overflow-hidden">
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {showDashboard && (
                <TaskDashboard 
                  nodes={nodes}
                  taskDone={taskDone}
                  taskError={taskError}
                  taskId={taskId}
                  elapsedTime={elapsedTime}
                />
              )}
              
              {showAnalytics && (
                <AgentAnalytics 
                  nodes={nodes}
                />
              )}
            </div>
          </div>
        )}

        {/* 中央Canvas区域 */}
        <div className="flex-1 relative bg-[#0a0a1e]">
          <canvas
            ref={canvasRef}
            className="w-full h-full cursor-pointer"
            style={{ imageRendering: 'pixelated' }}
            onClick={handleClick}
            onMouseMove={handleMouseMove}
          />

          {/* Agent信息面板覆盖层 (左下角) */}
          {selectedChar && (
            <div className="absolute bottom-6 left-6 bg-black/90 border-2 border-cyan-500/70 rounded-lg p-4 min-w-56
                          backdrop-blur-sm shadow-2xl">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-3 h-3 rounded-full bg-green-400 animate-pulse" />
                <div className="text-[12px] font-mono text-cyan-400 font-bold">
                  {selectedChar.label} - 详细信息
                </div>
              </div>
              <div className="space-y-2 text-[10px] font-mono text-gray-300">
                <div className="flex justify-between">
                  <span className="text-gray-500">Agent ID:</span>
                  <span className="text-gray-200">{selectedChar.agentId}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">状态:</span>
                  <span className={selectedChar.isActive ? 'text-green-400' : 'text-gray-500'}>
                    {selectedChar.state.toUpperCase()}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">位置:</span>
                  <span className="text-gray-200">({selectedChar.tileCol}, {selectedChar.tileRow})</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">帧数:</span>
                  <span className="text-gray-200">{selectedChar.frame}</span>
                </div>
                {selectedChar.bubbleText && (
                  <div className="pt-2 border-t border-gray-700">
                    <div className="text-[9px] text-yellow-300 font-bold mb-1">当前消息:</div>
                    <div className="text-[8px] text-gray-300 bg-gray-900/50 p-2 rounded">
                      "{selectedChar.bubbleText}"
                    </div>
                  </div>
                )}
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  setSelectedAgent(null)
                  loopRef.current?.selectAgent(null)
                }}
                className="mt-3 w-full py-1 text-[9px] font-mono text-gray-500 hover:text-gray-300 
                         border border-gray-700 rounded hover:border-gray-600 transition-colors"
              >
                [ 关闭详情 ]
              </button>
            </div>
          )}

          {/* 任务状态覆盖层 (右上角) */}
          {taskId && !showDashboard && (
            <div className="absolute top-6 right-6 bg-black/85 border border-gray-600/60 rounded-xl p-4
                          backdrop-blur-sm shadow-xl w-64">
              <div className="text-[11px] font-mono text-gray-400 mb-3 font-bold uppercase tracking-wider">
                执行进度监控
              </div>
              <div className="space-y-2">
                {nodes.map(node => (
                  <div key={node.node_id} className="flex items-center gap-3 p-2 rounded bg-gray-900/30">
                    <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                      node.status === 'running' ? 'bg-yellow-400 animate-pulse' :
                      node.status === 'completed' ? 'bg-green-400' :
                      node.status === 'failed' ? 'bg-red-400' : 'bg-gray-600'
                    }`} />
                    <div className="flex-1 min-w-0">
                      <div className="text-[10px] font-mono text-gray-300 truncate">{node.name}</div>
                      <div className={`text-[9px] font-mono font-bold mt-0.5 ${
                        node.status === 'running' ? 'text-yellow-300' :
                        node.status === 'completed' ? 'text-green-300' :
                        node.status === 'failed' ? 'text-red-300' : 'text-gray-500'
                      }`}>
                        {node.status === 'pending' ? '🕒 待机' :
                         node.status === 'running' ? '⚡ 执行中' :
                         node.status === 'completed' ? `✅ ${(node.elapsed_seconds || 0).toFixed(1)}s` :
                         '❌ 失败'}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 右侧Agent列表 */}
        <div className="w-64 shrink-0 bg-[#1a1a3e] border-l border-[#6b4f10] flex flex-col overflow-hidden">
          <div className="bg-[#2a2a5a] px-4 py-2 border-b border-[#6b4f10]">
            <span className="text-[11px] font-mono text-yellow-400 tracking-wider uppercase">
              Agent 工作站
            </span>
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {nodes.map(node => {
              const ch = officeStateRef.current?.getCharacterByAgentId(node.agent_id)
              const palette = officeStateRef.current?.getAgentColor(node.agent_id) ?? '#6b7280'
              const isActive = node.status === 'running'
              const isCompleted = node.status === 'completed'
              const hasError = node.status === 'failed'
              
              return (
                <div
                  key={node.node_id}
                  className={`p-3 rounded-lg border cursor-pointer transition-all duration-200 ${
                    selectedAgent === ch?.id
                      ? 'border-cyan-500/70 bg-cyan-500/15 shadow-lg' 
                      : isActive ? 'border-yellow-500/50 bg-yellow-500/10 hover:border-yellow-500/70' :
                        isCompleted ? 'border-green-500/50 bg-green-500/10 hover:border-green-500/70' :
                        hasError ? 'border-red-500/50 bg-red-500/10 hover:border-red-500/70' :
                        'border-gray-700/40 bg-gray-800/20 hover:border-gray-600 hover:bg-gray-800/30'
                  }`}
                  onClick={() => {
                    if (ch) {
                      setSelectedAgent(ch.id)
                      loopRef.current?.selectAgent(ch.id)
                    }
                  }}
                >
                  {/* Agent头部信息 */}
                  <div className="flex items-center gap-2 mb-2">
                    <div
                      className={`w-4 h-4 rounded ${
                        isActive ? 'animate-pulse' : ''
                      }`}
                      style={{ backgroundColor: palette }}
                    />
                    <span className="text-[10px] font-mono font-bold text-gray-200 flex-1">
                      {ch?.label ?? node.agent_id}
                    </span>
                    <div className={`text-[8px] px-1.5 py-0.5 rounded-full ${
                      isActive ? 'bg-yellow-500/20 text-yellow-400' :
                      isCompleted ? 'bg-green-500/20 text-green-400' :
                      hasError ? 'bg-red-500/20 text-red-400' :
                      'bg-gray-600/20 text-gray-500'
                    }`}>
                      {isActive ? 'WORK' : isCompleted ? 'DONE' : hasError ? 'ERR' : 'IDLE'}
                    </div>
                  </div>
                  
                  {/* Agent描述 */}
                  <div className="text-[9px] font-mono text-gray-400 mb-2 h-8 flex items-center">
                    {node.name}
                  </div>
                  
                  {/* 状态和时间信息 */}
                  <div className={`text-[9px] font-mono font-bold ${
                    isActive ? 'text-yellow-400' :
                    isCompleted ? 'text-green-400' :
                    hasError ? 'text-red-400' : 'text-gray-500'
                  }`}>
                    {node.status === 'pending' ? '🕒 准备就绪' :
                     node.status === 'running' ? '⚡ 正在执行' :
                     node.status === 'completed' ? `✅ 完成 (${(node.elapsed_seconds || 0).toFixed(1)}s)` :
                     '❌ 执行失败'}
                  </div>
                  
                  {/* 输出摘要 */}
                  {(node.output_summary || node.error) && (
                    <div className="mt-2 pt-2 border-t border-gray-700/30">
                      <div className={`text-[8px] font-mono p-2 rounded ${
                        node.error 
                          ? 'bg-red-900/20 text-red-300' 
                          : 'bg-gray-900/30 text-gray-400'
                      }`}>
                        {node.error ? node.error : node.output_summary}
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}