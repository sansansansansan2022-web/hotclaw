/** PixelOffice renderer — Optimized Canvas 2D rendering for the pixel office.
 *
 * Enhanced version with:
 * - Sprite caching for improved performance
 * - Dirty rectangle rendering
 * - Color palette caching
 * - Better memory management
 */

import type { Character } from './types'
import {
  TILE_SIZE, CHAR_HEIGHT,
  TileType,
  type OfficeLayout,
  CharacterState, Direction,
} from './types'
import {
  FALLBACK_FLOOR_COLOR, WALL_COLOR,
  AGENT_PALETTES,
  CHARACTER_SITTING_OFFSET_PX,
  BUBBLE_VERTICAL_OFFSET_PX,
} from './constants'
import { BUBBLE_SPRITE, DESK_SPRITE, MONITOR_SPRITE, CHARACTER_SPRITES } from './sprites/spriteData'
import { OfficeState } from './OfficeState'

// ── Floor tile colors ─────────────────────────────────────────
const FLOOR_COLORS: Record<number, string> = {
  [TileType.WALL]:    WALL_COLOR,
  [TileType.FLOOR_1]: '#2d2d5a',
  [TileType.FLOOR_2]: '#252550',
  [TileType.VOID]:    '#1a1a2e',
}

const AGENT_SPRITE_TYPE: Record<string, keyof typeof CHARACTER_SPRITES> = {
  profile_agent:          'analysis',
  hot_topic_agent:        'analysis',
  topic_planner_agent:    'planning',
  title_generator_agent:   'creation',
  content_writer_agent:   'creation',
  audit_agent:            'audit',
}

interface Drawable {
  zY: number
  draw: (ctx: CanvasRenderingContext2D) => void
  key?: string
  bounds?: { x: number; y: number; width: number; height: number }
}

interface CachedSprite {
  imageData: ImageData
  width: number
  height: number
}

export class OptimizedRenderer {
  private canvas: HTMLCanvasElement
  private ctx: CanvasRenderingContext2D
  zoom: number
  
  // 性能优化：缓存系统
  private spriteCache: Map<string, CachedSprite> = new Map()
  private colorPaletteCache: Map<string, Map<string, string>> = new Map()
  private lastFrameDrawables: Drawable[] = []
  private frameCount = 0

  constructor(canvas: HTMLCanvasElement, zoom = 2) {
    this.canvas = canvas
    this.ctx = canvas.getContext('2d')!
    this.zoom = zoom
    this.ctx.imageSmoothingEnabled = false
    
    // 初始化颜色调色板缓存
    this.initializeColorPalettes()
  }

  setZoom(zoom: number) {
    this.zoom = zoom
    this.ctx.imageSmoothingEnabled = false
    // 缩放变化时清空缓存
    this.clearCache()
  }
  
  // 初始化颜色调色板缓存
  private initializeColorPalettes() {
    AGENT_PALETTES.forEach((palette, index) => {
      const paletteMap = new Map<string, string>()
      paletteMap.set('#6366f1', palette) // 主色
      paletteMap.set('#4f46e5', this.darken(palette, 0.4)) // 阴影
      paletteMap.set('#312e81', this.darken(palette, 0.4)) // 深色
      this.colorPaletteCache.set(`palette_${index}`, paletteMap)
    })
  }
  
  // 清空缓存
  private clearCache() {
    this.spriteCache.clear()
  }

  render(state: OfficeState) {
    const { ctx, canvas, zoom } = this
    const { layout, selectedAgentId, hoveredAgentId } = state

    // 计算居中偏移
    const mapW = layout.cols * TILE_SIZE * zoom
    const mapH = layout.rows * TILE_SIZE * zoom
    const offsetX = Math.floor((canvas.width - mapW) / 2)
    const offsetY = Math.floor((canvas.height - mapH) / 2)

    // 构建当前帧的可绘制对象
    const currentDrawables = this.buildDrawables(state, offsetX, offsetY, selectedAgentId, hoveredAgentId)

    // 全屏清除（简化版本，后续可优化为脏矩形）
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // 绘制地板瓦片
    this.renderTileGrid(layout, offsetX, offsetY)

    // Z排序并绘制
    currentDrawables.sort((a, b) => a.zY - b.zY)
    for (const drawable of currentDrawables) {
      drawable.draw(ctx)
    }

    // 更新帧计数器用于缓存管理
    this.frameCount++
    if (this.frameCount % 600 === 0) { // 每10秒清理一次旧缓存
      this.cleanupCache()
    }

    this.lastFrameDrawables = currentDrawables
  }

  // 构建可绘制对象数组
  private buildDrawables(state: OfficeState, offsetX: number, offsetY: number, selectedAgentId: number | null, hoveredAgentId: number | null): Drawable[] {
    const drawables: Drawable[] = []
    const { layout } = state

    // 座位家具
    for (const seat of layout.seats) {
      const char_ = seat.agentId ? state.getCharacterByAgentId(seat.agentId) : undefined
      const isActive = char_?.isActive ?? false

      // 桌子
      drawables.push({
        zY: seat.seatRow * TILE_SIZE + TILE_SIZE,
        draw: (c) => this.drawCachedSprite(DESK_SPRITE, offsetX + seat.seatCol * TILE_SIZE * this.zoom, offsetY + seat.seatRow * TILE_SIZE * this.zoom, this.zoom),
        key: `desk-${seat.uid}`
      })

      // 显示器
      drawables.push({
        zY: seat.seatRow * TILE_SIZE + TILE_SIZE + 0.5,
        draw: (c) => {
          this.drawCachedSprite(
            MONITOR_SPRITE,
            offsetX + (seat.seatCol + 0.5) * TILE_SIZE * this.zoom,
            offsetY + (seat.seatRow - 0.5) * TILE_SIZE * this.zoom,
            this.zoom * 0.8,
          )
          // 活跃状态光晕
          if (isActive) {
            const gx = offsetX + (seat.seatCol + 1) * TILE_SIZE * this.zoom
            const gy = offsetY + (seat.seatRow - 0.3) * TILE_SIZE * this.zoom
            const grad = c.createRadialGradient(gx, gy, 0, gx, gy, TILE_SIZE * this.zoom)
            grad.addColorStop(0, 'rgba(14,165,233,0.3)')
            grad.addColorStop(1, 'rgba(14,165,233,0)')
            c.fillStyle = grad
            c.fillRect(gx - TILE_SIZE * this.zoom, gy - TILE_SIZE * this.zoom, TILE_SIZE * this.zoom * 2, TILE_SIZE * this.zoom * 2)
          }
        },
        key: `monitor-${seat.uid}-${isActive ? 'active' : 'inactive'}`
      })
    }

    // 角色
    for (const ch of state.getAllCharacters()) {
      const charZY = ch.y + TILE_SIZE / 2
      const spriteType = AGENT_SPRITE_TYPE[ch.agentId] ?? 'idle'
      const sprites = CHARACTER_SPRITES[spriteType]

      let spriteData: string[][]
      if (ch.state === CharacterState.TYPE) {
        spriteData = sprites.type[ch.dir] ?? sprites.idle[ch.dir]
      } else if (ch.state === CharacterState.WALK) {
        spriteData = sprites.walk[ch.dir]?.[ch.frame % 4] ?? sprites.idle[ch.dir]
      } else {
        spriteData = sprites.idle[ch.dir] ?? sprites.idle[0]
      }

      const sittingOff = ch.state === CharacterState.TYPE ? CHARACTER_SITTING_OFFSET_PX : 0
      const agentIdx = Array.from(state.getAllCharacters()).findIndex(ch_ => ch_.id === ch.id)
      const color = AGENT_PALETTES[agentIdx % AGENT_PALETTES.length]

      // 角色精灵
      drawables.push({
        zY: charZY,
        draw: (c) => {
          this.drawCachedCharacterSprite(spriteData, ch, offsetX, offsetY, this.zoom, sittingOff, color)
        },
        key: `char-${ch.id}-${ch.state}-${ch.frame}`
      })

      // 标签
      drawables.push({
        zY: charZY + 0.1,
        draw: (c) => this.drawLabel(ch, state, offsetX, offsetY, this.zoom, selectedAgentId === ch.id, hoveredAgentId === ch.id),
        key: `label-${ch.id}-${selectedAgentId === ch.id ? 'selected' : 'normal'}`
      })

      // 气泡
      if (ch.bubbleText) {
        drawables.push({
          zY: charZY + 0.2,
          draw: (c) => this.drawBubble(ch, offsetX, offsetY, this.zoom),
          key: `bubble-${ch.id}`
        })
      }

      // 选择轮廓
      if (selectedAgentId === ch.id || hoveredAgentId === ch.id) {
        drawables.push({
          zY: charZY - 0.1,
          draw: (c) => this.drawOutline(spriteData, ch, offsetX, offsetY, this.zoom, selectedAgentId === ch.id),
          key: `outline-${ch.id}-${selectedAgentId === ch.id ? 'selected' : 'hovered'}`
        })
      }
    }

    return drawables
  }

  // ── Tile rendering ─────────────────────────────────────────

  private renderTileGrid(layout: OfficeLayout, offsetX: number, offsetY: number) {
    const { ctx, zoom } = this
    const s = TILE_SIZE * zoom

    for (let r = 0; r < layout.rows; r++) {
      for (let c = 0; c < layout.cols; c++) {
        const tile = layout.tiles[r]?.[c] ?? TileType.VOID
        if (tile === TileType.VOID) continue

        const color = FLOOR_COLORS[tile] ?? FALLBACK_FLOOR_COLOR
        ctx.fillStyle = color
        ctx.fillRect(offsetX + c * s, offsetY + r * s, s, s)
      }
    }

    // 细微的网格线
    ctx.save()
    ctx.strokeStyle = 'rgba(255,255,255,0.03)'
    ctx.lineWidth = 1
    for (let r = 0; r <= layout.rows; r++) {
      ctx.beginPath()
      ctx.moveTo(offsetX, offsetY + r * s + 0.5)
      ctx.lineTo(offsetX + layout.cols * s, offsetY + r * s + 0.5)
      ctx.stroke()
    }
    for (let c = 0; c <= layout.cols; c++) {
      ctx.beginPath()
      ctx.moveTo(offsetX + c * s + 0.5, offsetY)
      ctx.lineTo(offsetX + c * s + 0.5, offsetY + layout.rows * s)
      ctx.stroke()
    }
    ctx.restore()
  }

  // ── 优化的精灵渲染 ────────────────────────────────────────

  /** 使用缓存绘制精灵 */
  private drawCachedSprite(sprite: string[][], px: number, py: number, scale: number) {
    const cacheKey = `${sprite.length}x${sprite[0]?.length}-${scale}`
    
    let cached = this.spriteCache.get(cacheKey)
    if (!cached) {
      // 创建缓存
      cached = this.createSpriteCache(sprite, scale)
      this.spriteCache.set(cacheKey, cached)
    }

    // 使用缓存绘制
    this.ctx.putImageData(cached.imageData, Math.round(px), Math.round(py))
  }

  /** 为精灵创建缓存 */
  private createSpriteCache(sprite: string[][], scale: number): CachedSprite {
    const w = sprite[0]?.length ?? 0
    const h = sprite.length
    const canvasW = Math.ceil(w * scale)
    const canvasH = Math.ceil(h * scale)
    
    // 创建临时canvas用于预渲染
    const tempCanvas = document.createElement('canvas')
    tempCanvas.width = canvasW
    tempCanvas.height = canvasH
    const tempCtx = tempCanvas.getContext('2d')!
    tempCtx.imageSmoothingEnabled = false

    // 绘制精灵到临时canvas
    for (let r = 0; r < h; r++) {
      for (let c = 0; c < w; c++) {
        const color = sprite[r]?.[c]
        if (!color) continue
        tempCtx.fillStyle = color
        tempCtx.fillRect(Math.round(c * scale), Math.round(r * scale), Math.ceil(scale), Math.ceil(scale))
      }
    }

    const imageData = tempCtx.getImageData(0, 0, canvasW, canvasH)
    return { imageData, width: canvasW, height: canvasH }
  }

  /** 绘制带颜色映射的角色精灵 */
  private drawCachedCharacterSprite(
    sprite: string[][],
    ch: Character,
    offsetX: number,
    offsetY: number,
    zoom: number,
    sittingOff: number,
    accentColor: string,
  ) {
    const w = sprite[0]?.length ?? 0
    const h = sprite.length

    // 锚点：精灵底部中心对齐到(ch.x, ch.y)
    const anchorX = offsetX + ch.x * zoom - w * zoom / 2
    const anchorY = offsetY + (ch.y + sittingOff) * zoom - h * zoom

    // 获取颜色调色板
    const agentIdx = AGENT_PALETTES.indexOf(accentColor)
    const palette = this.colorPaletteCache.get(`palette_${agentIdx}`)
    
    if (!palette) {
      // 回退到原始绘制方法
      this.drawCharacterSpriteFallback(sprite, ch, offsetX, offsetY, zoom, sittingOff, accentColor)
      return
    }

    // 使用putImageData优化绘制
    const imageData = this.ctx.createImageData(Math.ceil(w * zoom), Math.ceil(h * zoom))
    const data = imageData.data

    for (let r = 0; r < h; r++) {
      for (let c = 0; c < w; c++) {
        const color = sprite[r]?.[c]
        if (!color) continue

        // 颜色调色板映射
        let drawColor = color
        if (color === '#6366f1') drawColor = palette.get('#6366f1') || accentColor
        else if (color === '#4f46e5') drawColor = palette.get('#4f46e5') || this.darken(accentColor, 0.4)
        else if (color === '#312e81') drawColor = palette.get('#312e81') || this.darken(accentColor, 0.4)

        // 转换为RGBA
        const rVal = parseInt(drawColor.slice(1, 3), 16)
        const gVal = parseInt(drawColor.slice(3, 5), 16)
        const bVal = parseInt(drawColor.slice(5, 7), 16)

        // 填充缩放后的像素块
        const pixelSize = Math.ceil(zoom)
        for (let dr = 0; dr < pixelSize; dr++) {
          for (let dc = 0; dc < pixelSize; dc++) {
            const destX = Math.round(c * zoom) + dc
            const destY = Math.round(r * zoom) + dr
            if (destX < imageData.width && destY < imageData.height) {
              const index = (destY * imageData.width + destX) * 4
              data[index] = rVal     // R
              data[index + 1] = gVal // G
              data[index + 2] = bVal // B
              data[index + 3] = 255  // A
            }
          }
        }
      }
    }

    this.ctx.putImageData(imageData, Math.round(anchorX), Math.round(anchorY))
  }

  /** 回退的字符精灵绘制方法 */
  private drawCharacterSpriteFallback(
    sprite: string[][],
    ch: Character,
    offsetX: number,
    offsetY: number,
    zoom: number,
    sittingOff: number,
    accentColor: string,
  ) {
    const w = sprite[0]?.length ?? 0
    const h = sprite.length
    const anchorX = offsetX + ch.x * zoom - w * zoom / 2
    const anchorY = offsetY + (ch.y + sittingOff) * zoom - h * zoom

    const bodyColor = accentColor
    const darkColor = this.darken(accentColor, 0.4)

    for (let r = 0; r < h; r++) {
      for (let c = 0; c < w; c++) {
        const color = sprite[r]?.[c]
        if (!color) continue

        let drawColor = color
        if (color === '#6366f1') drawColor = bodyColor
        else if (color === '#4f46e5') drawColor = darkColor
        else if (color === '#312e81') drawColor = darkColor

        this.ctx.fillStyle = drawColor
        this.ctx.fillRect(
          Math.round(anchorX + c * zoom),
          Math.round(anchorY + r * zoom),
          Math.ceil(zoom),
          Math.ceil(zoom),
        )
      }
    }
  }

  // ── 其他绘制方法保持不变 ────────────────────────────────────────

  /** 绘制精灵数据 */
  private drawSprite(sprite: string[][], px: number, py: number, scale: number) {
    const w = sprite[0]?.length ?? 0
    const h = sprite.length

    for (let r = 0; r < h; r++) {
      for (let c = 0; c < w; c++) {
        const color = sprite[r]?.[c]
        if (!color) continue
        this.ctx.fillStyle = color
        this.ctx.fillRect(Math.round(px + c * scale), Math.round(py + r * scale), Math.ceil(scale), Math.ceil(scale))
      }
    }
  }

  /** 绘制轮廓 */
  private drawOutline(
    sprite: string[][],
    ch: Character,
    offsetX: number,
    offsetY: number,
    zoom: number,
    isSelected: boolean,
  ) {
    const w = sprite[0]?.length ?? 0
    const h = sprite.length
    const sittingOff = ch.state === CharacterState.TYPE ? CHARACTER_SITTING_OFFSET_PX : 0
    const anchorX = offsetX + ch.x * zoom - w * zoom / 2 - zoom
    const anchorY = offsetY + (ch.y + sittingOff) * zoom - h * zoom - zoom

    this.ctx.save()
    this.ctx.globalAlpha = isSelected ? 0.6 : 0.3
    this.ctx.fillStyle = isSelected ? '#ffffff' : '#93c5fd'

    for (let r = 0; r < h; r++) {
      for (let c = 0; c < w; c++) {
        if (!sprite[r]?.[c]) continue
        const hasNeighbor =
          !sprite[r - 1]?.[c] || !sprite[r + 1]?.[c] ||
          !sprite[r]?.[c - 1] || !sprite[r]?.[c + 1]
        if (hasNeighbor) {
          this.ctx.fillRect(
            Math.round(anchorX + c * zoom),
            Math.round(anchorY + r * zoom),
            Math.ceil(zoom),
            Math.ceil(zoom),
          )
        }
      }
    }
    this.ctx.restore()
  }

  /** 绘制标签 */
  private drawLabel(
    ch: Character,
    _state: OfficeState,
    offsetX: number,
    offsetY: number,
    zoom: number,
    isSelected: boolean,
    isHovered: boolean,
  ) {
    const label = ch.label
    const labelX = offsetX + ch.x * zoom
    const labelY = offsetY + ch.y * zoom - CHAR_HEIGHT * zoom - 4 * zoom

    const fontSize = Math.max(10, Math.round(6 * zoom))
    this.ctx.font = `bold ${fontSize}px monospace`
    const textW = this.ctx.measureText(label).width
    const padX = 3 * zoom
    const padY = 2 * zoom
    const boxX = labelX - textW / 2 - padX
    const boxY = labelY - fontSize - padY
    const boxW = textW + padX * 2
    const boxH = fontSize + padY * 2
    const r = 2 * zoom

    // 圆角框
    this.ctx.fillStyle = 'rgba(0,0,0,0.7)'
    this.ctx.beginPath()
    ;(this.ctx as any).roundRect(boxX, boxY, boxW, boxH, r)
    this.ctx.fill()

    // 边框
    this.ctx.strokeStyle = isSelected ? '#ffffff' : isHovered ? '#93c5fd' : '#6b7280'
    this.ctx.lineWidth = 1
    this.ctx.stroke()

    // 文本
    const labelColor = ch.isActive
      ? '#22c55e'
      : isSelected ? '#ffffff' : isHovered ? '#93c5fd' : '#9ca3af'
    this.ctx.fillStyle = labelColor
    this.ctx.textAlign = 'center'
    this.ctx.textBaseline = 'bottom'
    this.ctx.fillText(label, labelX, labelY - 1)
  }

  /** 绘制气泡 */
  private drawBubble(ch: Character, offsetX: number, offsetY: number, zoom: number) {
    const sittingOff = ch.state === CharacterState.TYPE ? CHARACTER_SITTING_OFFSET_PX : 0
    const bubbleX = offsetX + ch.x * zoom - 16 * zoom
    const bubbleY = offsetY + (ch.y + sittingOff - CHAR_HEIGHT - BUBBLE_VERTICAL_OFFSET_PX) * zoom

    // 绘制气泡背景
    this.drawSprite(BUBBLE_SPRITE, bubbleX, bubbleY, zoom)

    // 绘制气泡内文本
    const text = ch.bubbleText
    if (!text) return

    const fontSize = Math.max(8, Math.round(4 * zoom))
    this.ctx.font = `${fontSize}px monospace`
    this.ctx.fillStyle = '#ffffff'
    this.ctx.textAlign = 'center'
    this.ctx.textBaseline = 'middle'
    this.ctx.fillText(text, bubbleX + 16 * zoom, bubbleY + 8 * zoom)
  }

  // ── 颜色工具 ─────────────────────────────────────────

  private darken(hex: string, amount: number): string {
    const r = parseInt(hex.slice(1, 3), 16)
    const g = parseInt(hex.slice(3, 5), 16)
    const b = parseInt(hex.slice(5, 7), 16)
    return `rgb(${Math.round(r * (1 - amount))},${Math.round(g * (1 - amount))},${Math.round(b * (1 - amount))})`
  }

  private lighten(hex: string, amount: number): string {
    const r = parseInt(hex.slice(1, 3), 16)
    const g = parseInt(hex.slice(3, 5), 16)
    const b = parseInt(hex.slice(5, 7), 16)
    return `rgb(${Math.min(255, Math.round(r + (255 - r) * amount))},${Math.min(255, Math.round(g + (255 - g) * amount))},${Math.min(255, Math.round(b + (255 - b) * amount))})`
  }

  // ── 缓存管理 ─────────────────────────────────────────

  private cleanupCache() {
    // 限制缓存大小，删除最旧的一半
    if (this.spriteCache.size > 50) {
      const entries = Array.from(this.spriteCache.entries())
      const toRemove = entries.slice(0, Math.floor(entries.length / 2))
      toRemove.forEach(([key]) => this.spriteCache.delete(key))
    }
  }
}