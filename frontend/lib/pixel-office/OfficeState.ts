/** OfficeState — core game state manager for PixelOffice.
 *
 * Manages 6 agent characters, their positions, states, and animations.
 * Responds to SSE events from the backend to update agent states.
 *
 * Based on OpenClaw-bot-review's OfficeState class.
 */

import {
  TILE_SIZE, CHAR_HEIGHT,
  type Character, type OfficeLayout, type Seat,
  type CharacterState, type Direction, CharacterState as CS, Direction as DIR,
} from './types'
import {
  WALK_SPEED_PX_PER_SEC,
  WALK_FRAME_DURATION_SEC,
  TYPE_FRAME_DURATION_SEC,
  CHARACTER_SITTING_OFFSET_PX,
  BUBBLE_DURATION_SEC,
  MATRIX_EFFECT_DURATION,
  AGENT_PALETTES,
} from './constants'
import { CHARACTER_SPRITES } from './sprites/spriteData'
import { createDefaultLayout } from './layout/defaultLayout'

// ── Agent → Sprite type mapping ───────────────────────────────
const AGENT_SPRITE_TYPE: Record<string, keyof typeof CHARACTER_SPRITES> = {
  profile_agent:          'analysis',
  hot_topic_agent:       'analysis',
  topic_planner_agent:   'planning',
  title_generator_agent: 'creation',
  content_writer_agent:  'creation',
  audit_agent:           'audit',
}

// ── Agent config ───────────────────────────────────────────────
const AGENT_CONFIG = [
  { agentId: 'profile_agent',          name: '小档', role: '账号解析'   },
  { agentId: 'hot_topic_agent',       name: '小热', role: '热点分析'   },
  { agentId: 'topic_planner_agent',   name: '小策', role: '选题策划'   },
  { agentId: 'title_generator_agent', name: '小标', role: '标题生成'   },
  { agentId: 'content_writer_agent',  name: '小文', role: '正文生成'   },
  { agentId: 'audit_agent',          name: '小审', role: '审核评估'   },
]

function tileCenter(col: number, row: number) {
  return {
    x: col * TILE_SIZE + TILE_SIZE / 2,
    y: row * TILE_SIZE + TILE_SIZE / 2,
  }
}

export class OfficeState {
  layout: OfficeLayout
  characters: Map<number, Character> = new Map()
  selectedAgentId: number | null = null
  hoveredAgentId: number | null = null

  constructor(layout?: OfficeLayout) {
    this.layout = layout || createDefaultLayout()
    this.initCharacters()
  }

  private initCharacters() {
    AGENT_CONFIG.forEach((config, idx) => {
      const seat = this.layout.seats.find(s => s.agentId === config.agentId)
      const center = seat
        ? tileCenter(seat.seatCol, seat.seatRow)
        : tileCenter(1, 1)
      const dir = seat?.facingDir ?? DIR.DOWN

      const ch: Character = {
        id: idx,
        agentId: config.agentId,
        label: config.name,
        x: center.x,
        y: center.y,
        tileCol: Math.round(center.x / TILE_SIZE),
        tileRow: Math.round(center.y / TILE_SIZE),
        state: CS.IDLE,
        dir,
        frame: 0,
        frameTimer: 0,
        moveSpeed: WALK_SPEED_PX_PER_SEC,
        isActive: false,
        currentTool: null,
        bubbleText: '',
        bubbleTimer: 0,
        bubbleType: null,
        matrixEffect: 'spawn',
        matrixEffectTimer: 0,
        seatId: seat?.uid ?? null,
      }
      this.characters.set(idx, ch)
    })
  }

  // ── Character lookup ─────────────────────────────────────────
  getCharacterByAgentId(agentId: string): Character | undefined {
    for (const ch of this.characters.values()) {
      if (ch.agentId === agentId) return ch
    }
    return undefined
  }

  getCharacter(id: number): Character | undefined {
    return this.characters.get(id)
  }

  getAllCharacters(): Character[] {
    return Array.from(this.characters.values())
  }

  // ── Update loop (called every frame) ────────────────────────
  update(dt: number): void {
    for (const ch of this.characters.values()) {
      this.updateCharacter(ch, dt)
    }
  }

  private updateCharacter(ch: Character, dt: number): void {
    ch.frameTimer += dt

    // Matrix spawn/despawn animation
    if (ch.matrixEffect) {
      ch.matrixEffectTimer += dt
      if (ch.matrixEffectTimer >= MATRIX_EFFECT_DURATION) {
        ch.matrixEffect = null
        ch.matrixEffectTimer = 0
      }
      return
    }

    // Bubble countdown
    if (ch.bubbleTimer > 0) {
      ch.bubbleTimer -= dt
      if (ch.bubbleTimer <= 0) {
        ch.bubbleText = ''
        ch.bubbleType = null
        ch.bubbleTimer = 0
      }
    }

    switch (ch.state) {
      case CS.TYPE: {
        // Typing animation: alternate frame every TYPE_FRAME_DURATION
        if (ch.frameTimer >= TYPE_FRAME_DURATION_SEC) {
          ch.frameTimer -= TYPE_FRAME_DURATION_SEC
          ch.frame = (ch.frame + 1) % 2
        }
        break
      }
      case CS.WALK: {
        if (ch.frameTimer >= WALK_FRAME_DURATION_SEC) {
          ch.frameTimer -= WALK_FRAME_DURATION_SEC
          ch.frame = (ch.frame + 1) % 4
        }
        break
      }
      case CS.IDLE: {
        ch.frame = 0
        break
      }
    }
  }

  // ── SSE Event handlers ──────────────────────────────────────

  /** Agent started executing — set to TYPE state, show bubble */
  onNodeStart(agentId: string, name: string) {
    const ch = this.getCharacterByAgentId(agentId)
    if (!ch) return

    ch.isActive = true
    ch.state = CS.TYPE
    ch.currentTool = 'typing'
    ch.bubbleText = `▶ ${name}`
    ch.bubbleTimer = BUBBLE_DURATION_SEC
    ch.bubbleType = 'task'
  }

  /** Agent completed — show output summary bubble */
  onNodeComplete(
    agentId: string,
    name: string,
    outputSummary: string,
    _elapsedSeconds: number,
  ) {
    const ch = this.getCharacterByAgentId(agentId)
    if (!ch) return

    ch.isActive = false
    ch.state = CS.IDLE
    ch.currentTool = null
    // Show brief completion feedback
    ch.bubbleText = `✓ ${outputSummary.slice(0, 12) || name}`
    ch.bubbleTimer = 3.0
    ch.bubbleType = 'output'
  }

  /** Agent failed — show error bubble */
  onNodeError(agentId: string, error: string) {
    const ch = this.getCharacterByAgentId(agentId)
    if (!ch) return

    ch.isActive = false
    ch.state = CS.IDLE
    ch.currentTool = null
    ch.bubbleText = `✗ ${error.slice(0, 12)}`
    ch.bubbleTimer = 5.0
    ch.bubbleType = 'error'
  }

  // ── Selection ────────────────────────────────────────────────

  selectAgent(id: number | null) {
    this.selectedAgentId = id
  }

  hoverAgent(id: number | null) {
    this.hoveredAgentId = id
  }

  // ── Sprite data access ─────────────────────────────────────

  /** Get the sprite data for a character at current frame */
  getSpriteData(ch: Character): string[][] {
    const type = AGENT_SPRITE_TYPE[ch.agentId] ?? 'idle'
    const sprites = CHARACTER_SPRITES[type]

    switch (ch.state) {
      case CS.TYPE:
        return sprites.type[ch.dir] ?? sprites.idle[ch.dir]
      case CS.WALK:
        return sprites.walk[ch.dir]?.[ch.frame % 4] ?? sprites.idle[ch.dir]
      default:
        return sprites.idle[ch.dir] ?? sprites.idle[DIR.DOWN]
    }
  }

  /** Get palette color for agent */
  getAgentColor(agentId: string): string {
    const idx = AGENT_CONFIG.findIndex(a => a.agentId === agentId)
    return AGENT_PALETTES[idx % AGENT_PALETTES.length]
  }
}
