'use client'

import { useEffect, useRef, useState } from 'react'

// 场景区域定义
const ZONES = {
  sky:        { x:0,    y:0,    w:1100, h:80  },
  wall:       { x:0,    y:80,   w:1100, h:128 },
  office_L:   { x:0,    y:208,  w:512,  h:256 },
  office_R:   { x:512,  y:208,  w:512,  h:256 },
  divider:    { x:512,  y:208,  w:4,    h:256 },
  corridor:   { x:0,    y:464,  w:1100, h:64  },
  lobby:      { x:0,    y:528,  w:1100, h:52  },
}

// 工位坐标配置
const DESKS = [
  { agentId:"profile_agent",        x:40,   y:220 },
  { agentId:"hot_topic_agent",      x:200,  y:220 },
  { agentId:"topic_planner_agent",  x:360,  y:220 },
  { agentId:"title_generator_agent",x:580,  y:220 },
  { agentId:"content_writer_agent", x:740,  y:220 },
  { agentId:"audit_agent",          x:900,  y:220 },
]

// 6个智能体定义
const AGENTS: Array<{id: number, name: string, agentId: string, sprite: string, status: 'working' | 'sync' | 'idle' | 'offline', floor: number, deskCol: number}> = [
  { id:1, name:"账号定位解析", sprite:"/sprites/chars/char_1.png", agentId:"profile_agent",       status:"working", floor:2, deskCol:0 },
  { id:2, name:"热点分析",     sprite:"/sprites/chars/char_2.png", agentId:"hot_topic_agent",     status:"sync",    floor:2, deskCol:1 },
  { id:3, name:"选题策划",     sprite:"/sprites/chars/char_3.png", agentId:"topic_planner_agent", status:"idle",    floor:2, deskCol:2 },
  { id:4, name:"标题生成",     sprite:"/sprites/chars/char_4.png", agentId:"title_generator_agent",status:"working", floor:3, deskCol:0 },
  { id:5, name:"正文生成",     sprite:"/sprites/chars/char_5.png", agentId:"content_writer_agent",status:"working", floor:3, deskCol:1 },
  { id:6, name:"审核",         sprite:"/sprites/chars/char_6.png", agentId:"audit_agent",         status:"offline", floor:3, deskCol:2 },
]

// 状态颜色映射
const STATUS_COLORS = {
  working: "#22c55e",
  sync:    "#eab308",
  idle:    "#6b7280",
  offline: "#ef4444",
}

// 方向映射
const ROW = { down:0, up:1, side:2 }

// 素材资源接口
interface Assets {
  tiles:  { wood: HTMLImageElement, white: HTMLImageElement, carpet: HTMLImageElement, wall: HTMLImageElement }
  objs:   { desk: HTMLImageElement, chair: HTMLImageElement, shelf: HTMLImageElement, plant: HTMLImageElement, vending: HTMLImageElement, couch: HTMLImageElement, rug: HTMLImageElement, lamp: HTMLImageElement, window: HTMLImageElement }
  chars:  HTMLImageElement[]
}

// 智能体状态接口
interface AgentState {
  id: number
  name: string
  agentId: string
  sprite: string
  status: 'working' | 'sync' | 'idle' | 'offline'
  x: number
  y: number
  targetX: number
  targetY: number
  frameIndex: number
  lastFrameTime: number
  direction: 'down' | 'up' | 'side'
  isMoving: boolean
  floor: number
  deskCol: number
}

export default function NewsroomScene() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animationFrameIdRef = useRef<number | null>(null)
  const [assets, setAssets] = useState<Assets | null>(null)
  const [agents, setAgents] = useState<AgentState[]>(() => 
    AGENTS.map(agent => {
      const desk = DESKS.find(d => d.agentId === agent.agentId)!
      return {
        ...agent,
        x: desk.x + 24,  // 角色脚底中心对齐桌子中心
        y: desk.y + 96,  // 桌子底部
        targetX: desk.x + 24,
        targetY: desk.y + 96,
        frameIndex: 0,
        lastFrameTime: 0,
        direction: 'down',
        isMoving: false
      }
    })
  )
  const [fps, setFps] = useState(0)
  const [clouds] = useState([
    { x: 100, y: 20, speed: 0.5 },
    { x: 300, y: 35, speed: 0.3 },
    { x: 700, y: 25, speed: 0.4 }
  ])

  // 图片预加载函数
  const loadImage = (src: string): Promise<HTMLImageElement> =>
    new Promise(resolve => {
      const img = new Image()
      img.onload = () => resolve(img)
      img.src = src
    })

  // 瓷砖平铺方法
  const drawTiled = (ctx: CanvasRenderingContext2D, tile: HTMLImageElement, startX: number, startY: number, areaW: number, areaH: number, scale = 2) => {
    const tw = tile.width * scale
    const th = tile.height * scale
    for (let y = startY; y < startY + areaH; y += th) {
      for (let x = startX; x < startX + areaW; x += tw) {
        ctx.drawImage(tile, x, y, tw, th)
      }
    }
  }

  // 单体素材绘制
  const drawObj = (ctx: CanvasRenderingContext2D, img: HTMLImageElement, x: number, y: number, scale = 2) => {
    ctx.drawImage(img, x, y, img.width * scale, img.height * scale)
  }

  // 绘制角色（正常方向）
  const drawCharacter = (ctx: CanvasRenderingContext2D, img: HTMLImageElement, frameW: number, frameH: number, frameIndex: number, row: number, footX: number, footY: number) => {
    const dw = frameW * 2
    const dh = frameH * 2
    ctx.drawImage(
      img,
      frameIndex * frameW, row * frameH,
      frameW, frameH,
      footX - dw / 2, footY - dh,
      dw, dh
    )
  }

  // 绘制角色（向左翻转）
  const drawCharacterFlipped = (ctx: CanvasRenderingContext2D, img: HTMLImageElement, frameW: number, frameH: number, frameIndex: number, footX: number, footY: number) => {
    const dw = frameW * 2
    const dh = frameH * 2
    ctx.save()
    ctx.translate(footX + dw / 2, footY - dh)
    ctx.scale(-1, 1)
    ctx.drawImage(img, frameIndex * frameW, ROW.side * frameH, frameW, frameH, 0, 0, dw, dh)
    ctx.restore()
  }

  // 绘制工位
  const drawDesk = (ctx: CanvasRenderingContext2D, assets: Assets, deskX: number, deskY: number) => {
    // 椅子在桌子正下方
    drawObj(ctx, assets.objs.chair, deskX + 16, deskY + 104)
    // 桌子
    drawObj(ctx, assets.objs.desk,  deskX, deskY)
    // 台灯
    drawObj(ctx, assets.objs.lamp,  deskX + 64, deskY + 4)
  }

  // 绘制状态标签
  const drawStatusLabel = (ctx: CanvasRenderingContext2D, name: string, status: string, x: number, y: number) => {
    const label = status.toUpperCase()
    ctx.font = "bold 10px monospace"
    const tw = ctx.measureText(label).width
    // 背景
    ctx.fillStyle = STATUS_COLORS[status as keyof typeof STATUS_COLORS]
    ctx.fillRect(x - tw/2 - 4, y - 12, tw + 8, 12)
    // 文字
    ctx.fillStyle = "#ffffff"
    ctx.fillText(label, x - tw/2, y - 2)
    // 角色名
    ctx.fillStyle = "#ffffff"
    ctx.font = "11px monospace"
    ctx.textAlign = "center"
    ctx.fillText(name, x, y - 16)
  }

  // 预加载所有素材
  useEffect(() => {
    const loadAssets = async () => {
      try {
        // 加载瓷砖
        const [wood, white, carpet, wall] = await Promise.all([
          loadImage('/tiles/tile_floor_wood.png'),
          loadImage('/tiles/tile_floor_white.png'),
          loadImage('/tiles/tile_floor_carpet.png'),
          loadImage('/tiles/tile_wall.png')
        ])

        // 加载家具
        const [desk, chair, shelf, plant, vending, couch, rug, lamp, window] = await Promise.all([
          loadImage('/objs/obj_desk.png'),
          loadImage('/objs/obj_chair.png'),
          loadImage('/objs/obj_bookshelf.png'),
          loadImage('/objs/obj_plant.png'),
          loadImage('/objs/obj_vending.png'),
          loadImage('/objs/obj_couch.png'),
          loadImage('/objs/obj_rug.png'),
          loadImage('/objs/obj_lamp.png'),
          loadImage('/objs/obj_window.png')
        ])

        // 加载角色精灵
        const chars = await Promise.all(
          Array.from({ length: 6 }, (_, i) => loadImage(`/sprites/chars/char_${i + 1}.png`))
        )

        setAssets({
          tiles: { wood, white, carpet, wall },
          objs: { desk, chair, shelf: shelf, plant, vending, couch, rug, lamp, window },
          chars
        })
      } catch (error) {
        console.error('Failed to load assets:', error)
      }
    }

    loadAssets()
  }, [])

  // 主渲染循环
  useEffect(() => {
    if (!canvasRef.current || !assets) return

    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')!
    ctx.imageSmoothingEnabled = false

    let lastTime = 0
    let frameCount = 0
    let lastFpsUpdate = 0

    const render = (time: number) => {
      const deltaTime = time - lastTime
      lastTime = time
      frameCount++

      // 更新FPS
      if (time - lastFpsUpdate >= 1000) {
        setFps(Math.round(frameCount * 1000 / (time - lastFpsUpdate)))
        frameCount = 0
        lastFpsUpdate = time
      }

      // 清空画布
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      // 分层渲染
      drawBackground(ctx)
      drawFloor(ctx)
      drawWalls(ctx)
      drawFurniture(ctx)
      updateAgents(deltaTime)
      drawAgents(ctx)
      drawUI(ctx)

      animationFrameIdRef.current = requestAnimationFrame(render)
    }

    const drawBackground = (ctx: CanvasRenderingContext2D) => {
      // 天空渐变
      const gradient = ctx.createLinearGradient(0, 0, 0, ZONES.sky.h)
      gradient.addColorStop(0, '#87ceeb')
      gradient.addColorStop(1, '#e0f6ff')
      ctx.fillStyle = gradient
      ctx.fillRect(ZONES.sky.x, ZONES.sky.y, ZONES.sky.w, ZONES.sky.h)

      // 云朵
      ctx.fillStyle = 'rgba(255, 255, 255, 0.8)'
      clouds.forEach(cloud => {
        ctx.fillRect(cloud.x, cloud.y, 60, 20)
        ctx.fillRect(cloud.x + 15, cloud.y - 10, 40, 15)
      })
    }

    const drawFloor = (ctx: CanvasRenderingContext2D) => {
      // 办公区木地板
      drawTiled(ctx, assets.tiles.wood, ZONES.office_L.x, ZONES.office_L.y, ZONES.office_L.w, ZONES.office_L.h)
      drawTiled(ctx, assets.tiles.wood, ZONES.office_R.x, ZONES.office_R.y, ZONES.office_R.w, ZONES.office_R.h)
      
      // 走廊白砖
      drawTiled(ctx, assets.tiles.white, ZONES.corridor.x, ZONES.corridor.y, ZONES.corridor.w, ZONES.corridor.h)
      
      // 大厅白砖
      drawTiled(ctx, assets.tiles.white, ZONES.lobby.x, ZONES.lobby.y, ZONES.lobby.w, ZONES.lobby.h)
      
      // 地毯装饰
      drawObj(ctx, assets.objs.rug, 200, 530)
    }

    const drawWalls = (ctx: CanvasRenderingContext2D) => {
      // 外墙瓷砖
      drawTiled(ctx, assets.tiles.wall, ZONES.wall.x, ZONES.wall.y, ZONES.wall.w, ZONES.wall.h)
      
      // 窗户（间隔摆放）
      for (let i = 0; i < 6; i++) {
        if (i % 2 === 0) {
          drawObj(ctx, assets.objs.window, 80 + i * 180, 96)
        }
      }
    }

    const drawFurniture = (ctx: CanvasRenderingContext2D) => {
      // 绘制所有工位
      DESKS.forEach(desk => {
        drawDesk(ctx, assets, desk.x, desk.y)
      })

      // 大厅家具
      drawObj(ctx, assets.objs.couch, 400, 536)
      drawObj(ctx, assets.objs.vending, 800, 532)
      drawObj(ctx, assets.objs.plant, 50, 540)
      drawObj(ctx, assets.objs.plant, 1000, 540)

      // 书架（贴墙）
      drawObj(ctx, assets.objs.shelf, 50, 210)
      drawObj(ctx, assets.objs.shelf, 1000, 210)
    }

    const updateAgents = (deltaTime: number) => {
      setAgents(prev => prev.map(agent => {
        const newAgent = { ...agent }
        const now = Date.now()

        // 更新动画帧
        if (now - agent.lastFrameTime > 150) {
          newAgent.frameIndex = (agent.frameIndex + 1) % 7
          newAgent.lastFrameTime = now
        }

        // 根据状态更新行为
        switch (agent.status) {
          case 'working':
            newAgent.isMoving = false
            newAgent.direction = 'down'
            break

          case 'sync':
            if (!agent.isMoving && Math.random() < 0.01) {
              const neighbors = DESKS.filter(d => d.agentId !== agent.agentId)
              const targetDesk = neighbors[Math.floor(Math.random() * neighbors.length)]
              newAgent.targetX = targetDesk.x + 24
              newAgent.targetY = targetDesk.y + 96
              newAgent.isMoving = true
              newAgent.direction = agent.x < newAgent.targetX ? 'side' : 'side'
            }
            break

          case 'idle':
            if (!agent.isMoving && Math.random() < 0.005) {
              // 走到大厅再回来
              newAgent.targetX = 600
              newAgent.targetY = 550
              newAgent.isMoving = true
              newAgent.direction = 'side'
            } else if (agent.isMoving && Math.abs(agent.x - agent.targetX) < 10) {
              // 回到工位
              const homeDesk = DESKS.find(d => d.agentId === agent.agentId)!
              newAgent.targetX = homeDesk.x + 24
              newAgent.targetY = homeDesk.y + 96
              newAgent.direction = 'side'
            }
            break

          case 'offline':
            newAgent.isMoving = false
            break
        }

        // 移动逻辑
        if (agent.isMoving) {
          const dx = agent.targetX - agent.x
          const dy = agent.targetY - agent.y
          const distance = Math.sqrt(dx * dx + dy * dy)

          if (distance > 2) {
            newAgent.x = agent.x + dx * 0.05
            newAgent.y = agent.y + dy * 0.05
          } else {
            newAgent.isMoving = false
            newAgent.frameIndex = 0
          }
        }

        return newAgent
      }))
    }

    const drawAgents = (ctx: CanvasRenderingContext2D) => {
      agents.forEach((agent, index) => {
        const charImg = assets.chars[index]
        if (!charImg) return

        const frameW = charImg.naturalWidth / 7
        const frameH = charImg.naturalHeight / 3

        // 应用透明度（offline状态）
        if (agent.status === 'offline') {
          ctx.globalAlpha = 0.35
        }

        // 绘制角色
        if (agent.direction === 'side' && agent.x > agent.targetX) {
          drawCharacterFlipped(ctx, charImg, frameW, frameH, agent.frameIndex, agent.x, agent.y)
        } else {
          const row = ROW[agent.direction] || ROW.down
          drawCharacter(ctx, charImg, frameW, frameH, agent.frameIndex, row, agent.x, agent.y)
        }

        ctx.globalAlpha = 1.0

        // 绘制状态标签
        drawStatusLabel(ctx, agent.name, agent.status, agent.x, agent.y - 48)

        // sync状态下绘制信封
        if (agent.status === 'sync' && agent.isMoving) {
          ctx.fillStyle = '#ffeb3b'
          ctx.fillRect(agent.x - 8, agent.y - 60, 16, 12)
          ctx.fillStyle = '#f44336'
          ctx.beginPath()
          ctx.moveTo(agent.x - 8, agent.y - 60)
          ctx.lineTo(agent.x, agent.y - 66)
          ctx.lineTo(agent.x + 8, agent.y - 60)
          ctx.closePath()
          ctx.fill()
        }

        // working状态下显示器光晕效果
        if (agent.status === 'working') {
          const desk = DESKS.find(d => d.agentId === agent.agentId)!
          const alpha = 0.3 + 0.2 * Math.sin(Date.now() / 300)
          ctx.fillStyle = `rgba(34, 197, 94, ${alpha})`
          ctx.fillRect(desk.x + 25, desk.y + 25, 30, 15)
        }
      })
    }

    const drawUI = (ctx: CanvasRenderingContext2D) => {
      // FPS计数器
      ctx.fillStyle = '#00ff00'
      ctx.font = 'bold 12px monospace'
      ctx.textAlign = 'left'
      ctx.fillText(`FPS: ${fps}`, 10, 20)

      // 时钟
      ctx.fillStyle = '#ff0000'
      ctx.font = 'bold 14px monospace'
      ctx.textAlign = 'right'
      const now = new Date()
      const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`
      ctx.fillText(timeStr, canvas.width - 10, 20)
    }

    animationFrameIdRef.current = requestAnimationFrame(render)

    return () => {
      if (animationFrameIdRef.current) {
        cancelAnimationFrame(animationFrameIdRef.current)
      }
    }
  }, [assets, agents, fps, clouds])

  if (!assets) {
    return (
      <div className="flex items-center justify-center h-96 bg-gray-900">
        <div className="text-white text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p>加载场景素材中...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-gray-900 p-4 rounded-lg">
      <canvas
        ref={canvasRef}
        width={1100}
        height={580}
        className="border-2 border-gray-700 bg-black"
      />
    </div>
  )
}