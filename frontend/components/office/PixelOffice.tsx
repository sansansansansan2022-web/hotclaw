/** PixelOffice — Canvas-based pixel art editorial office.
 *
 * Renders the HotClaw editorial office using Canvas 2D with:
 * - 6 agent characters at workstations
 * - Real-time SSE-driven state updates (TYPE/IDLE)
 * - Floating task bubbles above active agents
 * - Click/hover selection
 * - Canvas pixel rendering with Z-sorting
 */

"use client"

import { useEffect, useRef, useCallback, useState } from 'react'
import { OfficeState } from '@/lib/pixel-office/OfficeState'
import { GameLoop } from '@/lib/pixel-office/GameLoop'
import type { NodeState } from '@/hooks/useTaskSSE'

interface Props {
  nodes: NodeState[]
  taskDone: boolean
  taskError: string | null
  taskId: string | null
  onCreateTask: (positioning: string) => void
  loading: boolean
  resultData: Record<string, unknown> | null
}

export default function PixelOffice({
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

  const [canvasSize, setCanvasSize] = useState({ w: 800, h: 600 })
  const [selectedAgent, setSelectedAgent] = useState<number | null>(null)
  const [inputValue, setInputValue] = useState('')

  // ── Initialize game loop ──────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    // Set canvas size to fill container
    const updateSize = () => {
      const parent = canvas.parentElement
      if (!parent) return
      const w = parent.clientWidth
      const h = parent.clientHeight
      canvas.width = w
      canvas.height = h
      setCanvasSize({ w, h })
    }
    updateSize()
    window.addEventListener('resize', updateSize)

    // Create office state and game loop
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

  // ── Sync SSE events to game loop ───────────────────────────
  useEffect(() => {
    const loop = loopRef.current
    if (!loop) return

    // Find nodes that are running
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

  // Task-level events
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

  // ── Canvas interaction ────────────────────────────────────
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

  // ── Agent info panel ─────────────────────────────────────
  const selectedChar = selectedAgent !== null
    ? officeStateRef.current?.getCharacter(selectedAgent)
    : null

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden bg-[#1a1a2e]">
      {/* Top bar */}
      <div className="h-10 shrink-0 flex items-center justify-between px-4 bg-[#2a2a5a] border-b border-[#6b4f10]">
        <span className="text-[13px] font-mono text-yellow-400 tracking-widest">
          HOTCLAW PIXEL OFFICE
        </span>
        <div className="flex items-center gap-3">
          {/* Task input */}
          <form onSubmit={handleSubmit} className="flex gap-1">
            <input
              type="text"
              value={inputValue}
              onChange={e => setInputValue(e.target.value)}
              placeholder="输入账号定位..."
              disabled={loading}
              className="bg-[#0a0a1e] border border-gray-600 rounded px-2 py-0.5 text-[10px] font-mono text-gray-200
                         focus:outline-none focus:border-cyan-500 w-40 placeholder-gray-600 disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={loading || !inputValue.trim()}
              className="px-2 py-0.5 bg-cyan-700 hover:bg-cyan-600 text-[10px] font-mono text-white
                         rounded disabled:opacity-40 transition-colors"
            >
              {loading ? '...' : '▶'}
            </button>
          </form>
          {/* Status */}
          <div className="flex items-center gap-1.5">
            {taskId ? (
              <>
                {nodes.some(n => n.status === 'running') && (
                  <span className="w-[6px] h-[6px] rounded-full bg-yellow-400 animate-pulse" />
                )}
                {taskDone && <span className="w-[6px] h-[6px] rounded-full bg-green-400" />}
                {taskError && <span className="w-[6px] h-[6px] rounded-full bg-red-400" />}
                <span className="text-[9px] font-mono text-gray-400">
                  {taskId.slice(0, 8)}...
                </span>
              </>
            ) : (
              <span className="text-[9px] font-mono text-gray-600">等待任务...</span>
            )}
          </div>
        </div>
      </div>

      {/* Main area: canvas + side panel */}
      <div className="flex-1 flex min-h-0">
        {/* Canvas */}
        <div className="flex-1 relative">
          <canvas
            ref={canvasRef}
            className="w-full h-full cursor-pointer"
            style={{ imageRendering: 'pixelated' }}
            onClick={handleClick}
            onMouseMove={handleMouseMove}
          />

          {/* Agent info panel overlay (bottom-left) */}
          {selectedChar && (
            <div className="absolute bottom-4 left-4 bg-black/80 border border-cyan-500/50 rounded p-3 min-w-48">
              <div className="text-[11px] font-mono text-cyan-400 font-bold mb-1">
                {selectedChar.label}
              </div>
              <div className="text-[9px] font-mono text-gray-400 space-y-0.5">
                <div>Agent: {selectedChar.agentId}</div>
                <div>State: <span className={selectedChar.isActive ? 'text-green-400' : 'text-gray-500'}>
                  {selectedChar.state.toUpperCase()}
                </span></div>
                <div>Position: ({selectedChar.tileCol}, {selectedChar.tileRow})</div>
                {selectedChar.bubbleText && (
                  <div className="text-[8px] text-yellow-300 mt-1 truncate">
                    &quot;{selectedChar.bubbleText}&quot;
                  </div>
                )}
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  setSelectedAgent(null)
                  loopRef.current?.selectAgent(null)
                }}
                className="mt-2 text-[8px] font-mono text-gray-500 hover:text-gray-300"
              >
                [ 关闭 ]
              </button>
            </div>
          )}

          {/* Task status overlay (top-right) */}
          {taskId && (
            <div className="absolute top-4 right-4 bg-black/80 border border-gray-600/50 rounded px-3 py-2">
              <div className="text-[9px] font-mono text-gray-400 mb-1">执行进度</div>
              <div className="space-y-0.5">
                {nodes.map(node => (
                  <div key={node.node_id} className="flex items-center gap-1.5 text-[8px] font-mono">
                    <span className={`w-[5px] h-[5px] rounded-full ${
                      node.status === 'running' ? 'bg-yellow-400 animate-pulse' :
                      node.status === 'completed' ? 'bg-green-400' :
                      node.status === 'failed' ? 'bg-red-400' : 'bg-gray-600'
                    }`} />
                    <span className="text-gray-400 w-16 truncate">{node.name}</span>
                    <span className={
                      node.status === 'running' ? 'text-yellow-300' :
                      node.status === 'completed' ? 'text-green-300' :
                      node.status === 'failed' ? 'text-red-300' : 'text-gray-600'
                    }>
                      {node.status === 'pending' ? '...' :
                       node.status === 'running' ? '工作中' :
                       node.status === 'completed' ? `${node.elapsed_seconds?.toFixed(1)}s` :
                       '失败'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right sidebar: node detail */}
        <div className="w-56 shrink-0 bg-[#1a1a3e] border-l border-[#6b4f10] flex flex-col overflow-hidden">
          <div className="bg-[#2a2a5a] px-3 py-1 border-b border-[#6b4f10]">
            <span className="text-[10px] font-mono text-yellow-400 tracking-wider">AGENTS</span>
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {nodes.map(node => {
              const ch = officeStateRef.current?.getCharacterByAgentId(node.agent_id)
              const palette = officeStateRef.current?.getAgentColor(node.agent_id) ?? '#6b7280'
              return (
                <div
                  key={node.node_id}
                  className={`p-2 rounded border cursor-pointer transition-colors ${
                    selectedAgent === ch?.id
                      ? 'border-cyan-500 bg-[#2a2a5a]'
                      : 'border-gray-700/30 bg-[#0a0a1e] hover:border-gray-600'
                  }`}
                  onClick={() => {
                    if (ch) {
                      setSelectedAgent(ch.id)
                      loopRef.current?.selectAgent(ch.id)
                    }
                  }}
                >
                  <div className="flex items-center gap-1.5 mb-1">
                    {/* Color swatch */}
                    <div
                      className="w-3 h-3 rounded-sm"
                      style={{ backgroundColor: palette }}
                    />
                    <span className="text-[9px] font-mono text-gray-200">{ch?.label ?? node.agent_id}</span>
                  </div>
                  <div className="text-[8px] font-mono text-gray-500 mb-1">{node.name}</div>
                  <div className={`text-[8px] font-mono ${
                    node.status === 'running' ? 'text-yellow-400' :
                    node.status === 'completed' ? 'text-green-400' :
                    node.status === 'failed' ? 'text-red-400' : 'text-gray-600'
                  }`}>
                    {node.status === 'pending' ? '待机' :
                     node.status === 'running' ? '● 执行中' :
                     node.status === 'completed' ? '✓ 完成' :
                     '✗ 失败'}
                  </div>
                  {node.output_summary && (
                    <div className="text-[7px] font-mono text-gray-500 mt-0.5 truncate">
                      {node.output_summary}
                    </div>
                  )}
                  {node.error && (
                    <div className="text-[7px] font-mono text-red-500 mt-0.5 truncate">
                      {node.error}
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
