'use client'

import { useState, useEffect, useRef } from 'react'

// 简单的数据类型定义
interface Agent {
  id: string
  name: string
  status: 'idle' | 'working' | 'sync' | 'alert'
  position: { x: number; y: number }
}

interface LogEntry {
  timestamp: string
  message: string
  type: 'info' | 'warning' | 'error'
}

interface Task {
  id: string
  title: string
  status: 'pending' | 'processing' | 'completed'
}

export default function NewsroomPage() {
  // 状态管理
  const [agents, setAgents] = useState<Agent[]>([
    { id: 'agent-1', name: '写作助手', status: 'idle', position: { x: 100, y: 100 } },
    { id: 'agent-2', name: '编辑专家', status: 'working', position: { x: 200, y: 150 } },
    { id: 'agent-3', name: '校对大师', status: 'sync', position: { x: 300, y: 100 } },
  ])

  const [logs, setLogs] = useState<LogEntry[]>([
    { timestamp: '14:30:25', message: '系统初始化完成', type: 'info' },
    { timestamp: '14:31:12', message: '写作助手开始处理新文章', type: 'info' },
    { timestamp: '14:32:45', message: '检测到内容质量异常', type: 'warning' },
  ])

  const [tasks, setTasks] = useState<Task[]>([
    { id: 'task-1', title: '撰写科技新闻稿', status: 'processing' },
    { id: 'task-2', title: '审核财经报道', status: 'pending' },
    { id: 'task-3', title: '校对体育专栏', status: 'completed' },
  ])

  const canvasRef = useRef<HTMLCanvasElement>(null)

  // 初始化画布
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // 设置画布尺寸
    canvas.width = 800
    canvas.height = 600

    // 绘制场景
    drawScene(ctx)
  }, [])

  // 绘制场景函数
  const drawScene = (ctx: CanvasRenderingContext2D) => {
    // 清空画布
    ctx.clearRect(0, 0, 800, 600)
    
    // 绘制背景
    ctx.fillStyle = '#2c3e50'
    ctx.fillRect(0, 0, 800, 600)
    
    // 绘制网格
    ctx.strokeStyle = '#34495e'
    ctx.lineWidth = 1
    for (let i = 0; i <= 800; i += 40) {
      ctx.beginPath()
      ctx.moveTo(i, 0)
      ctx.lineTo(i, 600)
      ctx.stroke()
    }
    for (let i = 0; i <= 600; i += 40) {
      ctx.beginPath()
      ctx.moveTo(0, i)
      ctx.lineTo(800, i)
      ctx.stroke()
    }
    
    // 绘制家具 - 简单的矩形表示
    drawFurniture(ctx)
    
    // 绘制角色
    agents.forEach(agent => {
      drawAgent(ctx, agent)
    })
  }

  // 绘制家具
  const drawFurniture = (ctx: CanvasRenderingContext2D) => {
    // 工作台
    ctx.fillStyle = '#8b4513'
    ctx.fillRect(80, 80, 120, 80)
    ctx.fillStyle = '#a0522d'
    ctx.fillRect(85, 85, 110, 70)
    
    // 咖啡机
    ctx.fillStyle = '#696969'
    ctx.fillRect(600, 100, 60, 80)
    
    // 服务器机柜
    ctx.fillStyle = '#2f4f4f'
    for (let i = 0; i < 4; i++) {
      ctx.fillRect(650, 200 + i * 25, 100, 20)
    }
    
    // 白板
    ctx.fillStyle = '#f5f5dc'
    ctx.fillRect(300, 50, 150, 100)
    ctx.strokeStyle = '#000000'
    ctx.lineWidth = 2
    ctx.strokeRect(300, 50, 150, 100)
  }

  // 绘制角色
  const drawAgent = (ctx: CanvasRenderingContext2D, agent: Agent) => {
    const { x, y } = agent.position
    
    // 根据状态选择颜色
    let color = '#3498db' // 默认蓝色
    switch (agent.status) {
      case 'working':
        color = '#2ecc71' // 绿色
        break
      case 'sync':
        color = '#f39c12' // 橙色
        break
      case 'alert':
        color = '#e74c3c' // 红色
        break
    }
    
    // 绘制角色身体
    ctx.fillStyle = color
    ctx.fillRect(x, y, 30, 40)
    
    // 绘制头部
    ctx.fillStyle = '#f1c40f'
    ctx.fillRect(x + 5, y - 15, 20, 15)
    
    // 绘制状态指示器
    ctx.fillStyle = color
    ctx.beginPath()
    ctx.arc(x + 15, y - 25, 8, 0, Math.PI * 2)
    ctx.fill()
    
    // 绘制名字标签
    ctx.fillStyle = '#ffffff'
    ctx.font = '12px Arial'
    ctx.textAlign = 'center'
    ctx.fillText(agent.name, x + 15, y + 55)
  }

  // 更新代理状态
  const updateAgentStatus = (agentId: string, newStatus: Agent['status']) => {
    setAgents(prev => prev.map(agent => 
      agent.id === agentId ? { ...agent, status: newStatus } : agent
    ))
    
    // 添加日志
    const timestamp = new Date().toLocaleTimeString()
    setLogs(prev => [
      { timestamp, message: `代理 ${agentId} 状态变更为 ${newStatus}`, type: 'info' },
      ...prev.slice(0, 9) // 保持最多10条日志
    ])
  }

  // 模拟代理活动
  useEffect(() => {
    const interval = setInterval(() => {
      setAgents(prev => prev.map(agent => {
        // 随机移动和状态变化
        if (Math.random() > 0.7) {
          const statuses: Agent['status'][] = ['idle', 'working', 'sync', 'alert']
          return {
            ...agent,
            position: {
              x: Math.max(50, Math.min(700, agent.position.x + (Math.random() - 0.5) * 10)),
              y: Math.max(50, Math.min(500, agent.position.y + (Math.random() - 0.5) * 10))
            },
            status: statuses[Math.floor(Math.random() * statuses.length)]
          }
        }
        return agent
      }))
    }, 3000)

    return () => clearInterval(interval)
  }, [])

  return (
    <div className="min-h-screen bg-gray-900 text-white p-6">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">像素风 AI 编辑部工作台</h1>
        
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 主场景区域 */}
          <div className="lg:col-span-2">
            <div className="bg-gray-800 rounded-lg p-4">
              <h2 className="text-xl font-semibold mb-4">编辑部场景</h2>
              <canvas 
                ref={canvasRef} 
                className="border-2 border-gray-700 rounded bg-gray-900"
              />
            </div>
          </div>
          
          {/* 控制面板区域 */}
          <div className="space-y-6">
            {/* 代理状态面板 */}
            <div className="bg-gray-800 rounded-lg p-4">
              <h3 className="text-lg font-semibold mb-3">代理状态</h3>
              <div className="space-y-2">
                {agents.map(agent => (
                  <div key={agent.id} className="flex items-center justify-between p-2 bg-gray-700 rounded">
                    <span>{agent.name}</span>
                    <div className="flex items-center space-x-2">
                      <span className={`px-2 py-1 rounded text-xs ${
                        agent.status === 'working' ? 'bg-green-600' :
                        agent.status === 'sync' ? 'bg-yellow-600' :
                        agent.status === 'alert' ? 'bg-red-600' :
                        'bg-blue-600'
                      }`}>
                        {agent.status}
                      </span>
                      <button 
                        onClick={() => updateAgentStatus(agent.id, 'working')}
                        className="px-2 py-1 bg-green-600 rounded text-xs hover:bg-green-700"
                      >
                        工作
                      </button>
                      <button 
                        onClick={() => updateAgentStatus(agent.id, 'idle')}
                        className="px-2 py-1 bg-blue-600 rounded text-xs hover:bg-blue-700"
                      >
                        空闲
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            
            {/* 系统日志面板 */}
            <div className="bg-gray-800 rounded-lg p-4">
              <h3 className="text-lg font-semibold mb-3">系统日志</h3>
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {logs.map((log, index) => (
                  <div key={index} className={`text-sm p-2 rounded ${
                    log.type === 'error' ? 'bg-red-900' :
                    log.type === 'warning' ? 'bg-yellow-900' :
                    'bg-gray-700'
                  }`}>
                    <span className="text-gray-400 mr-2">[{log.timestamp}]</span>
                    <span>{log.message}</span>
                  </div>
                ))}
              </div>
            </div>
            
            {/* 任务管理面板 */}
            <div className="bg-gray-800 rounded-lg p-4">
              <h3 className="text-lg font-semibold mb-3">任务列表</h3>
              <div className="space-y-2">
                {tasks.map(task => (
                  <div key={task.id} className="p-2 bg-gray-700 rounded flex justify-between items-center">
                    <span>{task.title}</span>
                    <span className={`px-2 py-1 rounded text-xs ${
                      task.status === 'completed' ? 'bg-green-600' :
                      task.status === 'processing' ? 'bg-yellow-600' :
                      'bg-gray-600'
                    }`}>
                      {task.status}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}