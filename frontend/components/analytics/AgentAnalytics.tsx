/** Agent Analytics Panel - Agent性能分析面板
 *
 * 提供各Agent的性能统计和可视化分析：
 * - 执行效率雷达图
 * - 响应时间分布
 * - 成功率统计
 * - 资源消耗对比
 */

import { useState, useEffect } from 'react'
import type { NodeState } from '@/hooks/useTaskSSE'

interface AgentAnalyticsProps {
  nodes: NodeState[]
  className?: string
}

interface AgentMetric {
  agentId: string
  name: string
  executions: number
  successes: number
  failures: number
  avgResponseTime: number
  minResponseTime: number
  maxResponseTime: number
  successRate: number
}

export default function AgentAnalytics({ nodes, className = '' }: AgentAnalyticsProps) {
  const [metrics, setMetrics] = useState<AgentMetric[]>([])
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null)

  // 计算Agent性能指标
  useEffect(() => {
    const agentStats = new Map<string, {
      executions: number
      totalTime: number
      minTime: number
      maxTime: number
      successes: number
      failures: number
    }>()

    // 统计每个Agent的执行数据
    nodes.forEach(node => {
      if (!agentStats.has(node.agent_id)) {
        agentStats.set(node.agent_id, {
          executions: 0,
          totalTime: 0,
          minTime: Infinity,
          maxTime: 0,
          successes: 0,
          failures: 0
        })
      }

      const stats = agentStats.get(node.agent_id)!
      stats.executions += 1
      stats.totalTime += node.elapsed_seconds || 0
      stats.minTime = Math.min(stats.minTime, node.elapsed_seconds || Infinity)
      stats.maxTime = Math.max(stats.maxTime, node.elapsed_seconds || 0)
      
      if (node.status === 'completed') {
        stats.successes += 1
      } else if (node.status === 'failed') {
        stats.failures += 1
      }
    })

    // 转换为指标数组
    const metricsArray: AgentMetric[] = Array.from(agentStats.entries()).map(([agentId, stats]) => ({
      agentId,
      name: nodes.find(n => n.agent_id === agentId)?.name || agentId,
      executions: stats.executions,
      successes: stats.successes,
      failures: stats.failures,
      avgResponseTime: stats.executions > 0 ? stats.totalTime / stats.executions : 0,
      minResponseTime: stats.minTime === Infinity ? 0 : stats.minTime,
      maxResponseTime: stats.maxTime,
      successRate: stats.executions > 0 ? (stats.successes / stats.executions) * 100 : 0
    }))

    setMetrics(metricsArray)
  }, [nodes])

  // 获取颜色映射
  const getAgentColor = (agentId: string) => {
    const colors = [
      '#818cf8', // analysis - 蓝紫色
      '#fb923c', // planning - 橙色
      '#4ade80', // creation - 绿色
      '#c084fc', // audit - 紫色
      '#60a5fa', // 其他1 - 蓝色
      '#f87171'  // 其他2 - 红色
    ]
    const index = Array.from(new Set(nodes.map(n => n.agent_id))).indexOf(agentId)
    return colors[index % colors.length]
  }

  return (
    <div className={`bg-black/80 border border-purple-500/30 rounded-lg p-4 font-mono text-xs ${className}`}>
      {/* 标题 */}
      <div className="flex items-center justify-between mb-4 pb-2 border-b border-gray-700">
        <h3 className="text-purple-400 font-bold tracking-wider">AGENT ANALYTICS</h3>
        <span className="text-gray-500 text-[10px]">{metrics.length} Agents</span>
      </div>

      {/* 总体统计 */}
      <div className="grid grid-cols-3 gap-2 mb-4">
        <StatCard 
          title="总执行数" 
          value={metrics.reduce((sum, m) => sum + m.executions, 0)} 
          color="blue"
        />
        <StatCard 
          title="平均成功率" 
          value={`${Math.round(metrics.reduce((sum, m) => sum + m.successRate, 0) / metrics.length || 0)}%`} 
          color="green"
        />
        <StatCard 
          title="平均响应时间" 
          value={`${Math.round(metrics.reduce((sum, m) => sum + m.avgResponseTime, 0) / metrics.length || 0)}s`} 
          color="yellow"
        />
      </div>

      {/* Agent列表 */}
      <div className="mb-4">
        <h4 className="text-gray-400 text-[11px] mb-2 uppercase tracking-wider">Agent Performance</h4>
        <div className="space-y-2 max-h-48 overflow-y-auto">
          {metrics.map(metric => (
            <AgentRow
              key={metric.agentId}
              metric={metric}
              isSelected={selectedAgent === metric.agentId}
              onSelect={() => setSelectedAgent(selectedAgent === metric.agentId ? null : metric.agentId)}
              color={getAgentColor(metric.agentId)}
            />
          ))}
        </div>
      </div>

      {/* 详细指标对比 */}
      {selectedAgent && (
        <div className="border-t border-gray-700 pt-3">
          <h4 className="text-gray-400 text-[11px] mb-2 uppercase tracking-wider">
            {metrics.find(m => m.agentId === selectedAgent)?.name} - Detailed Metrics
          </h4>
          <AgentDetailPanel metric={metrics.find(m => m.agentId === selectedAgent)!} />
        </div>
      )}

      {/* 雷达图占位符 */}
      <div className="mt-4 p-3 bg-gray-900/30 border border-gray-700/50 rounded">
        <div className="text-center text-gray-600 text-[10px]">
          [ 雷达图可视化区域 ]
        </div>
        <div className="text-center text-gray-700 text-[9px] mt-1">
          展示多维度性能对比
        </div>
      </div>
    </div>
  )
}

// 统计卡片组件
function StatCard({ title, value, color }: { title: string; value: string | number; color: string }) {
  const colorClasses = {
    blue: 'text-blue-400 border-blue-500/30',
    green: 'text-green-400 border-green-500/30',
    yellow: 'text-yellow-400 border-yellow-500/30',
    purple: 'text-purple-400 border-purple-500/30'
  }

  return (
    <div className={`bg-gray-900/30 border rounded p-2 ${colorClasses[color as keyof typeof colorClasses]}`}>
      <div className="text-lg font-bold">{value}</div>
      <div className="text-gray-500 text-[9px]">{title}</div>
    </div>
  )
}

// Agent行组件
function AgentRow({ 
  metric, 
  isSelected, 
  onSelect,
  color 
}: { 
  metric: AgentMetric; 
  isSelected: boolean; 
  onSelect: () => void;
  color: string;
}) {
  return (
    <div 
      className={`p-2 rounded border cursor-pointer transition-all ${
        isSelected 
          ? 'border-cyan-500/50 bg-cyan-500/10' 
          : 'border-gray-700/30 bg-gray-800/20 hover:border-gray-600'
      }`}
      onClick={onSelect}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div 
            className="w-3 h-3 rounded-sm" 
            style={{ backgroundColor: color }}
          />
          <span className="text-gray-200 text-[10px] font-medium">{metric.name}</span>
        </div>
        <div className="text-right">
          <div className="text-green-400 text-[10px] font-bold">{Math.round(metric.successRate)}%</div>
          <div className="text-gray-500 text-[8px]">{metric.executions}次执行</div>
        </div>
      </div>
      
      {isSelected && (
        <div className="mt-2 pt-2 border-t border-gray-700/30">
          <div className="grid grid-cols-2 gap-2 text-[9px]">
            <div>
              <span className="text-gray-500">平均:</span>
              <span className="text-yellow-400 ml-1">{metric.avgResponseTime.toFixed(2)}s</span>
            </div>
            <div>
              <span className="text-gray-500">最快:</span>
              <span className="text-green-400 ml-1">{metric.minResponseTime.toFixed(2)}s</span>
            </div>
            <div>
              <span className="text-gray-500">最慢:</span>
              <span className="text-red-400 ml-1">{metric.maxResponseTime.toFixed(2)}s</span>
            </div>
            <div>
              <span className="text-gray-500">成功率:</span>
              <span className="text-blue-400 ml-1">{Math.round(metric.successRate)}%</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// Agent详情面板
function AgentDetailPanel({ metric }: { metric: AgentMetric }) {
  return (
    <div className="grid grid-cols-2 gap-2 text-[9px]">
      <DetailItem label="执行次数" value={metric.executions} color="blue" />
      <DetailItem label="成功次数" value={metric.successes} color="green" />
      <DetailItem label="失败次数" value={metric.failures} color="red" />
      <DetailItem label="成功率" value={`${Math.round(metric.successRate)}%`} color="purple" />
      <DetailItem label="平均响应" value={`${metric.avgResponseTime.toFixed(2)}s`} color="yellow" />
      <DetailItem label="响应范围" value={`${metric.minResponseTime.toFixed(1)}-${metric.maxResponseTime.toFixed(1)}s`} color="cyan" />
    </div>
  )
}

// 详情项目组件
function DetailItem({ label, value, color }: { label: string; value: string | number; color: string }) {
  const colorClasses = {
    blue: 'text-blue-400',
    green: 'text-green-400',
    red: 'text-red-400',
    yellow: 'text-yellow-400',
    purple: 'text-purple-400',
    cyan: 'text-cyan-400'
  }

  return (
    <div>
      <div className="text-gray-500">{label}</div>
      <div className={`${colorClasses[color as keyof typeof colorClasses]} font-bold`}>{value}</div>
    </div>
  )
}