/** PixelOffice types — shared across the pixel office engine.
 *
 * Based on OpenClaw-bot-review/lib/pixel-office/types.ts
 */

// ── Grid & Physics ──────────────────────────────────────────────
export const TILE_SIZE = 16    // pixels per tile
export const CHAR_WIDTH = 16   // character sprite width
export const CHAR_HEIGHT = 24  // character sprite height (anchored bottom-center)

// ── Character States ─────────────────────────────────────────────
export const CharacterState = {
  IDLE: 'idle',
  WALK: 'walk',
  TYPE: 'type',   // seated, working at desk
} as const
export type CharacterState = (typeof CharacterState)[keyof typeof CharacterState]

// ── Directions ──────────────────────────────────────────────────
export const Direction = {
  DOWN:  0,
  LEFT:  1,
  RIGHT: 2,
  UP:    3,
} as const
export type Direction = (typeof Direction)[keyof typeof Direction]

// ── Sprite Data ─────────────────────────────────────────────────
// 2D array of hex color strings ('' = transparent). [row][col]
export type SpriteData = string[][]

// ── Floor Tiles ─────────────────────────────────────────────────
export const TileType = {
  WALL:    0,
  FLOOR_1: 1,
  FLOOR_2: 2,
  FLOOR_3: 3,
  VOID:    8,
} as const
export type TileType = (typeof TileType)[keyof typeof TileType]

// ── Seats ────────────────────────────────────────────────────────
export interface Seat {
  uid: string
  seatCol: number   // tile column
  seatRow: number   // tile row
  facingDir: Direction
  assigned: boolean
  agentId: string | null  // backend agent_id
}

// ── Office Layout ───────────────────────────────────────────────
export interface OfficeLayout {
  cols: number
  rows: number
  tiles: TileType[][]
  seats: Seat[]
}

// ── Character ───────────────────────────────────────────────────
export interface Character {
  // Identity
  id: number                    // 0-5 for 6 agents
  agentId: string              // backend agent_id: "profile_agent" etc.
  label: string                // display name: "小档" etc.

  // Position
  x: number                    // pixel center x
  y: number                    // pixel center y
  tileCol: number              // current tile column
  tileRow: number              // current tile row

  // Movement
  state: CharacterState
  dir: Direction
  frame: number               // animation frame (0-3)
  frameTimer: number          // time accumulator for animation
  moveSpeed: number           // pixels per second

  // Status
  isActive: boolean           // true = working, false = idle
  currentTool: string | null  // "typing", "reading", etc.

  // Visual effects
  bubbleText: string          // floating text above head
  bubbleTimer: number         // countdown to hide bubble
  bubbleType: 'task' | 'output' | 'error' | null
  matrixEffect: 'spawn' | 'despawn' | null
  matrixEffectTimer: number

  // Seat
  seatId: string | null      // uid of assigned seat
}

// ── Office State ────────────────────────────────────────────────
export interface OfficeStateData {
  layout: OfficeLayout
  characters: Map<number, Character>  // keyed by agent index 0-5
  selectedAgentId: number | null
  hoveredAgentId: number | null
  nextAvailableSeat: number  // circular index for auto-assignment
}
