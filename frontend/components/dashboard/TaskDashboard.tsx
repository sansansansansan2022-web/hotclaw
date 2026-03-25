/** Task Dashboard - 实时任务监控仪表板
 *
 * 提供任务执行状态的可视化展示，包括：
 * - 任务进度概览
 * - Agent活动状态
 * - 性能指标显示
 * - 历史趋势图表
 */

import { useState, useEffect } from 'react'
import type { NodeState } from '@/hooks/useTaskSSE'

interface DashboardProps {
  nodes: NodeState[]
  taskDone: boolean
  taskError: string | null
  taskId: string | null
  elapsedTime: number
}

export default function TaskDashboard({ nodes, taskDone, taskError, taskId, elapsedTime }: DashboardProps) {
  const [metrics, setMetrics] = useState({
    completedNodes: 0,
    totalNodes: 6,
    successRate: 0,
    avgResponseTime: 0
  })

  // 计算实时指标
  useEffect(() => {
    const completed = nodes.filter(n => n.status === 'completed').length
    const failed = nodes.filter(n => n.status === 'failed').length
    const total = nodes.length
    const successRate = total > 0 ? ((completed / total) * 100) : 0
    
    const avgTime = nodes
      .filter(n => n.elapsed_seconds)
      .reduce((sum, n) => sum + (n.elapsed_seconds || 0), 0) / 
      (nodes.filter(n => n.elapsed_seconds).length || 1)

    setMetrics({
      completedNodes: completed,
      totalNodes: total,
      successRate: Math.round(successRate),
      avgResponseTime: Math.round(avgTime * 100) / 100
    })
  }, [nodes])

  // 任务进度百分比
  const progressPercent = Math.round((metrics.completedNodes / metrics.totalNodes) * 100)

  return (
    <div className="bg-black/80 border border-cyan-500/30 rounded-lg p-4 font-mono text-xs">
      {/* 标题栏 */}
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-gray-700">
        <h3 className="text-cyan-400 font-bold tracking-wider">TASK DASHBOARD</h3>
        <div className="flex items-center gap-2">
          {taskId && (
            <span className="text-gray-500">ID: {taskId.slice(0, 8)}...</span>
          )}
          <div className={`w-2 h-2 rounded-full ${
            taskDone ? 'bg-green-400' : 
            taskError ? 'bg-red-400' : 
            nodes.some(n => n.status === 'running') ? 'bg-yellow-400 animate-pulse' : 
            'bg-gray-600'
          }`} />
        </div>
      </div>

      {/* 主要指标 */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        {/* 进度环 */}
        <div className="flex flex-col items-center">
          <div className="relative w-16 h-16 mb-1">
            <svg className="w-full h-full" viewBox="0 0 36 36">
              <path
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                fill="none"
                stroke="#374151"
                strokeWidth="3"
              />
              <path
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                fill="none"
                stroke="#22c55e"
                strokeWidth="3"
                strokeDasharray={`${progressPercent}, 100`}
                strokeLinecap="round"
              />
              <text
                x="18"
                y="20"
                textAnchor="middle"
                fill="#9ca3af"
                fontSize="8"
                fontWeight="bold"
              >
                {progressPercent}%
              </text>
            </svg>
          </div>
          <span className="text-gray-400 text-[10px]">完成进度</span>
        </div>

        {/* 时间统计 */}
        <div className="flex flex-col">
          <div className="text-green-400 text-lg font-bold mb-1">
            {Math.floor(elapsedTime / 60)}:{String(Math.floor(elapsedTime % 60)).padStart(2, '0')}
          </div>
          <span className="text-gray-400 text-[10px]">运行时间</span>
          <div className="mt-2 text-yellow-400 text-sm">
            {metrics.avgResponseTime}s
          </div>
          <span className="text-gray-400 text-[10px]">平均响应</span>
        </div>
      </div>

      {/* Agent状态网格 */}
      <div className="mb-4">
        <h4 className="text-gray-400 text-[11px] mb-2 uppercase tracking-wider">Agent Status</h4>
        <div className="grid grid-cols-3 gap-2">
          {nodes.map((node, index) => {
            const isActive = node.status === 'running'
            const isCompleted = node.status === 'completed'
            const hasError = node.status === 'failed'
            
            return (
              <div 
                key={node.node_id}
                className={`p-2 rounded border text-center ${
                  isActive ? 'border-yellow-500/50 bg-yellow-500/10' :
                  isCompleted ? 'border-green-500/50 bg-green-500/10' :
                  hasError ? 'border-red-500/50 bg-red-500/10' :
                  'border-gray-700/50 bg-gray-800/30'
                }`}
              >
                <div className={`w-2 h-2 rounded-full mx-auto mb-1 ${
                  isActive ? 'bg-yellow-400 animate-pulse' :
                  isCompleted ? 'bg-green-400' :
                  hasError ? 'bg-red-400' :
                  'bg-gray-600'
                }`} />
                <div className="text-[9px] text-gray-300 truncate">{node.name}</div>
                {node.elapsed_seconds && (
                  <div className="text-[8px] text-gray-500 mt-1">
                    {node.elapsed_seconds.toFixed(1)}s
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* 性能指标卡片 */}
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-gray-900/50 border border-gray-700/50 rounded p-2">
          <div className="text-green-400 text-lg font-bold">{metrics.successRate}%</div>
          <div className="text-gray-400 text-[9px]">成功率</div>
        </div>
        <div className="bg-gray-900/50 border border-gray-700/50 rounded p-2">
          <div className="text-blue-400 text-lg font-bold">{metrics.completedNodes}/{metrics.totalNodes}</div>
          <div className="text-gray-400 text-[9px]">完成节点</div>
        </div>
      </div>

      {/* 错误信息显示 */}
      {taskError && (
        <div className="mt-3 p-2 bg-red-900/20 border border-red-500/30 rounded">
          <div className="text-red-400 text-[10px] font-bold mb-1">ERROR</div>
          <div className="text-red-300 text-[9px]">{taskError}</div>
        </div>
      )}
    </div>
  )
}