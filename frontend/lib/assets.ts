/** Centralized asset paths for HotClaw pixel art.
 * True 16-bit pixel art game style sprite sheet.
 *
 * Sprite sheet layout (PixelOfficeAssets.png = 384x160):
 *   Row 0 (idle):  6 agent characters in idle pose
 *   Row 1 (work):   Same 6 agents in working pose
 *   Each cell: 64x80 px
 *
 * Agent mapping (6 backend agents → 6 sprite types):
 *   profile_agent         → 分析型 (蓝紫, col=0)
 *   hot_topic_agent      → 热点型 (橙,   col=1)
 *   topic_planner_agent  → 策划型 (绿,   col=2)
 *   title_generator_agent → 标题型 (红,   col=3)
 *   content_writer_agent  → 创作型 (紫,   col=4)
 *   audit_agent          → 审核型 (黄,   col=5)
 */

// === Room scene backgrounds ===
export const SCENES = {
  /** Large multi-room: sofa + bookshelf + workstations + server rack */
  large: "/assets/LargePixelOffice.png",
  /** Medium single-room editorial office */
  medium: "/assets/PixelOffice.png",
} as const;

// === Sprite sheet (agents + props + UI in one image) ===
export const SPRITESHEET = {
  /** Main sprite sheet: 384x160, 6 cols x 2 rows, each cell 64x80 */
  main: "/assets/PixelOfficeAssets.png",
  cellW: 64,
  cellH: 80,
} as const;

// === Agent sprite cell positions in sprite sheet ===
// Each agent occupies one column, 2 rows (idle + work)
export const AGENTS = {
  /** 蓝紫 - 分析型: profile */
  analysis: { col: 0, row: 0 },
  /** 橙 - 热点型: hot_topic */
  hotTopic: { col: 1, row: 0 },
  /** 绿 - 策划型: topic_planner */
  planning: { col: 2, row: 0 },
  /** 红 - 标题型: title_generator */
  title: { col: 3, row: 0 },
  /** 紫 - 创作型: content_writer */
  creation: { col: 4, row: 0 },
  /** 黄 - 审核型: audit */
  audit: { col: 5, row: 0 },
} as const;

// === Individual Agent sprite images (transparent PNG) ===
export const AGENT_SPRITES = {
  /** 蓝紫 - 分析型: profile */
  analysis: "/assets/agent_01_analysis.png",
  /** 橙 - 热点型: hot_topic */
  hotTopic: "/assets/agent_02_planning.png",
  /** 绿 - 策划型: topic_planner */
  planning: "/assets/agent_03_creation.png",
  /** 红 - 标题型: title_generator */
  title: "/assets/agent_04_title.png",
  /** 紫 - 创作型: content_writer */
  creation: "/assets/agent_05_content.png",
  /** 黄 - 审核型: audit */
  audit: "/assets/agent_06_audit.png",
} as const;

// === Agent role → individual sprite image mapping ===
export const AGENT_SPRITE_URL: Record<string, string> = {
  profile_agent:          AGENT_SPRITES.analysis,
  hot_topic_agent:       AGENT_SPRITES.hotTopic,
  topic_planner_agent:   AGENT_SPRITES.planning,
  title_generator_agent: AGENT_SPRITES.title,
  content_writer_agent:  AGENT_SPRITES.creation,
  audit_agent:           AGENT_SPRITES.audit,
};

// === Individual effect & UI sprites ===
export const SPRITES = {
  fxExclamation: "/assets/06_hotclaw_fx_exclamation.png",
  uiGear: "/assets/07_hotclaw_ui_settings_gear.png",
  agentIdle: "/assets/02_hotclaw_agent_idle.png",
  agentWork: "/assets/03_hotclaw_agent_work.png",
  agentAlert: "/assets/05_hotclaw_agent_alert.png",
} as const;

// === Agent role → sprite cell mapping ===
export const AGENT_CELL: Record<string, { col: number; row: number }> = {
  // Analysis type (蓝紫)
  profile_agent:          AGENTS.analysis,
  // Hot topic type (橙)
  hot_topic_agent:       AGENTS.hotTopic,
  // Planning type (绿)
  topic_planner_agent:   AGENTS.planning,
  // Title type (红)
  title_generator_agent: AGENTS.title,
  // Creation type (紫)
  content_writer_agent:  AGENTS.creation,
  // Audit type (黄)
  audit_agent:           AGENTS.audit,
};

/** Compute background-position for a sprite cell. */
export function getSpritePosition(col: number, row: number): string {
  return `-${col * SPRITESHEET.cellW}px -${row * SPRITESHEET.cellH}px`;
}

/** Get sprite cell for a backend agent_id (idle state). */
export function getAgentCell(agentId: string): { col: number; row: number } {
  return AGENT_CELL[agentId] ?? AGENTS.analysis;
}

/** Get generic status sprite path. */
export function getStatusSprite(
  status: "pending" | "running" | "completed" | "failed" | "skipped"
): string {
  switch (status) {
    case "running":
      return SPRITES.agentWork;
    case "failed":
      return SPRITES.agentAlert;
    default:
      return SPRITES.agentIdle;
  }
}
