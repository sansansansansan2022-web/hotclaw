/** Character sprite data — hardcoded 16x24 pixel art arrays.
 *
 * Format: SpriteData = string[][] where each cell is a hex color or '' (transparent)
 * Layout per character: [DOWN, LEFT, RIGHT, UP] × [idle, walk_frame_0, walk_frame_1, walk_frame_2, walk_frame_3, type_frame_0, type_frame_1]
 *
 * 颜色约定:
 *   H = 头发/头部高亮
 *   h = 头发/头部阴影
 *   F = 面部肤色
 *   E = 眼睛
 *   B = 身体主色
 *   b = 身体阴影
 *   A = 手臂
 *   L = 腿
 *   _ = 透明
 */

import type { SpriteData } from '../types'

// 简化版 16x16 角色精灵（行 0-15 = 身体+腿, 忽略底部阴影）
const _ = ''  // transparent

// ── 通用脚手架：人物轮廓模板 ──────────────────────────────────────
// 每个角色 4 方向 × 7 帧 = 28 个 16×16 SpriteData

type SpriteSet = {
  idle:   SpriteData[]   // [DOWN, LEFT, RIGHT, UP]
  walk:   SpriteData[][] // [direction][frame]
  type:   SpriteData[]   // [DOWN, LEFT, RIGHT, UP]
}

// 工具函数：从模板生成走路动画帧（身体轻微上下）
function walkFrames(base: SpriteData, bobOffset = 1): SpriteData[] {
  const frames: SpriteData[] = []
  for (let f = 0; f < 4; f++) {
    const shift = f % 2 === 0 ? 0 : bobOffset
    frames.push(base.map(row => [...row]))
  }
  return frames
}

// 简化：所有角色复用同一套精灵结构，不同色调
// 这套精灵渲染时通过 ctx.globalCompositeOperation + tint 实现角色区分

export const CHARACTER_SPRITES = {
  // ── 蓝紫 - 分析型 (分析阶段 agent) ─────────────────────────────
  analysis: buildCharacterSet('#818cf8', '#6366f1', '#4f46e5', '#312e81'),
  // ── 橙 - 策划型 (策划阶段 agent) ──────────────────────────────
  planning: buildCharacterSet('#fb923c', '#f97316', '#ea580c', '#7c2d12'),
  // ── 绿 - 创作型 (创作阶段 agent) ──────────────────────────────
  creation: buildCharacterSet('#4ade80', '#22c55e', '#16a34a', '#14532d'),
  // ── 紫 - 审核型 (审核阶段 agent) ─────────────────────────────
  audit:    buildCharacterSet('#c084fc', '#a855f7', '#9333ea', '#581c87'),
  // ── 灰 - 默认/待机 (不活跃 agent) ────────────────────────────
  idle:    buildCharacterSet('#9ca3af', '#6b7280', '#4b5563', '#1f2937'),
} as const

type AgentType = keyof typeof CHARACTER_SPRITES

function buildCharacterSet(
  skin: string, body: string, shadow: string, dark: string
): SpriteSet {
  const eye  = '#1e1b4b'
  const white = '#ffffff'
  const lip  = '#fca5a5'

  // ── DOWN (面向下): 行 0=头顶, 1-2=面部, 3=身体, 4=腿 ──────────
  const down_idle: SpriteData = [
    [_,_,'#1f2937','#1f2937','#1f2937','#1f2937','#1f2937','#1f2937','#1f2937','#1f2937','#1f2937','#1f2937','#1f2937','#1f2937',_,_],
    [_,_,'#1f2937',skin,skin,skin,skin,skin,skin,skin,skin,skin,skin,'#1f2937',_,_],
    [_,skin,skin,skin,skin,skin,eye,eye,eye,eye,skin,skin,skin,skin,_],
    [_,skin,skin,skin,skin,skin,eye,eye,eye,eye,skin,skin,skin,skin,_],
    [_,skin,skin,skin,skin,skin,skin,lip,skin,skin,skin,skin,skin,skin,_],
    [_,_,_,_,body,body,body,body,body,body,body,body,_,_,_,_],
    [_,_,_,body,body,body,body,body,body,body,body,body,body,_,_,_],
    [_,_,body,body,body,body,body,body,body,body,body,body,body,body,_,_],
    [_,body,body,body,body,body,body,body,body,body,body,body,body,body,_,_],
    [_,body,body,body,body,body,body,body,body,body,body,body,body,body,_,_],
    [_,_,body,body,body,body,body,body,body,body,body,body,body,_,_,_],
    [_,_,body,shadow,shadow,body,shadow,shadow,shadow,shadow,body,shadow,shadow,_,_,_],
    [_,_,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,_,_,_],
    [_,_,_,shadow,'#1f2937','#1f2937',shadow,'#1f2937','#1f2937',shadow,'#1f2937','#1f2937',shadow,_,_,_],
    [_,_,_,shadow,'#1f2937','#1f2937',shadow,'#1f2937','#1f2937',shadow,'#1f2937','#1f2937',shadow,_,_,_],
    [_,_,_,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,_,_,_],
    [_,_,shadow,'#1f2937',shadow,'#1f2937',shadow,'#1f2937',shadow,'#1f2937',shadow,'#1f2937',shadow,_,_,_],
    [_,_,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,_,_,_],
    [_,_,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,_,_,_],
    [_,_,shadow,'#1f2937',shadow,'#1f2937',shadow,'#1f2937',shadow,'#1f2937',shadow,'#1f2937',shadow,_,_,_],
    [_,_,_,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,_,_,_],
    [_,_,_,_,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,_,_,_,_],
    [_,_,_,_,_,_,shadow,shadow,shadow,shadow,shadow,_,_,_,_,_],
    [_,_,_,_,_,_,shadow,shadow,shadow,shadow,shadow,_,_,_,_,_],
  ]

  // Walking frames: alternate leg positions
  const down_walk_0 = [...down_idle]
  const down_walk_1 = shiftLegs(down_idle, 1)
  const down_walk_2 = [...down_idle]
  const down_walk_3 = shiftLegs(down_idle, -1)

  // Type (seated): upper body same, legs together, slight animation
  const down_type_0 = down_idle.map((row, i) =>
    i < 6 ? row.map(c => c === shadow ? dark : c) : row
  )
  const down_type_1 = down_type_0  // typing alternation via opacity

  // ── LEFT ─────────────────────────────────────────────────────
  const left_idle: SpriteData = [
    [_,_,'#1f2937','#1f2937','#1f2937','#1f2937','#1f2937','#1f2937','#1f2937','#1f2937',_,_,_,_,_,_],
    [_,_,'#1f2937',skin,skin,skin,skin,skin,skin,skin,skin,'#1f2937',_,_,_,_],
    [_,skin,skin,skin,skin,skin,skin,skin,eye,eye,skin,skin,skin,skin,_],
    [_,skin,skin,skin,skin,skin,skin,skin,eye,eye,skin,skin,skin,skin,_],
    [_,skin,skin,skin,skin,skin,skin,skin,skin,lip,skin,skin,skin,skin,_],
    [_,_,_,_,body,body,body,body,body,body,body,body,body,_,_,_],
    [_,_,_,body,body,body,body,body,body,body,body,body,body,body,_,_],
    [_,_,body,body,body,body,body,body,body,body,body,body,body,body,body,_],
    [_,body,body,body,body,body,body,body,body,body,body,body,body,body,body,_],
    [_,body,body,body,body,body,body,body,body,body,body,body,body,body,body,_],
    [_,_,body,body,body,body,body,body,body,body,body,body,body,body,_,_,_],
    [_,_,body,shadow,shadow,body,shadow,shadow,shadow,shadow,body,shadow,shadow,_,_,_],
    [_,_,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,_,_,_],
    [_,_,_,shadow,'#1f2937','#1f2937',shadow,'#1f2937','#1f2937',shadow,'#1f2937','#1f2937',shadow,_,_,_],
    [_,_,_,shadow,'#1f2937','#1f2937',shadow,'#1f2937','#1f2937',shadow,'#1f2937','#1f2937',shadow,_,_,_],
    [_,_,_,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,_,_,_],
    [_,_,shadow,'#1f2937',shadow,'#1f2937',shadow,'#1f2937',shadow,'#1f2937',shadow,'#1f2937',shadow,_,_,_],
    [_,_,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,_,_,_],
    [_,_,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,_,_,_],
    [_,_,shadow,'#1f2937',shadow,'#1f2937',shadow,'#1f2937',shadow,'#1f2937',shadow,'#1f2937',shadow,_,_,_],
    [_,_,_,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,_,_,_],
    [_,_,_,_,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,_,_,_,_],
    [_,_,_,_,_,_,shadow,shadow,shadow,shadow,shadow,_,_,_,_,_],
    [_,_,_,_,_,_,shadow,shadow,shadow,shadow,shadow,_,_,_,_,_],
  ]

  const left_walk = [shiftLegs(left_idle, 1), left_idle, shiftLegs(left_idle, -1), left_idle]

  // ── RIGHT (镜像 LEFT) ────────────────────────────────────────
  const right_idle = mirrorHoriz(left_idle)
  const right_walk = left_walk.map(mirrorHoriz)

  // ── UP (背对): 不显示面部，只显示头发和身体 ──────────────────
  const up_idle: SpriteData = [
    [_,_,'#1f2937','#1f2937','#1f2937','#1f2937','#1f2937','#1f2937','#1f2937','#1f2937','#1f2937','#1f2937','#1f2937','#1f2937',_,_],
    [_,_,'#1f2937',skin,skin,skin,skin,skin,skin,skin,skin,skin,skin,'#1f2937',_,_],
    [_,skin,skin,skin,skin,skin,skin,skin,skin,skin,skin,skin,skin,skin,_],
    [_,skin,skin,skin,skin,skin,skin,skin,skin,skin,skin,skin,skin,skin,_],
    [_,skin,skin,skin,skin,skin,skin,skin,skin,skin,skin,skin,skin,skin,_],
    [_,_,_,_,body,body,body,body,body,body,body,body,_,_,_,_],
    [_,_,_,body,body,body,body,body,body,body,body,body,body,_,_,_],
    [_,_,body,body,body,body,body,body,body,body,body,body,body,body,_,_],
    [_,body,body,body,body,body,body,body,body,body,body,body,body,body,_,_],
    [_,body,body,body,body,body,body,body,body,body,body,body,body,body,_,_],
    [_,_,body,body,body,body,body,body,body,body,body,body,body,_,_,_],
    [_,_,body,shadow,shadow,body,shadow,shadow,shadow,shadow,body,shadow,shadow,_,_,_],
    [_,_,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,_,_,_],
    [_,_,_,shadow,'#1f2937','#1f2937',shadow,'#1f2937','#1f2937',shadow,'#1f2937','#1f2937',shadow,_,_,_],
    [_,_,_,shadow,'#1f2937','#1f2937',shadow,'#1f2937','#1f2937',shadow,'#1f2937','#1f2937',shadow,_,_,_],
    [_,_,_,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,_,_,_],
    [_,_,shadow,'#1f2937',shadow,'#1f2937',shadow,'#1f2937',shadow,'#1f2937',shadow,'#1f2937',shadow,_,_,_],
    [_,_,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,_,_,_],
    [_,_,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,_,_,_],
    [_,_,shadow,'#1f2937',shadow,'#1f2937',shadow,'#1f2937',shadow,'#1f2937',shadow,'#1f2937',shadow,_,_,_],
    [_,_,_,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,_,_,_],
    [_,_,_,_,shadow,shadow,shadow,shadow,shadow,shadow,shadow,shadow,_,_,_,_],
    [_,_,_,_,_,_,shadow,shadow,shadow,shadow,shadow,_,_,_,_,_],
    [_,_,_,_,_,_,shadow,shadow,shadow,shadow,shadow,_,_,_,_,_],
  ]

  const up_walk = [shiftLegs(up_idle, 1), up_idle, shiftLegs(up_idle, -1), up_idle]

  return {
    idle: [down_idle, left_idle, right_idle, up_idle],
    walk: [
      [down_walk_0, down_walk_1, down_walk_2, down_walk_3],
      left_walk,
      right_walk,
      up_walk,
    ],
    type: [down_type_0, left_idle, mirrorHoriz(left_idle), up_idle],
  }
}

// ── 工具函数 ────────────────────────────────────────────────────

function shiftLegs(sprite: SpriteData, direction: 1 | -1): SpriteData {
  const legRows = sprite.slice(12)
  const topRows = sprite.slice(0, 12)
  // Swap leg pixels: shift inner columns
  return [
    ...topRows,
    ...legRows.map(row => {
      const newRow = [...row]
      // Shift pixels at column 7-8
      const tmp = newRow[7]
      newRow[7] = newRow[8]
      newRow[8] = tmp
      return newRow
    }),
  ]
}

function mirrorHoriz(sprite: SpriteData): SpriteData {
  return sprite.map(row => {
    const w = row.length
    const mid = Math.floor(w / 2)
    const left = row.slice(0, mid).reverse()
    const right = row.slice(mid)
    return [...left, ...right]
  })
}

// ── 气泡精灵 ────────────────────────────────────────────────────

/** Speech bubble: 32×16 pixel cloud shape */
export const BUBBLE_SPRITE: SpriteData = (() => {
  const B = 'rgba(0,0,0,0.85)'
  const rows: string[][] = []
  for (let r = 0; r < 16; r++) {
    const row = new Array(32).fill('') as string[]
    if (r === 0) {
      // Top rounded
      for (let c = 8; c < 24; c++) row[c] = B
    } else if (r < 10) {
      for (let c = 0; c < 32; c++) row[c] = B
    } else if (r === 10) {
      // Bubble tail left
      for (let c = 0; c < 10; c++) row[c] = B
      for (let c = 10; c < 26; c++) row[c] = B
    } else if (r === 11) {
      for (let c = 0; c < 8; c++) row[c] = B
      for (let c = 8; c < 20; c++) row[c] = B
    } else {
      for (let c = 0; c < 6; c++) row[c] = B
    }
    rows.push(row)
  }
  return rows
})()

// ── 家具精灵 (工位/桌子) ─────────────────────────────────────────

/** Desk sprite: 32×32 (2×2 tiles) */
export const DESK_SPRITE: SpriteData = (() => {
  const W = '#8B6914'   // wood
  const L = '#A07828'   // lighter
  const S = '#B8922E'   // surface
  const D = '#5a3a10'   // dark edge
  const rows: string[][] = []
  for (let r = 0; r < 32; r++) {
    const row = new Array(32).fill('') as string[]
    if (r === 0 || r === 31) {
      for (let c = 0; c < 32; c++) row[c] = r === 0 ? W : D
    } else if (r === 1 || r === 15) {
      row[0] = W; row[31] = D
      for (let c = 1; c < 31; c++) row[c] = r === 1 ? L : W
    } else if (r < 15) {
      row[0] = W; row[31] = D
      for (let c = 1; c < 31; c++) row[c] = S
    } else if (r === 30) {
      row[0] = D; row[31] = D
      for (let c = 1; c < 31; c++) row[c] = D
    } else {
      row[0] = D; row[31] = D
      for (let c = 1; c < 31; c++) row[c] = '#4a3210'
    }
    rows.push(row)
  }
  return rows
})()

/** Monitor sprite: 16×12 */
export const MONITOR_SPRITE: SpriteData = (() => {
  const frame = '#374151'
  const screen = '#0ea5e9'
  const stand = '#6b7280'
  const rows: string[][] = []
  for (let r = 0; r < 12; r++) {
    const row = new Array(16).fill('') as string[]
    if (r === 0) {
      for (let c = 2; c < 14; c++) row[c] = frame
    } else if (r < 9) {
      row[1] = frame; row[14] = frame
      for (let c = 2; c < 14; c++) row[c] = screen
    } else if (r === 9) {
      for (let c = 2; c < 14; c++) row[c] = frame
      row[7] = stand; row[8] = stand
    } else if (r === 10) {
      for (let c = 5; c < 11; c++) row[c] = stand
    } else {
      for (let c = 6; c < 10; c++) row[c] = stand
    }
    rows.push(row)
  }
  return rows
})()
