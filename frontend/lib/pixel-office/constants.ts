/** PixelOffice engine constants.
 *
 * Physics, timing, and rendering constants.
 * Based on OpenClaw-bot-review/lib/pixel-office/constants.ts
 */

// ── Physics ───────────────────────────────────────────────────
export const WALK_SPEED_PX_PER_SEC = 80
export const DEFAULT_ZOOM = 2        // 2x pixel scale

// ── Animation timing ──────────────────────────────────────────
export const WALK_FRAME_DURATION_SEC  = 0.12
export const TYPE_FRAME_DURATION_SEC  = 0.4
export const IDLE_BLINK_SEC          = 3.0

// ── Seat & Movement ───────────────────────────────────────────
export const CHARACTER_SITTING_OFFSET_PX = 4  // visual offset when seated
export const SEAT_REST_MIN_SEC = 8
export const SEAT_REST_MAX_SEC = 30
export const WANDER_PAUSE_MIN_SEC = 3
export const WANDER_PAUSE_MAX_SEC = 12

// ── Matrix effect (spawn/despawn) ─────────────────────────────
export const MATRIX_EFFECT_DURATION = 0.3

// ── Bubble ────────────────────────────────────────────────────
export const BUBBLE_VERTICAL_OFFSET_PX = 2
export const BUBBLE_DURATION_SEC = 4.0

// ── Rendering ────────────────────────────────────────────────
export const FALLBACK_FLOOR_COLOR = '#2a2a4a'
export const WALL_COLOR = '#1a1a2e'
export const GRID_LINE_COLOR = 'rgba(255,255,255,0.03)'

// ── Agent palette ─────────────────────────────────────────────
// Each agent gets a unique color palette for character tinting
export const AGENT_PALETTES = [
  '#6366f1',  // 0: indigo - 分析型 (蓝紫)
  '#f97316',  // 1: orange  - 策划型 (橙)
  '#22c55e',  // 2: green   - 创作型 (绿)
  '#a855f7',  // 3: purple  - 审核型 (紫)
  '#3b82f6',  // 4: blue    - 备用
  '#ec4899',  // 5: pink    - 备用
]

// ── Default character walk speed ───────────────────────────────
export const DEFAULT_CHAR_SPEED = WALK_SPEED_PX_PER_SEC
