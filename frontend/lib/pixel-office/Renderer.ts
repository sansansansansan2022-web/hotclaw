/** PixelOffice renderer — Canvas 2D rendering for the pixel office.
 *
 * Renders tiles, furniture, characters, and bubbles with Z-sorting.
 * Uses imageSmoothingEnabled = false for crisp pixel art.
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
}

export class Renderer {
  private canvas: HTMLCanvasElement
  private ctx: CanvasRenderingContext2D
  zoom: number
  
  // 性能优化：缓存系统
  private spriteCache: Map<string, ImageData> = new Map()
  private colorCache: Map<string, Map<string, string>> = new Map()
  private lastDrawables: Drawable[] = []
  private dirtyRects: { x: number; y: number; width: number; height: number }[] = []

  constructor(canvas: HTMLCanvasElement, zoom = 2) {
    this.canvas = canvas
    this.ctx = canvas.getContext('2d')!
    this.zoom = zoom
    this.ctx.imageSmoothingEnabled = false
    
    // 初始化缓存
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
      this.colorCache.set(`palette_${index}`, paletteMap)
    })
  }
  
  // 清空缓存
  private clearCache() {
    this.spriteCache.clear()
    this.dirtyRects = []
  }

  render(state: OfficeState) {
    const { ctx, canvas, zoom } = this
    const { layout, selectedAgentId, hoveredAgentId } = state

    // Clear
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Compute centering offset
    const mapW = layout.cols * TILE_SIZE * zoom
    const mapH = layout.rows * TILE_SIZE * zoom
    const offsetX = Math.floor((canvas.width - mapW) / 2)
    const offsetY = Math.floor((canvas.height - mapH) / 2)

    // Draw tiles
    this.renderTileGrid(layout, offsetX, offsetY)

    // Build drawables (furniture + characters with Z-sorting)
    const drawables: Drawable[] = []

    // Seats → draw desk + monitor at each seat
    for (const seat of layout.seats) {
      const char_ = seat.agentId ? state.getCharacterByAgentId(seat.agentId) : undefined
      const isActive = char_?.isActive ?? false

      // Desk (2x2 tiles, sits behind character)
      drawables.push({
        zY: seat.seatRow * TILE_SIZE + TILE_SIZE,
        draw: (c) => this.drawSprite(DESK_SPRITE, offsetX + seat.seatCol * TILE_SIZE * zoom, offsetY + seat.seatRow * TILE_SIZE * zoom, zoom),
      })

      // Monitor (1x1 tile, on top of desk)
      drawables.push({
        zY: seat.seatRow * TILE_SIZE + TILE_SIZE + 0.5,
        draw: (c) => {
          this.drawSprite(
            MONITOR_SPRITE,
            offsetX + (seat.seatCol + 0.5) * TILE_SIZE * zoom,
            offsetY + (seat.seatRow - 0.5) * TILE_SIZE * zoom,
            zoom * 0.8,
          )
          // Screen glow when active
          if (isActive) {
            const gx = offsetX + (seat.seatCol + 1) * TILE_SIZE * zoom
            const gy = offsetY + (seat.seatRow - 0.3) * TILE_SIZE * zoom
            const grad = c.createRadialGradient(gx, gy, 0, gx, gy, TILE_SIZE * zoom)
            grad.addColorStop(0, 'rgba(14,165,233,0.3)')
            grad.addColorStop(1, 'rgba(14,165,233,0)')
            c.fillStyle = grad
            c.fillRect(gx - TILE_SIZE * zoom, gy - TILE_SIZE * zoom, TILE_SIZE * zoom * 2, TILE_SIZE * zoom * 2)
          }
        },
      })
    }

    // Characters — Z-sorted by y + TILE_SIZE/2
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

      // Character sprite
      drawables.push({
        zY: charZY,
        draw: (c) => {
          const agentIdx = Array.from(state.getAllCharacters()).findIndex(ch_ => ch_.id === ch.id)
          const color = AGENT_PALETTES[agentIdx % AGENT_PALETTES.length]
          this.drawCharacterSprite(spriteData, ch, offsetX, offsetY, zoom, sittingOff, color)
        },
      })

      // Label above head
      drawables.push({
        zY: charZY + 0.1,
        draw: (c) => this.drawLabel(ch, state, offsetX, offsetY, zoom, selectedAgentId === ch.id, hoveredAgentId === ch.id),
      })

      // Bubble above head
      if (ch.bubbleText) {
        drawables.push({
          zY: charZY + 0.2,
          draw: (c) => this.drawBubble(ch, offsetX, offsetY, zoom),
        })
      }

      // Selection outline
      if (selectedAgentId === ch.id || hoveredAgentId === ch.id) {
        drawables.push({
          zY: charZY - 0.1,
          draw: (c) => this.drawOutline(spriteData, ch, offsetX, offsetY, zoom, selectedAgentId === ch.id),
        })
      }
    }

    // Sort by Z, lower = further back = drawn first
    drawables.sort((a, b) => a.zY - b.zY)

    for (const d of drawables) {
      d.draw(ctx)
    }
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

    // Subtle grid lines
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

  // ── Sprite rendering ────────────────────────────────────────

  /** Draw a SpriteData (2D color array) at pixel position */
  private drawSprite(sprite: string[][], px: number, py: number, scale: number) {
    const { ctx } = this
    const w = sprite[0]?.length ?? 0
    const h = sprite.length

    for (let r = 0; r < h; r++) {
      for (let c = 0; c < w; c++) {
        const color = sprite[r]?.[c]
        if (!color) continue
        ctx.fillStyle = color
        ctx.fillRect(Math.round(px + c * scale), Math.round(py + r * scale), Math.ceil(scale), Math.ceil(scale))
      }
    }
  }

  /** Draw a character sprite with agent-specific color tinting */
  private drawCharacterSprite(
    sprite: string[][],
    ch: Character,
    offsetX: number,
    offsetY: number,
    zoom: number,
    sittingOff: number,
    accentColor: string,
  ) {
    const { ctx } = this
    const w = sprite[0]?.length ?? 0
    const h = sprite.length

    // Anchor: bottom-center of sprite at (ch.x, ch.y)
    const anchorX = offsetX + ch.x * zoom - w * zoom / 2
    const anchorY = offsetY + (ch.y + sittingOff) * zoom - h * zoom

    // Draw character with color tint on body pixels
    const bodyColor = accentColor
    const darkColor = this.darken(accentColor, 0.4)
    const lightColor = this.lighten(accentColor, 0.2)

    for (let r = 0; r < h; r++) {
      for (let c = 0; c < w; c++) {
        const color = sprite[r]?.[c]
        if (!color) continue

        // Map palette colors to agent accent
        let drawColor = color
        if (color === '#6366f1') drawColor = bodyColor      // agent blue → agent accent
        else if (color === '#4f46e5') drawColor = darkColor // shadow
        else if (color === '#312e81') drawColor = darkColor  // dark

        ctx.fillStyle = drawColor
        ctx.fillRect(
          Math.round(anchorX + c * zoom),
          Math.round(anchorY + r * zoom),
          Math.ceil(zoom),
          Math.ceil(zoom),
        )
      }
    }
  }

  // ── Outline (selection/hover) ───────────────────────────────

  private drawOutline(
    sprite: string[][],
    ch: Character,
    offsetX: number,
    offsetY: number,
    zoom: number,
    isSelected: boolean,
  ) {
    const { ctx } = this
    const w = sprite[0]?.length ?? 0
    const h = sprite.length
    const sittingOff = ch.state === CharacterState.TYPE ? CHARACTER_SITTING_OFFSET_PX : 0
    const anchorX = offsetX + ch.x * zoom - w * zoom / 2 - zoom
    const anchorY = offsetY + (ch.y + sittingOff) * zoom - h * zoom - zoom

    ctx.save()
    ctx.globalAlpha = isSelected ? 0.6 : 0.3
    ctx.fillStyle = isSelected ? '#ffffff' : '#93c5fd'

    // Draw 1px outline around sprite
    for (let r = 0; r < h; r++) {
      for (let c = 0; c < w; c++) {
        if (!sprite[r]?.[c]) continue
        // Check if this is an edge pixel
        const hasNeighbor =
          !sprite[r - 1]?.[c] || !sprite[r + 1]?.[c] ||
          !sprite[r]?.[c - 1] || !sprite[r]?.[c + 1]
        if (hasNeighbor) {
          ctx.fillRect(
            Math.round(anchorX + c * zoom),
            Math.round(anchorY + r * zoom),
            Math.ceil(zoom),
            Math.ceil(zoom),
          )
        }
      }
    }
    ctx.restore()
  }

  // ── Label ─────────────────────────────────────────────────

  private drawLabel(
    ch: Character,
    _state: OfficeState,
    offsetX: number,
    offsetY: number,
    zoom: number,
    isSelected: boolean,
    isHovered: boolean,
  ) {
    const { ctx } = this
    const label = ch.label
    const labelX = offsetX + ch.x * zoom
    const labelY = offsetY + ch.y * zoom - CHAR_HEIGHT * zoom - 4 * zoom

    const fontSize = Math.max(10, Math.round(6 * zoom))
    ctx.font = `bold ${fontSize}px monospace`
    const textW = ctx.measureText(label).width
    const padX = 3 * zoom
    const padY = 2 * zoom
    const boxX = labelX - textW / 2 - padX
    const boxY = labelY - fontSize - padY
    const boxW = textW + padX * 2
    const boxH = fontSize + padY * 2
    const r = 2 * zoom

    // Rounded box
    ctx.fillStyle = 'rgba(0,0,0,0.7)'
    ctx.beginPath()
    ctx.roundRect(boxX, boxY, boxW, boxH, r)
    ctx.fill()

    // Border
    ctx.strokeStyle = isSelected ? '#ffffff' : isHovered ? '#93c5fd' : '#6b7280'
    ctx.lineWidth = 1
    ctx.stroke()

    // Text
    const labelColor = ch.isActive
      ? '#22c55e'
      : isSelected ? '#ffffff' : isHovered ? '#93c5fd' : '#9ca3af'
    ctx.fillStyle = labelColor
    ctx.textAlign = 'center'
    ctx.textBaseline = 'bottom'
    ctx.fillText(label, labelX, labelY - 1)
  }

  // ── Bubble ─────────────────────────────────────────────────

  private drawBubble(ch: Character, offsetX: number, offsetY: number, zoom: number) {
    const { ctx } = this
    const sittingOff = ch.state === CharacterState.TYPE ? CHARACTER_SITTING_OFFSET_PX : 0
    const bubbleX = offsetX + ch.x * zoom - 16 * zoom
    const bubbleY = offsetY + (ch.y + sittingOff - CHAR_HEIGHT - BUBBLE_VERTICAL_OFFSET_PX) * zoom

    // Draw bubble background
    this.drawSprite(BUBBLE_SPRITE, bubbleX, bubbleY, zoom)

    // Draw text inside bubble
    const text = ch.bubbleText
    if (!text) return

    const fontSize = Math.max(8, Math.round(4 * zoom))
    ctx.font = `${fontSize}px monospace`
    ctx.fillStyle = '#ffffff'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(text, bubbleX + 16 * zoom, bubbleY + 8 * zoom)
  }

  // ── Color utilities ─────────────────────────────────────────

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
}
