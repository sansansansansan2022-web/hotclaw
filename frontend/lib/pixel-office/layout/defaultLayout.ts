/** Default editorial office layout for HotClaw.
 *
 * Grid: 21 cols × 17 rows × 16px tiles = 336×272px @ 1x
 * Seats are positioned to match the LargePixelOffice.png scene.
 *
 * Agent mapping (matches AGENT_CELL in assets.ts):
 *   0: profile_agent          → 分析型 (蓝紫)
 *   1: hot_topic_agent       → 分析型 (蓝紫)
 *   2: topic_planner_agent   → 策划型 (橙)
 *   3: title_generator_agent  → 创作型 (绿)
 *   4: content_writer_agent   → 创作型 (绿)
 *   5: audit_agent           → 审核型 (紫)
 */

import { Direction, TileType, type OfficeLayout, type Seat } from '../types'

export const DEFAULT_COLS = 21
export const DEFAULT_ROWS = 17

// ── Tile map ──────────────────────────────────────────────────
// 0=墙, 1=地板1(浅), 2=地板2(深), 8=虚空
export function createDefaultTileMap(): TileType[][] {
  const tiles: TileType[][] = []
  for (let r = 0; r < DEFAULT_ROWS; r++) {
    const row: TileType[] = []
    for (let c = 0; c < DEFAULT_COLS; c++) {
      // Wall border
      if (r === 0 || r === DEFAULT_ROWS - 1 || c === 0 || c === DEFAULT_COLS - 1) {
        row.push(TileType.WALL)
      }
      // Entry area (left side, rows 12-16)
      else if (r >= 12 && r <= 15 && c <= 2) {
        row.push(TileType.FLOOR_1)
      }
      // Sofa area (bottom left, rows 13-16, cols 3-7)
      else if (r >= 13 && r <= 15 && c >= 3 && c <= 7) {
        row.push(TileType.FLOOR_2)
      }
      // Server rack area (left wall, rows 10-14)
      else if (r >= 10 && r <= 14 && c <= 1) {
        row.push(TileType.FLOOR_1)
      }
      // Main work area (center, rows 1-12)
      else if (r >= 1 && r <= 12) {
        // Alternating floor pattern
        row.push((r + c) % 2 === 0 ? TileType.FLOOR_1 : TileType.FLOOR_2)
      }
      // Lower area (rows 13-16, right side)
      else if (r >= 13) {
        row.push(TileType.FLOOR_1)
      }
      // Everything else = void
      else {
        row.push(TileType.VOID)
      }
    }
    tiles.push(row)
  }
  return tiles
}

// ── Seats (workstations) ────────────────────────────────────────
// Each agent has a fixed seat. Seat position = tile col/row.
// Agent faces toward their desk (for monitor rendering).

const SEATS: Seat[] = [
  {
    uid: 'seat-0',
    agentId: 'profile_agent',
    seatCol: 3,
    seatRow: 8,
    facingDir: Direction.DOWN,
    assigned: true,
  },
  {
    uid: 'seat-1',
    agentId: 'hot_topic_agent',
    seatCol: 6,
    seatRow: 5,
    facingDir: Direction.DOWN,
    assigned: true,
  },
  {
    uid: 'seat-2',
    agentId: 'topic_planner_agent',
    seatCol: 10,
    seatRow: 7,
    facingDir: Direction.DOWN,
    assigned: true,
  },
  {
    uid: 'seat-3',
    agentId: 'title_generator_agent',
    seatCol: 13,
    seatRow: 5,
    facingDir: Direction.DOWN,
    assigned: true,
  },
  {
    uid: 'seat-4',
    agentId: 'content_writer_agent',
    seatCol: 16,
    seatRow: 8,
    facingDir: Direction.DOWN,
    assigned: true,
  },
  {
    uid: 'seat-5',
    agentId: 'audit_agent',
    seatCol: 19,
    seatRow: 6,
    facingDir: Direction.DOWN,
    assigned: true,
  },
]

export const DEFAULT_SEATS = SEATS

export function createDefaultLayout(): OfficeLayout {
  return {
    cols: DEFAULT_COLS,
    rows: DEFAULT_ROWS,
    tiles: createDefaultTileMap(),
    seats: SEATS,
  }
}
